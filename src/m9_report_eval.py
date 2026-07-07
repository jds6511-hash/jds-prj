"""M9 AAR 평가: Coverage(LLM-judge 이진) + Groundedness(G-Eval 3단계 CoT).
cites==[] 문장은 judge 없이 자동 ungrounded. [DESIGN_SPEC 4-9, v2 14·17장]"""
import argparse, json, random, re
from pathlib import Path
import common
from llm import make_llm
from m6_evaluate import load_queries

_GROUNDED_PROMPT = """당신은 영상 리포트 검증자입니다. 아래 3단계로 판정하세요.
① 검증 대상 문장이 주장하는 내용을 먼저 요약하라.
② 인용된 세그먼트들의 실제 내용(자막·캡션)을 요약하라.
③ 두 내용이 일치하는지 근거를 들어 판정하라.
확신이 없으면 반드시 false로 보수 판정하라.
마지막 줄에 JSON으로만 답하라: {{"match": true}} 또는 {{"match": false}}

검증 대상 문장: {sentence}

인용된 세그먼트 내용:
{segments}
"""

_COVERAGE_PROMPT = """아래 리포트가 다음 세그먼트의 내용을 언급했는지 판정하세요.
확신이 없으면 반드시 false로 보수 판정하라.
마지막 줄에 JSON으로만 답하라: {{"match": true}} 또는 {{"match": false}}

세그먼트 (idx {idx}): subtitle: "{subtitle}" caption: "{caption}"

리포트:
{report}
"""


def _parse_verdict(text: str) -> bool:
    """judge 출력에서 최종 판정 파싱. 실패 시 보수적으로 False. [v2 17-4]

    값이 따옴표로 감싸인 변형("match": "true")도 허용. [m8m9-prompt-critique B-5]
    """
    matches = re.findall(r'"match"\s*:\s*"?(true|false)"?', text, re.IGNORECASE)
    return matches[-1].lower() == "true" if matches else False


def _parse_ok(text: str) -> bool:
    """judge 출력에서 판정 필드가 파싱 가능했는지 여부. truncation 편향 진단용.
    [m8m9-prompt-critique B-6]"""
    return bool(re.search(r'"match"', text, re.IGNORECASE))


def _fmt_segs(segs) -> str:
    return "\n".join(f'[seg#{s["idx"]}] subtitle: "{s["subtitle"]}" '
                     f'caption: "{s["caption"]}"' for s in segs)


def _grounded_prompt(sentence: dict, cited_segments: list[dict]) -> str:
    return _GROUNDED_PROMPT.format(sentence=sentence["text"],
                                   segments=_fmt_segs(cited_segments))


def judge_grounded(sentence: dict, cited_segments: list[dict], judge) -> bool:
    """복수 인용은 전부 함께 제공(개별 대조 시 정당한 종합 서술이 오분류됨). [14-2]"""
    return _parse_verdict(judge(_grounded_prompt(sentence, cited_segments)))


def judge_coverage(report_text: str, segment: dict, judge) -> bool:
    prompt = _COVERAGE_PROMPT.format(idx=segment["idx"], subtitle=segment["subtitle"],
                                     caption=segment["caption"], report=report_text)
    return _parse_verdict(judge(prompt))


def eval_report(report: dict, segments: list[dict], gt_seg_indices: list[int],
                judge) -> dict:
    by_idx = {s["idx"]: s for s in segments}
    per_sentence = []
    for s in report["sentences"]:
        if not s["cites"]:
            grounded, parse_ok = False, True             # 자동 ungrounded, judge 호출 없음
        else:
            raw = judge(_grounded_prompt(s, [by_idx[c] for c in s["cites"]]))
            grounded, parse_ok = _parse_verdict(raw), _parse_ok(raw)
        per_sentence.append({"sent_id": s["sent_id"], "cites": s["cites"],
                             "grounded": grounded, "judge_parse_ok": parse_ok})
    report_text = "\n".join(s["text"] for s in report["sentences"])
    per_gt = [{"seg_idx": i, "covered": judge_coverage(report_text, by_idx[i], judge)}
              for i in sorted(set(gt_seg_indices))]
    return {
        "groundedness_rate": round(
            sum(p["grounded"] for p in per_sentence) / max(len(per_sentence), 1), 4),
        "coverage_rate": round(
            sum(p["covered"] for p in per_gt) / max(len(per_gt), 1), 4),
        "per_sentence": per_sentence, "per_gt_segment": per_gt}


def check_judge_config(cfg: dict) -> None:
    """judge 모델 규정 [v2 17-6]: 다른 패밀리 1순위, 동일 시 same_model_judge 명시 필수."""
    if not cfg.get("judge_model"):
        raise ValueError("judge_model 미지정 — report_model과 다른 패밀리로 지정하라 [v2 17-6]")
    if cfg["judge_model"] == cfg["report_model"] and not cfg.get("same_model_judge"):
        raise ValueError("report_model과 judge_model이 동일 — 의도라면 config에 "
                         "same_model_judge: true를 명시하라 [v2 17-6]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--queries", default="data/queries/queries.jsonl")
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    check_judge_config(cfg)
    wdir = common.work_dir(cfg, args.video_id)
    doc = common.load_segments(wdir / "segments.json", require=["subtitle", "caption"])
    report = json.loads((wdir / "report.json").read_text(encoding="utf-8"))
    n = doc["n_segments"]
    for s in report["sentences"]:                       # 검증 포인트 [4-9]
        assert all(0 <= c < n for c in s["cites"]), f"cites 범위 위반: {s}"

    test_qs = [q for q in load_queries(args.queries)
               if q["split"] == "test" and q["video_id"] == args.video_id]
    gt_idx = [i for q in test_qs for i in q["gt_seg_idx"]]

    judge = make_llm(cfg["judge_model"], max_new_tokens=512)
    out = eval_report(report, doc["segments"], gt_idx, judge)
    rdir = Path(cfg["paths"]["results"]); rdir.mkdir(exist_ok=True)
    common.atomic_write_json(rdir / "report_eval.json",
                             {"video_id": args.video_id,
                              "judge_model": cfg["judge_model"], **out})
    print(f"M9 완료: coverage={out['coverage_rate']} groundedness={out['groundedness_rate']}")

    if cfg.get("same_model_judge"):                     # 사람 스팟체크 자동 추출 [4-9]
        rng = random.Random(cfg["seed"])
        pool = [s for s in report["sentences"]]
        sample = rng.sample(pool, min(cfg["human_check_n"], len(pool)))
        common.atomic_write_json(rdir / "human_check_sample.json", sample)
        print(f"same_model_judge=true → 사람 스팟체크 {len(sample)}문장 추출")


if __name__ == "__main__":
    main()

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
    _parse_verdict와 동일한 값 패턴을 요구 — 키만 있고 값이 비정형('"match": maybe')인
    출력을 파싱 성공으로 과대보고하지 않도록 [리뷰 2026-07-11 Minor]."""
    return bool(re.search(r'"match"\s*:\s*"?(true|false)"?', text, re.IGNORECASE))


def _clean_caption(caption: str) -> str:
    """오염된 캡션을 judge 판정 근거로 그대로 쓰지 않도록 대체 — M8 _fmt_seg와 동일 필터.
    안 그러면 오염된 데이터가 grounded 판정의 기준 자체가 돼 검증이 무력화된다."""
    return "(캡션 품질 문제로 제외됨)" if common.is_corrupted_caption(caption) else caption


def _fmt_segs(segs) -> str:
    return "\n".join(f'[seg#{s["idx"]}] subtitle: "{s["subtitle"]}" '
                     f'caption: "{_clean_caption(s["caption"])}"' for s in segs)


def _grounded_prompt(sentence: dict, cited_segments: list[dict]) -> str:
    return _GROUNDED_PROMPT.format(sentence=sentence["text"],
                                   segments=_fmt_segs(cited_segments))


def judge_grounded(sentence: dict, cited_segments: list[dict], judge) -> bool:
    """복수 인용은 전부 함께 제공(개별 대조 시 정당한 종합 서술이 오분류됨). [14-2]"""
    return _parse_verdict(judge(_grounded_prompt(sentence, cited_segments)))


def judge_coverage(report_text: str, segment: dict, judge) -> tuple[bool, bool]:
    """반환: (covered, judge_parse_ok) — groundedness와 동일하게 truncation 진단 병기
    [리뷰 2026-07-11 Minor]."""
    prompt = _COVERAGE_PROMPT.format(idx=segment["idx"], subtitle=segment["subtitle"],
                                     caption=_clean_caption(segment["caption"]), report=report_text)
    raw = judge(prompt)
    return _parse_verdict(raw), _parse_ok(raw)


def eval_report(report: dict, segments: list[dict], gt_seg_indices: list[int],
                judge) -> dict:
    by_idx = {s["idx"]: s for s in segments}
    # gt 인덱스 범위 검증 — judge 비용을 다 치른 뒤 KeyError로 죽는 경로 차단
    # (m6 validate_gt_seg_idx의 대응물) [리뷰 2026-07-11 Major]
    bad_gt = [i for i in gt_seg_indices if i not in by_idx]
    assert not bad_gt, f"gt_seg_idx 범위 밖 인덱스 {bad_gt} — 라벨/seg_len 불일치 가능성"
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
    per_gt = []
    for i in sorted(set(gt_seg_indices)):
        covered, parse_ok = judge_coverage(report_text, by_idx[i], judge)
        per_gt.append({"seg_idx": i, "covered": covered, "judge_parse_ok": parse_ok})
    # gt_seg_indices가 비면(예: video_id에 test 질의가 없는 dev 영상에 잘못 실행) 0.0으로
    # 조용히 묻히지 않도록 null로 구분 — "커버리지 0%"와 "측정 불가"는 다른 상태다.
    coverage_rate = round(sum(p["covered"] for p in per_gt) / len(per_gt), 4) if per_gt else None
    return {
        "groundedness_rate": round(
            sum(p["grounded"] for p in per_sentence) / max(len(per_sentence), 1), 4),
        "coverage_rate": coverage_rate,
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
    doc = common.load_segments(wdir / "segments.json", require=["subtitle", "caption"],
                               seg_len=cfg["seg_len_sec"])
    report = json.loads((wdir / "report.json").read_text(encoding="utf-8"))
    n = doc["n_segments"]
    for s in report["sentences"]:                       # 검증 포인트 [4-9]
        assert all(0 <= c < n for c in s["cites"]), f"cites 범위 위반: {s}"

    test_qs = [q for q in load_queries(args.queries)
               if q["split"] == "test" and q["video_id"] == args.video_id]
    gt_idx = [i for q in test_qs for i in q["gt_seg_idx"]]

    judge = make_llm(cfg["judge_model"], max_new_tokens=512,
                     load_4bit=cfg.get("llm_4bit", False))
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

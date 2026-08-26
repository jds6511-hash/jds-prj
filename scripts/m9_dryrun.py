"""M9 예비 점검 — **공식 test를 열지 않고** M9 배선 전체를 돌린다.

M9는 `split=="test"` 질의만 읽으므로 **실행 자체가 test 접촉**이다. 그래서 실제 test로
"한 번 돌려보고 고치는" 것이 불가능하다. 배선 결함은 test를 연 뒤에 발견되면 그 실행이
낭비되고, 다시 여는 것은 또 하나의 승인 사건이다.

이 스크립트는 **합성 fixture**(임시 디렉터리의 가짜 영상 1편·질의·리포트)로 같은 경로를
지난다.

```
확인하는 것
  freeze manifest 대조          동결 이후 코드·프롬프트가 바뀌었는가
  구조 validator                schema · video_id · n_segments · 인용 범위 · 추적 가능성
  judge 배선                    프롬프트 조립 · 파싱 · parse_ok 기록 (스텁 judge)
  집계·결과 스키마              coverage/groundedness · coverage_by_type · per_video
  결과 파일 경로                영상별 분리(고정 이름이면 마지막 것만 남는다)

확인하지 않는 것
  실제 test 수치                 열지 않는다
  judge 품질                     스텁이다 — 판정 정확도를 보는 도구가 아니다
```

`--freeze` 를 주면 동결 manifest 대조까지 한다. 통과하면 `M9_READY_FOR_TEST_OPENING`의
기술적 전제(배선)가 충족된 것이고, **그 자체가 test 개방 승인은 아니다.**
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                    # noqa: E402
import m9_report_eval as M9                                      # noqa: E402
from aar_view import TraceError, build as trace_build            # noqa: E402

FIXTURE_VIDEO = "dryrun_synthetic_video"     # 실제 영상 이름과 겹치지 않게 둔다
N_SEG = 6


class StubJudge:
    """정해진 순서로 판정을 돌려주는 가짜 judge. **품질 평가용이 아니다.**

    `make_llm`을 부르지 않는다 — GPU도, 모델 다운로드도 없어야 예비 점검이 성립한다.
    """
    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls = []

    def __call__(self, prompt: str, **kw) -> str:
        self.calls.append(prompt)
        v = self.verdicts.pop(0) if self.verdicts else True
        if v is None:                      # 파싱 실패 재현
            return "판단하기 어렵습니다"
        return json.dumps({"value": bool(v)}, ensure_ascii=False)


def write_fixture(root: Path) -> dict:
    """segments·report·queries 3종을 만든다. queries의 split은 "test"다 —
    **합성 영상**이므로 실제 test 39건과 무관하다."""
    wdir = root / "work" / FIXTURE_VIDEO
    wdir.mkdir(parents=True)
    segments = [{"idx": i, "start": i * 5, "end": i * 5 + 5,
                 "subtitle": f"합성 자막 {i}", "caption": f"합성 캡션 {i}",
                 "motion_score": 0.5, "is_static": False,
                 "rep_frame": f"frames/seg_{i:04d}.jpg"} for i in range(N_SEG)]
    doc = {"video_id": FIXTURE_VIDEO, "n_segments": N_SEG, "segments": segments}
    common.save_segments(wdir / "segments.json", doc)

    # 두 validator의 기준이 다르다 — 그래서 리포트를 두 벌 만든다.
    #   aar_view(추적 뷰)  인용 없는 문장을 **거부**한다("추적 불가한 주장을 남기지 않는다")
    #   M9(평가)          인용 없는 문장을 judge 호출 없이 **자동 ungrounded로 계수**한다
    # 어느 쪽이 옳은지는 이 스크립트가 정하지 않는다(프로토콜 문서 §충돌 표에 기록).
    report = {
        "video_id": FIXTURE_VIDEO, "schema_version": 2,
        "model": "stub", "map_chunk_size": 60,
        "sentences": [
            {"sent_id": 0, "text": "합성 장면이 이어진다 [seg#0].", "cites": [0]},
            {"sent_id": 1, "text": "두 번째 동작이 나타난다 [seg#2, seg#3].", "cites": [2, 3]},
        ],
        "raw_output": "합성", "provenance": {"role": "report", "schema_version": 2},
    }
    common.atomic_write_json(wdir / "report.json", report)

    with_uncited = dict(report)
    with_uncited["sentences"] = report["sentences"] + [
        {"sent_id": 2, "text": "근거 없는 문장이다.", "cites": []}]
    common.atomic_write_json(wdir / "report_with_uncited.json", with_uncited)

    queries = [
        {"query_id": "dr_q01", "video_id": FIXTURE_VIDEO, "text": "합성 질의 1",
         "type": "자막형", "gt_start": 0.0, "gt_end": 5.0, "gt_seg_idx": [0],
         "split": "test"},
        {"query_id": "dr_q02", "video_id": FIXTURE_VIDEO, "text": "합성 질의 2",
         "type": "장면형", "gt_start": 10.0, "gt_end": 20.0, "gt_seg_idx": [2, 3],
         "split": "test"},
        {"query_id": "dr_q03", "video_id": FIXTURE_VIDEO, "text": "합성 질의 3",
         "type": "복합형", "gt_start": 25.0, "gt_end": 30.0, "gt_seg_idx": [5],
         "split": "test"},
    ]
    qpath = root / "queries_dryrun.jsonl"
    qpath.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in queries),
                     encoding="utf-8")
    return {"wdir": wdir, "queries": qpath, "report": report,
            "report_with_uncited": with_uncited, "doc": doc}


def run(root: Path, freeze_manifest: Path | None = None) -> dict:
    fx = write_fixture(root)
    out = {"fixture_video": FIXTURE_VIDEO, "n_segments": N_SEG, "checks": {}}

    # ① 동결 대조 — 동결 이후 코드·프롬프트가 바뀌었으면 여기서 걸린다
    if freeze_manifest is not None:
        import m8_freeze
        man = json.loads(Path(freeze_manifest).read_text(encoding="utf-8"))
        diffs = m8_freeze.verify(man)
        out["checks"]["freeze_match"] = not diffs
        out["freeze_id"] = man.get("freeze_id")
        out["freeze_diffs"] = diffs
        if man.get("test_opened") is not False:
            out["checks"]["freeze_test_unopened"] = False
        else:
            out["checks"]["freeze_test_unopened"] = True

    # ② 구조 validator — 사람·judge 판정 전에 fail-closed로 걸러야 하는 층
    doc = trace_build(fx["wdir"] / "report.json", fx["wdir"] / "segments.json")
    out["checks"]["structural_valid"] = True
    out["traceability"] = {"n_sentences": doc["n_sentences"],
                           "cited_segments": doc["cited_segments"],
                           "index_consistency": doc["index_consistency"]}

    # 잘못된 리포트는 반드시 거부돼야 한다 — 통과하면 validator가 없는 것과 같다
    bad = dict(fx["report"])
    bad["sentences"] = [{"sent_id": 0, "text": "범위 밖 인용", "cites": [N_SEG + 5]}]
    bad_path = fx["wdir"] / "report_bad.json"
    common.atomic_write_json(bad_path, bad)
    try:
        trace_build(bad_path, fx["wdir"] / "segments.json")
        out["checks"]["structural_rejects_bad_citation"] = False
    except TraceError:
        out["checks"]["structural_rejects_bad_citation"] = True

    # ③ judge 배선 + 집계 — 스텁 judge로 M9 본 함수를 그대로 지난다
    queries = M9.load_queries(fx["queries"])
    test_qs = [q for q in queries if q["split"] == "test"
               and q["video_id"] == FIXTURE_VIDEO]
    gt_idx = [i for q in test_qs for i in q["gt_seg_idx"]]
    gt_types: dict = {}
    for q in test_qs:
        for i in q["gt_seg_idx"]:
            gt_types.setdefault(i, []).append(q["type"])
    judge = StubJudge([True, False, None, True, False, True, True, False])
    # 인용 없는 문장이 든 판을 쓴다 — M9의 "judge 호출 없이 ungrounded" 경로를 지나야 한다
    res = M9.eval_report(fx["report_with_uncited"], fx["doc"]["segments"], gt_idx,
                         judge, gt_types=gt_types)
    out["checks"]["judge_called"] = bool(judge.calls)
    out["checks"]["uncited_sentence_is_ungrounded"] = (
        res["per_sentence"][2]["grounded"] is False
        and res["per_sentence"][2]["cites"] == [])
    out["checks"]["parse_failure_recorded"] = any(
        p["judge_parse_ok"] is False for p in res["per_sentence"])
    out["checks"]["coverage_by_type_present"] = "coverage_by_type" in res
    out["checks"]["rates_are_numbers"] = all(
        isinstance(res[k], float) for k in ("coverage_rate", "groundedness_rate"))
    out["aggregate"] = {k: res[k] for k in
                        ("coverage_rate", "groundedness_rate", "coverage_by_type")}

    # ④ 결과 경로가 영상별로 분리되는가 — 고정 이름이면 마지막 영상만 남는다
    rdir = root / "results"
    rdir.mkdir(exist_ok=True)
    p_a, h_a = M9.result_paths(rdir, "video_a")
    p_b, h_b = M9.result_paths(rdir, "video_b")
    out["checks"]["result_paths_per_video"] = (p_a != p_b and h_a != h_b)

    # ⑤ 결과 스키마 — 필수 키가 다 있는가
    required = ("coverage_rate", "groundedness_rate", "per_sentence", "per_gt_segment")
    out["checks"]["result_schema_complete"] = all(k in res for k in required)

    out["ok"] = all(out["checks"].values())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", help="m8_freeze_manifest 경로 — 주면 동결 대조까지 한다")
    ap.add_argument("--out", help="결과 JSON 경로(선택)")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        res = run(Path(td), Path(a.freeze) if a.freeze else None)
    for k, v in res["checks"].items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"\nM9 배선 예비 점검: {'PASS' if res['ok'] else 'FAIL'} "
          f"(공식 test는 열지 않았다)")
    if a.out:
        common.atomic_write_json(a.out, res)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

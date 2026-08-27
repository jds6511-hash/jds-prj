"""C1·C2·C3 관문 집행 — 규격 `docs/finalization/M8_GATE_SPEC_FREEZE_2026-08-27.md`.

지표 계산은 `m8_metrics`·`m8_c1`에 있고, 이 모듈은 **분모를 어디서 읽는가**와
**무엇을 판정에 쓰는가**를 강제한다.

```
분모   `load_reference`로 FROZEN_*.json에서만 읽는다. draft CSV는 읽지 않는다
       (동결 뒤 CSV가 바뀌면 해시 불일치로 fail-closed)
C1    m8_c1 3-state. UNCLEAR는 통과가 아니다
C3    영상별 = 리포트 문장 수 / 정답 사건 수. 패널 집계 = MAX. PASS = MAX <= 2.0
C2    주지표 `event_temporal_alignment` 중앙값 >= 0.70. θ별 recall 3종은
      전부 계산해 보고하되 **판정에는 쓰지 않는다**(넘기면 거부)
```

`Redundancy`·`overmerge`·`spurious_event`는 C3에 합치지 않는다(규격 §2-3) —
진단으로만 보고한다.

사용:
    python scripts/m8_gates.py --c2-metric <지표명>        # 리포트가 생긴 뒤에만
"""
import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                      # noqa: E402
import m8_c1                                                       # noqa: E402
import m8_metrics as M                                             # noqa: E402
from event_inventory_kit import OUT, load_reference                 # noqa: E402

PANEL_MANIFEST = ROOT / "docs" / "finalization" / "m8_c2_panel_manifest_2026-08-27.json"
C3_STATISTIC = "max"          # 규격 §2-1에서 동결. 결과를 보고 바꾸지 않는다
C3_THRESHOLD = 2.0
# 규격 §2A에서 동결(2026-08-27, M8 출력 0건 시점). 보충 §3-3의 **주지표**다.
# θ 기반 recall은 "세 값을 모두 보고하고 하나를 고르지 않는다"고 동결돼 있어
# 판정 지표로 쓸 수 없다 — 그래서 후보가 아니라 상수다.
C2_METRIC = "event_temporal_alignment"
C2_THRESHOLD = 0.70
# 진단 전용. C2 PASS/FAIL에 들어가지 않는다.
C2_DIAGNOSTIC_PREFIX = "temporal_event_recall@"

DIAGNOSTICS_NOTE = (
    "Redundancy·overmerge·spurious_event는 관문이 아니라 진단이다(규격 §2-3). "
    "Redundancy는 아직 구현되지 않았다 — 미매칭 수를 후보로만 보고한다.")


class GateRunError(RuntimeError):
    """판정에 필요한 산출물이 없을 때. **없는 것을 0으로 세지 않는다.**"""


def reference_events(video_id: str, out_dir=None, csv_path=None) -> list:
    """정답 사건 목록. **동결본에서만** 읽는다.

    `csv_path`를 넘기면 동결 이후 CSV가 바뀌었는지도 함께 검사한다 — 그게
    draft가 우회로 들어오는 것을 막는 자리다.
    """
    return load_reference(video_id, out_dir=out_dir, csv_path=csv_path)


def video_compression(rep: dict, refs: list):
    """사전등록 §2-2 그대로 — 리포트 문장 수 / 정답 사건 수.

    구조 경로에서는 사건 1개 = 문장 1개(`events_to_sentences`)라, 보충 사전등록의
    "생성 사건 수 ÷ 정답 사건 수"와 **값이 같다.** 두 문구가 갈리지 않는다.
    """
    return M.compression(len(rep.get("sentences") or []), len(refs))


def c2_candidates(rep: dict, refs: list) -> dict:
    """per-video 값 전부. 판정에 쓰는 것은 `C2_METRIC` 하나이고 나머지는 진단이다."""
    gens = [e for e in (rep.get("events") or []) if e.get("span")]
    out = {"event_temporal_alignment": M.event_temporal_alignment(refs, gens)}
    out.update(M.temporal_event_recall(refs, gens))
    return out


def alignment_diagnostics(rep: dict, refs: list, n_segments: int) -> dict:
    """진단. 정렬 유형(`EVENT_ALIGNMENT_TYPES`)은 사람이 붙이는 라벨이라
    여기서는 **기계로 셀 수 있는 미매칭 수만** 후보로 낸다."""
    gens = [e for e in (rep.get("events") or []) if e.get("span")]
    m = M.match_events(refs, gens)
    matched = {j for j in m.values() if j is not None}
    return {"unmatched_reference_events": sum(1 for v in m.values() if v is None),
            "unmatched_generated_events": len(gens) - len(matched),
            "timeline_span_coverage": M.timeline_span_coverage(gens, n_segments),
            **M.structural_summary(rep, n_segments)}


def video_row(video_id: str, wdir, n_segments: int, out_dir=None,
              csv_path=None) -> dict:
    """영상 하나의 판정 입력. canonical `report.json`만 읽는다."""
    p = Path(wdir) / "report.json"
    if not p.is_file():
        raise GateRunError(f"{video_id}: report.json이 없다 — 없는 것을 0으로 "
                           f"세지 않는다 ({p})")
    rep = json.loads(p.read_text(encoding="utf-8"))
    refs = reference_events(video_id, out_dir=out_dir, csv_path=csv_path)
    finding = m8_c1.inspect_video(rep)
    return {"video_id": video_id,
            "n_sentences": len(rep.get("sentences") or []),
            "n_reference_events": len(refs),
            "c1_finding": finding, "c1_status": m8_c1.video_status(finding),
            "compression": video_compression(rep, refs),
            "c2_candidates": c2_candidates(rep, refs),
            "diagnostics": alignment_diagnostics(rep, refs, n_segments)}


def panel_verdict(rows: list, c2_metric: str | None = None) -> dict:
    """패널 판정. C2 지표는 규격 §2A에서 동결된 **주지표**다.

    원 사전등록 §2-3은 "Event Recall 중앙값"이라 이름만 적었고, 보충 §3-3이 그 자리를
    주지표 `event_temporal_alignment`(연속값)와 θ별 부지표로 갈랐다. 부지표는
    "θ 세 값을 모두 보고하고 하나를 고르지 않는다"고 동결돼 있으므로, θ recall을
    판정에 쓰는 것은 그 문구와 직접 충돌한다 — 그래서 여기서 거부한다.

    미매칭 정답 사건은 **IoU 0으로 평균에 들어간다**(보충 §3-3 "매칭 실패 = 0").
    matched만 평균내면 값이 달라지므로 그 정의를 바꾸지 않는다.
    """
    names = sorted({k for r in rows for k in (r.get("c2_candidates") or {})})
    c2_metric = C2_METRIC if c2_metric is None else c2_metric
    if c2_metric.startswith(C2_DIAGNOSTIC_PREFIX):
        raise M.GateSpecError(
            f"{c2_metric}는 **진단 전용**이다 — 보충 §3-3이 θ 세 값을 모두 보고하고 "
            f"하나를 고르지 않는다고 동결했다. C2 판정은 {C2_METRIC}로 한다")
    if c2_metric not in names:
        raise M.GateSpecError(f"C2 지표 {c2_metric!r}는 보고된 후보가 아니다 — {names}")

    c1 = M.c1_verdict([r["c1_status"] for r in rows])
    c2 = M.c2_verdict([(r.get("c2_candidates") or {}).get(c2_metric) for r in rows],
                      threshold=C2_THRESHOLD)
    c3 = M.c3_verdict([r.get("compression") for r in rows],
                      statistic=C3_STATISTIC, threshold=C3_THRESHOLD)
    passed = [c1["passed"], c2["passed"], c3["passed"]]
    return {"C1": c1, "C2": c2, "C3": c3, "c2_metric": c2_metric,
            "n_videos": len(rows),
            "all_passed": False if False in passed
                          else (None if None in passed else True),
            "diagnostics_note": DIAGNOSTICS_NOTE}


def panel_videos(manifest=PANEL_MANIFEST) -> list:
    return list(json.loads(Path(manifest).read_text(encoding="utf-8"))["final_panel"])


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--c2-metric", default=None,
                    help="기본값은 동결된 주지표. θ recall은 거부된다")
    ap.add_argument("--out", default="results/m8_gates.json")
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))
    rows = []
    for v in panel_videos():
        wdir = Path(common.work_dir(cfg, v))
        doc = json.loads((wdir / "segments.json").read_text(encoding="utf-8"))
        rows.append(video_row(v, wdir, int(doc["n_segments"]),
                              csv_path=OUT / f"{v}.csv"))
    out = {"gate_spec": "docs/finalization/M8_GATE_SPEC_FREEZE_2026-08-27.md",
           "gt_freeze": "docs/finalization/m8_c2_gt_freeze_2026-08-27.json",
           "verdict": panel_verdict(rows, a.c2_metric), "per_video": rows}
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    common.atomic_write_json(p, out)
    print(f"작성: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

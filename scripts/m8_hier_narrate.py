"""M8 hier — 사건 서술 경로. **구조는 코드, 서술은 LLM 한 문장, 렌더는 코드.**

`docs/finalization/M8_C2_LABELS_RETIREMENT_2026-08-29.md` §6의 다음 질문을 본다.

> 5초 단위 VLM 캡션을 모았을 때, 화면 묘사가 아니라 시간적으로 진행되는
> 사건 서술로 어떻게 바꾸는가.

프로토타입 4회에서 실패한 것은 계층이 아니라 **출력 형식**이었다
(v1 자유생성 · v3 title 12/16 누락 · v4 title 보수 실패). 그래서 이 경로는

```
JSON을 요구하지 않는다      문장 하나만 받는다 — 파싱 실패면이 거의 없다
title 필드를 두지 않는다     누락되는 필드를 패치하는 대신 없앤다
새 구조를 만들지 않는다      확정된 v3 경계를 그대로 읽어 쓴다
```

**점수를 계산하지 않는다.** C1/C2/C3·Event Recall·GT 대조 없음 — 은퇴한 기준이다.

사용:
    python scripts/m8_hier_narrate.py --config config_server.yaml \
        --source runs/m8_hier/m8_hier_prototype_canary_v3/m8c2_3I7oGwk6EaQ.json
"""
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                       # noqa: E402
import m8_hier as H                                                 # noqa: E402
import m8_report                                                    # noqa: E402

RUNDIR = ROOT / "runs/m8_hier"
FROZEN = ("event_id", "start_seg", "end_seg", "support_span", "anchor_cites")


def narrate(src: dict, segments: list, llm, save=None) -> tuple:
    """확정된 span마다 문장 하나. 시간 구조를 만들지도 바꾸지도 않는다.

    **호출 직후 raw를 먼저 남긴다** — parse/validate 실패가 저장보다 앞에 오면
    프로세스가 죽었을 때 원인을 못 밝힌다(2026-08-29 사고 2건).
    """
    by_idx = {s["idx"]: s for s in segments}
    out, raws, failed = [], [], []
    for a in src["atomic_events"]:
        span = [by_idx[i] for i in range(a["start_seg"], a["end_seg"] + 1)]
        r = llm(H.build_narration_prompt(span))
        raws.append({"event_id": a["event_id"], "raw": r, "narration": None})
        if save:
            save(raws)
        t = H.parse_narration(r)
        raws[-1]["narration"] = t
        if not t:
            failed.append(a["event_id"])
        out.append({**{k: a[k] for k in FROZEN}, "narration": t})
    return out, raws, failed


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_server.yaml")
    ap.add_argument("--source", required=True)
    ap.add_argument("--run-kind", default="m8_hier_narration")
    ap.add_argument("--out", default=str(RUNDIR))
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))

    sp = Path(a.source)
    src_bytes = sp.read_bytes()
    src = json.loads(src_bytes.decode("utf-8"))
    vid = src["video_id"]

    wdir = Path(common.work_dir(cfg, vid))
    doc = common.load_segments(wdir / "segments.json",
                               require=["subtitle", "caption"],
                               seg_len=cfg["seg_len_sec"])
    segs = doc["segments"]
    if len(segs) != src["n_segments"]:
        raise SystemExit(f"구간 수 불일치 {len(segs)} vs {src['n_segments']}")

    from llm import make_llm
    llm = make_llm(cfg["report_model"],
                   max_new_tokens=cfg.get("report_max_new_tokens", 2048),
                   load_4bit=cfg.get("llm_4bit", False))

    out_dir = Path(a.out) / a.run_kind
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{vid}.json"
    assert "report.json" not in p.name, "공식 산출물 경로에 쓰지 않는다"

    ckpt_path = out_dir / f"{vid}.checkpoint.json"
    atomics, raws, failed = narrate(
        src, segs, llm,
        save=lambda rs: common.atomic_write_json(
            ckpt_path, {"video_id": vid, "stage": "narration", "raw": rs}))
    out = {"video_id": vid, "schema": H.NARRATION_SCHEMA, "run_kind": a.run_kind,
           "n_segments": src["n_segments"],
           "lineage": {"kind": "narration_only",
                       "structure_from": src.get("run_kind"),
                       "source_path": str(sp).replace("\\", "/"),
                       "source_sha256": hashlib.sha256(src_bytes).hexdigest(),
                       "structure_regenerated": False,
                       "frozen_fields": list(FROZEN) + ["major_events"]},
           "atomic_events": atomics,
           "major_events": src["major_events"],
           "overview": H.compose_overview(src["major_events"]),
           "provenance": m8_report.report_provenance(llm, cfg),
           # v4에서 실패 경로가 원본을 버려 원인을 못 밝혔다. 실패해도 남긴다.
           "raw": {"narration": raws}}
    failures = H.validate_narration_document(out, vid)
    out["prototype_status"] = "OK" if not failures else "INVALID"
    out["validation"] = {"passed": not failures, "failures": failures,
                         "failed_events": failed}
    common.atomic_write_json(p, out)

    print(f"{vid}: 구간 {out['n_segments']} · 사건 {len(atomics)} · "
          f"주요 사건 {len(out['major_events'])}")
    for x in atomics:
        t = x["start_seg"] * cfg["seg_len_sec"]
        print(f"  {x['event_id']}  {t // 60:02d}:{t % 60:02d}  "
              f"{x['narration'] or '(실패)'}")
    print(f"상태: {out['prototype_status']}" + (f" — {failures}" if failures else ""))
    print(f"산출물: {p}")
    print("점수 계산 없음 — 은퇴한 기준(C1/C2/C3·GT)을 쓰지 않는다")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())

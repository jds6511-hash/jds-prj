"""M8 REDESIGN ROUND 1 개발 실행 — **development only.**

소비된 공식 패널 8편에 redesign 후보를 돌린다. 그 8편은 공식 결과를 본 순간
확증 표본으로서는 소진됐고, 지금부터는 개발 증거다.

```
채택      R1 짧은 사건 보존 · R2 과분할 억제 (한 프롬프트의 양방향 계약)
          R5 빈 청크 1단 분할 재시도 · R6 사건명 한국어
보류      R3 span 정밀도 · R4 거부→절단 · R7 C3 amendment
```

**공식 산출물을 건드리지 않는다.** 확정 경로(`work/<vid>/report.json`)에 쓰지 않고
run 디렉터리에만 쓴다. 여기서 나온 C1/C2/C3는 **개발 점수**이고 확증이 아니다.

사용:
    python scripts/m8_redesign_dev.py --run-id r1
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
import m8_report                                                   # noqa: E402
from m8_gates import panel_videos                                   # noqa: E402

RUN_KIND = "m8_redesign_dev"
ADOPTED = ["R1_short_event_preserve", "R2_granularity_contract",
           "R5_empty_chunk_split_retry", "R6_korean_event_title"]
HELD = ["R3_span_refinement", "R4_reject_to_truncate", "R7_c3_amendment"]


def dev_report_path(run_dir, video_id: str) -> Path:
    return Path(run_dir) / f"report_dev_{video_id}.json"


def generate(segments: list, llm, cfg: dict) -> dict:
    """redesign 계약 + 분할 재시도. baseline과 다른 것은 이 두 인자뿐이다."""
    return m8_report.generate_report_structured(
        segments, llm, cfg["map_chunk_size"], cfg["map_chunk_overlap"],
        rules=m8_report.EVENT_RULES_V2, split_retry=True)


def row(video_id: str, rep: dict, n_segments: int, path) -> dict:
    st = M.structural_summary(rep, n_segments)
    f = m8_c1.inspect_video(rep)
    return {"video_id": video_id, "n_segments": n_segments,
            "n_sentences": len(rep.get("sentences") or []),
            "n_events": len(rep.get("events") or []),
            "valid_events": st["valid_events"],
            "rejected_events": st["rejected_events"],
            "rejection_reasons": st["rejection_reasons"],
            "uncited_evaluable_sentences": st.get("uncited_evaluable_sentences"),
            "chunks": len(rep.get("map_raw_outputs") or []),
            "chunk_retries": len(rep.get("chunk_retries") or []),
            "chunk_splits": rep.get("chunk_splits") or [],
            "c1_status": m8_c1.video_status(f),
            "c1_kind_status": {k: f[k]["status"] for k in m8_c1.C1_KINDS},
            "path": str(path)}


def run(cfg, videos: list, llm, run_dir, run_id: str,
        limit_videos=None, limit_chunks=None) -> dict:
    rows, failures = [], []
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    for v in (videos[:limit_videos] if limit_videos else videos):
        try:
            wdir = Path(common.work_dir(cfg, v))
            doc = common.load_segments(wdir / "segments.json",
                                       require=["subtitle", "caption"],
                                       seg_len=cfg["seg_len_sec"])
            s = doc["segments"]
            if limit_chunks:
                s = s[:cfg["map_chunk_size"] * limit_chunks]
            rep = generate(s, llm, cfg)
            out = dev_report_path(run_dir, v)
            common.atomic_write_json(out, {
                "video_id": v, "run_kind": RUN_KIND, "run_id": run_id,
                "schema_version": m8_report.SCHEMA_VERSION,
                "model": cfg["report_model"],
                "map_chunk_size": cfg["map_chunk_size"],
                "provenance": m8_report.report_provenance(llm, cfg),
                "redesign": {"adopted": ADOPTED, "held": HELD,
                             "rules": "EVENT_RULES_V2", "split_retry": True},
                **rep})
            rows.append(row(v, rep, len(s), out))
            print(f"  {v}: 완료", flush=True)
        except Exception as e:                              # noqa: BLE001
            failures.append({"video_id": v,
                             "error": f"{type(e).__name__}: {e}"[:300]})
            print(f"  {v}: 실패 ({type(e).__name__})", flush=True)
    return {"run_kind": RUN_KIND, "run_id": run_id,
            "note": ("development only — 이 실행의 C1/C2/C3는 개발 점수이고 "
                     "확증이 아니다. 소비된 패널이라 fresh confirmation에 쓸 수 없다."),
            "adopted": ADOPTED, "held": HELD,
            "n_requested": len(videos), "n_written": len(rows),
            "failures": failures, "per_video": rows}


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_server.yaml")
    ap.add_argument("--run-id", default="r1")
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit-videos", type=int, default=None)
    ap.add_argument("--limit-chunks", type=int, default=None)
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))
    run_dir = Path(a.out) if a.out else ROOT / "results" / f"m8_redesign_{a.run_id}"
    from llm import make_llm
    llm = make_llm(cfg["report_model"],
                   max_new_tokens=cfg.get("report_max_new_tokens", 2048),
                   load_4bit=cfg.get("llm_4bit", False))
    man = run(cfg, panel_videos(), llm, run_dir, a.run_id,
              a.limit_videos, a.limit_chunks)
    p = Path(run_dir) / f"m8_redesign_dev_{a.run_id}.json"
    common.atomic_write_json(p, man)
    print(f"완료 — 생성 {man['n_written']}편 · 실패 {len(man['failures'])}편")
    print(f"manifest: {p}")
    print("이 실행은 development evidence다 — 확증이 아니다")
    return 1 if man["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

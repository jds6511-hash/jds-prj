"""저장된 raw를 고친 파서로 다시 읽는다. **LLM을 부르지 않는다.**

2026-08-29 첫 실행의 결함 두 건은 모델이 아니라 파서였다.

```
① stt_cites를 모델은 `["seg#55", "seg#56"]`로 냈는데 순수 숫자만 받아
   14건을 `no_stt_cite`로 버렸다
② JSON이 깨진 1건(EP21)에서 맨문장 폴백이 JSON 원문을 요약으로 삼았다
```

생성물은 전량 저장돼 있으므로 **GPU 없이 결정적으로 정정**할 수 있다. 경계·span·
근거 앵커는 손대지 않는다 — 재생성이 아니라 재파싱이다.

사용:
    python scripts/bcs_reparse.py --source runs/bcs/bcs_v0/wonyi_geoje.json
"""
import argparse
import collections
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import bcs as B                                                     # noqa: E402
import common                                                       # noqa: E402

FROZEN = ("episode_id", "start_seg", "end_seg", "support_span", "anchor_cites")


def reparse(doc: dict, segments: list) -> dict:
    raws = {r["episode_id"]: r["raw"] for r in doc["raw"]["content"]}
    by_idx = {s["idx"]: s for s in segments}
    eps = []
    for e in doc["episodes"]:
        span = [by_idx[i] for i in range(e["start_seg"], e["end_seg"] + 1)]
        c = B.verify_content(B.parse_content(raws[e["episode_id"]]), e, span)
        eps.append({**{k: e[k] for k in FROZEN}, **c})
    return eps


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--source", required=True)
    ap.add_argument("--run-kind", default="bcs_v0_reparsed")
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))

    sp = Path(a.source)
    doc = json.loads(sp.read_text(encoding="utf-8"))
    vid = doc["video_id"]
    wdir = Path(common.work_dir(cfg, vid))
    segs = B.sanitize_stt(common.load_segments(
        wdir / "segments.json", require=["subtitle", "caption"],
        seg_len=cfg["seg_len_sec"])["segments"])
    if len(segs) != doc["n_segments"]:
        raise SystemExit("구간 수 불일치")

    eps = reparse(doc, segs)
    out = {**{k: v for k, v in doc.items() if k not in ("episodes", "raw",
                                                        "validation",
                                                        "prototype_status")},
           "run_kind": a.run_kind,
           "lineage": {"kind": "reparse_only", "structure_regenerated": False,
                       "llm_called": False, "source_run_kind": doc["run_kind"],
                       "source_path": str(sp).replace("\\", "/"),
                       "frozen_fields": list(FROZEN)},
           "episodes": eps, "raw": doc["raw"]}
    failures = B.validate(out, vid)
    out["prototype_status"] = "OK" if not failures else "INVALID"
    out["validation"] = {"passed": not failures, "failures": failures}

    p = sp.parent.parent / a.run_kind / f"{vid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    common.atomic_write_json(p, out)
    if not failures:
        p.with_suffix(".md").write_text(B.render(out, seg_len=cfg["seg_len_sec"]),
                                        encoding="utf-8")

    before = doc["episodes"]
    bn = sum(1 for e in before if (e.get("dialogue_note") or "").strip())
    an = sum(1 for e in eps if (e.get("dialogue_note") or "").strip())
    print(f"{vid}  Episode {len(eps)} (구조 불변)")
    print(f"dialogue_note   {bn} → {an}")
    print(f"버림 사유       {dict(collections.Counter(e['dropped'] for e in before if e['dropped']))}"
          f" → {dict(collections.Counter(e['dropped'] for e in eps if e['dropped']))}")
    print(f"parse_mode      {dict(collections.Counter(e.get('parse_mode') for e in eps))}")
    changed = [e["episode_id"] for e, b in zip(eps, before)
               if e["summary"] != b["summary"]]
    print(f"요약이 바뀐 Episode  {changed}")
    print(f"상태: {out['prototype_status']}" + (f" — {failures}" if failures else ""))
    print(f"산출물: {p}")
    print("LLM을 부르지 않았다 — 저장된 raw 재파싱")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""M8 hier prototype v4 — **title-only format repair.**

새 hierarchy generation이 아니다. v3에서 성공한 시간 구조를 **완전히 고정**한 채
비어 있는 `title` 필드만 채운다.

```
v3   Atomic 16 · Major 2 · 겹침 0 · 타임라인 구멍 0
     그러나 title 12/16 누락 → atomic_empty_field → CANARY_INVALID
v4   그 12개만 채운다. 나머지는 하나도 건드리지 않는다
```

바꾸지 않는 것: atomic 경계 · start/end · major 경계 · major grouping ·
major title · atomic description · support_span · anchor_cites · 사건 수.
**변경 여부를 코드가 대조하고, 하나라도 달라지면 무효로 끝낸다.**

fail-closed: 12개 중 하나라도 못 채우면 `CANARY_INVALID` → `PROTOTYPE_STOP`.
placeholder·서술 첫 문장 복사 같은 우회로 validator를 통과시키지 않는다.

사용:
    python scripts/m8_hier_title_repair.py --config config_server.yaml \
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

# 이 필드가 하나라도 달라지면 v4는 format repair가 아니게 된다.
FROZEN_ATOMIC = ("event_id", "start_seg", "end_seg", "description",
                 "support_span", "anchor_cites")


def assert_structure_unchanged(src: dict, out: dict):
    a0, a1 = src["atomic_events"], out["atomic_events"]
    if len(a0) != len(a1):
        raise H.HierInvalid("atomic_count_changed", [len(a0), len(a1)])
    for x, y in zip(a0, a1):
        for k in FROZEN_ATOMIC:
            if x.get(k) != y.get(k):
                raise H.HierInvalid("frozen_field_changed",
                                    [x.get("event_id"), k])
    if src["major_events"] != out["major_events"]:
        raise H.HierInvalid("major_changed")
    if src.get("overview") != out.get("overview"):
        raise H.HierInvalid("overview_changed")


def repair(src: dict, llm) -> tuple:
    """빈 title만 채운다. 기존 title은 문체가 아쉬워도 손대지 않는다."""
    out = json.loads(json.dumps(src))
    targets = [a for a in out["atomic_events"] if not (a.get("title") or "").strip()]
    raws, filled = [], []
    for a in targets:
        r = llm(H.build_title_prompt(a["description"]))
        t = H.parse_title(r)
        raws.append({"event_id": a["event_id"], "raw": r, "title": t})
        if not t:
            raise H.HierInvalid("title_repair_failed", a["event_id"])
        a["title"] = t
        filled.append(a["event_id"])
    return out, {"n_targets": len(targets), "filled": filled, "raw": raws}


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_server.yaml")
    ap.add_argument("--source", required=True)
    ap.add_argument("--run-kind", default="m8_hier_prototype_canary_v4")
    ap.add_argument("--out", default=str(RUNDIR))
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))

    sp = Path(a.source)
    src_bytes = sp.read_bytes()
    src = json.loads(src_bytes.decode("utf-8"))
    vid = src["video_id"]

    from llm import make_llm
    llm = make_llm(cfg["report_model"],
                   max_new_tokens=cfg.get("report_max_new_tokens", 2048),
                   load_4bit=cfg.get("llm_4bit", False))

    out_dir = Path(a.out) / a.run_kind
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{vid}.json"
    assert "report.json" not in p.name, "공식 산출물 경로에 쓰지 않는다"

    lineage = {"kind": "title_only_format_repair",
               "not_a_new_hierarchy_generation": True,
               "source_run_kind": src.get("run_kind"),
               "source_path": str(sp).replace("\\", "/"),
               "source_sha256": hashlib.sha256(src_bytes).hexdigest(),
               "frozen_fields": list(FROZEN_ATOMIC) +
                                ["major_events", "overview"]}

    try:
        out, diag = repair(src, llm)
        assert_structure_unchanged(src, out)
    except H.HierInvalid as e:
        common.atomic_write_json(p, {**src, "run_kind": a.run_kind,
                                     "lineage": lineage,
                                     "prototype_status": "CANARY_INVALID",
                                     "invalid_reason": e.reason,
                                     "invalid_detail": e.detail})
        print(f"CANARY_INVALID — {e.reason}: {e.detail}")
        print("PROTOTYPE_STOP — fallback title을 만들지 않는다")
        return 2

    out["run_kind"] = a.run_kind
    out["lineage"] = lineage
    out["provenance_title_repair"] = m8_report.report_provenance(llm, cfg)
    out["title_repair"] = {k: v for k, v in diag.items() if k != "raw"}
    failures = H.validate_document(out, vid)
    out["prototype_status"] = "CANARY_OK" if not failures else "CANARY_INVALID"
    out["validation"] = {"passed": not failures, "failures": failures}
    out.setdefault("raw", {})["title_repair"] = diag["raw"]
    common.atomic_write_json(p, out)

    print(f"{vid}: title 보수 {diag['n_targets']}건 → {len(diag['filled'])}건 완료")
    for r in diag["raw"]:
        print(f"  {r['event_id']}  {r['title']}")
    print(f"상태: {out['prototype_status']}" + (f" — {failures}" if failures else ""))
    print(f"산출물: {p}")
    print("구조 무변경 대조 통과 — 경계·grouping·서술·앵커 그대로")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())

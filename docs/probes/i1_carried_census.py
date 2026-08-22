"""carried-over census를 **development 산출물에서 파생**한다 — 손으로 적지 않는다.

`i1_validation_analysis --carried`는 넘긴 census의 합을 공표값
(`PUBLISHED_CARRIED_TP` = baseline 71 / primary 71 / fallback 70,
`PUBLISHED_CARRIED_DRIFT` = 71)과 대조하고, 어긋나면 candidate 결과를 열지 않는다
(보충3 §4).

**그 게이트가 의미를 가지려면 census가 공표값과 독립적으로 만들어져야 한다.** 공표
숫자를 그대로 타이핑해 넘기면 게이트는 자기 입력을 자기와 비교하는 동어반복이 된다.
그래서 여기서는 dev 확정 산출물 `_scratch/i1_detector_dev.json`의 `by_cell`에서
C1·C4·C5만 뽑고, 규칙 이름은 `i1_detector_dev`의 FROZEN 상수로 맞춘다.

전수 셀이라 스케일링하지 않는다(`population == sampled`). 아니면 멈춘다.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import i1_detector_dev as D                                      # noqa: E402

DEV_JSON = ROOT / "docs" / "probes" / "_scratch" / "i1_detector_dev.json"
LABELS = ROOT / "label_kit" / "i1_validation" / "labels_v.csv"
CELLS = ("C1", "C4", "C5")


class CensusError(RuntimeError):
    pass


def _rule_blocks(dev: dict) -> dict:
    """규칙 이름 → dev 산출물 블록. 후보는 config로 찾는다(순서에 기대지 않는다)."""
    out = {"baseline": dev["baseline"]}
    for name, cfg in (("primary", D.FROZEN_PRIMARY),
                      ("fallback", D.FROZEN_FALLBACK)):
        hit = [c for c in dev["candidates"] if c["config"] == cfg]
        if len(hit) != 1:
            raise CensusError(f"{name} config {cfg}에 맞는 블록이 {len(hit)}개다")
        out[name] = hit[0]
    return out


def build(dev: dict) -> dict:
    if tuple(dev["census_cells"]) != CELLS:
        raise CensusError(f"전수 셀이 {dev['census_cells']}로 바뀌었다 — "
                          f"이어받을 셀 목록이 {list(CELLS)}가 아니다")
    blocks = _rule_blocks(dev)
    carried = {}
    for cell in CELLS:
        base = blocks["baseline"]["by_cell"][cell]
        if not base.get("is_census") or base["population"] != base["sampled"]:
            raise CensusError(f"{cell}이 전수가 아니다 — 이어받을 수 없다")
        drift = {name: b["by_cell"][cell]["drift"] for name, b in blocks.items()}
        if len(set(drift.values())) != 1:
            raise CensusError(f"{cell}: drift가 규칙마다 다르다 {drift} — "
                              f"참 라벨은 규칙과 무관해야 한다")
        carried[cell] = {
            "population": base["population"],
            "analyzable": base["analyzable"],
            "drift": base["drift"],
            "tp": {name: b["by_cell"][cell]["tp"] for name, b in blocks.items()},
            "carried_over_census": True,
            "revalidated_in_validation": False,
        }
    return carried


def _sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provenance(carried: dict, a_labels: dict) -> dict:
    n_cjk_present = sum(1 for v in a_labels.values()
                        if v == "cjk_text_present")
    return {
        "analysis_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            encoding="utf-8").stdout.strip(),
        "labels_v_csv_sha256": _sha256(LABELS),
        "n_a_labels": len(a_labels),
        "b_target_count": n_cjk_present,
        "b_stage_empty_because": ("A 라벨에 cjk_text_present가 없다 — B는 그 라벨만"
                                  " 대상이다. **B 설계의 한계가 사라진 것이 아니라"
                                  " 이 표본에서 발동하지 않았다**"),
        "carried_reproduction_gate_enabled": True,
        "carried_source": str(DEV_JSON.relative_to(ROOT)).replace("\\", "/"),
        "carried_derived_not_transcribed": ("공표값을 타이핑하지 않고 dev 산출물"
                                            " by_cell에서 파생했다 — 게이트가"
                                            " 동어반복이 되지 않게"),
        "carried_sum_tp": {k: sum(c["tp"][k] for c in carried.values())
                           for k in ("baseline", "primary", "fallback")},
        "carried_sum_drift": sum(c["drift"] for c in carried.values()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--provenance-out")
    a = ap.parse_args()
    dev = json.loads(DEV_JSON.read_text(encoding="utf-8"))
    carried = build(dev)
    Path(a.out).write_text(json.dumps(carried, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"saved: {a.out}")
    for k in ("baseline", "primary", "fallback"):
        print(f"  {k}: carried tp = {sum(c['tp'][k] for c in carried.values())}")
    print(f"  drift = {sum(c['drift'] for c in carried.values())}")
    if a.provenance_out:
        import csv
        al = {r["sample_id"]: (r.get("label") or "").strip()
              for r in csv.DictReader(
                  LABELS.read_text(encoding="utf-8-sig").splitlines())}
        p = provenance(carried, al)
        Path(a.provenance_out).write_text(
            json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved: {a.provenance_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

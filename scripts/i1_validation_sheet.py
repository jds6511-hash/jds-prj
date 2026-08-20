"""I1 detector fresh validation — 표집 + 블라인드 컨택트시트.

사전등록: `I1_detector_보충2_validation표집_2026-08-20.md`(`4a6ff15`) +
`I1_detector_보충3_표집확정_2026-08-20.md`(`6194889`). 둘 다 표집 전에 커밋됐다.

**A116의 116 프레임을 `(video_id, seg_idx)` 단위로 전량 제외한다.** 프레임 1장이
4 arm에 공유되므로 arm 하나만 빼면 나머지 3개가 새 표본에 섞인다 — 그러면
development set 재사용이다.

**C1·C3·C4·C5는 잔여 모집단이 0이다**(보충3 §1). 현행 detector 적중 82건이 곧 그
셀들의 모집단 전부였고 A116이 전수 표집했다. 그래서 쿼터가 없다.

**시트는 완전 블라인드다.** 프레임·시각·`sample_id`만 올린다. arm·캡션·현행 적중·
셀·**후보 발동 여부**를 전부 가린다. 후보가 발동한 프레임을 알면 라벨이 후보 쪽으로
끌린다.

`m5_search`·`m6_evaluate`를 import하지 않는다(CLAUDE.md 3조). work/·results/·config
불변. 읽기 전용.
"""
import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "docs" / "probes"))

import i1_detector_dev as D                                    # noqa: E402
from i1_sample_sheet import build_sheets, collect              # noqa: E402

import common                                                  # noqa: E402

AKIT = ROOT / "label_kit" / "i1_frames"
OUT = ROOT / "label_kit" / "i1_validation"
# 매니페스트는 **라벨 디렉터리 밖**에 둔다. arm·셀·캡션·현행 적중이 들어 있어서
# 같은 폴더에 두면 경고문 하나에 블라인드가 걸린다 — A116은 그 구조였다
META = ROOT / "label_kit" / "i1_validation_meta"
# 보충3 §1-1. 잔여 0인 셀은 여기 없다
QUOTA = {"C2": 60, "C0": 24}
SEED = 20260820
EXHAUSTED_CELLS = ("C1", "C3", "C4", "C5")
# freeze를 여기서 다시 적지 않는다 — 단일 출처는 i1_detector_dev다
RULES = {"baseline": "baseline",
         "primary": D.FROZEN_PRIMARY,
         "fallback": D.FROZEN_FALLBACK}
HIDDEN_FROM_SHEET = ("arm", "cell", "i1a_hit", "caption", "cjk_count",
                     "cjk_ratio", "longest_cjk_run", "video_id",
                     "fires_baseline", "fires_primary", "fires_fallback")


README = """# I1 detector validation — A단계 라벨 (프레임 83장)

**화면에 글자가 있는지만 본다.** 캡션은 보지 않는다 — 이 시트에 캡션이 없는 이유다.

## 라벨 값 하나를 `labels_v.csv`의 `label` 칸에 적는다

| 값 | 뜻 |
|---|---|
| `cjk_text_present` | 화면에 **한자·가나**가 보인다 (간판·자막·자수·포장 등) |
| `korean_text_only` | 화면에 글자가 있는데 **한글(또는 로마자)뿐**이다 |
| `no_text` | 화면에 읽을 수 있는 글자가 없다 |
| `unclear` | 글자가 있는지, 어떤 문자인지 판단이 안 된다 |

## 순서

1. `sheet_01.jpg` ~ `sheet_03.jpg`를 열어 훑는다
2. 작은 글자가 애매하면 `full/<sample_id>.jpg` 원본(1920×1080)을 연다
3. `labels_v.csv`에 값을 적는다. **83행 전부 채운다** (빈 칸이 있으면 분석이 거부한다)

## 하지 말 것

- **캡션을 찾아보지 마라.** 캡션에 적힌 글자를 화면에서 봤다고 믿게 된다
- 검색 결과·모델명·판정 결과를 참고하지 마라
- 이 폴더에는 메타데이터가 없다. `label_kit/i1_validation_meta/`도 열지 마라

B단계는 `cjk_text_present`로 라벨한 것만 대상이고, 그때 별도 시트를 만든다.
"""


class SheetError(RuntimeError):
    pass


def used_frames() -> set:
    """A116이 이미 쓴 프레임. arm 무관하게 프레임 단위로 뺀다."""
    man = json.loads((AKIT / "manifest.json").read_text(encoding="utf-8"))
    return {(i["video_id"], i["seg_idx"]) for i in man["instances"]}


def exclude_used(rows: list, used: set) -> tuple:
    kept = [r for r in rows if (r["video_id"], r["seg_idx"]) not in used]
    return kept, len(rows) - len(kept)


def sample(rows: list, seed: int) -> list:
    """층 내 단순무작위. 쿼터가 없는 셀은 뽑지 않는다."""
    rng = random.Random(seed)
    by_cell = {}
    for r in rows:
        by_cell.setdefault(r["cell"], []).append(r)
    picked = []
    for cell, quota in QUOTA.items():
        pool = sorted(by_cell.get(cell, []),
                      key=lambda r: (r["video_id"], r["seg_idx"], r["arm"]))
        rng.shuffle(pool)
        picked.extend(pool[:quota])
    return picked


def check_c0_invariant(rows: list) -> None:
    """**C0에서 어느 규칙도 발동하지 않아야 한다.**

    비교 대상은 `language_drift(CJK) OR 반복`이다. C0 정의가 `CJK 0 ∧ 현행 미적중`
    이라 구조적으로는 발동할 수 없지만, 추론으로 두지 않는다. 하나라도 발동하면
    셀 정의와 데이터가 어긋난 것이고 **C0의 human label 생략이 무효**다.
    """
    bad = []
    for r in rows:
        if r["cell"] != "C0":
            continue
        for name, cfg in RULES.items():
            if D.fires_total(r, cfg):
                bad.append((r.get("sample_id") or
                            f'{r["video_id"]}#{r["seg_idx"]}', name))
    if bad:
        raise SheetError(
            f"C0 불변식 위반 {len(bad)}건 (예: {bad[:3]}) — C0에서 규칙이 발동했다. "
            "human label 생략을 적용할 수 없다. 셀 정의와 데이터를 대조하라")


def assign_ids(rows: list, seed: int) -> list:
    """프레임 단위로 `V###` 부여. `S###`와 겹치지 않게 접두를 바꿨다.

    **번호를 뽑은 순서대로 매기면 셀이 드러난다** — 쿼터 순서가 C2 60 → C0 24라서
    `V001~V060`이 전부 C2가 된다. 라벨하는 사람이 앞쪽 60장이 같은 층이라는 것을
    알면 판정이 끌린다. 그래서 프레임 목록을 seed 고정으로 섞은 뒤 번호를 준다.

    프레임 1장은 여러 arm에 공유되므로 **프레임 단위로 id를 주고 인스턴스에
    되돌려 붙인다.**
    """
    frames, seen = [], set()
    for r in rows:
        key = (r["video_id"], r["seg_idx"])
        if key not in seen:
            seen.add(key)
            frames.append(key)
    random.Random(seed).shuffle(frames)
    fid = {k: f"V{i:03d}" for i, k in enumerate(frames, 1)}
    return [{**r, "sample_id": fid[(r["video_id"], r["seg_idx"])]} for r in rows]


def write_label_file(rows: list, path) -> None:
    """빈 label 칸만 있는 CSV. **이미 라벨한 파일을 덮어쓰지 않는다.**"""
    path = Path(path)
    if path.exists():
        return
    ids = sorted({r["sample_id"] for r in rows})
    path.write_text("sample_id,label\n" + "".join(f"{s},\n" for s in ids),
                    encoding="utf-8")


def sheet_rows(rows: list) -> list:
    """시트에 올라가는 것만. 나머지는 매니페스트에만 남는다."""
    return [{"sample_id": r["sample_id"], "start": r["start"], "end": r["end"]}
            for r in rows]


def manifest(picked: list, pool: list, n_excluded: int,
             remaining: dict) -> dict:
    by_cell = {}
    for r in picked:
        by_cell[r["cell"]] = by_cell.get(r["cell"], 0) + 1
    return {
        "stage": "validation",
        "prereg": ("docs/preregistration/I1_detector_보충2_validation표집_"
                   "2026-08-20.md + 보충3_표집확정_2026-08-20.md"),
        "freeze_doc": "docs/I1_detector_candidate_freeze_2026-08-20.md",
        "seed": SEED,
        "quota": dict(QUOTA),
        "sampled_by_cell": by_cell,
        "n_sampled": len(picked),
        "distinct_frames": len({(r["video_id"], r["seg_idx"]) for r in picked}),
        "n_excluded_a116_instances": n_excluded,
        "remaining_population": dict(remaining),
        "exhausted_cells": list(EXHAUSTED_CELLS),
        "carried_over_census": list(EXHAUSTED_CELLS),
        "carried_over_note": ("이 셀들은 잔여 모집단이 0이라 development census를 "
                              "이어받는다. **이번에 재검증되지 않았다** — "
                              "validation에서 확인됐다고 쓰지 마라"),
        "rules_evaluated": {k: v for k, v in RULES.items()},
        "primary_vs_fallback": {
            "separable_on_fresh_data": False,
            "reason": ("두 후보의 development 차이는 C4 인스턴스 1건이었고 C4 잔여가 "
                       "0이다 — 새 표본에서 가를 수 없다"),
            "resolution": "simple_rule_preference",
            "resolved_to": "fallback (R_only, R=2)",
        },
        "hidden_from_sheet": list(HIDDEN_FROM_SHEET),
        "c0_human_label": "omitted (보충2). cjk_count == 0 파생 규칙으로 처리",
        "instances": picked,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_aihub.yaml")
    ap.add_argument("--dry-run", action="store_true",
                    help="manifest only, no sheet images")
    a = ap.parse_args()
    cfg = common.load_config(ROOT / a.config)

    pool_all = collect(cfg)
    kept, n_ex = exclude_used(pool_all, used_frames())
    remaining = {}
    for r in kept:
        remaining[r["cell"]] = remaining.get(r["cell"], 0) + 1
    picked = assign_ids(sample(kept, SEED), SEED)
    check_c0_invariant(picked)

    OUT.mkdir(parents=True, exist_ok=True)
    META.mkdir(parents=True, exist_ok=True)
    man = manifest(picked, kept, n_ex, remaining)
    (META / "manifest_v.json").write_text(
        json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    # 시트는 sample_id 순서로 — 번호는 이미 섞여 있으므로 셀이 드러나지 않는다
    frames, seen = [], set()
    for r in sorted(picked, key=lambda x: x["sample_id"]):
        if r["sample_id"] not in seen:
            seen.add(r["sample_id"])
            frames.append(r)
    write_label_file(picked, OUT / "labels_v.csv")
    (OUT / "README.md").write_text(README, encoding="utf-8")
    if not a.dry_run:
        build_sheets(frames, cfg, OUT)
        # 시트 썸네일(300px)에서는 간판·자막 같은 작은 글자가 안 읽힌다.
        # 판정 대상이 바로 그 글자다 — 원본도 sample_id 이름으로 낸다
        full = OUT / "full"
        full.mkdir(parents=True, exist_ok=True)
        for f in frames:
            dst = full / f"{f['sample_id']}.jpg"
            if not dst.exists():
                dst.write_bytes((Path(common.work_dir(cfg, f["video_id"]))
                                 / f["rep_frame"]).read_bytes())
    print(f"sampled: {len(picked)} instances / {len(frames)} frames")
    print(f"excluded A116 instances: {n_ex}")
    print(f"remaining pool by cell: {remaining}")
    print(f"label file: {OUT / 'labels_v.csv'}")
    print("labels: cjk_text_present / korean_text_only / no_text / unclear")
    print(f"metadata kept OUTSIDE the labeling dir: {META}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

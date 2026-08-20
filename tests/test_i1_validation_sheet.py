"""I1 validation 표집 — 보충2·보충3의 경계를 시트 생성 전에 고정.

막는 것 셋.
1. A116 프레임이 새 표본에 섞이는 것 (development set 재사용)
2. C0 human-label 생략이 반복 branch 발동 인스턴스에까지 적용되는 것
3. 후보 발동 여부가 라벨 시트에 노출되는 것
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "docs" / "probes"))
import i1_validation_sheet as V                                # noqa: E402


def _row(vid, seg, cell, cjk=0, run=0, ratio=0.0, hit=False, arm="A1"):
    return {"arm": arm, "video_id": vid, "seg_idx": seg, "cell": cell,
            "cjk_count": cjk, "longest_cjk_run": run, "cjk_ratio": ratio,
            "i1a_hit": hit, "caption": "x", "start": 0, "end": 5,
            "rep_frame": "frames/seg_0000.jpg"}


# ---- 쿼터·seed 고정 ------------------------------------------------------

def test_quota_and_seed_are_frozen():
    """보충3 §1-1. 잔여 0인 셀은 쿼터가 0이다."""
    assert V.QUOTA == {"C2": 60, "C0": 24}
    assert V.SEED == 20260820
    assert V.EXHAUSTED_CELLS == ("C1", "C3", "C4", "C5")


def test_frozen_rules_come_from_the_freeze_module():
    """freeze를 여기서 다시 적지 않는다 — 단일 출처를 쓴다."""
    import i1_detector_dev as D
    assert V.RULES["primary"] == D.FROZEN_PRIMARY
    assert V.RULES["fallback"] == D.FROZEN_FALLBACK
    assert V.RULES["baseline"] == "baseline"


# ---- A116 제외 -----------------------------------------------------------

def test_a116_frames_are_excluded_by_video_and_seg():
    used = {("v1", 0), ("v2", 3)}
    rows = [_row("v1", 0, "C2"), _row("v1", 1, "C2"), _row("v2", 3, "C2")]
    kept, n_ex = V.exclude_used(rows, used)
    assert [(r["video_id"], r["seg_idx"]) for r in kept] == [("v1", 1)]
    assert n_ex == 2


def test_exclusion_covers_all_arms_of_the_same_frame():
    """프레임 1장은 4 arm에 공유된다 — arm 하나만 빼면 나머지가 새 표본에 섞인다."""
    used = {("v1", 0)}
    rows = [_row("v1", 0, "C2", arm=a) for a in ("A1", "A2", "A3", "A4")]
    kept, n_ex = V.exclude_used(rows, used)
    assert kept == [] and n_ex == 4


def test_used_frames_are_read_from_the_a116_manifest():
    used = V.used_frames()
    assert len(used) == 116
    assert all(isinstance(v, str) and isinstance(i, int) for v, i in used)


# ---- 표집 --------------------------------------------------------------

def test_sample_respects_quota_and_is_deterministic():
    rows = [_row("v", i, "C2", cjk=2, run=2, ratio=0.02) for i in range(200)]
    a = V.sample(rows, V.SEED)
    b = V.sample(rows, V.SEED)
    assert len(a) == 60
    assert [r["seg_idx"] for r in a] == [r["seg_idx"] for r in b]


def test_sample_takes_all_when_pool_is_smaller_than_quota():
    rows = [_row("v", i, "C2", cjk=2, run=2, ratio=0.02) for i in range(10)]
    assert len(V.sample(rows, V.SEED)) == 10


def test_exhausted_cell_yields_nothing_and_is_recorded():
    rows = [_row("v", i, "C4", cjk=5, run=5, ratio=0.1, hit=True)
            for i in range(50)]
    picked = V.sample(rows, V.SEED)
    assert picked == []                                    # C4는 쿼터가 없다


# ---- C0 불변식 ----------------------------------------------------------

def test_c0_invariant_holds_when_nothing_fires():
    rows = [_row("v", 0, "C0", cjk=0, run=0, ratio=0.0, hit=False)]
    V.check_c0_invariant(rows)                             # 예외 없음


def test_c0_invariant_fails_closed_when_repetition_branch_fires():
    """C0에서 반복 규칙이 발동하면 human label 생략이 무효다."""
    rows = [_row("v", 0, "C0", cjk=0, run=0, ratio=0.0, hit=True)]
    with pytest.raises(V.SheetError, match="C0"):
        V.check_c0_invariant(rows)


def test_c0_invariant_checks_every_frozen_rule():
    src = (ROOT / "scripts" / "i1_validation_sheet.py").read_text(encoding="utf-8")
    assert "RULES" in src.split("def check_c0_invariant")[1].split("def ")[0]


# ---- 시트 블라인드 ------------------------------------------------------

def test_manifest_hides_firing_and_cell_from_sheet_fields():
    hidden = V.HIDDEN_FROM_SHEET
    for k in ("arm", "cell", "i1a_hit", "caption", "fires_primary",
              "fires_fallback", "fires_baseline"):
        assert k in hidden, k


def test_sheet_rows_expose_only_sample_id_and_time():
    rows = [_row("v", 0, "C2", cjk=2, run=2, ratio=0.02)]
    sheet = V.sheet_rows(V.assign_ids(rows, V.SEED))
    assert set(sheet[0]) == {"sample_id", "start", "end"}


def test_manifest_records_exclusion_seed_and_remaining_population():
    rows = [_row("v", i, "C2", cjk=2, run=2, ratio=0.02) for i in range(100)]
    man = V.manifest(V.assign_ids(V.sample(rows, V.SEED), V.SEED), rows,
                     n_excluded=464, remaining={"C2": 734, "C0": 8114})
    assert man["seed"] == V.SEED
    assert man["n_excluded_a116_instances"] == 464
    assert man["remaining_population"] == {"C2": 734, "C0": 8114}
    assert man["quota"] == V.QUOTA
    assert man["exhausted_cells"] == list(V.EXHAUSTED_CELLS)
    assert man["carried_over_census"] == list(V.EXHAUSTED_CELLS)


def test_manifest_declares_primary_fallback_indistinguishable():
    """보충3 §2-3 — fresh 데이터로 두 후보를 가를 수 없다는 사실을 산출물에 남긴다."""
    rows = [_row("v", i, "C2", cjk=2, run=2, ratio=0.02) for i in range(70)]
    man = V.manifest(V.assign_ids(V.sample(rows, V.SEED), V.SEED), rows, 0,
                     {"C2": 734, "C0": 8114})
    assert man["primary_vs_fallback"]["separable_on_fresh_data"] is False
    assert man["primary_vs_fallback"]["resolution"] == "simple_rule_preference"


def test_ids_are_stable_and_prefixed():
    rows = [_row("v", i, "C2", cjk=2, run=2, ratio=0.02) for i in range(3)]
    ids = sorted(r["sample_id"] for r in V.assign_ids(rows, V.SEED))
    assert ids == ["V001", "V002", "V003"]                 # A116의 S###와 겹치지 않는다


def test_cli_output_is_ascii_safe():
    src = (ROOT / "scripts" / "i1_validation_sheet.py").read_text(encoding="utf-8")
    for line in src.split("if __name__")[0].splitlines():
        if line.strip().startswith("print("):
            assert line.isascii(), line


def test_build_sheets_writes_to_the_given_dir(tmp_path, monkeypatch):
    """모듈 전역 OUT을 쓰면 다른 라벨셋의 시트를 덮어쓴다.

    실제 사고: 검증 시트가 `label_kit/i1_frames/`에 들어가 A116 시트 3장을
    덮어썼다. 라벨은 무손상이었지만(labels.csv sha256 불변) 표시 산출물이
    사라졌다. 출력 디렉터리는 인자로 받아야 한다.
    """
    import inspect
    import i1_sample_sheet as S
    assert "out" in inspect.signature(S.build_sheets).parameters


def test_validation_script_passes_its_own_output_dir():
    src = (ROOT / "scripts" / "i1_validation_sheet.py").read_text(encoding="utf-8")
    assert "build_sheets(frames, cfg, OUT)" in src
    assert V.OUT.name == "i1_validation"


# ---- sample_id가 셀을 드러내지 않는다 -----------------------------------

def test_sample_ids_do_not_leak_cell_order():
    """쿼터 순서대로 번호를 매기면 V001~V060=C2, V061~=C0가 되어 셀이 드러난다.

    라벨하는 사람이 앞쪽 60장이 같은 층이라는 것을 알면 판정이 끌린다.
    """
    rows = ([_row("v", i, "C2", cjk=2, run=2, ratio=0.02) for i in range(60)]
            + [_row("v", 100 + i, "C0") for i in range(24)])
    out = V.assign_ids(rows, V.SEED)
    first60 = [r["cell"] for r in out if int(r["sample_id"][1:]) <= 60]
    assert set(first60) == {"C2", "C0"}, "앞 60번이 한 층으로 뭉쳐 있다"


def test_assign_ids_is_deterministic_and_frame_scoped():
    """프레임 1장이 여러 arm에 공유되면 같은 sample_id를 받아야 한다."""
    rows = [_row("v", 0, "C2", cjk=2, run=2, ratio=0.02, arm=a)
            for a in ("A1", "A2")] + [_row("v", 1, "C2", cjk=2, run=2, ratio=0.02)]
    a = V.assign_ids(rows, V.SEED)
    b = V.assign_ids(rows, V.SEED)
    assert [r["sample_id"] for r in a] == [r["sample_id"] for r in b]
    same = {r["sample_id"] for r in a if r["seg_idx"] == 0}
    assert len(same) == 1                                  # 같은 프레임 = 같은 id
    assert len({r["sample_id"] for r in a}) == 2           # 프레임 2장 = id 2개


def test_label_file_is_created_with_blank_column_and_not_overwritten(tmp_path):
    rows = V.assign_ids([_row("v", i, "C2", cjk=2, run=2, ratio=0.02)
                         for i in range(3)], V.SEED)
    p = tmp_path / "labels_v.csv"
    V.write_label_file(rows, p)
    first = p.read_text(encoding="utf-8")
    assert first.startswith("sample_id,label")
    assert first.count("\n") == 4                          # 헤더 + 3행
    p.write_text("sample_id,label\nV001,no_text\n", encoding="utf-8")
    V.write_label_file(rows, p)                            # 두 번째 호출
    assert "no_text" in p.read_text(encoding="utf-8")      # 덮어쓰지 않는다


# ---- 라벨 디렉터리에 메타데이터를 두지 않는다 ---------------------------

LEAK_KEYS = ("arm", "cell", "caption", "i1a_hit", "cjk_count", "cjk_ratio",
             "longest_cjk_run", "video_id", "seg_idx")


def test_manifest_lives_outside_the_labeling_dir():
    """경고문에 의존하지 않는다 — 라벨러가 열 이유가 없는 곳에 둔다."""
    assert V.OUT.name == "i1_validation"
    assert V.META.name != V.OUT.name
    assert V.META.parent == V.OUT.parent
    assert not str(V.META).startswith(str(V.OUT) + "\\")
    assert not str(V.META).startswith(str(V.OUT) + "/")


def test_labeling_dir_contains_no_metadata_file():
    """실제 산출물 검사 — 라벨 디렉터리의 텍스트 파일에 누출 키가 없어야 한다."""
    if not V.OUT.exists():
        pytest.skip("표집 미실행")
    for p in V.OUT.rglob("*"):
        if not p.is_file() or p.suffix.lower() in (".jpg", ".jpeg", ".png"):
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        for k in LEAK_KEYS:
            assert k not in txt, f"{p.name}에 {k}가 있다"


def test_readme_is_written_for_the_labeler():
    if not V.OUT.exists():
        pytest.skip("표집 미실행")
    r = V.OUT / "README.md"
    assert r.exists()
    txt = r.read_text(encoding="utf-8")
    for lab in ("cjk_text_present", "korean_text_only", "no_text", "unclear"):
        assert lab in txt

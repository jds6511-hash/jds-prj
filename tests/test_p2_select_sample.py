"""P2 표본 선정 — **규칙이 추출보다 먼저 커밋된다.**

결정 문서: `docs/P2_승인1_규모확정_2026-08-20.md` · `docs/P2_선정규칙_동률처리_2026-08-20.md`.

막는 것 여섯.
1. `sampling_frame_usable`이 아닌 영상이 표본에 들어가는 것
2. 계열 배분에서 Hamilton 이외의 정수화를 쓰는 것
3. remainder 동률을 결과가 유리한 쪽으로 푸는 것
4. seed 없이·다른 seed로 뽑는 것
5. 비-EBS를 무작위 추출로 깎는 것 (전수여야 한다)
6. 캡션·검색·모델 산출물이 선정에 들어오는 것
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import p2_select_sample as SEL                                   # noqa: E402


def _row(vid, family, usable=True, n=200):
    return {"source_id": vid, "program": family,
            "publisher": family.split("_")[0],
            "n_segments": n, "sampling_frame_usable": usable,
            "file_sha256": "h" + vid, "source_url": "u/" + vid,
            "selected_audio_language": "ko", "speech_status": "audio_track_ko"}


def _pool(counts, unusable=()):
    rows = []
    for fam, k in counts.items():
        for i in range(k):
            rows.append(_row(f"{fam}{i}", fam))
    rows += [_row(v, f, usable=False) for v, f in unusable]
    return rows


# ---- 동률 규칙이 선언돼 있다 ---------------------------------------------

def test_tie_break_is_declared_and_static():
    assert SEL.TIE_BREAK == "program_id_ascending"
    assert SEL.SEED == 20260820
    assert SEL.C_CAP == 0.80 and SEL.TARGET_K == 35


def test_tie_break_does_not_look_at_counts_or_outcomes():
    """정적 규칙이다 — 표본 크기·점수·캡션을 보지 않는다."""
    import inspect
    src = inspect.getsource(SEL.hamilton)
    for bad in ("caption", "mrr", "score", "qwen", "alpha"):
        assert bad not in src.lower(), bad


# ---- Hamilton 배분 -------------------------------------------------------

def test_hamilton_matches_the_documented_allocation():
    """실측 usable 29 → 28 배분."""
    usable = {"ebs_hangukgihaeng": 10, "ebs_docuprime": 6,
              "ebs_geonchuktamgu": 6, "ebs_geukhanjigeop": 4, "ebs_other": 3}
    q = SEL.hamilton(usable, 28)
    assert q == {"ebs_hangukgihaeng": 9, "ebs_docuprime": 6,
                 "ebs_geonchuktamgu": 6, "ebs_geukhanjigeop": 4,
                 "ebs_other": 3}
    assert sum(q.values()) == 28


def test_hamilton_total_is_exact_and_never_exceeds_supply():
    for total in range(0, 30):
        usable = {"a": 10, "b": 6, "c": 6, "d": 4, "e": 3}
        q = SEL.hamilton(usable, total)
        assert sum(q.values()) == total
        assert all(q[k] <= usable[k] for k in usable)


def test_hamilton_tie_is_resolved_by_program_id_ascending():
    """동률에서 이름 순서만 본다."""
    usable = {"zz": 5, "aa": 5}
    q = SEL.hamilton(usable, 5)          # 각 2.5 → 동률 1석
    assert q == {"aa": 3, "zz": 2}


# ---- 표본 구성 ----------------------------------------------------------

def test_only_usable_rows_enter_the_sample():
    rows = _pool({"ebs_a": 3}, unusable=[("bad1", "ebs_a")])
    r = SEL.select(rows, free_videos={"f1": 200}, target_k=4)
    ids = [x["source_id"] for x in r["selected"]]
    assert "bad1" not in ids
    assert len(ids) == 4          # ebs 3 + free 1


def test_cap_forbids_ebs_when_there_is_no_non_ebs():
    """`E <= 4N`이므로 N=0이면 E=0이다 — 상한이 산술적으로 그렇다."""
    rows = _pool({"ebs_a": 10})
    r = SEL.select(rows, free_videos={}, target_k=10)
    assert r["ebs_cap_from_c"] == 0
    assert r["selected"] == []


def test_non_ebs_is_census_not_sampled():
    rows = _pool({"ebs_a": 30, "kbs_docu": 2, "other_docu_public": 1})
    r = SEL.select(rows, free_videos={"f1": 183, "f2": 211, "f3": 192,
                                      "f4": 395}, target_k=35)
    non = [x for x in r["selected"] if x["publisher"] != "ebs"]
    assert len(non) == 7
    assert r["non_ebs_census"] is True


def test_ebs_respects_the_cap_and_target():
    rows = _pool({"ebs_a": 10, "ebs_b": 6, "ebs_c": 6, "ebs_d": 4,
                  "ebs_e": 3, "kbs_docu": 2, "other_docu_public": 1})
    r = SEL.select(rows, free_videos={f"f{i}": 200 for i in range(4)},
                   target_k=35)
    ebs = [x for x in r["selected"] if x["publisher"] == "ebs"]
    assert len(ebs) == 28
    assert len(r["selected"]) == 35
    assert len(ebs) / len(r["selected"]) <= SEL.C_CAP + 1e-9


def test_draw_is_deterministic_under_the_frozen_seed():
    rows = _pool({"ebs_a": 10, "ebs_b": 6, "ebs_c": 6, "ebs_d": 4,
                  "ebs_e": 3, "kbs_docu": 2, "other_docu_public": 1})
    free = {f"f{i}": 200 for i in range(4)}
    a = SEL.select(rows, free_videos=free, target_k=35)
    b = SEL.select(rows, free_videos=free, target_k=35)
    assert [x["source_id"] for x in a["selected"]] == \
        [x["source_id"] for x in b["selected"]]


def test_a_different_seed_changes_the_draw():
    rows = _pool({"ebs_a": 10})
    free = {"f1": 200, "f2": 200, "f3": 200}
    a = SEL.select(rows, free_videos=free, target_k=9, seed=SEL.SEED)
    b = SEL.select(rows, free_videos=free, target_k=9, seed=1)
    assert {x["source_id"] for x in a["selected"]} != \
        {x["source_id"] for x in b["selected"]}


def test_binding_random_choice_is_reported():
    """쿼터가 공급과 같은 계열은 전수다 — 무작위가 구속하지 않는다."""
    rows = _pool({"ebs_a": 10, "ebs_b": 6})
    r = SEL.select(rows, free_videos={f"f{i}": 200 for i in range(4)},
                   target_k=19)
    assert r["program_quota"] == {"ebs_a": 9, "ebs_b": 6}
    b = r["random_choice_binding"]
    assert b["ebs_a"] == "choose 9 of 10"
    assert "ebs_b" not in b            # 6 of 6 = census


def test_reserve_order_is_recorded_but_not_used():
    rows = _pool({"ebs_a": 10})
    r = SEL.select(rows, free_videos={f"f{i}": 200 for i in range(4)},
                   target_k=13)
    assert len(r["selected"]) == 13
    assert len(r["reserve_order"]["ebs_a"]) == 1
    assert r["reserve_note"]


def test_provenance_fields_travel_with_the_selection():
    rows = _pool({"ebs_a": 1})
    r = SEL.select(rows, free_videos={"f1": 200}, target_k=2)
    s = r["selected"][0]
    for k in ("source_id", "source_url", "file_sha256", "n_segments",
              "publisher", "program"):
        assert k in s, k


def test_free_videos_are_marked_as_pre_indexed():
    r = SEL.select([], free_videos={"jissi_farm": 211}, target_k=1)
    f = r["selected"][0]
    assert f["publisher"] == "free"
    assert f["pre_indexed"] is True
    assert f["n_segments"] == 211


def test_no_model_or_search_symbols():
    body = (ROOT / "scripts" / "p2_select_sample.py").read_text(
        encoding="utf-8").split('"""', 2)[2]
    for bad in ("m3_generate", "m5_search", "m6_evaluate", "caption",
                "qwen", "mrr"):
        assert bad not in body.lower(), bad


def test_cli_output_is_ascii_safe():
    src = (ROOT / "scripts" / "p2_select_sample.py").read_text(
        encoding="utf-8")
    for line in src.split("if __name__")[0].splitlines():
        if line.strip().startswith("print("):
            assert line.isascii(), line

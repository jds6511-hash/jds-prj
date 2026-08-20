"""I1 validation B단계 시트 — **A 라벨만 보고 대상을 고른다.**

사전등록: 보충2 §2 · 보충4 §7.

막는 것 다섯.
1. dev 도구의 넓은 대상 규칙((나) i1a 음성 ∧ C2 전수)이 validation에 새는 것 —
   validation의 동결된 도출 규칙은 A == cjk_text_present만 B를 요구한다
2. A가 덜 찬 상태에서 B를 시작하는 것
3. 캡션을 보여주면서 arm·셀·후보 발동·A 라벨까지 같이 보여주는 것
4. B 시트가 라벨 디렉터리에 들어가 A용 누출 검사를 깨는 것
5. 이미 쓴 B 라벨을 덮어쓰는 것
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "docs" / "probes"))
import i1_validation_stage_b as B                                # noqa: E402
import i1_validation_analysis as A                               # noqa: E402


def _inst(sid, cell, cjk, run, caption, hit=False):
    return {"sample_id": sid, "cell": cell, "cjk_count": cjk,
            "longest_cjk_run": run, "cjk_ratio": 0.02, "i1a_hit": hit,
            "arm": "qwen3vl_4b/P0", "caption": caption,
            "start": 65.0, "end": 70.0, "video_id": "vid_x", "seg_idx": 13}


def _kit(tmp_path, insts, labels, b_rows=None):
    out = tmp_path / "i1_validation"
    meta = tmp_path / "i1_validation_meta"
    out.mkdir()
    meta.mkdir()
    (meta / "manifest_v.json").write_text(
        json.dumps({"instances": insts}, ensure_ascii=False), encoding="utf-8")
    (out / "labels_v.csv").write_text(
        "sample_id,label\n" + "".join(f"{s},{v}\n" for s, v in labels.items()),
        encoding="utf-8")
    if b_rows is not None:
        (out / "labels_vb.csv").write_text(b_rows, encoding="utf-8")
    return out, meta


# ---- 대상 규칙 -----------------------------------------------------------

def test_targets_are_cjk_text_present_only():
    """**(나) i1a 음성 ∧ C2 전수는 validation 대상이 아니다.**

    validation의 `true_label`은 A가 no_text·korean_text_only면 B 없이 drift를
    확정한다. dev 도구의 넓은 규칙을 그대로 쓰면 쓰이지 않는 B 라벨이 생기고,
    나중에 "이 라벨도 있으니 쓰자"는 경로가 열린다.
    """
    insts = [_inst("V001", "C2", 2, 2, "看板 앞"),
             _inst("V002", "C2", 2, 2, "한국어 캡션"),
             _inst("V003", "C0", 0, 0, "글자 없음")]
    lab = {"V001": "cjk_text_present", "V002": "korean_text_only",
           "V003": ""}
    assert [i["sample_id"] for i in B.targets({"instances": insts}, lab)] \
        == ["V001"]


def test_target_requires_caption_cjk():
    """캡션에 CJK가 0이면 도출 규칙상 CJK drift가 될 수 없다."""
    insts = [_inst("V001", "C0", 0, 0, "한국어만")]
    assert B.targets({"instances": insts},
                     {"V001": "cjk_text_present"}) == []


def test_targets_are_sorted_by_sample_id():
    insts = [_inst("V009", "C2", 2, 2, "漢"), _inst("V002", "C2", 2, 2, "字")]
    lab = {"V009": "cjk_text_present", "V002": "cjk_text_present"}
    assert [i["sample_id"] for i in B.targets({"instances": insts}, lab)] \
        == ["V002", "V009"]


def test_label_vocabulary_matches_frozen_derivation():
    """B 라벨 어휘가 동결된 `true_label` 매핑과 어긋나면 분석이 KeyError로 죽는다."""
    assert set(B.LABELS) == {"matches_screen", "drift_despite_text",
                             "drift_no_text", "unclear"}
    inst = {"sample_id": "V001", "cjk_count": 2}
    for b in ("matches_screen", "drift_despite_text", "drift_no_text"):
        assert A.true_label(inst, "cjk_text_present", b) in ("scene_text",
                                                             "drift")
    assert A.true_label(inst, "cjk_text_present", "unclear") \
        == A.EXCLUDED


# ---- A 완결성 ------------------------------------------------------------

def test_incomplete_a_labels_are_refused(tmp_path):
    insts = [_inst("V001", "C2", 2, 2, "漢字"), _inst("V002", "C2", 2, 2, "字")]
    out, meta = _kit(tmp_path, insts, {"V001": "cjk_text_present", "V002": ""})
    with pytest.raises(B.SheetError, match="A 라벨"):
        B.build(out, meta, tmp_path / "b")


def test_a_labels_sha256_is_frozen_in_manifest(tmp_path):
    insts = [_inst("V001", "C2", 2, 2, "漢字")]
    out, meta = _kit(tmp_path, insts, {"V001": "cjk_text_present"})
    m = json.loads(B.build(out, meta, tmp_path / "b").read_text(
        encoding="utf-8"))
    import hashlib
    assert m["a_labels_sha256"] == hashlib.sha256(
        (out / "labels_v.csv").read_bytes()).hexdigest()


# ---- 시트 위생 -----------------------------------------------------------

def test_sheet_shows_caption_but_hides_everything_else(tmp_path):
    insts = [_inst("V001", "C2", 2, 2, "看板 문구가 보인다")]
    out, meta = _kit(tmp_path, insts, {"V001": "cjk_text_present"})
    B.build(out, meta, tmp_path / "b")
    txt = (tmp_path / "b" / "sheet_b.md").read_text(encoding="utf-8")
    assert "看板 문구가 보인다" in txt                 # 캡션은 보여준다
    for bad in ("qwen3vl_4b", "C2", "i1a_hit", "cjk_count", "longest_cjk_run",
                "cjk_ratio", "fires_", "cjk_text_present", "vid_x"):
        assert bad not in txt, bad


def test_blindness_limit_is_recorded(tmp_path):
    """캡션 노출로 후보 발동 블라인드가 유지되지 않는다는 사실을 남긴다."""
    insts = [_inst("V001", "C2", 2, 2, "漢字")]
    out, meta = _kit(tmp_path, insts, {"V001": "cjk_text_present"})
    m = json.loads(B.build(out, meta, tmp_path / "b").read_text(
        encoding="utf-8"))
    assert m["candidate_blind"] is False
    assert "캡션" in m["blindness_limit"]
    assert set(m["hidden_from_sheet"]) >= {"arm", "cell", "i1a_hit",
                                           "a_label", "candidate_firing"}


def test_sheet_is_written_outside_the_a_labeling_dir(tmp_path):
    """B 시트가 A 라벨 디렉터리에 들어가면 A용 누출 검사가 깨진다."""
    insts = [_inst("V001", "C2", 2, 2, "漢字")]
    out, meta = _kit(tmp_path, insts, {"V001": "cjk_text_present"})
    mp = B.build(out, meta, tmp_path / "b")
    assert out not in mp.parents
    assert not (out / "sheet_b.md").exists()


def test_b_labels_go_to_the_path_the_frozen_analysis_reads(tmp_path):
    """분석 코드가 `i1_validation/labels_vb.csv`를 읽는다 — 경로를 바꾸지 않는다."""
    assert A.KIT.name == "i1_validation"
    insts = [_inst("V001", "C2", 2, 2, "漢字")]
    out, meta = _kit(tmp_path, insts, {"V001": "cjk_text_present"})
    B.build(out, meta, tmp_path / "b")
    p = out / "labels_vb.csv"
    assert p.exists()
    assert p.read_text(encoding="utf-8").splitlines()[0] == "sample_id,label_b"
    assert "V001," in p.read_text(encoding="utf-8")


def test_blank_b_label_file_has_no_leak_keys(tmp_path):
    """A용 누출 검사가 라벨 디렉터리 전체를 훑는다 — 새 파일도 통과해야 한다."""
    insts = [_inst("V001", "C2", 2, 2, "漢字")]
    out, meta = _kit(tmp_path, insts, {"V001": "cjk_text_present"})
    B.build(out, meta, tmp_path / "b")
    txt = (out / "labels_vb.csv").read_text(encoding="utf-8")
    for k in ("caption", "arm", "cell", "i1a_hit", "漢字"):
        assert k not in txt, k


def test_existing_b_labels_are_not_overwritten(tmp_path):
    insts = [_inst("V001", "C2", 2, 2, "漢字")]
    out, meta = _kit(tmp_path, insts, {"V001": "cjk_text_present"},
                     b_rows="sample_id,label_b\nV001,matches_screen\n")
    B.build(out, meta, tmp_path / "b")
    assert "matches_screen" in (out / "labels_vb.csv").read_text(
        encoding="utf-8")


# ---- 금지 import ---------------------------------------------------------

def test_does_not_import_search_or_eval():
    body = (ROOT / "scripts" / "i1_validation_stage_b.py").read_text(
        encoding="utf-8").split('"""', 2)[2]
    for bad in ("m5_search", "m6_evaluate", "frame_human_kit"):
        assert bad not in body, bad


def test_cli_output_is_ascii_safe():
    src = (ROOT / "scripts" / "i1_validation_stage_b.py").read_text(
        encoding="utf-8")
    for line in src.split("if __name__")[0].splitlines():
        if line.strip().startswith("print("):
            assert line.isascii(), line

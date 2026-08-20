"""영상 출처 provenance — **인덱싱 전에 기록해야 한다.**

막는 것 여덟.
1. 레지스트리에 없는 신규 영상으로 M1을 돌리는 것
2. 필드가 비어 있는데 통과하는 것
3. `file_sha256` 불일치를 통과하는 것 (검증한 바이트와 다른 파일)
4. selected set 안에서 `source_id`가 중복되는 것
5. 면제를 코드가 조용히 적용하는 것 (면제는 데이터로만 존재한다)
6. 과거에 알 수 없던 값을 추측해 채우는 것
7. downstream meta가 값을 덮어쓰는 것
8. provenance가 지표·eligibility 계산에 쓰이는 것
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import provenance as P                                           # noqa: E402


def _reg(videos=None, exempt=None):
    return {"videos": videos or {}, "legacy_exempt": exempt or {}}


def _vid(tmp_path, name="v.mp4", data=b"bytes"):
    p = tmp_path / name
    p.write_bytes(data)
    return p, P.sha256_file(p)


def test_required_fields_are_declared():
    assert P.PROV_FIELDS == ("source_url", "source_id", "file_sha256")
    assert P.REGISTRY_REL == "data/provenance/videos.json"


# ---- fail-closed --------------------------------------------------------

def test_unregistered_new_video_is_blocked(tmp_path):
    f, _ = _vid(tmp_path)
    with pytest.raises(P.ProvenanceError, match="레지스트리에 없다"):
        P.resolve(_reg(), "newvid", f)


def test_missing_fields_are_blocked(tmp_path):
    f, h = _vid(tmp_path)
    reg = _reg({"v": {"source_url": "u", "source_id": "", "file_sha256": h}})
    with pytest.raises(P.ProvenanceError, match="누락"):
        P.resolve(reg, "v", f)


def test_sha256_mismatch_is_fail_closed(tmp_path):
    f, _ = _vid(tmp_path)
    reg = _reg({"v": {"source_url": "u", "source_id": "s",
                      "file_sha256": "deadbeef"}})
    with pytest.raises(P.ProvenanceError, match="file_sha256 불일치"):
        P.resolve(reg, "v", f)


def test_duplicate_source_id_is_fail_closed(tmp_path):
    f, h = _vid(tmp_path)
    reg = _reg({"a": {"source_url": "u1", "source_id": "same",
                      "file_sha256": h},
                "b": {"source_url": "u2", "source_id": "same",
                      "file_sha256": h}})
    assert P.duplicate_source_ids(reg) == {"same": ["a", "b"]}
    with pytest.raises(P.ProvenanceError, match="source_id 중복"):
        P.resolve(reg, "a", f)


def test_hash_verification_requires_a_file(tmp_path):
    f, h = _vid(tmp_path)
    reg = _reg({"v": {"source_url": "u", "source_id": "s", "file_sha256": h}})
    with pytest.raises(P.ProvenanceError, match="파일 경로"):
        P.resolve(reg, "v", None)


# ---- 정상 경로 ---------------------------------------------------------

def test_registered_video_passes_and_records_verification(tmp_path):
    f, h = _vid(tmp_path)
    reg = _reg({"v": {"source_url": "https://x/y", "source_id": "y",
                      "file_sha256": h}})
    out = P.resolve(reg, "v", f)
    assert out["provenance_status"] == "recorded"
    assert out["file_sha256"] == h and out["source_id"] == "y"
    assert out["sha256_verified_at_m1"] is True


# ---- 면제는 데이터로만 존재한다 -------------------------------------------

def test_legacy_exemption_is_data_not_code_silence(tmp_path):
    f, _ = _vid(tmp_path)
    reg = _reg(exempt={"old": {"reason": "출처 기록 없이 인덱싱된 기존 영상"}})
    out = P.resolve(reg, "old", f)
    assert out["provenance_status"] == P.EXEMPT_MARK
    assert out["reason"]
    # **추측해서 채우지 않는다**
    assert all(out[k] is None for k in P.PROV_FIELDS)
    # 목록에 없으면 여전히 차단된다
    with pytest.raises(P.ProvenanceError):
        P.resolve(reg, "other_old", f)


# ---- downstream 전달 ----------------------------------------------------

def test_propagate_copies_the_value():
    src = {"provenance": {"source_id": "y", "file_sha256": "h"}}
    dst = P.propagate(src, {"text_hash": "t"})
    assert dst["provenance"] == src["provenance"]
    assert dst["text_hash"] == "t"


def test_propagate_refuses_to_overwrite_a_different_value():
    src = {"provenance": {"source_id": "y"}}
    with pytest.raises(P.ProvenanceError, match="덮어쓰기"):
        P.propagate(src, {"provenance": {"source_id": "OTHER"}})


def test_propagate_is_idempotent():
    src = {"provenance": {"source_id": "y"}}
    once = P.propagate(src, {})
    assert P.propagate(src, once) == once


def test_missing_source_provenance_leaves_dst_untouched():
    assert P.propagate({}, {"text_hash": "t"}) == {"text_hash": "t"}


# ---- 파이프라인 배선 ----------------------------------------------------

def test_m1_requires_provenance_before_writing_segments():
    src = (ROOT / "src" / "m1_preprocess.py").read_text(encoding="utf-8")
    assert "provenance" in src
    # 해시 대조 없이 통과하는 경로가 없어야 한다
    assert "resolve(" in src


def test_m4_propagates_instead_of_recomputing():
    src = (ROOT / "src" / "m4_index.py").read_text(encoding="utf-8")
    assert "propagate" in src
    assert "sha256_file" not in src        # m4가 다시 계산하지 않는다


def test_provenance_is_not_used_in_metrics_or_eligibility():
    """기록 전용이다 — 지표·적격 판정에 들어가면 안 된다."""
    for name in ("m6_evaluate.py", "m5_search.py"):
        src = (ROOT / "src" / name).read_text(encoding="utf-8")
        assert "provenance" not in src, name
    gate = (ROOT / "scripts" / "p2_staging_verify.py").read_text(
        encoding="utf-8")
    # 게이트는 provenance를 기록하지만 판정식에는 n_segments만 쓴다
    assert "def classify_segments" in gate
    assert "source_url" not in gate.split("def classify_segments")[1][:400]


def test_registry_lives_in_a_tracked_path():
    """영상은 gitignore 대상이지만 출처 기록은 저장소에 남아야 한다."""
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "data/provenance/" not in ignore
    assert "data/provenance/videos.json" not in ignore


# ---- text_hash 불변 (기존 인덱스 보호) -----------------------------------

def test_adding_provenance_does_not_change_text_hash():
    """`provenance`가 text_hash를 바꾸면 **기존 인덱스 전부가 무효화된다.**"""
    import common
    doc = {"video_id": "v", "n_segments": 1,
           "segments": [{"idx": 0, "start": 0, "end": 5,
                         "subtitle": "s", "caption": "c"}]}
    before = common.index_text_hash(doc)
    doc2 = {**doc, "provenance": {"source_id": "y", "file_sha256": "h"}}
    assert common.index_text_hash(doc2) == before


def test_load_segments_accepts_the_extra_top_level_key(tmp_path):
    import common
    doc = {"video_id": "v", "duration_sec": 5.0, "fps": 30.0, "n_segments": 1,
           "provenance": {"source_id": "y"},
           "segments": [{"idx": 0, "start": 0, "end": 5}]}
    p = tmp_path / "segments.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    assert common.load_segments(p)["provenance"]["source_id"] == "y"


# ---- validator: 기록 가능성이 아니라 기록 완결성 --------------------------

import p2_provenance_validate as V                                # noqa: E402

SEL = [{"source_id": "a", "pre_indexed": False},
       {"source_id": "b", "pre_indexed": False},
       {"source_id": "old", "pre_indexed": True}]
REG = {"videos": {"a": {"source_url": "u/a", "source_id": "a",
                        "file_sha256": "ha"},
                  "b": {"source_url": "u/b", "source_id": "b",
                        "file_sha256": "hb"}},
       "legacy_exempt": {"old": {"reason": "출처 없음"}}}
STAGE = {"videos": [{"source_id": "a", "file_sha256": "ha"},
                    {"source_id": "b", "file_sha256": "hb"}]}


def test_validator_passes_on_a_complete_registry():
    r = V.validate(SEL, REG, STAGE)
    assert r["ok"] is True
    assert r["recorded"] == 2 and r["legacy_exempt"] == 1
    assert r["sha256_checked"] == 2


def test_validator_catches_a_single_missing_video():
    """한 편만 누락돼도 FULL로 넘어가면 안 된다."""
    reg = {"videos": {k: v for k, v in REG["videos"].items() if k != "b"},
           "legacy_exempt": REG["legacy_exempt"]}
    r = V.validate(SEL, reg, STAGE)
    assert r["ok"] is False and r["missing"] == 1
    assert any("b" in p for p in r["problems"])


def test_validator_catches_staging_hash_drift():
    stage = {"videos": [{"source_id": "a", "file_sha256": "DIFFERENT"},
                        {"source_id": "b", "file_sha256": "hb"}]}
    r = V.validate(SEL, REG, stage)
    assert r["ok"] is False
    assert any("staging과 다르다" in p for p in r["problems"])


def test_validator_rejects_a_new_video_marked_as_legacy():
    """신규 영상을 면제로 처리하는 우회 경로를 막는다."""
    reg = {"videos": {"a": REG["videos"]["a"]},
           "legacy_exempt": {"b": {"reason": "x"}, "old": {"reason": "y"}}}
    r = V.validate(SEL, reg, STAGE)
    assert r["ok"] is False
    assert any("신규는 기록 필수" in p for p in r["problems"])


def test_validator_checks_indexed_outputs_when_asked(tmp_path):
    w = tmp_path / "a"
    w.mkdir()
    prov = {"source_url": "u/a", "source_id": "a", "file_sha256": "ha"}
    (w / "segments.json").write_text(
        json.dumps({"provenance": prov}), encoding="utf-8")
    (w / "meta.json").write_text(
        json.dumps({"provenance": {**prov, "source_id": "TAMPERED"}}),
        encoding="utf-8")
    r = V.validate([SEL[0]], REG, STAGE, work_dir=tmp_path)
    row = r["rows"][0]
    assert row["segments"] == "match" and row["meta"] == "MISMATCH"
    assert r["ok"] is False


def test_validator_flags_indexed_output_without_provenance(tmp_path):
    w = tmp_path / "a"
    w.mkdir()
    (w / "segments.json").write_text(json.dumps({}), encoding="utf-8")
    r = V.validate([SEL[0]], REG, STAGE, work_dir=tmp_path)
    assert r["ok"] is False
    assert any("provenance가 없다" in p for p in r["problems"])


def test_real_registry_and_selected_list_pass():
    """실제 산출물로 돌린다 — 계약이 아니라 완결성 검사다."""
    sel_p = ROOT / "docs" / "P2_선정표본_2026-08-20.json"
    if not sel_p.exists():
        pytest.skip("선정 목록 없음")
    sel = json.loads(sel_p.read_text(encoding="utf-8"))["selected"]
    reg = P.load_registry(P.registry_path(ROOT))
    stage_p = ROOT / "artifacts" / "p2_sampling_frame" / "manifest.json"
    stage = (json.loads(stage_p.read_text(encoding="utf-8"))
             if stage_p.exists() else None)
    r = V.validate(sel, reg, stage)
    assert r["ok"] is True, r["problems"][:5]
    assert r["n_selected"] == 35
    assert r["recorded"] == 31 and r["legacy_exempt"] == 4

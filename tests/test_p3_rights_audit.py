"""영상 외부 반출 권한 감사 — 계약 테스트.

핵심은 **fail-closed**다. 명시적 근거 없이 `yes`가 되지 않고, `unclear`는 반출
불가로 취급한다. 계약(NDA·외주)은 rights clearance를 대신하지 못한다.
"""
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import p3_rights_audit as R                                        # noqa: E402


def _rec(sid, legacy=False):
    r = {"video_id": sid, "source_id": sid, "n_segments": 10,
         "provenance_reference": "docs/x.json"}
    r.update({"acquisition_class": "pre_existing", "legacy_exempt": True}
             if legacy else
             {"acquisition_class": "downloaded",
              "source_url": f"https://example.test/{sid}"})
    return r


FULL_YES = {"external_annotation_allowed": "yes",
            "basis": "직접 제작",
            "third_party_delivery_right": "yes",
            "retention_redistribution_limit": "사본 30일 후 삭제",
            "deletion_required_after_work": "yes",
            "identifiable_person_constraint": "없음"}


# ---- 기본값은 unclear ------------------------------------------------------

def test_no_evidence_means_unclear():
    rows = R.audit([_rec("a"), _rec("b")], evidence={})
    assert {r["external_annotation_allowed"] for r in rows} == {"unclear"}
    assert all(r["basis"] == "없음" for r in rows)


def test_unclear_is_not_transferable():
    rows = R.audit([_rec("a")], evidence={})
    assert R.transferable(rows[0]) is False


def test_legacy_video_defaults_unclear():
    """기확보 영상은 출처 기록이 없다 — 보유 권한을 추정하지 않는다."""
    rows = R.audit([_rec("old", legacy=True)], evidence={})
    assert rows[0]["external_annotation_allowed"] == "unclear"
    assert rows[0]["legacy_exempt"] is True


# ---- yes로 올라가는 조건 ---------------------------------------------------

def test_full_evidence_allows_yes():
    rows = R.audit([_rec("a")], evidence={"a": dict(FULL_YES)})
    assert rows[0]["external_annotation_allowed"] == "yes"
    assert R.transferable(rows[0]) is True


@pytest.mark.parametrize("missing", [
    "basis", "third_party_delivery_right", "retention_redistribution_limit",
    "deletion_required_after_work", "identifiable_person_constraint"])
def test_incomplete_evidence_downgrades_to_unclear(missing):
    ev = dict(FULL_YES)
    del ev[missing]
    rows = R.audit([_rec("a")], evidence={"a": ev})
    assert rows[0]["external_annotation_allowed"] == "unclear"
    assert missing in rows[0]["downgrade_reason"]


def test_no_third_party_right_cannot_be_yes():
    ev = dict(FULL_YES, third_party_delivery_right="no")
    rows = R.audit([_rec("a")], evidence={"a": ev})
    assert rows[0]["external_annotation_allowed"] == "no"


def test_explicit_no_is_preserved():
    ev = dict(FULL_YES, external_annotation_allowed="no")
    rows = R.audit([_rec("a")], evidence={"a": ev})
    assert rows[0]["external_annotation_allowed"] == "no"
    assert R.transferable(rows[0]) is False


# ---- 오타·미지 항목은 통과시키지 않는다 ------------------------------------

def test_unknown_source_id_in_evidence_is_an_error():
    with pytest.raises(R.RightsError):
        R.audit([_rec("a")], evidence={"typo_id": dict(FULL_YES)})


def test_invalid_state_is_an_error():
    ev = dict(FULL_YES, external_annotation_allowed="probably")
    with pytest.raises(R.RightsError):
        R.audit([_rec("a")], evidence={"a": ev})


def test_states_are_limited():
    assert R.STATES == ("yes", "no", "unclear")


# ---- 파일럿 게이트 --------------------------------------------------------

def test_pilot_gate_requires_all_yes():
    rows = R.audit([_rec("a"), _rec("b")],
                   evidence={"a": dict(FULL_YES)})
    g = R.pilot_gate(rows, ["a", "b"])
    assert g["allowed"] is False
    assert g["blocking"] == ["b"]


def test_pilot_gate_passes_when_every_video_cleared():
    rows = R.audit([_rec("a")], evidence={"a": dict(FULL_YES)})
    g = R.pilot_gate(rows, ["a"])
    assert g["allowed"] is True and g["blocking"] == []


def test_pilot_gate_rejects_unknown_video():
    rows = R.audit([_rec("a")], evidence={"a": dict(FULL_YES)})
    with pytest.raises(R.RightsError):
        R.pilot_gate(rows, ["a", "ghost"])


# ---- 보고서 --------------------------------------------------------------

def test_report_counts_states_and_holds_transfer():
    r = R.report(records=[_rec("a"), _rec("b")], evidence={})
    assert r["counts"] == {"yes": 0, "no": 0, "unclear": 2}
    assert r["external_transfer_status"] == "HOLD"
    assert r["ready_for_external_transfer"] == []


def test_report_states_contract_is_not_clearance():
    r = R.report(records=[_rec("a")], evidence={})
    assert "NDA" in r["contract_is_not_clearance"]
    assert "vdi" in json.dumps(r, ensure_ascii=False).lower()


def test_report_records_vdi_does_not_bypass():
    r = R.report(records=[_rec("a")], evidence={})
    assert r["vdi_alternative"]["bypasses_rights_clearance"] is False


def test_report_declares_no_inference_rule():
    r = R.report(records=[_rec("a")], evidence={})
    assert r["inference_allowed"] is False


# ---- 누출·쓰기 경계 -------------------------------------------------------

def test_module_does_not_import_search_or_eval():
    src = (ROOT / "scripts" / "p3_rights_audit.py").read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not ({"m5_search", "m6_evaluate", "m4_index", "p2_retrieve",
                 "p2_evaluate"} & mods)


def test_module_reads_no_caption_or_subtitle():
    src = (ROOT / "scripts" / "p3_rights_audit.py").read_text(encoding="utf-8")
    for bad in ("caption", "subtitle", "segments.json"):
        assert bad not in src, bad


def test_module_has_no_registry_writer():
    """SoT 전환은 계속 HOLD — 이 도구가 registry를 쓰지 않는다."""
    src = (ROOT / "scripts" / "p3_rights_audit.py").read_text(encoding="utf-8")
    assert "videos.jsonl" not in src
    assert "write_text" not in src.split("def main")[0]

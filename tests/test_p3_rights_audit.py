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
            "third_party_viewing_right": "yes",
            "third_party_delivery_right": "yes",
            "retention_redistribution_limit": "사본 30일 후 삭제",
            "deletion_required_after_work": "yes",
            "identifiable_person_constraint": "없음",
            "embedded_third_party_content": "없음",
            "attribution_requirement": "해당 없음",
            "source_url": "https://example.test/v",
            "license_url": "https://example.test/terms",
            "license_type": "직접 보유",
            "accessed_at": "2026-08-24"}


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
    "basis", "third_party_viewing_right", "third_party_delivery_right",
    "retention_redistribution_limit", "deletion_required_after_work",
    "identifiable_person_constraint", "attribution_requirement",
    "embedded_third_party_content"])
def test_incomplete_evidence_downgrades_to_unclear(missing):
    ev = dict(FULL_YES)
    del ev[missing]
    rows = R.audit([_rec("a")], evidence={"a": ev})
    assert rows[0]["external_annotation_allowed"] == "unclear"
    assert missing in rows[0]["downgrade_reason"]


def test_no_access_right_at_all_is_no():
    """열람도 사본 전달도 안 되면 어떤 경로로도 외부 annotation이 불가능하다."""
    ev = dict(FULL_YES, third_party_viewing_right="no",
              third_party_delivery_right="no")
    rows = R.audit([_rec("a")], evidence={"a": ev})
    assert rows[0]["external_annotation_allowed"] == "no"


def test_delivery_denied_but_viewing_allowed_stays_yes():
    """사본 전달만 막힌 경우는 VDI 경로가 남아 있다 — 전체를 no로 닫지 않는다."""
    ev = dict(FULL_YES, third_party_delivery_right="no")
    rows = R.audit([_rec("a")], evidence={"a": ev})
    assert rows[0]["external_annotation_allowed"] == "yes"
    assert rows[0]["allowed_access_modes"] == ["viewing"]


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


# ---- 열람권과 사본 전달권을 구분한다 --------------------------------------

VIEW_ONLY = dict(FULL_YES, basis="제공기관 약관 (원격 열람만 허용)",
                 third_party_delivery_right="no",
                 retention_redistribution_limit="사본 생성 금지",
                 deletion_required_after_work="해당 없음",
                 attribution_requirement="출처 표시")


def test_required_evidence_covers_viewing_and_attribution():
    for f in ("third_party_viewing_right", "third_party_delivery_right",
              "attribution_requirement"):
        assert f in R.REQUIRED_EVIDENCE, f


def test_view_only_source_is_viewable_but_not_deliverable():
    rows = R.audit([_rec("a")], evidence={"a": dict(VIEW_ONLY)})
    e = rows[0]
    assert R.transferable(e, mode="viewing") is True
    assert R.transferable(e, mode="delivery") is False
    assert e["external_annotation_allowed"] == "yes"


def test_full_yes_allows_both_modes():
    rows = R.audit([_rec("a")], evidence={"a": dict(FULL_YES)})
    assert R.transferable(rows[0], mode="viewing") is True
    assert R.transferable(rows[0], mode="delivery") is True


def test_no_viewing_right_cannot_be_yes():
    ev = dict(FULL_YES, third_party_viewing_right="no")
    rows = R.audit([_rec("a")], evidence={"a": ev})
    assert rows[0]["external_annotation_allowed"] == "no"


def test_unknown_access_mode_is_an_error():
    rows = R.audit([_rec("a")], evidence={"a": dict(FULL_YES)})
    with pytest.raises(R.RightsError):
        R.transferable(rows[0], mode="download_forever")


def test_pilot_gate_mode_is_recorded():
    rows = R.audit([_rec("a")], evidence={"a": dict(VIEW_ONLY)})
    g = R.pilot_gate(rows, ["a"], mode="delivery")
    assert g["allowed"] is False and g["mode"] == "delivery"
    assert R.pilot_gate(rows, ["a"], mode="viewing")["allowed"] is True


# ---- pilot-only 코호트 ----------------------------------------------------

PILOT_YES = dict(FULL_YES, pilot_only=True, eligible_for_p3_main=False)


def test_pilot_only_flags_are_carried():
    rows = R.audit([_rec("p1")], evidence={"p1": dict(PILOT_YES)})
    assert rows[0]["pilot_only"] is True
    assert rows[0]["eligible_for_p3_main"] is False


def test_pilot_flags_default_false_and_none():
    rows = R.audit([_rec("a")], evidence={})
    assert rows[0]["pilot_only"] is False
    assert rows[0]["eligible_for_p3_main"] is None


def test_pilot_only_video_cannot_be_main_eligible():
    ev = dict(PILOT_YES, eligible_for_p3_main=True)
    with pytest.raises(R.RightsError):
        R.audit([_rec("p1")], evidence={"p1": ev})


def test_pilot_cohort_gate_requires_pilot_only_videos():
    """본 표본 후보를 파일럿에 끌어오면 이후 라벨이 오염된다."""
    rows = R.audit([_rec("a")], evidence={"a": dict(FULL_YES)})
    g = R.pilot_gate(rows, ["a"], mode="delivery", require_pilot_only=True)
    assert g["allowed"] is False
    assert "pilot_only" in g["blocking_reason"]["a"]


def test_pilot_cohort_gate_passes_with_ten_cleared_pilot_videos():
    ids = [f"p{i}" for i in range(10)]
    recs = [_rec(i) for i in ids]
    ev = {i: dict(PILOT_YES) for i in ids}
    g = R.pilot_gate(R.audit(recs, ev), ids, mode="delivery",
                     require_pilot_only=True)
    assert g["allowed"] is True and g["n_pilot"] == 10


def test_report_counts_pilot_cohort():
    r = R.report(records=[_rec("a"), _rec("p1")],
                 evidence={"p1": dict(PILOT_YES)})
    assert r["pilot_only_cleared"] == ["p1"]
    assert r["pilot_cohort_target"] == 10


# ---- mode-specific 판정: 최상위 yes 하나로 합치지 않는다 -------------------

PROV = {"source_url": "https://example.test/v", "license_url":
        "https://example.test/terms", "license_type": "공공누리 제1유형",
        "accessed_at": "2026-08-24"}
FULL2 = dict(FULL_YES, embedded_third_party_content="없음", **PROV)


def test_rights_status_is_recorded_per_mode():
    rows = R.audit([_rec("a")], evidence={"a": dict(FULL2)})
    assert rows[0]["rights_status"] == {"viewing": "yes", "delivery": "yes"}


def test_view_only_rights_status_keeps_delivery_no():
    ev = dict(FULL2, third_party_delivery_right="no")
    e = R.audit([_rec("a")], evidence={"a": ev})[0]
    assert e["rights_status"] == {"viewing": "yes", "delivery": "no"}
    assert e["allowed_access_modes"] == ["viewing"]
    assert e["delivery_prohibited_note"]


def test_unrecorded_mode_is_unclear_not_no():
    ev = {k: v for k, v in FULL2.items()
          if k != "third_party_delivery_right"}
    e = R.audit([_rec("a")], evidence={"a": ev})[0]
    assert e["rights_status"]["delivery"] == "unclear"
    assert e["external_annotation_allowed"] == "unclear"


def test_gate_records_selected_mode_and_pass():
    rows = R.audit([_rec("a")], evidence={"a": dict(FULL2)})
    g = R.pilot_gate(rows, ["a"], mode="viewing")
    assert g["pilot_access_mode"] == "viewing"
    assert g["pilot_gate_pass"] is True


def test_gate_pass_is_false_for_mode_not_allowed():
    ev = dict(FULL2, third_party_delivery_right="no")
    rows = R.audit([_rec("a")], evidence={"a": ev})
    assert R.pilot_gate(rows, ["a"], mode="delivery")["pilot_gate_pass"] is False
    assert R.pilot_gate(rows, ["a"], mode="viewing")["pilot_gate_pass"] is True


# ---- 직접 제작도 자동 yes가 아니다 ----------------------------------------

def test_embedded_third_party_content_is_required_evidence():
    assert "embedded_third_party_content" in R.REQUIRED_EVIDENCE


def test_self_produced_with_embedded_third_party_content_is_not_yes():
    """직접 찍어도 제3자 음악·방송화면·작품이 들어가면 권리가 갈린다."""
    ev = dict(FULL2, basis="직접 촬영",
              embedded_third_party_content="배경음악 상용 트랙")
    e = R.audit([_rec("a")], evidence={"a": ev})[0]
    assert e["external_annotation_allowed"] == "unclear"
    assert "embedded" in e["downgrade_reason"]


def test_self_produced_needs_person_constraint_recorded():
    ev = {k: v for k, v in FULL2.items()
          if k != "identifiable_person_constraint"}
    ev["basis"] = "직접 촬영"
    e = R.audit([_rec("a")], evidence={"a": ev})[0]
    assert e["external_annotation_allowed"] == "unclear"


def test_basis_alone_never_grants_yes():
    e = R.audit([_rec("a")],
                evidence={"a": {"external_annotation_allowed": "yes",
                                "basis": "직접 제작"}})[0]
    assert e["external_annotation_allowed"] == "unclear"


# ---- 근거 재현성 (URL·라이선스·접근일) ------------------------------------

def test_provenance_fields_are_required_for_yes():
    for f in ("source_url", "license_url", "license_type", "accessed_at"):
        assert f in R.REQUIRED_PROVENANCE, f


@pytest.mark.parametrize("missing", ["source_url", "license_url",
                                     "license_type", "accessed_at"])
def test_missing_provenance_blocks_yes(missing):
    ev = {k: v for k, v in FULL2.items() if k != missing}
    e = R.audit([_rec("a")], evidence={"a": ev})[0]
    assert e["external_annotation_allowed"] == "unclear"
    assert missing in e["downgrade_reason"]


def test_snapshot_reference_is_optional_but_reported():
    e = R.audit([_rec("a")], evidence={"a": dict(FULL2)})[0]
    assert e["external_annotation_allowed"] == "yes"
    assert e["evidence_snapshot_ref"] == "미기록"

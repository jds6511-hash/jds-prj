"""영상 외부 반출 권한 감사 (P3-A 라벨 경로 C 선행 조건).

외부 annotator에게 원본 영상·음성을 넘기려면 **영상별 이용 권한**이 확인돼야 한다.
NDA·외주계약은 rights clearance를 대신하지 못한다 — 계약을 맺어도 원래 없던 콘텐츠
이용권이 새로 생기지 않는다.

설계 원칙은 **fail-closed**다.

```
기본값        unclear (반출 불가)
yes 조건      6개 항목이 전부 명시적으로 기록됐고 제3자 제공 권한이 yes일 때만
추정 금지     publisher·acquisition_class·source_url로 권한을 유추하지 않는다
```

레지스트리는 **read-only 투영**으로만 읽는다. SoT 전환은 계속 HOLD이고 이 도구에
writer를 두지 않는다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import video_registry as V                                          # noqa: E402

STATES = ("yes", "no", "unclear")
ACCESS_MODES = ("viewing", "delivery")
EVIDENCE_PATH = ROOT / "planning" / "rights_clearance.json"
PILOT_COHORT_TARGET = 10

# yes로 올라가려면 전부 있어야 하는 항목.
# **열람권과 사본 전달권을 나눠 받는다** — VDI·원격 annotation은 열람권만 필요하고,
# 파일에 담아 보내는 것은 전달권이 따로 있어야 한다.
REQUIRED_EVIDENCE = ("basis", "third_party_viewing_right",
                     "third_party_delivery_right",
                     "retention_redistribution_limit",
                     "deletion_required_after_work",
                     "identifiable_person_constraint",
                     "attribution_requirement")


class RightsError(RuntimeError):
    pass


def load_evidence(path=EVIDENCE_PATH) -> dict:
    """근거 파일이 없으면 빈 dict — 전부 unclear가 된다(정상 초기 상태)."""
    p = Path(path)
    if not p.is_file():
        return {}
    doc = json.loads(p.read_text(encoding="utf-8"))
    ev = doc.get("videos", doc)
    if not isinstance(ev, dict):
        raise RightsError("근거 파일의 videos가 dict가 아니다")
    return ev


def _entry(rec: dict, ev: dict) -> dict:
    sid = rec["source_id"]
    pilot = bool(ev.get("pilot_only", False))
    main_ok = ev.get("eligible_for_p3_main")
    if pilot and main_ok:
        raise RightsError(f"{sid}: pilot_only이면서 eligible_for_p3_main이다 — "
                          f"파일럿에 쓴 영상은 본 표본에 재사용하지 않는다")
    out = {"source_id": sid,
           "acquisition_class": rec.get("acquisition_class"),
           "legacy_exempt": bool(rec.get("legacy_exempt")),
           "pilot_only": pilot,
           "eligible_for_p3_main": (False if pilot else main_ok),
           "basis": ev.get("basis", "없음")}
    for f in REQUIRED_EVIDENCE[1:]:
        out[f] = ev.get(f, "미기록")
    out["allowed_access_modes"] = []

    state = ev.get("external_annotation_allowed", "unclear")
    if state not in STATES:
        raise RightsError(f"{sid}: 허용되지 않는 상태값 {state!r} — {STATES}")

    if state == "no":
        out["external_annotation_allowed"] = "no"
        return out

    view = ev.get("third_party_viewing_right")
    deliver = ev.get("third_party_delivery_right")
    # 열람 자체가 막혀 있으면 사본 전달 주장은 성립하지 않는다(보수적으로 닫는다)
    if view == "no":
        out["external_annotation_allowed"] = "no"
        out["downgrade_reason"] = ("제3자 열람 권한이 없다 — 사본 전달 여부와 "
                                  "무관하게 외부 annotation이 불가능하다")
        return out
    if deliver == "no" and view == "yes":
        # VDI·원격 열람 경로만 남는다 — 전체를 no로 닫지 않는다
        out["allowed_access_modes"] = ["viewing"]
    elif view == "yes" and deliver == "yes":
        out["allowed_access_modes"] = list(ACCESS_MODES)

    missing = [f for f in REQUIRED_EVIDENCE if f not in ev]
    if state == "yes" and missing:
        out["external_annotation_allowed"] = "unclear"
        out["allowed_access_modes"] = []
        out["downgrade_reason"] = (f"근거 항목 미기록: {missing} — 없는 값을 "
                                  f"추정해 yes로 올리지 않는다")
        return out

    if state == "yes" and not out["allowed_access_modes"]:
        out["external_annotation_allowed"] = "unclear"
        out["downgrade_reason"] = ("열람·전달 권한이 yes/no로 기록되지 않았다 — "
                                  "허용 경로가 특정되지 않는다")
        return out

    out["external_annotation_allowed"] = "yes" if state == "yes" else "unclear"
    if state != "yes":
        out["allowed_access_modes"] = []
        out["downgrade_reason"] = "명시적 근거가 기록되지 않았다"
    return out


def audit(records: list, evidence: dict) -> list:
    ids = {r["source_id"] for r in records}
    unknown = sorted(set(evidence) - ids)
    if unknown:
        raise RightsError(f"근거 파일에 없는 영상이 있다: {unknown} — 오타이거나 "
                          f"레지스트리에 없는 영상이다")
    return [_entry(r, evidence.get(r["source_id"], {})) for r in records]


def transferable(entry: dict, mode: str = "delivery") -> bool:
    """`unclear`는 반출 불가다 — 판단을 보류한 것이 허가가 되지 않는다.

    경로를 구분한다. `viewing`은 VDI·원격 열람, `delivery`는 사본 전달이다.
    """
    if mode not in ACCESS_MODES:
        raise RightsError(f"허용되지 않는 접근 경로 {mode!r} — {ACCESS_MODES}")
    return (entry["external_annotation_allowed"] == "yes"
            and mode in entry.get("allowed_access_modes", []))


def pilot_gate(rows: list, pilot_ids: list, mode: str = "delivery",
               require_pilot_only: bool = False) -> dict:
    """파일럿 영상 **전부**가 해당 경로로 허용될 때만 실제 반출을 시작한다."""
    by_id = {r["source_id"]: r for r in rows}
    missing = [i for i in pilot_ids if i not in by_id]
    if missing:
        raise RightsError(f"감사 대상에 없는 파일럿 영상: {missing}")
    blocking, why = [], {}
    for i in pilot_ids:
        e = by_id[i]
        reasons = []
        if not transferable(e, mode=mode):
            reasons.append(f"{mode} 권한 미확인 "
                           f"({e['external_annotation_allowed']})")
        if require_pilot_only and not e.get("pilot_only"):
            reasons.append("pilot_only가 아니다 — 본 표본 후보를 파일럿에 쓰면 "
                           "이후 라벨이 오염된다")
        if reasons:
            blocking.append(i)
            why[i] = "; ".join(reasons)
    return {"pilot_ids": list(pilot_ids), "n_pilot": len(pilot_ids),
            "mode": mode, "require_pilot_only": require_pilot_only,
            "allowed": not blocking, "blocking": blocking,
            "blocking_reason": why,
            "rule": "하나라도 허용되지 않으면 파일럿 반출을 시작하지 않는다"}


def report(records=None, evidence=None) -> dict:
    if records is None:
        records = V.project_from_selection()
    if evidence is None:
        evidence = load_evidence()
    rows = audit(records, evidence)
    counts = {s: sum(1 for r in rows if
                     r["external_annotation_allowed"] == s) for s in STATES}
    ready = sorted(r["source_id"] for r in rows if transferable(r))
    view_only = sorted(r["source_id"] for r in rows
                       if r.get("allowed_access_modes") == ["viewing"])
    pilot_ok = sorted(r["source_id"] for r in rows if r.get("pilot_only")
                      and r["external_annotation_allowed"] == "yes")
    return {
        "ready_for_remote_viewing_only": view_only,
        "pilot_only_cleared": pilot_ok,
        "pilot_cohort_target": PILOT_COHORT_TARGET,
        "pilot_cohort_note": ("파일럿 코호트는 main 300편과 완전히 별개다 — "
                              "pilot_only=true · eligible_for_p3_main=false로 "
                              "영구 제외한다"),
        "probe": "p3_rights_audit",
        "purpose": ("외부 annotator에게 원본 영상·음성을 넘길 권한이 영상별로 "
                    "있는지 확인한다. 반출 승인 자체가 아니다"),
        "n_videos": len(rows),
        "counts": counts,
        "videos": rows,
        "ready_for_external_transfer": ready,
        "external_transfer_status": "HOLD" if not ready else "부분_확인",
        "inference_allowed": False,
        "inference_rule": ("publisher·acquisition_class·source_url로 권한을 "
                           "유추하지 않는다. 기본값은 unclear이고, unclear는 "
                           "반출 불가다"),
        "contract_is_not_clearance": ("NDA·외주계약은 rights clearance를 대신하지 "
                                      "못한다 — 계약을 맺어도 원래 없던 콘텐츠 "
                                      "이용권이 새로 생기지 않는다"),
        "vdi_alternative": {
            "candidate": ("다운로드 불가 VDI·원격 annotation 환경 — 원본이 통제 "
                          "영역을 벗어나지 않는 구조"),
            "bypasses_rights_clearance": False,
            "note": ("원격 제3자에게 열람시키는 행위 자체의 허용 여부도 source "
                     "terms 확인 대상이다"),
        },
        "required_evidence_fields": list(REQUIRED_EVIDENCE),
        "evidence_path": str(EVIDENCE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "evidence_present": bool(evidence),
        "registry_access": "read-only 투영 (project_from_selection). writer 없음",
        "sot_transition": "HOLD",
        "not_covered": [
            "P3 신규 300편 — 아직 수집하지 않았으므로 감사 대상에 없다",
            "파일럿 후보 영상 — 선정 후 같은 절차로 감사한다",
            "법률 자문 — 이 도구는 상태를 기록할 뿐 적법성을 판단하지 않는다",
        ],
    }


def main():
    ap = argparse.ArgumentParser(description="외부 반출 권한 감사 (fail-closed)")
    ap.add_argument("--out")
    a = ap.parse_args()
    r = report()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

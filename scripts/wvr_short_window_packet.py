"""SHORT_WINDOW_V1 blinded adjudication packet 생성 (2026-09-09).

사전등록: `docs/preregistration/WVR_SHORT_WINDOW_V1_2026-09-09.md`

```
packet    창별 collapsed event sequence를 Arm A / Arm B로 가려서 낸다
숨김      density mapping(어느 쪽이 0.5fps인지)·salt·자동 matcher 진단
공개 시점 사람 판정이 끝난 뒤 --reveal로 매핑을 연다
```

자동 matcher는 audit diagnostic으로만 저장한다 — 판정 authority가 아니다.
GPU를 쓰지 않는다.
"""
import argparse
import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_density as density                               # noqa: E402
import wvr_density_v2 as v2                                 # noqa: E402
import wvr_short_window as sw                               # noqa: E402

PACKET_NAME = "short_window_packet.md"
BLIND_MAP_NAME = "short_window_blind_map.json"
AUDIT_NAME = "short_window_audit.json"
VERDICT_NAME = "short_window_verdicts.json"

# packet에 절대 넣지 않는 것 (density를 노출한다)
LEAKING_FIELDS = ("fps", "frames", "delivered_frame_count", "input_token_count",
                  "generated_token_count", "video_token_count", "arm")


class PacketError(RuntimeError):
    """packet 계약 위반."""


def load_arm(runs: Path, window_id: str, arm: str) -> dict:
    path = runs / ("%s_%s_%s.json" % (sw.ARTIFACT_TAG, window_id, arm))
    if not path.is_file():
        raise PacketError("산출물이 없다: %s" % path.name)
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("event") != sw.EVENT:
        raise PacketError("SHORT_WINDOW 산출물이 아니다: %s" % path.name)
    return record


def technical_failures(records: dict) -> list:
    """arm 정체를 드러내지 않는 형태(창 + A/B 표지)로 무효 사유를 모은다."""
    rows = []
    for (window_id, arm), record in records.items():
        validity = record.get("arm_validity") or {}
        if not validity.get("valid"):
            rows.append({"window_id": window_id,
                         "label": record["blind_label"],
                         "reasons": validity.get("reasons") or ["UNKNOWN"]})
    return rows


def audit_alignment(reference: dict, arm: dict) -> dict:
    """자동 matcher — audit diagnostic 전용."""
    left = (reference.get("parsed") or {}).get("collapsed") or []
    right = (arm.get("parsed") or {}).get("collapsed") or []
    per_tolerance = {}
    for tolerance in density.MATCH_TOLERANCE_SEC:
        alignment = v2.align(left, right, tolerance)
        per_tolerance["tol_%.1f" % tolerance] = {
            "temporally_compatible_count":
                alignment["temporally_compatible_count"],
            "equivalent_count": alignment["equivalent_count"],
            "adjudication_count": alignment["adjudication_count"],
            "different_count": sum(
                1 for row in alignment["candidates"]
                if row["relation"] == v2.SEMANTICALLY_DIFFERENT),
            "reference_only": len(alignment["reference_only"]),
            "arm_only": len(alignment["arm_only"]),
            "reference_without_equivalent":
                len(alignment["reference_without_equivalent"]),
            "arm_without_equivalent":
                len(alignment["arm_without_equivalent"]),
            "merge_candidates": len(alignment["merge_candidates"]),
            "split_candidates": len(alignment["split_candidates"]),
            "order_inversions": alignment["order_inversions"],
        }
    return {"role": sw.AUTOMATIC_MATCHER_ROLE, "per_tolerance": per_tolerance}


def event_lines(record: dict) -> list:
    rows = (record.get("parsed") or {}).get("collapsed") or []
    return ["%7.1f–%7.1f | %s | %s | %s"
            % (row["start_sec"], row["end_sec"], row["actor"], row["action"],
               row["object_or_state"]) for row in rows]


def build(runs: Path, salt: str) -> dict:
    windows = sw.derive_windows(json.loads(
        (runs / sw.SOURCE_ARTIFACT).read_text(encoding="utf-8")))
    sw.assert_expected(windows)

    records, mapping, audit = {}, {}, {}
    for window in windows:
        window_id = window["window_id"]
        mapping[window_id] = {}
        for arm in sw.ARMS:
            record = load_arm(runs, window_id, arm)
            label = sw.blind_label(window_id, arm, salt)
            record["blind_label"] = label
            records[(window_id, arm)] = record
            mapping[window_id][label] = arm
        if set(mapping[window_id]) != {"A", "B"}:
            raise PacketError("A/B 배정이 깨졌다: %s" % window_id)
        audit[window_id] = audit_alignment(records[(window_id, sw.ARM_S0)],
                                           records[(window_id, sw.ARM_S1)])

    failures = technical_failures(records)
    lines = ["# SHORT_WINDOW_V1 blinded adjudication packet",
             "",
             "사전등록: `docs/preregistration/WVR_SHORT_WINDOW_V1_2026-09-09.md`",
             "",
             "```",
             "각 창의 두 출력은 Arm A · Arm B로 가려져 있다.",
             "어느 쪽이 0.5fps(higher-density reference)인지는 판정 전까지 공개되지 않는다.",
             "0.5fps는 truth가 아니다 — 어느 쪽이 더 촘촘한지가 정답을 뜻하지 않는다.",
             "판정값은 STABLE · GRANULARITY_SHIFT · MATERIAL_DIVERGENCE · UNRESOLVED 넷뿐이다.",
             "```",
             "",
             "```",
             "기술 게이트   %s" % ("6/6 통과 (파싱 · 절단 없음 · English-only · 표현 비축퇴)"
                                if not failures else
                                "실패 %d건 — %s" % (len(failures), failures)),
             "```",
             ""]
    for window in windows:
        window_id = window["window_id"]
        lines += ["## %s  %.0f–%.0f초 (48초)"
                  % (window_id, window["start_sec"], window["end_sec"]), ""]
        for label in ("A", "B"):
            arm = mapping[window_id][label]
            lines += ["### Arm %s" % label, "", "```",
                      "  start–  end  | actor | action | object_or_state"]
            lines += ["  " + row for row in event_lines(records[(window_id,
                                                                 arm)])]
            lines += ["```", ""]

    packet = "\n".join(lines).rstrip() + "\n"
    return {
        "packet": packet,
        "blind_map": {
            "event": sw.EVENT, "salt": salt, "salt_sha256": sw.salt_hash(salt),
            "mapping": mapping,
            "note": ("이 파일은 adjudication이 끝나기 전에 리뷰어에게 보여주지 "
                     "않는다. packet에는 salt_sha256만 들어간다."),
        },
        "audit": {
            "event": sw.EVENT, "role": sw.AUTOMATIC_MATCHER_ROLE,
            "salt_sha256": sw.salt_hash(salt),
            "windows": audit, "technical_failures": failures,
            "note": ("자동 matcher는 판정 authority가 아니다(V2에서 exact-string "
                     "matcher의 한계가 확인됐다). 사람 판정 후 대조용으로만 쓴다."),
        },
        "technical_failures": failures,
        "windows": windows,
    }


def write(runs: Path, built: dict) -> None:
    (runs / PACKET_NAME).write_text(built["packet"], encoding="utf-8")
    (runs / BLIND_MAP_NAME).write_text(
        json.dumps(built["blind_map"], ensure_ascii=False, indent=1),
        encoding="utf-8")
    (runs / AUDIT_NAME).write_text(
        json.dumps(built["audit"], ensure_ascii=False, indent=1),
        encoding="utf-8")


def parse_verdicts(raw: str) -> dict:
    rows = {}
    for chunk in raw.split(","):
        window_id, _, verdict = chunk.strip().partition("=")
        if verdict not in sw.VERDICTS:
            raise PacketError("모르는 판정값: %r" % verdict)
        rows[window_id] = verdict
    expected = [row[0] for row in sw.EXPECTED_WINDOWS]
    if sorted(rows) != sorted(expected):
        raise PacketError("창 %r 전부의 판정이 필요하다" % expected)
    return rows


def reveal(runs: Path, verdicts: dict) -> dict:
    blind = json.loads((runs / BLIND_MAP_NAME).read_text(encoding="utf-8"))
    audit = json.loads((runs / AUDIT_NAME).read_text(encoding="utf-8"))
    order = [row[0] for row in sw.EXPECTED_WINDOWS]
    verdict = sw.probe_verdict([verdicts[window_id] for window_id in order],
                               audit["technical_failures"])
    return {
        "event": sw.EVENT, "probe_verdict": verdict,
        "window_verdicts": verdicts,
        "window_pass": {window_id: sw.window_pass(value)
                        for window_id, value in verdicts.items()},
        "blind_mapping": blind["mapping"], "salt_sha256": blind["salt_sha256"],
        "technical_failures": audit["technical_failures"],
        "automatic_matcher_role": sw.AUTOMATIC_MATCHER_ROLE,
        "semantic_sufficiency_claim_allowed":
            sw.SEMANTIC_SUFFICIENCY_CLAIM_ALLOWED,
        "allowed_pass_conclusion": sw.ALLOWED_PASS_CONCLUSION,
        "event_extraction_approved": sw.EVENT_EXTRACTION_APPROVED,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="blinded packet · reveal")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--reveal", metavar="P1=STABLE,P2=...,P3=...")
    args = parser.parse_args(argv)
    runs = Path(args.runs)

    if args.reveal:
        record = reveal(runs, parse_verdicts(args.reveal))
        (runs / VERDICT_NAME).write_text(
            json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        print("probe_verdict=%s" % record["probe_verdict"])
        for window_id, value in sorted(record["window_verdicts"].items()):
            print("  %s %s pass=%s  A=%s B=%s"
                  % (window_id, value, record["window_pass"][window_id],
                     record["blind_mapping"][window_id]["A"],
                     record["blind_mapping"][window_id]["B"]))
        return 0

    built = build(runs, secrets.token_hex(16))
    write(runs, built)
    print("packet=%s  blind_map=%s  audit=%s"
          % (PACKET_NAME, BLIND_MAP_NAME, AUDIT_NAME))
    print("technical_failures=%s" % (built["technical_failures"] or "없음"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

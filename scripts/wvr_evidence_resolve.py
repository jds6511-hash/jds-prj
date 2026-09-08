"""V2 충돌 claim을 채택 제출본 canonical evidence로 대조한다 (2026-09-09).

사전등록: `docs/preregistration/WVR_EVIDENCE_RESOLUTION_V1_2026-09-09.md`

```
새 추론 없음 · GPU 없음 · 읽기 전용.
입력  frozen V2 산출물 6건 + segments.json(5초 evidence) + aar_canonical.json(1분 episode)
금지  episode summary를 evidence로 쓰는 것, 없음을 CONTRADICTS로 쓰는 것,
      사전 표면형을 evidence 열람 후 추가하는 것
```
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wvr_density_v1b as events                              # noqa: E402
import wvr_evidence_lexicon as lex                            # noqa: E402
import wvr_evidence_v1 as ev                                  # noqa: E402

PAIRS = ("D1", "D2", "D3")


class ResolveError(RuntimeError):
    """evidence resolution 계약 위반."""


def assert_no_inference() -> None:
    for banned in ("torch", "transformers"):
        if banned in sys.modules:
            raise ResolveError("추론 라이브러리가 로드됐다: %s" % banned)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def load_v2(runs: Path, pair: str, arm: str) -> dict:
    path = runs / ("%s_%s_%s.json" % (events.tag_for(events.EVENT_V2), pair,
                                      arm))
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("event") != events.EVENT_V2:
        raise ResolveError("V2 산출물이 아니다: %s" % path.name)
    if record.get("arm_status") != "ARM_VALID":
        raise ResolveError("무효 arm은 입력으로 쓰지 않는다: %s" % path.name)
    return record


def episodes_for(canonical: dict, start: float, end: float) -> list:
    rows = []
    for episode in canonical["episodes"]:
        if float(episode["start_sec"]) < end and \
                float(episode["end_sec"]) > start:
            rows.append({
                "episode_id": episode["episode_id"],
                "start_sec": float(episode["start_sec"]),
                "end_sec": float(episode["end_sec"]),
                "source": episode.get("source"),
                "grounding_status": episode.get("grounding_status"),
                "content_status": episode.get("content_status"),
            })
    return rows


def resolve_candidate(row: dict, segments: list, canonical: dict) -> dict:
    start, end = row["evidence_window"]
    evidence = ev.evidence_segments(segments, start, end)
    ref_terms = ev.claim_terms(row["reference"])
    arm_terms = ev.claim_terms(row["arm"])
    ref_support = ev.claim_support(ref_terms, evidence)
    arm_support = ev.claim_support(arm_terms, evidence)
    ref_verdict = ev.claim_verdict(ref_support, arm_support)
    arm_verdict = ev.claim_verdict(arm_support, ref_support)
    return {
        "source": row["source"],
        "reference": row["reference"], "arm": row["arm"],
        "evidence_window": [start, end],
        "evidence_segment_idx": [seg["idx"] for seg in evidence],
        "pre_freeze_viewed_idx": [seg["idx"] for seg in evidence
                                  if seg["pre_freeze_viewed"]],
        "episodes": episodes_for(canonical, start, end),
        "reference_terms": ref_terms, "arm_terms": arm_terms,
        "reference_support": ref_support, "arm_support": arm_support,
        "reference_verdict": ref_verdict["verdict"],
        "reference_reasons": ref_verdict["reasons"],
        "arm_verdict": arm_verdict["verdict"],
        "arm_reasons": arm_verdict["reasons"],
        "resolution": ev.pair_resolution(ref_verdict["verdict"],
                                         arm_verdict["verdict"]),
    }


def find_event(collapsed: list, span: tuple):
    for row in collapsed:
        if (float(row["start_sec"]), float(row["end_sec"])) == span:
            return row
    return None


def add_reviewer_named(candidates: list, pair: str, reference_events: list,
                       arm_events: list) -> list:
    """리뷰어 지목 쌍을 union으로 합친다(중복은 source 태그만 추가)."""
    rows = list(candidates)
    for named_pair, ref_span, arm_span in ev.REVIEWER_NAMED_CONFLICTS:
        if named_pair != pair:
            continue
        existing = None
        for row in rows:
            if (float(row["reference"]["start_sec"]),
                float(row["reference"]["end_sec"])) == ref_span and \
                (float(row["arm"]["start_sec"]),
                 float(row["arm"]["end_sec"])) == arm_span:
                existing = row
                break
        if existing is not None:
            if ev.SOURCE_REVIEWER not in existing["source"]:
                existing["source"].append(ev.SOURCE_REVIEWER)
            continue
        reference = find_event(reference_events, ref_span)
        arm = find_event(arm_events, arm_span)
        if reference is None or arm is None:
            raise ResolveError("리뷰어 지목 구간이 frozen 출력에 없다: %s %s %s"
                               % (named_pair, ref_span, arm_span))
        rows.append({
            "reference_index": reference_events.index(reference),
            "arm_index": arm_events.index(arm),
            "reference": reference, "arm": arm,
            "evidence_window": ev.evidence_window(reference, arm),
            "source": [ev.SOURCE_REVIEWER],
        })
    return rows


def resolve(runs: Path, segments_path: Path, canonical_path: Path,
            video_path: Path) -> dict:
    assert_no_inference()
    segments_sha = sha256(segments_path)
    if segments_sha != ev.EXPECTED_SEGMENTS_SHA256:
        raise ResolveError("segments.json 해시 불일치: %s" % segments_sha)
    video_sha = sha256(video_path)
    if video_sha != ev.EXPECTED_VIDEO_SHA256:
        raise ResolveError("영상 해시 불일치: %s" % video_sha)

    segments = json.loads(segments_path.read_text(encoding="utf-8"))["segments"]
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))

    rows, totals = {}, {ev.REFERENCE_ONLY: 0, ev.ARM_ONLY: 0,
                        ev.BOTH_SUPPORTED: 0, ev.NEITHER_RESOLVED: 0}
    for pair in PAIRS:
        s0 = load_v2(runs, pair, "S0")
        s1 = load_v2(runs, pair, "S1")
        reference_events = s0["parsed"]["collapsed"]
        arm_events = s1["parsed"]["collapsed"]
        per_tolerance = {}
        for tolerance in ev.TOLERANCES:
            found = ev.candidate_pairs(reference_events, arm_events, tolerance)
            per_tolerance["tol_%.1f" % tolerance] = {
                "candidate_count": len(found),
                "reviewer_coverage": ev.reviewer_coverage(found, pair),
            }
        primary = ev.candidate_pairs(reference_events, arm_events,
                                     ev.PRIMARY_TOLERANCE)
        merged = add_reviewer_named(primary, pair, reference_events,
                                    arm_events)
        resolved = [resolve_candidate(row, segments, canonical)
                    for row in merged]
        counts = dict.fromkeys(totals, 0)
        for row in resolved:
            counts[row["resolution"]] += 1
            totals[row["resolution"]] += 1
        rows[pair] = {
            "window": s0["window"],
            "reference_event_count": len(reference_events),
            "arm_event_count": len(arm_events),
            "per_tolerance": per_tolerance,
            "conflict_count": len(resolved),
            "resolution_counts": counts,
            "conflicts": resolved,
        }

    verdict = ev.event_verdict(totals[ev.REFERENCE_ONLY], totals[ev.ARM_ONLY])
    return {
        "schema": "wvr_evidence_resolution_v1", "event": ev.EVENT,
        "prereg": ("docs/preregistration/"
                   "WVR_EVIDENCE_RESOLUTION_V1_2026-09-09.md"),
        "code_git_head": git_head(),
        "new_inference_allowed": ev.NEW_INFERENCE_ALLOWED,
        "semantic_sufficiency_claim_allowed":
            ev.SEMANTIC_SUFFICIENCY_CLAIM_ALLOWED,
        "promotion_allowed": ev.PROMOTION_ALLOWED,
        "event_extraction_approved": ev.EVENT_EXTRACTION_APPROVED,
        "inputs": {
            "segments": str(segments_path).replace("\\", "/"),
            "segments_sha256": segments_sha,
            "segment_count": len(segments),
            "video_sha256": video_sha,
            "canonical": str(canonical_path).replace("\\", "/"),
            "canonical_run_id": canonical.get("run_id"),
            "canonical_boundary": canonical.get("boundary"),
            "canonical_episode_count": len(canonical["episodes"]),
            "non_evidence_fields": list(ev.NON_EVIDENCE_FIELDS),
        },
        "lexicon": {
            "name": lex.LEXICON_NAME, "hash": lex.lexicon_hash(),
            "source": lex.SOURCE,
            "collision_dropped": {term: list(owners) for term, owners
                                  in lex.COLLISION_DROPPED.items()},
            "action_entry_count": len(lex.ACTION_TERMS),
            "object_entry_count": len(lex.OBJECT_TERMS),
        },
        "pre_freeze_viewed_seg_idx": list(ev.PRE_FREEZE_VIEWED_SEG_IDX),
        "match_tolerances": list(ev.TOLERANCES),
        "primary_tolerance_sec": ev.PRIMARY_TOLERANCE,
        "pairs": rows, "resolution_totals": totals,
        "event_verdict": verdict,
        "note": ("caption 채널은 Qwen2.5-VL-3B-4bit 출력이고 subtitle은 Whisper ASR"
                 "이다. 어느 쪽도 인간 GT가 아니므로 판정은 이 evidence 층에 대한 "
                 "지지·반증일 뿐이다. 지지 부재는 반증이 아니다."),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="V2 충돌 evidence 대조")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    parser.add_argument("--segments", default=ev.SEGMENTS_PATH)
    parser.add_argument("--canonical", default=ev.CANONICAL_PATH)
    parser.add_argument("--video", default="data/videos/full_xekZO4n4QuE.mp4")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    record = resolve(Path(args.runs), Path(args.segments),
                     Path(args.canonical), Path(args.video))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                        encoding="utf-8")

    print("event_verdict=%s totals=%s" % (record["event_verdict"],
                                          record["resolution_totals"]))
    for pair in PAIRS:
        row = record["pairs"][pair]
        print("%s %s conflicts=%s %s" % (
            pair, row["window"]["window_id"], row["conflict_count"],
            row["resolution_counts"]))
        for tolerance in ("tol_4.0", "tol_8.0"):
            cover = row["per_tolerance"][tolerance]["reviewer_coverage"]
            print("   %s candidates=%s reviewer=%s missing=%s" % (
                tolerance, row["per_tolerance"][tolerance]["candidate_count"],
                cover["status"], len(cover["missing"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

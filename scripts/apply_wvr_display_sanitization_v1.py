"""표시 계층 정화 + 행 내부 반복 정리 — 새 추론 0회.

```
입력   runs/wvr_multimodal_clean_v1/<vid>/          (읽기 전용)
       기존 visual event_timeline.json              (읽기 전용 · broad_activity 참조용)
출력   runs/wvr_multimodal_clean_v1_patch2/<vid>/
```

patch1(안전 fallback + 자막 크레딧 필터)의 판단을 그대로 다시 태우고, 그 위에
표시 단계만 두 가지 고친다 — visual 원문의 비한국어 혼입, 행 안의 연속 반복.
경계·관계·chapter·임계·어휘집·프롬프트·transcript는 건드리지 않는다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "jds_video" / "_internal"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_multimodal_report_v1 as report_mod         # noqa: E402
import wvr_safe_fallback_v1 as safe                   # noqa: E402
import wvr_display_sanitize_v1 as sanitize            # noqa: E402
from apply_wvr_safe_fallback_patch_v1 import (        # noqa: E402
    coverage, largest_gap, load, parse_rows, write)

EVENT = "WVR_DISPLAY_SANITIZATION_AND_LOCAL_DEDUP_PATCH_V1"


def visual_records(path):
    """원본 visual artifact — 읽기만 한다. category·broad_activity만 꺼낸다."""
    if not path or not Path(path).is_file():
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    events = payload if isinstance(payload, list) else payload.get("events", [])
    return {e["event_id"]: {"category": e.get("category", ""),
                            "broad_activity": list(e.get("broad_activity", [])),
                            "summary": e.get("summary", ""),
                            "claim_ids": list(e.get("supporting_claim_ids", [])),
                            "support_intervals": list(e.get("support_intervals", []))}
            for e in events if e.get("event_id")}


def sanitize_event_text(event, records):
    """timeline event의 화면 서술을 표시용으로 정한다."""
    ids = event.get("visual_event_ids") or []
    record = records.get(ids[0], {}) if ids else {}
    return sanitize.sanitize_visual_text(event.get("summary", ""),
                                         category=record.get("category") or event.get("category"),
                                         broad_activity=record.get("broad_activity", []))


def main(argv=None):
    ap = argparse.ArgumentParser(description=EVENT)
    ap.add_argument("--clean-dir", required=True)
    ap.add_argument("--visual-events", required=True, help="원본 event_timeline.json(읽기 전용)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--duration-sec", type=float, required=True)
    ap.add_argument("--patch1-dir", required=True, help="BEFORE 비교 대상")
    ap.add_argument("--overview-title")
    args = ap.parse_args(argv)

    clean, out_dir = Path(args.clean_dir), Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    transcript = load(clean / "speech" / "transcript_raw.json")
    utterances = {u["id"]: u for u in transcript["utterances"]}
    speech_events = {e["speech_event_id"]: e
                     for e in load(clean / "speech" / "speech_events.json")["speech_events"]}
    timeline = load(clean / "multimodal_timeline.json")["events"]
    chapters = load(clean / "semantic_chapters.json")["chapters"]
    guard = load(clean / "guard_report.json")
    asr = load(clean / "speech" / "asr_diagnostics.json")
    asr_states = {f["utterance_id"]: f["state"] for f in asr["utterance_flags"]}
    records = visual_records(args.visual_events)

    subtitle_flags = safe.subtitle_credit_flags(list(utterances.values()))
    credit_ids = [uid for uid, flagged in subtitle_flags.items() if flagged]

    # 화면 근거 후보 — 표시 가능한 문장이 남는 event만 대체에 쓴다
    visual_only = [e for e in timeline if e["evidence_type"] == "VISUAL"]

    def visual_for(event):
        best, overlap = None, 0.0
        for candidate in visual_only:
            span = min(event["end"], candidate["end"]) - max(event["start"], candidate["start"])
            if span > overlap:
                best, overlap = candidate, span
        return (best, sanitize_event_text(best, records)) if best else (None, None)

    sanitation, dedup_log, decisions, rows = [], [], {}, []

    def emit(event, summary, evidence, display, category, speech_ids, utterance_ids,
             sanitized=None):
        cleaned = sanitize.dedup_local(summary)
        if cleaned["removed"]:
            dedup_log.append({"row_id": "ROW%03d" % (len(rows) + 1),
                              "start": event["start"], "end": event["end"],
                              "original_fallback_text": summary,
                              "display_fallback_text": cleaned["text"],
                              "removed_repetitions": cleaned["removed"]})
        rows.append({"row_id": "ROW%03d" % (len(rows) + 1), "start": event["start"],
                     "end": event["end"], "category": category, "summary": cleaned["text"],
                     "evidence": evidence, "display": display,
                     "visual_event_ids": event.get("visual_event_ids", []),
                     "speech_event_ids": speech_ids, "utterance_ids": utterance_ids,
                     "visual_claim_ids": event.get("visual_claim_ids", []),
                     "visual_display_decision": (sanitized or {}).get("display_decision"),
                     "original_text": (sanitized or {}).get("original_text"),
                     "removed_repetitions": cleaned["removed"]})

    for event in sorted(timeline, key=lambda e: (e["start"], e["end"])):
        speech_ids = event.get("speech_event_ids", [])

        if not speech_ids:
            if report_mod.is_speaking_only(event.get("summary", "")):
                continue
            verdict = sanitize_event_text(event, records)
            sanitation.append({"row_kind": "VISUAL", "start": event["start"],
                               "end": event["end"],
                               "visual_event_ids": event.get("visual_event_ids", []),
                               "visual_claim_ids": event.get("visual_claim_ids", []),
                               **verdict})
            if not verdict["display_text"]:
                continue                       # 오염 문장을 사용자 화면에서 숨긴다
            emit(event, verdict["display_text"], "화면", "VISUAL_EVIDENCE",
                 event.get("category", ""), [], [], verdict)
            continue

        speech_id = speech_ids[0]
        source = speech_events.get(speech_id, {})
        record = guard["events"].get(speech_id, {})
        items = [utterances[uid] for uid in source.get("supporting_utterance_ids", [])
                 if uid in utterances]
        fallback_event, fallback_verdict = visual_for(event)
        if fallback_verdict is not None:
            sanitation.append({"row_kind": "VISUAL_FALLBACK_SOURCE",
                               "start": event["start"], "end": event["end"],
                               "speech_event_id": speech_id,
                               "visual_event_ids": fallback_event.get("visual_event_ids", []),
                               "visual_claim_ids": fallback_event.get("visual_claim_ids", []),
                               **fallback_verdict})
        decision = safe.display_decision(
            approved=record.get("approved", False), reasons=record.get("reasons", []),
            generated=record.get("generated", ""), extractive=source.get("summary", ""),
            utterances=items, subtitle_flags=subtitle_flags, asr_states=asr_states,
            visual_summary=(fallback_verdict or {}).get("display_text"),
            summary_source=record.get("summary_source"))
        decisions[speech_id] = {**decision, "start": event["start"], "end": event["end"],
                                "previous_source": record.get("summary_source"),
                                "previous_summary": record.get("used")}
        if decision["summary"]:
            downgraded = decision["display"] == safe.VISUAL_ONLY_DOWNGRADE
            emit(event, decision["summary"], decision["evidence"], decision["display"],
                 "관찰 장면" if downgraded else event.get("category", ""),
                 speech_ids, decision["utterance_ids"],
                 fallback_verdict if downgraded else None)

    # ── 개요·제목: 표시되는 문장만 입력으로 다시 검증한다(새 생성 없음) ──
    import wvr_generative_guard_v1 as gen_guard
    import wvr_grounding_guard_v1 as grounding

    safe_texts = safe.overview_input_texts(rows)
    write(out_dir / "overview_input.json", {
        "event": EVENT, "video_id": args.video_id,
        "note": "표시되는 행만 담는다 — 보류·자막 크레딧·오염 문장 제외",
        "chapters": [{"chapter_id": c["chapter_id"], "start": c["start"], "end": c["end"],
                      "title": c["title"], "summary": c["summary"]} for c in chapters],
        "rows": [{"start": r["start"], "end": r["end"], "category": r["category"],
                  "summary": r["summary"], "evidence": r["evidence"]} for r in rows]})

    overview, title = report_mod.compose_overview(rows), None
    overview_source, title_source = "EXTRACTIVE_FALLBACK", "EXTRACTIVE_FALLBACK"
    if args.overview_title and Path(args.overview_title).is_file():
        injected = load(args.overview_title)
        candidate = ((injected.get("overview") or {}).get("parsed") or {}).get("summary", "")
        if (candidate and sanitize.script_clean(candidate)
                and gen_guard.language_gate(candidate)["status"] == gen_guard.PASS
                and grounding.check_grounding(candidate, safe_texts)["status"] == grounding.GROUNDED):
            overview, overview_source = sanitize.dedup_local(candidate)["text"], "GENERATIVE"
        name = ((injected.get("title") or {}).get("parsed") or {}).get("category", "")
        if (name and sanitize.script_clean(name)
                and gen_guard.language_gate(name)["status"] == gen_guard.PASS
                and grounding.check_grounding(name, safe_texts)["status"] == grounding.GROUNDED):
            title, title_source = name, "GENERATIVE"

    lines = ["# %s" % (title or "%s 영상 보고서" % args.video_id), "", "□ 개요", "",
             overview.strip(), "", "□ 세부내용", "",
             "| 구분 | 시간 | 내용 | 비고 |", "|---|---|---|---|"]
    for row in rows:
        lines.append("| %s | %s ~ %s | %s | %s |"
                     % (row["category"], report_mod.hhmmss(row["start"]),
                        report_mod.hhmmss(row["end"]), row["summary"], row["evidence"]))
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    # ── sidecar: 숨긴 문장의 원문·근거를 모두 남긴다 ──
    sidecar = report_mod.build_sidecar(rows, [], transcript_path=str(
        clean / "speech" / "transcript_raw.json"))
    sidecar["withheld_speech_events"] = [
        {"speech_event_id": sid, "display": d["display"], "reason": d["reason"],
         "utterance_ids": d["utterance_ids"]}
        for sid, d in decisions.items()
        if d["display"] in (safe.AUDIO_WITHHELD_ASR_UNRELIABLE, safe.NON_REPORTABLE_EVENT)]
    sidecar["visual_display_sanitation"] = sanitation
    sidecar["local_repetition_cleanup"] = dedup_log
    write(out_dir / "report_evidence.json", sidecar)

    write(out_dir / "visual_sanitation.json", {
        "event": EVENT, "video_id": args.video_id,
        "visual_source": str(args.visual_events),
        "note": "원본 visual claim·frame 근거는 수정하지 않았다. 표시 문장만 정한다.",
        "counts": sanitize.sanitation_counts(sanitation),
        "records": sanitation})
    write(out_dir / "local_dedup.json", {
        "event": EVENT, "video_id": args.video_id,
        "rule": "연속·완전 일치 반복만(문장 → 구 → 낱말). 유사 문장은 제거하지 않는다",
        "cleaned_row_count": len(dedup_log),
        "removed_unit_count": sum(len(d["removed_repetitions"]) for d in dedup_log),
        "rows": dedup_log})
    write(out_dir / "fallback_decisions.json", {
        "event": EVENT, "video_id": args.video_id,
        "display_counts": safe.display_counts(list(decisions.values())),
        "decisions": decisions})

    before_rows = parse_rows(Path(args.patch1_dir) / "report.md")
    after_view = [{"summary": r["summary"], "evidence": r["evidence"],
                   "start": r["start"], "end": r["end"]} for r in rows]
    evidence_counts = {"화면": 0, "음성": 0, "음성+화면": 0}
    for row in rows:
        evidence_counts[row["evidence"]] = evidence_counts.get(row["evidence"], 0) + 1
    withheld = [d for d in decisions.values()
                if d["display"] in (safe.AUDIO_WITHHELD_ASR_UNRELIABLE,
                                    safe.NON_REPORTABLE_EVENT)]
    counts = sanitize.sanitation_counts(sanitation)
    evaluation = {
        "event": EVENT, "video_id": args.video_id,
        "new_model_inference": {"stt": 0, "visual": 0, "summary": 0},
        "rows": {"before": len(before_rows), "after": len(rows)},
        "mixed_script_visual_detected": (counts.get(sanitize.SAFE_VISUAL_DOWNGRADE, 0)
                                         + counts.get(sanitize.VISUAL_TEXT_WITHHELD_MIXED_SCRIPT, 0)),
        "safe_visual_downgrade": counts.get(sanitize.SAFE_VISUAL_DOWNGRADE, 0),
        "visual_text_withheld_mixed_script": counts.get(
            sanitize.VISUAL_TEXT_WITHHELD_MIXED_SCRIPT, 0),
        "local_repetition_cleaned_rows": len(dedup_log),
        "removed_repetition_units": sum(len(d["removed_repetitions"]) for d in dedup_log),
        "display_counts": safe.display_counts(list(decisions.values())),
        "evidence_counts_after": evidence_counts,
        "subtitle_credit_removed": len(credit_ids),
        "audio_withheld": sum(1 for d in decisions.values()
                              if d["display"] == safe.AUDIO_WITHHELD_ASR_UNRELIABLE),
        "visual_only_downgrade": sum(1 for d in decisions.values()
                                     if d["display"] == safe.VISUAL_ONLY_DOWNGRADE),
        "withheld_count": len(withheld),
        "coverage_sec": {"before": coverage(before_rows), "after": coverage(after_view)},
        "largest_gap_sec": {"before": largest_gap(before_rows, args.duration_sec),
                            "after": largest_gap(after_view, args.duration_sec)},
        "overview_source": overview_source, "title_source": title_source}
    write(out_dir / "patch_evaluation.json", evaluation)

    md = ["# BEFORE(patch1) / AFTER(patch2) — %s" % args.video_id, "",
          "| 항목 | BEFORE | AFTER |", "|---|---|---|",
          "| report row | %d | %d |" % (len(before_rows), len(rows)),
          "| mixed-script visual 검출 | - | %d |" % evaluation["mixed_script_visual_detected"],
          "| SAFE_VISUAL_DOWNGRADE | - | %d |" % evaluation["safe_visual_downgrade"],
          "| VISUAL_TEXT_WITHHELD_MIXED_SCRIPT | - | %d |"
          % evaluation["visual_text_withheld_mixed_script"],
          "| 반복 정리 행 | - | %d |" % evaluation["local_repetition_cleaned_rows"],
          "| 제거 단위 | - | %d |" % evaluation["removed_repetition_units"],
          "| 음성 보류 | - | %d |" % evaluation["audio_withheld"],
          "| 화면 강등 | - | %d |" % evaluation["visual_only_downgrade"],
          "| 커버리지(초) | %s | %s |" % (evaluation["coverage_sec"]["before"],
                                     evaluation["coverage_sec"]["after"]),
          "| 최대 gap(초) | %s | %s |" % (evaluation["largest_gap_sec"]["before"],
                                     evaluation["largest_gap_sec"]["after"])]
    (out_dir / "before_after_comparison.md").write_text("\n".join(md) + "\n",
                                                        encoding="utf-8", newline="\n")
    print(json.dumps({k: evaluation[k] for k in
                      ("rows", "mixed_script_visual_detected", "safe_visual_downgrade",
                       "visual_text_withheld_mixed_script", "local_repetition_cleaned_rows",
                       "removed_repetition_units", "display_counts", "coverage_sec",
                       "largest_gap_sec", "overview_source", "title_source")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Report Composer V2 — 검증된 event를 Report Episode로 묶어 최종 보고서를 만든다.

```
입력   runs/wvr_multimodal_clean_v1/<vid>/          분석·융합 결과(읽기 전용)
       runs/wvr_multimodal_clean_v1_patch2/<vid>/   표시 판단(안전 fallback·정화)
       기존 visual event_timeline.json              broad_activity(읽기 전용)
       speech_reportability.json                    보고 가치 판정
출력   runs/wvr_multimodal_composer_v2/<vid>/
```

분석 계층은 한 줄도 바꾸지 않는다. 특정 영상·단어·시간대 조건문은 없다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "jds_video" / "_internal"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_multimodal_report_v1 as report_mod         # noqa: E402
import wvr_report_composer_v2 as composer             # noqa: E402
import wvr_display_sanitize_v1 as sanitize            # noqa: E402
import wvr_report_usability_v1 as usability          # noqa: E402
import wvr_grounding_guard_v1 as grounding           # noqa: E402
import wvr_speech_report_style_v1 as style           # noqa: E402
from apply_wvr_safe_fallback_patch_v1 import (        # noqa: E402
    coverage, largest_gap, load, parse_rows, write)
from apply_wvr_display_sanitization_v1 import visual_records  # noqa: E402

EVENT = "WVR_MULTIMODAL_REPORT_COMPOSER_V2"
UNRELIABLE_ASR = ("ASR_LOW_CONFIDENCE", "ASR_REPETITION_ANOMALY")
WITHHELD = ("AUDIO_WITHHELD_ASR_UNRELIABLE", "NON_REPORTABLE_EVENT")
# 보고서 문체 압축이 붙으면 승인 상태의 이름이 늘어난다. 붙지 않으면 기존 그대로다.
APPROVED_DISPLAYS = composer.APPROVED_DISPLAYS + style.APPROVED_REPORT_DISPLAYS
REWRITABLE = ("GENERATIVE", "REGENERATED", "EXTRACTIVE_FALLBACK")


def thirds_overview(episodes):
    """초반·중반·후반의 흐름만 적는다. 문장마다 구성 episode가 그대로 근거다(§16·§17)."""
    if not episodes:
        return "", []
    start = min(e["start"] for e in episodes)
    end = max(e["end"] for e in episodes)
    step = (end - start) / 3.0 or 1.0
    labels = ("초반", "중반", "후반")
    lines, evidence = [], []
    for index, label in enumerate(labels):
        lower, upper = start + step * index, start + step * (index + 1)
        block = [e for e in episodes
                 if e["start"] < upper and e["end"] > lower]
        if not block:
            continue
        seen = []
        for episode in sorted(block, key=lambda e: -(e["end"] - e["start"])):
            if episode["category"] in (composer.NEUTRAL_SPEECH, composer.NEUTRAL_VISUAL):
                continue                  # 내용이 없는 구분은 흐름 설명에 쓰지 않는다
            if episode["category"] not in seen:
                seen.append(episode["category"])
            if len(seen) == 3:
                break
        if not seen:
            continue
        lines.append("%s에는 %s 관련 내용이 이어진다." % (label, ", ".join(seen)))
        evidence.append({"sentence_id": "S%02d" % len(lines), "segment": label,
                         "report_episode_ids": [e["episode_id"] for e in block]})
    return " ".join(lines), evidence


def compose_title(episodes, limit=3):
    """가장 오래 이어진 구분 몇 개로만 만든다 — 직업·장소·계절 추정을 넣지 않는다(§14)."""
    weight = {}
    for episode in episodes:
        weight[episode["category"]] = weight.get(episode["category"], 0.0) + (
            episode["end"] - episode["start"])
    ranked = [name for name, _ in sorted(weight.items(), key=lambda kv: (-kv[1], kv[0]))]
    picked = []
    for name in ranked:
        if name in (composer.NEUTRAL_SPEECH, composer.NEUTRAL_VISUAL):
            continue
        # 이미 고른 구분을 품고 있거나 그 안에 든 이름은 같은 말이 두 번 나오게 한다
        if any(name in chosen or chosen in name for chosen in picked):
            continue
        picked.append(name)
        if len(picked) == limit:
            break
    return " · ".join(picked or ranked[:limit]), picked


def main(argv=None):
    ap = argparse.ArgumentParser(description=EVENT)
    ap.add_argument("--clean-dir", required=True)
    ap.add_argument("--patch2-dir", required=True)
    ap.add_argument("--usability-dir", required=True, help="BEFORE 비교 대상")
    ap.add_argument("--visual-events", required=True)
    ap.add_argument("--reportability", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--duration-sec", type=float, required=True)
    ap.add_argument("--language-retry", help="usability_v1의 한국어 전용 재생성 결과")
    ap.add_argument("--speech-report-summaries",
                    help="WVR_SPEECH_REPORT_STYLE_COMPRESSION_V1 결과. 주면 음성 행의 "
                         "표시 문장을 여기서 가져오고 원문 발췌는 보고서에 넣지 않는다(§3)")
    args = ap.parse_args(argv)

    clean, patch2, out_dir = Path(args.clean_dir), Path(args.patch2_dir), Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    timeline = load(clean / "multimodal_timeline.json")["events"]
    chapters = load(clean / "semantic_chapters.json")["chapters"]
    speech_events = {e["speech_event_id"]: e
                     for e in load(clean / "speech" / "speech_events.json")["speech_events"]}
    utterances = {u["id"]: u for u in
                  load(clean / "speech" / "transcript_raw.json")["utterances"]}
    generative = load(clean / "generative_summary.json")["events"]
    asr_states = {f["utterance_id"]: f["state"]
                  for f in load(clean / "speech" / "asr_diagnostics.json")["utterance_flags"]}
    decisions = load(patch2 / "fallback_decisions.json")["decisions"]
    records = visual_records(args.visual_events)
    reportability = load(args.reportability)["events"]
    retry_events = (load(args.language_retry).get("events") or {}) if (
        args.language_retry and Path(args.language_retry).is_file()) else {}
    report_style = (load(args.speech_report_summaries).get("events") or {}) if (
        args.speech_report_summaries and Path(args.speech_report_summaries).is_file()) else None

    chapter_of = {}
    for chapter in chapters:
        for event_id in chapter.get("event_ids", []):
            chapter_of.setdefault(event_id, []).append(chapter["chapter_id"])

    visual_events = [e for e in timeline if e["evidence_type"] == "VISUAL"]
    labels_useful = usability.activity_labels_discriminate(
        [r.get("broad_activity", []) for r in records.values()])

    def visual_view(event):
        """화면 서술은 **visual artifact 원문**에서 가져온다.

        융합(VISUAL_AUDIO) event의 `summary`는 음성 쪽 문장이라 그대로 쓰면 화면 근거가
        아닌 말을 화면 서술로 내보내게 된다. 정화 규칙은 patch2와 같은 것을 쓴다.
        """
        ids = event.get("visual_event_ids") or []
        record = records.get(ids[0], {}) if ids else {}
        source = record.get("summary") or (event.get("summary", "") if not ids else "")
        verdict = sanitize.sanitize_visual_text(
            source, category=record.get("category") or event.get("category"),
            broad_activity=record.get("broad_activity", []))
        return verdict, record

    def visual_span(visual_id):
        """화면 근거의 **실제** 구간. 음성 구간으로 대신하지 않는다(§4)."""
        intervals = records.get(visual_id, {}).get("support_intervals") or []
        if not intervals:
            return None
        return (min(i["start_sec"] for i in intervals),
                max(i["end_sec"] for i in intervals))

    visual_spans = {}
    for event in timeline:
        for visual_id in event.get("visual_event_ids") or []:
            span = visual_span(visual_id)
            if span:
                visual_spans[visual_id] = span

    episodes, suppressed, composition = [], [], []

    def new_id():
        return "RE%03d" % (len(episodes) + 1)

    for event in sorted(timeline, key=lambda e: (e["start"], e["end"])):
        speech_ids = event.get("speech_event_ids", [])
        verdict, record = visual_view(event)

        if not speech_ids:
            if report_mod.is_speaking_only(event.get("summary", "")) or not verdict["display_text"]:
                suppressed.append({"source": event["event_id"], "reason": "NON_REPORTABLE_VISUAL",
                                   "start": event["start"], "end": event["end"],
                                   "summary": event.get("summary", "")})
                continue
            episodes.append({
                "episode_id": new_id(), "start": event["start"], "end": event["end"],
                "summary": verdict["display_text"], "evidence": composer.VISUAL,
                "display": "VISUAL_EVIDENCE", "approved_category": None,
                "broad_activity": record.get("broad_activity", []),
                "visual_event_ids": event.get("visual_event_ids", []),
                "speech_event_ids": [], "multimodal_event_ids": [event["event_id"]],
                "chapter_ids": chapter_of.get(event["event_id"], []),
                "visual_claim_ids": event.get("visual_claim_ids", []), "utterance_ids": [],
                "visual_display_decision": verdict["display_decision"],
                "frozen_link": False,
                "original_text": verdict["original_text"]})
            continue

        speech_id = speech_ids[0]
        label = composer.normalize_reportability(
            (reportability.get(speech_id) or {}).get("label"))
        decision = decisions.get(speech_id, {})
        fused = event["evidence_type"] == "VISUAL_AUDIO"

        if not composer.is_reportable(label):
            suppressed.append({"source": speech_id, "reason": composer.NON_REPORTABLE_SPEECH,
                               "label": label,
                               "classifier_reason": (reportability.get(speech_id) or {}).get("reason"),
                               "start": event["start"], "end": event["end"],
                               "summary": decision.get("summary")})
            continue

        linked = composer.has_frozen_link(event, speech_id)
        # 보고서 문체 압축을 쓰는 실행에서는 그 판정이 음성 행의 존폐를 정한다. 압축이
        # 실패한 event는 원문 발췌로 되돌리지 않고 내린다(§3·§15).
        style_entry = (report_style or {}).get(speech_id)
        style_withheld = report_style is not None and (
            not style_entry or not style_entry.get("summary")
            or style_entry.get("decision") == style.AUDIO_WITHHELD)
        withheld_audio = (decision.get("display") in WITHHELD or not decision.get("summary")
                          or decision.get("display") == "VISUAL_ONLY_DOWNGRADE"
                          or style_withheld)
        if withheld_audio:
            # 음성은 내린다. 화면 근거는 **이미 연결된 것으로 판정된 경우에만** 살리고,
            # 그때도 구간은 화면 근거 자신의 것을 쓴다(§2·§4·§9).
            visual_ids = event.get("visual_event_ids", []) if (fused and linked) else []
            span = visual_span(visual_ids[0]) if visual_ids else None
            if visual_ids and span and verdict["display_text"]:
                episodes.append({
                    "episode_id": new_id(), "start": span[0], "end": span[1],
                    "summary": verdict["display_text"], "evidence": composer.VISUAL,
                    "display": "VISUAL_ONLY_DOWNGRADE", "approved_category": None,
                    "broad_activity": record.get("broad_activity", []),
                    "visual_event_ids": visual_ids, "speech_event_ids": speech_ids,
                    "multimodal_event_ids": [event["event_id"]],
                    "chapter_ids": chapter_of.get(event["event_id"], []),
                    "visual_claim_ids": event.get("visual_claim_ids", []),
                    "utterance_ids": [], "visual_display_decision": verdict["display_decision"],
                    "frozen_link": True, "original_text": verdict["original_text"]})
                composition.append({"speech_event_id": speech_id,
                                    "action": "AUDIO_WITHHELD_LINKED_VISUAL_KEPT",
                                    "reason": "frozen relation으로 연결된 화면 근거만 남긴다"})
                continue
            suppressed.append({"source": speech_id,
                               "reason": (style.AUDIO_WITHHELD if style_withheld
                                          and decision.get("display") in REWRITABLE
                                          else "AUDIO_WITHHELD_NO_LINKED_VISUAL"
                                          if decision.get("display") == "VISUAL_ONLY_DOWNGRADE"
                                          else decision.get("display", "NO_SUMMARY")),
                               "report_style_reason": (style_entry or {}).get("reason"),
                               "attempt_reasons": (style_entry or {}).get("attempt_reasons"),
                               "start": event["start"], "end": event["end"],
                               "summary": decision.get("previous_summary"),
                               "note": "근접한 화면 event를 끌어와 붙이지 않는다(§2)"})
            continue

        source = speech_events.get(speech_id, {})
        members = [utterances[uid] for uid in source.get("supporting_utterance_ids", [])
                   if uid in utterances]
        parsed = (generative.get(speech_id) or {}).get("parsed") or {}
        base_summary = decision["summary"]
        evidence_texts = [u["text"] for u in members]

        if style_entry:
            # 압축 계층이 언어·근거·수치·claim·문체를 전부 통과시킨 문장이다. 표시
            # 계층에서 다시 생성하지 않고, 실패해도 원문 발췌로 되돌리지 않는다(§3).
            base_summary = style_entry["summary"]
            parsed = {"category": style_entry.get("category") or ""}
            decision = {**decision, "display": style_entry["decision"],
                        "report_style_reason": style_entry.get("reason")}
            composition.append({"speech_event_id": speech_id,
                                "action": "SPEECH_REPORT_STYLE",
                                "decision": style_entry["decision"],
                                "reason": style_entry.get("reason")})
        # usability_v1이 이미 해결한 표기 오염을 되돌리지 않는다 — 같은 검사를 다시 건다.
        elif usability.display_language_check(
                base_summary, evidence_texts)["status"] == usability.FAIL:
            injected = ((retry_events.get(speech_id) or {}).get("parsed") or {})
            candidate = injected.get("summary")
            if (candidate and sanitize.script_clean(candidate)
                    and usability.display_language_check(
                        candidate, evidence_texts)["status"] == usability.PASS
                    and grounding.check_grounding(
                        candidate, evidence_texts)["status"] == grounding.GROUNDED):
                base_summary, parsed = candidate, injected
                composition.append({"speech_event_id": speech_id,
                                    "action": "LANGUAGE_MIX_REGENERATION_KEPT",
                                    "reason": "usability_v1의 한국어 전용 재생성을 이어받았다"})
            else:
                extractive = source.get("summary") or base_summary
                base_summary = sanitize.dedup_local(extractive)["text"]
                composition.append({"speech_event_id": speech_id,
                                    "action": "LANGUAGE_MIX_EXTRACTIVE",
                                    "reason": "재생성본이 없거나 가드를 통과하지 못했다"})
        approved_category = parsed.get("category")
        # 보고서 문체 압축을 쓰는 실행에서는 주제 분할을 다시 하지 않는다 — 사건의
        # 구성·구간·provenance는 그대로 두고 표시 문장만 바꾸는 것이 이번 범위다(§17).
        parts = ([{"summary": base_summary,
                   "utterance_ids": [u["id"] for u in members],
                   "start": members[0]["start"] if members else None,
                   "end": members[-1]["end"] if members else None, "split": False}]
                 if style_entry else composer.split_summary_by_topic(base_summary, members))
        if len(parts) > 1:
            composition.append({"speech_event_id": speech_id, "action": "TOPIC_SPLIT",
                                "parts": len(parts),
                                "reason": "승인 요약의 문장들이 내용어를 공유하지 않는다"})
        for part in parts:
            member_ids = set(part["utterance_ids"])
            block = [u for u in members if u["id"] in member_ids] or members
            text, compressed = part["summary"], {"compressed": False, "removed_sentences": []}
            if composer.looks_like_transcript(text):
                compressed = composer.compress_transcript_text(text)
                text = compressed["text"]
            start = part["start"] if part["start"] is not None else event["start"]
            end = part["end"] if part["end"] is not None else event["end"]
            evidence, visual_ids, claim_ids = composer.AUDIO, [], []
            fused_clause = None
            if fused and linked and not part["split"] and verdict["display_text"]:
                span = visual_span((event.get("visual_event_ids") or [None])[0])
                fused_clause = composer.modality_clause(
                    verdict["display_text"],
                    span[0] if span else start, span[1] if span else end, start, end)
            if fused_clause:
                text = composer.compose_fused_summary(text, fused_clause)
                evidence = composer.VISUAL_AUDIO
                visual_ids = event.get("visual_event_ids", [])
                claim_ids = event.get("visual_claim_ids", [])
                composition.append({"speech_event_id": speech_id, "action": "FUSED_KEPT",
                                    "relation": [r.get("relation") for r in event.get("relations", [])],
                                    "reason": "이미 같은 사건으로 판정된 화면 근거를 한 행으로 유지"})
            terms = composer.uncertain_terms(text, block, asr_states, UNRELIABLE_ASR)
            dropped = composer.drop_uncertain_clauses(text, terms)
            if dropped["removed"]:
                composition.append({"speech_event_id": speech_id,
                                    "action": "UNCERTAIN_CLAUSE_DROPPED",
                                    "terms": terms, "removed": dropped["removed"],
                                    "reason": "불확실 고유명사가 든 문장을 뺐다(교정하지 않는다)"})
                text = dropped["text"]
            episodes.append({
                "episode_id": new_id(), "start": start, "end": end, "summary": text,
                "evidence": evidence, "display": decision.get("display"),
                "frozen_link": bool(fused_clause),
                "visual_clause": fused_clause,
                "clause_provenance": composer.clause_provenance(text, fused_clause, evidence),
                "approved_category": approved_category,
                "broad_activity": records.get((visual_ids or [None])[0], {}).get("broad_activity", [])
                if visual_ids else [],
                "visual_event_ids": visual_ids, "speech_event_ids": speech_ids,
                "multimodal_event_ids": [event["event_id"]],
                "chapter_ids": chapter_of.get(event["event_id"], []),
                "visual_claim_ids": claim_ids,
                "utterance_ids": [u["id"] for u in block],
                "reportability": label, "topic_split": part["split"],
                "transcript_compressed": compressed["compressed"],
                "removed_sentences": compressed["removed_sentences"],
                "uncertain_terms": terms,
                "visual_display_decision": verdict["display_decision"] if visual_ids else None,
                "original_text": None})

    # ── 종속 화면 관찰 접기 ──
    kept = []
    for episode in episodes:
        verdict = composer.is_subordinate_visual(episode, episodes)
        if verdict:
            suppressed.append({"source": episode["episode_id"], "reason": verdict[0],
                               "folded_into": verdict[1], "start": episode["start"],
                               "end": episode["end"], "summary": episode["summary"],
                               "visual_event_ids": episode.get("visual_event_ids", []),
                               "visual_claim_ids": episode.get("visual_claim_ids", [])})
            continue
        kept.append(episode)

    # ── 구분 · 중요도 ──
    for episode in kept:
        chosen = composer.choose_episode_category(
            episode.get("approved_category"), episode["summary"],
            episode.get("broad_activity"), episode["evidence"],
            activity_labels_useful=labels_useful,
            blocked_terms=tuple(episode.get("uncertain_terms") or ()),
            approved=episode.get("display") in APPROVED_DISPLAYS)
        episode["category"] = chosen["category"]
        episode["category_source"] = chosen["source"]
    for episode, level in zip(kept, composer.assign_importance(kept, APPROVED_DISPLAYS)):
        episode["importance"] = level
        episode["transcript_like"] = composer.looks_like_transcript(episode["summary"])
        texts = [utterances[uid]["text"] for uid in episode.get("utterance_ids", [])
                 if uid in utterances]
        episode["report_style_audit"] = style.audit_report_style(episode["summary"], texts)

    # 근거 감사 — 실패한 사건은 보고서로 내보내지 않는다(§8).
    audit_records, audited = [], []
    for episode in kept:
        verdict = composer.audit_episode(episode, visual_spans)
        audit_records.append({"episode_id": episode["episode_id"], "evidence": episode["evidence"],
                              "start": episode["start"], "end": episode["end"],
                              "visual_event_ids": episode.get("visual_event_ids", []),
                              "speech_event_ids": episode.get("speech_event_ids", []),
                              "frozen_link": bool(episode.get("frozen_link")), **verdict})
        episode["evidence_audit"] = verdict["status"]
        if verdict["status"] != composer.EPISODE_GROUNDED:
            suppressed.append({"source": episode["episode_id"], "reason": verdict["status"],
                               "start": episode["start"], "end": episode["end"],
                               "summary": episode["summary"], "problems": verdict["problems"]})
            continue
        audited.append(episode)

    # MINOR는 **표시하되 진단으로만 표시한다**(추가 F). 시간이 겹친다는 이유로 내리면
    # 그 구간의 유일한 근거를 잃는다 — 의미가 겹치는 행은 이미 위에서 접혔다(§9).
    final = sorted(audited, key=lambda e: (e["start"], e["end"], e["episode_id"]))

    # ── 제목 · 개요 (구성 episode에서만) ──
    title, _ = compose_title(final)
    overview, overview_evidence = composer.narrative_overview(final)
    if not overview:
        overview, overview_evidence = thirds_overview(final)
    title_audit = composer.audit_title(title, final)
    overview_audit = composer.audit_overview(overview, final)
    if not title_audit["usable"]:
        title = "%s 영상 보고서" % args.video_id
    overview_text = " ".join(record["text"] for record in overview_audit if record["usable"])
    if not overview_text:
        overview_text = report_mod.compose_overview(
            [{"summary": e["summary"], "category": e["category"], "evidence": e["evidence"],
              "start": e["start"], "end": e["end"]} for e in final])

    lines = ["# %s" % title, "", "□ 개요", "", overview_text, "", "□ 세부내용", "",
             "| 구분 | 시간 | 내용 | 비고 |", "|---|---|---|---|"]
    for episode in final:
        lines.append("| %s | %s ~ %s | %s | %s |"
                     % (episode["category"], report_mod.hhmmss(episode["start"]),
                        report_mod.hhmmss(episode["end"]), episode["summary"],
                        episode["evidence"]))
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    write(out_dir / "report_episodes.json", {
        "event": EVENT, "video_id": args.video_id, "episode_count": len(final),
        "episodes": final, "suppressed": suppressed})
    write(out_dir / "episode_composition_decisions.json", {
        "event": EVENT, "video_id": args.video_id,
        "rule": "이미 판정된 relation만 사용한다 · 시간 포함은 병합 근거가 아니다",
        "decisions": composition, "suppressed": suppressed})
    write(out_dir / "episode_evidence_audit.json", {
        "event": EVENT, "video_id": args.video_id,
        "rule": "화면 근거는 같은 multimodal event이거나 frozen relation으로 연결된 것만 쓴다",
        "counts": {status: sum(1 for r in audit_records if r["status"] == status)
                   for status in (composer.EPISODE_GROUNDED, composer.EPISODE_PROVENANCE_ERROR,
                                  composer.EPISODE_TEMPORAL_ERROR)},
        "records": audit_records})
    if report_style is not None:
        records = [{"episode_id": e["episode_id"], "evidence": e["evidence"],
                    "display": e.get("display"), "summary": e["summary"],
                    "speech_event_ids": e.get("speech_event_ids", []),
                    "utterance_ids": e.get("utterance_ids", []),
                    **e["report_style_audit"]} for e in final]
        write(out_dir / "transcript_style_audit.json", {
            "event": EVENT, "video_id": args.video_id,
            "rule": "행마다 전사 복사(§7)와 보고 문체(§6)를 다시 본다 — 최종 화면 문장 기준",
            "counts": style.style_counts(records),
            "leakage_rows": sum(1 for r in records
                                if set(r["signals"]) & set(style.LEAKAGE_SIGNALS)),
            "records": records})
        write(out_dir / "fallback_decisions.json", {
            "event": EVENT, "video_id": args.video_id,
            "rule": "생성 → 1회 재생성 → 구분 범위 요약 → 음성 보류. 원문 발췌는 근거 계층에만 남는다",
            "counts": {k: sum(1 for v in report_style.values() if v.get("decision") == k)
                       for k in style.APPROVED_REPORT_DISPLAYS + (style.AUDIO_WITHHELD,)},
            "decisions": {sid: {k: entry.get(k) for k in
                                ("decision", "summary", "category", "reason",
                                 "attempt_index", "attempt_reasons", "previous_display",
                                 "previous_summary", "evidence_extractive_only",
                                 "utterance_ids", "retention")}
                          for sid, entry in report_style.items()}})
        write(out_dir / "speech_report_summaries.json", load(args.speech_report_summaries))

    write(out_dir / "title_grounding.json", {"event": EVENT, "video_id": args.video_id,
                                             **title_audit, "final_title": title})
    write(out_dir / "overview_grounding.json", {
        "event": EVENT, "video_id": args.video_id, "overview": overview_text,
        "sentences": overview_audit, "segment_evidence": overview_evidence})

    sidecar = report_mod.build_sidecar(
        [{**e, "row_id": e["episode_id"]} for e in final], [],
        transcript_path=str(clean / "speech" / "transcript_raw.json"))
    sidecar["event"] = EVENT
    sidecar["report_episodes"] = final
    sidecar["suppressed"] = suppressed
    sidecar["composition_decisions"] = composition
    if report_style is not None:
        # 보고서에는 의미 요약만 나가고, 원문 발췌는 여기에 남는다(§3·§19).
        sidecar["evidence_extractive_only"] = {
            sid: entry.get("evidence_extractive_only")
            for sid, entry in report_style.items() if entry.get("evidence_extractive_only")}
    write(out_dir / "report_evidence.json", sidecar)

    before_rows = parse_rows(Path(args.usability_dir) / "report.md")
    after_view = [{"summary": e["summary"], "evidence": e["evidence"],
                   "start": e["start"], "end": e["end"]} for e in final]
    counts = composer.composer_counts(final, suppressed)
    generic_categories = sum(1 for e in final if e["category"] in
                             (composer.NEUTRAL_SPEECH, composer.NEUTRAL_VISUAL))
    evaluation = {
        "event": EVENT, "video_id": args.video_id,
        "new_model_inference": {"stt": 0, "visual": 0,
                                "reportability_calls": len(reportability)},
        "rows": {"before": len(before_rows), "after": len(final)},
        "report_episodes": len(final),
        "evidence_counts": counts["evidence"],
        "importance_counts": counts["importance"],
        "suppressed_counts": counts["suppressed"],
        "meta_or_filler_suppressed": sum(1 for s in suppressed
                                         if s["reason"] == composer.NON_REPORTABLE_SPEECH),
        "subordinate_visual_suppressed": counts["suppressed"].get(
            composer.SUBORDINATE_VISUAL_DETAIL, 0),
        "generic_category_rows": generic_categories,
        "transcript_like_rows": sum(1 for e in final if e.get("transcript_like")),
        "report_style": ({
            "display_counts": {k: sum(1 for e in final if e.get("display") == k)
                               for k in APPROVED_DISPLAYS},
            "audio_withheld_by_style": sum(1 for s in suppressed
                                           if s["reason"] == style.AUDIO_WITHHELD),
            "raw_transcript_rows": sum(1 for e in final if set(
                e["report_style_audit"]["signals"]) & set(style.LEAKAGE_SIGNALS)),
            "transcript_style_fail_rows": sum(
                1 for e in final
                if e["report_style_audit"]["status"] != style.TRANSCRIPT_STYLE_PASS),
            "extractive_rows_in_report": sum(
                1 for e in final if e.get("display") == "EXTRACTIVE_FALLBACK"),
        } if report_style is not None else None),
        "topic_split_events": sum(1 for c in composition if c["action"] == "TOPIC_SPLIT"),
        "fused_rows_kept": sum(1 for e in final if e["evidence"] == composer.VISUAL_AUDIO),
        "uncertain_term_rows": sum(1 for e in final if e.get("uncertain_terms")),
        "uncertain_clause_dropped": sum(1 for c in composition
                                        if c["action"] == "UNCERTAIN_CLAUSE_DROPPED"),
        "evidence_audit": {status: sum(1 for r in audit_records if r["status"] == status)
                           for status in (composer.EPISODE_GROUNDED,
                                          composer.EPISODE_PROVENANCE_ERROR,
                                          composer.EPISODE_TEMPORAL_ERROR)},
        "title_unsupported_claims": sum(1 for c in title_audit["title_claims"]
                                        if not c["grounded"]),
        "overview_unsupported_sentences": sum(1 for r in overview_audit if not r["usable"]),
        "coverage_sec": {"before": coverage(before_rows), "after": coverage(after_view)},
        "largest_gap_sec": {"before": largest_gap(before_rows, args.duration_sec),
                            "after": largest_gap(after_view, args.duration_sec)},
        "final_categories": sorted({e["category"] for e in final})}
    write(out_dir / "composer_evaluation.json", evaluation)
    write(out_dir / "before_after_comparison.json", {
        "before": {"source": str(args.usability_dir), "rows": len(before_rows),
                   "coverage_sec": evaluation["coverage_sec"]["before"],
                   "largest_gap_sec": evaluation["largest_gap_sec"]["before"]},
        "after": {"source": str(out_dir), "rows": len(final),
                  "coverage_sec": evaluation["coverage_sec"]["after"],
                  "largest_gap_sec": evaluation["largest_gap_sec"]["after"],
                  "evidence": counts["evidence"], "importance": counts["importance"]}})
    md = ["# BEFORE(usability_v1) / AFTER(composer_v2) — %s" % args.video_id, "",
          "| 항목 | BEFORE | AFTER |", "|---|---|---|",
          "| report row | %d | %d |" % (len(before_rows), len(final)),
          "| 화면 / 음성 / 음성+화면 | - | %d / %d / %d |"
          % (counts["evidence"].get(composer.VISUAL, 0),
             counts["evidence"].get(composer.AUDIO, 0),
             counts["evidence"].get(composer.VISUAL_AUDIO, 0)),
          "| MAJOR / SUPPORTING / MINOR | - | %d / %d / %d |"
          % (counts["importance"].get(composer.MAJOR, 0),
             counts["importance"].get(composer.SUPPORTING, 0),
             counts["importance"].get(composer.MINOR, 0)),
          "| META·FILLER 제외 | - | %d |" % evaluation["meta_or_filler_suppressed"],
          "| 종속 화면 관찰 접음 | - | %d |" % evaluation["subordinate_visual_suppressed"],
          "| generic 구분 | - | %d |" % generic_categories,
          "| 전사형 행 | - | %d |" % evaluation["transcript_like_rows"],
          "| 제목 미지지 표현 | - | %d |" % evaluation["title_unsupported_claims"],
          "| 개요 미지지 문장 | - | %d |" % evaluation["overview_unsupported_sentences"],
          "| 커버리지(초) | %s | %s |" % (evaluation["coverage_sec"]["before"],
                                     evaluation["coverage_sec"]["after"]),
          "| 최대 gap(초) | %s | %s |" % (evaluation["largest_gap_sec"]["before"],
                                     evaluation["largest_gap_sec"]["after"])]
    (out_dir / "before_after_comparison.md").write_text("\n".join(md) + "\n",
                                                        encoding="utf-8", newline="\n")
    print(json.dumps({k: evaluation[k] for k in
                      ("rows", "evidence_counts", "importance_counts", "suppressed_counts",
                       "meta_or_filler_suppressed", "generic_category_rows",
                       "transcript_like_rows", "topic_split_events", "fused_rows_kept",
                       "uncertain_term_rows", "evidence_audit", "title_unsupported_claims",
                       "overview_unsupported_sentences", "coverage_sec", "largest_gap_sec",
                       "final_categories")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

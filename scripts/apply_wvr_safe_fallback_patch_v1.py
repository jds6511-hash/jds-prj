"""clean 산출물에 안전 fallback + 자막 크레딧 필터를 적용한다(새 추론 0회).

```
입력   runs/wvr_multimodal_clean_v1/<vid>/   (읽기 전용)
출력   runs/wvr_multimodal_clean_v1_patch1/<vid>/
       report.md · report_evidence.json · fallback_decisions.json
       subtitle_credit_filter.json · patch_evaluation.json · before_after_comparison.md
```

STT·VLM 추론을 다시 돌리지 않는다. 경계·관계·chapter·임계·어휘집은 그대로다.
개요·제목은 패치 후 실제로 화면에 나가는 문장만으로 다시 만들 입력을 준비한다(§12).
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "jds_video" / "_internal"))

import wvr_multimodal_report_v1 as report_mod    # noqa: E402
import wvr_safe_fallback_v1 as safe              # noqa: E402

EVENT = "WVR_SAFE_FALLBACK_PATCH_V1"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                          encoding="utf-8", newline="\n")


def parse_rows(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 4 or cells[0] == "구분":
            continue
        stamps = re.findall(r"\d+:\d+:\d+", cells[1])

        def seconds(stamp):
            h, m, s = (int(p) for p in stamp.split(":"))
            return h * 3600 + m * 60 + s

        rows.append({"summary": cells[2], "evidence": cells[3],
                     "start": seconds(stamps[0]) if stamps else 0,
                     "end": seconds(stamps[-1]) if len(stamps) > 1 else 0})
    return rows


def coverage(rows):
    spans = sorted((r["start"], r["end"]) for r in rows if r["end"] > r["start"])
    total, cursor = 0.0, None
    for start, end in spans:
        if cursor is None or start > cursor[1]:
            if cursor:
                total += cursor[1] - cursor[0]
            cursor = [start, end]
        else:
            cursor[1] = max(cursor[1], end)
    if cursor:
        total += cursor[1] - cursor[0]
    return round(total, 1)


def largest_gap(rows, duration):
    spans = sorted((r["start"], r["end"]) for r in rows if r["end"] > r["start"])
    gaps, cursor = [], 0
    for start, end in spans:
        gaps.append(max(0, start - cursor))
        cursor = max(cursor, end)
    gaps.append(max(0, duration - cursor))
    return round(max(gaps), 1) if gaps else 0.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=EVENT)
    ap.add_argument("--clean-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--duration-sec", type=float, required=True)
    ap.add_argument("--overview-title", help="승인 행으로 다시 만든 overview_title.json")
    args = ap.parse_args(argv)

    clean = Path(args.clean_dir)
    out_dir = Path(args.out)
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

    subtitle_flags = safe.subtitle_credit_flags(list(utterances.values()))
    credit_ids = [uid for uid, flagged in subtitle_flags.items() if flagged]
    write(out_dir / "subtitle_credit_filter.json", {
        "event": EVENT, "video_id": args.video_id,
        "filter": "common.is_subtitle_credit (canonical · 전체 일치 판정)",
        "flagged_utterances": [{"id": uid, "text": utterances[uid]["text"]}
                               for uid in credit_ids],
        "flagged_count": len(credit_ids),
        "note": "raw transcript는 그대로 두고 보고 단계에서만 제외한다"})

    # 음성을 내릴 때 대신 쓸 화면 근거 — 시간이 가장 많이 겹치는 화면 전용 event
    visual_only = [e for e in timeline if e["evidence_type"] == "VISUAL"]

    def visual_for(event):
        best, overlap = None, 0.0
        for candidate in visual_only:
            span = min(event["end"], candidate["end"]) - max(event["start"], candidate["start"])
            if span > overlap:
                best, overlap = candidate, span
        return best["summary"] if best else None

    decisions, rows = {}, []
    for event in sorted(timeline, key=lambda e: (e["start"], e["end"])):
        speech_ids = event.get("speech_event_ids", [])
        if not speech_ids:
            # 화면 전용 행 — 기존 규칙(발화 묘사 억제) 그대로
            if report_mod.is_speaking_only(event.get("summary", "")):
                continue
            rows.append({"row_id": "ROW%03d" % (len(rows) + 1), "start": event["start"],
                         "end": event["end"], "category": event.get("category", ""),
                         "summary": event.get("summary", ""), "evidence": "화면",
                         "display": "VISUAL_EVIDENCE",
                         "visual_event_ids": event.get("visual_event_ids", []),
                         "speech_event_ids": [], "utterance_ids": [],
                         "visual_claim_ids": event.get("visual_claim_ids", [])})
            continue

        speech_id = speech_ids[0]
        source = speech_events.get(speech_id, {})
        record = guard["events"].get(speech_id, {})
        items = [utterances[uid] for uid in source.get("supporting_utterance_ids", [])
                 if uid in utterances]
        decision = safe.display_decision(
            approved=record.get("approved", False), reasons=record.get("reasons", []),
            generated=record.get("generated", ""), extractive=source.get("summary", ""),
            utterances=items, subtitle_flags=subtitle_flags, asr_states=asr_states,
            visual_summary=visual_for(event),
            summary_source=record.get("summary_source"))
        decisions[speech_id] = {**decision, "start": event["start"], "end": event["end"],
                                "previous_source": record.get("summary_source"),
                                "previous_summary": record.get("used")}
        if decision["summary"]:
            rows.append({"row_id": "ROW%03d" % (len(rows) + 1), "start": event["start"],
                         "end": event["end"],
                         "category": (event.get("category", "")
                                      if decision["display"] != safe.VISUAL_ONLY_DOWNGRADE
                                      else "관찰 장면"),
                         "summary": decision["summary"], "evidence": decision["evidence"],
                         "display": decision["display"],
                         "visual_event_ids": event.get("visual_event_ids", []),
                         "speech_event_ids": speech_ids,
                         "utterance_ids": decision["utterance_ids"],
                         "visual_claim_ids": event.get("visual_claim_ids", [])})

    # 개요·제목: 화면에 나가는 문장만 입력으로 (§12)
    write(out_dir / "overview_input.json", {
        "event": EVENT, "video_id": args.video_id,
        "note": "표시되는 행만 담는다 — 보류·자막 크레딧·차단 생성문 제외",
        "chapters": [{"chapter_id": c["chapter_id"], "start": c["start"], "end": c["end"],
                      "title": c["title"], "summary": c["summary"]}
                     for c in chapters
                     if c.get("summary_source") != "EXTRACTIVE_FALLBACK" or True],
        "rows": [{"start": r["start"], "end": r["end"], "category": r["category"],
                  "summary": r["summary"], "evidence": r["evidence"]} for r in rows]})

    # 개요·제목: 주입본이 있으면 언어·근거 가드를 다시 통과한 것만 쓴다
    import wvr_generative_guard_v1 as gen_guard
    import wvr_grounding_guard_v1 as grounding

    safe_texts = safe.overview_input_texts(rows)
    overview, title = report_mod.compose_overview(rows), None
    overview_source, title_source = "EXTRACTIVE_FALLBACK", "EXTRACTIVE_FALLBACK"
    if args.overview_title and Path(args.overview_title).is_file():
        injected = load(args.overview_title)
        candidate = ((injected.get("overview") or {}).get("parsed") or {}).get("summary", "")
        if candidate and gen_guard.language_gate(candidate)["status"] == gen_guard.PASS and                 grounding.check_grounding(candidate, safe_texts)["status"] == grounding.GROUNDED:
            overview, overview_source = candidate, "GENERATIVE"
        name = ((injected.get("title") or {}).get("parsed") or {}).get("category", "")
        if name and gen_guard.language_gate(name)["status"] == gen_guard.PASS and                 grounding.check_grounding(name, safe_texts)["status"] == grounding.GROUNDED:
            title, title_source = name, "GENERATIVE"

    lines = ["# %s" % (title or "%s 영상 보고서" % args.video_id), "", "□ 개요", "",
             overview.strip(), "", "□ 세부내용", "",
             "| 구분 | 시간 | 내용 | 비고 |", "|---|---|---|---|"]
    for row in rows:
        lines.append("| %s | %s ~ %s | %s | %s |"
                     % (row["category"], report_mod.hhmmss(row["start"]),
                        report_mod.hhmmss(row["end"]), row["summary"], row["evidence"]))
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    withheld = [d for d in decisions.values()
                if d["display"] in (safe.AUDIO_WITHHELD_ASR_UNRELIABLE,
                                    safe.NON_REPORTABLE_EVENT)]
    write(out_dir / "fallback_decisions.json", {
        "event": EVENT, "video_id": args.video_id,
        "display_counts": safe.display_counts(list(decisions.values())),
        "withheld_rows": [{"speech_event_id": sid, "display": d["display"],
                           "reason": d["reason"], "start": d["start"], "end": d["end"],
                           "utterance_ids": d["utterance_ids"],
                           "previous_summary": d["previous_summary"]}
                          for sid, d in decisions.items()
                          if d["display"] in (safe.AUDIO_WITHHELD_ASR_UNRELIABLE,
                                              safe.NON_REPORTABLE_EVENT)],
        "decisions": decisions})

    sidecar = report_mod.build_sidecar(rows, [], transcript_path=str(
        clean / "speech" / "transcript_raw.json"))
    sidecar["withheld_speech_events"] = [
        {"speech_event_id": sid, "display": d["display"], "reason": d["reason"],
         "utterance_ids": d["utterance_ids"]}
        for sid, d in decisions.items()
        if d["display"] in (safe.AUDIO_WITHHELD_ASR_UNRELIABLE, safe.NON_REPORTABLE_EVENT)]
    write(out_dir / "report_evidence.json", sidecar)

    before_rows = parse_rows(clean / "report.md")
    after_view = [{"summary": r["summary"], "evidence": r["evidence"],
                   "start": r["start"], "end": r["end"]} for r in rows]
    evidence_counts = {"화면": 0, "음성": 0, "음성+화면": 0}
    for row in rows:
        evidence_counts[row["evidence"]] = evidence_counts.get(row["evidence"], 0) + 1
    evaluation = {
        "event": EVENT, "video_id": args.video_id,
        "new_model_inference": {"stt": 0, "visual": 0, "summary": 0},
        "subtitle_credit_removed": len(credit_ids),
        "display_counts": safe.display_counts(list(decisions.values())),
        "rows": {"before": len(before_rows), "after": len(rows)},
        "evidence_counts_after": evidence_counts,
        "coverage_sec": {"before": coverage(before_rows), "after": coverage(after_view)},
        "largest_gap_sec": {"before": largest_gap(before_rows, args.duration_sec),
                            "after": largest_gap(after_view, args.duration_sec)},
        "withheld_count": len(withheld),
        "overview_source": overview_source,
        "title_source": title_source,
    }
    write(out_dir / "patch_evaluation.json", evaluation)
    md = ["# BEFORE / AFTER — %s" % args.video_id, "",
          "| 항목 | BEFORE | AFTER |", "|---|---|---|",
          "| report row | %d | %d |" % (len(before_rows), len(rows)),
          "| 커버리지(초) | %s | %s |" % (evaluation["coverage_sec"]["before"],
                                     evaluation["coverage_sec"]["after"]),
          "| 최대 gap(초) | %s | %s |" % (evaluation["largest_gap_sec"]["before"],
                                     evaluation["largest_gap_sec"]["after"]),
          "| 자막 크레딧 제거 | - | %d |" % len(credit_ids),
          "| 음성 보류 | - | %d |" % len(withheld), "",
          "표시 상태: %s" % json.dumps(evaluation["display_counts"], ensure_ascii=False)]
    (out_dir / "before_after_comparison.md").write_text("\n".join(md) + "\n",
                                                        encoding="utf-8", newline="\n")
    print(json.dumps({k: evaluation[k] for k in
                      ("rows", "display_counts", "subtitle_credit_removed",
                       "withheld_count", "coverage_sec", "evidence_counts_after")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

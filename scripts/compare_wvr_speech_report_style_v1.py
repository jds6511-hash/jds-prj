"""BEFORE(composer_v2) / AFTER(보고서 문체 압축) 비교 — §22·§23.

새 추론 0회. 두 보고서의 행을 읽어 **전사가 그대로 남아 있는가**와 **의미가 남아
있는가**를 따로 센다. 짧아진 것과 사라진 것은 다른 일이다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "jds_video" / "_internal"))
sys.path.insert(0, str(ROOT / "scripts"))

import wvr_report_composer_v2 as composer   # noqa: E402
import wvr_speech_report_style_v1 as style  # noqa: E402
from apply_wvr_safe_fallback_patch_v1 import coverage, load, write  # noqa: E402

EVENT = "WVR_SPEECH_REPORT_STYLE_COMPRESSION_V1"
SPEECH_EVIDENCE = (composer.AUDIO, composer.VISUAL_AUDIO)


def audit_rows(episodes, utterances):
    out = []
    for episode in episodes:
        texts = [utterances[uid]["text"] for uid in episode.get("utterance_ids", [])
                 if uid in utterances]
        audit = episode.get("report_style_audit") or style.audit_report_style(
            episode["summary"], texts)
        out.append({"episode_id": episode["episode_id"], "evidence": episode["evidence"],
                    "display": episode.get("display"), "summary": episode["summary"],
                    "status": audit["status"], "signals": audit["signals"],
                    "longest_verbatim_run": audit["leakage"]["longest_run"],
                    "verbatim_ratio": audit["leakage"]["verbatim_ratio"]})
    return out


def side(episodes, records):
    speech = [e for e in episodes if e["evidence"] in SPEECH_EVIDENCE]
    # 이번 작업의 대상은 **음성에서 온 문장**이다. 화면 서술은 visual artifact 원문이고
    # 동결 대상이라 같은 잣대로 세면 수치가 엉킨다(§0) — 따로 센다.
    speech_records = [r for r in records if r["evidence"] in SPEECH_EVIDENCE]
    visual_records = [r for r in records if r["evidence"] not in SPEECH_EVIDENCE]
    leaky = [r for r in speech_records if set(r["signals"]) & set(style.LEAKAGE_SIGNALS)]
    return {
        "speech_transcript_style_rows": sum(
            1 for r in speech_records if r["status"] != style.TRANSCRIPT_STYLE_PASS),
        "visual_non_declarative_rows": sum(
            1 for r in visual_records if r["status"] != style.TRANSCRIPT_STYLE_PASS),
        "report_rows": len(episodes),
        "audio_rows": sum(1 for e in episodes if e["evidence"] == composer.AUDIO),
        "visual_audio_rows": sum(1 for e in episodes
                                 if e["evidence"] == composer.VISUAL_AUDIO),
        "visual_rows": sum(1 for e in episodes if e["evidence"] == composer.VISUAL),
        "speech_rows": len(speech),
        "transcript_style_rows": sum(1 for r in records
                                     if r["status"] != style.TRANSCRIPT_STYLE_PASS),
        "raw_transcript_rows": len(leaky),
        "raw_transcript_episode_ids": [r["episode_id"] for r in leaky],
        "extractive_fallback_rows": sum(1 for e in episodes
                                        if e.get("display") == "EXTRACTIVE_FALLBACK"),
        "display_counts": {d: sum(1 for e in episodes if e.get("display") == d)
                           for d in sorted({e.get("display") for e in episodes if e.get("display")})},
        "coverage_sec": coverage([{"start": e["start"], "end": e["end"]} for e in episodes]),
    }


def retention_rows(before, after):
    """같은 speech event를 쓰는 행끼리 짝지어 의미 보존을 잰다(§23)."""
    index = {}
    for episode in before:
        for speech_id in episode.get("speech_event_ids", []) or []:
            index.setdefault(speech_id, episode)
    rows = []
    for episode in after:
        for speech_id in episode.get("speech_event_ids", []) or []:
            source = index.get(speech_id)
            if not source:
                continue
            measure = style.information_retention(episode["summary"], source["summary"], [])
            rows.append({"speech_event_id": speech_id,
                         "before_episode_id": source["episode_id"],
                         "after_episode_id": episode["episode_id"],
                         "display": episode.get("display"),
                         "before_display": source.get("display"),
                         # 원문 발췌였던 행은 애초에 비교 대상이 아니다 — 거기서 낱말이
                         # 사라지는 것이 이번 작업의 목적이다.
                         "comparable": source.get("display") in ("GENERATIVE", "REGENERATED"),
                         "before": source["summary"], "after": episode["summary"],
                         **{k: measure[k] for k in ("topic_retention", "dropped_numbers",
                                                    "chars_before", "chars_after")}})
            break
    return rows


def lost_events(before, after, decisions):
    """BEFORE에는 있었는데 AFTER에서 사라진 speech event — 정보 손실의 실제 단위다."""
    after_ids = {sid for e in after for sid in (e.get("speech_event_ids") or [])
                 if e["evidence"] in SPEECH_EVIDENCE}
    out = []
    for episode in before:
        if episode["evidence"] not in SPEECH_EVIDENCE:
            continue
        for speech_id in episode.get("speech_event_ids") or []:
            if speech_id in after_ids:
                continue
            entry = (decisions or {}).get(speech_id) or {}
            out.append({"speech_event_id": speech_id, "episode_id": episode["episode_id"],
                        "before_display": episode.get("display"),
                        "before_summary": episode["summary"],
                        "decision": entry.get("decision"),
                        "attempt_reasons": entry.get("attempt_reasons")})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=EVENT)
    ap.add_argument("--before-dir", required=True)
    ap.add_argument("--after-dir", required=True)
    ap.add_argument("--clean-dir", required=True)
    ap.add_argument("--video-id", required=True)
    args = ap.parse_args(argv)

    before_dir, after_dir = Path(args.before_dir), Path(args.after_dir)
    utterances = {u["id"]: u for u in load(
        Path(args.clean_dir) / "speech" / "transcript_raw.json")["utterances"]}
    before = load(before_dir / "report_episodes.json")["episodes"]
    after = load(after_dir / "report_episodes.json")["episodes"]
    summaries = load(after_dir / "speech_report_summaries.json")
    decisions = summaries.get("events") or {}

    before_records = audit_rows(before, utterances)
    after_records = audit_rows(after, utterances)
    retention = retention_rows(before, after)
    comparable = [r for r in retention if r["comparable"]]
    lost = lost_events(before, after, decisions)
    guard_failures = {}
    for entry in decisions.values():
        for reasons in entry.get("attempt_reasons") or []:
            for reason in reasons:
                guard_failures[reason] = guard_failures.get(reason, 0) + 1

    payload = {
        "event": EVENT, "video_id": args.video_id,
        "before": {"source": str(before_dir), **side(before, before_records)},
        "after": {"source": str(after_dir), **side(after, after_records)},
        "speech_report_decisions": summaries.get("counts", {}),
        "guard_failure_counts": guard_failures,
        "new_inference": summaries.get("provenance", {}).get("calls"),
        "information_retention": {
            "paired_rows": len(retention),
            "comparable_rows": len(comparable),
            "median_topic_retention": (
                sorted(r["topic_retention"] for r in comparable)[len(comparable) // 2]
                if comparable else None),
            "rows_below_quarter": sum(1 for r in comparable if r["topic_retention"] < 0.25),
            "rows_with_dropped_numbers": sum(1 for r in comparable if r["dropped_numbers"]),
            "loss_candidates": [{k: r[k] for k in ("speech_event_id", "topic_retention",
                                                   "dropped_numbers", "before", "after")}
                                for r in comparable if r["topic_retention"] < 0.25
                                or r["dropped_numbers"]],
            "rows": retention},
        "lost_speech_events": lost,
        "before_row_audit": before_records,
        "after_row_audit": after_records,
    }
    write(after_dir / "before_after_comparison.json", payload)

    md = ["# BEFORE(composer_v2) / AFTER(speech report style) — %s" % args.video_id, "",
          "| 항목 | BEFORE | AFTER |", "|---|---|---|"]
    for label, key in (("report row", "report_rows"), ("화면 행", "visual_rows"),
                       ("음성 행", "audio_rows"), ("음성+화면 행", "visual_audio_rows"),
                       ("전사형 음성 행", "speech_transcript_style_rows"),
                       ("원문 복사 행", "raw_transcript_rows"),
                       ("화면 행 문체 미달(동결 대상)", "visual_non_declarative_rows"),
                       ("원문 발췌 표시 행", "extractive_fallback_rows"),
                       ("커버리지(초)", "coverage_sec")):
        md.append("| %s | %s | %s |" % (label, payload["before"][key], payload["after"][key]))
    md += ["", "```", "표시 상태  %s" % json.dumps(payload["speech_report_decisions"],
                                                ensure_ascii=False),
           "가드 차단  %s" % json.dumps(guard_failures, ensure_ascii=False),
           "새 추론    %s" % json.dumps(payload["new_inference"], ensure_ascii=False),
           "의미 보존  비교 가능 행 %s · 중앙값 %s · 0.25 미만 %s · 수치 빠진 행 %s"
           % (payload["information_retention"]["comparable_rows"],
              payload["information_retention"]["median_topic_retention"],
              payload["information_retention"]["rows_below_quarter"],
              payload["information_retention"]["rows_with_dropped_numbers"]),
           "사라진 음성 event  %d" % len(lost), "```"]
    (after_dir / "before_after_comparison.md").write_text("\n".join(md) + "\n",
                                                          encoding="utf-8", newline="\n")
    print(json.dumps({"before": {k: payload["before"][k] for k in
                                 ("report_rows", "speech_transcript_style_rows",
                                  "raw_transcript_rows", "extractive_fallback_rows")},
                      "after": {k: payload["after"][k] for k in
                                ("report_rows", "speech_transcript_style_rows",
                                 "raw_transcript_rows", "extractive_fallback_rows")},
                      "decisions": payload["speech_report_decisions"],
                      "lost_speech_events": len(lost)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Speech Event → 보고서 문체 요약 (서버 GPU 실행).

```
입력   clean speech/            speech_events.json · transcript_raw.json · asr_diagnostics.json
       clean generative_summary.json   이전에 승인된 구분(category)만 참조
       patch2 fallback_decisions.json  이번에 다시 쓸 대상과 그 이전 표시 상태
       speech_reportability.json       보고 가치 판정(동결)
출력   speech_report_summaries.json
```

새 모델을 만들지 않는다 — 기존 frozen report model을 그대로 쓴다(§8). 바뀌는 것은
**프롬프트와 통과 조건**뿐이고, 통과 조건은 기존 가드 전량 + 전사 복사·문체 검사다.

생성 실패를 원문 발췌로 복구하지 않는다(§3). 실패하면 구분 범위 안의 한 문장이거나
음성 보류다.
"""
import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "jds_video" / "_internal"))

import wvr_generative_guard_v1 as guard            # noqa: E402
import wvr_grounding_guard_v1 as grounding         # noqa: E402
import wvr_report_composer_v2 as composer          # noqa: E402
import wvr_report_usability_v1 as usability        # noqa: E402
import wvr_speech_report_style_v1 as style         # noqa: E402
import wvr_summary_arm_v1 as arm                   # noqa: E402

EVENT = "WVR_SPEECH_REPORT_STYLE_COMPRESSION_V1"
PROMPT_VERSION = "WVR_SPEECH_REPORT_STYLE_V1/2026-09-18"
VERIFY_PROMPT_VERSION = "WVR_CLAIM_VERIFY_V1/2026-09-17"   # 검증 프롬프트는 동결본 그대로

REWRITABLE_DISPLAYS = ("GENERATIVE", "REGENERATED", "EXTRACTIVE_FALLBACK")
UNRELIABLE_ASR = ("ASR_LOW_CONFIDENCE", "ASR_REPETITION_ANOMALY")
UNCERTAIN_MARK = "[전사 불확실] "

_RULES = """작성 규칙
- 위 발화에서 확인되는 내용만 쓴다. 발화에 없는 사실·수치·이름·기관·장소·목적·
  인과관계·평가를 새로 만들지 마라.
- 발화 문장을 그대로 옮기지 마라. 무엇을 말했는지 정리해서 다시 쓴다.
- 말버릇, 군말, 반복, 감탄, 호칭, 되묻는 말은 빼라.
- 1인칭 주어("제가", "저는", "우리는")를 쓰지 말고 비인칭으로 쓴다.
- 한국어 1~2문장으로 쓰고, 모든 문장을 "-다"로 끝낸다. 물음표·느낌표를 쓰지 마라.
- 발화가 실제로 한 일에 따라 설명한다 / 논의한다 / 보고한다 / 검토한다 / 제안한다 /
  안내한다 / 질문한다 / 답변한다 / 점검한다 / 언급한다 중에서 고른다. 근거가 없으면
  그 동사를 쓰지 마라.
- 수치는 발화에 실제로 있고 이 구간의 핵심일 때만 남긴다. 새 수치를 만들지 마라.
- "[전사 불확실]"이 붙은 발화의 낱말은 뜻을 지어내 고치지 마라. 그 낱말을 빼도 뜻이
  통하면 더 일반적인 표현으로 줄여 쓰고, 통하지 않으면 그 부분을 쓰지 마라.
- 발화 번호(U0001 같은 것)나 화자 번호를 문장에 쓰지 마라.
- category는 이 구간의 주제를 나타내는 짧은 한국어 명사구다.
- 출력은 JSON 하나만. 다른 말을 덧붙이지 마라: {"category": "...", "summary": "..."}"""

_RETRY = """

이전 출력은 다음 이유로 보고서에 쓸 수 없다: %s
발화 문장을 옮기지 말고 무엇을 말했는지만 비인칭 보고 문체로 1~2문장 쓴다.
모든 문장은 "-다"로 끝낸다. 한국어로만 답한다."""

_VERIFY_TEMPLATE = """아래 "발화"만 보고 "주장"이 사실인지 판정한다.

발화
{evidence}

주장
{claim}

판정 기준
- SUPPORTED: 발화에서 직접 확인된다.
- UNCERTAIN: 발화와 관련은 있으나 그렇게 단정할 수 없다.
- UNSUPPORTED: 발화에 없는 대상·역할·관계·사실이다.

규칙
- 발화 밖의 상식이나 배경지식을 쓰지 마라.
- 발화에 없는 인물·역할(예: 고객, 서비스 제공자)이 주장에 나오면 UNSUPPORTED다.
- 출력은 JSON 하나만: {{"verdict": "SUPPORTED|UNCERTAIN|UNSUPPORTED", "reason": "한 문장"}}"""


def git_head():
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                             capture_output=True, text=True)
        return out.stdout.strip() or None
    except OSError:
        return None


def build_prompt(event, utterances, asr_states, approved_category, dropped_count):
    """§9 — 이 event의 발화와 그 진단만 넣는다. 다른 event·영상 metadata는 넣지 않는다."""
    lines = ["다음은 한 영상의 %s ~ %s 구간에서 나온 발화다. 이 구간에서 무엇을 말했는지"
             " 보고서 문장으로 정리하라." % (arm.hhmmss(event["start"]), arm.hhmmss(event["end"])),
             "", "발화"]
    for item in utterances:
        mark = UNCERTAIN_MARK if asr_states.get(item["id"]) in UNRELIABLE_ASR else ""
        lines.append("- %s%s" % (mark, item["text"].strip()))
    notes = []
    if approved_category:
        notes.append("이 구간에 이미 확인된 주제: %s" % approved_category)
    if dropped_count:
        notes.append("전사가 깨진 발화 %d건은 근거에서 빠졌다." % dropped_count)
    if notes:
        lines += ["", "참고"] + ["- %s" % note for note in notes]
    lines += ["", _RULES]
    return "\n".join(lines)


def parse_verdict(raw):
    import re

    match = re.search(r"\{.*\}", raw or "", re.S)
    if not match:
        return {"verdict": guard.UNCERTAIN, "reason": "판정 JSON 없음"}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"verdict": guard.UNCERTAIN, "reason": "판정 JSON 파싱 실패"}
    verdict = str(parsed.get("verdict", "")).upper()
    if verdict not in (guard.SUPPORTED, guard.UNCERTAIN, guard.UNSUPPORTED):
        verdict = guard.UNCERTAIN
    return {"verdict": verdict, "reason": str(parsed.get("reason", ""))[:300]}


def run_guards(parsed, evidence_texts, all_texts, verify):
    """기존 가드 전량 + 이번 계층의 두 검사. 어느 하나라도 걸리면 쓰지 않는다(§10)."""
    summary = (parsed or {}).get("summary", "")
    category = (parsed or {}).get("category", "")
    reasons = []

    language = guard.language_gate(summary)
    category_language = guard.language_gate(category)
    if language["status"] != guard.PASS:
        reasons.append(guard.LANGUAGE_GATE_FAIL)
    if category_language["status"] != guard.PASS:
        reasons.append("CATEGORY_LANGUAGE_GATE_FAIL")

    display_language = usability.display_language_check(summary, all_texts)
    if display_language["status"] == usability.FAIL:
        reasons.append(usability.DISPLAY_LANGUAGE_MIX_FAIL)

    ground = grounding.check_grounding(summary, evidence_texts)
    if ground["status"] != grounding.GROUNDED:
        reasons.append(ground["status"])

    numbers = arm.unsupported_numbers(summary, evidence_texts)
    if numbers:
        reasons.append("UNSUPPORTED_NUMBER")

    verification = guard.verify_summary(summary, evidence_texts, verify) if verify else None
    if verification and verification["status"] == guard.UNSUPPORTED:
        reasons.append("UNSUPPORTED_CLAIM")

    audit = style.audit_report_style(summary, all_texts)
    if audit["status"] != style.TRANSCRIPT_STYLE_PASS:
        reasons.append(style.TRANSCRIPT_STYLE_FAIL)

    return {"summary": summary, "category": category, "approved": not reasons,
            "reasons": reasons, "language": language, "category_language": category_language,
            "display_language": display_language, "grounding": ground,
            "unsupported_numbers": numbers, "verification": verification,
            "style_audit": audit, "style_signals": audit["signals"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=EVENT)
    ap.add_argument("--clean-dir", required=True)
    ap.add_argument("--patch2-dir", required=True)
    ap.add_argument("--reportability", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--max-new-tokens", type=int, default=256)
    ap.add_argument("--verify-max-new-tokens", type=int, default=160)
    ap.add_argument("--limit", type=int, help="canary용 — 앞의 N건만 처리한다")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    clean, patch2 = Path(args.clean_dir), Path(args.patch2_dir)
    speech = clean / "speech"
    utterances = {u["id"]: u for u in
                  json.loads((speech / "transcript_raw.json").read_text(encoding="utf-8"))["utterances"]}
    events = {e["speech_event_id"]: e for e in
              json.loads((speech / "speech_events.json").read_text(encoding="utf-8"))["speech_events"]}
    asr_states = {f["utterance_id"]: f["state"] for f in
                  json.loads((speech / "asr_diagnostics.json").read_text(encoding="utf-8"))["utterance_flags"]}
    decisions = json.loads((patch2 / "fallback_decisions.json").read_text(encoding="utf-8"))["decisions"]
    reportability = json.loads(Path(args.reportability).read_text(encoding="utf-8"))["events"]
    generative = json.loads((clean / "generative_summary.json").read_text(encoding="utf-8"))["events"]

    targets = [sid for sid in sorted(decisions)
               if decisions[sid].get("summary")
               and decisions[sid].get("display") in REWRITABLE_DISPLAYS
               and composer.is_reportable((reportability.get(sid) or {}).get("label"))]
    if args.limit:
        targets = targets[:args.limit]

    generate = None
    if not args.dry_run:
        import llm
        generate = llm.make_llm(args.model, max_new_tokens=args.max_new_tokens, load_4bit=False)

    started = time.time()
    calls = {"compress": 0, "regenerate": 0, "verify": 0}
    results = {}

    def verify(claim, evidence_texts):
        calls["verify"] += 1
        prompt = _VERIFY_TEMPLATE.format(
            evidence="\n".join("- " + t for t in evidence_texts), claim=claim)
        return parse_verdict(generate(prompt))

    for speech_id in targets:
        event = events.get(speech_id)
        decision = decisions[speech_id]
        if not event:
            continue
        members = [utterances[uid] for uid in event["supporting_utterance_ids"]
                   if uid in utterances]
        clean_members = guard.clean_evidence(members)
        evidence_texts = [u["text"] for u in clean_members]
        all_texts = [u["text"] for u in members]
        approved_category = ((generative.get(speech_id) or {}).get("parsed") or {}).get("category")
        prompt = build_prompt(event, clean_members, asr_states, approved_category,
                              len(members) - len(clean_members))

        entry = {"start": event["start"], "end": event["end"],
                 "utterance_ids": [u["id"] for u in members],
                 "evidence_utterance_ids": [u["id"] for u in clean_members],
                 "previous_display": decision.get("display"),
                 "previous_summary": decision.get("summary"),
                 "previous_category": approved_category,
                 "prompt_chars": len(prompt)}
        if args.dry_run:
            entry["prompt_head"] = prompt[:400]
            results[speech_id] = entry
            continue

        attempts, raws = [], []
        calls["compress"] += 1
        raws.append(generate(prompt))
        for index in range(2):
            try:
                parsed = arm.parse_summary_output(raws[index])
            except ValueError as exc:
                attempts.append({"summary": "", "category": "", "approved": False,
                                 "reasons": ["PARSE_FAIL"], "parse_error": str(exc)})
            else:
                attempts.append(run_guards(parsed, evidence_texts, all_texts, verify))
            if attempts[-1]["approved"] or index == 1:
                break
            calls["regenerate"] += 1
            raws.append(generate(prompt + _RETRY % ", ".join(attempts[-1]["reasons"])))

        # 압축이 두 번 다 막혔으면, **이미 동결 가드를 통과해 쓰이고 있던** 요약이
        # 보고 문체 조건까지 만족하는지 본다. 원문 발췌가 아니라 같은 생성 계층이다.
        if (not attempts[-1]["approved"]
                and decision.get("display") in ("GENERATIVE", "REGENERATED")
                and (decision.get("summary") or "").strip()):
            retained = run_guards({"summary": decision["summary"],
                                   "category": approved_category or ""},
                                  evidence_texts, all_texts, verify=None)
            retained["decision"] = style.APPROVED_SUMMARY_RETAINED
            retained["note"] = "claim 검증은 동결 파이프라인에서 이미 통과했다 — 다시 묻지 않는다"
            attempts.append(retained)

        # "승인된 구분"은 **동결 파이프라인이 실제로 채택한** 구분만이다. 추출식으로
        # 되돌아간 event의 category는 그 생성이 가드에 막힌 것이라 승인된 적이 없다.
        category_approved = decision.get("display") in ("GENERATIVE", "REGENERATED")
        candidates = [{"category": attempt.get("category"), "approved": False}
                      for attempt in attempts if attempt.get("category")]
        if approved_category:
            candidates.append({"category": approved_category,
                               "approved": category_approved})
        outcome = style.resolve_decision(attempts, candidates, evidence_texts)
        entry.update({k: outcome[k] for k in
                      ("decision", "summary", "category", "attempt_index",
                       "attempt_reasons", "reason")})
        entry["attempts"] = attempts
        entry["raw"] = [r[:600] for r in raws]
        if outcome["summary"]:
            entry["final_style_audit"] = style.audit_report_style(outcome["summary"], all_texts)
            entry["retention"] = style.information_retention(
                outcome["summary"], decision.get("summary") or "", all_texts)
        # 원문 발췌는 근거 계층에만 남는다 — 사용자 보고서로 가지 않는다(§3·§19).
        entry["evidence_extractive_only"] = (
            decision.get("summary") if decision.get("display") == "EXTRACTIVE_FALLBACK" else None)
        results[speech_id] = entry

    counts = {}
    for entry in results.values():
        counts[entry.get("decision")] = counts.get(entry.get("decision"), 0) + 1
    payload = {"event": EVENT, "video_id": args.video_id, "dry_run": bool(args.dry_run),
               "provenance": {"model_name": args.model, "do_sample": False,
                              "max_new_tokens": args.max_new_tokens,
                              "prompt_version": PROMPT_VERSION,
                              "verify_prompt_version": VERIFY_PROMPT_VERSION,
                              "same_model_as_verifier": True,
                              "bias_note": "검증기가 생성기와 같은 모델이다 — 기존 조건을 유지했다",
                              "code_git_head": git_head(), "host": platform.node(),
                              "calls": calls, "elapsed_sec": round(time.time() - started, 1)},
               "targets": targets, "counts": counts, "events": results}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                              encoding="utf-8", newline="\n")
    print(json.dumps({"targets": len(targets), "calls": calls, "counts": counts,
                      "elapsed_sec": payload["provenance"]["elapsed_sec"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

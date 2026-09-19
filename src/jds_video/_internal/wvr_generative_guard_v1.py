"""생성형 요약 가드 — 하드 게이트 · claim 단위 검증 · 안전한 fallback.

```
generative summary
   ↓ language_gate()        다른 언어로 이탈하면 여기서 끊는다(의미 검증에 맡기지 않는다)
   ↓ split_claims()         최소 주장 단위로 나눈다
   ↓ verify_summary()       claim마다 SUPPORTED / UNCERTAIN / UNSUPPORTED
   ↓ event_anomaly_summary() 근거 자체가 깨졌는지(STT anomaly) 본다
   ↓ decide_summary()       PASS → 생성문 / FAIL → 추출식 fallback
```

PHASE A 실측이 이 설계의 이유다.

```
임베딩 코사인만으로는  정상 압축(0.7958)과 환각(0.5811)이 뒤섞여 구분되지 않았다
어휘 미지원 비율로도   중앙값 0.40 · p90 0.70이라 임계로 가를 수 없다
언어 이탈             chapter 1건이 중국어로 나왔고 의미 검증은 이를 잡지 못한다
```

새 사실로 실패를 복구하지 않는다 — 실패하면 **원문 발췌(추출식)로 되돌린다**.
"""
from __future__ import annotations

import re
import unicodedata

PASS = "PASS"
FAIL = "FAIL"
SUPPORTED = "SUPPORTED"
UNCERTAIN = "UNCERTAIN"
UNSUPPORTED = "UNSUPPORTED"

GENERATIVE = "GENERATIVE"
REGENERATED = "REGENERATED"
SAFE_FALLBACK = "SAFE_FALLBACK"
EXTRACTIVE_FALLBACK = "EXTRACTIVE_FALLBACK"

LANGUAGE_GATE_FAIL = "LANGUAGE_GATE_FAIL"
NORMAL = "NORMAL"
STT_ANOMALY = "STT_ANOMALY"
LOW_CONFIDENCE = "LOW_CONFIDENCE"

MIN_HANGUL_RATIO = 0.45        # 문자 중 한글 비율이 이보다 낮으면 한국어 출력으로 보지 않는다
REPEAT_TOKEN_MIN = 4           # 같은 낱말이 이만큼 이어지면 전사 이상으로 본다
ANOMALY_DEPENDENCY_RATIO = 0.6 # 근거의 이 비율 이상이 이상 발화면 생성을 신뢰하지 않는다

_HAN = re.compile(r"[一-鿿㐀-䶿]")
_KANA = re.compile(r"[぀-ヿ]")
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
_HANGUL = re.compile(r"[가-힣]")
_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
_TOKEN = re.compile(r"[가-힣A-Za-z0-9]+")
# 문장 끝과 쉼표, 그리고 **어절 끝의** 연결어미에서만 나눈다. 어절 안의 "가고"처럼
# 우연히 같은 글자가 들어간 말까지 자르면 한 문장이 조각난다(실측).
_CLAIM_SPLIT = re.compile(r"(?<=[.!?])\s+|,\s*(?=\S)|(?<=[가-힣])(?:하며|으며|지만)\s+(?=\S)")


# ── 언어 하드 게이트 ────────────────────────────────────────────────────

def language_gate(text, min_hangul_ratio=MIN_HANGUL_RATIO):
    """사용자에게 나갈 문장이 한국어인지. 다른 문자 체계는 즉시 막는다."""
    value = (text or "").strip()
    if not value:
        return {"status": FAIL, "reason_code": LANGUAGE_GATE_FAIL, "reason": "빈 문자열"}
    for pattern, name in ((_HAN, "한자"), (_KANA, "가나"), (_CYRILLIC, "키릴")):
        if pattern.search(value):
            return {"status": FAIL, "reason_code": LANGUAGE_GATE_FAIL,
                    "reason": "%s가 섞였다" % name}
    letters = _LETTER.findall(value)
    if not letters:
        return {"status": FAIL, "reason_code": LANGUAGE_GATE_FAIL, "reason": "글자가 없다"}
    ratio = len(_HANGUL.findall(value)) / len(letters)
    if ratio < min_hangul_ratio:
        return {"status": FAIL, "reason_code": LANGUAGE_GATE_FAIL,
                "reason": "한글 비율이 낮다(%.2f)" % ratio}
    return {"status": PASS, "reason": "한국어", "hangul_ratio": round(ratio, 3)}


# ── atomic claim ───────────────────────────────────────────────────────

def split_claims(summary, min_chars=4):
    """요약을 최소 주장 단위로 나눈다. 규칙 기반이라 결정적이다."""
    parts = [p.strip(" ,·") for p in _CLAIM_SPLIT.split(summary or "") if p and p.strip(" ,·")]
    claims = [p for p in parts if len(p) >= min_chars]
    return claims or ([summary.strip()] if (summary or "").strip() else [])


def verify_summary(summary, evidence_texts, verify):
    """claim마다 판정하고 가장 나쁜 결과를 요약 전체의 상태로 삼는다.

    `verify(claim, evidence_texts) -> {"verdict": ..., "reason": ...}`를 주입한다.
    하나라도 UNSUPPORTED면 그 요약은 그대로 쓰지 않는다.
    """
    claims = split_claims(summary)
    results = []
    for claim in claims:
        outcome = verify(claim, list(evidence_texts))
        verdict = outcome.get("verdict", UNCERTAIN)
        if verdict not in (SUPPORTED, UNCERTAIN, UNSUPPORTED):
            verdict = UNCERTAIN
        results.append({"claim": claim, "verdict": verdict,
                        "reason": outcome.get("reason", "")})
    if any(r["verdict"] == UNSUPPORTED for r in results):
        status = UNSUPPORTED
    elif results and all(r["verdict"] == SUPPORTED for r in results):
        status = SUPPORTED
    else:
        status = UNCERTAIN
    return {"status": status, "claims": results,
            "counts": {v: sum(1 for r in results if r["verdict"] == v)
                       for v in (SUPPORTED, UNCERTAIN, UNSUPPORTED)}}


# ── STT anomaly (전사는 고치지 않는다) ─────────────────────────────────

def _has_broken_characters(text):
    for char in text:
        if char.isspace() or char in ".,!?~…·%":
            continue
        category = unicodedata.category(char)
        if category.startswith("P") or category.startswith("N"):
            continue
        if _HANGUL.match(char) or ("A" <= char.upper() <= "Z"):
            continue
        if _HAN.match(char) or _KANA.match(char):
            continue
        return True                      # 한글·영문·한자·가나 어디에도 없는 글자
    return False


def _max_token_run(text):
    tokens = _TOKEN.findall(text)
    best = run = 1
    for index in range(1, len(tokens)):
        run = run + 1 if tokens[index] == tokens[index - 1] else 1
        best = max(best, run)
    return best if tokens else 0


def utterance_flag(utterance, repeat_min=REPEAT_TOKEN_MIN):
    text = utterance.get("text", "")
    if _max_token_run(text) >= repeat_min or _has_broken_characters(text):
        return STT_ANOMALY
    if utterance.get("low_confidence"):
        return LOW_CONFIDENCE
    return NORMAL


def event_anomaly_summary(utterances, dependency_ratio=ANOMALY_DEPENDENCY_RATIO):
    """근거 중 얼마가 깨졌는지. 대부분이 깨졌으면 생성문을 신뢰하지 않는다."""
    flags = {u["id"]: utterance_flag(u) for u in utterances}
    anomaly = [uid for uid, flag in flags.items() if flag == STT_ANOMALY]
    low = [uid for uid, flag in flags.items() if flag == LOW_CONFIDENCE]
    ratio = len(anomaly) / len(utterances) if utterances else 0.0
    return {"flags": flags, "anomaly_utterance_ids": anomaly,
            "low_confidence_utterance_ids": low,
            "anomaly_ratio": round(ratio, 3),
            "depends_on_anomaly": ratio >= dependency_ratio}


def clean_evidence(utterances):
    """생성 입력에서 이상 발화를 뺀다. 원본 전사는 그대로 둔다."""
    normal = [u for u in utterances if utterance_flag(u) == NORMAL]
    return normal or list(utterances)


# ── 최종 판정 ──────────────────────────────────────────────────────────

def decide_summary(generated, extractive, language, verification, anomaly, numbers,
                   regenerated=False):
    """가드를 모두 통과한 생성문만 보고서에 올린다. 실패하면 추출식으로 되돌린다."""
    reasons = []
    if language.get("status") != PASS:
        reasons.append(language.get("reason_code", LANGUAGE_GATE_FAIL))
    if verification.get("status") == UNSUPPORTED:
        reasons.append("UNSUPPORTED_CLAIM")
    elif verification.get("status") == UNCERTAIN:
        reasons.append("UNCERTAIN_CLAIM")
    if anomaly.get("depends_on_anomaly"):
        reasons.append("STT_ANOMALY_DEPENDENCY")
    if numbers:
        reasons.append("UNSUPPORTED_NUMBER")

    blocking = {LANGUAGE_GATE_FAIL, "UNSUPPORTED_CLAIM", "STT_ANOMALY_DEPENDENCY",
                "UNSUPPORTED_NUMBER"}
    if blocking & set(reasons) or not (generated or "").strip():
        return {"summary": extractive, "summary_source": EXTRACTIVE_FALLBACK,
                "reasons": reasons or ["EMPTY_GENERATION"]}
    return {"summary": generated,
            "summary_source": REGENERATED if regenerated else GENERATIVE,
            "reasons": reasons}


def source_counts(decisions):
    counts = {GENERATIVE: 0, REGENERATED: 0, SAFE_FALLBACK: 0, EXTRACTIVE_FALLBACK: 0}
    for decision in decisions:
        counts[decision["summary_source"]] = counts.get(decision["summary_source"], 0) + 1
    return counts

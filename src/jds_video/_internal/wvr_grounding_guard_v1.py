"""근거에 없던 사람·역할·기관·장소가 생성문에 새로 나타나는지 본다 + ASR 진단 상태.

```
왜 필요한가   claim 검증을 같은 모델에게 맡겼더니 "서비스 제공자가 고객에게…"를
              SUPPORTED로 통과시켰다. 프롬프트에 그 사례를 금지어로 적어도 막히지 않았다.
어떻게        의미 판정을 다시 모델에 묻지 않는다. 생성문에 등장한 **역할·기관·장소**를
              뽑아 근거 문자열과 대조한다. 임계값이 없고 결정적이다.
한계          모든 함의를 풀지 않는다. 위험한 변화(사람에게 없던 역할 부여, 새 기관·장소)만
              보수적으로 막는다. 애매하면 UNCERTAIN이고, UNCERTAIN은 승인 근거가 아니다.
```

서버에 다른 계열 지시모델이 없어(캐시에 Qwen 계열과 KURE뿐) 새 모델을 받지 않고
이 결정적 가드를 쓴다.
"""
from __future__ import annotations

import re

GROUNDED = "GROUNDED"
NOVEL_ENTITY = "NOVEL_ENTITY"
NOVEL_ROLE = "NOVEL_ROLE"
UNCERTAIN = "UNCERTAIN"

ASR_NORMAL = "ASR_NORMAL"
ASR_LOW_CONFIDENCE = "ASR_LOW_CONFIDENCE"
ASR_REPETITION_ANOMALY = "ASR_REPETITION_ANOMALY"
ASR_UNRESOLVED = "ASR_UNRESOLVED"

# 사람에게 역할을 부여하는 말. 화자를 이런 존재로 바꿔 쓰는 것이 이번에 막으려는 실패다.
ROLE_LEXICON = (
    "고객", "손님", "직원", "사장", "점원", "판매자", "구매자", "소비자", "이용객",
    "제공자", "공급자", "담당자", "관리자", "운영자", "진행자", "사회자", "발표자",
    "의뢰인", "의사", "간호사", "교사", "학생", "선생", "강사", "기사", "운전자",
    "작업자", "근로자", "노동자", "사용자", "가입자", "회원", "환자", "주민", "시민",
    "장관", "차관", "총리", "대통령", "의원", "청장", "국장", "과장", "위원", "위원장",
    "경찰", "군인", "소방관", "공무원", "기자", "변호사", "회계사", "요리사", "주최자",
    "서비스 제공자", "봉사자", "자원봉사자",
)

# 사람을 가리키되 역할을 새로 만들지 않는 중립어 — 이것만으로는 막지 않는다.
NEUTRAL_PERSON = (
    "사람", "사람들", "참가자", "참석자", "발화자", "화자", "모두", "여러분", "우리",
    "본인", "상대방", "다른 사람", "누군가", "일행",
)

# "회·단·사·점·원"은 회사·행사·점검처럼 흔한 말과 충돌해 뺐다. "부"는 정부 부처를
# 잡아야 해서 남기되 3자 이상 조건이 오분류를 막는다.
_ORG_SUFFIX = ("부", "청", "처", "센터", "위원회", "본부", "공사", "재단", "협회")
# 장소 접미사는 용언 활용과 충돌하는 것을 뺐다 — "면·리·로·길·장·관"을 두면
# "신청하면" 같은 말이 지명으로 잡힌다(실측: 회의 SP026 거짓 양성).
_PLACE_SUFFIX = ("역", "군", "읍", "마트", "시장", "공항", "터미널")
# 용언 활용형은 개체 후보가 아니다.
_VERB_TAIL = ("하면", "되면", "으면", "이면", "려면", "하고", "되고", "하는", "되는",
              "하며", "하여", "해서", "하지", "되지", "한다", "된다", "했다", "겠다",
              "합니다", "습니다", "입니다", "있다", "없다", "이다")
_ORG_PLACE_MIN = 3        # 접미사만으로 판단하지 않도록 최소 길이를 둔다

_TOKEN = re.compile(r"[가-힣]{2,}")
_STEM = re.compile(r"(은|는|이|가|을|를|에게|에서|에|으로|로|와|과|도|만|의|께|께서|들)$")


def _stem(word):
    return _STEM.sub("", word)


def _flat(texts):
    return re.sub(r"\s+", "", " ".join(texts or []))


def extract_entities(text):
    """생성문에서 역할·기관·장소 후보를 뽑는다. 활동 서술어는 건드리지 않는다."""
    words = [_stem(w) for w in _TOKEN.findall(text or "")]
    roles, orgs, places = [], [], []
    for word in words:
        if word in NEUTRAL_PERSON or word.endswith(_VERB_TAIL):
            continue
        if any(word == role or word.endswith(role) for role in ROLE_LEXICON):
            if word not in roles:
                roles.append(word)
            continue
        if len(word) >= _ORG_PLACE_MIN and word.endswith(_ORG_SUFFIX) and word not in orgs:
            orgs.append(word)
        elif len(word) >= _ORG_PLACE_MIN and word.endswith(_PLACE_SUFFIX) and word not in places:
            places.append(word)
    # 두 낱말짜리 역할 표현도 본다(예: "서비스 제공자")
    for role in ROLE_LEXICON:
        if " " in role and role in (text or "") and role not in roles:
            roles.append(role)
    return {"roles": roles, "orgs": orgs, "places": places}


def _grounding_of(entity, evidence_flat):
    """근거 문자열에 그 개체가 있는가. 접두 일치는 확정 근거로 보지 않는다."""
    compact = entity.replace(" ", "")
    if compact in evidence_flat:
        return "EXACT"
    if len(compact) >= 3:
        for length in range(len(compact) - 1, 2, -1):
            if compact[:length] in evidence_flat:
                return "PARTIAL"
    return "NONE"


def check_grounding(generated, evidence_texts, visual_texts=None):
    """생성문의 역할·기관·장소가 근거에 있는지 대조한다."""
    entities = extract_entities(generated)
    evidence_flat = _flat(list(evidence_texts or []) + list(visual_texts or []))
    checked, ungrounded, partial = [], [], []
    for kind in ("roles", "orgs", "places"):
        for entity in entities[kind]:
            grounding = _grounding_of(entity, evidence_flat)
            checked.append({"entity": entity, "kind": kind, "grounding": grounding})
            if grounding == "NONE":
                ungrounded.append(entity)
            elif grounding == "PARTIAL":
                partial.append(entity)

    if any(item["kind"] == "roles" and item["grounding"] == "NONE" for item in checked):
        status = NOVEL_ROLE
    elif ungrounded:
        status = NOVEL_ENTITY
    elif partial:
        status = UNCERTAIN
    else:
        status = GROUNDED
    return {"status": status, "checked": checked, "ungrounded": ungrounded,
            "partial": partial, "entities": entities}


def approve(language_pass, semantic_status, grounding_status):
    """§7 승인 조건 — 세 가지가 모두 맞아야 생성문을 쓴다."""
    reasons = []
    if not language_pass:
        reasons.append("LANGUAGE_GATE_FAIL")
    if semantic_status == "UNSUPPORTED":
        reasons.append("UNSUPPORTED_CLAIM")
    if grounding_status != GROUNDED:
        reasons.append(grounding_status)
    return {"approved": not reasons, "reasons": reasons}


# ── ASR 진단 (전사를 고치지 않는다) ────────────────────────────────────

LOW_LOGPROB = -1.0
HIGH_NO_SPEECH = 0.6
HIGH_COMPRESSION = 2.4


def asr_state(segment):
    """faster-whisper가 실제로 주는 값만 본다. 없는 지표를 만들지 않는다."""
    logprob = segment.get("avg_logprob")
    no_speech = segment.get("no_speech_prob")
    compression = segment.get("compression_ratio")
    if logprob is None and no_speech is None and compression is None:
        return ASR_UNRESOLVED
    if compression is not None and compression >= HIGH_COMPRESSION:
        return ASR_REPETITION_ANOMALY
    if (logprob is not None and logprob <= LOW_LOGPROB) or \
            (no_speech is not None and no_speech >= HIGH_NO_SPEECH):
        return ASR_LOW_CONFIDENCE
    return ASR_NORMAL


def asr_record(target_id, segment, words=None):
    """진단 기록. **무엇이 옳은 말이었는지 추측하지 않는다.**"""
    record = {
        "target_id": target_id,
        "text": segment.get("text", ""),
        "start": segment.get("start"),
        "end": segment.get("end"),
        "avg_logprob": segment.get("avg_logprob"),
        "no_speech_prob": segment.get("no_speech_prob"),
        "compression_ratio": segment.get("compression_ratio"),
        "state": asr_state(segment),
    }
    if words:
        record["words"] = [{"word": w.get("word"), "probability": w.get("probability"),
                            "start": w.get("start"), "end": w.get("end")} for w in words]
        probabilities = [w.get("probability") for w in words
                         if w.get("probability") is not None]
        if probabilities:
            record["min_word_probability"] = round(min(probabilities), 4)
            record["mean_word_probability"] = round(sum(probabilities) / len(probabilities), 4)
    return record

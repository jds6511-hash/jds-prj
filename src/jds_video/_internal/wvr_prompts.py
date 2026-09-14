"""WHOLE_VIDEO_REPORT_LIGHT_V1 생성 계약 8종 (2026-09-08 · freeze).

```
SPARSE_GLOBAL_PROMPT_V1   전체 영상 sparse pass — 거친 구조만
EVENT_PROMPT_V1           chunk 하나에서 사건 추출 (frames 입력)
EVENT_MERGE_PROMPT_V1     인접 chunk overlap 구간의 사건 통합 (텍스트만)
CHAPTER_PROMPT_V1         통합 사건 목록 → 의미 장
HIGHLIGHT_PROMPT_V1       장·사건 → 하이라이트
OVERVIEW_PROMPT_V1        장 → 개요 3~5문장
ANALYSIS_PROMPT_V1        장 → 분석 3~6항
CONCLUSION_PROMPT_V1      장·개요 → 결론 1~2문장
```

계약 본문은 **동결**이다. 문자를 하나라도 바꾸면 hash가 바뀌고
`tests/test_wvr_contract.py`가 사전등록 문서의 표와 불일치로 실패한다.
바꾸려면 새 버전 이름(`..._V2`)과 새 사전등록 사건이 필요하다.

입력 금지 항목은 프롬프트 본문에 적지 않는다 — 그것은 호출자의 계약이고
`wvr_contract.assert_video_only_inputs`가 막는다.
"""
import hashlib

# ── 모든 계약이 공유하는 규칙 ──────────────────────────────────────────
COMMON_RULES = """[공통 규칙]
- 한국어로만 쓴다. 한자·가나·라틴 문자로 된 낱말을 섞지 않는다.
- JSON 하나만 출력한다. 설명·머리말·코드펜스를 붙이지 않는다.
- 영상에서 보이는 것만 쓴다. 소리·대사·자막은 입력에 없으므로 말하지 않는다.
- 화면에 글자로 보이지 않는 상호·상품명·인물 이름을 추측해 쓰지 않는다.
- 시간은 영상 전체 기준 초 단위 실수로 쓴다.
- 근거가 없으면 항목을 만들지 않는다. 빈 목록을 출력하는 것이 허용된다."""


SPARSE_GLOBAL_PROMPT_V1 = """당신은 영상 전체에서 드문 간격으로 뽑은 프레임을 순서대로 본다.
세부 사건이 아니라 영상 전체의 거친 구조만 적는다.

%s
- major_phases는 시간순이고 서로 겹치지 않는다.
- approx_start_sec·approx_end_sec는 프레임이 보인 시각의 범위로만 적는다.

[출력 형식]
{"video_kind": "...",
 "recurring_subjects": ["..."],
 "major_phases": [{"label": "...", "approx_start_sec": 0.0, "approx_end_sec": 0.0}]}
""" % COMMON_RULES


EVENT_PROMPT_V1 = """당신은 한 구간(chunk)에서 뽑은 프레임을 시간순으로 본다.
이 구간에서 실제로 일어난 사건만 적는다.

%s
- start_sec·end_sec는 반드시 이 구간의 범위 안에 있어야 한다.
- 사건은 시간순으로 적고, 같은 장면을 두 항목으로 쪼개지 않는다.
- visible_evidence에는 그렇게 판단한 화면 근거를 적는다(동작·물체·장소·화면 글자).
- confidence는 high·medium·low 중 하나다. 흐릿하면 low로 적고 지우지 않는다.

[구간]
start_sec=%%(chunk_start).1f end_sec=%%(chunk_end).1f

[출력 형식]
{"events": [{"start_sec": 0.0, "end_sec": 0.0, "what_happens": "...",
             "visible_evidence": "...", "confidence": "high"}]}
""" % COMMON_RULES


EVENT_MERGE_PROMPT_V1 = """당신은 인접한 두 구간이 겹치는 시간대에서 각각 추출된 사건 목록을 받는다.
프레임은 주어지지 않는다. 두 목록을 하나로 정리하는 일만 한다.

%s
- 시간이 겹치고 같은 사건을 가리키는 항목만 하나로 합친다.
- 새 사건을 만들지 않는다. 합친 항목의 내용은 입력 문장에서만 만든다.
- 합칠 수 없으면 각각 그대로 남긴다. 근거 없이 지우지 않는다.
- event_ids에는 합쳐진 입력 항목의 id를 모두 적는다.

[겹치는 시간대]
start_sec=%%(overlap_start).1f end_sec=%%(overlap_end).1f

[앞 구간 사건]
%%(left)s

[뒤 구간 사건]
%%(right)s

[출력 형식]
{"merged": [{"event_ids": ["..."], "start_sec": 0.0, "end_sec": 0.0,
             "what_happens": "..."}],
 "kept": ["..."]}
""" % COMMON_RULES


CHAPTER_PROMPT_V1 = """당신은 영상 전체의 사건 목록을 받는다. 프레임은 주어지지 않는다.
사건을 묶어 의미 있는 장(chapter)으로 나눈다.

%s
- 장은 시간순이고 서로 겹치지 않는다.
- 각 장의 summary_sentences는 1~2문장이고, 문장마다 근거 사건 id를 적는다.
- 사건 목록에 없는 내용을 문장에 넣지 않는다.
- title은 12자 이내의 명사구로 쓴다.

[사건 목록]
%%(events)s

[출력 형식]
{"chapters": [{"title": "...", "start_sec": 0.0, "end_sec": 0.0,
               "summary_sentences": [{"text": "...", "source_event_ids": ["..."]}]}]}
""" % COMMON_RULES


HIGHLIGHT_PROMPT_V1 = """당신은 장 목록과 사건 목록을 받는다. 프레임은 주어지지 않는다.
영상을 처음 보는 사람에게 먼저 보여줄 구간을 고른다.

%s
- %%(min_count)d개 이상 %%(max_count)d개 이하로 고른다. 억지로 개수를 채우지 않는다.
- 구간의 시간은 근거 사건의 시간 범위 안에 있어야 한다.
- reason에는 왜 대표 구간인지 화면 근거로 적는다.

[장 목록]
%%(chapters)s

[사건 목록]
%%(events)s

[출력 형식]
{"highlights": [{"start_sec": 0.0, "end_sec": 0.0, "title": "...",
                 "reason": "...", "source_event_ids": ["..."]}]}
""" % COMMON_RULES


OVERVIEW_PROMPT_V1 = """당신은 장 목록만 받는다. 프레임과 사건 원문은 주어지지 않는다.
영상 전체가 무엇을 담고 있는지 개요를 쓴다.

%s
- 3문장 이상 5문장 이하로 쓴다.
- 문장마다 근거 장 id를 적는다.
- 장 요약 문장을 그대로 옮기지 않는다. 전체 흐름으로 다시 쓴다.

[장 목록]
%%(chapters)s

[출력 형식]
{"overview_sentences": [{"text": "...", "source_chapter_refs": ["..."]}]}
""" % COMMON_RULES


ANALYSIS_PROMPT_V1 = """당신은 장 목록만 받는다. 프레임과 사건 원문은 주어지지 않는다.
영상의 구성과 진행 방식을 분석한다.

%s
- 3항 이상 6항 이하로 쓴다.
- 항목마다 근거 장 id를 적는다.
- 장 요약 문장을 그대로 옮기지 않는다. 영상에 없는 배경 지식을 넣지 않는다.

[장 목록]
%%(chapters)s

[출력 형식]
{"analysis_points": [{"text": "...", "source_chapter_refs": ["..."]}]}
""" % COMMON_RULES


CONCLUSION_PROMPT_V1 = """당신은 장 목록과 개요를 받는다. 프레임은 주어지지 않는다.
보고서의 결론을 쓴다.

%s
- 1문장 이상 2문장 이하로 쓴다.
- 문장마다 근거 장 id를 적는다.
- 새 사실을 추가하지 않는다. 평가·권고를 쓰지 않는다.

[장 목록]
%%(chapters)s

[개요]
%%(overview)s

[출력 형식]
{"conclusion_sentences": [{"text": "...", "source_chapter_refs": ["..."]}]}
""" % COMMON_RULES


CONTRACTS = {
    "SPARSE_GLOBAL_PROMPT_V1": SPARSE_GLOBAL_PROMPT_V1,
    "EVENT_PROMPT_V1": EVENT_PROMPT_V1,
    "EVENT_MERGE_PROMPT_V1": EVENT_MERGE_PROMPT_V1,
    "CHAPTER_PROMPT_V1": CHAPTER_PROMPT_V1,
    "HIGHLIGHT_PROMPT_V1": HIGHLIGHT_PROMPT_V1,
    "OVERVIEW_PROMPT_V1": OVERVIEW_PROMPT_V1,
    "ANALYSIS_PROMPT_V1": ANALYSIS_PROMPT_V1,
    "CONCLUSION_PROMPT_V1": CONCLUSION_PROMPT_V1,
}

CONTRACT_COUNT = 8


def contract_hash(name: str) -> str:
    """계약 본문의 sha256. 사전등록 문서의 표와 일치해야 한다."""
    return hashlib.sha256(CONTRACTS[name].encode("utf-8")).hexdigest()


def contract_hashes() -> dict:
    return {name: contract_hash(name) for name in CONTRACTS}

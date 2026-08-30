# v2.1 Gate B — 티켓 분해 (2026-08-30)

```
대상    Gate B = LLM · GRD · AAR 의 P0 전부
성격    작업 분해 + preflight 기록
아님    모델 비교 · official test 접근 · M9
```

```
Canonical Episodes → Episode Content LLM → Grounding Validator → aar_canonical.json
```

Gate A에서 선 계약을 다시 구현하지 않는다. raw store · parse contract ·
sanitation · evidence timeline · canonical boundary는 **재사용만** 한다.

---

## PREFLIGHT (2026-08-30)

### P1 단일 LLM configuration — 스펙과 저장소가 다르다

```
FROZEN SPEC §22   content: {provider: ollama, model: qwen3:8b, temperature: 0}
저장소 실제        config.yaml report_model: Qwen/Qwen2.5-7B-Instruct
                  src/llm.py = transformers 경로 · ollama provider 미구현
                  BCS v0가 실제로 쓴 모델도 Qwen2.5-7B-Instruct
```

**스펙 본문을 고치지 않는다.** 여기에 compatibility mapping으로 남긴다.

```
Gate B acceptance 사용 모델   Qwen/Qwen2.5-7B-Instruct (transformers)
사유                          저장소에 이미 명시된 단일 configuration
                              ollama provider는 이 저장소에 존재하지 않는다
금지                          모델 비교 · Qwen vs Kanana 재개 · 모델 선택 실험
```

이 선택은 **사용자 확인 대기 항목**이다. deterministic 티켓(B-01·03~09)에는
영향이 없고, B-02 실행 전에 확정한다.

### P2 prompt contract — 스펙에 이미 있다 (§13)

```
필수   summary
선택   dialogue_note · stt_cites
금지   episode_id · start/end · segment_ids · support_span · anchor_cites
       source · provenance · canonical ordering · boundary
       title · key_actions[] · actors[] · importance[] · uncertainty_note
```

`stt_cites`는 **인용 후보**다. canonical provenance가 아니다(§14).
prompt version/hash는 아직 없다 — B-03에서 신설한다.

### P3 raw-before-parse — 이미 통과 가능

A-03 `SOURCE_TYPES`에 `llm`이 있다. 두 번째 raw store를 만들지 않는다.

### P4 failure vocabulary — A-04 그대로

`MODEL_FAILURE` · `PARSE_CONTRACT_FAILURE` · `EMPTY` · `VALID_PARSE`.
`status_for_store_outcome`이 store 어휘와 잇는다. sanitation·grounding 실패를
parse 실패로 재분류하지 않는다.

### P5 claim eligibility — A-05 그대로

`usable_for_claims`는 코드가 정하고 A-06이 변형 없이 전달한다(이미 잠김).
`FAIL_INELIGIBLE_SUPPORT`는 B-06에서 신설한다.

### P6 grounding 자동 검증 범위

`GRD-004`는 P1을 유지한다. NLI가 필요한 것을 결정적 P0로 위장하지 않는다.

```
BLOCKER      없음
결정 대기     MODEL-DECISION (B-02 착수 전) — acceptance priority P1과 다른 사안이다
```

---

## 티켓

```
B-01  Episode 구조 · content 스키마 · 코드 파생      deterministic   COMPLETE
B-03  prompt builder + version/hash                   deterministic   COMPLETE
B-02  LLM invocation adapter (A-03 raw 경유)          model-dependent  P1 확정 후
B-04  content 병합 · failure isolation                deterministic   COMPLETE
B-05  support/provenance 확정 바인딩                   deterministic   COMPLETE
B-06  grounding validator                             deterministic   COMPLETE
B-07  aar_canonical 스키마 · 직렬화                    deterministic   COMPLETE
B-08  Gate B fixtures + failure injection             deterministic   COMPLETE
B-09  acceptance 매핑 · 집계                          deterministic
```

**B-02만 모델을 쓴다.** (아래 MODEL-DECISION은 acceptance P1과 무관한 이름이다.) 착수 전에 model config · prompt version · raw persistence ·
failure classification 넷이 고정돼 있어야 한다.

---

## B-01 Episode 구조 + content 스키마  **COMPLETE**

```
green    LLM-001 · LLM-002 · LLM-003 · LLM-004 · LLM-005
산출물   src/v2_1_episode.py · tests/test_v2_1_episode.py (31 tests)
```

```
코드가 정한다   episode_id · start/end_seg · start/end_sec
               support_span · anchor_cites · source
모델이 낸다     summary · (선택) dialogue_note · stt_cites
```

`source` 파생은 **보존된 발화가 아니라 usable한 발화**만 센다. SUSPECT가 남아
있다는 이유로 `stt`가 되면 A-05 판정이 무의미해진다.

`anchors`는 m8_hier와 같은 규칙(시작·중간·끝 · 최대 3)이지만 그 모듈을 import하지
않는다 — v2.1이 legacy 파이프라인에 의존을 만들지 않는다.


---

## B-03 episode prompt builder + version/hash  **COMPLETE**

```
green    LLM-002 (출력 계약) · B-02의 선행 조건 中 prompt version
산출물   src/v2_1_prompt.py · tests/test_v2_1_prompt.py (23 tests)
```

### 근거는 목록이 아니라 블록으로 가른다

```
[근거]   usable_for_claims == true
[참고]   preserved == true AND usable_for_claims == false   기본값: 넣지 않는다
```

같은 목록에 `usable=false` 플래그만 붙이면 옆문으로 인용된다 — OPEN-9가 막으려던
것이 정확히 그것이다. 참고 블록은 opt-in이고, 들어갈 때도 "사실 주장의 근거로 쓸
수 없다"를 블록 머리에 적는다.

근거 블록이 비면 **프롬프트를 만들지 않는다.** 근거 없이 요약을 시키는 것이 환각의
입구다.

### prompt_hash는 계약의 지문이다

```
해시 입력   CONTRACT 사전 하나 (sort_keys 직렬화)
해시 비입력 에피소드 내용 · backend · 모델 이름 · run id · 실행 시각
```

테스트가 해시를 직접 재현해 입력을 못 박는다. 소스에서 단어를 찾는 방식은
`timeline`이 `time`에 걸려 쓸 수 없었고, 애초에 기능 검증이 아니었다.

### B-02 선행 조건 현황

```
prompt version        확보 (episode_content_v1 · contract_hash)
raw persistence       확보 (A-03 · source_type=llm)
failure classification 확보 (A-04)
model config          미확정  ← P1. B-02 착수 전 hard gate
```


---

## B-04 content 병합 + failure isolation  **COMPLETE**

```
green    LLM-009 (model failure isolation)
산출물   src/v2_1_content.py · tests/test_v2_1_content.py (22 tests)
```

### 셋을 분리했다

```
episode structure   언제나 유지 — 모델이 죽어도 id·시간·소속·순서가 남는다
content state       MODEL_FAILURE · PARSE_CONTRACT_FAILURE · EMPTY · VALID_PARSE
content payload     summary (+ 선택 dialogue_note · stt_cites)
```

`CONTENT_STATUSES is PARSE_STATUSES` — A-04와 다른 어휘를 만들지 않는다(테스트로 고정).

### 실패를 내용으로 위장하지 않는다

```
어떤 실패에도        content is None · status != VALID_PARSE
필드 누락            PARSE_CONTRACT_FAILURE · reason=missing_summary
                    (구조는 왔는데 약속한 필드가 없다 — 빈 출력과 다르다)
placeholder 문구     소스 스캔으로 금지
```

### 모델이 파생 필드를 덮지 못한다

`episode_id`·`support_span`·`source` 등을 모델이 보내와도 무시하고 `ignored_fields`에
기록한다. **조용히 버리지 않는다** — 기록이 없으면 프롬프트가 새는 것을 못 본다.
모르는 필드(`camera_move`)는 파생 필드가 아니므로 hijack으로 세지 않는다(SCH-006).

### 하지 않은 것

grounding을 시작하지 않았다. `usable_for_claims`·`FAIL_*`·named entity·timeline이
소스에 있으면 테스트가 실패한다. B-05·B-06 소관이다.


---

## B-05 support/provenance 바인딩  **COMPLETE**

```
green    LLM-004 · LLM-005의 최종 바인딩 · B-06의 입력
산출물   src/v2_1_binding.py · tests/test_v2_1_binding.py (22 tests)
invariant 조회 사실은 모두 보존하고, 판정은 하나도 하지 않는다
```

```
B-05   이 cite가 실제로 무엇을 가리키는가
B-06   그 결과로 이 claim을 통과시킬 수 있는가
```

### cite 하나당 남기는 사실

```
original_cite        모델이 쓴 표기 그대로
canonical_ref        해석된 번호 (없으면 None)
resolution_status    RESOLVED · UNKNOWN_SEGMENT · UNREADABLE
segment_id · inside_episode
sanitation_status · usable_for_claims · source_type
```

`inside_episode=False`는 **사실이지 판정이 아니다.** 인용을 영상 전체에서 조회하는
이유가 그것이다 — 구간 밖을 가리켰다는 것도 기록돼야 B-06이 구분할 수 있다.

구간은 있는데 그 채널에 근거가 없는 경우(`sanitation_status=None`)와 구간 자체가
없는 경우(`UNKNOWN_SEGMENT`)를 다른 사실로 적는다.

### 제거하지 않는다

자격 없는 인용도, 읽히지 않는 표기도, 중복도 그대로 남는다. 지우면 B-06이
"인용이 없었다"와 "SUSPECT를 실제로 인용했다"를 구분하지 못하고,
`FAIL_INELIGIBLE_SUPPORT`가 다시 참조 실패와 섞인다(OPEN-9).

provenance도 자격과 무관하게 **구간에 실제로 있던 근거 전부**를 적는다.
무엇을 근거로 삼았는지가 아니라 무엇이 있었는지가 provenance다.

### B-04 정정 — 정규화 지점을 옮겼다

처음에는 B-04가 인용을 정규화·정렬·중복 제거했다. 그러면 `original_cite`가
사라져 B-05가 볼 사실이 없다. **B-04는 모델이 쓴 그대로 보존**하고 표기 해석은
B-05가 한다. `EpisodeContent.stt_cites`의 타입도 그에 맞췄다.


---

## B-06 grounding validator  **COMPLETE**

```
green    GRD-001 · 002 · 003 · 005 · 006 · 008 · 009 · 010 · 011 · 012   10/10 P0
P1       GRD-004 미구현 유지 (의미 함의) · GRD-007은 partial support 정책
산출물   src/v2_1_grounding.py · tests/test_v2_1_grounding.py (35 tests)
```

### 상태 어휘

```
PASS · NOT_APPLICABLE
FAIL_NO_SUPPORT · FAIL_REFERENCE · FAIL_OUTSIDE_EPISODE
FAIL_INELIGIBLE_SUPPORT · FAIL_UNSUPPORTED
```

다섯 가지 참조 문제를 서로 다른 사유로 적는다.

```
unreadable_cite         표기가 참조가 아니다
unknown_segment         그런 구간이 없다
no_evidence_at_segment  구간은 있으나 그 채널에 근거가 없다
outside_episode         구간 밖을 가리킨다
ineligible_support      존재하지만 claim 근거가 될 수 없다
```

### GRD-012 — 통과 조건은 인용 개수가 아니다

자격 없는 인용은 **eligible이 0일 때만** 실패 사유가 된다. VALID이 따로 있으면
claim은 그 VALID으로 서고 SUSPECT 인용은 **진단으로 남는다**(사실은 지우지 않는다).
반대로 SUSPECT를 VALID 옆에 붙였다고 통과가 되지도 않는다 — 조건은 `eligible >= 1`이다.

첫 구현은 SUSPECT 인용 하나만으로 전체를 FAIL시켜 GRD-012와 어긋났다. 테스트가 잡았다.

### GRD-005 — 문자열 앵커의 한계를 명시한다

```
검사한다   숫자 · 따옴표 안 문자열 · 라틴 문자 토큰
안 한다    따옴표 없는 한국어 고유명사 일반
```

결정 가능한 것만 P0로 본다. 나머지는 GRD-004(P1)의 영역이고 여기서 흉내내지 않는다.

### short-circuit 하지 않는다

첫 실패에서 멈추지 않고 결정 가능한 위반을 전부 `reasons[]`에 적은 뒤 상태 하나를
고른다. 상태 선택 순서는 고정이라 인용 순서를 바꿔도 결과가 같다.

### 실패는 숨기지 않는다

```
구조 유지 · summary 유지 · dialogue만 제거 · grounding_status는 FAIL로 보존
```


---

## B-07 aar_canonical 스키마 + 직렬화  **COMPLETE**

```
green    AAR-001 ~ AAR-006 (P0) · AAR-007 (P1)
산출물   src/v2_1_aar.py · tests/test_v2_1_aar.py (34 tests)
```

### 정본은 표현 없이 선다

```
schema · video_id · run_id · segment_count
episodes[]  구조 · content_status · summary · dialogue_note
            provenance · grounding_status · grounding_reasons[]
quality_notes  결정적 집계만 (SPEC §15)
```

`highlights` · `synthesis` · `rendered` · `highlight_group` 같은 표현 어휘는
문서 최상위에서도, episode 안에서도 거부한다. **표현 계층이 무엇을 묶든 canonical
episode 목록은 고정점이다**(AAR-005).

### AAR-002는 Gate A 검증기를 재사용한다

겹침·빈틈·exactly-once 판정을 다시 구현하지 않고 `validate_partition`을 부른다.
소스 스캔이 그 재사용을 강제한다 — 두 벌이 되면 언젠가 갈라진다.

### 재실행 동일성은 구조에 대한 것이다

```
structural_signature   episode_id · start/end_seg · start/end_sec
포함하지 않는다        run_id · summary · 판정 · 직렬화 바이트
```

run id가 달라 파일이 달라지는 것은 위반이 아니다. 경계가 움직이면 signature가
바뀌고, 문장만 바뀌면 그대로다.

### 직렬화기는 재판정하지 않는다

grounding 실패를 누락하거나 통과처럼 정규화하면 GRD-009 위반이다. 실패 사유
배열까지 그대로 싣고 왕복에서도 보존한다. `validate_grounding`·`anchors_in`이
소스에 있으면 테스트가 실패한다.


---

## B-08 Gate B fixtures + failure injection  **COMPLETE**

```
산출물   tests/v2_1_gate_b.py (공용 파이프라인) · tests/test_v2_1_failure_injection.py
         28 tests
```

단위 테스트는 자기 계층 안에서만 본다. 여기서는 **사슬 전체를 통과시킨 뒤** 결함이
어디서 잡히는지 본다 — 계층 사이의 틈으로 새는 결함은 이 방식으로만 보인다.

```
segments → raw store → sanitation → timeline → episodes
        → content → binding → grounding → aar_canonical
```

모델 출력 자리에는 payload 사전·문자열·주입된 실패를 넣는다. LLM은 부르지 않는다.

### 고정한 주입 9종

```
1  모델 실패가 구조를 지우는가              구조·id·경계 유지 · summary는 None
2  parse 실패가 EMPTY로 위장되는가          PARSE_CONTRACT_FAILURE로 남는다
3  모델의 파생 필드가 채택되는가            무시 + ignored_fields에 기록
4  SUSPECT만으로 통과하는가                 FAIL_INELIGIBLE_SUPPORT
5  VALID 옆 SUSPECT가 필수 근거가 되는가    VALID만 남겨도 PASS · SUSPECT만 남기면 FAIL
6  없는 참조가 다른 segment로 보정되는가    segment_id=None 유지 · FAIL_REFERENCE
7  직렬화가 실패를 통과로 정규화하는가      상태·사유가 원본과 일치
8  표현 필드가 정본에 섞이는가              최상위·episode 안 모두 거부
9  partition 일부가 빠지는가                누락·겹침·빈틈 전부 거부
```

주입 목록과 테스트의 대응을 `_COVERAGE` 지도로 들고, 지도가 어긋나면 먼저 깨진다.

### 주입 5의 설계

"VALID이 있으니 통과"가 맞는지 확인하려면 **SUSPECT를 빼도 통과하는지** 봐야 한다.
그래서 같은 claim을 `[9]`(VALID만)과 `[6]`(SUSPECT만)으로 두 번 돌려 전자는 PASS,
후자는 FAIL인 것을 함께 잰다.

### 주입 7의 한계를 적는다

문서를 손으로 고쳐 `grounding_status`를 PASS로 바꾸면 **형식 검증만으로는 잡히지
않는다.** 원본 판정과 대조해야 드러난다. 그 사실 자체를 테스트로 남겼다 —
`validate_aar`가 만능이라는 오해를 막는다.


---

## Gate B P1 정리 (2026-08-30)

matrix 기준 Gate B의 P1은 **7개**다. 이전 보고에서 "P1 3/3"이라고 적은 것은 근거
없는 수치였다 — 정정한다.

```
LLM-006  no ASR case          CONTRACT PASS / B-02 integration pending
LLM-007  no caption case      CONTRACT PASS / B-02 integration pending
LLM-010  rich dialogue        CONTRACT PASS / B-02 integration pending
LLM-008  empty evidence       PASS
GRD-004  unsupported event    WAIVED   (V2_1_P1_WAIVERS.md)
GRD-007  partial support      PASS
AAR-007  serialization roundtrip  PASS
```

### CONTRACT PASS를 PASS와 구분하는 이유

지금 확인할 수 있는 것은 **그 입력을 모델에게 올바르게 전달할 수 있다**까지다.
B-02가 없으므로 실제 호출 뒤 `summary`가 raw store → parse → merge를 거쳐 돌아오는
것은 검증할 수 없다. 특히 `LLM-010`을 "프롬프트에 대화가 들어갔다"만으로 닫으면
표현이 과해진다.

B-02 이후 같은 S1·S3·S4 fixture를 adapter integration test에 태워 확인하고 그때
`PASS`로 승격한다.

```
S3 caption-only   정상 summary 또는 명시적 content failure
S4 ASR-only       정상 summary 또는 명시적 content failure
S1 rich dialogue  dialogue evidence를 포함한 실제 invocation
```

산출물: `tests/test_v2_1_llm_p1_contract.py` (13 tests)

### A-10 fixture 정정 — S3 · S4도 퇴화해 있었다

S1에서 한 번 고친 결함(같은 문장 12회 → 채널 전체가 반복 판정에 걸려 usable 근거
0)이 S3·S4에 그대로 남아 있었다. `LLM-006`·`LLM-007`을 쓰려는 순간 드러났다.

재발 방지 테스트를 **문자열 유일성이 아니라 usable 근거 존재**로 다시 썼다 —
S1의 boilerplate 8건은 의도된 설계(SAN-010 vs SAN-011)라 유일성으로는 잴 수 없다.

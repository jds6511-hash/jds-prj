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
B-02a LLM adapter contract (fake generator 주입)      deterministic   COMPLETE
B-02b 실제 모델 invocation (lab GPU)                 model-dependent  COMPLETE
B-04  content 병합 · failure isolation                deterministic   COMPLETE
B-05  support/provenance 확정 바인딩                   deterministic   COMPLETE
B-06  grounding validator                             deterministic   COMPLETE
B-07  aar_canonical 스키마 · 직렬화                    deterministic   COMPLETE
B-08  Gate B fixtures + failure injection             deterministic   COMPLETE
B-09  acceptance 매핑 · 집계                          deterministic   COMPLETE
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


---

## MODEL-DECISION — **CLOSED (2026-08-30)**

```
provider   transformers
model      Qwen/Qwen2.5-7B-Instruct
```

근거.

```
저장소의 실제 report_model과 일치 (config.yaml)
src/llm.py에 transformers 경로가 이미 있다
ollama provider는 이 저장소에 구현돼 있지 않다
BCS v0가 쓴 content model과도 같다
추가 비교 없이 단일 runtime configuration을 고정할 수 있다
```

**이 결정은 "Qwen2.5가 Qwen3보다 낫다"가 아니다.** 현재 저장소에서 Gate B를 구현
가능한 단일 runtime을 고정한 것뿐이므로 추가 모델 비교 금지와 충돌하지 않는다.

### FROZEN SPEC §22와의 compatibility mapping

```
SPEC §22          content: {provider: ollama, model: qwen3:8b, temperature: 0}
구현              transformers · Qwen/Qwen2.5-7B-Instruct · do_sample=False
```

**SPEC 본문은 고치지 않는다.** deviation을 여기에 기록한다.

`temperature: 0`은 ollama 표기다. transformers에서 같은 의도를 내는 것은 greedy
decoding, 즉 `do_sample=False`다. **이름을 억지로 맞추지 않는다** — `temperature=0`
이라고 적어 두고 실제로는 다른 것을 하는 편이 더 나쁘다. `GenerationConfig`는
`do_sample`·`max_new_tokens`만 담고 `temperature` 키를 두지 않는다(테스트로 고정).

---

## B-02a LLM adapter contract  **COMPLETE**

```
산출물   src/v2_1_llm_adapter.py · tests/test_v2_1_llm_adapter.py (27 tests)
성격     로컬·결정적. 모델을 올리지 않는다
```

```
generator 예외        MODEL_FAILURE            raw 없음
깨진 raw              PARSE_CONTRACT_FAILURE   raw 보존
빈 출력               EMPTY                    raw 보존
정상 summary          VALID_PARSE              raw 보존
```

**호출 실패에는 raw를 만들지 않는다.** 저장할 것이 없기 때문이다 — 빈 파일을 남기면
"모델이 빈 응답을 줬다"와 구분되지 않는다.

raw는 구간의 시작 segment 번호로 키를 잡는다(구간은 겹치지 않으므로 유일). A-03
store를 그대로 쓰고 두 번째 store를 만들지 않는다 — 소스 스캔이 강제한다.
provenance는 raw meta에 남는다: `producer=Qwen/Qwen2.5-7B-Instruct`,
`producer_version=do_sample=False max_new_tokens=512`.

모델을 올리는 코드(`transformers`·`torch`·`from_pretrained`·`cuda`)가 소스에 있으면
테스트가 실패한다. 그것은 B-02b다.

---

## B-02b 실제 모델 invocation — 승인 대기

```
provider   transformers
model      Qwen/Qwen2.5-7B-Instruct
환경       lab GPU server (로컬 6GB로는 7B 실행 불가 — config.yaml 실측 주석)
데이터     Gate B synthetic fixture (S1 · S3 · S4)
```

하지 않는 것.

```
Qwen3 비교 · Kanana 비교 · prompt 후보 비교 · temperature sweep
generation parameter tuning · 성능 ranking · C0 재실험
official test · M9 · 새 GT
```

**모델 실험이 아니라 구현 integration 검증이다.** 끝나면 LLM-006·007·010을
`CONTRACT PASS → PASS`로 승격한다.


---

## B-02b 실제 모델 invocation — **COMPLETE (2026-08-31)**

```
서버      kixlab2 · RTX 4090 24564 MiB · driver 595.84
env       /ssd/daeseok/envs/prj  (transformers 5.14.1 · torch 2.13.0+cu130)
model     Qwen/Qwen2.5-7B-Instruct · llm_4bit=false · do_sample=False
          max_new_tokens=512 · 단일 호출 · 배치 없음
동기화     git archive HEAD | ssh … tar -x   (push 없음)
산출물     runs/v2_1/b02b_integration_run2.json
          runs/v2_1/b02b_raw/{run1,run2}_{S1,S3,S4}.raw
```

OOM 없음. 4bit 전환 없음. 모델 변경 없음. 프롬프트 변경 없음.

### run 1 — 세 호출 전부 PARSE_CONTRACT_FAILURE

모델은 **완전한 JSON을 코드펜스로 감쌌다.** 파서가 그 펜스를 `not_json_object`로
거절했다.

```
```json
{ "summary": "…", "stt_cites": [] }
```
```

이건 이 프로젝트가 세 번 겪은 **"표기를 계약으로 착각"**과 같은 부류다
(v2 canary 맨 배열 · BCS `"seg#55"`). 프롬프트가 아니라 파서를 고쳤다 —
결과를 보고 프롬프트를 만지면 그 순간 prompt tuning 실험이 된다.

받아들이는 범위는 좁게 못 박았다(A-04 · 5 tests).

```
출력 전체가 펜스 하나로 감싸인 경우만 벗긴다
벗긴 뒤에도 완전한 JSON이어야 한다 — 깨졌으면 실패 (구조 fallback 아님)
펜스 밖 설명문은 받지 않는다 — 어디까지가 출력인지 알 수 없다
```

### run 2 — 세 경로 전부 통과

```
S3  LLM-006  VALID_PARSE  구조 유지  raw 146ch  dialogue_note None  cites []
S4  LLM-007  VALID_PARSE  구조 유지  raw 213ch  dialogue_note "선택"  cites 10개
S1  LLM-010  VALID_PARSE  구조 유지  raw 140ch  dialogue_note "선택"  cites [8, 10]
```

`invoke → raw persist → parse → merge`가 세 경로에서 모두 성립했고, 모델이 파생
필드를 보내지 않아 `ignored_fields`는 전부 비었다.

**run1과 run2의 raw는 바이트 동일하다**(sha256 일치). greedy decoding이 결정적이었고
두 실행의 차이는 파서뿐이라는 뜻이다.

### 발견 — 프롬프트 예시값 복사 (미조치)

`dialogue_note`에 **`"선택"`**이 들어왔다. 프롬프트 출력 예시
`{"summary": "한 문장", "dialogue_note": "선택", …}`의 자리표시자를 모델이 그대로
베낀 것이다. 이 프로젝트에서 3B를 기각한 사유(예시 문장 복사 오염)와 같은 종류다.

**이번에 고치지 않는다.** 프롬프트 수정은 별도 결정 사건이고, B-02b는 integration
검증이지 prompt 개선이 아니다. 실제 문서를 만들기 전에는 닫아야 할 결함으로 기록한다.

### 사고 기록 — run 1 산출물을 지웠다

재동기화 때 `rm -rf`로 서버 작업 트리를 지우면서 run 1의 결과 JSON도 함께 지웠다.
raw는 work 디렉터리에 남아 있어 회수했고, run1·run2 raw가 바이트 동일해 손실된
정보는 상태 요약뿐이다. **다음부터 산출물은 작업 트리 밖에 쓰거나 회수 후 동기화한다.**

### P1 승격

```
LLM-006  CONTRACT PASS → PASS
LLM-007  CONTRACT PASS → PASS
LLM-010  CONTRACT PASS → PASS
```

Gate B P1: **6 PASS · 1 WAIVED(GRD-004)**.


---

## B-09 Gate B 집계 — **두 층으로 나눈 판정**

```
산출물   tests/test_v2_1_gate_b_acceptance.py (37 tests)
```

### 층 1 — matrix acceptance

```
Gate B P0    22/22   전부 테스트로 덮임
Gate B P1     7      6 PASS + 1 WAIVED (GRD-004)
regression   무회귀 · tree clean · P1 waiver 규칙 만족

MATRIX ACCEPTANCE = PASS
```

지도는 matrix 원문을 다시 읽어 P0·P1이 빠지지 않았는지 검사하고, waiver로 닫은
항목은 **테스트가 없어야 하며 대장에 등록돼 있어야** 통과한다. skip은 waiver가
아니다.

`LLM-006 · 007 · 010`은 테스트만이 아니라 **B-02b 실행 산출물**로도 확인한다 —
`runs/v2_1/b02b_integration_run2.json`의 세 case가 `VALID_PARSE`이고 구조가
유지됐는지, 결정된 모델·decoding으로 돌았는지, 모델 비교 흔적이 없는지를 본다.

### 층 2 — closure

```
GATE B CLOSURE = BLOCKED
사유   OPEN-10  prompt example placeholder leakage
```

**테스트가 전부 green인데 알려진 결함을 안고 완료를 선언하지 않는다.** 두 층을
같은 것으로 취급하면 "green이니 끝"이라는 잘못된 종결이 남는다.

---

## OPEN-10 — Prompt example placeholder leakage  **수정 완료 · 판정 대기**

```
관측     dialogue_note = "선택"                  (B-02b run 2 · S1 · S4)
원인     출력 예시의 placeholder literal을 모델이 그대로 복사
         {"summary": "한 문장", "dialogue_note": "선택", "stt_cites": [구간 번호]}
위험     실제 dialogue 근거가 없는 구간에도 가짜 dialogue_note가 canonical content로
         남을 수 있다
분류     implementation defect
         모델 비교 아님 · prompt 품질 튜닝 아님
전례     3B를 기각했던 "예시 문장 복사 오염"과 같은 종류
증거     runs/v2_1/b02b_integration_run2.json · runs/v2_1/b02b_raw/run2_S{1,4}.raw
```

**GRD-004 waiver로 덮지 않는다.** 그 waiver는 일반적인 semantic entailment 한계에
대한 것이고, 이것은 우리가 프롬프트에 직접 넣어 둔 문자열이 복사되는 **재현 가능한
producer-side contamination**이다. 범위를 넓혀 먹이면 waiver가 너무 많은 것을 덮는다.

### 수정 원칙 — prompt tuning 실험이 아니다

```
한다     재현된 literal placeholder leakage 제거만
         (예시에서 자연어 자리표시자 제거 · optional field를 생략 가능 구조로 표현)
         같은 S1 · S3 · S4 세 건 재실행으로 오염이 사라졌는지 확인
안 한다   prompt 후보 비교 · 문장 품질 평가 · generation 파라미터 조정
         모델 비교 · 새 fixture · official test
```

`prompt_hash`가 바뀌므로 그 사실도 기록한다.

---

## 실행 절차 결함 (software acceptance 아님)

```
사고    재동기화 rm -rf가 서버 작업 트리 안의 run 1 결과 JSON을 함께 지웠다
영향    raw는 work 디렉터리에서 회수 · run1·run2 raw가 바이트 동일해 손실은 상태 요약뿐
분류    execution-procedure defect
규칙    산출물은 checkout 트리 밖에 쓰거나, 동기화 전에 회수 완료를 확인한다
```


---

## OPEN-10 수정 후 재실행 (run 3 · 2026-08-31)

```
prompt     episode_content_v1 → v2 · contract_hash beaa322ea0200d3d
조건       동일 — Qwen/Qwen2.5-7B-Instruct · do_sample=False · max_new_tokens=512
           llm_4bit=false · 같은 S1 · S3 · S4 · 새 fixture 없음
산출물     runs/v2_1/b02b_integration_run3.json · b02b_raw/run3_S{1,3,4}.raw
           (이번에는 checkout 트리 밖 /ssd/daeseok/b02b_out 에 쓰고 회수했다)
```

### 지정한 acceptance — 충족

```
S1 · S3 · S4 에서 "선택" leakage 없음      OK  (raw 원문에도 없음)
VALID_PARSE 유지                          OK  세 건 전부
canonical episode 구조 불변                OK  intact=True
같은 model · do_sample · max_new_tokens    OK
raw-before-parse 유지                      OK  raw_ref 세 건 모두 존재
ignored_fields 비어 있음                   OK  파생 필드 hijack 없음
```

### 그러나 같은 부류가 다른 모양으로 나타났다

```
run 2   dialogue_note = "선택"                     예시 자리표시자 복사
run 3   dialogue_note = "[0, 1, 2, …]"   (S4)      인용 목록을 note에 넣음
        dialogue_note = "['seg#8', 'seg#10']" (S1)
        S3는 ASR이 아예 없는데 stt_cites 12개       지어낸 인용
```

두 선택 항목을 모델이 혼동한다. **프롬프트 문구를 더 고치는 것은 이번 승인 범위
밖**이라 여기서 멈추고 사실만 기록한다.

### 결정적으로 다른 점 — canonical 오염 여부

저장된 run 3 raw를 파이프라인 뒤쪽에 그대로 태워 확인했다(모델·GPU 미사용).

```
S3   NOT_APPLICABLE      dialogue 없음 · summary 유지
S4   FAIL_NO_SUPPORT     dialogue 제거 · summary 유지
S1   FAIL_UNSUPPORTED    dialogue 제거 · summary 유지
```

**세 경로 모두 오염이 canonical content에 남지 않는다.** 반면 run 2의 `"선택"`은
앵커가 없어 grounding을 **통과했을 것**이다(`anchors_in("선택") == set()`).
그것이 OPEN-10이 중요했던 이유이고, 지금 상태가 run 2보다 엄밀히 나은 이유다.

검증: `tests/test_v2_1_open10_followup.py` (12 tests · 저장된 산출물만 사용)

### 판정은 사용자에게 넘긴다

```
관점 A   OPEN-10의 정의된 결함은 제거됐고 새 오염은 canonical에 도달하지 않는다
         → OPEN-10 CLOSED · 필드 혼동은 OPEN-11로 관찰 등록 · Gate B closure 가능

관점 B   같은 producer-side contamination이 재발했으므로 원인이 남아 있다
         → CLOSURE 계속 BLOCKED · 프롬프트 최소 수정 1회 추가 승인
```

**자동으로 A를 택하지 않는다.** 프롬프트를 반복 수정하기 시작하면 prompt tuning
실험이 되고, 그 경계는 사용자가 유보한 판단이다.

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
결정 대기     P1 모델 확정 (B-02 착수 전)
```

---

## 티켓

```
B-01  Episode 구조 · content 스키마 · 코드 파생      deterministic   COMPLETE
B-03  prompt builder + version/hash                   deterministic   COMPLETE
B-02  LLM invocation adapter (A-03 raw 경유)          model-dependent  P1 확정 후
B-04  content 병합 · failure isolation                deterministic   COMPLETE
B-05  support/provenance 확정 바인딩                   deterministic   COMPLETE
B-06  grounding validator                             deterministic
B-07  aar_canonical 스키마 · 직렬화                    deterministic
B-08  Gate B fixtures + failure injection             deterministic
B-09  acceptance 매핑 · 집계                          deterministic
```

**B-02만 모델을 쓴다.** 착수 전에 model config · prompt version · raw persistence ·
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

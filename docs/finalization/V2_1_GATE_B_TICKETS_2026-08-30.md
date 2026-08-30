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
B-02  LLM invocation adapter (A-03 raw 경유)          model-dependent
B-03  prompt builder + version/hash                   deterministic
B-04  content 병합 · failure isolation                deterministic
B-05  support/provenance 확정 바인딩                   deterministic
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

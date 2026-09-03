# E-04 GEO/TRI 감사 — Dataset Regression 10건 (2026-09-02)

## 판정 이력

```
E-04 감사(귀속)
     GEO = NOT CLOSED · TRI = NOT CLOSED
     PROVEN 2     GEO-003(P0) · TRI-006(P0)
     UNPROVEN 8   GEO-001 · GEO-002 · GEO-004 · TRI-001 · TRI-002
                  TRI-003 · TRI-004 · TRI-005
     GEO  P0 1/2 · P1 0/2
     TRI  P0 1/3 · P1 0/3
     분류  evidence-gap 7 · implementation-gap 1 (TRI-005)

E-04 보강(증거 테스트)
     GEO CLOSED       4/4  (P0 2/2 · P1 2/2)
     TRI = NOT CLOSED 5/6  — TRI-005 미해결 (P0)
```

```
production 코드 변경   없음
산출물   tests/test_v2_1_geo_tri_evidence.py     증거 · 14 tests
        tests/test_v2_1_geo_tri_acceptance.py   지도 · 25 tests
```

**§19 Dataset Regression은 아직 final tally에 넣지 않는다.** GEO는 4/4지만 같은 절의
TRI가 열려 있고, 부분 매핑을 집계에 넣지 않는 원칙을 유지한다.

---

## 이 family가 무엇인가

`V2_1_IMPLEMENTATION_PLAN_2026-08-30.md` §21 Fixture 전략.

```
geoje   풍부한 대화 STT · evidence integration · instruction-echo caption 회귀 · grounding
3I7     sparse/invalid STT · 오염·외국어 caption · 검은 화면 전환 · evidence 희소
```

즉 GEO = `wonyi_geoje`, TRI = `m8c2_3I7oGwk6EaQ` 회귀다.

**그런데 v2.1 테스트는 실제 영상 산출물을 읽지 않는다**(A-10: "work/·runs/를 읽지
않는다 — 실제 영상 산출물에 의존하면 fixture가 인덱스 재생성에 따라 흔들린다").
대신 합성 fixture의 **문자열이 그 두 영상의 실측값**이다.

```
INSTRUCTION_ECHO   geoje chunk3 최대 peak (d=0.6798) VLM 출력 그대로
FOREIGN_CAPTION    3I7 seg#1 캡션 전체가 중국어였던 실측값
BOILERPLATE        3I7 반복 문구 "다음 영상에서 만나요."
EXCITED_SPEECH     캡션용 반복 규칙을 STT에 적용해 지워졌던 geoje 실제 발화 11건 중 하나
MALFORMED_PAYLOAD  EP21 사고의 깨진 LLM 출력
```

fixture 주석이 그렇게 적는다 — "문자열은 전부 실측에서 가져왔다. 지어낸 오염 표본으로
sanitation을 맞추면 실제 산출물에서 빗나간다."

따라서 **결함 의미론에 대해서는 이 fixture가 정당한 회귀 운반체**다. 다만 그것이
"실제 영상 전체에서의 견고성"은 아니므로, closure 문구에서 그 구분을 못 박았다.

---

## PROVEN 2 (감사 시점)

### GEO-003 — instruction echo effect → fixed-window boundary 무영향 (P0) **PROVEN**

E-01a에서 만든 ERR-010 증거가 **바로 이 계약의 실행 증거**다.

```
test_err_010_an_instruction_echo_peak_does_not_move_the_fixed_window
  S6 echo fixture · boundary_signal에 C0 실측 최대 peak 0.6798 주입
  창 15s · 20s · 60s에서 boundary_positions · window_spans · episode 시간 구조 불변
```

새 기능 테스트를 또 만들지 않았다. 대신 acceptance mapping에서 **그 구체 테스트를
직접 잠갔다** — 상태 참조가 아니라 함수 이름·fixture·비교 대상까지 확인하므로,
그 테스트가 사라지거나 이름이 바뀌면 GEO-003이 깨진다.

### TRI-006 — 3I7 `"다음 영상에서 만나요."` (P0) **PROVEN**

OPEN-9 계약 세 단계가 각각 그 실제 문구로 이미 측정돼 있었다.

```
1. 삭제되지 않음    test_s1_separates_boilerplate_from_real_speech (8건 그대로)
                  test_san_010_every_status_preserves_the_original_text
2. SUSPECT        같은 테스트 — 8건 전부 SUSPECT/repeated
3. 단독 지지 불가   test_grd_011_suspect_only_support_is_ineligible
                  test_grd_012_suspect_beside_valid_does_not_auto_pass
```

`GRD-011/012`의 `world`가 쓰는 S1 seg#0이 바로 `BOILERPLATE`라서, 이 세 단계가
**같은 문구에 대해** 성립한다. E-04에서 세 단계를 한 자리에 묶은 테스트를 추가해
"eligible support로 쓰인 accepted claim 0건"까지 함께 적었다.

---

## UNPROVEN 8 (감사 시점)

### GEO-001 — rich STT ingestion → dialogue evidence 사용 (P1) **UNPROVEN**

있던 것.

```
test_llm_010_eligible_speech_reaches_the_evidence_block   프롬프트 [근거] 블록 진입
test_pass_keeps_the_dialogue                             S1에서 dialogue 유지
```

없던 것.

```
rich STT가 **dialogue claim의 근거가 됐다**는 사슬 전체. 있던 것은 (a) 프롬프트 진입과
(b) S1(반복 boilerplate가 대부분인 채널) 기준이다. "ASR가 timeline에 있다"·"source가
stt다"는 사용의 증거가 아니다. 그리고 그 ASR 근거를 없앴을 때 같은 dialogue가
통과하지 못한다는 대조 arm이 없었다.
```

분류: **evidence-gap.**

### GEO-002 — known instruction echo caption → 정상 caption과 구분 (P0) **UNPROVEN**

있던 것.

```
test_s6_echo_and_foreign_caption_are_flagged_differently   echo REJECTED · 외국어 SUSPECT
test_san_001_ordinary_caption_is_valid                     정상 caption VALID
```

없던 것.

```
**비교 arm이 같은 자리에 없었다.** echo가 단독으로 REJECTED인 것은 계약의 절반이고,
"정상 caption과 구분"은 두 arm을 함께 봐야 성립한다. 기존 두 테스트는 서로 다른
파일·다른 입력에 흩어져 있었다.
```

분류: **evidence-gap.**

감사 중 확인한 fixture 성질 하나를 적어 둔다. **S6의 나머지 10건은 같은 문장
반복이므로 그 자체로 `SUSPECT/repeated`다.** 그래서 S6 안에서 "정상 arm"을 잡으면
안 되고, 진짜 정상 caption은 S1(구간마다 다른 문장)에서 가져와야 한다. 처음에 S6를
정상 arm으로 썼다가 실패했고, 그 사실을 테스트 주석에 남겼다.

### GEO-004 — content generation → dialogue-heavy episode 처리 (P1) **UNPROVEN**

있던 것.

```
test_llm_006 · test_llm_010    프롬프트 계층에서 발화 근거 처리
여러 content merge 테스트       summary 생성 성공
```

없던 것.

```
fixture가 실제로 **dialogue-heavy임을 먼저 증명**하고, 그 상태에서 구조·내용·grounding이
처리되는지를 본 테스트. "summary 생성 성공"은 증거가 아니다.
```

분류: **evidence-gap.**

계약을 확장하지 않았다 — matrix 원문이 "처리"이므로 **dialogue 생성을 강제하지
않는다.** 근거가 붙은 dialogue가 통과하는 것까지만 확인하고, dialogue가 없는 모델
출력을 실패로 만들지 않았다.

### TRI-001 — effectively absent STT → 구조적 성공 (P1) **UNPROVEN**

있던 것.

```
test_llm_006_caption_only_episode_still_has_claim_evidence   S3 프롬프트 계층
```

없던 것.

```
S3(no STT · caption only · fixture 주석이 "3I7류")를 정본까지 태워 **구조**가
성공하는지 본 테스트. ERR-009(전 채널 공백)로 대체하지 않았다 — TRI-001은
"STT만 사실상 없음 + 다른 근거 존재"이고 더 약한 조건이다.
```

분류: **evidence-gap.** 내용 품질은 요구하지 않았다 — canonical partition 유효 ·
episode 존재 · 구조적 실패 없음까지다.

### TRI-002 — contaminated STT → meaningful dialogue 오인 금지 (P0) **UNPROVEN**

있던 것.

```
test_subtitle_credit_is_rejected              오염 판정 자체
test_grd_011_suspect_only_support_is_ineligible  SUSPECT 단독 → 실패
```

없던 것.

```
**오염 ASR**을 근거로 든 dialogue가 최종 상태까지 승격되지 않는 경로. 기존 증거는
(a) 판정 계층 단독과 (b) SUSPECT(반복) 사례다. STT 고유 오염인 `subtitle_credit`
(무발화 구간에 STT가 만들어 내던 형태)을 인용한 dialogue가 어떻게 되는지를 잰
테스트가 없었다.
```

분류: **evidence-gap.**

### TRI-003 — 외국어 caption 이상 → sanitation state 반영 (P1) **UNPROVEN**

있던 것.

```
test_s6_echo_and_foreign_caption_are_flagged_differently   SUSPECT/foreign_script
```

없던 것.

```
그 상태가 **timeline까지 실려 가는지**. 판정 계층에서만 확인돼 있었고,
`EvidenceRef.status · preserved · usable_for_claims`로 전달되는지는 재지 않았다.
```

분류: **evidence-gap.** 기존 계약이 정한 상태(`SUSPECT/foreign_script`)를 그대로
따랐고, 외국어라는 이유로 새 `REJECTED` 규칙을 만들지 않았다.

### TRI-004 — black-screen transition → diagnostic 가능 (P1) **UNPROVEN**

계약 의미를 먼저 확정했다. 임의 해석하지 않았다.

```
근거 1  V2_1_IMPLEMENTATION_PLAN §21   3I7 특성 목록에 "검은 화면 전환"
근거 2  C0_BOUNDARY_SIGNAL_OBSERVATION §4   상위 peak 30건 분류에 "검은 화면 전환  2"
근거 3  같은 문서 §4-1 · §4-3          seg#44 d=0.531 (검은 화면 → 만복대 바위)
                                     seg#10 d=0.496 (손 클로즈업 → 검은 화면)
```

즉 **"경계로 잡는다"가 아니라 "진단 산출물에 나타나고 확인 가능하다"**다. CP-008/009과
같은 자세다.

있던 것.

```
없다. C0 문서가 서술로 기록하고 있고, `runs/c0/c0_boundary_signal.json`에 두 건이
남아 있지만 그것을 재는 테스트가 없었다.
```

분류: **evidence-gap.**

### TRI-005 — sparse evidence → narrative hallucination 금지 (P0) **UNPROVEN**

**이 항목만 성격이 다르다. evidence-gap이 아니다.**

먼저 실측했다. sparse ASR(구간 9에 유효 발화 1건, 나머지 공백)에 대해 두 payload를
같은 경로로 태웠다.

```
summary "남성이 문을 연다."                                   grounding=PASS
summary "남성이 문을 열고 건물에 들어가 물건을 훔친 뒤 달아난다."   grounding=PASS
                                                            reasons=[]
```

**발명된 후속 사건이 그대로 통과한다.** 무엇이 걸리고 무엇이 안 걸리는지도 실측했다.

```
걸린다   dialogue_note에 근거 없는 숫자     FAIL_UNSUPPORTED      (unsupported_anchor)
        dialogue_note에 인용 없음         FAIL_NO_SUPPORT       (no_support_ref)
        오염·부적격 근거만 인용            FAIL_INELIGIBLE_SUPPORT
        구간 밖 인용                     FAIL_OUTSIDE_EPISODE
안 걸린다 summary의 발명된 숫자             PASS
        summary의 발명된 서사·후속 사건     PASS
```

이유는 설계에 이미 적혀 있다.

```
v2_1_synthesis.LIMITATION = "semantic entailment not automatically verified"
```

`summary`는 모델 출력을 **그대로 보존**하며(실패를 문구로 메우지 않기 위한 설계),
의미 함의 검증은 자동으로 하지 않는다고 선언돼 있다. dialogue claim은 근거 자격으로
게이트되지만 summary는 그렇지 않다.

분류: **implementation-gap.** 증거를 늘려 닫을 수 없다.

```
닫으려면 필요한 것   summary 수준 의미 함의 검증
그런데             표현 계층 LLM 도입 금지 · 새 prompt/containment 계약은 별도 사전등록
따라서             E-04에서 만들지 않는다. 판단은 사용자 결정 사항이다.
```

선택지를 적어 둔다(여기서 고르지 않는다).

```
A  matrix 문구를 계층별로 좁힌다
   "sparse evidence → dialogue claim이 근거를 넘어서지 않고, 표현 계층이 서사를
    덧붙이지 않는다"  → 이 형태면 지금 증거로 닫힌다
B  P0 유지 + 명시적 waiver — 한계를 그대로 기록한다
C  새 계약(의미 함의 검증)을 별도 사전등록으로 세운다
```

**A는 문구 완화이므로 matrix 본문 수정이고, 그것 자체가 별도 승인 사건이다.**
그래서 지금은 UNPROVEN으로 둔다.

---

# E-04 보강 — 일곱 건을 좁게 닫는다

`tests/test_v2_1_geo_tri_evidence.py` 14 tests. production 변경 없음.

```
GEO-001  S4(ASR 단독 12발화)에서 유효 근거 12건임을 먼저 확인
         dialogue + stt_cites[9] → PASS · 정본에 dialogue 유지 · cite VALID/eligible
         대조: 그 ASR을 공백으로 바꾸면 같은 dialogue가 통과하지 못한다
         반대편: 인용 없는 dialogue는 FAIL_NO_SUPPORT

GEO-002  echo REJECTED/instruction_echo · usable False · 원문 보존
         S6 나머지 10건은 SUSPECT/repeated — 상태도 사유도 echo와 다르다
         진짜 정상 caption(S1)은 VALID이고 근거로 쓸 수 있다(12건)

GEO-003  ERR-010 테스트를 이름·fixture·비교 대상까지 잠근다

GEO-004  dialogue-heavy 증명: 유효 ASR 12 vs 유효 caption 0
         결과: validate_aar ok · 두 episode 모두 VALID_PARSE · summary 존재
         근거 붙은 dialogue는 PASS · 근거 없는 쪽은 NOT_APPLICABLE
         source가 두 episode 모두 stt로 파생

TRI-001  S3(no STT) → validate_aar ok · partition 유효 · span 일치
         grounding은 NOT_APPLICABLE (실패가 아니다) · source visual
         **내용 품질을 요구하지 않는다**

TRI-002  오염 ASR("한글자막 by …")을 인용한 dialogue → FAIL_INELIGIBLE_SUPPORT
         보존은 유지(cite.sanitation_status = REJECTED · usable False)
         정본에서 dialogue 제거 · summary 유지
         반복 오염(3I7 문구)도 같은 결론

TRI-003  SUSPECT/foreign_script가 timeline EvidenceRef까지 전달
         preserved True · usable_for_claims False
         사유 구분(반복 vs 외국어) · 정상 caption(S1)은 근거로 사용 가능

TRI-004  산출물에서 검은 화면 전환 2건 이상 확인
         seg·distance·pct_rank·양쪽 캡션 원문이 함께 남아 있어야 통과
         전환의 **두 방향**(검은 화면으로 들어감 · 나옴)이 모두 있어야 통과
         관측이 채택으로 이어지지 않음도 함께 고정(not_done에 provider_adoption)

TRI-006  세 단계를 한 자리에서: 8건 보존 · SUSPECT/repeated · 실제 발화는 VALID
         이것만 인용한 claim → FAIL_INELIGIBLE_SUPPORT
         통과한 claim의 eligible cite에 이 문구가 0건 · 인용 사실은 기록 유지
```

---

## mutation 9건

```
1  binding에서 근거 자격을 버린다(timeline까지만 보존)     GEO-001 RED
2  echo 규칙 제거 — 정상 caption과 같게 처리               GEO-002 RED
3  ERR-010 테스트 이름 변경                              GEO-003 RED
4  source를 항상 visual로 (ASR 경로 무시)                 GEO-004 RED
5  STT 없으면 structural abort                          TRI-001 RED
6  subtitle_credit 규칙 제거 — 오염 STT를 VALID로          TRI-002 RED
7  foreign_script 규칙 제거                              TRI-003 RED
8  SUSPECT를 usable_for_claims=True로                    TRI-006 RED
9  산출물에서 검은 화면 peak 제거 / 한 방향만 남김 /
   캡션 원문 제거 (전부 사본에서)                          TRI-004 RED × 3
```

FROZEN 문서와 기록된 산출물은 수정하지 않았다. 9번은 **사본에서만** 흔들어 검사의
이가 있는지 확인했다.

TRI-005에는 mutation이 없다. 흔들 대상 자체가 없기 때문이다 — 사용자가 제안한
mutation("남성이 문을 열고 … 훔친다")은 **주입해도 GREEN**이고, 그것이 이 항목을
implementation-gap으로 분류한 근거다.

---

## 집계 반영

```
GEO      4/4 CLOSED    P0 2/2 · P1 2/2
TRI      5/6           P0 2/3 · P1 3/3 · TRI-005(P0) 미해결
§19      final tally 미편입 — 부분 매핑을 집계에 넣지 않는다
미매핑    14 (변화 없음) · P0 8 (변화 없음)
판정      IMPLEMENTATION_COMPLETE = NO
```

TRI-005가 해결되면 §19 10건을 한 번에 넣는다(→ 미매핑 4 · P0 3, REG만 남는다).

---

## Closure 문구

```
GEO CLOSED — dataset-regression evidence for rich STT, known instruction-echo
caption, and its boundary non-effect is mapped and verified.

TRI = NOT CLOSED — TRI-005 remains open (implementation-gap).

This does not establish semantic event-detection accuracy or general dataset
robustness.
```

## 이 감사가 주장하지 않는 것

```
실제 geoje·3I7 영상 전체에서 견고하다        합성 fixture로 결함 의미론만 쟀다
sparse evidence에서 서사 발명이 막힌다        막히지 않는다 (TRI-005)
dialogue-heavy episode에서 dialogue가 항상 생성된다   matrix 원문은 "처리"다
검은 화면을 경계로 잡는다                    진단에서 관측 가능하다는 것뿐이다
외국어 caption을 삭제한다                    보존하고 상태로 남긴다
```

---

## 후속 (2026-09-03)

```
TRI-005   CLOSED — C3 remediation
          이 감사의 분류(implementation-gap)는 그대로 둔다. 그 판단이 맞았고,
          증거를 늘려 닫지 않았다는 기록이기 때문이다.
GEO/TRI   10/10 → §19 final tally 편입
상세      V2_1_TRI_005_CLOSURE_2026-09-03.md
```

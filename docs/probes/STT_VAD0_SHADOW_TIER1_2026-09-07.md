# Tier 1 — VAD0 shadow abstention 결과 (2026-09-07)

트랙: `STT_VAD_ONLY_SHADOW_V1` · 사전등록
`docs/preregistration/STT_VAD_ONLY_SHADOW_V1_2026-09-07.md`

```
규칙        SUSPECT_STT_VAD0 := existing VALID AND speech_overlap_ratio == 0
범위        저장된 B1 40.4분 · 485구간 · LLM 없음 · 재전사 없음
바꾼 것      shadow 계산의 claim eligibility 하나뿐
확정 인덱스  무변경 · 제출본 무변경 (HWPX sha f874f643…)
```

## 1. 재현 정보

```
code_revision        1ed6d1aba749d5892a221e5ea104d45a46d16dc5
segments_sha256      aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92
measurements_sha256  59675339ab1fa64c1af6f38487db9573ecbaf56f6d821d646dc2763315b0be42
window_sec           60.0
flag                 --shadow-vad0 (기본값 off · 켜야만 계산된다)
```

## 2. 구간 계층

```
구간                       485
usable_for_claims  before  294
                   after    84
VALID → shadow SUSPECT     210
```

210은 Phase A 실측(210/294)과 같다 — 규칙 자체의 sanity check이며 성공 지표가 아니다.

## 3. episode 계층 — 가장 중요한 안전 수치

```
episode 수                 41
partition_equal            true      경계·구간 구조가 두 arm에서 동일
new ERR-009 전환           0         ← 근거가 0이 된 episode 없음
ASR 근거를 전부 잃은 episode 21 / 41
claim evidence 합계        777 → 567  (−210, ASR 제거분과 정확히 일치)
shadow 후 최소 eligible    5         (eligible == 1 로 떨어진 episode 0)
```

```
eligible 분포   before  16+ 36 · 6-15 5
               after   6-15 33 · 16+ 7 · 2-5 1

ASR eligible    before  6-15 33 · 2-5 7 · 1 1
               after   0 21 · 2-5 11 · 6-15 5 · 1 4

source 전환     stt → visual 21 · stt → stt 20
```

**ASR을 전부 잃은 21개 구간도 캡션 근거가 남아 evidence-empty가 되지 않는다.**
그래서 ERR-009 신규 진입이 0이다. TRI-005 sparse safe mode(eligible == 1) 진입도 0이다.

## 4. 회귀

```
GEO-001 · GEO-004 · TRI · ERR · sanitation 매핑 테스트   116 passed
shadow 경로 전용 회귀 (tests/test_stt_vad0_shadow.py)     20 passed
canonical partition 변화                                 0
raw text · raw artifact · 원본 판정 변경                  0
```

shadow 전용 회귀는 GEO 조건을 **shadow 경로로 통과**시킨다.

```
GEO-001  발화가 VAD speech와 겹치면 shadow에서도 근거로 남는다 (전 구간 동일)
GEO-004  근거가 빠져도 경계·구간 수가 그대로다
ERR-009  근거가 0이 되는 구간을 LLM 없이 결정적으로 센다
TRI-005  shadow는 근거를 줄이기만 한다 — 새 근거·새 문장을 만들지 않는다
```

## 5. mutation — 5개 전부 RED

```
M1  overlap > 0인데 SUSPECT        RED   test_any_positive_overlap_is_not_touched
M2  overlap == 0인데 VALID 유지     RED   episode counterfactual · ERR-009 검출
M3  원본 판정을 실제로 변경          RED   test_production_judgements_are_not_mutated
M4  기본 flag ON                    RED   test_the_flag_defaults_to_off
M5  라틴·반복·gap을 조건에 추가       RED   counterfactual 결과가 달라진다
```

M5가 이번 사전등록의 핵심을 지킨다 — 판정 입력은 `speech_overlap_ratio` 하나뿐이다.

## 6. 구현 형태

```
scripts/stt_vad0_shadow.py     신규 · production 판정을 mutate하지 않는다
                               원본과 counterfactual을 나란히 들고 있는 ShadowRow
                               dataclasses.replace로 **새 객체**를 만든다
src/v2_1_sanitation.py         수정 0
기본값                          SHADOW_VAD0_DEFAULT = False
측정값 없는 구간                KeyError — 0으로 간주하지 않는다
```

## 7. 이 결과가 주장하지 않는 것

```
210건의 Whisper hallucination을 제거했다     아니다 — GT가 없다
보고서 품질이 좋아졌다                        측정하지 않았다 (Tier 1은 LLM을 부르지 않는다)
표현 회수율이 유지된다                        아직 모른다 — Tier 2 소관이다
VAD-only를 채택해도 된다                     아니다 — §6 채택 관문은 Tier 2 이후다
```

허용되는 표현은 이것이다.

```
The shadow rule abstained from claim use for STT with zero overlap with the
frozen VAD speech intervals.
```

## 8. Tier 2 판단 재료 (있는 그대로)

```
raw preservation                 100%
partition equality               동일
GEO / TRI regression             0
VALID → shadow SUSPECT           210
episode eligible 분포            §3
new ERR-009 transitions          0
episodes losing all ASR          21 / 41
episodes losing all evidence     0
```

Tier 1 단계에서 "유의미한 episode가 대량 empty"는 **관측되지 않았다**(0건). 다만
21개 구간이 캡션 단독 근거로 바뀌므로, 요약 내용이 실제로 어떻게 달라지는지는
LLM을 부르는 Tier 2에서만 알 수 있다.

```
Tier 2 (S0/S1 paired 4090)   HOLD · 별도 승인 사건
production 채택               HOLD
제출본 재생성                  금지
```

## 9. 산출물

```
runs/stt_sanitation_v1/tier1_vad0/{summary,segment_rows,episodes}.json
scripts/stt_vad0_shadow.py · tests/test_stt_vad0_shadow.py (20건)
```

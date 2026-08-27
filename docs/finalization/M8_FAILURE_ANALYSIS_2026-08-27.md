# M8 실패 분해 — 2026-08-27 (진단 전용)

```
OFFICIAL RESULT — 이 문서가 바꾸지 않는다
  M8 evaluation   COMPLETE
  M8 acceptance   FAIL
  C1  파국 4/8편                                    임계 0      FAIL
  C2  median(event_temporal_alignment) 0.3311      >= 0.70    FAIL
  C3  max(Compression) 7.00                        <= 2.0     FAIL
  official result changed by this analysis:  NO
```

목적은 **왜 FAIL했는지 기존 동결 taxonomy와 재현 가능한 산출물로 설명하는 것**이다.
FAIL을 PASS로 재해석하는 것이 아니다. 임계·통계량·지표·taxonomy를 고치지 않았고,
공식 산출물을 쓰지 않았다(읽기만).

기계 정본: `m8_failure_analysis_2026-08-27.json`
(GT 사건 68 · 생성 사건 93 · 거부 11 · 청크 41 전건).

**post-hoc operationalization을 명시한다.** `alignment_type`은 동결 taxonomy
이름에 기계 규칙을 붙인 것이고 그 규칙은 사전등록에 없다 —
`reasonable_match` IoU≥0.5, `boundary_too_wide` ≥2배, `overmerge`는 다른 GT를
그 길이의 50% 이상 먹었을 때. `HIGH/MID/LOW/UNMATCHED` bucket도 관문 임계가 아니다.

---

## 1. Identity 대조

```
GT aggregate sha256   68a079ba17eb09fb22575e0f5b0db6daab7b7601805205a0022910e496a5696f
C2 metric             event_temporal_alignment · median · >= 0.70
C3 metric             리포트 문장 수 / 정답 사건 수 · max · <= 2.0
정답 목록 출처          FROZEN_*.json 8편 (load_reference, CSV 해시 대조 통과)
리포트 출처            work/<vid>/report.json 8편 (공식 실행 m8_official_0827)
```

---

## 2. 지배적 발견 4건

### 2-1. UNDER-GENERATION — 청크당 사건 산출량이 근본적으로 낮다

```
청크 41개 · 병합 전 원본 사건 합계 104건 · median 2.0건/청크
청크 크기 60구간 = 300초.  즉 5분 영상에서 사건을 약 2건 뽑는다
전체 2,075구간 → 유효 생성 사건 93건 · GT 68건
```

총량만 보면 93 > 68이라 부족해 보이지 않는다. **문제는 분포다.**

### 2-2. 놓친 정답 사건은 짧다 — 22/68건

```
미매칭 GT   n=22   길이 median  6구간 (min 3 · max 41)
매칭 GT     n=46   길이 median 24구간 (min 2 · max 173)
```

짧은 사건이 조직적으로 사라진다. 놓친 것들의 이름이 그것을 보여준다 —
`인트로` · `축하파티` · `출근길` · `퇴근` · `출근` · `아웃트로` ·
`운전하며 이동` · `호수와 숲`. 모델은 긴 장면을 하나로 묶고, 그 사이의
짧은 전환·이동·식사를 별도 사건으로 세우지 않는다.

### 2-3. OVER-FRAGMENTATION — 생성 사건의 51%가 아무 GT와도 매칭되지 않는다

```
생성 93건 중 미매칭 47건 (50.5%)
```

1:1 Hungarian에서 정답 사건 하나는 생성 사건 하나만 받는다. 같은 시간대에
여러 생성 사건이 몰리면 나머지는 전부 미매칭으로 떨어진다.

`baekmansonghee_jirisan`이 전형이다 — GT2 `등산시작`(105구간)에 생성 사건 **7건**이
겹친다. 매칭된 1건 외 6건은 `주차장과 인터뷰 준비` · `버스 이용 안내` ·
`지리산 역사와 코스 안내` · `식사와 휴식` · `로타리 대피소 도착`처럼 **그 긴 사건의
내부 조각**이다. GT 7건에 생성 15건, Compression 2.14.

즉 **2-1과 2-3은 같은 축의 양쪽이다** — 생성 사건의 입도가 GT 입도와 맞지 않는다.
짧은 GT는 삼켜지고(under), 긴 GT는 쪼개진다(over).

### 2-4. TEMPORAL / SPAN — 매칭돼도 경계가 어긋난다

```
정답 사건별 매칭 IoU (68건, 미매칭 = 0)
  min 0.0 · p25 0.0 · median 0.337 · p75 0.600 · max 0.955

bucket    HIGH(>=0.7) 13 · MID(0.3~0.7) 25 · LOW(<0.3) 8 · UNMATCHED 22
정렬 유형   reasonable_match 25 · missed_event 22 · boundary_shift 10 ·
           overmerge 7 · boundary_too_wide 4
```

**깨끗하게 맞은 것은 68건 중 25건뿐이다.** 나머지는 못 찾았거나(22),
경계가 밀렸거나(10), 여러 사건을 먹었거나(7), 너무 넓다(4).

θ별 recall(0.3/0.5/0.7)은 동결된 부지표이고 여기서도 진단으로만 인용한다 —
어느 θ도 판정에 쓰지 않았다.

---

## 3. 영상별 분류

```
video                    GT  문장  생성  미GT  미생성  거부  align  compr  분류
baekmansonghee_jirisan    7   15   15    1     9    0  0.520  2.14  OVER_FRAGMENTATION
softyeon_ceramics        12    6    6    6     0    1  0.217  0.50  UNDER_GENERATION
jissi_farm               11   11   11    3     3    0  0.428  1.00  RELATIVELY_STABLE
kbs_banff                10   14   14    8    12    5  0.102  1.40  MIXED(SPAN+REJECTION)
wonyi_gyeongju           10   16   16    1     7    0  0.561  1.60  RELATIVELY_STABLE
wonyi_geoje               8   10   10    1     3    1  0.547  1.25  RELATIVELY_STABLE
m8c2_3I7oGwk6EaQ          1    7     7    0     6    1  0.225  7.00  MIXED(OVER+SPAN)
m8c2_cIxG7OHYMPU          9   14   14    2     7    3  0.234  1.56  MIXED(SPAN+REJECTION)
```

**분류는 acceptance taxonomy가 아니라 설명용 post-hoc 요약이다.**
`RELATIVELY_STABLE` 3편도 alignment 0.43~0.56으로 임계 0.70에는 못 미친다 —
"안정"은 다른 5편 대비 상대적 표현이다.

**하나의 원인으로 설명되지 않는다**(Q4의 답). 최소 두 독립 failure mode가 섞여 있다:
① 사건 입도 불일치(2-1·2-3, 8편 전부에 영향) ② 거부·빈 청크로 인한 구간 공백
(2편에 집중). 여기에 ③ 경계 정밀도가 겹친다.

---

## 4. 상세 사례 4건

### 4-1. `softyeon_ceramics` — under-generation 대표

```
GT 12 · 생성 6 · 미매칭 GT 6 · 미매칭 생성 0

GT 0 [0,4]      5구간  gen —          missed_event   인트로 + 팝업 진행
GT 1 [5,9]      5구간  gen —          missed_event   축하파티
GT 2 [10,20]   11구간  gen —          missed_event   출근길
GT 3 [21,38]   18구간  gen [0,59]     IoU 0.300      가게 오픈 및 정리
GT 4 [39,63]   25구간  gen [55,74]    IoU 0.250      재료준비
GT 5 [75,111]  37구간  gen [75,113]   IoU 0.949      수업진행
GT 6 [112,116]  5구간  gen —          missed_event   퇴근
GT 7 [123,127]  5구간  gen —          missed_event   출근
GT 8 [131,138]  8구간  gen [110,169]  IoU 0.133      식사
GT 9 [148,176] 29구간  gen [165,171]  IoU 0.241      포장작업
GT10 [177,187] 11구간  gen [177,191]  IoU 0.733      타코야끼만들기
GT11 [188,191]  4구간  gen —          missed_event   아웃트로
```

**미매칭 생성이 0건이다** — 생성된 6건은 전부 어딘가에 매칭됐다. 즉 alignment 실패가
아니라 **산출량 자체가 부족**했다. 생성 span은 반대로 거대하다(`[0,59]`·`[110,169]`) —
청크 하나를 사실상 1~2개 사건으로 뭉갰고, 그 안의 짧은 GT 6건이 전부 삼켜졌다.

### 4-2. `baekmansonghee_jirisan` — over-fragmentation / compression 대표

```
GT 7 · 생성 15 · 미매칭 GT 1 · 미매칭 생성 9 · Compression 2.14

GT 2 [15,119] 105구간 gen [55,114] IoU 0.571 — 겹치는 생성 사건 7건
미매칭 생성 9건 중 5건이 GT2 범위 안:
  [11,19] 주차장과 인터뷰 준비 · [19,25] 버스 이용 안내 ·
  [25,38] 지리산 역사와 코스 안내 · [38,47] 식사와 휴식 · [47,59] 로타리 대피소 도착
```

긴 지속 사건 하나를 시간 조각으로 나눠 서술한다. 단순 spurious가 아니라
**입도 불일치**다 — 조각 각각은 그 시간대에 실제로 일어난 일이다.

### 4-3. `m8c2_3I7oGwk6EaQ` — 단일 장기 GT vs 생성 7건

```
GT 1건 [0,172] 173구간 (등산)  ·  생성 7건  ·  Compression 7.00  ·  alignment 0.225
매칭된 생성 span [55,93] → IoU 0.225 (boundary_shift)
미매칭 생성 6건: [0,29] · [30,59] · [65,71] · [72,89] · [89,114] · [165,172]
```

GT는 미매칭이 아니다(0건). **하나의 173구간 사건에 생성 7건이 붙었고, 그중 하나만
매칭되어 IoU가 0.225로 떨어졌다.** 이 영상의 Compression 7.00이 패널 MAX다.

부수 관측 — 생성 사건명 2건이 영어다(`NIGHT SCENE OF FOREST` ·
`SCENES OF NIGHT WALKING PATH`). **`description`은 전부 한국어다.** 그래서
`language_drift`가 ABSENT인 것은 동결 정의대로 맞다 — 규격 §1-2가 가른 것이
"문장 안에 외국 문자가 섞인 것"과 "생성 언어 자체가 바뀐 것"이고, 여기서
한국어 서술 기능은 유지됐다. 이름 필드의 언어 일관성은 별개 문제로 §8에 넣는다.

### 4-4. `kbs_banff` — 거부·빈 청크·span이 함께 큰 사례

```
GT 10 · 생성 14 · 미매칭 GT 8 · 미매칭 생성 12 · 거부 5 · alignment 0.102
span 커버 0.636 · C1 early_stop PRESENT (실패 청크 [0, 2] / 총 6)

청크별 병합 전 원본 사건 수
  c0: 4건 → **4건 전부 거부** → 유효 0 → 재생성 시도 → 그것도 0  ← GT0~4 구간
  c1: 1건   c2: 1건(재생성 실패)   c3: 1건   c4: 6건   c5: 6건

c0의 거부 4건과 겹치는 GT (전부 미매칭으로 끝남)
  too_many_evidence     [0,29]   → GT0, GT1
  too_many_evidence     [29,38]  → GT1, GT2
  evidence_outside_span [38,41]  → GT2
  too_many_evidence     [41,59]  → GT3, GT4
```

앞 절반(GT0~7 중 7건)이 미매칭이고, 그 구간의 생성 후보는 **제안되었으나 거부됐다.**
뒤 절반은 반대로 c4·c5에서 6건씩 나와 미매칭 생성 12건이 몰렸다.

**이것을 인과 증명으로 쓰지 않는다.** 말할 수 있는 것은
"미매칭 GT 8건 중 5건(GT0~4)이 거부된 후보의 시간대와 겹쳤다"까지다.
거부 후보를 되살려 counterfactual C2/C3를 계산하지 않았다.

---

## 5. 거부 분석 — 11건 전건

```
reason                  건수   특징
too_many_evidence         6   제안 span이 넓다: [0,29] [29,38] [41,59] [110,169] [220,279]
evidence_outside_span     4   [38,41] [25,35] [25,35] [35,50]
bad_span                  1   span 자체가 파싱 불가 (softyeon c1)

미매칭 GT와 시간대가 겹친 거부   7건 / 11건
  kbs_banff        5건 → GT0,1,2,3,4,8
  m8c2_cIxG7OHYMPU 1건 → GT6
  (나머지 4건은 매칭된 GT 또는 GT 없는 구간)
```

`too_many_evidence`는 `MAX_EVIDENCE_PER_EVENT` 상한 위반이다. 걸린 span이 전부
넓다는 것은 **§2 입도 문제와 같은 뿌리**를 가리킨다 — 넓은 span을 제안하면
근거 구간도 많아지고, 그러면 validator가 거부한다.

허용 진술: "미매칭 GT N건이 거부 후보 시간대와 겹쳤다."
금지 진술: "거부가 없었으면 C2가 X여서 PASS했다." — 하지 않았다.

---

## 6. C1 implementation gap — 사후 분류

```
A. OFFICIAL FROZEN RESULT   변경 없음
   C1 = FAIL · early_stop PRESENT 4/8

B. POST-HOC SEMANTIC DIAGNOSTIC
   kbs_banff          실패 청크 [0, 2] / 총 6 (마지막 5)   MID_STREAM_EMPTY_CHUNK
   m8c2_3I7oGwk6EaQ   실패 청크 [2]    / 총 4 (마지막 3)   MID_STREAM_EMPTY_CHUNK
   m8c2_cIxG7OHYMPU   실패 청크 [4]    / 총 6 (마지막 5)   MID_STREAM_EMPTY_CHUNK
   wonyi_geoje        실패 청크 [5]    / 총 6 (마지막 5)   TAIL_TERMINATION
```

동결 evaluator의 `early_stop` operationalization이 사전등록 산문보다 넓게
적용되었다 — 4건 중 **3건은 중간 구멍**이고 1건만 마지막 청크다.

`truncated_tail`은 8편 전부 None이다.

**"그러므로 C1은 사실 PASS"라고 쓰지 않는다.** 공식 C1은 FAIL이고,
acceptance impact는 **NONE**이다 — C1을 좁게 읽어도 C2(0.3311)·C3(7.00)이 FAIL이다.

---

## 7. Redundancy

```
spec recovered   부분적 — "같은 정답 사건을 여러 문장이 중복 서술한 비율"(§2-2) 한 줄뿐.
                 비율의 분자·분모가 없다
implemented      NO
status           DEFINITION_AMBIGUOUS
```

임의 임계·정의를 만들지 않았다. 대신 **다른 이름의 기계적 관측치**를 낸다 —
`gt_events_with_multiple_overlapping_generated`와 GT별 겹친 생성 사건 수 분포.
정본 JSON의 `per_video[*].redundancy_diagnostic`에 있다.
**C3를 대체하지 않고, 이 값으로 C3를 재해석하지 않는다.**

---

## 8. 원인 계층

```
OBSERVED — 계산·로그로 직접 확인
  O1  청크 41개에서 병합 전 원본 사건 104건, median 2.0건/청크(=300초)
  O2  미매칭 GT 22/68. 그 길이 median 6구간 vs 매칭 GT median 24구간
  O3  생성 93건 중 47건(50.5%)이 1:1에서 미매칭
  O4  매칭 IoU median 0.337. reasonable_match는 68건 중 25건
  O5  거부 11건 중 7건이 미매칭 GT 시간대와 겹침. kbs_banff c0은 4건 전부 거부 후
      재생성도 0건
  O6  early_stop 4건 중 3건이 중간 청크, 1건이 마지막 청크. truncated_tail 0편
  O7  m8c2_3I7oGwk6EaQ 생성 사건명 2건이 영어, description은 전부 한국어

SUPPORTED INTERPRETATION — 여러 관측이 지지
  S1  주된 실패는 **사건 입도 불일치**다. 같은 축의 양쪽으로 나타난다 —
      짧은 GT는 넓은 생성 span에 삼켜지고(O2·4-1), 긴 GT는 여러 조각으로
      쪼개진다(O3·4-2·4-3)
  S2  C2 0.3311은 "못 찾았다"와 "찾았지만 경계가 어긋났다"가 **반반**이다 —
      22건 미매칭(0.0 기여) + 매칭 46건의 IoU median이 0.5 미만(O4)
  S3  넓은 span 제안이 `too_many_evidence` 거부를 유발하고, 거부가 그 구간의
      유효 사건을 0으로 만든다(O5). 즉 거부는 독립 원인이 아니라 입도 문제의
      **하류 증상**일 가능성이 높다
  S4  C3 FAIL은 두 경로로 온다 — 긴 GT 쪼개기(baekmansonghee 2.14)와
      GT 자체가 1건인 영상(3I7 7.00). 후자를 빼도 임계를 넘는다

HYPOTHESIS — 아직 검증하지 않음
  H1  청크 프롬프트가 "이어지는 장면은 하나의 사건으로 묶어라"(규칙 3)를 강하게
      적용해 짧은 사건을 억제할 가능성
  H2  청크 경계(60구간)가 사건 경계와 무관해 경계 근처 사건이 절단·병합될 가능성
  H3  `MAX_EVIDENCE_PER_EVENT` 상한이 긴 사건을 제안할 유인을 꺾어, 모델이
      넓은 span + 소수 근거로 타협할 가능성
  H4  단일 장기 사건 영상(3I7)에서는 GT 입도 자체가 극단이라 어떤 생성 입도로도
      Compression을 맞출 수 없을 가능성
```

---

## 9. 개선 후보 — 제안만. 이번에 구현하지 않았다

| # | TARGET FAILURE MODE | EVIDENCE | PROPOSED CHANGE | EXPECTED EFFECT | RISK | REQUIRES NEW CONFIRMATION |
|---|---|---|---|---|---|---|
| R1 | 짧은 사건 누락 | O2 · 4-1 | 청크 프롬프트에 사건 수 하한을 두지 않되 "짧은 전환·이동·식사도 별개 사건" 예시 추가 | 미매칭 GT 감소 | 과분할로 Compression 악화 | YES |
| R2 | 긴 사건 쪼개기 | O3 · 4-2 | 병합 규칙을 이름 일치 + span 인접에서 **시간 인접 + 목적 유사**로 확장 | Compression·미매칭 생성 감소 | 서로 다른 사건 병합 | YES |
| R3 | 경계 정밀도 | O4 · S2 | span 제안을 근거 구간에서 파생하도록 제약 | IoU 상승 | span 축소로 recall 손실 | YES |
| R4 | 넓은 span → 거부 | O5 · S3 | `MAX_EVIDENCE_PER_EVENT` 초과를 거부가 아니라 **절단**으로 처리 | 유효 사건 0 구간 감소 | 근거 선택이 임의적 | YES |
| R5 | 빈 청크 | O5 · O6 | 재생성 1회 실패 시 청크를 반으로 쪼개 재시도 | 구간 공백 감소 | 지연 증가 | YES |
| R6 | 사건명 언어 혼입 | O7 | 사건명도 한국어로 쓰도록 프롬프트에 명시 | 표기 일관성 | 없음(서술은 이미 한국어) | YES |
| R7 | 단일 장기 사건 | S4 · H4 | C3의 GT 1건 영상 취급을 사전등록 amendment로 논의 | — | 사전등록 변경 사건 | YES |

**어느 것도 이번 작업에서 구현하지 않았다.** 프롬프트·config·모델·병합 로직
모두 손대지 않았다.

---

## 10. 확증 표본 귀결

```
current N=8 reusable for fresh confirmation      NO
fresh confirmation needed after material change  YES
```

N=8은 **공식 결과를 본 순간 소비된 confirmation sample**이다. 지금부터 이 8편은
failure analysis · diagnostic · redesign을 위한 development evidence로만 쓴다.
수정된 M8을 같은 8편으로 재실행해 "개선됐다"를 확증으로 주장할 수 없다.

이번 작업에서 새 패널 sourcing을 시작하지 않았고, N을 정하지 않았고,
새 라벨을 만들지 않았다.

---

## 11. 상태

```
M8 evaluation   COMPLETE
M8 acceptance   FAIL
M9              HOLD          official test opened: NO
push            NO
test39          접촉 없음
```

다음은 **사용자 결정 사건**이다 — R1~R7 중 무엇을 채택할지, 그리고 수정 후
fresh confirmation 패널을 어떻게 구성할지.

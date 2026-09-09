# WVR_SAMPLING_SEMANTIC_DENSITY_FRAME_ADJUDICATION_V1 결과 (2026-09-09)

사전등록: `docs/preregistration/WVR_FRAME_ADJUDICATION_V1_2026-09-09.md`
(commit `2c98977` — 판정 전 freeze) · packet `032a91b` · 관찰 도구 `937405c`
추론 0회 · GPU 미사용 · 프레임 512×288(모델 입력 픽셀)

```
사건 판정   SAMPLING_LOSS_CONFIRMED
            (사전등록 §6 우선순위 ②: DROP material 1건 확인 · FRAMES_INSUFFICIENT 0건)
Q1  GENERATION_ERROR_NOT_SAMPLING          / S0_CLAIM_MATCHES
Q2  GENERATION_ERROR_NOT_SAMPLING          / S1_CLAIM_MATCHES
Q3  DROP_FRAMES_CARRY_MATERIAL_INFORMATION / S0_CLAIM_MATCHES
```

normative source는 `runs/wvr_light_v1/frame_adjudication_verdicts.json`이다.

## 0. 관찰 순서와 그 오염 공개

```
이번 관찰    KEEP-only 대지 3장 → 그 다음 DROP-only 대지 3장 (Q1·Q2·Q3 순)
오염         packet 생성 검증 때 **KEEP·DROP 혼합 대지 3장을 이미 열었다**(commit 032a91b).
             따라서 "DROP을 처음 보는 상태에서 KEEP sufficiency를 먼저 판단"하는
             이상적 순서는 이 사건에서 성립하지 않는다
기록값       observation_order = KEEP_THEN_DROP_WITH_PRIOR_COMBINED_EXPOSURE
```

새 판정 범주를 만들지 않았고(사전등록 §6 어휘 그대로), 오염을 판정으로 흡수하지도
않았다. 이 항목을 근거로 판정을 무효로 볼지는 리뷰어의 판단이다.

또한 프레임에 박힌 자막·타이틀 카드는 **시각 행동의 근거로 쓰지 않았다**(§4 규칙 5).
Q2의 `감자 껍질 자동 분리 시스템` 문구는 판정에 넣지 않았다.

## 1. Q1 — P2 448–464초

질문: garment/pajama sequence가 계속되는가, food-on-plate로 전환되는가?

```
KEEP-only 관찰 (448 · 452 · 456 · 460)
  448  작업대 앞에서 주황빛 천/의류를 양손으로 든 상태
  452  거의 검은 화면 + 손 + "Another day" 타이틀 카드 → 장면 전환 지점
  456  접시 위 빵가루 입힌 덩어리 1개를 숟가락으로 들어올림 (음식)
  460  도마 위 토마토를 칼로 자름 (음식 준비)
  → KEEP만으로 "의류 작업 종료 → 전환 → 음식 장면"이 식별된다.
     456·460에 의류는 없다
DROP 추가 관찰 (450 · 454 · 458 · 462)
  450  448과 같은 의류 취급
  454  트레이 위 빵가루 덩어리 6개
  458  트레이 위 덩어리 2개 근접
  462  반으로 자른 토마토
  → 음식 장면을 촘촘하게 만들 뿐, KEEP에 없던 report-material 사건은 없다
```

```
원인 판정   GENERATION_ERROR_NOT_SAMPLING
claim       S0_CLAIM_MATCHES
            S0: 437–453 holding fabric → 453–464 placing food on a plate  (일치)
            S1: 448–456 hanging pajama pants → 456–464 holding pajama pants (불일치)
근거 시각    452(전환 카드) · 456(접시 위 음식) · 460(토마토 절단) — 모두 KEEP
서술         CLEAR
```

S1은 456·460을 **입력으로 받았는데도** 의류를 계속 보고했다. 즉 이 divergence는
표집 손실이 아니라 생성·표현 쪽에서 설명된다.

## 2. Q2 — P3 104–128초

질문: potato peeling인가, potato ricer/pressing/mixing인가?

```
KEEP-only 관찰 (104 · 108 · 112 · 116 · 120 · 124)
  104·108·112  손에 든 흰색·스테인리스 압출 기구(ricer/press)를 그릇 위에서 사용
  116          기구를 그릇 안쪽으로 눌러 내림
  120          기구에서 국수 모양으로 눌린 감자가 초록 그릇으로 떨어짐
  124          그릇에 눌린 감자가 큰 더미로 쌓임
  → KEEP만으로 "칼·필러로 깎는 동작이 아니라 기구로 눌러 압출한다"가 식별된다.
     칼·필러는 어느 KEEP 프레임에도 없다
DROP 추가 관찰 (106 · 110 · 114 · 118 · 122 · 126)
  106  감자를 든 상태 + 기구
  110  압출 가닥이 떨어짐
  114  기구를 벌려 내부에 남은 감자 덩어리가 보임
  118·122·126  압출·더미 축적 반복
  → 기구 내부(114)가 새로 보이지만, 판별 대상인 "깎기 vs 누르기"는 KEEP에서 이미 결정된다
```

```
원인 판정   GENERATION_ERROR_NOT_SAMPLING
claim       S1_CLAIM_MATCHES
            S1: 104–112 using potato ricer · 112–120 pressing potato ricer  (일치)
                120–128 mixing potato mixture                              (미확인)
            S0: 104–128 peeling potato — 보이는 동작은 압출이고 깎기가 아니다   (불일치)
근거 시각    112·116(누름) · 120(압출된 감자 낙하) — 모두 KEEP
서술         원인 판정 CLEAR · claim correspondence BORDERLINE
             (S1의 120–128 `mixing`은 KEEP에서 확인되지 않고, `peeling`이라는 낱말이
              기구의 기능을 가리키는 서술로 읽힐 여지가 남는다)
```

## 3. Q3 — P3 128–144초

질문: forming potato balls인가, gloves/mixing sequence인가?

```
KEEP-only 관찰 (128 · 132 · 136 · 140)
  128  검은 장갑을 낀 손, 그릇에 눌린 감자 더미
  132  장갑 손이 나무 주걱으로 그릇 안을 섞음 (혼합 확인)
  136  장갑 손을 그릇 위로 들어 무언가를 뭉치는 동작 — 덩어리 형태는 불분명
  140  장갑 손이 그릇 가장자리, 오른쪽에 흰 접시가 보임
  → KEEP만으로는 "혼합"까지 확인되고, **완성된 덩어리(ball)는 확인되지 않는다**
DROP 추가 관찰 (130 · 134 · 138 · 142)
  130  주걱으로 혼합 (KEEP과 동류)
  134  장갑 손이 그릇 위
  138  **장갑 손이 뭉친 덩어리 1개를 그릇 위로 들어올림 — 공 형태가 명확**
  142  **흰 접시에 완성된 덩어리 3개 + 손이 네 번째를 놓는 중**
  → KEEP에 없던 report-material 사건(성형 완료·접시 배치)이 DROP에서 처음 드러난다
```

```
원인 판정   DROP_FRAMES_CARRY_MATERIAL_INFORMATION
claim       S0_CLAIM_MATCHES
            S0: 128–136 mixing · 136–144 forming potato balls  (일치)
            S1: 128–136 wearing gloves · 136–144 mixing potato mixture
                — 장갑·혼합은 사실이지만 성형 사건을 누락한다
근거 시각    138(들어올린 덩어리) · 142(접시 위 완성 3개) — 둘 다 **DROP 전용**
서술         DROP 정보 추가는 CLEAR · 136 KEEP의 뭉치는 동작 해석은 BORDERLINE
```

## 4. 사건 판정

```
① FRAMES_INSUFFICIENT     0건        → 발동하지 않음
② DROP material           Q3 1건     → SAMPLING_LOSS_CONFIRMED
③ GENERATION_ERROR        Q1·Q2 2건  → ②에 우선순위가 밀린다(기록만)
```

사전등록 §6 우선순위를 그대로 적용했고, 결과를 본 뒤 순서를 바꾸지 않았다.

## 5. 이 판정이 의미하는 것과 의미하지 않는 것

의미하는 것:

```
Q3(P3 128–144)에서 0.5fps에만 있는 프레임이 report-material 사건(성형 완료·접시 배치)을
  실제로 추가했다 — 138초·142초
Q1·Q2에서는 KEEP 프레임만으로 판별 정보가 보였고, 두 arm의 불일치는
  한쪽 출력이 자기 입력 프레임과 맞지 않는 쪽으로 설명된다
따라서 divergence의 원인은 하나가 아니다 — 같은 영상 56초 안에
  표집 손실 1건과 생성·표현 오류 2건이 함께 나타났다
```

의미하지 않는 것:

```
`0.25fps universally sufficient`         금지 — Q1·Q2가 KEEP 충분이어도 그렇게 쓰지 않는다
`0.25fps는 쓸 수 없다`                    금지 — 확인된 손실은 Q3 구간 1건이다
`0.5fps가 truth`                         아니다. Q1·Q2에서 S0·S1이 각각 프레임과 어긋났다
0.25fps semantic sufficiency 판정         여전히 NOT ESTABLISHED
전체 영상·다른 구간·파이프라인 일반화        범위 밖 (영상 1편 · 3구간 56초 · KEEP 14·DROP 14)
원본 해상도에서만 보이는 세부              이 사건이 보지 않았다(512×288 고정)
```

## 6. provenance

```
prereg commit        2c98977   (판정 전 freeze)
packet commit        032a91b   (프레임 28장 + 대지 3장 + manifest)
관찰 도구 commit      937405c   (KEEP/DROP 분리 대지 · 판정 기록기 — 관찰 전 커밋)
결과 파일            runs/wvr_light_v1/frame_adjudication_verdicts.json
프레임 검증           28/28 sha256 일치 · KEEP ⊆ S1 입력 · DROP ⊆ S0−S1 · 512×288 6/6
                     manifest video sha256 ea0e9f48… (V2·SHORT_WINDOW과 동일 파일)
테스트               tests/test_wvr_frame_adjudication.py WVR-F01~F23 23/23
뮤테이션              M1~M17 전부 RED (구멍 없음)
관찰 순서             KEEP_THEN_DROP_WITH_PRIOR_COMBINED_EXPOSURE (§0에 공개)
```

## 7. 상태

```
FRAME_ADJUDICATION_V1            CLOSED / SAMPLING_LOSS_CONFIRMED
0.25fps semantic sufficiency     NOT ESTABLISHED
0.5fps                           higher-density reference · factual authority 아님
long-context-only-collapse 가설   NOT SUPPORTED (SHORT_WINDOW_V1에서 확정)
WVR event extraction             HOLD (chapter·highlight·overview·analysis·conclusion 포함)
현행 제출본 R1-VAD0-QUALITY        READ-ONLY / NO PROMOTION
official test                    UNOPENED        M9  HOLD
```

다음 architecture 방향은 이 결과를 보고 **리뷰어가 결정한다.** 이 사건은 여기서 멈춘다.

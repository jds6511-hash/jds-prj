# WVR_SAMPLING_SEMANTIC_DENSITY_SHORT_WINDOW_V1 실행 기록 (2026-09-09)

사전등록: `docs/preregistration/WVR_SHORT_WINDOW_V1_2026-09-09.md`
(commit `db24136` — 실행 전 freeze) · 실행 commit `db2413658668` · 서버 RTX 4090

```
실행        6/6 완료 (P1·P2·P3 × S0·S1) · 창×arm마다 fresh process 1회
기술 게이트  6/6 통과 — 파싱 OK · 절단 0 · English-only 만족 · 표현 비축퇴 ·
                     runtime failure 0
사건 판정    CLOSED / SHORT_WINDOW_PAIRED_STABILITY_HOLD
             P1 GRANULARITY_SHIFT · P2 MATERIAL_DIVERGENCE · P3 MATERIAL_DIVERGENCE
             (리뷰어가 packet 내용만 보고 판정 · 2026-09-09)
long-context-only-collapse 가설   NOT SUPPORTED
0.25fps semantic sufficiency       NOT ESTABLISHED
```

**48초로 줄여도 report-material divergence가 P2·P3에서 남았다.** 즉 180초
long-context representation collapse만이 원인이었다는 가설은 지지되지 않는다.
동시에 `0.25fps is worse`도 결론이 아니다 — 어느 arm이 프레임 실물과 맞는지는
아직 판정되지 않았다.

## 1. 창 파생 (사전등록 §3 그대로 재현)

```
입력   evidence_resolution_v1.json에서 REVIEWER_NAMED ∧ NEITHER_RESOLVED
       D1 380–390 · 420–450 · 450–460
       D2 104–112 · 112–120 · 128–136 · 136–144 · 144–152
cluster  C1 D1 380–390 (10초) · C2 D1 420–460 (40초) · C3 D2 104–152 (48초)
창       P1 360–408 · P2 416–464 · P3 104–152   (48초 · [start, end) · 4초 grid)
```

파생 함수의 출력이 `EXPECTED_WINDOWS`와 일치했다(`assert_expected` 통과). 서버에서도
같은 값을 재확인한 뒤 실행했다.

## 2. 단일 변경 확인

```
변경    context_length_sec  180.0 → 48.0
동결    6개 arm 전부 single_change == true
        (model·revision·dtype bf16·quantization None·attn sdpa·512×288·
         greedy·num_beams 1·repetition_penalty 1.0·do_sample_frames False·
         do_resize False·max_new_tokens 4096·프롬프트 해시 37f9588e…·English-only)
프레임  S0 24프레임(2초 간격) · S1 12프레임(4초 간격 · S0의 exact KEEP 부분집합)
토큰    input 2,153(S0) · 1,229(S1) — 창·arm 3쌍 모두 동일값
```

생성 토큰은 6개 arm 모두 상한 4,096에 도달하지 않았다(절단 0건). arm별 값은 §0의
이유로 판정 후에 기록한다.

## 3. 판정 절차 (진행 중)

```
packet      runs/wvr_light_v1/short_window_packet.md      ← 리뷰어에게 제출 (blinded)
별도 파일   runs/wvr_light_v1/short_window_blind_map.json  (salt·A/B mapping)
            runs/wvr_light_v1/short_window_audit.json      (자동 matcher 진단)
판정 입력   scripts/wvr_short_window_packet.py --reveal P1=…,P2=…,P3=…
            → short_window_verdicts.json 생성 + mapping 공개
```

자동 matcher는 `AUDIT_DIAGNOSTIC_ONLY`다 — V2에서 exact-string matcher가 표현 차이를
처리하지 못한다는 것이 확인됐으므로 primary 판정에 쓰지 않는다.

### 잔존 blinding 누출 — 공개

```
① 사건 개수·서술 granularity 자체가 통계적 단서가 될 수 있다 (사전등록 §5-1에 기재)
② actor 표기 습관이 단서가 될 수 있다 — V2 보고서(§4)에 D1에서 "a person"(S0) vs
   "person"(S1)이 기록돼 있고, 이번 packet에도 두 표기가 섞여 있다
```

③ **mapping은 저장소에서 복원 가능하다.** 산출물 파일명이 `..._S0.json`·`..._S1.json`
   이고 provenance 보존을 위해 6건 전부를 커밋했으므로, 파일을 열면 어느 쪽이 0.5fps인지
   바로 보인다. 즉 이번 blinding은 **절차적 blinding**이다 — packet만 읽는다는 규율에
   의존하고, 기술적으로 mapping을 차단하지 않는다. blind_map을 .gitignore로 감추는 것은
   이 사실을 가리는 착시라 하지 않았다.

blinding은 표지를 가리는 장치이고 단서를 없애지 못한다. 위 항목을 알고도 판정할지는
리뷰어의 판단이다.

## 4. 판정 규칙 (동결 · 재확인)

```
창 판정   STABLE · GRANULARITY_SHIFT (= 창 PASS) · MATERIAL_DIVERGENCE · UNRESOLVED
사건 판정 ① 기술 무효 → INCONCLUSIVE  (이번 실행에서는 해당 없음)
          ② MATERIAL_DIVERGENCE 하나라도 → SHORT_WINDOW_PAIRED_STABILITY_HOLD
          ③ UNRESOLVED 하나라도 → INCONCLUSIVE
          ④ 세 창 모두 PASS → C01_SHORT_WINDOW_PAIRED_STABILITY_PASS
```

PASS가 나와도 허용되는 결론은 하나뿐이다.

```
C01에서 180초 probe가 보여준 report-material divergence는 48초 conflict-focused
window에서는 재현되지 않았고, 0.25fps 출력은 0.5fps higher-density reference에
대해 report-materially stable했다.
```

`0.25fps is universally semantically sufficient`는 금지다.

## 5. 검증

```
테스트    tests/test_wvr_short_window.py  WVR-S01~S30  30/30 통과
뮤테이션  N1~N24 전부 RED (구멍 없음)
          packet 누출 뮤테이션 2건(N19 프레임 수 노출 · N20 arm 이름 노출)은
          산출물이 있어야 검증되므로 실행 후 재검증했다
```

## 6. 상태

```
SHORT_WINDOW_V1                   EXECUTED / ADJUDICATION_PENDING
WVR_EVIDENCE_RESOLUTION_V1        CLOSED / BRANCH_C_EVIDENCE_INCONCLUSIVE
density V2                        CLOSED / PAIRED_OUTPUT_STABILITY_HOLD
0.25fps semantic sufficiency      NOT ESTABLISHED   ·  0.5fps authority  NO
WVR event extraction              HOLD   ·  프레임 실물 열람  미승인
현행 제출본                         READ-ONLY / NO PROMOTION
official test  UNOPENED     M9  HOLD
```

## 7. 산출물

```
runs/wvr_light_v1/short_window_P{1,2,3}_S{0,1}.json   6건
runs/wvr_light_v1/short_window_packet.md              blinded packet
runs/wvr_light_v1/short_window.log
src/wvr_short_window.py · scripts/wvr_short_window_run.py
scripts/wvr_short_window_packet.py · scripts/wvr_short_window_batch.sh
tests/test_wvr_short_window.py
```

## 8. 판정 결과와 blind mapping (판정 후 공개)

```
창   판정                  창 PASS   Arm A    Arm B
P1   GRANULARITY_SHIFT     True      S1       S0
P2   MATERIAL_DIVERGENCE   False     S1       S0
P3   MATERIAL_DIVERGENCE   False     S0       S1
사건 판정  SHORT_WINDOW_PAIRED_STABILITY_HOLD
           (사전등록 §5-3 ②: MATERIAL_DIVERGENCE 하나라도 있으면 HOLD ·
            기술 무효 0건이므로 ①은 발동하지 않았다)
근거 파일  runs/wvr_light_v1/short_window_verdicts.json
```

리뷰어 판정 요지(원문 기준):

```
P1  두 arm 모두 sushi/food handling → chicken 관련 → cloth/garment holding으로
    이어지고, 한쪽이 soup·noodles·chicken placement를 더 세분했다.
    underwear ↔ orange/pink cloth도 모순으로 단정할 정도는 아니다 → granularity
P2  416–453초는 사실상 같은 chain인데 마지막 구간에서 한쪽은 pajama pants holding,
    다른 쪽은 food를 plate에 placing으로 바뀐다 → 흡수 불가
P3  104–128초가 potato peeling ↔ potato ricer 사용·pressing·mixing으로 갈리고,
    이후 forming potato balls ↔ wearing gloves·mixing이 같은 시간대에 대응한다
    → 관찰된 action sequence 자체가 다르다
```

## 9. arm별 수치 (판정 후 공개)

```
창 arm  프레임  input tok  gen tok  raw  collapsed  unique sig  peak VRAM   wall
P1 S0     24      2,153      462     10      9          9      17,390.7   26.0초
P1 S1     12      1,229      278      6      5          5      17,105.4   18.3초
P2 S0     24      2,153      592     12      7          6      17,390.7   31.1초
P2 S1     12      1,229      297      6      6          4      17,105.4   19.1초
P3 S0     24      2,153      273      6      4          4      17,390.7   20.1초
P3 S1     12      1,229      276      6      6          5      17,105.4   18.3초
```

생성 토큰 상한 4,096에 도달한 arm은 없다(최대 592).

**divergence의 방향은 대칭이 아니다.** P2에서 마지막 구간을 `food on a plate`로
바꾼 쪽은 프레임이 더 많은 S0이고, P3에서 104–128초를 `peeling potato` 한 구간으로
묶은 쪽도 S0다. 즉 이번 두 창에서 **고밀도 arm의 출력이 저밀도 arm의 상위집합이
아니었다.** 어느 쪽이 프레임 실물과 맞는지는 이 사건이 답하지 않는다.

## 10. 자동 matcher (AUDIT_DIAGNOSTIC_ONLY · 판정에 쓰지 않았다)

허용오차 4.0초 기준.

```
창   시간정렬 후보  EQUIVALENT  ADJUDICATION  DIFFERENT  merge  split  순서뒤집힘
P1        19            0            19          0        0      0        0
P2        18            0            18          0        0      0        0
P3        12            2            10          0        0      1        0
```

허용오차 8.0초에서도 EQUIVALENT는 0·0·2로 같았다(후보만 24·23·17로 늘었다).
**V2에서 관측된 한계가 그대로 재현됐다** — exact-string matcher는 48초 창에서도
표현 차이를 흡수하지 못한다. 사람 판정을 primary로 둔 사전등록 결정이 이 수치로
정당화된다(자동 판정이었다면 P2·P3의 material divergence를 잡지 못했다).

## 11. 다음 사건 (리뷰어 승인)

```
WVR_SAMPLING_SEMANTIC_DENSITY_FRAME_ADJUDICATION_V1   NEXT / APPROVED FOR PREREG
대상   P2 448–464 · P3 104–128 · P3 128–144  (material divergence 구간만)
방법   S0·S1 공통 KEEP 프레임 + S0에만 있는 DROP 프레임을 직접 본다
금지   prompt · matcher · repetition penalty · context length 재조정
```

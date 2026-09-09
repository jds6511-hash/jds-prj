# WVR_SAMPLING_SEMANTIC_DENSITY_SHORT_WINDOW_V1 실행 기록 (2026-09-09)

사전등록: `docs/preregistration/WVR_SHORT_WINDOW_V1_2026-09-09.md`
(commit `db24136` — 실행 전 freeze) · 실행 commit `db2413658668` · 서버 RTX 4090

```
실행        6/6 완료 (P1·P2·P3 × S0·S1) · 창×arm마다 fresh process 1회
기술 게이트  6/6 통과 — 파싱 OK · 절단 0 · English-only 만족 · 표현 비축퇴 ·
                     runtime failure 0
사건 판정    미정 — blinded adjudication 대기 (Claude는 판정하지 않는다)
```

**이 문서는 판정 전에 쓰였으므로 arm별 내용·생성 토큰 수를 싣지 않는다.**
그 수치는 packet의 Arm A/B와 사건 순서로 대조하면 density mapping을 드러낸다.

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

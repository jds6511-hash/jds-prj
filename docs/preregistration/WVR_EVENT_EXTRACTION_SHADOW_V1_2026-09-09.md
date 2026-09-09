# WVR_EVENT_EXTRACTION_SHADOW_V1 사전등록 (2026-09-09)

승인: 리뷰어 결정 — `APPROVED / PREREG → COMMIT → EXECUTION`.
**이 문서는 GPU 실행 전에 커밋한다. 결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

## 0. normative authority 우선순위 (리뷰어 확정)

```
① WVR_EVENT_EXTRACTION_SHADOW_V1 preregistration (이 문서)
② frozen prompt/schema/runtime hash
③ execution artifacts / raw results
④ PROJECT_OVERVIEW.md — 지도이지 실험 계약서가 아니다
```

`PROJECT_OVERVIEW.md`와 frozen prompt가 충돌하면 이 사건에서는 ①②가 우선한다.

## 1. 질문 두 개 — 섞지 않는다

```
A. overlap/context stability
   48초 local context에서 만든 Local Event representation이, 같은 실제 24초 구간을
   서로 다른 인접 context에서 다시 봤을 때 report-material하게 일관되는가?
B. frame-grounded event validity
   Qwen이 낸 Local Event가 모델이 실제로 본 512×288 sampled frame과 시각적으로
   양립하는가?
```

Overview 품질 실험이 아니다. Event Map production 실험도 아니다.

## 2. 이 사건의 성격 (리뷰어 정정)

```
Inference configuration change      NONE (SHORT_WINDOW_V1 S0 대비)
Architecture under characterization 결정적 48초 / 24초 overlap tiling of C01
New measurement instrumentation     overlap 비교 + 사전등록 7 overlap frame audit
```

`single_change = true`를 주장하지 않는다 — 인과효과 하나를 재는 ablation이 아니라
**architecture shadow characterization**이다. overlap packet·blinding·frame audit은
inference 변수가 아니라 measurement instrumentation이다.

## 3. 선행 상태 (전제 · 이 사건이 바꾸지 않는다)

```
SHORT_WINDOW_V1            CLOSED / SHORT_WINDOW_PAIRED_STABILITY_HOLD
FRAME_ADJUDICATION_V1      CLOSED / SAMPLING_LOSS_CONFIRMED
  Q1 GENERATION_ERROR_NOT_SAMPLING · Q2 GENERATION_ERROR_NOT_SAMPLING
  Q3 DROP_FRAMES_CARRY_MATERIAL_INFORMATION
0.25fps semantic sufficiency   NOT ESTABLISHED
0.5fps                         higher-density reference · factual authority 아님
                               이 사건에서는 provisional working density로만 쓴다
48초                           technically executable / technically valid
                               diagnostic window length —
                               semantic stability는 NOT validated (SHORT_WINDOW HOLD)
Track A canonical evidence     downstream auxiliary claim-verification layer ·
                               discriminative coverage LIMITED (실측) ·
                               지지도 반증도 못 하면 UNRESOLVED 유지
production Event extraction    HOLD · Chapter·Highlight·Overview·Analysis·
                               Conclusion HOLD
현행 제출본                      READ-ONLY / NO PROMOTION
official test UNOPENED         M9 HOLD
```

`FRAME_ADJUDICATION_V1`의 prior combined-sheet exposure는 procedural limitation으로
기록됐고 리뷰어가 사건 무효 사유로 쓰지 않았다.

## 4. 동결 — 모델·runtime (SHORT_WINDOW_V1 S0와 동일)

```
model_id            Qwen/Qwen3-VL-8B-Instruct
model_revision      0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
dtype               bfloat16      quantization  None
attn_implementation sdpa          device_map    None
allocator           default (PYTORCH_CUDA_ALLOC_CONF 주입 없음)
해상도               512×288 · do_resize False · do_sample_frames False
생성                 greedy · num_beams 1 · max_new_tokens 4096 ·
                    repetition_penalty 1.0
process             창 하나당 fresh process 1회 · runtime retry 없음
입력                 video-only — 자막·캡션·canonical evidence·과거 arm 텍스트·
                    사람 판정을 입력으로 넣지 않는다
```

실행기는 매 창마다 `inference_config_change()`로 대조하고 `NONE`이 아니면
**GPU를 쓰기 전에 중단**한다(WVR-H12·H24).

## 5. 동결 — prompt·schema

```
prompt   SAMPLING_DIAG_PROMPT_V2 (변경 금지)
hash     37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273
schema   events[{start_sec, end_sec, actor, action, object_or_state}]
언어      English-only diagnostic 유지
규칙      observable visual content only · persistent action/state interval merge ·
         non-consecutive reappearance 보존
파서      기존 v2 parser + consecutive run-collapse 그대로
```

**`support_frame_times`는 이번 사건의 schema가 아니다**(리뷰어 확정). 넣으면 prompt·
schema 변경이 되므로 후속 변형 후보로만 남긴다. controlled vocabulary·stopword
normalization·repetition penalty 변경·새 semantic matcher도 넣지 않는다.

## 6. 창 일정 (결과 보기 전 동결)

```
범위      [0, 600)           반열린 구간
length    48초   stride 24초   overlap 24초
sampling  0.5fps · 창당 24프레임 (start, start+2, … , start+46)
창 수      24     추론 24회 (창당 1회)
start     0 24 48 72 96 120 144 168 192 216 240 264
          288 312 336 360 384 408 432 456 480 504 528 552
마지막 창   [552, 600)  → 600초를 빈틈없이 덮는다
```

## 7. 겹침 불변식

인접 창 쌍 23개. 각 겹침에서 다음을 검증한다.

```
shared timestamp count = 12
shared timestamps exact match (양쪽 격자의 교집합)
shared frame의 model-input 픽셀 sha256 exact match
```

같은 시각의 공유 프레임이 두 창에서 픽셀 수준으로 다르면 그 쌍은 **semantic 비교
대상으로 쓰지 않고 기술적으로 INVALID**로 처리한다. tolerance로 살리지 않고 숨기지
않는다(WVR-H10·H11).

## 8. raw-before-parse

```
raw model output → 파일로 persist → parse → collapse
```

정리 전에 원문을 먼저 남긴다(WVR-H22). 창별 provenance에 남기는 것:

```
window_id · start_sec · end_sec · sampling fps · frame timestamps · frame hashes
video sha256 · model revision · prompt hash · runtime config hash
input token count · generated token count · finish reason · generation_cap_hit
raw output hash · parsed output hash · collapse output hash
```

## 9. 기술 검증 게이트 (창 단위)

```
process completed · no OOM · no runtime failure · raw persisted
JSON parse OK · schema valid · English-only 만족 · generation cap 미도달
representation degeneracy 없음 · frame count 24 · 0.5fps 격자 정확
video provenance 동일
```

기존 V2/SHORT_WINDOW의 validity 논리를 그대로 쓰고 창 고유 검사만 더한다.
**invalid 창은 결과를 본 뒤 재실행해 살리지 않는다** — INVALID provenance로 남긴다.

technical invalidity가 semantic reviewer gate에 미치는 방식(미리 명시):

```
필수 창이 invalid이거나 공유 프레임 identity가 깨지면 → 사건 판정 INCONCLUSIVE
그 경우 23 overlap semantic 판정을 사건 결론으로 승격하지 않는다
```

## 10. overlap 비교 packet

23개 겹침마다 인접 두 창의 collapsed event 중 겹침과 교차하는 것을 뽑는다.
경계를 넘는 event는 **결정적으로 clip**하되 원본을 보존한다.

```
original_event_id · original_start · original_end · clipped_start · clipped_end
```

원본 event를 수정하지 않는다(WVR-H17). packet에 싣는 것은 다음뿐이다.

```
overlap id · overlap 절대 시간 범위
Arm A: clipped collapsed event sequence
Arm B: clipped collapsed event sequence
```

## 11. blinding

```
규칙      earlier/later → Arm A/B 배정은 prereg commit SHA와 overlap id의
         결정적 함수 (sha256 첫 바이트 parity) — 사람이 결과를 보고 고르지 않는다
고정      실행 후 배정 변경 불가 (같은 입력 → 같은 출력)
packet    mapping 미표시 · reviewer 판정 확정 전 reveal 금지
mapping   별도 artifact(shadow_v1_blind_map.json)에 실제 source 창 기록
```

**저장소에서 mapping을 완전히 숨길 수 없다** — 산출물 파일명이 창 id를 담는다.
따라서 이것은 **procedural blinding**이며, packet만 읽는다는 규율에 의존한다.
보호 장치처럼 과장하지 않는다.

## 12. 자동 matcher의 역할

4초 primary / 8초 sensitivity 시간 매처를 기록하되 `AUDIT_DIAGNOSTIC_ONLY`로 표시한다.

```
semantic equivalence authority 아님 · materiality authority 아님
PASS/HOLD 계산 authority 아님
```

lexical mismatch를 새 normalization으로 고치지 않는다.

## 13. reviewer 판정 어휘 (executor가 채우지 않는다)

overlap 판정(4값): `STABLE` · `GRANULARITY_SHIFT` · `MATERIAL_DIVERGENCE` ·
`UNRESOLVED`.
frame-grounding 판정(4값): `SUPPORTED` · `PARTIALLY_SUPPORTED` · `UNSUPPORTED` ·
`FRAMES_INSUFFICIENT`.

executor는 기술 게이트까지만 자동 계산하고 `semantic_verdict = null`로 남긴다
(WVR-H16·H31).

## 14. frame bank와 사전등록 frame audit

```
bank      0, 2, … , 598초 · 300프레임 · 512×288 · 픽셀 sha256 전량 기록
identity  창 추론이 실제로 먹인 픽셀 해시와 대조한다 (불일치는 그대로 기록)
PNG 정책   사전등록 7 overlap의 공유 프레임 84장만 PNG로 저장한다.
          300장 전량 PNG는 저장소 크기 때문에 남기지 않는다(사전 명시).
          해시는 300장 전량 남기므로 재생성·검증이 가능하다
경로       inference 입력 경로를 바꾸지 않는다 — bank는 reviewer audit 전용이다
```

audit overlap 7개(결과 보고 고르지 않는다 · 확장 금지):

```
stress   O04 [96,120)  O05 [120,144)  O18 [432,456)  O19 [456,480)
control  O01 [24,48)   O12 [288,312)  O23 [552,576)
```

stress set은 과거 Q1~Q3 시간대를 결정적으로 포함시키기 위한 것이고, **과거 판정을
이번 출력의 정답 label로 쓰지 않는다.** 과거 S0/S1 텍스트·canonical evidence·사람
판정을 프롬프트에 넣지 않는다.

각 audit overlap packet: 공유 12프레임 대지 1장 + 개별 PNG + 절대 시각 + sha256 +
blinded Arm A/B clipped event sequence. 판정은 reviewer가 한다.

## 15. shadow acceptance gate (동결)

```
Technical INCONCLUSIVE
  필수 창 technical invalid · 공유 프레임 identity 실패 · 절단 ·
  언어 계약 실패 · representation degeneracy · packet provenance 실패
  → INCONCLUSIVE (결과를 본 뒤 재시도하지 않는다)

Semantic HOLD
  reviewer 판정에서 overlap 중 하나라도 MATERIAL_DIVERGENCE → HOLD

Semantic INCONCLUSIVE
  report-material UNRESOLVED가 하나라도 남으면 → INCONCLUSIVE

Shadow PASS 후보
  23 overlap 전부 STABLE 또는 GRANULARITY_SHIFT이고 material unresolved 없음
  단, 7개 frame-audit overlap에서 report-material event가 sampled pixels와
  명백히 충돌하면 PASS로 승격하지 않는다
    UNSUPPORTED material event → HOLD
    PARTIALLY_SUPPORTED 또는 FRAMES_INSUFFICIENT material item 잔존 → INCONCLUSIVE
```

최종 PASS/HOLD/INCONCLUSIVE는 **reviewer가 계산한다.**

## 16. gate 범위와 PASS 시 허용 결론 (리뷰어 정정)

```
Overlap stability   23/23 adjacent overlaps
Frame grounding      7/23 preregistered audit overlaps only
```

PASS 시 허용되는 최대 결론:

```
Within C01:
 (1) all 23 adjacent overlaps passed the report-material overlap-stability gate, and
 (2) the 7 preregistered frame-audit overlaps contained no disqualifying
     frame-grounding failure.
```

금지되는 주장:

```
all C01 events are frame-grounded · entire Event Map factuality verified
0.5fps universally sufficient · 0.5fps factual authority
production Event extraction approved · whole-video understanding solved
Overview quality proven · report factuality proven
```

## 17. 금지 사항

```
prompt·schema·runtime·창 일정 변경 (결과를 본 뒤 특히)
support_frame_times 추가 · controlled vocabulary · 새 matcher · normalization
frame audit overlap 추가·교체 (7개 고정)
실패 창 즉석 retry · silent fallback
event sequence를 단순 concat해 Event Map이라 부르는 것 (silent concat fallback 금지)
stitching production · Chapter · Highlight · Overview · Analysis · Conclusion · HWPX
executor의 semantic·materiality 판정 · mapping 조기 reveal
현행 제출본 수정·승격 · official test 접촉 · M9 실행
V1/V1B/V2/SHORT_WINDOW/EVIDENCE/FRAME_ADJUDICATION 산출물 수정
```

## 18. 테스트 (WVR-H01~H33)

```
창 일정   H01 사전등록 커밋 · H02 24창 · H03 첫·끝 창 · H04 stride·overlap ·
         H05 24프레임 half-open · H06 일정 밖 거부
겹침      H07 23쌍 · H08 공유 12개 · H09 audit 7개 동결·확장 금지 ·
         H10 identity 실패 → INCONCLUSIVE · H11 픽셀 해시 대조
동결      H12 inference 변경 NONE·drift 감지 · H13 프롬프트·schema·
         support_frame_times 부재 · H14 SHORT_WINDOW 기하 일치 ·
         H15 video-only 강제 · H16 executor 권한 선언
clip·blind H17 원본 불변 · H18 범위 밖 제외 · H19 A/B 상보·재현·SHA 의존 ·
         H20 packet 누출 금지 · H21 matcher audit-only
실행기    H22 raw persist 우선 · H23 창 1회 · H24 drift 거부 · H25 재시도 없음 ·
         H26 프레임·격자·provenance 결함 감지
경계      H27 frame bank 범위·audit 시각 · H28 frame 도구 추론 금지 ·
         H29 현행 제출본 해시 불변 · H30 test split 미접촉
실행 후   H31 기술 게이트만·semantic null · H32 창 기하 유지 ·
         H33 23겹침 공유 12/12
```

뮤테이션으로 각 invariant가 실제로 깨지면 RED가 되는지 확인하고 구멍은 결과에 적는다.

## 19. 실행 순서

```
사전등록 → prereg commit → 구현·테스트 commit → validator →
GPU 실행(24창) → raw persist → parse/collapse → provenance 검증 →
overlap packet → frame-audit packet → matcher audit →
full tests/mutations → clean tree → 결과 commit → STOP
```

사전등록 커밋 전에 새 Qwen 추론을 실행하지 않는다.

## 20. 산출물

```
runs/wvr_light_v1/shadow_v1_W{00..23}.json          창별 record (provenance·해시)
runs/wvr_light_v1/shadow_v1_W{00..23}_raw.txt       raw 원문 (파싱 전에 저장)
runs/wvr_light_v1/shadow_v1_summary.json            창 표 · 겹침 identity · 기술 게이트
runs/wvr_light_v1/shadow_v1_overlap_packet.md       blinded 23 overlap packet
runs/wvr_light_v1/shadow_v1_blind_map.json          mapping (판정 전 열람 금지)
runs/wvr_light_v1/shadow_v1_matcher_audit.json      AUDIT_DIAGNOSTIC_ONLY
runs/wvr_light_v1/shadow_frame_bank.json            300프레임 해시·provenance
runs/wvr_light_v1/shadow_frame_audit.json           7 overlap audit 명세
runs/wvr_light_v1/frames_shadow/                    공유 프레임 84장 + 대지 7장
src/wvr_shadow_v1.py · scripts/wvr_shadow_run.py ·
scripts/wvr_shadow_frames.py · scripts/wvr_shadow_packets.py ·
scripts/wvr_shadow_batch.sh · tests/test_wvr_shadow_v1.py
```

기존 사건 산출물과 현행 제출본은 변경하지 않는다.

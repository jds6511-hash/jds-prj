# WVR_SAMPLING_SEMANTIC_DENSITY_SHORT_WINDOW_V1 사전등록 (2026-09-09)

승인: 리뷰어 결정 — `APPROVED / PREREG → COMMIT → EXECUTION`.
**이 문서는 실행 전에 커밋한다. 결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

## 0. 이 사건이 답하는 질문 하나

```
V2의 report-material divergence가 180초 long-context representation collapse 때문에
생긴 것인지, 짧은 동일 window에서도 0.5fps ↔ 0.25fps 차이가 유지되는지.
```

새 factuality probe가 아니다. **프레임 실물은 아직 보지 않는다.**
답하지 않는 질문: 어느 arm이 사실인가 · 0.25fps가 보편적으로 충분한가.

## 1. 선행 상태

```
WVR_EVIDENCE_RESOLUTION_V1   CLOSED / BRANCH_C_EVIDENCE_INCONCLUSIVE
  채택 evidence 층은 지목 9행 중 8행을 갈라주지 못했다
  subtitle(독립 modality) 해결 0건 · caption도 다른 VLM 출력이라 authority 아님
WVR_SAMPLING_SEMANTIC_DENSITY_V2   CLOSED / PAIRED_OUTPUT_STABILITY_HOLD
0.25fps semantic sufficiency   NOT ESTABLISHED   ·  0.5fps factual authority  NO
event extraction HOLD  ·  현행 제출본 READ-ONLY  ·  official test UNOPENED  ·  M9 HOLD
```

## 2. 유일한 변경 — context 길이

```
변경   context 180초 → 48초  (축 이름 context_length_sec)
동결   model_id Qwen/Qwen3-VL-8B-Instruct · revision 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
       dtype bfloat16 · quantization None · attn sdpa · device_map None
       해상도 512×288 · do_sample False · num_beams 1 · repetition_penalty 1.0
       do_sample_frames False · do_resize False · max_new_tokens 4096
       프롬프트 SAMPLING_DIAG_PROMPT_V2
       hash 37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273
       English-only · parser·collapse 규칙 v2 그대로 · 허용오차 (4.0, 8.0)
       reference_fps 0.5 · density_fps 0.25 · keep_stride 2
```

`src/wvr_short_window.py`의 `FROZEN_FROM_V2`가 이 목록이고, 실행기는 매 arm마다
`single_change()`로 대조해 하나라도 다르면 **GPU를 쓰기 전에 중단**한다(WVR-S03·S26).

## 3. 창 파생 — 사람이 고를 여지가 없다

입력은 Evidence Resolution 산출물(`runs/wvr_light_v1/evidence_resolution_v1.json`)에서
`source`에 `REVIEWER_NAMED`가 있고 `resolution == NEITHER_RESOLVED`인 충돌 구간뿐이다.

```
① 같은 D pair 안에서 gap ≤ 8.0초면 같은 cluster로 병합
② cluster 중심에서 ±24초 → 48초 창
③ start를 4초 grid로 floor snap → end = start + 48
④ 창이 cluster를 못 덮거나 cluster가 48초보다 길면 오류로 중단
```

파생 결과(결과를 보기 전에 기록):

```
미해결 지목 충돌   D1 380–390 · 420–450 · 450–460
                  D2 104–112 · 112–120 · 128–136 · 136–144 · 144–152
cluster           C1 D1 380–390 (10초) · C2 D1 420–460 (40초) · C3 D2 104–152 (48초)
창                P1 360–408 · P2 416–464 · P3 104–152     전부 [start, end) 48초
```

48초는 임의값이 아니라 **가장 긴 cluster(C3)의 길이**다. 세 창을 그 길이로 통일한다.
`EXPECTED_CLUSTERS`·`EXPECTED_WINDOWS`에 위 값을 박아 두고, 파생 함수가 다른 값을
내면 실행이 거부된다(WVR-S08·S09·S12).

## 4. arm

```
S0   0.5fps  · 24프레임 · t = start + 0, 2, … , 46
S1   0.25fps · 12프레임 · t = start + 0, 4, … , 44   (S0의 exact KEEP 부분집합)
총 추론   3창 × 2arm = 6회 · 창×arm마다 fresh process 1회
```

`S1 ⊂ S0`는 `density.assert_contained`로 강제한다(WVR-S14). 모든 프레임은
`[start, end)` 안에 있다(WVR-S15).

## 5. 판정 — 자동 matcher는 authority가 아니다

V2에서 exact-string semantic matcher가 자연어 표현 차이를 처리하지 못한다는 것이
이미 확인됐으므로 같은 일을 반복하지 않는다.

```
자동 4초/8초 matcher   AUDIT_DIAGNOSTIC_ONLY — 별도 파일(short_window_audit.json)에만
primary 판정            세 창의 collapsed event sequence 전체를
                       blinded side-by-side로 사람이 판정한다
```

### 5-1. blinding

Claude는 판정하지 않고 packet만 만든다.

```
packet          runs/wvr_light_v1/short_window_packet.md
                창별로 Arm A / Arm B의 collapsed event sequence만 싣는다
숨김            density mapping(어느 쪽이 0.5fps인지) · salt · 자동 matcher 진단
                → short_window_blind_map.json · short_window_audit.json
                판정이 끝날 때까지 리뷰어에게 보여주지 않는다
A/B 배정        창별로 salt(실행 시 생성한 난수) 기반 → salt 없이는 재현 불가
                packet에는 salt_sha256만 남긴다
금지 필드       fps · frames · delivered_frame_count · input_token_count ·
                generated_token_count · video_token_count · arm 이름
```

**잔존 누출은 인정한다** — event 개수·서술 granularity 자체가 통계적 단서가 될 수
있다. blinding은 표지를 가리는 것이고 단서를 없애는 것이 아니다.

### 5-2. 창 판정값 (네 값만)

```
STABLE                report-material event chain 동일 · wording/무해한 granularity 차이만
GRANULARITY_SHIFT     같은 사건 구조인데 한쪽이 split/merge 또는 더 구체적 ·
                      report-level contradiction 없음
MATERIAL_DIVERGENCE   actor·action·object·state·event-order 중 보고서 내용을 바꿀
                      비호환 차이가 있음
UNRESOLVED            두 텍스트만으로 materiality를 결정할 수 없음
```

`STABLE`·`GRANULARITY_SHIFT` = 창 PASS.

### 5-3. 사건 판정 (우선순위 동결)

```
① 기술적 무효가 하나라도 있으면            INCONCLUSIVE
   (arm invalid — 파싱 실패 · 절단 · English-only 위반 · 표현 축퇴 · runtime failure)
② MATERIAL_DIVERGENCE가 하나라도 있으면    SHORT_WINDOW_PAIRED_STABILITY_HOLD
③ UNRESOLVED가 하나라도 있으면             INCONCLUSIVE
④ 세 창 모두 PASS                          C01_SHORT_WINDOW_PAIRED_STABILITY_PASS
```

①이 ②보다 앞선다 — 계측이 무효인 상태에서 내용 판정을 사건 결론으로 올리지 않기
위함이다. 세 창 전부의 판정이 없으면 사건 판정을 계산하지 않는다(WVR-S21·S22).

## 6. PASS가 의미하는 범위

PASS가 나와도 다음은 **금지**다.

```
0.25fps is universally semantically sufficient
```

허용되는 결론은 이것뿐이다.

```
C01에서 180초 probe가 보여준 report-material divergence는 48초 conflict-focused
window에서는 재현되지 않았고, 0.25fps 출력은 0.5fps higher-density reference에
대해 report-materially stable했다.
```

PASS 시 architecture 함의(리뷰어 결정 · 이 사건에서 실행하지 않는다):

```
10분 capacity PASS를 곧바로 10분·180초 semantic inference 단위로 쓰지 않는다.
Event Map 생성은 짧은 visual window에서 하고 상위 Event·Chapter 단계에서 통합한다.
기존 계약 "chunk boundary ≠ report boundary"와 일치한다.
다음 사건 후보는 EVENT_EXTRACTION_SHADOW_V1 (48초 이하 short-window architecture)이며
production event extraction 개방이 아니다 — 별도 승인 사건이다.
```

HOLD 시(48초에서도 material divergence가 남는 경우): **모델을 다시 튜닝하지 않는다.**
그 시점에만 KEEP/DROP 실제 프레임 visual adjudication을 별도 사건으로 연다.

## 7. 금지 사항

```
V2 동결값 변경(프롬프트·토큰·penalty·해상도·revision·양자화·attn 등)
창 재선택 · cluster 규칙 변경 · grid 변경 · 창 길이 변경
arm 재실행(창×arm은 1회) · 실패한 arm을 같은 사건에서 재시도
자동 matcher 결과를 primary 판정으로 사용
density mapping을 packet에 노출 · 판정 전에 mapping 공개
프레임 실물 열람 (별도 승인 사건)
결과를 본 뒤 §3·§5의 규칙·우선순위·판정 어휘 변경
"0.25fps PASS" 이상의 일반화 · event extraction 개시 · 제출본 승격
official test 접촉 · M9 실행
```

## 8. 테스트 (WVR-S01~S30)

```
동결      S01 사전등록 커밋 · S02 V2 동결값 · S03 drift 감지 · S04 범위 선언 ·
          S05 추론 6회
창 파생   S06 입력 필터 · S07 gap 규칙 · S08 cluster 재현 · S09 창 재현 ·
          S10 grid·포함 · S11 과장 cluster 오류 · S12 사전등록 불일치 거부
프레임    S13 24·12 · S14 exact 부분집합 · S15 half-open · S16 fps 출처 ·
          S17 미지 arm 거부
판정      S18 어휘 4값 · S19 material→HOLD · S20 unresolved→INCONCLUSIVE ·
          S21 기술 무효 우선 · S22 세 창 필수
blinding  S23 A/B 상보·salt 의존 · S24 packet 누출 금지 · S25 mapping 분리
실행기    S26 drift 거부 · S27 arm 1회 · S28 커밋된 evidence 산출물에서 파생
실행 후   S29 arm별 단일 변경·프레임 수 · S30 packet 3창 6arm
```

뮤테이션으로 각 테스트가 실제로 잡는지 확인하고 구멍은 결과 보고에 적는다.

## 9. 산출물

```
runs/wvr_light_v1/short_window_P{1,2,3}_S{0,1}.json    6건 (raw·collapsed·검증 포함)
runs/wvr_light_v1/short_window_packet.md               blinded — 리뷰어에게 제출
runs/wvr_light_v1/short_window_blind_map.json          숨김 (salt·mapping)
runs/wvr_light_v1/short_window_audit.json              숨김 (자동 matcher 진단)
runs/wvr_light_v1/short_window_verdicts.json           판정 입력 후 생성
src/wvr_short_window.py · scripts/wvr_short_window_run.py
scripts/wvr_short_window_packet.py · tests/test_wvr_short_window.py
```

V2·Evidence Resolution 산출물은 변경하지 않는다.

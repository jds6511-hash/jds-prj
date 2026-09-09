# WVR_EVENT_EXTRACTION_W00_DEGENERACY_FORENSIC_V1 사전등록 (2026-09-09)

승인: 리뷰어 결정 — `NEXT / APPROVED · READ-ONLY DIAGNOSTIC · NO NEW QWEN INFERENCE`.
**이 문서는 분석 실행 전에 커밋한다. 결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

## 0. 답할 질문 하나

```
SHADOW_V1의 W00 [0,48) 실패가
  ① 입력 builder / 0초 boundary 특수처리 문제인지,
  ② 시각 내용에 의해 발생한 model generation loop인지,
  ③ 현재 artifact만으로 구분할 수 없는지
를 확인한다.
```

품질 실험이 아니다. 복구 실험도 아니다. **W00을 되살리지 않는다.**

## 1. 선행 상태 (전제 · 바꾸지 않는다)

```
EVENT_EXTRACTION_SHADOW_V1   CLOSED / INCONCLUSIVE
                             reason WINDOW_TECHNICAL_INVALID — W00 [0,48)
                             overlap semantic stability   NOT ADJUDICATED
                             frame-grounding              NOT ADJUDICATED
                             blinded mapping              봉인 유지
FRAME_ADJUDICATION_V1        CLOSED / SAMPLING_LOSS_CONFIRMED
0.25fps semantic sufficiency NOT ESTABLISHED
0.5fps                       PROVISIONAL WORKING DENSITY ONLY
production Event extraction  HOLD · Chapter·Highlight·Overview·Analysis·Conclusion HOLD
현행 제출본 READ-ONLY · official test UNOPENED · M9 HOLD
```

리뷰어 기록: prereg commit과 implementation commit이 같은 커밋이었던 점, H32 테스트
단언 정정은 **추가 무효 사유로 승격하지 않는다**(GPU 전 freeze였고 게이트를 바꾸지 않았다).

## 2. 실행 형태

```
새 Qwen 추론      없다. GPU를 쓰지 않는다
쓰는 것            기존 artifact + 원본 영상 디코드(프레임 지표 계산에만)
수정하지 않는 것    shadow_v1_W*.json · *_raw.txt · overlap packet · blind map ·
                  frame bank/audit · 기존 사건 산출물 · 현행 제출본
```

`torch`·`transformers`를 import하지 않는 것이 계약이고 테스트로 강제한다.

## 3. 입력 (동결 · 읽기 전용)

```
창 record 24건   runs/wvr_light_v1/shadow_v1_W{00..23}.json
raw 원문 24건    runs/wvr_light_v1/shadow_v1_W{00..23}_raw.txt
요약             runs/wvr_light_v1/shadow_v1_summary.json
frame bank       runs/wvr_light_v1/shadow_frame_bank.json (300프레임 픽셀 sha256)
영상             data/videos/full_xekZO4n4QuE.mp4
                 sha256 ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
프롬프트 계약      SAMPLING_DIAG_PROMPT_V2 · hash 37f9588e58d0cb96…
```

## 4. 검사 6개 (결과 보기 전 고정)

### C1. serialized prompt 비교 (W00 vs W01 · 전 24창)

프레임을 제외하고 창마다 실제로 달라지는 것이 무엇인지 본다.

```
비교 대상   프롬프트 문자열(템플릿 % {window_start, window_end}) 전문 diff
           window metadata(frame_times · frame_indices · decoded_times · decoded_fps)
           input_token_count · runtime_config_hash
판정 기준   프롬프트가 `템플릿 % 값`과 문자 단위로 일치하고, 창 간 차이가
           숫자 자리(0.0 vs 552.0)뿐이면 W00 전용 프롬프트 특수처리는 없다
```

### C2. 입력 builder 코드 경로 (W00 전용 분기 탐색)

```
대상   src/wvr_shadow_v1.py · scripts/wvr_shadow_run.py ·
       scripts/wvr_capacity_probe.py(sample_frames) · src/wvr_density_v2.py(parse_events)
탐색   `if start`, `if not start`, `start or`, `== 0`, `start_sec or`,
       `truthy/falsy zero`, clipping, local↔absolute timestamp 변환
기능 확인  24창 전부에 대해 frame_times·frame_indices의 선형성을 계산으로 확인한다
          (start + 2·i · index = round(time × rate))
```

### C3. W00 raw 구조 분석 (salvage 금지)

```
기록   전체 길이 · 완성된 event object 수 · 최초 반복 위치(문자 offset·object index) ·
       unique signature 수 · zero-length interval(start==end) 수 ·
       truncation 지점(마지막 문자·미완결 토큰) · JSON 파싱 실패 지점
금지   잘린 JSON을 보정해 event를 복구하는 것 (구조 관찰만)
```

동일 지표를 W01~W23에도 계산해 비교군으로 쓴다.

### C4. 시각 지표 비교 (결정적 · 사람 해석 없음)

원본 영상에서 창별 24프레임(0.5fps · 512×288 · 기존 표집 경로 동일)을 디코드해
아래를 계산한다. **임계는 여기서 동결한다.**

```
mean luma                   프레임 평균 밝기 (0~255)
black frame ratio           mean luma < 16.0 인 프레임 비율
near-static ratio           인접 프레임 mean abs diff < 2.0 인 쌍 비율
mean adjacent diff          인접 프레임 mean abs diff 평균
```

이 값들은 **descriptive diagnostic**이다. 어떤 임계로도 사건 판정을 만들지 않는다.
프레임 픽셀 해시를 `shadow_frame_bank.json`과 대조해 동일 표집인지 확인한다.

### C5. 생성 결정성 조건

```
기록   do_sample · num_beams · repetition_penalty · max_new_tokens · seed 지정 여부 ·
       stopping criteria(현재는 max_new_tokens 외 없음) · allocator/backend 관측값
한계   재실행을 하지 않으므로 **결정성을 실측으로 확인하지 않는다.**
       greedy 경로가 통제 조건에서 결정적이었다는 기존 관측(2026-08-18 AI Hub
       2,328구간 완전일치)은 참조로만 적고 이번 사건의 증거로 쓰지 않는다
```

### C6. parser 책임 분리

```
확인   raw 자체가 반복·미완결인지 (json.loads 실패 지점 포함)
판정   raw가 미완결이면 원인을 parser로 돌리지 않고 MODEL_OUTPUT_DEGENERACY로 기록한다
       parser가 완결 JSON을 잘못 처리한 흔적이 있으면 그것을 별도로 적는다
```

## 5. 결과 분류 (네 값만 · 결정 규칙 동결)

```
INPUT_PIPELINE_DEFECT      A ∧ ¬B
MODEL_OUTPUT_DEGENERACY    ¬A ∧ B
MIXED                      A ∧ B
UNRESOLVED                 ¬A ∧ ¬B
```

두 증거 축의 정의:

```
A = INPUT_ANOMALY_FOUND
    W00에만 적용되는 입력 경로 차이가 확인됨 —
    프롬프트 문자 불일치 · 창 전용 코드 분기 · 프레임 격자/인덱스 비선형 ·
    표집 픽셀이 frame bank와 불일치 · runtime config 해시 상이
B = OUTPUT_DEGENERACY_CONFIRMED
    W00 raw가 구조적으로 반복 생성이며 미완결임이 확인됨 —
    반복 signature가 지배적이고(동일 signature 반복 ≥ 2회) JSON이 미완결
```

C4의 시각 지표는 **분류 규칙에 들어가지 않는다**(맥락 기록 전용).

## 6. 금지 사항

```
새 Qwen 추론 · W00 재실행 · prompt 수정 · schema 변경
max_new_tokens 4096 → 8192 상향 (승인되지 않았다)
잘린 raw를 보정해 event 복구
W01~W23 raw·overlap packet·blind map 삭제 또는 mapping reveal
overlap semantic 판정 · frame-grounding 판정 · 부분 판정("22개는 괜찮아 보인다")
결과를 본 뒤 §4 검사 항목·§5 분류 규칙·C4 임계 변경
SHADOW_V1B 등 후속 실험 개시 (리뷰어가 이 결과를 보고 고른다)
현행 제출본 수정 · official test 접촉 · M9 실행
```

## 7. 테스트 (WVR-J01~J14)

```
동결    J01 사전등록 커밋 · J02 추론 스택 미사용 · J03 분류 4값 ·
        J04 결정 규칙 진리표 · J05 C4 임계 동결(16.0 · 2.0)
입력    J06 기존 artifact 무변경(해시 대조) · J07 raw salvage 금지 ·
        J08 프롬프트 재구성 = 템플릿 % 값
구조    J09 반복 지표 계산 정확성(합성 입력) · J10 zero-length interval 카운트 ·
        J11 미완결 JSON 감지
시각    J12 프레임 격자·인덱스 선형성 · J13 지표가 분류에 들어가지 않음
경계    J14 mapping·packet·제출본 미접촉
```

뮤테이션으로 각 항목이 실제로 잡히는지 확인하고 구멍은 결과에 적는다.

## 8. 산출물

```
runs/wvr_light_v1/w00_forensic_v1.json          검사 6개 결과 · 증거 축 A·B · 분류
docs/probes/WVR_W00_DEGENERACY_FORENSIC_V1_2026-09-09.md
src/wvr_w00_forensic.py · scripts/wvr_w00_forensic.py
tests/test_wvr_w00_forensic.py
```

기존 산출물은 읽기만 한다.

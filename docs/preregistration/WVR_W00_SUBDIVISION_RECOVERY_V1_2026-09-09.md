# WVR_W00_SUBDIVISION_RECOVERY_V1 사전등록 (2026-09-09)

승인: 리뷰어 결정 — **architecture recovery probe**. 이 문서는 GPU 실행 전에 커밋한다.
**결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

recovery 이후의 production 승격 · Event Map 생성 · Chapter/Overview 생성은 하지 않는다.

## 0. 선행 상태 (동결 · 바꾸지 않는다)

```
WVR_EVENT_EXTRACTION_SHADOW_V1   CLOSED / INCONCLUSIVE
                                 reason = W00 WINDOW_TECHNICAL_INVALID
WVR_W00_DEGENERACY_FORENSIC_V1   CLOSED / MODEL_OUTPUT_DEGENERACY
WVR_W00_DEGENERACY_REPRO_V1      CLOSED / REPRODUCIBLE
                                 3/3 fresh run degenerate · 원본 포함 raw byte-identical
```

W00 실패 특성:

```
window                  [0,48)
sampling                0.5fps · 24프레임
max_new_tokens          4096
완성 object              95
zero-duration           95/95
positive-duration       0
unique signature        2
교대 루프                 confirmed
JSON                    unterminated
raw                     원본 + R1/R2/R3 byte-identical
```

입력 pipeline anomaly · parser defect · runtime config mismatch는 발견되지 않았다.

## 1. Primary question 하나

```
결정적으로 degeneracy를 일으키는 W00 [0,48)를 더 짧은 overlapping local window로
분해하면, prompt/runtime/sampling을 바꾸지 않고 technically valid한
event representation을 얻을 수 있는가?
```

이 사건이 재는 것은 `recovery efficacy` 하나다.

다음 인과 주장은 **측정하지 않는다**:

```
48초가 degeneracy의 원인이다
24초가 universally safe하다
영상 내용이 원인이다
prompt가 원인이다
```

## 2. normative authority 우선순위

```
① 이 사건 preregistration
② frozen prompt/model/runtime configuration
③ raw execution artifacts
④ prior W00 forensic/repro results
⑤ PROJECT_OVERVIEW.md
```

## 3. recovery architecture (결정적 분해)

failing parent `[0,48)`를 세 child로 분해한다.

```
C0 = [0,24)      C1 = [12,36)      C2 = [24,48)

window length = 24초    stride = 12초    overlap = 12초
sampling = 0.5fps       frames/window = 12
```

정확한 sampled timestamps:

```
C0   0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22
C1   12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34
C2   24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 46
```

parent `[0,48)`를 빈틈없이 cover해야 한다 (gap 0).

## 4. 변경되는 것 / 변경되지 않는 것

architecture change — 이것만 recovery mechanism으로 시험한다:

```
48초 local window  ->  24초 local window / 12초 overlap
```

W00과 동일하게 동결(frozen):

```
video · video sha256           data/videos/full_xekZO4n4QuE.mp4
                               ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
model                          Qwen/Qwen3-VL-8B-Instruct
revision                       0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
prompt                         SAMPLING_DIAG_PROMPT_V2
                               37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273
event schema                   start_sec · end_sec · actor · action · object_or_state
입력                            video-only · English-only diagnostic
sampling                       0.5fps
런타임                          bf16 · SDPA · default allocator
생성                            greedy · do_sample False · num_beams 1 ·
                               max_new_tokens 4096 · repetition_penalty 1.0
parser · collapse rule         불변
fresh-process policy           child 하나당 새 process
```

금지:

```
token cap 상향 · prompt 수정 · schema 수정 · event cap 추가 ·
repetition penalty 수정 · stop rule 추가 · controlled vocabulary ·
zero-duration 금지 instruction 추가 · temperature/do_sample 변경 ·
실패 child 즉석 retry
```

## 5. 실행 횟수

```
C0 × 1     C1 × 1     C2 × 1        총 3 inference run
```

각 child는 fresh process. 같은 child를 반복 측정하지 않는다.
실패하면 결과를 그대로 보존한다(INVALID provenance).

## 6. input identity / lineage gate (GPU 사용 전 + 실행 중)

각 child frame은 기존 C01 frame bank 및 원본 영상과 일치해야 한다.

```
video sha256 identical
0.5fps grid exact
frame pixel hash exact          (frame bank · 원본 W00 record 대조)
parent coverage exact           [0,48) gap 0
child timestamps                이 문서의 schedule과 exact
```

overlap:

```
C0 ∩ C1 = [12,24)    공유 프레임 6개    12, 14, 16, 18, 20, 22
C1 ∩ C2 = [24,36)    공유 프레임 6개    24, 26, 28, 30, 32, 34
```

공유 timestamp와 pixel hash가 완전히 동일해야 한다.
불일치 시 **semantic recovery를 판정하지 않는다.**

원본 W00 산출물 무변경도 실행 전에 확인한다:

```
shadow_v1_W00.json      c8e65b74b8c71aa97f85fc69c6ffdfb2c72fab18911e6e1565c8458e44daa074
shadow_v1_W00_raw.txt   c5e4f7526eb83d95544c34189a5f83569cd27b4811c2f28b5ab12b0b2b36b7e6
```

## 7. raw-before-parse

각 child:

```
inference -> raw persist -> raw hash -> parse -> collapse -> technical validity
```

unterminated JSON을 salvage해 valid output으로 승격하는 것은 금지다.
raw 수정 금지.

## 8. child technical gate

SHADOW_V1 technical validity 어휘를 그대로 쓴다. 각 child는 `WINDOW_VALID` 또는
`WINDOW_INVALID`다.

최소 검사:

```
process complete · no OOM · no runtime failure · raw persisted ·
JSON parse OK · schema valid · English-only 만족 ·
generation cap hit 없음 · representation degeneracy 없음 ·
frame count = 12 · grid exact
```

degeneracy detector 로직도 바꾸지 않는다(V2 `representation` · forensic 구조 분석).

## 9. primary recovery verdict (사전 동결)

```
SUBDIVISION_TECHNICAL_RECOVERY_PASS
    C0 VALID AND C1 VALID AND C2 VALID      (3/3)

SUBDIVISION_RECOVERY_FAIL
    하나라도 기존 failure 어휘에 의해 WINDOW_INVALID

INCONCLUSIVE
    recovery 자체를 평가할 수 없는 unrelated technical/provenance failure —
    input identity failure · frame hash mismatch ·
    runtime infrastructure failure · provenance failure · wrong frozen config
```

판정 우선순위는 `INCONCLUSIVE(측정 불가) -> FAIL -> PASS`다.
blocker 어휘(측정 불가)와 model-output 실패 어휘(FAIL)를 지금 나눠 둔다:

```
blocker      VIDEO_PROVENANCE_MISMATCH · SAMPLING_GRID_MISMATCH ·
             FRAME_COUNT_MISMATCH · SHARED_FRAME_IDENTITY_FAILURE ·
             RAW_NOT_PERSISTED · RUNTIME_FAILURE · CONFIG_MISMATCH ·
             CHILD_COUNT_MISMATCH
FAIL 사유     PARSE_FAILURE · CONTRACT_VIOLATION · NO_EVENT ·
             TRUNCATED_AT_CAP · OUTPUT_LANGUAGE_CONTRACT_FAILURE ·
             EVENT_REPRESENTATION_DEGENERACY
```

**결과를 본 뒤 예외를 만들지 않는다.**

## 10. 해석 제한

`SUBDIVISION_TECHNICAL_RECOVERY_PASS`가 나와도 다음은 쓰지 않는다:

```
24초 semantic stability proven · 24초 production approved ·
0.5fps sufficient · Event extraction solved
```

허용되는 최대 주장:

```
The deterministic W00 degeneracy observed at 48 seconds was not reproduced in
any of the three preregistered 24-second recovery children under the frozen
inference configuration.
```

FAIL이어도 `24초 전체 architecture 불가능`으로 일반화하지 않는다.

## 11. semantic packet은 technical PASS일 때만 생성

C0/C1/C2가 **3/3 VALID일 때만** reviewer용 semantic recovery packet을 만든다.
Claude는 semantic 판정을 하지 않는다.

두 overlap:

```
R-O1 = [12,24)      R-O2 = [24,36)
```

각 overlap에서 두 child의 collapsed event 중 overlap과 교차하는 event를 결정적으로
clip한다. 원본은 변경하지 않는다. 보존 필드:

```
original_event_id · original_start · original_end ·
clipped_start · clipped_end · actor · action · object_or_state
```

## 12. blind packet (mapping procedure 동결)

두 overlap을 procedural blind한다. earlier/later child mapping은 숨긴다.

```
label = f(prereg SHA, overlap_id, role)
        sha256("<prereg_sha>|<overlap_id>").digest()[0] & 1 로 A/B를 뒤집는다
        flip=1 -> earlier=B · later=A        flip=0 -> earlier=A · later=B
```

같은 입력이면 같은 출력이고, 실행 후 변경할 수 없다. 사람이 결과를 보고 고르지 않는다.
**reviewer verdict 전 reveal 금지.**

reviewer 전용 어휘(Claude가 채우지 않는다):

```
STABLE · GRANULARITY_SHIFT · MATERIAL_DIVERGENCE · UNRESOLVED
```

절차적 blinding임을 명시한다 — 산출물 파일명이 child id를 담고 있어 저장소에서
mapping 복원이 가능하다. packet만 읽는다는 규율에 의존한다.

## 13. frame packet (두 overlap 모두 사전등록)

```
R-O1 [12,24)    12, 14, 16, 18, 20, 22
R-O2 [24,36)    24, 26, 28, 30, 32, 34
```

각 overlap 6 프레임. 512×288 model-input 픽셀 그대로 사용한다.
저장: individual PNG · contact sheet · absolute timestamp · pixel sha256.
frame annotation이 원본 픽셀을 덮지 않게 한다(라벨은 프레임 밖 여백에 쓴다).

## 14. frame audit의 목적

```
context subdivision으로 valid JSON을 얻었지만, 두 child가 같은 shared pixel을 보고도
report-materially 다른 사건을 만드는가?
생성된 overlap event가 실제 shared pixel과 명백히 충돌하는가?
```

Claude는 support verdict를 내리지 않는다. reviewer 어휘:

```
SUPPORTED · PARTIALLY_SUPPORTED · UNSUPPORTED · FRAMES_INSUFFICIENT
```

## 15. recovery semantic gate는 reviewer 전용

technical recovery가 PASS여도 사건 전체를 executor가 PASS 처리하지 않는다. 상태는

```
SUBDIVISION_TECHNICAL_RECOVERY_PASS + SEMANTIC_REVIEW_PENDING
```

에서 멈춘다. 이후 reviewer가 판정한다:

```
Recovery semantic PASS 후보   두 overlap 모두 STABLE 또는 GRANULARITY_SHIFT이고
                             material unsupported/unresolved 없음
HOLD                         하나라도 MATERIAL_DIVERGENCE 또는
                             report-material UNSUPPORTED
INCONCLUSIVE                 하나라도 UNRESOLVED · material PARTIALLY_SUPPORTED ·
                             material FRAMES_INSUFFICIENT
```

## 16. 원본 W00과 기존 SHADOW_V1 보존

어떤 결과가 나와도 변경 금지:

```
original W00                     WINDOW_INVALID
W00_REPRO_V1                     REPRODUCIBLE
EVENT_EXTRACTION_SHADOW_V1       CLOSED / INCONCLUSIVE
```

C0/C1/C2 결과를 기존 W00 자리에 끼워 넣어 SHADOW_V1을 소급 복구하지 않는다.
기존 23 overlap blind packet은 mapping 봉인 유지 · semantic adjudication 금지.

## 17. recovery가 성공해도 이번에 하지 않는 것

```
전체 C01을 24초 window로 재실행 · 기존 48초 valid window를 24초로 바꾸기 ·
Event stitching production · Event Map production · Semantic Chapters ·
Highlights · Overview · Analysis · Conclusion · HWPX
```

이번 사건은 **known-failing W00 하나에 대한 fallback recovery probe**다.

## 18. 후속 branch (기록만 · 실행 금지)

```
PASS + semantic overlap stable    reviewer가 hierarchical fallback architecture 검토
PASS + semantic divergence        shorter context가 technical loop는 풀고
                                  representation 안정성은 못 푼 것
RECOVERY FAIL                     24초 subdivision도 현행 prompt/runtime에서
                                  recovery 불충분
INCONCLUSIVE                      measurement/provenance repair
```

어떤 후속 branch도 자동 실행하지 않는다.

## 19. 최소 invariant (테스트로 고정)

```
child 정확히 3개 · C0 [0,24) · C1 [12,36) · C2 [24,48)
각 12프레임 · 0.5fps 격자 exact
parent [0,48) full coverage · gap 없음
C0/C1 overlap 공유 프레임 정확히 6 · C1/C2 overlap 공유 프레임 정확히 6
공유 픽셀 hash-identical
prompt hash 불변 · model revision 불변 · runtime config 불변 · max_new_tokens 불변
raw-before-parse · 숨은 retry 없음
원본 W00 무변경 · 기존 blind map 무변경 · 현행 제출본 무변경 · official test 미개방
```

mutation suite RED 확인 + full suite 실행.

## 20. 실행 순서

```
1  prereg 작성            2  prereg commit         3  implementation/tests commit
4  validator              5  C0 inference          6  raw persist
7  C1 inference           8  raw persist           9  C2 inference
10 raw persist            11 parse/collapse        12 technical recovery gate
13 technical PASS인 경우에만 blind overlap packet
14 technical PASS인 경우에만 frame audit packet 2개
15 tests/mutations/full suite                      16 clean tree 확인
17 result commit          18 STOP
```

## 21. 산출물 이름

```
runs/wvr_light_v1/subdiv_v1_C{0,1,2}.json          child record
runs/wvr_light_v1/subdiv_v1_C{0,1,2}_raw.txt       raw 원문 (파싱 전 저장)
runs/wvr_light_v1/subdiv_v1_summary.json           identity·child 표·게이트
runs/wvr_light_v1/subdiv_v1_overlap_packet.md      blinded packet (PASS 시)
runs/wvr_light_v1/subdiv_v1_blind_map.json         mapping (봉인)
runs/wvr_light_v1/subdiv_v1_frame_audit.json       frame manifest (PASS 시)
runs/wvr_light_v1/frames_subdiv/                   PNG · contact sheet
runs/wvr_light_v1/subdiv_v1.log                    배치 로그
```

## 22. 실행 후 상태 (결과와 무관하게 유지)

```
WVR_EVENT_EXTRACTION_SHADOW_V1   CLOSED / INCONCLUSIVE
W00_FORENSIC_V1                  CLOSED / MODEL_OUTPUT_DEGENERACY
W00_REPRO_V1                     CLOSED / REPRODUCIBLE
production Event extraction      HOLD
Chapter / Highlight / Overview / Analysis / Conclusion   HOLD
현행 제출본                        READ-ONLY        official test UNOPENED       M9 HOLD
```

새 사건만 별도로 기록한다. 여기서 멈춘다.

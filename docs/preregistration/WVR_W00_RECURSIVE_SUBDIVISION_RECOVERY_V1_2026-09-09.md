# WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1 사전등록 (2026-09-09)

승인: 리뷰어 결정 — **recursive fallback 최소 feasibility probe**. 이 문서는 GPU 실행
전에 커밋한다. **결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

실패한 child **C0 [0,24) 하나만** 한 단계 더 세분한다. C1·C2는 재실행하지 않는다.

## 0. 선행 상태 (동결 · 바꾸지 않는다)

```
WVR_EVENT_EXTRACTION_SHADOW_V1     CLOSED / INCONCLUSIVE
WVR_W00_DEGENERACY_FORENSIC_V1     CLOSED / MODEL_OUTPUT_DEGENERACY
WVR_W00_DEGENERACY_REPRO_V1        CLOSED / REPRODUCIBLE
WVR_W00_SUBDIVISION_RECOVERY_V1    CLOSED / SUBDIVISION_RECOVERY_FAIL
  C0 [0,24)   WINDOW_INVALID       C1 [12,36) VALID       C2 [24,48) VALID
```

C0 실패 특성:

```
12프레임 · 0.5fps · generated 4,096 (cap) · 완성 object 93 ·
zero-duration 93/93 · positive-duration 0 · 반복 signature 3개 순환 ·
JSON 미완결 · MODEL_OUTPUT_DEGENERACY
```

읽기 전용으로 무변경을 확인할 산출물 해시:

```
subdiv_v1_C0.json      7925172a83d3304730e6b21509bdc0c70dbe78ae0e5433e0809a7e074471d0f6
subdiv_v1_C0_raw.txt   7460a5b61821e41b15dd0281aa15580a2ac7752dab48be2bbf809f1d193105d0
subdiv_v1_C1.json      44b7f96c1f23a0760f6cc8fa975d058b86d813878c75898136bd368979d75f11
subdiv_v1_C1_raw.txt   9316f9f62b519ef0cc8a99a827fa71ed153b5efea3a673e5d53b2d084392f117
subdiv_v1_C2.json      cb77b4b283f988d150efcb1c780d4cc1c8c5ff6d7ce566517ca35b17cc68f126
subdiv_v1_C2_raw.txt   70815aeee2408bd174d0a031a08200bf9e6b12fdff6d46a9c8a0ec36ef453b10
shadow_v1_W00.json     c8e65b74b8c71aa97f85fc69c6ffdfb2c72fab18911e6e1565c8458e44daa074
shadow_v1_W00_raw.txt  c5e4f7526eb83d95544c34189a5f83569cd27b4811c2f28b5ab12b0b2b36b7e6
```

## 1. Primary question 하나

```
24초에서도 결정적으로 degeneracy가 난 C0 [0,24)를 12초 overlapping local window로
한 단계 더 세분하면, frozen prompt/runtime/sampling을 유지한 채 technically valid한
Local Event output으로 복구되는가?
```

원인 규명이 아니다. 다음은 **주장하지 않는다**:

```
12초가 universally safe · 0초 boundary가 원인 · 영상 내용이 원인 ·
24초가 원인 · prompt가 원인
```

## 2. normative authority 우선순위

```
① 이 사건 preregistration
② frozen prompt/model/runtime configuration
③ raw execution artifacts
④ prior W00 forensic/repro/subdivision 결과
⑤ PROJECT_OVERVIEW.md
```

## 3. architecture change (결정적 분해)

실패한 parent `C0 [0,24)`만 분해한다.

```
D0 = [0,12)      D1 = [6,18)      D2 = [12,24)

window length = 12초    stride = 6초    overlap = 6초
sampling = 0.5fps       frames/window = 6
```

정확한 sampled timestamps:

```
D0   0, 2, 4, 6, 8, 10
D1   6, 8, 10, 12, 14, 16
D2   12, 14, 16, 18, 20, 22
```

parent `C0 [0,24)`를 gap 없이 cover해야 한다.

## 4. 동결 inference configuration (C0와 동일)

```
video · sha256                 data/videos/full_xekZO4n4QuE.mp4
                               ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
model                          Qwen/Qwen3-VL-8B-Instruct
revision                       0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
prompt                         SAMPLING_DIAG_PROMPT_V2
                               37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273
schema                         start_sec · end_sec · actor · action · object_or_state
입력                            video-only · English-only
sampling                       0.5fps
런타임                          bf16 · SDPA · default allocator
생성                            greedy · do_sample False · num_beams 1 ·
                               max_new_tokens 4096 · repetition_penalty 1.0
parser · collapse rule         불변
fresh-process policy           child 하나당 새 process
```

변경 금지:

```
prompt 수정 · schema 수정 · token cap 증가 · repetition penalty 변경 ·
event cap · stop criterion · temperature/sampling 변경 ·
zero-duration 방지 문구 추가 · 실패 child retry
```

창 길이 12초·overlap 6초·프레임 6장만이 이번 사건의 변경이다.

## 5. 실행

```
D0 ×1      D1 ×1      D2 ×1        총 3회 fresh-process inference
```

성공본 선택용 retry가 아니다. 각 결과는 독립 관측이고, 실패하면 그대로 보존한다.

## 6. input lineage gate

```
video sha 동일
0.5fps grid exact
각 child frame이 기존 C0 record · frame bank와 pixel hash identical
parent C0 [0,24) coverage exact · gap 0
```

overlap:

```
D0 ∩ D1 = [6,12)     공유 프레임 6, 8, 10      정확히 3장
D1 ∩ D2 = [12,18)    공유 프레임 12, 14, 16    정확히 3장
```

timestamp와 pixel hash 모두 동일해야 한다. 불일치면 recovery를 판정하지 않는다.

## 7. raw-before-parse

```
inference -> raw persist -> raw hash -> parse -> collapse -> technical gate
```

unterminated JSON salvage 금지. raw 수정 금지.

## 8. technical validity

기존 SHADOW/V2 어휘 그대로. 각 child는 `WINDOW_VALID` 또는 `WINDOW_INVALID`.

최소 게이트:

```
process completed · no OOM · no runtime failure · raw persisted ·
JSON parse OK · schema valid · English-only satisfied ·
generation cap hit 없음 · representation degeneracy 없음 ·
frame count = 6 · grid exact
```

degeneracy detector 변경 금지.

## 9. primary recovery verdict (사전 동결)

```
RECURSIVE_SUBDIVISION_TECHNICAL_PASS
    D0 VALID AND D1 VALID AND D2 VALID

RECURSIVE_SUBDIVISION_RECOVERY_FAIL
    하나라도 WINDOW_INVALID

INCONCLUSIVE
    recovery efficacy와 무관한 실패일 때만 —
    input identity failure · pixel lineage mismatch ·
    runtime infrastructure failure · wrong frozen config · provenance failure
```

우선순위는 `INCONCLUSIVE(측정 불가) -> FAIL -> PASS`다. blocker 어휘와 model-output
실패 어휘를 지금 나눠 둔다(SUBDIVISION_RECOVERY_V1과 같은 구분):

```
blocker      VIDEO_PROVENANCE_MISMATCH · SAMPLING_GRID_MISMATCH ·
             FRAME_COUNT_MISMATCH · SHARED_FRAME_IDENTITY_FAILURE ·
             LINEAGE_PIXEL_MISMATCH · RAW_NOT_PERSISTED · RUNTIME_FAILURE ·
             CONFIG_MISMATCH · CHILD_COUNT_MISMATCH · NO_PARSE_RECORD
FAIL 사유     PARSE_FAILURE · CONTRACT_VIOLATION · NO_EVENT ·
             TRUNCATED_AT_CAP · OUTPUT_LANGUAGE_CONTRACT_FAILURE ·
             EVENT_REPRESENTATION_DEGENERACY
```

**결과 후 예외를 추가하지 않는다.**

## 10. 깊이별 비교 축 (구조 항목만)

`W00 [0,48)` · `C0 [0,24)` · `D0 [0,12)`은 모두 timestamp 0에서 시작한다. 따라서
아래 항목을 나란히 기록한다.

```
generated tokens · cap hit · completed objects · raw unique signatures ·
zero-duration · positive-duration · JSON completion · degeneracy status · raw hash
```

이 비교로 `start_sec=0이 원인`이라고 단정하지 않는다. **실패가 어느 subdivision
depth까지 지속되는지만 기록한다.**

## 11. 기존 valid output과의 관계

`C1 [12,36) VALID`는 `D2 [12,24)`와 일부 시각을 공유하지만 **context가 다르므로 두
출력을 equivalent truth로 취급하지 않는다.** 기술 recovery가 PASS일 때만 별도 reviewer
packet에서 context stability를 볼 수 있다. executor는 그 비교를 판정하지 않는다.

## 12. semantic packet (3/3 VALID일 때만)

두 overlap:

```
RR-O1 = [6,12)      RR-O2 = [12,18)
```

각 overlap에서 두 child의 collapsed event를 결정적으로 clip한다. 원본은 변경하지 않고
아래를 보존한다:

```
original_event_id · original_start · original_end ·
clipped_start · clipped_end · actor · action · object_or_state
```

Claude semantic 판정 금지.

## 13. blinding (mapping procedure 동결)

technical PASS일 때만 procedural blind packet을 만든다. earlier/later child mapping은
숨긴다.

```
label = sha256("<prereg_sha>|<overlap_id>").digest()[0] & 1 로 A/B를 뒤집는다
        flip=1 -> earlier=B · later=A        flip=0 -> earlier=A · later=B
```

같은 입력이면 같은 출력이고 실행 후 변경할 수 없다. **reviewer verdict 전 reveal 금지.**
절차적 blinding임을 명시한다 — 산출물 파일명이 child id를 담고 있어 저장소에서 복원이
가능하고, packet만 읽는다는 규율에 의존한다.

## 14. frame audit (PASS일 때 두 overlap 모두)

```
RR-O1   6, 8, 10        RR-O2   12, 14, 16
```

512×288 model-input 픽셀 그대로. individual PNG + contact sheet + absolute timestamp +
pixel sha256. 라벨은 프레임 밖 여백에만 쓴다(원본 픽셀 미변경).

Claude는 `SUPPORTED · PARTIALLY_SUPPORTED · UNSUPPORTED · FRAMES_INSUFFICIENT`를
판단하지 않는다 — reviewer 전용이다.

## 15. semantic 판정은 reviewer 전용

```
STABLE · GRANULARITY_SHIFT · MATERIAL_DIVERGENCE · UNRESOLVED
```

technical PASS ≠ semantic PASS. PASS면 상태는

```
RECURSIVE_SUBDIVISION_TECHNICAL_PASS + SEMANTIC_REVIEW_PENDING
```

에서 멈춘다.

## 16. 해석 제한

PASS일 때 허용되는 최대 결론:

```
The known failing C0 [0,24) window was technically recoverable through one
additional preregistered 12-second overlapping subdivision level under the
frozen inference configuration.
```

금지:

```
12초 semantic stability proven · 12초 production approved ·
hierarchical fallback production approved · 0.5fps sufficient ·
Event extraction solved
```

FAIL이어도 `모든 더 짧은 window가 실패한다`로 일반화하지 않는다.

## 17. 이번 사건의 위치

recursive fallback architecture(정상 window는 건드리지 않고 실패 branch만 세분)의
**최소 feasibility**만 본다. 이 결과만으로 fallback 정책을 production 채택하지 않는다.

## 18. 더 이상 subdivision하지 않는다

D0/D1/D2 중 하나가 실패해도 이번 사건에서 `6초 window / 3초 overlap`으로 자동 진행하지
않는다. recursive depth를 사후에 늘리지 않는다. **12초에서 실패하면 STOP**이고, 다음
minimum context/failure policy는 리뷰어가 별도 설계한다.

## 19. 최소 invariant (테스트로 고정)

```
child 정확히 3개 · D0 [0,12) · D1 [6,18) · D2 [12,24)
각 6프레임 · 0.5fps 격자 exact
parent C0 [0,24) full coverage · gap 0
D0/D1 공유 3장 · D1/D2 공유 3장 · 픽셀 해시 동일
prompt·model·runtime 불변 · 4096 불변 · retry 없음 · raw-before-parse
C0 원본 산출물 무변경 · C1·C2 무변경 · SHADOW blind map 무변경 ·
현행 제출본 무변경 · official test 미개방
```

mutation RED 확인 + full suite 실행.

## 20. 실행 순서

```
1  prereg          2  prereg commit        3  implementation/tests commit
4  validator       5  D0 inference + raw persist
6  D1 inference + raw persist               7  D2 inference + raw persist
8  parse/collapse  9  technical gate
10 PASS일 때만 blind semantic packet         11 PASS일 때만 frame audit packet
12 tests/mutations/full suite               13 clean tree
14 result commit   15 STOP
```

## 21. 산출물 이름

```
runs/wvr_light_v1/recur_v1_D{0,1,2}.json         child record
runs/wvr_light_v1/recur_v1_D{0,1,2}_raw.txt      raw 원문 (파싱 전 저장)
runs/wvr_light_v1/recur_v1_summary.json          child 표·겹침 identity·게이트·깊이 비교
runs/wvr_light_v1/recur_v1_overlap_packet.md     blinded packet (PASS 시)
runs/wvr_light_v1/recur_v1_blind_map.json        mapping (봉인)
runs/wvr_light_v1/recur_v1_frame_audit.json      frame manifest (PASS 시)
runs/wvr_light_v1/frames_recur/                  PNG · contact sheet
runs/wvr_light_v1/recur_v1.log                   배치 로그
```

## 22. 실행 후 상태 (결과와 무관하게 유지)

```
SHADOW_V1                        CLOSED / INCONCLUSIVE
W00_FORENSIC_V1                  CLOSED / MODEL_OUTPUT_DEGENERACY
W00_REPRO_V1                     CLOSED / REPRODUCIBLE
SUBDIVISION_RECOVERY_V1          CLOSED / FAIL
production Event extraction      HOLD
Chapter / Highlight / Overview / Analysis / Conclusion   HOLD
현행 제출본                        READ-ONLY      official test UNOPENED     M9 HOLD
```

새 사건만 별도로 기록한다. 여기서 멈춘다.

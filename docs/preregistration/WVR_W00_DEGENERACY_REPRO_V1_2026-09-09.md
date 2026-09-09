# WVR_W00_DEGENERACY_REPRO_V1 사전등록 (2026-09-09)

승인: 리뷰어 결정 — 재현성 측정만. **이 문서는 GPU 실행 전에 커밋한다.
결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

## 0. Primary question 하나

```
기존 W00 [0,48)에서 발생한 MODEL_OUTPUT_DEGENERACY가
동일 input · 동일 inference configuration · fresh process 조건에서 재현되는가?
```

recovery 방법 시험이 아니다. 결과를 보고 recovery 실험으로 넘어가지 않는다.

## 1. normative authority 우선순위

```
① 이 사건 preregistration
② frozen inference configuration
③ raw execution artifacts
④ forensic/report documentation
⑤ PROJECT_OVERVIEW.md
```

문서 설명보다 frozen config가 우선한다.

## 2. 선행 상태 (동결 · 바꾸지 않는다)

```
WVR_EVENT_EXTRACTION_SHADOW_V1     CLOSED / INCONCLUSIVE
                                   reason = W00 WINDOW_TECHNICAL_INVALID
WVR_W00_DEGENERACY_FORENSIC_V1     CLOSED / MODEL_OUTPUT_DEGENERACY
  input anomaly NOT FOUND · window-specific branch NOT FOUND ·
  frame/grid anomaly NOT FOUND · parser cause NO
  W00 raw: 완성 object 95 · zero-length 95/95 · unique signature 2 ·
           교대 루프 · JSON 미완결 · 4096 cap 도달
  cap 도달은 반복의 원인이 아니라 결과
재현성·결정성                        아직 측정하지 않았다 (이 사건이 측정한다)
```

## 3. inference configuration (SHADOW_V1 W00과 완전 동일)

```
video        data/videos/full_xekZO4n4QuE.mp4
             sha256 ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
window       W00 [0, 48)
sampling     0.5fps · 24프레임 · t = 0, 2, 4, … , 46
model        Qwen/Qwen3-VL-8B-Instruct
revision     0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
prompt       SAMPLING_DIAG_PROMPT_V2
             hash 37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273
schema       events[{start_sec, end_sec, actor, action, object_or_state}] · 불변
dtype        bfloat16 · quantization None · attn sdpa · device_map None
allocator    default
생성          greedy · do_sample False · num_beams 1 ·
             max_new_tokens 4096 · repetition_penalty 1.0
runtime hash cb43ffd357d771ff2923f2d3e0dec0f48f85bba660171cfc3832a298f4fef5aa
             (원본 W00 record의 runtime_config_hash — R1~R3도 같아야 한다)
```

변경 금지: prompt · schema · max_new_tokens · repetition_penalty ·
temperature/do_sample · frame sampling · window 길이 · retry 전용 프롬프트 ·
zero-length 방지 규칙 · event cap · stop criterion 추가.

## 4. 실행 — fresh process 3회

```
R1  W00 [0,48)      R2  W00 [0,48)      R3  W00 [0,48)
```

각 run은 새 process에서 시작하고 이전 output·state·cache를 재사용하지 않는다.
입력 프레임 바이트와 inference configuration은 동일해야 한다.

**이 3회는 retry가 아니라 사전등록된 measurement observation 3건이다.**
성공한 run을 골라 production output이나 SHADOW_V1 복구에 쓰지 않는다.

## 5. input identity gate (GPU 사용 전)

R1/R2/R3 각각에서 원본 W00과 아래가 동일한지 확인한다.

```
video sha256 · window · 24 timestamps · 24 model-input 픽셀 해시 ·
serialized prompt text · prompt hash · model revision ·
runtime config hash · generation config · input construction path
```

하나라도 다르면 그 run은 reproduction observation으로 쓸 수 없다
(`INPUT_IDENTITY_FAILURE`). 사후 수정으로 되살리지 않는다.

원본 W00 산출물 무변경도 매번 확인한다.

```
shadow_v1_W00.json      sha256 c8e65b74b8c71aa97f85fc69c6ffdfb2c72fab18911e6e1565c8458e44daa074
shadow_v1_W00_raw.txt   sha256 c5e4f7526eb83d95544c34189a5f83569cd27b4811c2f28b5ab12b0b2b36b7e6
```

## 6. raw-before-parse

```
inference → raw persist → hash → parse → technical classification → structural analysis
```

raw를 수정·salvage하지 않는다. 미완결 JSON에서 완성 object를 뽑아 valid output으로
승격하지 않는다.

## 7. 각 run technical classification

기존 SHADOW_V1 technical gate(`sh.window_validity`)를 그대로 쓴다.

```
VALID  또는  WINDOW_INVALID   (reason vocabulary도 기존 그대로)
```

새 acceptance threshold를 만들지 않는다.

## 8. degeneracy structural audit (run별 · 결정적)

```
raw chars · generated tokens · finish reason
completed object count · unique signature count
max global signature repetition · max consecutive signature repetition
zero-length interval count · positive-duration interval count
first repeat object index · first repeat byte offset
JSON complete 여부
```

참고용으로 forensic에서 관측된 두 signature와의 exact-string 일치도 기록한다.

```
S1  a person / pouring / liquid from a bottle into a bowl
S2  a person / holding / a bottle
```

**단, 문구가 다르면 degeneracy가 아니라고 판단하지 않는다.** 구조(무진행 반복 ·
zero-length interval 지배 · 미완결)가 같은지 별도로 본다.

run별 degeneracy 판정은 forensic의 축 B를 그대로 쓴다.

```
OUTPUT_DEGENERACY_CONFIRMED = 지배적 signature 반복(≥2) ∧ JSON 미완결
→ 그 run의 degeneracy classification = MODEL_OUTPUT_DEGENERACY
```

## 9. reproducibility gate (동결)

```
REPRODUCIBLE     R1·R2·R3 전부 MODEL_OUTPUT_DEGENERACY            (3/3)
NOT_REPRODUCED   R1·R2·R3 전부 technically VALID                  (0/3)
INTERMITTENT     1/3 또는 2/3만 MODEL_OUTPUT_DEGENERACY
INCONCLUSIVE     재현성 자체를 측정할 수 없는 기술 문제 —
                 input identity failure · 무관한 runtime/OOM 실패 ·
                 provenance failure · config mismatch
```

또한 3개 run이 모두 VALID도 아니고 모두 degeneracy도 아닌데 degeneracy가 0건인
경우(예: 다른 사유의 INVALID 혼재)는 `INCONCLUSIVE`로 닫는다.
**결과를 본 뒤 비율 threshold를 추가하지 않는다.**

## 10. exact determinism 축 (primary verdict를 바꾸지 않는다)

```
EXACT_RAW_REPRODUCTION                세 raw가 byte-identical
STRUCTURAL_DEGENERACY_REPRODUCTION    문구·길이는 달라도 모두 무진행 반복
OUTPUT_VARIATION                      valid/invalid가 섞임
```

## 11. 원본 W00의 지위

```
original W00 = WINDOW_INVALID 유지 — 어떤 결과가 나와도 소급 VALID로 바꾸지 않는다
이번 valid run을 골라 SHADOW_V1을 PASS/HOLD 판정 가능 상태로 복구하지 않는다
23 overlap packet · blind mapping 미접촉 · mapping reveal 금지 · semantic 판정 금지
```

## 12. 금지되는 해석

`REPRODUCIBLE`이어도: 원인이 48초 context다 · 원인이 영상 내용이다 ·
prompt가 나쁘다 · 4096이 부족하다 — 단정 금지.

`NOT_REPRODUCED`여도: 문제가 해결됐다 · 원본 W00이 false alarm이다 ·
single retry가 안전하다 — 금지.

`INTERMITTENT`면 성공 run을 골라 production output으로 쓰지 않는다.

## 13. 후속 branch (기록만 · 실행 금지)

```
REPRODUCIBLE     → failed-window subdivision recovery 후보
                   48초 → 24초 local windows / 12초 overlap (prompt·runtime 불변)
INTERMITTENT     → 명시적 recovery/retry policy를 별도 실험으로 설계
NOT_REPRODUCED   → non-deterministic/transient failure handling architecture 설계
INCONCLUSIVE     → provenance/measurement repair
```

**이번 사건에서 어떤 branch도 실행하지 않는다. 24초 window 추론도 금지다.**

## 14. 테스트 (WVR-K01~K16)

```
동결    K01 사전등록 커밋 · K02 run 3개 고정 · K03 창은 W00 [0,48) ·
        K04 24 timestamps 동일 · K05 프롬프트·모델 revision 동결 ·
        K06 생성 설정 동결(cap 4096 · penalty 1.0 · greedy)
identity K07 픽셀 해시 24개 대조 · K08 runtime config hash 대조 ·
        K09 불일치 시 INPUT_IDENTITY_FAILURE
계약    K10 raw-before-parse · K11 hidden retry 없음 · K12 run 1회 제한
게이트   K13 재현성 4값 진리표 · K14 determinism 축 분리
경계    K15 원본 W00·blind artifact 미접촉(해시 대조) ·
        K16 제출본 해시 불변 · test split 미접촉
```

뮤테이션으로 위 invariant가 깨지면 RED인지 확인하고 구멍은 결과에 적는다.

## 15. 산출물

```
runs/wvr_light_v1/w00_repro_R{1,2,3}.json        run record (provenance·해시·구조)
runs/wvr_light_v1/w00_repro_R{1,2,3}_raw.txt     raw 원문 (파싱 전 저장)
runs/wvr_light_v1/w00_repro_summary.json         identity 표 · run 표 · 교차 비교 · 게이트
runs/wvr_light_v1/w00_repro.log                  배치 로그
docs/probes/WVR_W00_DEGENERACY_REPRO_V1_2026-09-09.md
src/wvr_w00_repro.py · scripts/wvr_w00_repro_run.py ·
scripts/wvr_w00_repro_summary.py · scripts/wvr_w00_repro_batch.sh ·
tests/test_wvr_w00_repro.py
```

기존 사건 산출물·현행 제출본은 읽기만 한다.

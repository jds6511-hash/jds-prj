# 프로젝트 개요와 현재 파이프라인 (2026-09-09 · SHADOW_V1 판정 반영)

이 문서는 **지도**다. 실험 계약서가 아니다. 충돌하면 아래 우선순위를 따른다.

```
① 해당 사건의 preregistration          docs/preregistration/
② frozen prompt/schema/runtime hash    src/wvr_*.py · config.yaml
③ execution artifacts / raw results    runs/**/*.json · results/*.json
④ 이 문서 (PROJECT_OVERVIEW.md)
```

---

## 0. Current Critical Gate

```
TRACK A  Search / Canonical Evidence
         FROZEN · 공식 평가 종료 · test 재평가 금지

TRACK B  Current Submission Baseline
         R1-VAD0-QUALITY · READ-ONLY / NO PROMOTION · rollback 기준

TRACK C  Next-generation Whole-Video Report
         EVENT_EXTRACTION_SHADOW_V1   CLOSED / INCONCLUSIVE
                                      reason = W00 WINDOW_TECHNICAL_INVALID
         W00_DEGENERACY_FORENSIC_V1   NEXT / APPROVED · NO NEW QWEN INFERENCE

0.25fps semantic sufficiency          NOT ESTABLISHED
fixed 0.25fps as sole Event Map input REJECTED FOR NEXT SHADOW ARCHITECTURE
0.5fps                                PROVISIONAL WORKING DENSITY ONLY
                                      factual authority 아님 · production default 아님

production Event extraction           HOLD
Chapter / Highlight / Overview / Analysis / Conclusion   HOLD
current submission                    READ-ONLY
official test                         UNOPENED (별도 승인 없이 열지 않는다)
M9                                    HOLD
```

---

## 1. 프로젝트 목표

한국어 영상에서 두 가지 사용자 기능을 제공한다.

```
① Search / Moment Retrieval   자연어 질의로 장면을 찾고 timestamp와 근거를 돌려준다
② Whole-Video Report          영상 전체의 사건 흐름을 구조화해 report.hwpx를 만든다
```

두 기능은 같은 영상을 쓰지만 **generation pipeline을 분리한다.**

```
Search / Evidence pipeline    ≠    Report-generation pipeline
```

---

## 2. Architecture at a Glance

```
                              VIDEO
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
     TRACK A — SEARCH / EVIDENCE      TRACK C — WHOLE-VIDEO REPORT
     기존 확정 파이프라인                 차세대 탐색 파이프라인 (HOLD 다수)

     5초 segments                      local visual windows (48초)
     STT + VLM captions                Qwen3-VL video-only
           │                                  │
           ▼                                  ▼
     embedding index                    local visual events
           │                                  │
           ▼                                  ▼
     search / timestamp                overlap consistency
     evidence retrieval                       │
           │                                  ▼
           │                            event stitching        ← HOLD
           │                                  ▼
           │                              Event Map            ← HOLD
           │                                  ▼
           │                         Semantic Chapters         ← HOLD
           │                                  ▼
           │                              Highlights           ← HOLD
           │                                  ▼
           │                       Overview / Analysis         ← HOLD
           │                                  ▼
           │                              Conclusion           ← HOLD
           └──────────────► claim verification (보조 검증)
                                              ▼
                                  Integrated Report Object
                                              ▼
                                         report.hwpx
```

### TRACK B — Current Submission Baseline

TRACK B는 현재 제출본을 재현·rollback하기 위한 기존 V2.1 report pipeline이다.
Track C 실험은 Track B의 canonical·submission artifact·rollback state를 수정하지 않는다.

---

## 3. Cross-track Contracts

### 3-1. Search와 report generation을 분리한다

```
Track A의 STT·caption·embedding      검색과 evidence retrieval에 쓴다
Track C의 Local Event 생성            video-only visual input만 쓴다
STT                                  Track C report-generation input이 아니다
Track A canonical evidence            downstream auxiliary claim-verification layer
```

**canonical evidence의 현재 실측 지위** — truth도 oracle도 아니다.

```
discriminative coverage   LIMITED (EVIDENCE_RESOLUTION_V1: 지목 9행 중 8행 미해결 ·
                          지지 hit 17건 전부 caption(Qwen2.5-VL-3B 출력) ·
                          subtitle 채널 판정력 0건)
지지도 반증도 못 하면       UNRESOLVED를 유지한다
```

장기적으로 factual verification의 중요한 입력이지만 **검증된 능력 이상으로 표현하지 않는다.**

### 3-2. Boundary contract

```
frame/sample boundary  ≠  event boundary
local window boundary  ≠  event boundary
event boundary         ≠  chapter boundary
chapter boundary       ≠  report boundary
```

48초 local window를 쓰더라도 최종 보고서가 48초 단위로 끊기는 것이 아니다.

### 3-3. Factual authority

```
raw Qwen output                    factual authority 아님
local Event / Chapter synthesis    factual authority 아님
verified report claim              canonical evidence 제약을 받는다 (판별 못 하면 UNRESOLVED)
0.5fps · 0.25fps                   둘 다 truth 아님
evidence에 claim이 없다는 사실만으로 claim을 false로 확정하지 않는다
```

### 3-4. Report-stage separation

```
Event Map → Semantic Chapters → Highlights → Overview → Analysis → Conclusion
→ Claim Verification → Integration / Rendering
```

`Overview ≠ Analysis`, `Analysis ≠ Conclusion`. 각 단계는 별도 승인 사건이다.

---

## 4. 데이터 규모

```
영상 provenance 등재      42건        data/provenance/videos.json
work/ 디렉터리            20개        E2E fixture 4 · M8 사례 2 포함 —
                                     20편이 독립 색인 영상이라는 뜻이 아니다
질의가 붙은 영상           7편         dev 3 + test 4
AI Hub 보조 집합          194편       work_aihub/ (환경·모델 확증용)
질의                     135건       data/queries/queries.jsonl
  dev  96건 / 영상 3편    장면형 38 · 복합형 34 · 자막형 24
  test 39건 / 영상 4편    장면형 13 · 복합형 14 · 자막형 12
```

질의 유형: `자막형`(발화 중심) · `장면형`(시각 중심) · `복합형`(두 채널 결합).

---

## 5. TRACK A — Search / Canonical Evidence

### 5-1. 역할

```
① 자연어 장면 검색  ② timestamp retrieval  ③ canonical evidence 제공
④ Track C가 만든 report claim의 보조 factual verification (판별력 LIMITED)
```

Track A의 caption·STT를 Track C whole-video report의 generation input으로 쓰지 않는다.

### 5-2. 배포 확정 구성

```
캡션 VLM        Qwen2.5-VL-3B-Instruct · P0 · 4bit(NF4) · rep_penalty 1.1 · 3fps 표집
                캡션 프롬프트에 "화면 글자를 옮기지 말라" 지시 포함
자막 STT        faster-whisper-large-v3
보고서 LLM       Qwen2.5-7B-Instruct (Track B · 서버 GPU 전용)
임베더          KURE-v1 (질의·자막·캡션 동일 모델 강제)
융합 정규화      per-query z-score  (minmax 유의 열세 실측 · 2026-07-13 개정)
α               0.5   results/alpha_search_dev.json · tie_set [0.2, 0.4, 0.5]
                config에 없다 — CLI `--alpha` 주입
static_threshold 0 (캡션→자막 치환 off)
abstention       max(sub, cap) · τ = 0.55 (KURE-v1 종속 · 임베더 교체 시 재캘리브레이션)
```

`Qwen3-VL-8B-Instruct`는 Track C 진단·탐색 모델이고 배포 채택 모델이 아니다.
`Qwen3-VL-4B`는 후보 상태이며 채택되지 않았다.

### 5-3. Search pipeline

| 단계 | 모듈 | 역할 |
|---|---|---|
| M1 | `src/m1_preprocess.py` | mp4 → audio + 5초 segments |
| M2 | `src/m2_keyframe.py` | 대표 프레임 선택 · 정적 구간 fallback |
| M3 | `src/m3_generate.py` | STT + caption 생성 |
| M4 | `src/m4_index.py` | subtitle·caption 임베딩 (n, 1024) + text_hash |
| M5 | `src/m5_search.py` | 코사인 → z-score → α 가중합 + abstention |
| M6 | `src/m6_evaluate.py` | dev grid search → test 단발 평가 |
| M7 | `src/m7_demo.py` · `m7_webui.py` | 데모 UI |

실행 순서 불변식:

```
m3(재캡셔닝 포함) → m4 → m6
```

### 5-4. 확정 Search 성능 (test 39건 · α=0.5 · 비가역 자원)

```
지표         baseline(α=1.0 · 자막 단독)   proposed(융합)
hit@1              0.5641                   0.7692
hit@5              0.7692                   0.8718
MRR                0.6489                   0.8286
IoU@0.5 R@1        0.5641                   0.7692
```

유형별 — 이득의 출처와 대가:

```
자막형   0.9167 / 0.9583  →  0.8333 / 0.8802   소폭 손실
복합형   0.7857 / 0.8246  →  0.8571 / 0.8869
장면형   0.0000 / 0.1741  →  0.6154 / 0.7183   이득의 대부분
```

### 5-5. Test-contact policy

과거 공식 test 접촉 이력은 `DESIGN_SPEC` 8-6에 기록된 상태를 따른다.
**추가 test 평가·WVR test opening은 별도 승인 사건 없이 실행하지 않는다.**

---

## 6. TRACK B — Current Submission Baseline (V2.1)

M8 v1은 2026-08-27 공식 판정에서 생성 COMPLETE · acceptance FAIL(C1 파국 4/8편 ·
C2 median align 0.3311 · C3 max compression 7.00)이었고, 임계를 고치지 않고 구조를
재설계한 결과가 V2.1이다.

| 단계 | 역할 |
|---|---|
| S0 | 5초 ASR/VLM raw ingest |
| S1 | fixed-window 60초 episode |
| S2 | Qwen2.5-7B raw generation |
| S3 | content parse (계약 위반은 PARSE_CONTRACT_FAILURE로 기록) |
| S4 | grounding |
| S5 | canonical assembly (`aar_canonical.json` — 여기까지가 정본) |
| S6 | presentation (canonical 수정 금지) |
| S7 | MD/HWPX render (A2' 순수 Python OWPML) |

### 6-1. Current submission

```
arm            R1-VAD0-QUALITY
정책 3층        episode_content_v3_summary_only + STT_VAD0 + output_quality_v1
presentation   grouping 300초
artifact       runs/quality_candidate/S7/report.hwpx
sha256         5732075871fd…   tag submission-quality-2026-09-08
canonical      41 episode · fixed_window 60초 · segments sha aa008317…
status         READ-ONLY / NO PROMOTION
rollback       4e10aaab… (submission-vad0-2026-09-07) ·
               f874f643… (submission-ready-2026-09-03)
```

`M9`는 `split=="test"` 하드코딩이라 실행 자체가 test 접촉이다 — HOLD.
`semantic entailment` UNVERIFIED · `GRD-004` P1 WAIVED.

---

## 7. TRACK C — Next-generation Whole-Video Report

### 7-1. 목적

목적은 "10분 영상을 한 번에 Qwen에 넣는 것"이 아니다.

```
local visual understanding → temporally traceable local events → event stitching
→ global event structure → semantic chapters → whole-video overview
```

라는 **계층형 영상 이해 구조**를 만드는 것이다. 긴 raw-video context를 더 주는 것이
항상 더 좋은 전체 이해를 보장하지 않는다는 것이 WVR density 실험에서 확인됐다.

### 7-2. WVR에서 정리된 사실

```
C01 0.5fps / 300 frames            prefill OOM
0.25fps / 150 frames               capacity PASS (의미 충분성 아님)
0.25fps semantic sufficiency       NOT ESTABLISHED
180초 paired output                report-material divergence
48초 paired output                 divergence 재현 (P2·P3 MATERIAL_DIVERGENCE)
long-context-only-collapse 가설     NOT SUPPORTED
canonical evidence resolution      핵심 충돌 대부분 미해결 (BRANCH_C)
FRAME_ADJUDICATION_V1              SAMPLING_LOSS_CONFIRMED
                                   Q1·Q2 GENERATION_ERROR_NOT_SAMPLING ·
                                   Q3 DROP_FRAMES_CARRY_MATERIAL_INFORMATION
EVENT_EXTRACTION_SHADOW_V1         CLOSED / INCONCLUSIVE (W00 technical invalid)
```

**48초의 지위** — `technically executable / technically valid diagnostic window length`.
semantic stability는 **NOT validated**(SHORT_WINDOW_V1 = HOLD).

### 7-3. EVENT_EXTRACTION_SHADOW_V1 결과 (2026-09-09)

C01 전체를 48초 창 · 24초 stride로 tile해 24회 추론했다.

```
실행           24/24 · 재시도 0 · OOM 0 · 창당 24프레임 · 0.5fps 격자 정확
기술 검증       23창 WINDOW_VALID · W00 [0,48) WINDOW_INVALID
W00 증상       max_new_tokens 4096까지 start_sec=0/end_sec=0 형태를 반복 →
               JSON 미완결 → PARSE_FAILURE. cap 도달은 반복의 결과에 가깝다
겹침 identity   23/23 OK — 공유 12/12 · 픽셀 sha256 불일치 0 · bank 대조 576건 0
사건 판정       CLOSED / INCONCLUSIVE (reason WINDOW_TECHNICAL_INVALID — W00)
overlap semantic stability   NOT ADJUDICATED (부분 판정도 하지 않는다)
frame-grounding              NOT ADJUDICATED
blinded mapping              봉인 유지 (reveal 금지)
```

이 실패는 "Event architecture가 틀렸다"는 결과가 아니라, **전체영상 pipeline에서
local extractor 하나가 반복 생성에 빠졌을 때 어떻게 다룰지가 처음 드러난 failure mode**다.
전체영상 보고서로 가려면 반드시 해결해야 하는 문제로 취급한다.

### 7-4. 다음 사건 — W00_DEGENERACY_FORENSIC_V1

```
상태   NEXT / APPROVED · READ-ONLY DIAGNOSTIC · NO NEW QWEN INFERENCE
질문   W00 실패가 입력 builder/0초 boundary 특수처리 문제인지, 시각 내용에 의한
      model generation loop인지, 아니면 현재 artifact만으로 구분 불가인지
결과 분류  INPUT_PIPELINE_DEFECT · MODEL_OUTPUT_DEGENERACY · MIXED · UNRESOLVED
금지   prompt 수정 · W00 재실행 · token cap 증가(4096→8192 승인되지 않았다) ·
      W01~W23 raw·packet 삭제 · mapping reveal
```

`4096 → 8192` 상향은 승인되지 않았다 — V1B에서 "토큰을 더 주면 반복이 길어지는" 유형을
이미 봤기 때문이다.

### 7-5. 다음 shadow architecture 방향 (설계 목표 · 미승인)

```
VIDEO → short overlapping local windows → 0.5fps provisional local sampling
      → frame-grounded Local Events → overlap consistency check
      → event stitching → Event Map
```

`support_frame_times`(event가 스스로 근거 프레임 시각을 내는 schema)는 **후속 변형
후보**이며 현재 프롬프트·schema에 포함되지 않는다(`SAMPLING_DIAG_PROMPT_V2` 동결).
frame grounding은 사전등록된 소수 overlap의 실제 공유 프레임을 reviewer가 event
sequence와 대조하는 방식으로만 한다.

속도·중복 계산량은 이 단계의 기각 사유가 아니다 — semantic stability를 우선한다.

---

## 8. Shadow gate 어휘 (SHADOW 계열 공통)

overlap 판정(reviewer 전용):

```
STABLE · GRANULARITY_SHIFT · MATERIAL_DIVERGENCE · UNRESOLVED
```

frame-grounding 판정(reviewer 전용):

```
SUPPORTED · PARTIALLY_SUPPORTED · UNSUPPORTED · FRAMES_INSUFFICIENT
```

사건 판정 우선순위:

```
기술 무효 → INCONCLUSIVE  >  MATERIAL_DIVERGENCE → HOLD  >
UNRESOLVED → INCONCLUSIVE  >  전부 통과 → PASS 후보
```

gate 범위는 항상 분리해 적는다.

```
overlap stability   측정한 overlap 수 / 전체
frame grounding      사전등록 audit overlap 수 / 전체
```

PASS가 나와도 금지되는 주장:

```
0.5fps universally sufficient · 0.5fps factual authority
all events are frame-grounded · entire Event Map factuality verified
production Event extraction approved · whole-video understanding solved
Overview quality proven · report factuality proven
```

---

## 9. 방법론 규율

```
①  test 재평가 금지 · 모든 튜닝은 dev 전용
②  현행 submission READ-ONLY
③  prereg → commit → execution
④  결과 확인 후 parameter/threshold/gate/판정 어휘 변경 금지
⑤  one-variable incident discipline (또는 변경 없음을 명시)
⑥  raw persist before parse
⑦  provenance·hash 기록
⑧  full suite + mutation + clean tree
⑨  오염된 run은 삭제가 아니라 INVALID provenance로 보존
⑩  Qwen output ≠ factual authority
⑪  자동 matcher ≠ semantic authority
⑫  실패 arm 즉석 retry 금지 · silent fallback 금지
⑬  캡션 수동 편집 금지 · 라벨 작성 시 검색 결과 참조 금지
⑭  submission promotion·test opening은 별도 review 사건
```

---

## 10. 어디를 보면 되는가

```
재시작           docs/작업현황_*.md 최신판 → docs/README.md(문서 지도)
수치 최종 출처    DESIGN_SPEC.md · results/*.json · runs/**/[결과].json
제출 상태        docs/finalization/V2_1_SUBMISSION_QUALITY_PROMOTION_2026-09-08.md
사전등록         docs/preregistration/  (내용을 고치지 않는 문서 · 정정은 errata)
probe 결과       docs/probes/
검증 절차        .claude/skills/pipeline-verify · .claude/skills/gpu-batch
서버 접속값       SERVER_LOCAL.md (git 미추적 · 문서에는 자리표시자만)
```

---

## 11. 현재 정지선

승인된 범위는 `W00_DEGENERACY_FORENSIC_V1`(읽기 전용 · GPU 없음)까지다.
다음은 별도 reviewer approval 전까지 HOLD.

```
SHADOW_V1B 또는 다른 재실행 · token cap 상향 · prompt 수정
production Event extraction · Semantic Chapters · Highlights
Overview · Analysis · Conclusion · Integrated report generation
submission promotion · official test opening · M9
```

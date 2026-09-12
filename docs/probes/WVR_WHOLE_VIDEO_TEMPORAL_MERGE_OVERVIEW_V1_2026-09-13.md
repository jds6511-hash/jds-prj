# WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1 — 실행 결과 (2026-09-13)

사전등록: `docs/preregistration/WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1_2026-09-13.md`

```
상태   EXECUTED / REVIEW_PENDING
```

**이 문서는 관측값만 적는다.** Overview 품질 PASS · semantic completeness ·
chunk 관찰 우열 · 다음 단계 진행 여부는 전부 reviewer 결정이다(사전등록 §10).

---

## A. 실행 요약

```
merge          로컬 · 결정적 · 추론 0회
synthesis      kixlab2 · RTX 4090 (실행 직전 유휴 40MiB) · 1회
격리 클론      /ssd/daeseok/jds-prj-chunkov-v2 (기존 clone 재사용)
code_git_head  cd9f118a959bb7889cc0eb778481e7a69884bb8b
모델           Qwen/Qwen3-VL-8B-Instruct
               revision 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
호출           runtime.synthesize — 텍스트 전용, 영상 프레임 없음
               (scripts/wvr_video_overview_preview_run.py:107-113)
생성 파라미터  do_sample False · num_beams 1 · max_new_tokens 1024
elapsed        18.188초 (추론 10.329초) · peak VRAM 17,031 MiB
```

```
new visual inference   0
new STT inference      0
synthesis inference    1
retry                  0
```

---

## B. Gate G1~G10 — 10/10 PASS (synthesis 전)

```
G1  C01~C05 source 해시가 사전등록 §1과 일치       PASS
G2  entry 시각이 source 창 범위 안에서 파생        PASS
G3  duplicate source-time exposure 제거            PASS (entry 간 겹침 0초)
G4  [0, 2424) temporal coverage · 빈틈 0           PASS
G5  source lineage 완전                            PASS
G6  deterministic merge — 2회 산출물 동일          PASS
G7  no visual inference                            PASS
G8  no STT inference                               PASS
G9  official test 경로 미접근                      PASS
G10 M9 미호출                                      PASS
```

**G9 초기 오탐 1건을 기록한다.** 첫 실행에서 `runs/wvr_whole_video_merge_v1/`가
아직 없어 mtime 기준이 0이 되는 바람에 `results/eval_test.json` ·
`src/m9_report_eval.py`가 "접근됨"으로 걸렸다. 기준을 프로세스 시작 시각으로
고쳤고 실제 접근은 없었다. 두 파일은 읽지도 쓰지도 않았다.

---

## C. Timeline 계측

```
timeline entry count                    96
temporal coverage                       2424.0초 (빈틈 0)
duplicate coverage before normalization  3144.0초
duplicate coverage after normalization      0.0초
source lineage completeness             96 / 96 (100%)
terminal remainder                      [2424.0, 2424.186485) · 0.186485초 · entry 없음
activity run (압축 후)                   36
```

chunk별 entry 기여:

```
C01 24 · C02 19 · C03 19 · C04 19 · C05 15
```

### 중복 제거가 적용된 방식 (사전등록 §3 그대로)

```
window overlap   창 i는 [s_i, s_i+24) 를 대표하고, 마지막 창만 [s_n-1, e_n-1)
chunk overlap    절대 시각 t의 소유자 = t를 포함하는 최저 index chunk
소유 구간        C01 [0,600) · C02 [600,1080) · C03 [1080,1560) ·
                 C04 [1560,2040) · C05 [2040,2424)
```

chunk stride 480 = 24 × 20 이므로 소유 경계(600 · 1080 · 1560 · 2040)가 전부
창 경계와 일치했다 — **구간을 잘라낸 곳이 없다.** 소유 밖 창은 통째로 버려졌다.

**NONOVERLAP은 semantic winner selection이 아니다.** duplicated temporal
exposure를 제거하기 위한 report-input normalization이다.
chunk 소유도 내용이 아니라 index로만 정했다.

### lineage

모든 entry가 `source_chunk` · `source_window`(segment_id + 원래 창 구간) ·
`source_artifact_sha256`(해당 chunk의 summaries·segments 해시)를 갖는다.
`[0, 2424)` 안의 모든 시각이 정확히 하나의 entry로 추적된다(G4·G5).

`runs/wvr_whole_video_merge_v1/timeline_lineage.json` 에 96건 전량이 있다.

---

## D. SHORT_OVERVIEW

```
음식 준비와 조리가 반복적으로 이루어지며, 이와 함께 구매 또는 둘러보기, 식사,
외출 준비, 포장 작업, 이동 등이 순차적으로 전환됩니다. 활동은 주기적으로 음식
관련 작업으로 돌아가며, 이동과 구매가 빈번하게 삽입되어 일상적인 흐름을 이룹니다.
마지막으로 정리 작업과 외출 준비가 종료 단계로 나타납니다.
```

## E. DETAILED_OVERVIEW

```
음식 준비 및 조리가 처음으로 시작되며, 이후 구매 또는 둘러보기로 전환됩니다.
식사 후 다시 구매 또는 둘러보기로 넘어가며, 이동과 포장 작업이 반복적으로
삽입되어 활동의 흐름을 이끕니다. 중간에 의류 작업 및 수선이 잠시 등장하지만,
음식 관련 활동이 다시 중심이 됩니다. 외출 준비와 정리 작업이 종료 단계로
나타나며, 마지막으로 음식 준비 및 조리, 식사가 반복적으로 마무리됩니다.
```

**이것은 2424초 전체 영상의 Overview다** — C01 preview가 아니다.
`temporal_coverage 2424.0초 · terminal remainder 0.186485초`.

---

## F. §6 context 보충 금지 — 기계적 확인

판정이 아니라 문자열 검사 결과다.

```
금지 맥락 어휘 출현        0건
  검사 어휘: 병원 · 퇴원 · 직장 · 출근 · 근무 · 휴가 · 시장 방문 · 계획 ·
             의도 · 감정 · 진료 · 약 · 가족 · 친구 · 일정
구간/window 식별자 노출    0건 (S** · W** · G*** · P** · seg#N)
사용된 활동 label          동결 label 집합 8종만 사용
                           구매 또는 둘러보기 · 식사 · 외출 준비 · 음식 준비 및 조리 ·
                           의류 작업 및 수선 · 이동 · 정리 작업 · 포장 작업
SHORT 문장 수              3
DETAILED 단락 수           1
context_inference_injected false
```

source의 `OBSERVED_CHANGE`가 전부 비어 있었고 **빈 채로 넘겼다**(§6).
synthesis 입력은 `BROAD_ACTIVITY_SEQUENCE` 36개와 빈 `OBSERVED_CHANGES` 뿐이다.

*문자열 검사는 관찰되지 않은 맥락이 없음을 증명하지 않는다 — 검사한 어휘가
없다는 것만 말한다. semantic 판정은 reviewer 몫이다.*

---

## G. 동결 유지 확인

```
synthesis 프롬프트   wvr_video_overview_preview_v2.SYNTHESIS_PROMPT_TEMPLATE 그대로
압축                 ov.compress_activity_timeline 그대로
파싱                 ov.parse_overview 그대로
모델 · revision      불변
```

실행기는 프롬프트를 timeline에서 **다시 만들어 파일과 동일한지 확인한 뒤에만**
호출한다. 이미 산출물이 있으면 거부한다(retry 금지).

새 visual prompt · 새 sampling · 새 stitching 연구 · Event Map · Semantic Chapter ·
Boundary Candidate 전부 손대지 않았다. C01~C05 재실행 없음.

---

## H. Baseline 보호

```
runs/wvr_video_overview_preview_v2/   읽기만 · 해시 불변 (G1)
runs/wvr_chunk_overview_v2/           읽기만 · 해시 불변 (G1)
runs/rei_c01/ · runs/rei_c01_beta_v3/ · runs/v3_paired/   미접촉
config.yaml · work/ · work_full/ · Track A 인덱스         미접촉
official test 미접근 (G9) · M9 미호출 (G10)
```

쓰기는 `runs/wvr_whole_video_merge_v1/` 에만 일어났다.

---

## I. 사전등록 대비 편차

```
없음. §3 중복 제거 규칙을 동결한 그대로 적용했고, synthesis는 gate PASS 후 1회다.
```

---

## J. 산출물

```
runs/wvr_whole_video_merge_v1/
    whole_video_activity_timeline.json     entry 96
    whole_video_activity_timeline.md       사람이 읽는 표
    timeline_lineage.json                  lineage 96건
    merge_gate.json                        G1~G10
    whole_video_synthesis_prompt.txt       2,889자
    whole_video_synthesis_input.json       압축 입력 + 프롬프트 해시
    whole_video_overview_raw.txt           모델 원문 (파싱 전 저장)
    whole_video_overview_result.json       SHORT / DETAILED
    whole_video_synthesis_record.json      provenance · 추론 수 · retry
src/wvr_whole_video_merge_v1.py
scripts/wvr_whole_video_merge_v1_build.py · wvr_whole_video_synthesize_v1.py
tests/test_wvr_whole_video_merge_v1.py     20건
```

---

## K. executor가 결정하지 않은 것

```
Overview 품질 PASS · semantic completeness · chunk 관찰 우열
다음 단계(Analysis / Conclusion / β-v3 report / HWPX) 진행 여부
M9 실행 여부 · official test 개방 여부
```

---

## L. 상태

```
WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1
EXECUTED / REVIEW_PENDING
```

---

## M. Reviewer 판정 (2026-09-13)

```
WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1
CLOSED / WHOLE_VIDEO_OVERVIEW_HOLD
```

**technical temporal merge는 PASS로 인정한다.**

```
C01~C05 source integration      PASS
timeline entries                96
coverage                        [0, 2424)
temporal gap                    0
duplicate after normalization   0
lineage                         96/96
synthesis inference             1
retry                           0
visual/STT inference            0
gate                            G1~G10 PASS
```

따라서 이후 다음 연구를 **재개하지 않는다.**

```
Event Map · Semantic Chapter · Boundary Candidate
visual sampling 연구 · chunk/window geometry 변경 · C01~C05 재실행
```

### HOLD 사유 — final Overview의 semantic consistency

**1. SHORT / DETAILED 종료부 불일치**

```
SHORT     마지막으로 정리 작업과 외출 준비가 종료 단계
DETAILED  마지막으로 음식 준비 및 조리, 식사가 반복적으로 마무리
```

같은 timeline을 요약하면서 마지막 흐름 설명이 일치하지 않는다.

**2. source보다 강한 해석 표현**

```
빈번하게 삽입되어 · 일상적인 흐름 · 활동의 흐름을 이끕니다 · 음식 관련 활동이 중심
```

broad activity timeline에서 직접 보장되지 않는 일반화일 수 있다.

### 후속 사건 승인

```
WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2
```

frozen 96-entry timeline을 바꾸지 않고 **최종 Overview synthesis만** 더 보수적이고
내부적으로 일관되게 만든다. 새 visual inference / STT / timeline merge 금지.

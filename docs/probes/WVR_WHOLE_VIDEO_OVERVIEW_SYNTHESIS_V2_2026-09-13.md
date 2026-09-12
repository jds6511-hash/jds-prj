# WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2 — 실행 결과 (2026-09-13)

사전등록: `docs/preregistration/WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2_2026-09-13.md`

```
상태   EXECUTED / REVIEW_PENDING
```

**이 문서는 관측값만 적는다.** 최종 Overview 품질 PASS/HOLD · semantic 정확성 ·
다음 단계 진행 여부는 전부 reviewer 결정이다(사전등록 §10).

---

## A. 실행 요약

```
호스트          kixlab2 · RTX 4090 (실행 직전 유휴 40MiB)
격리 클론       /ssd/daeseok/jds-prj-chunkov-v2
code_git_head   bfe772a34c765b2e31ccfdb75deb8569d78637eb
모델            Qwen/Qwen3-VL-8B-Instruct
                revision 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
호출            runtime.synthesize — 텍스트 전용, 영상 프레임 없음
생성 파라미터   do_sample False · num_beams 1 · max_new_tokens 1024
elapsed         16.422초 · peak VRAM 17,250 MiB
```

```
canonical flow inference   0      ← 결정적 계산
synthesis inference        2      (DETAILED 1 + SHORT 1)
visual inference           0
STT inference              0
timeline regeneration      0
retry                      0
```

frozen input 해시 확인 후 실행했다.

```
whole_video_activity_timeline.json   읽기만 · 96 entry 불변
timeline_lineage.json                읽기만 · 불변
merge_gate.json                      PASS 확인 후 시작
```

---

## B. CANONICAL_FLOW (결정적 · 추론 0회)

```
source timeline entry        96
phase                        46
transition                   45
first phase                  음식 준비 및 조리 · 구매 또는 둘러보기
final phase                  식사            [2352.0, 2424.0)
repeated activities (7)      구매 또는 둘러보기 · 식사 · 외출 준비 ·
                             음식 준비 및 조리 · 의류 작업 및 수선 · 이동 · 포장 작업
non-repeated activities (1)  정리 작업
```

phase 등장 횟수:

```
구매 또는 둘러보기 24 · 음식 준비 및 조리 21 · 식사 15 · 이동 7 ·
외출 준비 5 · 포장 작업 4 · 의류 작업 및 수선 3 · 정리 작업 1
```

phase가 timeline을 빈틈 없이 덮는다(첫 phase 0.0 · 마지막 phase 끝 2424.0 ·
entry_count 합 96). 테스트 `test_wvr_sv2_08`이 이를 강제한다.

**final phase는 마지막 entry들이 결정했다** — 중간부 패턴을 보고 추정하지 않았다.

---

## C. DETAILED_OVERVIEW

```
음식 준비 및 조리와 구매 또는 둘러보기가 먼저 이어진다. 이후 음식 준비 및 조리가
다시 나타나며, 식사가 추가된다. 식사가 끝나면 다시 구매 또는 둘러보기가 나타나고,
이동과 외출 준비, 포장 작업, 의류 작업 및 수선 등이 순차적으로 이어진다.
영상은 식사로 끝난다.
```

## D. SHORT_OVERVIEW

```
음식 준비 및 조리와 구매 또는 둘러보기가 먼저 이어진다.
다시 음식 준비 및 조리가 나타나며 식사가 추가된다.
식사 후 구매 또는 둘러보기가 다시 나타나고, 이동과 외출 준비, 포장 작업,
의류 작업 및 수선 등이 순차적으로 이어진다.
영상은 식사로 끝난다.
```

SHORT는 CANONICAL_FLOW를 보지 않았다 — **DETAILED만 입력으로 받았다.**

---

## E. Machine check — 8/8 PASS

```
short_activity_set ⊆ detailed_activity_set          PASS  (short_only 0건)
final_phase_short == final_phase_detailed            PASS  (양쪽 모두 {식사})
final_phase_detailed == canonical final_phase        PASS  (canonical {식사})
unknown label count == 0                             PASS
window/chunk identifier exposure == 0                PASS
overclaim term 출현 == 0                             PASS
context term 출현 == 0                               PASS
repetition claim 범위                                PASS (계측: overclaim 0건)
```

판정 방식은 사전등록 §7에 동결한 그대로다.

```
activity_set(text)        동결 label 8종 중 문자열로 나타나는 것
final_phase_labels(text)  text의 마지막 문장에 나타나는 동결 label 집합
문장 분리                 [.!?] 뒤 공백 또는 개행
```

**이 검사는 semantic 정확성을 증명하지 않는다.** 문자열 수준의 일관성만 본다.

---

## F. V1 대비 — reviewer가 지적한 두 문제

**1. 종료부 불일치 (해소됨, 기계 확인)**

```
                 SHORT 종료 활동        DETAILED 종료 활동     canonical final phase
V1               정리 작업 · 외출 준비   음식 준비 및 조리 · 식사   식사
V2               식사                    식사                     식사
```

V1은 SHORT·DETAILED가 서로 달랐고 **둘 다 canonical final phase와도 달랐다.**
V2는 셋이 일치한다.

**2. source보다 강한 해석 표현 (출현 0건, 기계 확인)**

```
V1에서 관측된 표현   빈번하게 삽입되어 · 일상적인 흐름 ·
                     활동의 흐름을 이끕니다 · 음식 관련 활동이 중심
V2 출현              0건 (검사 어휘 12종: 빈번 · 주기적 · 중심이 된다 · 중심이 ·
                     중심으로 · 흐름을 이끄 · 일상적 · 주요한 · 핵심적 ·
                     대부분 · 지속적으로 · 전반적으로)
```

---

## G. 관측 — DETAILED가 언급하지 않은 activity 1종

```
canonical activity 종류   8
DETAILED 언급             7
SHORT 언급                7
미언급                    정리 작업  (phase 등장 1회 · 유일한 non-repeated activity)
```

사전등록은 **전 activity 언급을 요구하지 않았다** — 요구한 것은 어휘 제한 ·
종료부 일치 · SHORT ⊆ DETAILED다. 따라서 규칙 위반이 아니다.
다만 활동 1종이 최종 Overview에 나타나지 않는다는 사실 자체는 기록한다.

**원인 귀속을 하지 않는다** — 프롬프트의 단락 수 제한 때문인지, 1회 등장이라
압축에서 빠진 것인지, 모델 선택인지는 이번 1회 실행으로 구분되지 않는다.

기타 형식 계측:

```
DETAILED 문장 수   4 (1단락)
SHORT 문장 수      4
```

---

## H. 동결 유지 확인

```
timeline               수정 0 · 재생성 0 · 해시 불변
C01~C05               미접촉
Event Map · Semantic Chapter · Boundary Candidate   미접촉
visual sampling · chunk/window geometry              미접촉
모델 · revision        불변
```

실행기는 merge gate가 PASS가 아니면 시작하지 않고, 산출물이 이미 있으면
거부한다(retry 금지). DETAILED 프롬프트 payload에는 초 단위 시각이 들어가지
않는다(테스트 `test_wvr_sv2_10`).

---

## I. Baseline 보호

```
runs/wvr_whole_video_merge_v1/   읽기만
runs/wvr_chunk_overview_v2/ · runs/wvr_video_overview_preview_v2/   미접촉
runs/rei_c01/ · runs/rei_c01_beta_v3/ · runs/v3_paired/             미접촉
config.yaml · work/ · work_full/ · Track A 인덱스                   미접촉
official test 미접근 · M9 미호출
```

쓰기는 `runs/wvr_overview_synthesis_v2/` 에만 일어났다.

---

## J. 사전등록 대비 편차

```
없음. §2 계층 · §3 CANONICAL_FLOW 규칙 · §4 표현 규칙 · §5 종료부 규칙 ·
§6 실행 조건을 동결한 그대로 적용했다. 추론 2회, retry 0.
```

---

## K. 산출물

```
runs/wvr_overview_synthesis_v2/
    canonical_flow.json · canonical_flow.md       phase 46
    detailed_prompt.txt · detailed_raw.txt
    short_prompt.txt · short_raw.txt
    overview_result.json                          CANONICAL / DETAILED / SHORT
    machine_checks.json                           8/8 PASS
    synthesis_record.json                         provenance · 추론 수 · retry
src/wvr_overview_synthesis_v2.py
scripts/wvr_overview_synthesis_v2_run.py
tests/test_wvr_overview_synthesis_v2.py           21건
```

---

## L. executor가 결정하지 않은 것

```
최종 Overview 품질 PASS/HOLD · semantic 정확성
"정리 작업" 미언급을 결함으로 볼지 여부
다음 단계(Analysis / Conclusion / β-v3 report / HWPX) 진행 여부
M9 실행 여부 · official test 개방 여부
```

---

## M. 상태

```
WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2
EXECUTED / REVIEW_PENDING
```

# WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2 사전등록 (2026-09-13)

승인: reviewer 판정 `WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1
CLOSED / WHOLE_VIDEO_OVERVIEW_HOLD` 의 후속 사건 승인.

**이 문서는 실행 전에 커밋한다. 결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

선행 문서:
`docs/probes/WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1_2026-09-13.md` §M ·
`docs/preregistration/WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1_2026-09-13.md`

---

## 0. 이 사건이 답하는 질문

```
frozen 96-entry whole-video timeline을 바꾸지 않고,
최종 Overview synthesis만 더 보수적이고 내부적으로 일관되게 만들 수 있는가.
```

**timeline merge를 다시 하지 않는다. 새 visual inference · STT를 하지 않는다.**

답하지 않는 질문: 최종 Overview 품질 PASS. reviewer가 실제 문장을 보고 결정한다.

---

## 1. Frozen input (변경 금지)

```
runs/wvr_whole_video_merge_v1/whole_video_activity_timeline.json
runs/wvr_whole_video_merge_v1/timeline_lineage.json
```

96 entry · timestamp · content · hash를 바꾸지 않는다. 읽기만 한다.

merge gate 산출물(`merge_gate.json`)이 `PASS`가 아니면 시작하지 않는다.

---

## 2. 계층 구조 (동결)

SHORT와 DETAILED를 독립적으로 생성하지 않는다.

```
frozen timeline
  → CANONICAL_FLOW      결정적 · 추론 0회
    → DETAILED_OVERVIEW  생성 1회 · CANONICAL_FLOW만 본다
      → SHORT_OVERVIEW   생성 1회 · DETAILED_OVERVIEW만 본다
```

**SHORT는 DETAILED의 압축본이다.** SHORT가 DETAILED에 없는 활동·해석·종료
상태를 추가하면 실패로 기록한다.

### CANONICAL_FLOW를 모델이 만들지 않는 이유

activity · 시간 순서 · 반복 여부 · 관찰 가능한 전환은 전부 timeline에서
**계산되는 값**이다. 계산으로 되는 것을 생성에 맡기면 그 단계에서 일반화가
들어온다. 따라서 이 단계는 추론 0회의 결정적 변환으로 동결한다.

---

## 3. CANONICAL_FLOW 규칙 (동결)

```
phase        연속한 entry 중 activity 집합이 동일한 구간을 하나로 묶는다
             (집합은 entry의 broad_activity 리스트를 순서 보존 dedup한 것)
phase 필드   phase_index · activities · start_sec · end_sec · entry_count
first phase  phases[0].activities
final phase  phases[-1].activities  ← 마지막 entry들이 결정한다
반복 여부    phase 등장 횟수 >= 2 인 activity만 repeated_activities에 넣는다
전환         인접 phase 쌍 중 activities가 다른 것만 기록한다
```

허용 정보는 위가 전부다. **의도 · 목적 · 감정 · 장소 추론 · 생활 패턴 해석 ·
중요도 임의 판정을 계산하지 않는다.**

---

## 4. 표현 규칙 (동결)

프롬프트에 금지어로 명시하고, 출력에서 출현 횟수를 계측한다.

```
금지 표현   빈번 · 주기적 · 중심이 된다/중심이/중심으로 · 흐름을 이끄 ·
            일상적 · 주요한 · 핵심적 · 대부분 · 지속적으로 · 전반적으로
금지 맥락   병원 · 퇴원 · 직장 · 출근 · 근무 · 휴가 · 시장 방문 · 계획 ·
            의도 · 감정 · 진료 · 가족 · 친구 · 일정 · 목적 · 이유
금지 노출   S** · W** · G*** · P** · C0* · seg#N · entry N · "N초"
어휘        timeline의 broad activity 표현을 그대로 쓴다. 새 활동 이름 금지.
반복 주장   repeated_activities에 있는 activity에만 허용한다
중요도      어떤 활동이 더 중요하다고 쓰지 않는다
```

---

## 5. 종료부 규칙 (동결)

```
DETAILED의 마지막 문장은 final_phase_activities에 있는 활동만으로 쓴다.
SHORT의 종료 활동은 DETAILED의 종료 활동과 같아야 한다.
전체 중간부 패턴을 보고 마지막 장면을 추정하지 않는다.
```

동결 시점의 실측값(결정적 계산 결과, 생성 전에 기록한다):

```
final_phase_activities   ["식사"]
final_phase_span         [2352.0, 2424.0)
```

*참고: V1의 SHORT("정리 작업과 외출 준비")와 DETAILED("음식 준비 및 조리, 식사")는
둘 다 이 값과 다르다. 그 불일치가 HOLD 사유였다.*

---

## 6. Execution (동결)

```
모델          Qwen/Qwen3-VL-8B-Instruct
              revision 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
호출          runtime.synthesize — 텍스트 전용, 영상 프레임 없음
생성          do_sample False · num_beams 1 · max_new_tokens 1024
추론 횟수     DETAILED 1회 + SHORT 1회 = 2회
              (CANONICAL_FLOW는 0회)
visual inference 0 · STT inference 0 · timeline regeneration 0
retry         금지. 실패하면 실패로 기록한다.
```

이미 산출물이 있으면 거부한다.

---

## 7. Machine check (기록 대상 · 판정 아님)

```
short_activity_set ⊆ detailed_activity_set
final_phase_short == final_phase_detailed
final_phase_detailed == canonical final_phase        (종료부 규칙 §5)
unknown label count == 0
window/chunk identifier exposure == 0
overclaim term 출현 == 0
context term 출현 == 0
```

판정 방식도 동결한다.

```
activity_set(text)         동결 label 8종 중 text에 문자열로 나타나는 것
final_phase_labels(text)   text의 **마지막 문장**에 나타나는 동결 label 집합
문장 분리                  [.!?] 뒤 공백 또는 개행
unknown label count        동결 label이 하나도 없으면 1, 있으면 0
                           (임의 명사를 activity로 판정할 수단이 없다 —
                            보수적 정의다. 과잉 주장을 하지 않는다.)
```

**이 검사는 semantic 정확성을 증명하지 않는다.** 문자열 수준의 일관성만 본다.

---

## 8. 금지 (재확인)

```
timeline 수정 · timeline 재생성 · 새 visual inference · 새 STT
C01~C05 재실행 · Event Map · Semantic Chapter · Boundary Candidate
visual sampling 연구 · chunk/window geometry 변경
결과를 보고 §3~§5 규칙 변경 · 좋은 결과를 위한 retry
executor의 최종 Overview 품질 PASS 선언
```

---

## 9. 필수 산출물

```
runs/wvr_overview_synthesis_v2/canonical_flow.json
runs/wvr_overview_synthesis_v2/canonical_flow.md
runs/wvr_overview_synthesis_v2/detailed_prompt.txt · detailed_raw.txt
runs/wvr_overview_synthesis_v2/short_prompt.txt · short_raw.txt
runs/wvr_overview_synthesis_v2/overview_result.json      CANONICAL/DETAILED/SHORT
runs/wvr_overview_synthesis_v2/machine_checks.json
runs/wvr_overview_synthesis_v2/synthesis_record.json
docs/probes/WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2_2026-09-13.md
```

---

## 10. executor가 결정하지 않는 것

```
최종 Overview 품질 PASS/HOLD · semantic 정확성
다음 단계(Analysis / Conclusion / β-v3 report / HWPX) 진행 여부
M9 실행 여부 · official test 개방 여부
```

executor 보고 상태는 다음까지만이다.

```
WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2
EXECUTED / REVIEW_PENDING
```

그리고 STOP한다.

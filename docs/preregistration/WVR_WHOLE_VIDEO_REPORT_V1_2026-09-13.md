# WVR_WHOLE_VIDEO_REPORT_V1 사전등록 (2026-09-13)

승인: reviewer 판정 `WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2
CLOSED / WHOLE_VIDEO_OVERVIEW_PASS` 의 `NEXT STAGE APPROVED`.

**이 문서는 실행 전에 커밋한다. 결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

선행 문서:
`docs/probes/WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2_2026-09-13.md` §N ·
`docs/preregistration/WVR_WHOLE_VIDEO_OVERVIEW_SYNTHESIS_V2_2026-09-13.md` ·
`docs/preregistration/WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1_2026-09-12.md`

---

## 0. 목적

```
Whole-video Analysis → Whole-video Conclusion → β/v3 report integration → HWPX
```

**이제 목적은 architecture probe가 아니라 실제 최종 보고서 생성이다.**
새 side experiment를 만들지 않는다. Analysis/Conclusion을 완벽하게 만들기 위한
반복 prompt campaign을 하지 않는다. **첫 결과를 생성하고 실제 문장을 보고한다.**

---

## 1. Overview branch freeze (읽기 전용)

```
runs/wvr_whole_video_merge_v1/whole_video_activity_timeline.json
runs/wvr_whole_video_merge_v1/timeline_lineage.json
runs/wvr_overview_synthesis_v2/canonical_flow.json
runs/wvr_overview_synthesis_v2/overview_result.json
```

수정·재생성하지 않는다. 해시를 gate에서 확인한다.
**새 Overview prompt tuning · 새 visual inference · 새 STT inference 금지.**
Event Map / Chapter / Boundary 연구 재개 금지.

---

## 2. Analysis (생성 1회)

### 입력 우선순위 (동결)

```
1. CANONICAL_FLOW          phase 열 · 반복 여부 · 전환 · 종료 phase
2. DETAILED_OVERVIEW
3. whole_video_activity_timeline  (집계 통계로만 — 개별 시각을 본문에 쓰지 않는다)
```

### 허용

```
활동의 반복 여부 · 시간적 전환 · 여러 activity group의 배치
영상 전반에서 관찰되는 구조적 패턴
```

### 금지

```
의도 · 감정 · 생활 습관 · 장소/상황 추정 · 원인·목적 추론 · 관찰되지 않은 맥락
새로운 사건 발명
```

**Analysis는 새로운 사건을 발명하지 않는다.**

표현 규칙은 Overview V2 §4와 같은 목록을 그대로 쓴다(overclaim 12종 ·
context 16종 · 식별자 노출 금지 · 초 단위 시각 금지).

---

## 3. Conclusion (생성 1회)

```
입력   SHORT_OVERVIEW + DETAILED_OVERVIEW + ANALYSIS
```

**Conclusion은 새 evidence를 추가하지 않는다.** Overview와 Analysis를 최종적으로
압축·종합한다. 종료 활동은 Overview·Analysis와 같아야 한다.

---

## 4. β/v3 report input adapter (동결)

기존 β/v3 engine source를 **수정하지 않는다.** 연결은 **report input layer**에서만 한다.

### 4-1. 24초 격자 정규화 (동결)

`common.load_segments` 는 `start == idx * seg_len_sec` 를 강제한다. frozen timeline
96 entry 중 **5개가 48초**(각 chunk의 마지막 소유 entry)이므로 그대로는 통과하지
못한다. 따라서 48초 entry를 **앞뒤 24초 둘로 나눈다.**

```
24초 entry     그대로 1개
48초 entry     [s, s+24) 와 [s+24, s+48) 두 개로 나눈다
               두 조각은 같은 broad_activity · 같은 source lineage를 갖는다
결과           101 segment × 24초 = 2424.0초 · start == idx*24 만족
```

내용을 바꾸지 않는다. **시간 격자만 맞춘다.** 새 관찰을 만들지 않는다.

동결 시점 실측: 48초 entry 5개 = index 23 · 42 · 61 · 80 · 95
(각각 C01~C05의 마지막 소유 entry). 96 + 5 = 101.

### 4-2. caption (동결)

```
caption = " · ".join(broad_activity)      원문 label을 재작성하지 않는다
비어 있으면 "(관측 요약 없음)"
```

### 4-3. subtitle (동결)

새 STT를 하지 않는다. 기존 M3 STT를 결정적으로 재집계한다.

```
source   work_full/full_xekZO4n4QuE/segments.json  (read-only, 제출 baseline 입력)
         sha256 aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92
규칙     rei_c01_adapter.aggregate_subtitle 그대로 —
         양의 겹침(접점 제외)만 포함 · start 오름차순 · 단일 공백 join
         문자열 수정·정규화·요약 금지
```

### 4-4. engine 실행 (동결)

```
python scripts/v2_1_b2_orchestrate.py
  --segments <adapter segments.json> --run-dir <run>/b2run
  --config configs/wvr_whole_video_beta_v3.yaml
  --video-id wvr_whole_video --run-id wvr-whole-video-v1
  --producer-version <adapter commit> --model-id Qwen/Qwen2.5-7B-Instruct
  --contract v3 --poll-gpu --clean
```

`--max-new-tokens` · `--window-sec` 는 인자를 주지 않는다(기본값 512 / 60.0).
config는 `configs/rei_c01_beta.yaml` 에서 `paths.work`·`paths.results` 만 바꾼
사본이다(`seg_len_sec: 24` · `llm_4bit: false` 유지).

**retry 금지. 실행 1회.**

---

## 5. Isolation (동결)

```
쓰기 허용   runs/wvr_whole_video_report_v1/ · work_wvr_report/ · results_wvr_report/
            configs/wvr_whole_video_beta_v3.yaml
쓰기 금지   runs/wvr_whole_video_merge_v1/ · runs/wvr_overview_synthesis_v2/
            runs/wvr_chunk_overview_v2/ · runs/wvr_video_overview_preview_v2/
            runs/rei_c01*/ · runs/v3_paired/ · work/ · work_full/ · config.yaml
            src/v2_1_*.py · scripts/v2_1_b2_orchestrate.py
```

---

## 6. Execution (동결)

```
Analysis      Qwen3-VL-8B-Instruct · runtime.synthesize (텍스트 전용)   1회
Conclusion    같은 모델 · 같은 호출                                     1회
β/v3          Qwen2.5-7B-Instruct · v2_1_b2_orchestrate · contract v3   1회
visual inference 0 · STT inference 0 · timeline regeneration 0 · retry 0
```

실행 순서: `adapter build + gate → Analysis → Conclusion → β/v3`.
gate가 FAIL이면 생성을 시작하지 않는다.

---

## 7. Gate (생성 전)

```
R1  Overview branch 4개 파일 해시 불변
R2  M3 STT source 해시가 §4-3과 일치
R3  segment 101개 · idx 연속 0…100 · start == idx*24
R4  temporal coverage 2424.0초 · 중복 0초 · 빈틈 0
R5  분할된 조각이 원본 entry와 같은 activity·lineage를 갖는다
R6  caption 전 segment 존재 · subtitle 필드 전 segment 존재
R7  engine source 해시 불변 (v2_1_b2_orchestrate · v2_1_prompt · v2_1_grounding ·
    v2_1_render_hwpx · v2_1_segments)
R8  deterministic — 2회 build 산출물 동일
R9  official test 경로 미접근
R10 M9 미호출
```

---

## 8. Machine check (기록 대상 · 판정 아님)

```
ANALYSIS      unknown activity 0 · identifier 노출 0 · overclaim 0 · context 0
              final phase == canonical final phase
CONCLUSION    activity set ⊆ (overview ∪ analysis) activity set
              final phase == canonical final phase
              identifier 노출 0 · overclaim 0 · context 0
```

판정 방식은 Overview V2 §7과 같은 함수를 그대로 쓴다.

---

## 9. 금지 (재확인)

```
β/v3 engine source 수정 · HWPX renderer 수정 · prompt contract 수정
timeline·CANONICAL_FLOW·Overview 수정 또는 재생성
새 visual inference · 새 STT · C01~C05 재실행
새 side experiment · 반복 prompt campaign · 좋은 결과를 위한 retry
official test 접촉 · M9 실행
executor의 최종 report quality PASS 선언
```

---

## 10. 보고 항목

```
ANALYSIS 본문
CONCLUSION 본문
β/v3   eligible / excluded · section completion · fallback · quality exclusions
HWPX   generated · valid · section count
실제 최종 보고서 본문
```

---

## 11. executor가 결정하지 않는 것

```
최종 report quality PASS/HOLD · semantic 정확성
Analysis/Conclusion 재생성 여부 · M9 실행 여부 · official test 개방 여부
```

executor 보고 상태는 다음까지만이다.

```
WVR_WHOLE_VIDEO_REPORT_V1
EXECUTED / REVIEW_PENDING
```

그리고 STOP한다.

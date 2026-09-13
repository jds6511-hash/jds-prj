# WVR_WHOLE_VIDEO_REPORT_V2 실행 계약 (2026-09-13)

Reviewer 판정:

```
WVR_WHOLE_VIDEO_REPORT_V1
CLOSED / WHOLE_VIDEO_REPORT_HOLD
```

이번 작업은 새 구조 연구가 아니라 사용자-facing 보고서 정리다.

## 동결 입력

```
runs/wvr_overview_synthesis_v2/overview_result.json
runs/wvr_overview_synthesis_v2/canonical_flow.json
runs/wvr_whole_video_merge_v1/whole_video_activity_timeline.json
runs/wvr_whole_video_merge_v1/timeline_lineage.json
runs/wvr_whole_video_report_v1/b2run/ 전체
work_full/full_xekZO4n4QuE/segments.json
```

Overview, canonical flow, timeline, lineage, β/v3 raw/intermediate, M3 STT를
수정·재생성하지 않는다.

## 허용 생성

```
Analysis    Qwen3-VL-8B-Instruct text-only 1회
Conclusion  같은 runtime text-only 1회
```

새 visual inference, STT, β/v3 regeneration, Overview/timeline regeneration은 0회다.
retry하지 않는다.

Analysis 입력은 CANONICAL_FLOW, frozen DETAILED_OVERVIEW,
whole_video_activity_timeline의 activity 순서·출현 집계만이다. Conclusion 입력은 frozen
SHORT/DETAILED Overview와 revised Analysis만이다.

## 사용자-facing 본문

개요와 상세 개요는 동결 원문을 byte/text-equivalent하게 넣는다. 새 Analysis와
Conclusion을 넣고, V1의 H01~H09 β/v3 generated natural-language summary를 전부
제외한다. β/v3는 eligible 36/41과 5개 quality exclusion code만 근거 절에 남긴다.
episode별 noisy text와 `seg#` 식별자는 넣지 않는다.

최종 구조:

```
# 영상 전체 보고서
## 개요
## 상세 개요
## 분석
## 결론
## 근거 및 생성 정보
```

기존 OWPML renderer를 변경하지 않고 final Markdown을 HWPX로 다시 렌더한다.

## 검증

```
Overview/canonical/timeline/lineage hash unchanged
β/v3 raw/intermediate tree hash unchanged
M3 STT hash unchanged
H01~H09 heading 0
seg# identifier 0
Analysis/Conclusion present
unknown activity 0 · context/intent overclaim 0
final phase == 식사
HWPX package errors 0
HWPX semantic text == final Markdown
official test untouched · M9 not invoked
```

GUI를 실제 확인하지 못하면 `GUI_LAYOUT_UNVERIFIED`로 기록한다.

최종 상태는 다음까지만 보고한다.

```
WVR_WHOLE_VIDEO_REPORT_V2
EXECUTED / REVIEW_PENDING
```

# Start Here

최종 발표에서 설명하는 공개 진입점은 세 개입니다.

## 1. 자연어 장면 검색

읽을 파일: [`src/jds_video/scene_search.py`](src/jds_video/scene_search.py)

```text
Video → 5초 구간 → STT + visual caption → embedding → score fusion → timestamp
```

핵심 공개 API:

- `VideoIndex`
- `search()` / `search_with_stats()`
- `create_app()`

세부 구현은 `src/jds_video/_internal/m1_preprocess.py`부터
`m7_webui.py`까지 이어집니다.

## 2. 영상 전체 보고서

읽을 파일: [`src/jds_video/whole_video_report.py`](src/jds_video/whole_video_report.py)

```text
Video → broad segment observation → temporal compression
      → canonical activity flow → Overview → Analysis / Conclusion → HWPX
```

핵심 공개 API:

- `segment_prompt()` / `parse_segment()`
- `compress_activity_timeline()` / `canonical_flow()`
- `analysis_prompt()` / `conclusion_prompt()`
- `final_report_markdown()` / `machine_checks()`

`src/jds_video/_internal/`은 검증된 기존 구현과 provenance 계약입니다.
튜터가 전체 내부 모듈을 순서대로 읽을 필요는 없습니다.

## 3. 화면 + 음성 보고서 (현재 보고서 경로)

읽을 파일: [`src/jds_video/multimodal_report.py`](src/jds_video/multimodal_report.py)

```text
Video → 구간 관찰 + 발화 → 같은 사건으로 결합 → 사건 요약
      → 근거 검증 → 보고 개요 / 영상 개요 / 세부 관찰 내용
```

핵심 공개 API:

- `compose_fused_summary()` / `modality_clause()` — 화면 근거와 음성 근거를 한 행으로
- `assign_importance()` / `choose_episode_category()` — 행의 비중과 구분
- `audit_title()` / `audit_overview()` — 제목·개요가 사건에 지지되는지
- `audit_report_style()` / `leakage_audit()` / `style_audit()` — 전사 복사와 말투 판정
- `resolve_decision()` — 생성 → 재생성 → 범위 요약 → 보류로 물러서는 순서

두 번째 묶음이 이 경로의 핵심입니다. **발화 근거는 다시 써서 싣고, 전사 원문은
보고서에 올리지 않습니다.**

## 결과 확인

- 검색 평가: [`results/retrieval_eval_test.json`](results/retrieval_eval_test.json)
- 보고서 예시: [`examples/multimodal_report.md`](examples/multimodal_report.md)
  (이전 관찰 전용 경로: [`examples/whole_video_report.md`](examples/whole_video_report.md))
- 개발 과정: [`docs/DEVELOPMENT_HISTORY.md`](docs/DEVELOPMENT_HISTORY.md)
- 발표 자료: [`docs/final_presentation.pptx`](docs/final_presentation.pptx)

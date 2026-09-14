# Start Here

최종 발표에서 설명하는 공개 진입점은 두 개입니다.

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

## 결과 확인

- 검색 평가: [`results/retrieval_eval_test.json`](results/retrieval_eval_test.json)
- 보고서 예시: [`examples/whole_video_report.md`](examples/whole_video_report.md)
- 개발 과정: [`docs/DEVELOPMENT_HISTORY.md`](docs/DEVELOPMENT_HISTORY.md)
- 발표 자료: [`docs/final_presentation.pptx`](docs/final_presentation.pptx)

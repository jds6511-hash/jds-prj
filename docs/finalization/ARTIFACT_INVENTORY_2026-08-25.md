# 최종 제출 artifact 목록 (2026-08-25)

기존 문서를 복제하지 않는다 — **참조 중심**이다. 새로 만든 것만 "신규"로 표시했다.

## 1. finalization 산출물 (신규)

| 파일 | 내용 | 성격 |
|---|---|---|
| `END_TO_END_AUDIT_2026-08-25.md` | 단계별 entrypoint·산출물·실패조건·상태·gap | 조사 |
| `SYSTEM_ARCHITECTURE_2026-08-25.md` | mermaid 파이프라인 + 단계별 확정값 | 발표·보고서 |
| `DEMO_SCENARIOS_2026-08-25.md` | 시연 순서·질의 3종·abstention·체크리스트 | 발표 |
| `SUCCESS_FAILURE_GALLERY_2026-08-25.md` | dev 9건 실제 실행 출력 (Top-5 표) | descriptive |
| `DEMO_GALLERY_2026-08-25.json` | 위의 원자료 | descriptive |
| `MODEL_SELECTION_CASE_STUDY_2026-08-25.md` | 3B/4B 1-page | 발표·보고서 |
| `OPERATIONAL_PROFILE_SUMMARY_2026-08-25.md` | 운영 실측 정리 + 표현 규칙 | 발표·보고서 |
| `EXTERNAL_BENCHMARK_CONTEXT_2026-08-25.md` | 외부 문헌 contextual only | 보고서 |
| `AAR_TRACEABILITY_2026-08-25.md` | AAR 구조·fail-closed·경계 | 보고서 |
| `REPRODUCIBILITY_SUMMARY_2026-08-25.md` | 안전장치 10항목 | 발표·보고서 |
| `LIMITATIONS_FUTURE_WORK_2026-08-25.md` | 한계 10 · 향후 7 | 보고서 |
| `FINAL_REPORT_OUTLINE_2026-08-25.md` | 절별 개요 + 출처 매핑 | 작업 지도 |
| `PRESENTATION_OUTLINE_2026-08-25.md` | 슬라이드 15장 + 예상질문 | 발표 |
| `ARTIFACT_INVENTORY_2026-08-25.md` | 이 문서 | 지도 |

## 2. 신규 제품 코드

| 파일 | 역할 | 테스트 |
|---|---|---|
| `scripts/demo.py` | 데모 단일 진입점 + preflight fail-closed | `tests/test_demo_preflight.py` (23) |
| `scripts/aar_view.py` | report.json → 주장·시각·근거 추적 렌더 | `tests/test_aar_view.py` (13) |
| `scripts/demo_gallery.py` | dev 전용 descriptive gallery 생성 | `tests/test_demo_gallery.py` (10) |
| `src/m7_webui.py` (수정) | 응답에 `rank`·`seek_to`·`video_id`·`query`·`top_k` 추가 | `tests/test_m7_webui.py` |
| `src/webui/index.html` (수정) | 서버 제공 rank·seek_to 사용, 구간 종료시각 표시 | 같음 |

## 3. 기존 핵심 산출물 (참조)

```
README.md                        문제·결과·Quick Start·재현 범위·한계
CLAUDE.md                        연구 규율 (절대 규칙)
docs/DESIGN_SPEC.md              확정 수치 전표 · 8-6 test 접촉 이력 · 8-5 M8/M9 결함 이력
docs/README.md                   문서 지도
results/eval_test.json           공식 test 39질의 결과 (diff_ci95)
results/alpha_search_dev.json    dev α 탐색 · alpha_star
config.yaml                      확정 config (α는 없다 — CLI 주입)
data/queries/queries.jsonl       dev 96 / test 39 질의·정답 라벨 (공개)
```

## 4. 연구 근거 문서 (보고서 인용용)

```
docs/재분석_2x2_2026-08-18.md            AI Hub 캡션 2×2 (4B +0.0310)
docs/재분석_dev정밀도3arm_2026-08-18.md   dev 3-arm (3B 0.4644 / 4B q4 0.3741)
docs/재분석_부호역전_2026-08-18.md        질의 유형·영상별 분해
docs/재분석_P1풀크기_2026-08-18.md        풀 크기 조작 (plausible contributor)
docs/probes/_scratch/p3_opcost_*.json    운영 실측·해석 규칙·판정 (동결)
docs/P3_설계민감도_2026-08-24.json        P3-A 설계 + frozen_decision
docs/P3_4B_deployment_confirmation_DRAFT_2026-08-24.md   P3-A 설계 초안
docs/P3_파일럿취득계획_2026-08-24.md      파일럿 취득 계획
docs/P3_반출권한감사_2026-08-24.json      반출 권한 감사 (35편 전부 unclear)
docs/작업현황_2026-08-25.md              현재 상태 (FINALIZATION)
```

## 5. 제출에 넣지 않는 것

```
원본 영상 mp4                     저작물. 저장소 비포함 정책 유지
work/*/segments.json · 임베딩      영상 파생 텍스트. 같은 이유로 비포함
P2 라벨 작업 파일                  annotation HOLD 상태
test 39 원본 판정 과정             DESIGN_SPEC 8-6 기록으로 대체
```

## 6. 제출 전 체크

```
python -m pytest tests/ -q                                    전체 통과
python scripts/demo.py --list                                 인덱스 목록
python scripts/demo.py --video-id <dev> --check-only          preflight 11항목 PASS
README의 모든 명령이 실제로 존재하는지 확인 (smoke)
finalization 문서에 test/P2/P3 outcome이 새로 들어가지 않았는지 확인
```

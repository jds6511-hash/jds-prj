# 최종 제출 artifact 목록 (2026-08-25 · 08-26 갱신)

기존 문서를 복제하지 않는다 — **참조 중심**이다. 새로 만든 것만 "신규"로 표시했다.

**2026-08-26 갱신** — §1-b에 08-26 산출물(케이스 스터디 · external E2E · F3 · F4 · F5)을
추가했다. §1의 08-25 목록은 그대로 둔다.

## 1. finalization 산출물 (신규)

| 파일 | 내용 | 성격 |
|---|---|---|
| `END_TO_END_AUDIT_2026-08-25.md` | 단계별 entrypoint·산출물·실패조건·상태·gap | 조사 |
| `SYSTEM_ARCHITECTURE_2026-08-25.md` | mermaid 파이프라인 + 단계별 확정값 | 발표·보고서 |
| `DEMO_SCENARIOS_2026-08-25.md` | 시연 순서·질의 3종·low-relevance 예시·체크리스트 | 발표 |
| `DEMO_REHEARSAL_2026-08-25.md` | 8분 리허설 체크리스트 · fallback 3단 · AAR 확보 절차 | 발표 |
| `SUCCESS_FAILURE_GALLERY_2026-08-25.md` | dev 9건 실제 실행 출력 (Top-5 표) | descriptive |
| `DEMO_GALLERY_2026-08-25.json` | 위의 원자료 | descriptive |
| `MODEL_SELECTION_CASE_STUDY_2026-08-25.md` | 3B/4B 1-page | 발표·보고서 |
| `OPERATIONAL_PROFILE_SUMMARY_2026-08-25.md` | 운영 실측 정리 + 표현 규칙 | 발표·보고서 |
| `EXTERNAL_BENCHMARK_CONTEXT_2026-08-25.md` | 외부 문헌 contextual only | 보고서 |
| `AAR_TRACEABILITY_2026-08-25.md` | AAR 구조·fail-closed·경계 | 보고서 |
| `REPRODUCIBILITY_SUMMARY_2026-08-25.md` | 안전장치 10항목 | 발표·보고서 |
| `LIMITATIONS_FUTURE_WORK_2026-08-25.md` | 한계 14 · 향후 7 (08-26에 12~14 추가) | 보고서 |
| `FINAL_REPORT_OUTLINE_2026-08-25.md` | 절별 개요 + 출처 매핑 | 작업 지도 |
| `PRESENTATION_OUTLINE_2026-08-25.md` | 슬라이드 15장 + 예상질문 | 발표 |
| `ARTIFACT_INVENTORY_2026-08-25.md` | 이 문서 | 지도 |

## 1-b. finalization 산출물 — 2026-08-26 추가

| 파일 | 내용 | 성격 |
|---|---|---|
| `CAPTION_RETRIEVAL_CASESTUDY_PLAN_2026-08-25.md` · `caption_retrieval_casestudy_plan.json` | 결과 열람 전 동결한 사례 연구 설계 | 사전등록 |
| `CAPTION_RETRIEVAL_CASESTUDY_AMENDMENT_2026-08-25.md` | outcome-blind amendment (3B도 같은 조건 재생성) | 사전등록 |
| `caption_retrieval_casestudy_comparability_audit.json` | STEP 5.5 대조 가능성 감사 (verdict PASS) | 감사 |
| `CAPTION_RETRIEVAL_CASESTUDY_RESULTS_2026-08-25.md` · `CAPTION_RETRIEVAL_CASESTUDY_TABLE.md` · `caption_retrieval_casestudy_results.json` | 5장면·15질의 결과 전량 | 보고서 |
| `docs/tutor/캡션검색_케이스스터디_1페이지.md` | 위의 1페이지 요약 | 튜터·발표 |
| `e2e_external_results.json` | external E2E PHASE 1~4 (schema v2 · runs[]) | 기능 검증 |
| `AAR_SERVER_RUNBOOK_2026-08-26.md` | F3 — 서버 1회 완주 절차·검증·실패 조건. **2026-08-26에 이 절차로 완주했고 실행에서 드러난 결함 3건을 반영했다** | 운영 |
| `F4_DOCUMENTATION_AUDIT_2026-08-26.md` | F4 — 문서·코드 정합성 감사 A~G | 감사 |
| `FINAL_REPORT_SOURCE_PACK_2026-08-26.md` | **F5** — 보고서 절별 재료 + conflict audit + 표·그림 후보 | 보고서 |
| `CLAIM_EVIDENCE_MATRIX_2026-08-26.md` | **F5** — 주장 C01~C20 · 근거 · 허용/금지 표현 | 보고서 |
| `final_report_facts_2026-08-26.json` | **F5** — 기계 판독 fact index (numeric fact마다 source_path) | 보고서 |

## 2. 신규 제품 코드

| 파일 | 역할 | 테스트 |
|---|---|---|
| `scripts/demo.py` | 데모 단일 진입점 + preflight fail-closed(12항목) + E2E/test 영상 거부 + AAR fallback 상태 | `tests/test_demo_preflight.py` (32) |
| `scripts/e2e_verify.py` | external E2E 공용 검증기 (`--video-id`) | `tests/test_e2e_external.py` (55) |
| `scripts/make_server_config.py` | 서버용 config 재생성 (수동 편집 금지 · 변경 금지 항목 assert) | `tests/test_e2e_external.py` 외 |
| `scripts/casestudy_make_config.py` | 사례 연구 arm별 격리 config 생성 | — |
| `scripts/aar_view.py` | report.json → 주장·시각·근거 추적 렌더 + 사전 생성물 점검 | `tests/test_aar_view.py` (20) |
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
docs/P2_활성설계_2026-08-24.json          P2 175행 설계 (완료 20 · 미완 155)
docs/probes/_scratch/caption_foreign_char_scan.json  캡션 QC 자체 측정 (오염 GT 아님)
docs/작업현황_2026-08-25.md              현재 상태 (FINALIZATION)
```

**보고서 집필 시작점은 F5 세 문서다** — `FINAL_REPORT_SOURCE_PACK_2026-08-26.md`(절별
재료) · `CLAIM_EVIDENCE_MATRIX_2026-08-26.md`(주장별 근거·표현 규칙) ·
`final_report_facts_2026-08-26.json`(수치의 source-of-truth). 위 문서들은 그 팩이
가리키는 원 출처다.

## 5. 제출에 넣지 않는 것

```
원본 영상 mp4                     저작물. 저장소 비포함 정책 유지
work/*/segments.json · 임베딩      영상 파생 텍스트. 같은 이유로 비포함
work/*/report.json                AAR artifact. work/ 아래라 이미 비포함
AAR_SAMPLE_*.md · aar_sample_*.json  렌더본 — 인용 구간의 자막·캡션 원문이 실린다.
                                  같은 이유로 비포함. 해시·수치는 final_report_facts에 있다
P2 라벨 작업 파일                  annotation HOLD 상태
test 39 원본 판정 과정             DESIGN_SPEC 8-6 기록으로 대체
```

## 6. 제출 전 체크

```
python -m pytest tests/ -q                                    전체 통과
python scripts/demo.py --list                                 인덱스 목록
python -m pytest tests/test_final_report_facts.py -q          F5 근거 경로·상태 정합 + AAR artifact 대조
python scripts/aar_view.py --video-id gwaktube_soviet_apartment  AAR 렌더 (산출물은 비추적)
python scripts/demo.py --video-id <dev> --check-only          preflight 12항목 + AAR 상태
README의 모든 명령이 실제로 존재하는지 확인 (smoke)
finalization 문서에 test/P2/P3 outcome이 새로 들어가지 않았는지 확인
```

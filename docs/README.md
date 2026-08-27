# 문서 지도

문서가 많다(루트 40 · `finalization/` 46 · `preregistration/` 26 · `probes/` 84).
**전부 읽을 필요 없다.** 아래 세 줄이 진입점이고 나머지는 필요할 때 찾는다.

| 상황 | 읽을 것 |
|---|---|
| 세션 재시작 | [작업현황_2026-08-25.md](작업현황_2026-08-25.md) — 가장 최신 스냅샷 |
| 지금 무엇이 남았는지 | [finalization/M8_M9_DECISIONS_2026-08-26.md](finalization/M8_M9_DECISIONS_2026-08-26.md) — 확정된 방법론 결정과 미결 |
| 설계·실측 근거를 찾을 때 | [DESIGN_SPEC.md](DESIGN_SPEC.md) — 수치의 최종 출처 |

> 프로젝트 종료선은 2026-08-26에 다시 정의됐다 —
> `M1~M7 → M8 COMPLETE → M8 FREEZE → M9(test-opening 승인) → HWPX/HWP`.
> M8·M9는 더 이상 향후과제가 아니다.

---

## 루트 — 설계·규약

| 파일 | 내용 |
|---|---|
| [DESIGN_SPEC.md](DESIGN_SPEC.md) | 설계·실측 근거 본체. 수치의 최종 출처 |
| [DESIGN_SPEC_CHANGELOG.md](DESIGN_SPEC_CHANGELOG.md) | 설계가 언제 왜 바뀌었는지 |
| [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) | 모듈별 구현 규약 |
| [HANDOFF_CURRENT.md](HANDOFF_CURRENT.md) | `scripts/make_handoff.py` 자동 생성. **직접 편집하지 않는다** — 오래됐으면 다시 생성해서 읽는다 |

## 루트 — 작업현황 계보

최신부터 읽는다. 이전 판은 그 시점의 판단을 되짚을 때만 본다.

| 파일 | 그 시점 |
|---|---|
| [작업현황_2026-08-25.md](작업현황_2026-08-25.md) | **최신** — 최종화 단계 진입 |
| [작업현황_2026-08-24.md](작업현황_2026-08-24.md) | P2 라벨링·P3 운영비 |
| [작업현황_2026-08-22.md](작업현황_2026-08-22.md) | 승인 ② 실행·P2 색인 배치 |
| [작업현황_2026-08-20.md](작업현황_2026-08-20.md) | P2 표집틀 확정 |
| [작업현황_2026-08-18.md](작업현황_2026-08-18.md) | 부호 역전·I1 freeze |
| [작업현황_2026-08-17.md](작업현황_2026-08-17.md) | 8회차 HOLD |

`archive/`로 옮기지 않은 이유는 다른 문서들이 절 번호까지 걸어 참조하기 때문이다
(예: "작업현황 2026-08-18 §5-3"). 경로를 옮기면 그 참조가 끊긴다.

## 루트 — 8회차 판정과 감사

| 파일 | 내용 |
|---|---|
| [8회차_HOLD_마감_2026-08-17.md](8회차_HOLD_마감_2026-08-17.md) | **8회차 종료 기록** — 판정·미결·교훈 |
| [판정자료_2026-08-17.md](판정자료_2026-08-17.md) | 8회차 게이트 수치 전문 (I1·A2 FAIL) |
| [감사_2026-08-17.md](감사_2026-08-17.md) | 평가 절차 감사 — α 식 오류·prompt bundle 교락·per_query 미저장 |
| [인프라개선_2026-08-22.md](인프라개선_2026-08-22.md) | 실행 인프라 개선 기록 |

## 루트 — 재분석 (2026-08-17 ~ 18)

감사에서 나온 질문을 하나씩 닫은 기록이다.

| 파일 | 무엇을 해소했나 |
|---|---|
| [재분석_전달분해_2026-08-17.md](재분석_전달분해_2026-08-17.md) | 재표집 단위(ICC 음수)·융합 전달 구조(76~81%) |
| [재분석_2x2_2026-08-18.md](재분석_2x2_2026-08-18.md) | caption model×prompt 2×2 — 귀속 해소·후보 `4B/P0` |
| [재분석_부호역전_2026-08-18.md](재분석_부호역전_2026-08-18.md) | dev↔AI Hub 부호 역전 |
| [재분석_알파곡선_2026-08-18.md](재분석_알파곡선_2026-08-18.md) | arm별 α 곡선 |
| [재분석_융합feature_2026-08-18.md](재분석_융합feature_2026-08-18.md) | 융합 정교화 시도 |
| [재분석_dev정밀도3arm_2026-08-18.md](재분석_dev정밀도3arm_2026-08-18.md) | dev 3-arm 정밀도 |
| [재분석_M8pilot_2026-08-18.md](재분석_M8pilot_2026-08-18.md) | **M8 pilot** — 6분류 taxonomy 동결·표본 소비 선언 |
| [재분석_P1풀크기_2026-08-18.md](재분석_P1풀크기_2026-08-18.md) | P1 풀 크기 |
| [재분석_I1검증셋A_2026-08-18.md](재분석_I1검증셋A_2026-08-18.md) · [B](재분석_I1검증셋B_2026-08-18.md) | I1 검출기 검증셋 |

## 루트 — I1 검출기 · P2 · P3

| 묶음 | 파일 |
|---|---|
| I1 검출기 | [후보 freeze](I1_detector_candidate_freeze_2026-08-20.md) · [validation 결과](I1_detector_validation결과_2026-08-22.md)(**one-shot 소비 기록**) · [모집단 소진 설계](I1_모집단소진_설계결과_2026-08-20.md) |
| P2 표집 | [영상후보 스크리닝규격](P2_영상후보_스크리닝규격_2026-08-20.md) · [선정규칙 동률처리](P2_선정규칙_동률처리_2026-08-20.md) · [선정표본](P2_선정표본_2026-08-20.md) · [승인1 규모확정](P2_승인1_규모확정_2026-08-20.md) · [승인검토 자원](P2_승인검토_자원_2026-08-20.md) · [질의쿼터](P2_질의쿼터_2026-08-20.md) |
| P2 라벨링 | [GT작성 가이드](P2_GT작성_가이드.md) · [표본크기 amendment](P2_GT_sample_size_amendment_2026-08-24.md) · [AI assist amendment DRAFT](P2_GT_AI_assist_amendment_DRAFT_2026-08-24.md) |
| P3 | [파일럿 취득계획](P3_파일럿취득계획_2026-08-24.md) · [4B 배포 확증 DRAFT](P3_4B_deployment_confirmation_DRAFT_2026-08-24.md) |

`DRAFT`가 붙은 둘은 **초안 상태 그대로**다 — 확정본으로 인용하지 마라.
JSON 산출물(`P2_*.json` · `P3_*.json`)은 같은 이름의 md와 짝이거나 도구가 읽는 정본이다.

## `finalization/` — 최종화 산출물 (46건)

2026-08-25부터의 마감 작업이 전부 여기 있다.

| 묶음 | 파일 |
|---|---|
| **M8 · M9 완료 경로** | [M8_M9_PROTOCOL](finalization/M8_M9_PROTOCOL_2026-08-26.md) · [M8_M9_DECISIONS](finalization/M8_M9_DECISIONS_2026-08-26.md)(D1~D6 승인 기록) · [M8_생성배치_계획](finalization/M8_생성배치_계획_2026-08-26.md) · [AAR_SERVER_RUNBOOK](finalization/AAR_SERVER_RUNBOOK_2026-08-26.md) |
| **C2 판정 패널** | [M8_C2_SOURCING_RULE](finalization/M8_C2_SOURCING_RULE_2026-08-27.md)(후보 조회 전 동결) · [M8_C2_PANEL_FREEZE](finalization/M8_C2_PANEL_FREEZE_2026-08-27.md) · `m8_c2_panel_manifest_*.json`(기계가 읽는 정본) |
| **관문 집행 규격** | [M8_GATE_SPEC_FREEZE](finalization/M8_GATE_SPEC_FREEZE_2026-08-27.md) — C1 3-state·pre-merge 판정, C3 집계 MAX. **M8 산출물 0건 시점에 동결** |
| **감사** | [PROJECT_DESIGN_CONFORMANCE_AUDIT](finalization/PROJECT_DESIGN_CONFORMANCE_AUDIT_2026-08-26.md)(COMPLETE) · [CAPTION_TO_RETRIEVAL_INTEGRITY_AUDIT](finalization/CAPTION_TO_RETRIEVAL_INTEGRITY_AUDIT_2026-08-26.md) · [CAPTION_TEXT_HANDLING_AUDIT](finalization/CAPTION_TEXT_HANDLING_AUDIT_2026-08-26.md) · [END_TO_END_AUDIT](finalization/END_TO_END_AUDIT_2026-08-25.md) · [F4_DOCUMENTATION_AUDIT](finalization/F4_DOCUMENTATION_AUDIT_2026-08-26.md) |
| **캡션↔검색 케이스 스터디** | [PLAN](finalization/CAPTION_RETRIEVAL_CASESTUDY_PLAN_2026-08-25.md) · [RESULTS](finalization/CAPTION_RETRIEVAL_CASESTUDY_RESULTS_2026-08-25.md) · [AMENDMENT](finalization/CAPTION_RETRIEVAL_CASESTUDY_AMENDMENT_2026-08-25.md) · [A2 AMENDMENT](finalization/CAPTION_RETRIEVAL_CASESTUDY_AMENDMENT_A2_2026-08-26.md) · [TABLE](finalization/CAPTION_RETRIEVAL_CASESTUDY_TABLE.md) |
| **AAR 추적** | [AAR_TRACEABILITY](finalization/AAR_TRACEABILITY_2026-08-25.md) · [AAR_SAMPLE](finalization/AAR_SAMPLE_gwaktube_soviet_apartment.md) |
| **보고서·발표 준비** | [FINAL_REPORT_OUTLINE](finalization/FINAL_REPORT_OUTLINE_2026-08-25.md) · [FINAL_REPORT_SOURCE_PACK](finalization/FINAL_REPORT_SOURCE_PACK_2026-08-26.md) · [CLAIM_EVIDENCE_MATRIX](finalization/CLAIM_EVIDENCE_MATRIX_2026-08-26.md) · [PRESENTATION_OUTLINE](finalization/PRESENTATION_OUTLINE_2026-08-25.md) · [DEMO_SCENARIOS](finalization/DEMO_SCENARIOS_2026-08-25.md) · [DEMO_REHEARSAL](finalization/DEMO_REHEARSAL_2026-08-25.md) |
| **시스템 요약** | [SYSTEM_ARCHITECTURE](finalization/SYSTEM_ARCHITECTURE_2026-08-25.md) · [REPRODUCIBILITY_SUMMARY](finalization/REPRODUCIBILITY_SUMMARY_2026-08-25.md) · [OPERATIONAL_PROFILE_SUMMARY](finalization/OPERATIONAL_PROFILE_SUMMARY_2026-08-25.md) · [ARTIFACT_INVENTORY](finalization/ARTIFACT_INVENTORY_2026-08-25.md) · [LIMITATIONS_FUTURE_WORK](finalization/LIMITATIONS_FUTURE_WORK_2026-08-25.md) |
| **사례·비교** | [MODEL_SELECTION_CASE_STUDY](finalization/MODEL_SELECTION_CASE_STUDY_2026-08-25.md) · [SUCCESS_FAILURE_GALLERY](finalization/SUCCESS_FAILURE_GALLERY_2026-08-25.md) · [EXTERNAL_BENCHMARK_CONTEXT](finalization/EXTERNAL_BENCHMARK_CONTEXT_2026-08-25.md) · [HISTORY_REWRITE](finalization/HISTORY_REWRITE_2026-08-26.md) |

`.json`은 같은 이름 md의 기계 판이거나 도구가 읽는 정본이다. 케이스 스터디는
`plan.json`(v1 동결)과 `plan_r2.json`(발표 기준)이 **둘 다** 있다 — 두 판을 합산하지 마라.

## `preregistration/` — 고치지 않는 문서 (26건)

**결과를 보기 전에 커밋됐다는 사실이 이 문서들의 존재 이유다.** 내용을 수정하면
"결과 보고 기준을 맞췄다"는 의심을 반박할 수단이 사라진다. 임계를 낮추지도, 새 기준을
추가하지도 않는다.

| 파일 | 무엇을 박았나 |
|---|---|
| [test_재평가_프로토콜_2026-08-13.md](preregistration/test_재평가_프로토콜_2026-08-13.md) | test 재평가 절차 |
| [M8_개선_사전등록_2026-08-14.md](preregistration/M8_개선_사전등록_2026-08-14.md) | M8 1차 개선 판정 기준(G1~G3) |
| [M8_구조변경_사전등록_2026-08-16.md](preregistration/M8_구조변경_사전등록_2026-08-16.md) | **구조화 map 관문 C1~C3 · 판정 표본 8~12편** |
| [M8_event지표_보충_2026-08-18.md](preregistration/M8_event지표_보충_2026-08-18.md) | event 지표 정의 |
| [event_inventory_사전등록_2026-08-18.md](preregistration/event_inventory_사전등록_2026-08-18.md) | 사람 사건 목록 작성 규약 |
| [8회차_개방게이트_2026-08-16.md](preregistration/8회차_개방게이트_2026-08-16.md) | 무결성 I1~I4 · α A1·A2 · τ T1~T3 · 절차 P1~P3 |
| [caption_2x2_사전등록_2026-08-17.md](preregistration/caption_2x2_사전등록_2026-08-17.md) | 2×2 arm·대비·채택조건·canary |
| 부호역전 확증 계열 | 사전등록 + 보충 1~4 (P2 설계·표집범위·표집틀 검증) |

나머지는 위 계열의 보충·amendment다. 폴더를 직접 훑는 편이 빠르다.

> **알려진 낡은 경로 2건.** 2026-08-17 문서 재배치 때 이 폴더 파일들은 `git mv`만 하고
> **내용은 건드리지 않았다.** 아래 두 줄의 경로는 이동 전 값 그대로이고, 가리키는 파일은
> 둘 다 같은 폴더 안에 있다.
>
> - `8회차_개방게이트_2026-08-16.md:11` → `docs/test_재평가_프로토콜_2026-08-13.md`
> - `M8_구조변경_사전등록_2026-08-16.md:9` → `docs/M8_개선_사전등록_2026-08-14.md`

## `tutor/` — 회의·자문 기록 (9건)

| 파일 | 내용 |
|---|---|
| [튜터회의_2026-08-11.md](tutor/튜터회의_2026-08-11.md) · [튜터회의_2026-08-14.md](tutor/튜터회의_2026-08-14.md) | 회의 기록 |
| [튜터결정_2026-08-14.md](tutor/튜터결정_2026-08-14.md) | 회의에서 확정된 결정 사항 |
| [자문요청_2026-08-16.md](tutor/자문요청_2026-08-16.md) | 외부 자문용 자립 문서(M8 파국·평가 규모) |
| [자문요청_캡션모델선택_2026-08-17.md](tutor/자문요청_캡션모델선택_2026-08-17.md) | 외부 자문용 자립 문서 — 캡션 모델 채택 판단 |

## `planning/` — 아직 실행 안 끝난 계획

| 파일 | 상태 |
|---|---|
| [평가확장_계획.md](planning/평가확장_계획.md) | 진행 중 |
| [ablation_plan_draft.md](planning/ablation_plan_draft.md) | 변형 실험 설계 |
| [phase4_회의록_설계.md](planning/phase4_회의록_설계.md) | **동결** — 2026-08-09 설계 확정 후 미착수 |

## `archive/` — 결론이 이미 흡수된 기록 (12건)

수치의 최종 출처는 DESIGN_SPEC이다. 여기 파일은 **그 수치가 어떻게 나왔는지 되짚을 때만**
본다.

7월: 설계점검_2026-07-09 · 평가분석_2026-07-10 · 오류분석_test_2026-07-13 ·
작업현황 07-11 / 07-13 / 07-14
8월: 작업현황 08-04 / 08-07 / 08-09 / 08-10 / 08-12 / 08-14

## 하위 디렉터리

| 경로 | 내용 |
|---|---|
| [presentation/](presentation/) | 발표덱 생성 스크립트·시연 런북·[예상질문_방어.md](presentation/예상질문_방어.md) |
| [probes/](probes/) | 후보 검증·계측 스크립트 81개. 산출물은 `_scratch/`(대부분 비추적) |
| [superpowers/](superpowers/) | 초기 설계 spec·plan |

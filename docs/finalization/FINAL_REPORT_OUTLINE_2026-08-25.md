# 최종 보고서 개요 (2026-08-25)

각 절에 **어느 산출물에서 가져올지**를 붙였다. 새로 계산할 것은 없다.

## 1. 문제 정의 (1~1.5p)

```
핵심     자막 검색은 아무도 말하지 않은 장면을 못 찾는다
근거     공식 test 39질의 중 장면형 13건에서 자막 단독 MRR 0.174
출처     README · results/eval_test.json · DESIGN_SPEC 8-0
```

## 2. 접근 (1.5~2p)

```
두 채널   자막(말한 것) + 장면 캡션(보이는 것)
융합     채널별 z-score → α 가중합. α=0.5는 dev grid search로 확정 (CLI 주입)
학습 없음  frozen 임베딩 (KURE-v1). 파인튜닝 없음
출처     docs/finalization/SYSTEM_ARCHITECTURE_2026-08-25.md (mermaid 그대로 사용 가능)
```

## 3. 시스템 (2~3p)

```
M1~M7 파이프라인 · 단계별 확정값 표 · 진입점
웹 UI: 순위·점수·발화/화면 근거·timestamp 재생·low-relevance 경고(배너만, 랭킹 불변)
출처     SYSTEM_ARCHITECTURE · END_TO_END_AUDIT §3
```

## 4. 실험 설계와 연구 규율 (2p) ← **차별점**

```
dev/test 분리 · 튜닝 접촉 0회 · 확정 절차 7회 전건 기록
캡션 수동 편집 금지 (자동 판정만) · 라벨은 프레임 실물 검증
paired video-cluster bootstrap B=2000 seed 42
출처     CLAUDE.md · DESIGN_SPEC 8-6 · docs/preregistration/
```

## 5. 결과 (2~3p)

```
공식 test 39질의: MRR 0.649 → 0.829 [+0.058, +0.310] · Hit@1 0.564 → 0.769
유형별: 장면형 0.174 → 0.718 / 복합형 0.825 → 0.887 / 자막형 0.958 → 0.880 (트레이드오프)
Hit@5·Hit@10은 CI가 0을 포함 — 유의하지 않다고 그대로 적는다
출처     results/eval_test.json · README
```

## 6. 캡션 모델 선택 case study (1~1.5p)

```
AI Hub +0.0310 ↔ dev −0.0903 · 둘 다 CI 0 배제 · 어느 쪽도 확증 자격 없음
질의 유형 이질성 · 풀 크기(plausible contributor) · 양자화는 설명 아님
운영 실측: deployment blocker 없음 / resource-footprint penalty 있음
결론: superiority unresolved · incumbent 3B retained · 4B candidate/not adopted
출처     MODEL_SELECTION_CASE_STUDY_2026-08-25.md (그대로 1p)
```

## 7. 실패·한계 사례 (1~1.5p)

```
dev descriptive gallery 9건 (성공 7 · 부분 1 · 어려움 1)
장면형이 편차가 가장 큰 유형 · 자막형 트레이드오프 · 무관 질의 경고
출처     SUCCESS_FAILURE_GALLERY_2026-08-25.md
```

## 8. AAR 리포트 (1p)

```
[seg#N] 인용 강제 · 저장 시 4개 검증 · aar_view로 주장→시각→근거 추적
결함 4건 규명 이력(인용만 남음 · 꼬리 절단 · 번호 몰아쓰기 · 반복 루프)
로컬 6GB 실행 불가 — 서버 GPU 전용
출처     AAR_TRACEABILITY_2026-08-25.md · DESIGN_SPEC 8-5(6)
```

## 9. 재현성·운영 (1~1.5p)

```
preflight fail-closed · text_hash · 자동 판정만 · label allowlist ·
마커/RUN_COMPLETE/validator · CANARY coverage · 동결 바이트 고정 · 결정성 실측
출처     REPRODUCIBILITY_SUMMARY_2026-08-25.md · OPERATIONAL_PROFILE_SUMMARY
```

## 10. 관련 연구 (0.5~1p)

```
Qwen3-VL 세대 개선 주장 · 본 endpoint를 대리하지 못하는 5가지 · adoption gate 아님
출처     EXTERNAL_BENCHMARK_CONTEXT_2026-08-25.md
```

## 11. 한계와 향후 과제 (1~1.5p)

```
한계 10항목 · 향후 과제 7항목 — 두 절을 분리한다
출처     LIMITATIONS_FUTURE_WORK_2026-08-25.md
```

## 부록

```
A  단계별 확정 config 표          config.yaml · SYSTEM_ARCHITECTURE
B  test 접촉 이력 7회             DESIGN_SPEC 8-6
C  P3-A 동결 설계 (향후 과제)      P3_4B_deployment_confirmation_DRAFT · P3_설계민감도 JSON
D  운영 실측 전량                 OPERATIONAL_PROFILE_SUMMARY
E  artifact inventory            ARTIFACT_INVENTORY_2026-08-25.md
```

## 쓰지 않는 표현

```
"3B가 더 좋은 모델로 검증됐다" · "4B 실패" · "P3를 못 해서 3B가 이겼다"
"4B가 운영비가 더 싸다" · "계산적으로 더 효율적" · "토큰당 처리속도"
데모 결과를 benchmark·evaluation으로 제시하는 것
Hit@5·Hit@10을 유의한 개선처럼 쓰는 것
```

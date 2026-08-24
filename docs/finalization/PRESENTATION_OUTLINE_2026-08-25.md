# 발표 개요 (2026-08-25)

라이브 시연 포함 약 15분 + 질의응답. 예상질문 대응은
`docs/presentation/예상질문_방어.md`에 있다.

## 슬라이드 순서

| # | 슬라이드 | 핵심 한 줄 | 근거 |
|---|---|---|---|
| 1 | 표지 | 한국어 영상 모먼트 검색 + AAR | — |
| 2 | 문제 | **자막 검색은 아무도 말하지 않은 장면을 못 찾는다** | test 장면형 자막 단독 MRR 0.174 |
| 3 | 실패 예시 1장 | 같은 구간의 자막에는 질의 단어가 없고 캡션에는 있다 | README `pb_q10` (공표된 test 결과) |
| 4 | 접근 | 두 채널 + z-score 융합, 학습 없음 | SYSTEM_ARCHITECTURE |
| 5 | 파이프라인 | M1→M7 한 장 (mermaid) | SYSTEM_ARCHITECTURE |
| 6 | **라이브 시연** | preflight → 장면형 → 자막형 → 복합형 → low-relevance 예시 | DEMO_SCENARIOS |
| 7 | 결과 | MRR 0.649 → **0.829** [+0.058, +0.310] | results/eval_test.json |
| 8 | 유형별 | 장면형 0.174 → **0.718** / 자막형 0.958 → 0.880 (트레이드오프) | 같음 |
| 9 | 연구 규율 | dev/test 분리 · 튜닝 접촉 0회 · 확정 절차 7회 전건 기록 | DESIGN_SPEC 8-6 |
| 10 | 모델 선택 case study | superiority **unresolved** · incumbent 3B retained | MODEL_SELECTION_CASE_STUDY |
| 11 | 운영 실측 | blocker 없음 / footprint penalty 있음 | OPERATIONAL_PROFILE_SUMMARY |
| 12 | 안전장치 | 잘못된 run이 정상 결과처럼 쓰이는 것을 막는다 | REPRODUCIBILITY_SUMMARY |
| 13 | AAR | 모든 문장에 `[seg#N]` · 주장→시각→근거 추적 | AAR_TRACEABILITY |
| 14 | 한계·향후 | 두 절을 분리해 제시 | LIMITATIONS_FUTURE_WORK |
| 15 | 마무리 | 작동하는 시스템 + 재현 가능한 절차 | — |

## 시연 실패 대비

```
1순위   라이브 검색 (scripts/demo.py)
2순위   --check-only 출력 + SUCCESS_FAILURE_GALLERY의 실제 표 (실행 출력 그대로)
3순위   README의 pb_q10 대조표 (공표된 test 결과)

AAR 1순위   사전 렌더된 AAR_<dev>.md (서버에서 미리 생성)
AAR 2순위   aar_view --out-md 현장 재실행 (GPU 불필요)
AAR 3순위   AAR_TRACEABILITY 구조 설명

라이브 M8 생성은 되면 보여주고 실패하면 즉시 사전 생성물로 넘어간다 —
서버·20GB GPU를 발표 성패의 조건으로 두지 않는다.
녹화물은 만들지 않는다 (2026-08-09 결정). 절차는 DEMO_REHEARSAL 참조
```

시연 직전 체크: `python scripts/demo.py --video-id <dev> --check-only` 11항목 PASS ·
`data/videos/<dev>.mp4` 존재 · `pytest tests/ -q` 통과.

## 예상 질문 — 짧은 답 3개

**"왜 3B인가? 4B가 더 신형인데."**
> 우열이 아직 정해지지 않았다. 두 표본이 반대 방향이고 둘 다 CI가 0을 배제한다. 4B는
> 6GB·4bit에서 OOM 없이 돌아가는 viable candidate이지만, incumbent를 교체할 fresh
> deployment-relevant evidence가 없어서 현재 배포를 유지한다.

**"자막형이 떨어졌는데 왜 융합을 쓰나?"**
> 트레이드오프를 숨기지 않는다. 자막형 0.958 → 0.880 대신 장면형 0.174 → 0.718을 얻는다.
> 전체 MRR은 0.649 → 0.829이고 CI가 0을 배제한다. 자막형은 원래 자막 검색이 잘하는 영역이다.

**"test를 여러 번 돌린 건 과적합이 아닌가?"**
> 튜닝 목적 접촉은 0회다. 확정 절차 공식 평가 7회의 사유를 전건 기록했고, 무효 처리한
> 1회와 경계 사례 1건까지 적었다. 적응성 기준으로 DESIGN_SPEC 8-6에서 방어한다.

## 발표에서 쓰지 않을 말

```
"3B가 더 좋다" · "4B는 실패했다" · "P3를 못 해서 3B가 이겼다"
"4B가 운영비가 싸다" · "계산적으로 더 효율적"
데모 결과를 성능 근거로 제시하는 것 (descriptive demonstration이다)
```

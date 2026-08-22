# I1 detector validation 결과 — one-shot 소비 (2026-08-22)

**한 번만 하는 평가였고 소비했다.** 이 문서는 결과 기록이고, 여기 수치를 근거로
detector를 다시 만지지 않는다(보충1 §6 종료 규칙). 사전등록:
`I1_detector_보충2_validation표집` · `보충3_표집확정` · `보충4_판정근거`.
freeze: `docs/I1_detector_candidate_freeze_2026-08-20.md`.

## 0. 결론

```
판정        primary·fallback 둘 다 **우세 관측** (보충4 §5 판정식)
채택        fallback R_only(R=2)
채택 이유    **validation에서 더 좋아서가 아니다** — 오히려 primary가 2건 더 잡았다.
            결과 전에 고정한 동률 해소 규칙(simple_rule_preference)이 단순한 규칙을
            택하기 때문이다 (보충1 §5)
경계        우세 관측은 **hard gate 승격이 아니다.** 재캡셔닝 트리거로 만드는 것은
            확정 인덱스에 영향을 주는 변경이라 사용자 승인 + 별도 사전등록이다
```

## 1. 라벨 (A단계)

```
표본        83프레임 / 84 인스턴스 (C2 60 · C0 24)
완결        83/83 · 허용외 값 0 · 중복 0 · unclear 0
분포        no_text 69 · korean_text_only 14 · cjk_text_present 0 · unclear 0
sha256      6f3d7ed9aa3a747a98e66916e6c0a989000550f12ec8721e43c04330fc8676cf
```

**B단계는 공집합이다.** B는 `cjk_text_present`만 대상이고 그 라벨이 0건이었다.
따라서 "B에서 캡션을 봐야 해 candidate-blind가 깨진다"는 사전등록의 한계는 이번
표본에서 **발동하지 않았다** — B 설계의 한계가 사라진 것이 아니다.

## 2. 재현 게이트 (carried-over census)

```
published    baseline 71 · primary 71 · fallback 70   drift 71
recomputed   baseline 71 · primary 71 · fallback 70   drift 71     match true
```

공표값을 타이핑하지 않고 dev 산출물 `i1_detector_dev.json`의 `by_cell`에서 파생했다
(`docs/probes/i1_carried_census.py`, 테스트 9건). 즉 **공표값과 독립된 계산 경로**다 —
같은 development data에서 나왔으므로 통계적으로 독립된 evidence는 아니다.

## 3. 판정 근거 블록 — fresh_strata_only (C0 + C2)

```
참 라벨      drift 60 (C2 전량) · not_cjk_drift 24 (C0 전량, cjk_count 0) · 제외 0

규칙                     fired  tp  precision           recall(C2)  CI
현행 baseline               0    0  측정 불가            0.0000     [0.0000, 0.0602]
primary  R_or_T(2, 0.02)   28   28  1.0 [0.879, 1.0]    0.4667     [0.3463, 0.5911]
fallback R_only(2)         26   26  1.0 [0.871, 1.0]    0.4333     [0.3157, 0.5590]

est_tp / est_drift  baseline 0.0 / 734 · primary 342.5 / 734 · fallback 318.1 / 734
```

판정식(보충4 §5)에 넣으면 두 후보 모두 **recall CI가 현행과 겹치지 않고 더 높으며
precision ≥ 0.95** → 우세 관측이다.

**관측 FP는 0건이다.** primary 28/28, fallback 26/26이 참 drift였다. 다만 point
estimate가 1.0이어도 CI 하한이 0.879 · 0.871이므로 **"이 규칙은 FP가 발생하지 않는다"로
확정하지 않는다.** 지표 명칭도 `freshly sampled rule-expansion region precision`이고
whole-detector precision이 아니다 — 현행 규칙의 발동 층 잔여가 0이라 후자는 이
모집단에서 측정 불가이고, 실제로 baseline은 fresh 층에서 한 번도 발동하지 않았다.

## 4. 사전등록 가정과 관측이 어긋난 곳 1건

```
preregistered expectation   separable_on_fresh_data = false
                            (두 후보를 가른 층 C4의 잔여 모집단이 0이므로)
observed                    **반증됐다** — fresh C2에서 2 인스턴스가 두 후보를 갈랐다.
                            primary만 발동했고 그 2건은 전부 TP다
selection rule              변경 없음. simple_rule_preference 그대로 적용 → R_only(2)
```

사전등록을 고치지 않는다. **결과가 사전등록 가정과 달랐다는 사실을 기록한다.**
primary로 옮기려면 그것은 validation 결과를 보고 후보를 재선택하는 것이므로 별도
사전등록 사건이다.

## 5. combined_with_carried_over — descriptive context only

```
baseline  est_tp  71.0 / 805   recall 0.0882
primary          413.5 / 805          0.5137
fallback         388.1 / 805          0.4821
precision        출력하지 않음 — carried census에 fired가 없어 FP 0을 가정해야 계산되고
                 그 방향이 세 규칙 모두에게 유리하다 (보충4 §4)
```

C1·C4·C5는 development census를 이어받았고 **이번에 재검증되지 않았다.** 이 블록을
fresh confirmation으로 부르지 않는다.

## 6. 한계

```
표본 구조   프레임 클러스터이고 같은 영상·콘텐츠 구조가 남아 있다 — 실제 불확실성은
           Wilson 구간보다 넓을 수 있다. 폭이 좁다고 정밀도가 충분하다고 하지 않는다
CI 해석     descriptive_only. 폭이 겹치면 겹쳤다고 적는다
모집단 소진  C1·C4·C5 잔여가 0이라 whole-detector fresh precision은 이 모집단에서
           측정할 수 없다. 다른 영상을 추가하지 않는 한 재측정 경로가 없다
라벨러      설계자와 동일인이다. 그래서 판정근거 문서를 첫 A 라벨 **전에** 커밋했다
```

## 7. provenance

```
analysis_commit          ab73e1c76badb56538784b9db7e049ef3936e243
labels_v.csv sha256      6f3d7ed9aa3a747a98e66916e6c0a989000550f12ec8721e43c04330fc8676cf
b_target_count           0
carried gate enabled     true · derived_not_transcribed
산출물                    docs/probes/_scratch/i1_validation_analysis.json
                         docs/probes/_scratch/i1_carried_census.json
                         docs/probes/_scratch/i1_validation_provenance.json
```

## 8. 이 결과로 하지 않는 것

```
재튜닝      R=1 추가 · 새 특징 · 임계 재조정 · C4 census 재사용 — 전부 금지
승격        재캡셔닝 트리거화(확정 인덱스 영향)는 사용자 승인 + 별도 사전등록
전용        이 결과를 4B 채택·test 개방 논의의 근거로 쓰지 않는다 — 독립 트랙이다
```

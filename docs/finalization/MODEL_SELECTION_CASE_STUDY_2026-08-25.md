# 캡션 모델 선택 — 1-page case study (2026-08-25)

**새 비교 실험을 하지 않았다.** 기존 결과만 정리한 발표·보고서용 요약이다.

## 질문

배포 캡션 모델을 `Qwen2.5-VL-3B`에서 `Qwen3-VL-4B`로 바꿀 근거가 있는가.

## 증거 — 두 표본이 반대 방향이고 둘 다 CI가 0을 배제한다

| 표본 | 규모 | 캡션 단독 Δ (4B−3B) | 융합 α=0.5 Δ | 정밀도 | 출처 |
|---|---|---|---|---|---|
| AI Hub (재사용) | 1,086질의 · 194 cluster | **+0.0310** [+0.0080, +0.0536] | +0.0191 (cluster CI 0 배제 · query CI 0 포함) | 양 arm bf16 | `docs/재분석_2x2_2026-08-18.md` |
| dev (배포 유사) | 96질의 · **cluster 3** | **−0.0903** [−0.2112, −0.0276] | −0.0764 (산술차, CI 미사전등록) | 양 arm 4bit | `docs/재분석_dev정밀도3arm_2026-08-18.md` |

**AI Hub는 재사용 표본이다** — 이미 `4B/P1 vs 3B/P0` 확증에 한 번 썼으므로 확증이 아니라
선택·추정이다. **dev는 cluster가 3이라 CI가 진단용**이다(사전등록 보충 §1). 어느 쪽도
확증 자격이 없다.

## 부분 해명 — 어디서 갈리는지

**질의 유형별** (dev, 캡션 단독 Δ): 복합형 n=34 **−0.2407** · 자막형 n=24 −0.0412 ·
장면형 n=38 **+0.0132**. 캡션 의존이 가장 큰 장면형에서는 4B가 근소 우세이고, 복합형이
−0.0903 전체를 끌고 간다. **AI Hub에는 유형 라벨이 없어** 유형 구성 차이를 검정할 수 없다.

**후보 풀 크기** (`docs/재분석_P1풀크기_2026-08-18.md`): 두 데이터셋에서 조작 방향이 반대인데
`I_pool` 부호가 같다(둘 다 예측대로 음수). 그러나 **남은 격차 약 0.067은 설명되지 않았다.**
`I_pool`을 adoption gate로 승격하지 않는다 — **plausible contributor까지이고 root-cause
증명이 아니다.**

**양자화는 설명이 아니다** — 4B bf16도 −0.0994로 함께 열세였다.

**기전 관측 하나**: 같은 프롬프트에서 캡션 길이가 3B 131.4자 vs 4B 82.0자(AI Hub) ·
133.6자 vs 82.9자(배포 노트북)다. 짧은 출력이 검색에 유리한지 불리한지는 **여기서
판단하지 않는다.**

## 운영 실측 — 교체 가능성 자체는 열려 있다

실제 6GB 배포 노트북(RTX 3060 Laptop) · 양 arm 실효 4bit · 프레임 40장 · 교대 배치.

```
frame당 wall-clock 중위수   3B 8.061s   4B 5.974s   (비 0.7065~0.7411, 두 실행 모두 4B가 짧다)
peak reserved VRAM         2.637GB     3.068GB     (+0.431GB)
생성 중 최소 free VRAM      2.34~2.42GB 1.906GB
모델 저장                   7.00GB      8.28GB      (+1.28GB)
OOM · 실패                  0 · 0       0 · 0
```

판정: **deployment blocker는 관측되지 않았고, resource-footprint penalty는 관측됐다.**

동일 prompt/config에서 4B 출력이 더 짧았고 그 결과 end-to-end caption wall-clock이 더
짧게 관측됐다. **"4B가 운영비가 더 싸다"·"계산적으로 더 효율적이다"라고 쓰지 않는다** —
전력·금전 비용을 측정하지 않았고 generation kernel 속도를 분리 측정하지 않았다.

## 외부 문헌 — contextual only

Qwen3-VL은 텍스트 타임스탬프 정합·interleaved-MRoPE·OCR 32개 언어 등 **세대 개선을
주장**한다. 그러나 (1) 동급 3B↔4B 공식 head-to-head 표가 없고, (2) 벤치마크가 한국어
long-form이 아니며, (3) 캡션→임베딩→랭킹이라는 본 프로젝트 endpoint를 대리하지 않고,
(4) 공개 수치는 bf16이며, (5) 캡션 길이 효과가 측정되지 않았다. 관련 temporal 벤치마크에서
**공식 보고값과 공개 재현 시도 사이 큰 차이가 보고된 사례**도 있다.

**외부 벤치마크는 adoption gate가 아니다.** 상세: `docs/finalization/EXTERNAL_BENCHMARK_CONTEXT_2026-08-25.md`.

## 결론

```
scientific superiority   unresolved
deployment decision      incumbent 3B retained
4B                       viable candidate / not adopted
```

**3B를 유지하는 이유는 "3B가 우월하다고 증명됐기 때문"이 아니다.** 정확히는
**4B가 incumbent를 교체할 충분한 fresh deployment-relevant evidence를 확보하지
못했기 때문에 현재 배포를 유지한다.**

교체를 판단하려면 새 표본이 필요하다. 설계는 동결됐고(`docs/P3_4B_deployment_confirmation_DRAFT_2026-08-24.md`)
실행은 annotation logistics 때문에 HOLD다 — 최소 가치 효과 **MRR +0.02 초과**,
**300영상 × 5질의 = 1,500 GT 행**, 외부 annotator 경로.

### 쓰지 않는 표현

```
"3B가 더 좋은 모델로 검증됐다"        "4B가 실패했다"
"P3를 못 해서 3B가 이겼다"           "3B 승리"
```

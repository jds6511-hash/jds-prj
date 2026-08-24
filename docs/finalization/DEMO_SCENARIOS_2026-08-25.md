# 데모 시나리오 (발표용, 2026-08-25)

**dev 영상 3편만 쓴다.** test 영상 4편은 `scripts/demo.py`의 preflight가 거부한다.
아래는 **illustrative demonstration이고 benchmark·evaluation 결과가 아니다.**

실제 실행 출력: `docs/finalization/SUCCESS_FAILURE_GALLERY_2026-08-25.md` ·
원자료 `DEMO_GALLERY_2026-08-25.json` (배포 구성 3B/4bit · KURE-v1 · α=0.5).

## 시연 순서 (약 8분)

```
0:00  preflight 보여주기      python scripts/demo.py --list
                            python scripts/demo.py --video-id <dev> --check-only
                            → 배포 identity·인덱스 정합 11항목이 화면에 찍힌다
1:00  웹 UI 시작             python scripts/demo.py --video-id <dev>
1:30  장면형 질의 (라이브)     발화가 없는 장면을 찾는다 — 자막 검색이 못 하는 것
3:30  자막형 질의            특정 발화 지점으로 이동
5:00  복합형 질의            장면 + 발화가 함께 걸리는 질의
6:30  근거·재생 시연          결과 카드 클릭 → 해당 timestamp 재생 · 발화/화면 근거 확인
7:30  무관 질의              low-relevance 경고 배너 (τ=0.55, 결과를 숨기지 않는다)
```

녹화물이 아니라 **라이브 검색**으로 한다(2026-08-09 결정 — 데모 GIF는 만들지 않는다).

## 질의 성격 3종 — 각각 무엇을 보여주는가

### 1. 장면 중심 (장면형)

```
사용자 의도   "그 장면"만 기억나고 무슨 말이 나왔는지는 모른다
왜 유용한가   발화가 없는 구간은 자막 검색으로 도달할 수 없다.
            공식 test에서 이 유형의 MRR이 0.174 → 0.718로 움직였다(공표된 결과)
dev 관측     kh_q08 성공(1위) · wl_q05 부분(3위) · gw_q05 어려움(5위 밖)
            → **세 유형 중 편차가 가장 큰 유형이 장면형이다** (dev 9건 기준 기술값)
```

### 2. 발화 중심 (자막형)

```
사용자 의도   들은 말은 기억나는데 그게 몇 분인지 모른다
왜 유용한가   자막 채널이 강한 영역. 융합이 자막 단독보다 약간 손해를 보는 구간이기도 하다
            (공식 test 0.958 → 0.880) — 트레이드오프를 숨기지 않고 그대로 말한다
dev 관측     gw_q01 · kh_q02 · wl_q01 전부 1위
```

### 3. 장면 + 발화 복합 (복합형)

```
사용자 의도   "그 얘기 하면서 그걸 보여주던 부분"
왜 유용한가   두 채널이 서로를 보완해야 맞는 구간. 융합의 존재 이유
dev 관측     gw_q04 · kh_q01 · wl_q09 전부 1위
```

## 무관 질의 — low-relevance robustness 예시

영상에 없는 것을 물으면 `low_relevance` **경고 배너**가 붙는다.

> **거부(abstain) 규칙이 아니다.** 결과를 숨기거나 "결과 없음"을 반환하지 않는다.
> 랭킹도 바뀌지 않는다 — 표시 계층 경고 하나다 (DESIGN_SPEC 8-2: "UI 배너만, 랭킹 불변").
> 발표에서는 **low-relevance robustness 예시**라고 부르고 "시스템이 abstain했다"고
> 말하지 않는다.

```
판정        max(raw_sub_max, raw_cap_max) < τ=0.55
τ 근거      dev 96 유관 vs 무관 20으로 재캘리브레이션 (2026-07-13)
            sub 단독 기준은 장면형을 오배제해서 max(sub, cap)으로 바꿨다
동작        결과를 숨기지 않고 경고만 붙인다 — 랭킹 불변
내부 이름     config 키는 abstention_tau다(동결). 사용자 대면 문구는 low-relevance 경고
```

## 시연 중 하지 않는 것

```
test 영상·질의 사용            preflight가 거부한다
α 변경 · 모델 교체             preflight가 거부한다 (배포 구성 외 조합 fail-closed)
"이 데모가 성능을 증명한다"는 말   descriptive demonstration이다
결과를 보고 좋은 질의만 골라 보여주기  gallery는 영상을 돌아가며 dev 질의셋 앞에서부터 골랐다
```

## 준비물 체크

```
python scripts/demo.py --list                       인덱스 완성 영상 확인
python scripts/demo.py --video-id <dev> --check-only  11항목 PASS 확인
data/videos/<dev>.mp4 존재                          없으면 재생 불가 (검색은 됨)
python -m pytest tests/ -q                          전체 통과 확인
```

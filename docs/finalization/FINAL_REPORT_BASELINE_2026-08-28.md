# 최종 보고서 baseline — 한국어 장편 영상 모먼트 검색 파이프라인 (2026-08-28)

```
report_baseline_date      2026-08-28
includes_research_through  AAR-v2 STEP A
does_not_include           AAR-v2 STEP B 이후
status                     이 시점 그대로 제출 가능한 초안
```

이후 STEP B를 수행하더라도 이 baseline의 historical identity를 유지한다. STEP B
결과는 **addendum 또는 revision으로 명시적으로 추가**하며, 이 문서를 조용히 다시
쓰지 않는다.

수치 색인: `final_report_facts_2026-08-28.json` (fact_id · value · source_path).
이 문서의 모든 숫자는 그 색인을 통해 원본 artifact로 연결된다.

---

## 1. 초록

긴 한국어 영상에서 사용자가 원하는 순간을 자연어로 찾아 그 시점부터 재생하고,
근거를 추적할 수 있으며, 선택적으로 사건 중심 보고서를 생성하는 시스템을 구축했다.

**검색 파이프라인은 실제 동작하는 수준으로 완성했다.** 확정 배포 구성
(Qwen2.5-VL-3B / P0 / 4bit · Whisper large-v3 · KURE-v1 · z-score 융합 α=0.5)에서
공식 test 39질의 기준 MRR 0.6489 → 0.8286, Hit@1 0.5641 → 0.7692였다(자막 단독 대비
자막+캡션 융합). 외부 영상 4편에 대한 기능 E2E는 4/4 PASS였다.

**캡션 모델 교체(3B → 4B) 판단은 미결로 남겼다.** AI Hub 재사용 표본(1,086질의)에서는
캡션 단독 4B가 +0.031(query CI [0.008, 0.0536], p=0.006) 앞섰으나, 배포 유사 dev
표본(96질의·영상 3편)에서는 −0.0903으로 방향이 뒤집혔다. 우열을 확정하지 못했으므로
**3B incumbent를 유지**했다.

**검색 이후 단계인 M8(사건 중심 보고서 생성)은 산출물 생성 자체에는 성공했으나
사전 정의된 acceptance 기준을 충족하지 못했다.** 판정 패널 8편 전부에서 구조적으로
유효한 보고서가 생성됐고(실패 0편, 인용 없는 평가대상 문장 0건), 정답 사건 68건 중
46건(67.65%)에 대응하는 생성 사건이 있었다. 그러나 동결된 관문 세 개
(C1 파국 0편 · C2 사건 시간정렬 ≥0.70 · C3 압축률 ≤2.00)를 모두 통과하지 못했다
(C1 4/8편 · C2 0.3311 · C3 max 7.00).

실패 원인 분석은 **사건 경계·입도 불일치**를 중심 병목으로 지목했다. 사전 정의된
redesign 2라운드를 수행했으나 일부 지표를 개선하면서 다른 회귀를 만들었고, 판정을
살리기 위한 3라운드를 하지 않고 acceptance FAIL로 종료했다. 후속 feasibility에서
선택적 재생성(STEP 0)과 결정적 거부-후보 구제(STEP 0.5)는 충분한 회수 능력을 보이지
못했다. 더 근본적인 후속 방향으로 boundary-first 아키텍처를 제안했고, 그 가장 앞단
전제만 검증한 STEP A에서 기존 임베딩의 국소 변화 신호가 균등 시간 분할보다 정답
경계 위치에 대해 더 유용한 정보를 담고 있음을 확인했다(0.5500 vs 0.2500).

**한계.** M8 판정 패널은 8편이고, acceptance 임계 일부는 외부 타당성 근거가
제한적이다. 후속 STEP 0/0.5/A는 모두 소비된 패널의 development evidence이며 성능
증거가 아니다. AAR-v2 아키텍처는 구현되지 않았다. 공식 test는 이번 기간에 열지
않았고 M9는 HOLD다.

---

## 2. 목표와 범위

**문제.** 긴 한국어 영상에서 원하는 순간을 자연어로 검색하고, 해당 timestamp부터
재생하며, 그 판단의 근거(자막·캡션)를 확인할 수 있게 한다. 선택적으로 영상 전체를
사건 중심으로 요약한 보고서를 제공한다.

```
범위     장편 영상 · 한국어 · 멀티모달(자막 + 화면 캡션) 검색
         근거 추적성 · 선택적 사건 중심 보고서(AAR)
범위 밖   범용 영상 이해 · 일반 영상 QA · 상용 규모 운영 시스템
```

---

## 3. 최종 시스템 아키텍처

**production search path** (배포 상태).

```
영상
 → 5초 구간 분할
 → Whisper large-v3            자막
 → Qwen2.5-VL-3B / P0 / 4bit   화면 캡션
 → KURE-v1 (1024차원)          자막·캡션·질의 동일 임베딩
 → 자막 채널 검색 · 캡션 채널 검색
 → 채널별 z-score 정규화 후 α=0.5 가중합
 → 순위화된 모먼트
 → 자막·캡션 근거 표시
 → timestamp seek · 재생
```

```
α          config에 없다. CLI 주입(--alpha). 확정값 0.5 (dev grid search)
abstention max(sub, cap) τ=0.55 — 저관련도 배너 경고뿐, 랭킹·결과는 불변
치환        static_threshold = 0 (off)
preflight   12항목 fail-closed. 하나라도 어긋나면 실행하지 않는다
```

**AAR(M8)은 production search path와 분리된 downstream 계층이다.** 4B 후보,
P2/P3 설계, M8 연구 결과, AAR-v2 feasibility는 production 아키텍처에 섞지 않는다.

---

## 4. 검색 성능 — 공식 test

공식 test 39질의(영상 4편, 자막형 12 · 복합형 14 · 장면형 13). α는 dev에서 정한
0.5를 그대로 썼다.

```
                 자막 단독    자막+캡션 융합(α=0.5)    차이 95% CI
MRR                0.6489              0.8286        [0.0583, 0.3098]
Hit@1              0.5641              0.7692        [0.0769, 0.3590]
Hit@5              0.7692              0.8718        [-0.0256, 0.2564]
Hit@10             0.7949              0.9231        [-0.0256, 0.2821]
```

**Hit@5·Hit@10은 CI가 0을 포함한다 — 유의를 주장하지 않는다.**

유형별 MRR(사후 부분집합이며 검정하지 않았다).

```
장면형  0.1741 → 0.7183   n=13    캡션 채널의 기여가 가장 크다
복합형  0.8246 → 0.8869   n=14
자막형  0.9583 → 0.8802   n=12    유일한 하락 — 트레이드오프이고 숨기지 않는다
```

test 접촉 이력: 튜닝 0회, 공식 절차 7회(검색 M6 5회 + 리포트 M9 2회).
**이번 기간에 test를 다시 열지 않았고 39→72 확장도 하지 않았다.**

---

## 5. 캡션 모델 선택 — 미결

캡션 단독(α=0.0)과 융합(α=0.5)은 **다른 endpoint다.** 값을 섞어 쓰지 않는다.

```
AI Hub 재사용 표본        1,086질의 · 194 클러스터 · arm당 캡션 2,328건 · 양 arm bf16
  캡션 단독 MRR            3B/P0 0.4773 · 4B/P0 0.5083
  Δ(4B − 3B)               +0.031   query CI [0.008, 0.0536] · p = 0.006
  융합(α=0.5) Δ            +0.0191  (cluster에서 0 배제 · query CI는 0 포함)
  자막 단독 MRR            0.4107 — 네 arm 전부 동일 (채널 격리 증거)

dev 배포 유사 표본        96질의 · 클러스터 3 · 양 arm 실효 4bit
  캡션 단독 MRR            3B/P0/4bit 0.4644 · 4B/P0/4bit 0.3741 · 4B/P0/bf16 0.3650
  Δ(4B − 3B)               −0.0903  CI [−0.2112, −0.0276] — 클러스터 3이라 diagnostic only
  양자화 효과 Δ            0.0091   CI [−0.0406, 0.0656] — 양자화는 설명이 아니다
  융합(α=0.5) Δ            −0.0764
```

**두 표본에서 부호가 반대다.** AI Hub는 확증에 이미 1회 사용한 재사용 표본이므로
선택·추정 용도이고, dev는 클러스터가 3개뿐이라 CI를 formal gate로 쓸 수 없다.

```
현재 배포   Qwen2.5-VL-3B / P0 / 4bit · α = 0.5
```

> **3B가 4B보다 우월하다고 증명되어서가 아니라, 4B로 교체할 충분한 fresh
> deployment-relevant evidence를 확보하지 못했기 때문에 incumbent를 유지했다.**

`3B 승리`·`4B 기각`·`4B 실패`·`P3를 못 해서 3B가 이겼다` 같은 표현을 쓰지 않는다.
과학적 우열은 **unresolved**다.

---

## 6. 캡션 → 검색 정성 사례 연구

영상 1편(`pland_costco_hosting`, 395구간)의 5개 장면, 장면당 3질의(대상·행위·관계),
총 15질의. 캡션 단독(α=0.0)에서 새로 생성한 3B/4B 캡션을 비교했다. 질의·장면은
결과 열람 전에 해시로 동결했다.

```
top1 적중(예시적)        3B 2 / 15 · 4B 2 / 15
target 순위가 더 높은 질의 3B 4 · 4B 11 · 동률 0
target 순위 중앙값        3B 31 · 4B 10
캡션 평균 길이(자)        3B 128.5 · 4B 76.4
현행 QC 규칙 flag        3B 4 · 4B 1
```

```
scene02   같은 프레임에서 3B는 배너 문구를, 4B는 냉장 진열대를 캡션에 남겼고
          질의가 어느 요소를 묻느냐에 따라 top1이 뒤집혔다
scene01   target 캡션에 질의 어휘(팬·기름·새우·튀기다)가 없어
          그 어휘를 가진 다른 구간(seg188)이 1위가 됐다
```

**한 영상 5장면 15질의의 정성 사례 연구다.** 모델 정확도 추정·벤치마크·유의성
결과가 아니고 채택 근거로 쓰지 않는다.

---

## 7. 검색 시스템 기능 검증 — 외부 E2E

외부 영상 4편, PHASE 1~4 전부 PASS. **기능 검증이지 외부 검색 벤치마크나 일반화
증명이 아니다.**

```
PHASE  성격                 길이(초)     구간   판정   파이프라인(초)
1      짧은 장면 중심          287.951      58   PASS         538
2      발화 중심 강연          623.595     125   PASS       2,001
3      장면 + 발화 혼합      1,289.474     258   PASS       2,610
4      장편 스트레스(선택)   4,115.992     824   PASS       8,468
```

검증한 단계: ingest · STT · caption · embedding · index · search · playback.
재생 근거: Range 요청 206 · 잘못된 id 404 · seek == start.
제외: `e2e_kfood`(인증 필요 — 우회하지 않았다).

PHASE 4에서 외부 timestamp 기준 anchor 2건을 REVIEW로 기록했다. anchor 1465초의
실제 자막은 다른 내용이었다. **anchor를 사후 수정하지 않았고, 이는 외부 참조
데이터 품질 문제이지 검색 정확도 판정이 아니다.**

---

## 8. AAR / M8 — 무엇을 평가했나

M8은 "보고서를 만들 수 있는가"만 본 것이 아니다. 사전 정의된 acceptance gate로
다음을 평가했다.

```
C1  파국적 생성 실패        language_drift · early_stop · repetition_loop
                            임계 0편 (하나라도 있으면 FAIL) · 3-state 판정
C2  사건 시간정렬            event_temporal_alignment 중앙값 >= 0.70
                            Hungarian 1:1 · 미매칭 정답은 0으로 센다
C3  압축률                   문장 수 ÷ 정답 사건 수 · max <= 2.00
구조 유효성                  스키마 · 인용 없는 평가대상 문장 0
```

M8은 **downstream 보고서 생성 연구 모듈**이며 검색 acceptance와 분리한다.

판정 순서는 되돌릴 수 없도록 미리 고정했다 — 소싱 규칙 → 후보 풀 해시 → 결정적
선정 → 사람 GT → GT 해시 → gate 규격 → evaluator 해시 → 생성 → 판정.

---

## 9. M8 baseline 결과

```
패널               영상 8편 · 정답 사건 68건
생성                8/8편 완료 · 실패 0편
모델                Qwen2.5-7B-Instruct · bf16 · 비양자화 · greedy
                   max_new_tokens 16384 · chunk 60 / overlap 5
구조 유효성          인용 없는 평가대상 문장 0건 (8편 전부)
생성 사건            93건
정답 대응            46 / 68 = 67.65%
미매칭 정답          22건 (그중 짧은 사건 18건)
미매칭 생성          47건
```

관문 판정.

```
C1  파국 영상 4 / 8            임계 0        FAIL
C2  정렬 중앙값 0.3311          임계 0.70     FAIL
C3  압축률 max 7.00            임계 2.00     FAIL

M8 evaluation   COMPLETE
M8 acceptance   FAIL
```

> **M8은 산출물 생성 자체에는 성공했지만 동결된 품질 acceptance를 통과하지
> 못했다.**

`M8은 보고서를 생성하지 못했다` · `M8은 완전히 실패했다` · `모델이 보고서를 못
쓴다`는 사실과 다르다.

---

## 10. 실패 원인

쉽게 말하면 이렇다.

> **놓치는 사건을 줄이려고 재현율을 올렸더니, 이번에는 사건을 너무 많이 만들기
> 시작했다.**

```
지표                  baseline    ROUND 1    ROUND 2   해석
미매칭 정답 사건            22         10         10   재현율은 실제로 올랐다
  그중 짧은 사건            18         10         10
생성 사건 총수              93        219        134   baseline의 2.4배 → 1.4배
미매칭 생성 사건            47        161         76   과생성이 회복되지 않았다
정렬 중앙값            0.3311     0.3892     0.4498   꾸준히 개선
압축률 max               7.00      16.00      13.00   악화 후 부분 회복
거부                        11         44         21
C1 파국 영상                 4          3          5
repetition_loop 영상         0          1          1   새 파국이 생겼다
비한국어 사건명               2          1          0
사건 0건 청크                1          3          5
```

ROUND 2 동결 gate 판정.

```
A  미매칭 정답 < 22          22 → 10        PASS
B  미매칭 생성 <= 47         47 → 76        FAIL
C  압축률 max <= 7.00      7.00 → 13.00     FAIL
D  정렬 중앙값 > 0.3311   0.3311 → 0.4498   PASS
E  새 repetition_loop 0편     0 → 1편       FAIL
F  새 catastrophic 없음    C1 4 → 5편       FAIL
```

편별로 보면 수렴 폭의 편차가 컸다.

```
잘 회복    wonyi_gyeongju 후보 28 → 10 · wonyi_geoje 17 → 9 · kbs_banff 55 → 22
회귀       jissi_farm  baseline에서 정상이던 편(생성 11 · 압축률 1.00)이
                       전역 고재현율 압력으로 후보 59까지 늘고 최종 생성 32 · 압축률 2.91
```

**외부 보고 문구는 다음으로 고정한다.**

> consolidation은 ROUND 1의 일부 과분할을 완화했지만, acceptance에 필요한 수준까지
> 안정적으로 수렴시키지는 못했다.

`방향은 옳았고 크기가 부족했다`는 정상이던 영상을 망가뜨린 회귀를 가리므로 쓰지
않는다.

---

## 11. 사건 경계·입도 문제

판정 패널의 정답 사건 68건의 길이 분포.

```
min 10초 · p25 30초 · median 62초 · p75 181초 · max 865초

<=40초        23 / 68   34%
45~180초      28 / 68   41%
>180초        17 / 68   25%
```

> 본 패널에서는 사건 길이 분포가 매우 넓어, 단일 고정 입도 설계가 다양한 정답
> 사건을 동시에 맞추기 어려운 구조를 보였다.

원리적 불가능성을 주장하는 것이 아니라 **이 패널의 관측**이다.

baseline 미매칭 정답 22건 중 18건이 짧은 사건이었다. 즉 실패가 무작위로 흩어진
것이 아니라 **짧은 사건 쪽에 몰려 있었다.**

극단 사례로 `m8c2_3I7oGwk6EaQ`는 정답 사건이 1건(영상 전체 865초)이라, 압축률
`문장 수 ÷ 1`이 임계 2.00을 넘지 않으려면 사건을 2건 이하로 끝내야 한다. 이 영상의
압축률 7.00이 C3 max를 결정했다.

---

## 12. 사람 서술과의 정성 대조

`wonyi_geoje` 1편에서, 사람이 쓴 사건 중심 서술 7개 절을 동결 GT 8건과 **사후에**
대조했다.

```
병합 1건 · 분할 1건 · 누락 1건 (짧은 아웃트로)
같은 영상 M8 산출물: 생성 10건 중 정답과 매칭되지 않은 것 3건
```

> 이 단일 사례에서 사람이 작성한 사건 구조는 동결 GT와 비교적 가까운 형태를 보였다.

한계를 그대로 적는다.

```
① 소비된 판정 패널의 영상이다 — 독립 표본이 아니다
② 7절 ↔ 8건 대응은 사후에 사람이 매핑한 것이다
③ 서술과 GT를 같은 사람이 만들었다
④ n = 1편이다
```

`사건 입도 정의가 모호하지 않음을 증명했다` · `따라서 M8 실패 원인은 모델이다`
같은 진술은 하지 않는다.

---

## 13. 왜 판정을 바꾸지 않았는가

```
gate를 결과 보고 변경         하지 않았다 — 임계·통계량·지표·taxonomy 무변경
amendment 소급 적용            하지 않았다
ROUND 3                       하지 않았다 (사전 정의된 라운드 상한 2회)
outcome-informed 가설          H3 · H5~H7을 future work로 분리하고 출처를 명시했다
official test                  열지 않았다
M9                            HOLD
```

ROUND 2의 `early_stop` 4편은 전부 분할로 회수된 청크였고, detector가 `chunk_splits`
회수를 모르는 **구현 결함**이다. 그 사실은 기록으로 유지하되 **판정을 살리기 위해
당겨 적용하지 않았다** — 적용해도 E(새 repetition_loop 1편)와 B·C는 여전히 실패다.

동시에 기준 자체의 한계도 적는다.

> 기준을 사전 동결했고 실패 후 변경하지 않았지만, 일부 절대 threshold의 외부 타당성
> 근거가 제한적이라는 한계도 남는다.

특히 C2의 0.70은 원 사전등록이 외부 근거가 없다고 스스로 밝힌 값이다. 그럼에도
결과를 보고 낮추지 않았다. `기준을 지켰으니 기준이 완벽하다`고 쓰지 않는다.

---

## 14. STEP 0 — 선택적 trigger feasibility

M8-v1 판정과 분리된 후속 development diagnostic이다. 새 라벨 0 · 생성 0 · LLM 0.

```
T1  accepted_event_count == 0 (원안 H6a)
    발화 1 / 41 청크 · 도달 1 / 22 = 4.5%       STRUCTURAL NO-GO
    그 청크는 baseline이 이미 재생성을 시도했다가 회수 실패한 자리다

후보 38개 전량 sweep · GO 8개
선택 T2@0.7  accepted_span_coverage < 0.7
    도달 10 / 22 · 영상 4 · 발화 8 / 41 · 헛발화 2 · 최대 점유 0.60
```

**핵심 발견은 선택된 trigger가 무엇을 골랐는지였다.**

```
발화 8청크 안     raw 후보 16 · 거부 9   거부 비율 0.5625
패널 전체         raw 후보 104 · 거부 11  거부 비율 0.1058

생성 자체가 없던 청크           1 / 8
후보를 만들었다가 전부 거부된 청크  4 / 8
```

즉 낮은 커버리지의 공백은 **생성 부재보다 거부(rejection)로 생긴 경우가 많았다.**
`softyeon_ceramics`는 커버리지가 1.0/1.0/1.0/0.81이라 T2가 발화하지 않는다 —
**커버리지 기반 trigger의 blind spot**이며, 그 영상의 미매칭 정답 6건은 이번 대상이
아니었다.

STEP 0은 **performance evidence가 아니다.**

---

## 15. STEP 0.5 — 결정적 거부-후보 구제

T2@0.7이 발화한 8청크 안에서, `too_many_evidence`로 거부된 후보의 evidence를
생성 순서 앞 4개로 결정적으로 절단하고 **현행 validator를 그대로 재적용**했다.
새 라벨 0 · 생성 0 · LLM 0.

```
발화 청크 내 거부 후보         9   (too_many_evidence 6 · evidence_outside_span 3)
적격(too_many_evidence)        6
절단 후 VALID                  5
절단 후에도 STILL_REJECTED     1   (evidence_outside_span)
추가된 사건                     5   패널 생성 93 → 98
추가 사건 중 정답과 안 겹친 것   0

새로 회수된 미매칭 정답         4 / 22
회수 영상                       2   kbs_banff 3 · m8c2_cIxG7OHYMPU 1
최대 영상 점유                 0.75
```

> evidence 절단 후 추가된 후보들이 정답 사건과 IoU > 0으로 겹치는 경우가 있었고,
> 기존 미매칭 정답 중 4건이 새로 회수됐다.

`좋은 사건 5개를 완벽히 복구했다` · `5개 모두 정확했다`고 쓰지 않는다. 매칭은
IoU > 0을 뜻하고 정확성을 뜻하지 않는다.

```
A  회수 >= 5        4        FAIL
B  회수 영상 >= 2   2        PASS
C  최대 점유 <= 0.60  0.75   FAIL

STEP 0.5   NO-GO
```

**NO-GO는 구조적이었다.** 적격 후보가 kbs_banff 4 · cIxG 1 · 3I7 1(미매칭 정답 0건)
뿐이라 회수 상한이 5이고, A를 채우려면 kbs가 4를 다 채워야 하므로 점유는 반드시
0.80이 되어 C를 위반한다. **A 충족은 곧 C 위반이었다.**

따라서 fresh M8-v2 연구를 착수하지 않았고 새 영상·새 라벨을 확보하지 않았다.

---

## 16. AAR-v2 아키텍처 가설

M8-v1을 수정한 것이 아니라 **실패 분석에서 도출된 architecture-level 후속 가설**이다.

```
boundary-first          LLM이 큰 청크에서 사건 경계를 처음부터 정하지 않는다
multi-scale 표현         짧은 사건을 먼저 보존하고 상위에서 묶는다
서술 분리                사건이 확정된 뒤에만 LLM에게 1~2문장 설명을 시킨다
결정적 evidence 처리      인용 개수를 모델이 자율 결정하지 않는다
결정적 보고서 조립         문서 전체를 다시 생성하지 않는다
```

> 새 아키텍처는 M8-v1 실패 분석에서 도출된 가설이며, 현재는 가장 앞단의 boundary
> signal만 feasibility를 확인했다.

다음 주장은 하지 않는다.

```
"deterministic merge면 과분할이 해결된다"
  ROUND1 → ROUND2에서 수렴은 부분적으로 작동했으나 영상별 편차가 컸다
  기대할 수 있는 것은 재현성 · 예측 가능성 · fail-closed · 분산 원인 분리이지
  merge 문제 해결 보장이 아니다

"repetition이 제거된다" · "early-stop이 해결된다"
  아키텍처가 바뀌면 legacy C1 detector 자체가 적용 불가일 수 있다.
  그 경우 "C1 PASS"가 아니라 legacy C1 not directly applicable이다

"보고서 품질이 개선된다"   검증되지 않았다
```

---

## 17. AAR-v2 STEP A — Boundary Detectability Probe

기존 산출물만 쓴 결정적 probe다. **새 라벨 0 · LLM 0 · GPU 0 · 새 embedding 0 ·
생성 0.**

```
입력   소비된 M8-v1 패널 8편 · 기존 emb_sub / emb_cap · 동결 GT 경계
GT     사건 68건 → 내부 경계 60개 → 적격 영상 7편
       (사건이 1건인 영상은 경계가 없어 분모에서 제외)
방법   인접 구간 코사인 거리 → 영상 내 채널별 percentile 정규화 → 두 채널 평균
       K = max(1, round(duration / 60)) · 상위 K개 · τ = ±10초 · 1:1 Hungarian
대조   같은 K개를 영상 내부에 균등 배치 (결정적)
```

```
embedding   33 / 60 = 0.5500
uniform     15 / 60 = 0.2500
Δ                     +0.3000

A  Δ >= +0.15                 PASS
B  embedding >= uniform >= 5편  7 / 7   PASS
C  embedding < uniform <= 2편   0       PASS

STEP A   GO
```

**바로 이어서 한계를 적는다.**

```
예측 총수 158 · GT 경계 60 · 적중 33 → 예측당 적중률 0.209 (진단값)
K가 GT 경계 수의 2.6배다 — recall만 쟀고 정밀도는 재지 않았다
uniform 비교자는 단순하다. 소박한 우연 기대치(≈0.345)로 바꿔도 Δ = +0.205로 판정은
  유지되지만, 이 계산은 사전등록에 없으므로 강건성 관찰로만 남긴다
kbs_banff가 0.222로 가장 약하다 — M8-v1 미매칭 정답 8건의 최대 기여 영상이다
소비된 패널의 development evidence다
```

판정에 쓰지 않은 진단.

```
채널        primary 33 · caption-only 32 · subtitle-only 20  — 신호는 대부분 캡션
tolerance   ±5초 0.483 · ±10초 0.550 · ±15초 0.567
경계 인접 사건 길이   짧은 쪽 <=40초 0.560 · 45~180초 0.609 · >180초 0.333
```

> 기존 subtitle/caption embedding의 국소 변화 신호가 균등 시간 분할보다 정답 경계
> 위치에 대해 더 유용한 정보를 포함한다는 feasibility evidence를 얻었다.

`boundary detection이 해결됐다` · `경계를 정확히 찾았다` · `AAR-v2가 성공했다`고
쓰지 않는다.

---

## 18. STEP A가 아직 답하지 않은 것

```
답한 것
  기존 임베딩의 국소 변화 신호가 정답 경계 근처에 더 자주 나타나는가        예

답하지 않은 것
  예측 정밀도                                    미검증
  event proposal 구성                            미검증
  사건 span 구성                                 미검증
  계층(micro / meso) 표현                        미검증
  평가 레벨과 렌더 레벨의 선택                     미정의
  deterministic merge 품질                       미검증
  LLM 사건 서술 품질                              미검증
  evidence attachment 품질                       미검증
  최종 보고서 조립                                미검증
  synthesis(특징·결론) 품질                       미검증
  fresh 일반화                                    미검증
```

**AAR-v2 전체 아키텍처는 구현되지 않았다.**

---

## 19. 사람이 읽을 AAR의 목표 형태 (design target)

향후 최종 보고서의 presentation target으로 다음 구조를 고려할 수 있다.

```
1. 분석 개요        2. 주요 사건        3. 영상의 주요 특징        4. 결론
```

역할을 두 층으로 나눈다.

```
Event factual layer     시간 범위 · 사건 제목 · 사실 서술 · segment citation
Synthesis layer         영상 전체 특징 · 사건 간 패턴 · 결론
                        → 문장마다 근거 event_id provenance가 필요하다
```

내부 표현 예시(설계 목표이며 현재 산출물이 아니다).

```
[특징] 지역 주민들과의 교류가 영상 전반에 반복해서 나타난다.   supports: [E03, E06]
[결론] 영상은 이동·낚시·물놀이·식사로 이어지는 여행 기록 구조를 가진다.
                                                          supports: [E01…E07]
```

`1. 분석 개요`에서도 사실/메타데이터("27분 영상", "화면·자막만 사용", "외부 정보
미사용")와 해석("여행 기록형 콘텐츠")은 분리해야 한다.

**이 구조는 AAR-v2 산출물로 구현된 적이 없다. design target으로만 기록한다.**

---

## 20. 현재 시스템 상태

```
검색 파이프라인                    READY
재생 · seek · 근거 표시             READY
외부 기능 E2E                      COMPLETE  (4 / 4 PASS)
3B / 4B 우열                       UNRESOLVED
배포                               3B incumbent 유지
M8 evaluation                     COMPLETE
M8 acceptance                     FAIL
M8 redesign                       CLOSED (ROUND 3 없음)
STEP 0                            COMPLETE / GO
STEP 0.5                          COMPLETE / NO-GO
AAR-v2 STEP A                     COMPLETE / GO (feasibility)
AAR-v2 full architecture          NOT IMPLEMENTED
P2                                HOLD (라벨 175 계획 · 20 작성)
P3                                설계 동결 · 실행 HOLD
M9                                HOLD
official test                     UNOPENED
```

---

## 21. 한계

```
 1  AI Hub 표본의 외적 타당성 — 재사용 표본이고 배포 도메인과 다르다
 2  dev 클러스터가 3개뿐이라 CI를 formal gate로 쓸 수 없다
 3  3B / 4B 우열 미결 — 두 표본에서 부호가 반대다
 4  캡션→검색 사례 연구는 영상 1편 · 15질의의 정성 관찰이다
 5  P2는 라벨 작성 비용으로 HOLD (175 계획 중 20 작성, 부분 GT 미분석)
 6  P3는 설계만 동결하고 실행 HOLD — 외부 annotator 경로 미확보
 7  캡션 QC는 현행 자동 규칙 기준이며, 규칙을 바꾸면 확정 인덱스가 달라진다
 8  M8 acceptance 임계 일부의 외부 타당성 근거가 제한적이다 (특히 C2 0.70)
 9  M8 판정 패널이 8편이다
10  사건 길이 분포가 넓어 단일 입도 설계가 어렵다 (본 패널 관측)
11  STEP 0 / 0.5는 outcome-informed이고 소비된 패널의 development evidence다
12  STEP A도 소비된 패널의 development evidence다
13  STEP A는 recall만 쟀고 정밀도를 재지 않았다
14  AAR-v2 아키텍처는 구현되지 않았다
15  사람 서술 대조는 n=1 · 사후 매핑 · 동일 작성자다
16  공식 test는 열지 않았고 M9는 실행하지 않았다
```

---

## 22. Future work

```
Near-term 후보 (이 보고서 baseline 확정 이후에 검토)
  AAR-v2 STEP B — boundary → event proposal / granularity feasibility
    다뤄야 할 것: 예측 정밀도 · top-K 과잉예측 · proposal 구성 ·
                 kbs_banff 취약성 · micro/meso 표현 · 평가 레벨 정의

Longer-term
  event 단위 서술 · 결정적 evidence attachment · provenance 있는 synthesis 계층
  fresh 데이터 검증 · M9는 별도 프로토콜에서만 · P3 배포 유사 확증

outcome-informed future work (출처 명시 유지)
  H3 출력 구조 2층화 · H5 영상 전체 2차 수렴 · H6 선택적 고재현율 ·
  H7 생성 파라미터 기반 반복 억제
```

---

## 23. 결론

```
1  검색 시스템은 실제 동작 가능한 수준으로 완성했다
2  캡션 모델 교체 문제는 데이터셋 의존적 증거 때문에 미결로 남겼고
   incumbent를 유지했다
3  M8은 구조적으로 사용 가능한 보고서를 생성했으나
   사전 정의된 품질 acceptance에 실패했다
4  실패 분석은 사건 경계·입도가 핵심 병목 중 하나임을 보여준다
5  단순 재현율 상향과 결정적 거부-후보 구제는 충분한 해결책이 아니었다
6  후속 boundary-first 가설의 첫 전제는 STEP A에서 feasibility GO였다
7  그러나 event proposal과 보고서 품질은 아직 검증되지 않았으므로
   AAR-v2가 성공했다고 결론내리지 않는다
```

이 프로젝트의 최종 성과는 **작동하는 검색 제품, 재현 가능한 평가 절차, 실패를 숨기지
않은 M8 결과, 그리고 실패 분석에서 도출된 검증 가능한 후속 설계**다.

기준을 먼저 정하고 실패했을 때 기준을 움직이지 않은 것 자체가 이 과정의 산출물이다.

---

## 부록 A. 표·그림 계획

```
F1   최종 production 아키텍처                          §3
F2   3B vs 4B 증거 부호 반전 (AI Hub ↔ dev)             §5
F3   캡션 → 검색 scene02 순위 역전                      §6
F4   M8 baseline → ROUND 1 → ROUND 2 지표 추이          §10
F5   M8 트레이드오프 다이어그램 (누락 ↓ · 과생성 ↑)       §10
F6   정답 사건 길이 분포 (68건)                          §11
F7   wonyi_geoje 사람 서술 ↔ GT 정성 대조                §12
F8   STEP 0 / STEP 0.5 결정 트리                        §14·§15
F9   AAR-v2 가설 아키텍처                               §16
F10  STEP A 경계 recall (embedding 0.55 vs uniform 0.25) §17
F11  해결된 것 / 미해결 상태표                            §20
```

새 그래프가 필요하면 **기존 동결 수치만** 쓴다. 새 metric을 만들지 않는다.

## 부록 B. 쉬운 표현 병기

```
technical  M8 generated structurally usable reports but failed the preregistered
           acceptance gates.
easy       보고서 파일은 정상적으로 만들어졌지만, 미리 정해둔 품질 기준까지는 넘지
           못했습니다.

technical  Recall improved but overgeneration regressed; the redesign did not
           converge to acceptance.
easy       놓치는 사건은 줄었지만 불필요한 사건이 늘어서, 전체적으로는 기준을 넘지
           못했습니다.

technical  Boundary-local embedding change signal exceeded uniform temporal
           partitioning in the consumed development panel.
easy       영상 내용을 나타내는 임베딩이 크게 바뀌는 지점이, 시간을 그냥 일정하게
           나눈 것보다 실제 사건 경계 근처에 더 자주 나타났습니다.

technical  Caption model superiority is unresolved; the incumbent was retained.
easy       어느 캡션 모델이 더 낫다고 결론내릴 수 없어서, 쓰던 모델을 그대로
           유지했습니다.
```

## 부록 C. 산출물 경로

보고서의 수치가 나온 authoritative artifact.

```
검색
  results/eval_test.json                                     공식 test 39질의
  results/alpha_search_dev.json                              α 확정 근거
  docs/finalization/e2e_external_results.json                외부 기능 E2E
  docs/finalization/caption_retrieval_casestudy_results.json 캡션→검색 사례 연구
  docs/재분석_2x2_2026-08-18.md                               3B/4B 2x2 재분석

M8
  docs/finalization/m8_c2_gt_freeze_2026-08-27.json          동결 GT (68 사건)
  docs/finalization/m8_evaluator_freeze_2026-08-27.json      evaluator 동결
  docs/finalization/m8_official_result_2026-08-27.json       공식 판정
  results/m8_official_0827/m8_official_full.json             생성 manifest
  docs/finalization/m8_failure_analysis_2026-08-27.json      실패 분해
  docs/finalization/m8_redesign_r2_threeway_2026-08-28.json  baseline/R1/R2 3-way
  docs/finalization/M8_REDESIGN_CLOSURE_2026-08-28.md        종결 판단
  docs/finalization/M8_HUMAN_REFERENCE_CONTRAST_2026-08-28.md 사람 서술 대조

후속 feasibility
  docs/finalization/M8V2_STEP0_SPEC_2026-08-28.md            STEP 0 규격(사전 동결)
  docs/finalization/M8V2_STEP0_RESULT_2026-08-28.md          STEP 0 결과
  results/m8v2_step0/m8v2_step0_reachability_2026-08-28.json STEP 0 frontier 전량
  docs/finalization/M8V2_STEP05_REJECTED_RESCUE_2026-08-28.md STEP 0.5 결과
  runs/m8v2_step05/step05_summary.json                       STEP 0.5 요약
  docs/finalization/AARV2_STEP_A_PREREG_2026-08-28.md        STEP A 사전등록
  docs/finalization/AARV2_STEP_A_RESULT_2026-08-28.md        STEP A 결과
  runs/aarv2_step_a/summary.json                             STEP A 요약

재현 도구 (전부 결정적 · LLM/GPU 없음)
  scripts/m8v2_step0_reachability.py
  scripts/m8v2_step05_rejected_rescue.py
  scripts/aarv2_step_a_boundary_probe.py

지표 정의
  src/m8_metrics.py                                          C1·C2·C3 구현

수치 색인
  docs/finalization/final_report_facts_2026-08-26.json        M1~M7 (수정 안 함)
  docs/finalization/final_report_facts_2026-08-28.json        M8 · STEP 0/0.5/A 추가
```

## 부록 D. 표현 규칙

```
쓴다      M8 evaluation completed, but acceptance failed
          보고서 생성 자체와 품질 acceptance는 구분한다
          일부 과분할을 완화했지만 안정적으로 수렴시키지 못했다
          STEP A는 architecture feasibility evidence다
          boundary signal이 존재한다

쓰지 않는다  M8은 작동하지 않았다
          모델이 보고서를 못 쓴다
          event boundary가 원인임을 증명했다
          AAR-v2가 M8 문제를 해결했다
          STEP A가 boundary detection을 검증했다
          human이 맞고 모델이 틀렸다
          좋은 사건 5개를 복구했다
          deterministic merge면 해결된다
          C1이 개선됐다
          방향은 옳았고 크기가 부족했다
          3B 승리 · 4B 기각 · 4B 실패
```

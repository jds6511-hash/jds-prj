# M8-v2 STEP 0 결과 — Trigger Reachability Pilot (2026-08-28)

```
판정        GO — 동결 기준 4개를 전부 충족한 후보가 8개 있다
선택        T2@0.7   accepted_span_coverage < 0.7
            reachable 10/22 · videos 4 · burden 8/41 · waste 2 · share 0.60

단, 이 pilot은 후보를 고르면서 동시에 **H6의 전제 하나를 반증했다.** §4를 먼저 읽어라.
```

```
새 라벨 0 · 새 generation 0 · LLM 호출 0 · GPU 0
M8-v1 판정 변경 없음 (COMPLETE · acceptance FAIL)
M9 · official test 접근 없음 · push 없음
```

규격은 실행 전에 동결됐다 — `M8V2_STEP0_SPEC_2026-08-28.md`.
threshold·GO 기준·선택 규칙을 결과를 보고 고치지 않았다.

전량 산출물: `results/m8v2_step0/m8v2_step0_reachability_2026-08-28.json`
(후보 38개 frontier 전부 + 청크 41개 feature 전부 + unmatched GT span 전부)

---

## 0. 전제 검증

```
baseline report 8/8   lineage sha256 일치 (m8_official_report_lineage_2026-08-27.json)
청크 경계 8/8          생성기 루프 재현값 == map_raw_outputs 길이
unmatched GT           22 / 68 재계산 — 기존 failure analysis와 일치
청크                   41
```

불일치가 있으면 진행하지 않도록 fail-closed로 짰다.

---

## 1. T1(H6a)은 탈락 확정

```
발화 청크    1 / 41      wonyi_geoje chunk 5
reachable   1 / 22      도달 상한 4.5%  <  요구 20%
그 청크      baseline이 이미 regeneration 시도 · recovered false
그 영상      RELATIVELY_STABLE으로 분류된 편
```

**STRUCTURAL NO-GO.** 후보로 취급하지 않는다.

---

## 2. frontier — 38개 전량

```
id          reach  vid  trig  waste  share   판정
T2@0.7         10    4     8      2   0.60   GO   ← 선택
T4@90          10    4     8      2   0.60   GO
T2@0.8         11    5     9      2   0.55   GO
T4@60          11    5     9      2   0.55   GO
T4@45          11    5    10      3   0.55   GO
T4@30          11    5    11      4   0.55   GO
T2@0.9         12    6    12      4   0.50   GO
T4@20          12    6    12      4   0.50   GO
──────────────────────────────────────────────────
T5a@0.5~0.9     7    2     4      1   0.86   ④ 위반
T5a@0.3         9    3     6      1   0.67   ④ 위반
T5b@0.5~2       9    3     7      2   0.67   ④ 위반
T2@0.2~0.6      8    3     5      1   0.75   ④ 위반
T5b@5           5    1     1      0   1.00   ②④ 위반
T3@2           11    4    16      9   0.45   ③ 위반
T3@3           15    6    22     12   0.33   ③ 위반
T3@5           20    6    31     18   0.40   ③ 위반
T3@6           21    6    34     20   0.38   ③ 위반
T3@1            1    1     1      0   1.00   ①②④ 위반
```

계열별 성격이 갈렸다.

```
T2·T4   좁고 얕다      burden 8~12로 제약을 지키지만 timeline 구멍만 본다
T5      좁고 편중됐다   거부가 kbs_banff에 몰려 한 영상이 86%를 독점 — ④ 위반
T3      넓고 얕다      밀도를 낮게 잡으면 22~34청크 발화 = 사실상 global
```

**T2와 T4는 이 패널에서 사실상 같은 규칙이다.** `T2@0.7`과 `T4@90`은 네 숫자가
완전히 같고 `T2@0.8`과 `T4@60`도 같다. accepted span이 연속 블록이라 "커버리지가
낮다"와 "긴 구멍이 있다"가 같은 청크를 고른다. 계열을 둘로 세지 마라.

선택 규칙(burden 최소 → 영상 수 최대 → 단순성 T2 < T4 → id순)에 따라 `T2@0.7`.

---

## 3. 선택된 후보의 경계 성질 — 그대로 적는다

```
share 0.60    ④의 상한과 **정확히 같다**. 한 건만 움직여도 위반이다
reachable 10  Gate A(≥5)를 만족하려면 reachable의 **50% 이상을 실제 회수**해야 한다
              reachable은 상한이지 회수량이 아니다
waste 2       발화 8청크 중 2개는 unmatched GT를 하나도 안 품는다
```

`T2@0.8`은 share 0.55 · videos 5 · reachable 11로 ②③④에서 더 여유롭고 burden은
+1이다. **선택 규칙이 burden 최소를 1순위로 박아뒀으므로 바꾸지 않는다.** 다만
fresh 단계로 갈 때 이 둘 중 무엇을 동결할지는 규칙이 아니라 판단의 문제로 남는다.

---

## 4. 이 pilot이 반증한 것 — H6의 전제

`T2@0.7`이 고른 8개 청크를 열어보면, 그 공백은 **모델이 아무것도 못 만들어서**
생긴 게 아니다.

```
발화 청크 8개 안에서
  raw candidate      16
  rejected            9        거부 비율 0.56
패널 전체
  raw candidate     104
  rejected           11        거부 비율 0.11
```

```
생성 자체가 없었던 청크          1 / 8
후보를 만들었는데 전부 거부된 청크  4 / 8
```

편별로 보면 더 분명하다.

```
video                ch  span        cov     raw  rejected  reachable GT
kbs_banff             0  [0,59]     0.083     4      4           5
kbs_banff             2  [110,169]  0.167     1      1           1
m8c2_cIxG7OHYMPU      4  [220,279]  0.167     1      1           1
m8c2_cIxG7OHYMPU      0  [0,59]     0.600     5      2           1
m8c2_3I7oGwk6EaQ      2  [110,169]  0.167     1      1           0
wonyi_gyeongju        4  [220,279]  0.600     2      0           1
wonyi_gyeongju        1  [55,114]   0.617     2      0           0
wonyi_geoje           5  [275,279]  0.096     0      0           1   ← 유일한 생성 실패
```

reachable 10건 중 **6건이 kbs_banff의 두 청크**에 있고, 그 두 청크의 후보는
5개 중 5개가 거부됐다. 거부 사유:

```
kbs_banff ch0   too_many_evidence 3 · evidence_outside_span 1
kbs_banff ch2   too_many_evidence 1
cIxG ch0        evidence_outside_span 2
cIxG ch4        too_many_evidence 1
3I7 ch2         too_many_evidence 1
```

`too_many_evidence`는 `MAX_EVIDENCE_PER_EVENT = 4` 초과다. **가장 큰 도달 블록이
모델 재현율이 아니라 출력 형식 제약에서 나왔다.**

### 결과적으로

H6의 전제는 "baseline이 이 구간에서 **사건을 생성하지 못했다**"였다.
발화 청크 8개 중 그 설명이 맞는 것은 **1개**다.

**같은 validator로 고재현율 재생성을 돌리면 같은 거부가 재현될 수 있다.**
`too_many_evidence`는 후보를 더 많이 만들수록 늘어나는 종류의 거부다.

---

## 5. 그래서 무엇이 결정 사항인가

Step 0은 "trigger가 존재하는가"에 GO를 냈다. 그러나 **intervention의 정의**는
이 pilot 결과로 새로 정해야 한다. 그 선택은 outcome-informed이고, fresh 이전에
동결해야 한다.

```
(a) H6 원안 유지        발화 청크에 고재현율 재생성
                       → 발화 청크 8개 중 1개에만 원인이 맞는다
                       → kbs_banff 6건은 다시 거부될 수 있다

(b) 거부 후보 구제      발화 청크의 rejected candidate를 버리지 말고 복구
                       (evidence 4개로 절단 = v1에서 HOLD한 R4)
                       → 관측된 지배적 차단 사유에 직접 대응한다
                       → LLM 재생성이 필요 없다

(c) 둘 다               독립변수가 2개가 된다 — 이번 설계 원칙 위반
```

**(b)는 이번 pilot과 같은 등급으로 지금 검증 가능하다.** `too_many_evidence`
거부는 결정적 변환(evidence 상위 4개로 절단, span 유지)이라 **생성 없이** 그
사건들이 unmatched GT와 매칭되는지 계산할 수 있다. 새 라벨 0, GPU 0, 반나절.

즉 fresh 영상을 구하기 전에 한 단계가 더 남았다.

```
STEP 0    trigger 존재 여부                      완료 — GO / T2@0.7
STEP 0.5  거부 후보 구제의 도달량 (제안)          미실행 — 사용자 결정 필요
STEP 1    fresh 영상 · rights · annotation       STEP 0.5 이후
```

---

## 6. 이 pilot이 덮지 못한 실패 모드

```
softyeon_ceramics    unmatched GT 6건 (두 번째 최대 기여자)
                     청크 커버리지 1.0 · 1.0 · 1.0 · 0.81
                     → T2·T4가 **구조적으로 발화하지 않는다**
```

원인은 UNDER_GENERATION_DOMINANT다 — 사건 6개가 거대한 span으로 타임라인을 전부
덮어 짧은 GT 12건을 삼켰다. **커버리지 기반 trigger는 이 모드에 원리적으로 눈이
멀었다.** 커버리지가 1.0이기 때문이다.

이 모드를 잡는 것은 T3(밀도)뿐인데 T3는 burden 22~34/41로 selective가 아니다.

```
그래서 T2@0.7의 reachable 상한 10/22는
  "짧은 사건이 삼켜진 모드"를 대부분 제외한 값이다
```

fresh 단계로 가더라도 이 한계는 그대로 간다. 보고서에 그렇게 적는다.

---

## 7. M8-v2 gate 수정 (GO일 때만 유효, 재확인)

```
Gate G 삭제       S1 = B0 + rescue이면 Hungarian 최적값은 열 추가에 단조 비감소.
                  alignment(S1) >= alignment(B0)는 항등적으로 참 — gate가 아니다
Gate C3 상대화    C3_max(S1) <= 1.15 x C3_max(B0)
                  additive라 C3는 개선될 수 없다 — regression-cost gate다
```

---

## 8. 경계

```
M8-v1 acceptance FAIL        불변
M8-v2                        아직 시작하지 않음
fresh N                      정하지 않음 (발화율 보고 역산)
새 라벨 · fresh panel         없음
M9 · official test           열지 않음
push                         하지 않음
```

이 문서의 수치는 성능 증거가 아니다. outcome-informed 설계이며, 선택된 trigger는
fresh data에서 동결 후 평가해야 의미를 갖는다.

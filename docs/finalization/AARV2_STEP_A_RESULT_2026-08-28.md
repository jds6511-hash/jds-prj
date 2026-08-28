# AAR-v2 STEP A 결과 — Boundary Detectability Probe (2026-08-28)

```
판정   GO
       A  pooled Δ = +0.3000   (필요 ≥ +0.15)          충족
       B  embedding ≥ uniform  7편 / 적격 7편 (필요 ≥5)  충족
       C  embedding < uniform  0편        (허용 ≤2)      충족
```

사전등록 `AARV2_STEP_A_PREREG_2026-08-28.md`를 실행 전에 동결했다. primary·K·τ·
matcher·GO 기준을 결과를 보고 고치지 않았다.

---

## A. Provenance

```
source_commit   2a2ea54 시점 작업트리
prereg          docs/finalization/AARV2_STEP_A_PREREG_2026-08-28.md
panel           M8-v1 consumed development panel 8편
GT events       68
GT boundaries   60   (적격 7편. m8c2_3I7oGwk6EaQ는 GT 1건 → 경계 0 → 제외)
new_labels 0 · LLM_calls 0 · generation 0 · GPU 0 · new_embeddings 0
```

preflight: 구간 수 = emb_sub 행 수 = emb_cap 행 수, 차원 1024, 타임스탬프 단조 —
8/8 통과. 불일치 시 중단하도록 fail-closed로 짰다.

---

## B. 사전등록된 primary

```
primary_score    mean(percentile_norm(d_sub), percentile_norm(d_cap))
normalization    영상 내 채널별 percentile rank (동점 평균) · 하이퍼파라미터 없음
subtitle 무효     transition 양쪽 중 하나라도 공백이면 d_sub invalid → caption 단독
K_rule           max(1, round(duration_sec / 60))
tolerance        ±10초
matching         1:1 Hungarian · 최대 cardinality 우선 · 그 안에서 총 거리 최소
uniform_baseline duration × i / (K+1),  i = 1..K   (시작·끝 제외, snap 없음)
GO_threshold     Δ ≥ +0.15 · better ≥ 5 · worse ≤ 2
```

---

## C. Pooled 결과

```
embedding   33 / 60 = 0.5500
uniform     15 / 60 = 0.2500
delta                 +0.3000
```

---

## D. 편별

```
video                    dur    K  GTb  emb    rec  uni    rec        Δ
baekmansonghee_jirisan   915   15    6    4  0.667    1  0.167   +0.500
softyeon_ceramics        960   16   11    6  0.545    4  0.364   +0.182
jissi_farm              1055   18   10    7  0.700    3  0.300   +0.400
kbs_banff               1580   26    9    2  0.222    1  0.111   +0.111
wonyi_gyeongju          1725   29    9    4  0.444    4  0.444   +0.000
wonyi_geoje             1635   27    7    5  0.714    1  0.143   +0.571
m8c2_cIxG7OHYMPU        1640   27    8    5  0.625    1  0.125   +0.500
m8c2_3I7oGwk6EaQ         865   14    0    —          —           제외
```

7편 전부 uniform 이상. 열세 0편. `wonyi_gyeongju`는 동률(Δ 0.000)이다.

---

## E. Secondary 진단 — 판정에 쓰지 않음

```
채널별 hit 합계 (적격 7편 · GT 경계 60)
  primary (sub+cap)   33
  caption-only        32
  subtitle-only       20
```

```
편별 caption-only    4 · 6 · 8 · 3 · 3 · 4 · 4
편별 subtitle-only   2 · 4 · 2 · 4 · 1 · 3 · 3
무효 subtitle transition   52 · 174 · 94 · 104 · 22 · 19 · 89
```

**신호는 대부분 caption에서 온다.** primary(33)와 caption-only(32)의 차이가 1이다.
`jissi_farm`은 caption-only(8)가 primary(7)보다 높다. 이 관찰은 **STEP A 판정을
바꾸지 않으며**, 향후 아키텍처 설계 참고용이다.

`softyeon_ceramics`는 무효 subtitle transition이 174개로 많다 — 무발화 구간이
많은 영상에서는 사실상 caption 단독으로 동작한다.

### E-1. tolerance 민감도 (판정 미사용)

```
±5초    29 / 60 = 0.483
±10초   33 / 60 = 0.550      ← 판정에 쓴 값
±15초   34 / 60 = 0.567
```

τ를 절반으로 줄여도 0.48이다. **신호가 tolerance 폭에 크게 기대고 있지 않다.**

---

## F. Duration 진단 — 판정 미사용

경계 양쪽 사건 중 **짧은 쪽** 길이로 분류했다(사전등록 §12).

```
short   ≤40초      14 / 25 = 0.560
medium  45~180초   14 / 23 = 0.609
long    >180초      1 /  3 = 0.333
unknown              4 /  9 = 0.444
```

**짧은 사건에 인접한 경계에서 신호가 사라지지 않는다.** M8-v1 실패의 중심이
짧은 사건 누락(미매칭 GT 22건 중 18건이 짧은 사건)이었으므로 이 방향은 유리하다.
다만 판정 기준이 아니고 표본이 작다(short 25건).

---

## G. Gate

```
A  Δ ≥ +0.15                     +0.3000   PASS
B  embedding ≥ uniform ≥ 5편      7 / 7     PASS
C  embedding < uniform ≤ 2편      0         PASS

STEP A   GO
```

---

## H. 해석

이 probe가 지지하는 것은 하나다 — **기존 subtitle/caption embedding의 국소 변화
신호가 균등 시간 분할보다 GT 사건 경계 위치에 대해 실용적으로 더 유용한 정보를
담고 있었다.** pooled recall이 0.55 대 0.25이고, 적격 7편 전부에서 열세가 없었으며,
tolerance를 ±5초로 좁혀도 0.48을 유지했다. 짧은 사건에 인접한 경계에서도 신호가
남아 있었다(0.56). 지지하지 않는 것은 그 밖의 전부다 — AAR-v2 성공, event proposal
성공, hierarchy 성공, micro/meso 수준의 정확성, 보고서 품질 개선, M8-v1 실패 해소,
fresh 일반화, performance confirmation 어느 것도 이 결과로 주장할 수 없다.
이것은 **아키텍처를 시작할 근거이지 아키텍처가 작동한다는 증거가 아니다.**

### H-1. 결과를 약하게 읽어야 하는 이유 세 가지 (사전등록 지표 아님)

**① recall만 쟀다. 정밀도는 낮다.**

```
예측 총 158개 · GT 경계 60개 · 적중 33개
예측당 적중률 0.209
```

K가 GT 경계 수의 2.6배다. 사전등록이 recall만 지표로 정했기 때문에 이렇게 나온
것이고, 이 숫자를 판정에 넣지 않는다. 그러나 **"경계를 정확히 찾는다"로 읽으면 안
된다** — "경계 근처에 신호가 있다"까지다. 정밀도는 STEP B의 문제다.

**② uniform baseline이 우연 수준보다 다소 낮게 나왔다.**

```
균등 간격 ≈ duration / (K+1) ≈ 58초 · 2τ = 20초
경계 하나가 격자점 ±10초에 들어갈 소박한 기대치 ≈ 20 / 58 ≈ 0.345
관측 uniform 0.250
```

더 엄격한 비교자(0.345)를 쓰면 Δ = +0.205이고 여전히 임계 +0.15를 넘는다.
**판정은 이 대체 비교자에서도 유지된다.** 이 계산은 사전등록에 없으므로 판정
근거가 아니라 강건성 관찰로만 적는다.

**③ 가장 필요한 영상에서 가장 약했다.**

```
kbs_banff   boundary recall 0.222 (최저)
            M8-v1 미매칭 GT 8건으로 최대 기여자
            failure mode: SPAN_ALIGNMENT_DOMINANT · REJECTION_HEAVY
```

boundary 신호가 **M8이 가장 크게 실패한 영상에서 가장 약하다.** GO가 그 영상을
고칠 수 있다는 뜻이 아니다.

---

## I. Boundaries

```
M8-v1 verdict changed                  NO
ROUND 3                                NO
M9                                     NO
official test                          NO
fresh data                             NO
new labels                             NO
LLM                                    NO
GPU                                    NO
new embeddings                         NO
AAR-v2 full architecture implemented   NO
push                                   NO
```

STEP A에서 평가하지 않은 것: C1 · C3 · event proposal · hierarchy · merge ·
LLM 사건 서술 · evidence attachment · report assembly · report synthesis ·
최종 보고서 양식(개요/주요 사건/특징/결론).

동결 산출물은 수정하지 않았다. STEP A는 새 artifact로만 기록했다.

---

## J. Tests / git

```
tests       tests/test_aarv2_step_a.py 41건 (지침 §22 12항목 + 경계 guard)
전체        2,340 passed · 1 skipped · exit 0
push        NO
```

---

## K. 다음

```
STEP A GO — 그러나 full AAR-v2를 구현하지 않는다
```

다음은 별도 사전등록이다.

```
STEP B   boundary → event proposal / granularity feasibility
         특히 §H-1 ①의 정밀도 문제와 ③의 kbs_banff 취약성을 정면으로 다뤄야 한다
```

STEP B 통과 전에는 LLM report generation · hierarchy 전체 구현 · final report
synthesis를 하지 않는다.

**일정 충돌은 미해결이다.** 최종 보고서(M1~M7 + M8 실패·원인) · 산출물 점검 ·
시연 · 발표가 아직 착수되지 않았고, STEP B와 그 이후 작업은 그것과 직접 경합한다.
우선순위는 별도 결정 사항이다.

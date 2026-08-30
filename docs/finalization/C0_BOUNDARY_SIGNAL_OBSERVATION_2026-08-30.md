# C0 — caption-text embedding 변화 신호 관찰 (2026-08-30)

```
성격   관찰 전용 descriptive observation
아님   threshold 결정 · optimal cutoff · minimum gap · smoothing tuning
       provider 채택 · 점수 계산 · GT 대조
규격   V2_1_ARCHITECTURE_SPEC_2026-08-30.md §5·§25
실행   LLM 미호출 · GPU 미사용 · 저장된 emb_cap.npy(KURE-v1)만 읽음
```

질문 하나.

> KURE caption-text embedding distance의 peak가 사람이 보기에 의미 있는
> 화면·내용 변화와 어느 정도 대응하는가.

---

## 1. 관찰 창

```
wonyi_geoje       chunk3   seg#110~169    LLM 경계 4종이 있는 구간
wonyi_geoje       chunk5   seg#220~279    Qwen이 붕괴했던 구간
m8c2_3I7oGwk6EaQ  seg#0~59               caption-dominant 대조
```

---

## 2. 신호 분포 — 좁다

```
창                     mean     p50     p90     max    국소peak
geoje chunk3          0.3137  0.2982  0.4742  0.6798     10
geoje chunk5          0.2815  0.2830  0.3859  0.5922     12
3I7   seg0~59         0.3053  0.3242  0.4752  0.5591     13
```

**peak가 중앙값의 1.5~2배 수준이다.** 배경과 확실히 분리되는 구조가 아니다.
절대 임계를 쓰지 않고 백분위로만 표현한 이유가 여기 있다.

---

## 3. LLM 경계는 peak 위에 있지 않다

```
창             arm                     창 안   거리 백분위 중앙   국소peak 위
chunk3        qwen_full                  5        0.745        1  (0.20)
              qwen_caption_only          2        0.695        0  (0.00)
              kanana_full                6        0.627        0  (0.00)
              kanana_caption_only       57        0.540        9  (0.16)
chunk5        qwen_full                 42        0.514        9  (0.21)
              qwen_caption_only         10        0.440        0  (0.00)
              kanana_full                5        0.325        1  (0.20)
              kanana_caption_only       40        0.506        7  (0.18)
3I7 0~59      bcs_qwen_caption_only      7        0.698        1  (0.14)
```

**peak 적중률이 어느 arm에서도 0.21을 넘지 않는다.** 백분위 중앙도 0.33~0.75로
흩어져 있다.

두 방식이 서로 다른 곳을 자른다. 이건 어느 쪽이 옳다는 뜻이 아니라
**둘 중 하나를 다른 하나로 검증할 수 없다**는 뜻이다.

---

## 4. peak의 성격 — 상위 10개씩 전수 분류

```
상위 peak 30건 (창당 10)
  지시문 에코        1
  캡션 오염          1   (is_corrupted_caption 적중)
  검은 화면 전환      2
  외형 어휘 차이만    0
  결함 표지 없음     26
```

### 4-1. 그러나 **가장 큰 peak가 캡션 결함이다**

```
geoje chunk3 최대 peak   seg#117  d=0.6798  pct=0.997
  이전  두 여성이 푸른색 배경 앞에서 앉아 있습니다. …
  현재  네, 알겠습니다. 다음은 주어진 요청에 따라 한 문장의 한국어로 객관적인 묘사입니다.
```

VLM이 **지시문을 그대로 되뱉은 출력**이다. 장면 변화가 아니다.

```
3I7 상위 5 안에
  seg#44  d=0.531  검은 화면 → '만복대' 바위
  seg#10  d=0.496  손 클로즈업 → 검은 화면
  seg#1   d=0.478  夕阳西下，天空被染成了温暖的橙红色…   ← 캡션 전체가 중국어
```

`max`를 쓰는 규칙은 **캡션 결함을 최우선으로 고르게 된다.** 절대 임계든 상위-K든
캡션 QC가 선행 조건이다.

### 4-2. 내가 우려했던 외형 요동은 상위 peak에 없다

geoje 255~265에서 옷 색이 분홍→파랑→검정→초록으로 흔들리는 것을 보고 그것이
peak를 만들 것이라고 예상했다. **상위 30건 중 0건이다.**

앞뒤 캡션의 어휘 차이가 외형 어휘에만 있는 경우는 상위 peak에 나타나지 않았다.
외형 요동은 거리를 **올리는 게 아니라 바닥을 높이는 쪽**으로 보인다(창 전체 mean이
0.28~0.31로 낮지 않다).

### 4-3. 실제 전환으로 읽히는 peak도 있다

```
geoje chunk5 seg#259  d=0.592   해변 대화 → 가스레인지에 소스 넣기
geoje chunk5 seg#237  d=0.489   창가 실내 → 상점가 바닥에 앉음
geoje chunk5 seg#221  d=0.522   소년 클로즈업 → 두 여성 해변
3I7        seg#44    d=0.531   검은 화면 → 만복대 바위 (컷 전환)
```

---

## 5. 결론

```
PROMISING_SIGNAL     아니다
MIXED_SIGNAL         ← 이것
UNSUITABLE_SIGNAL    아니다
```

근거.

```
+  상위 peak의 다수(26/30)가 캡션 결함 표지 없이 실제 내용 전환으로 읽힌다
+  외형 어휘 요동이 peak를 만든다는 우려는 상위에서 지지되지 않았다
-  분포가 좁아 peak가 배경과 뚜렷이 분리되지 않는다 (p90/median ≈ 1.4~1.6)
-  창별 최대 peak에 캡션 결함이 섞인다 — max·top-K 규칙에 직접 타격
-  LLM 경계와의 일치가 매우 낮다 (peak 적중 ≤ 0.21)
```

---

## 6. 다음 단계에 대한 함의 — 규칙을 정하지 않는다

```
전제조건  peak 기반 규칙을 쓰려면 **캡션 결함 필터가 선행**해야 한다
          (지시문 에코 · 외국어 캡션 · 검은 화면은 결정적으로 잡을 수 있다)
미해결    분포가 좁아 "몇 개를 고를 것인가"가 다시 임계 문제로 돌아온다
불가      LLM 경계를 정답으로 삼아 이 신호를 검증할 수 없다 (§3)
```

따라서 v2.1의 결정은 유지된다.

```
fixed_window_v1              default 유지
caption_text_change_point    CANDIDATE 유지 — 승격하지 않는다
```

**임계·최소 간격·smoothing을 정하지 않았다.** 이 문서로 provider를 채택하지 않는다.

---

## 7. STEP A와의 관계

`AARV2_STEP_A_RESULT_2026-08-28.md`는 다른 질문을 쟀다.

```
STEP A   GT 경계 대비 recall (K = duration/60 예산, ±10초 허용)  embedding 0.55 vs uniform 0.25
C0       peak가 의미 있는 변화에 대응하는가 (GT 없음)
```

**모순이 아니다.** STEP A는 예산을 정해 준 상태에서 균등 분할보다 낫다는 것을 보였고,
C0는 예산 없이 peak만 보면 캡션 QC가 선행 조건이라는 것을 보인다.

---

## 8. 경계

```
threshold 결정   NO    provider 채택   NO    프롬프트·모델   무변경
GT 대조         NO    새 라벨         NO    BCS·v2.1 수정   NO
M9 · test       NO    push           NO
```

산출물: `runs/c0/c0_boundary_signal.json`
(창별 분포 · 국소 peak 상위 10 · 캡션 원문 · LLM 경계 4종 대조)

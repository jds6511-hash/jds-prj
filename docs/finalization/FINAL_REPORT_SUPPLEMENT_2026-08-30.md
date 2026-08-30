# 최종 보고서 보충 절 — 2026-08-29 ~ 30 (companion addendum)

```
성격   FINAL_REPORT_BASELINE_2026-08-28.md 의 companion addendum
근거   baseline 자신의 revision_rule
       "STEP B 결과는 addendum 또는 revision으로 별도 추가한다.
        이 baseline의 본문을 다시 쓰지 않는다."
```

**동결본은 한 글자도 고치지 않았다.** 이 문서는 08-28 이후의 다섯 트랙과 v2.1
설계를 baseline과 같은 규율로 기록한다.

```
새 실험         5건 (전부 사전등록 또는 관찰 전용)
새 지표         없음
공식 지표 재계산  없음
frozen artifact 수정  없음
official test · M9    미접촉
```

---

## S1. 무엇이 추가됐나

```
S3  경계 caption-only ablation (geoje)          within-video causal diagnostic
S4  Boundary-Content Split prototype v0         제품 prototype · HWPX 2편
S5  모델 대조 진단 (Qwen vs Kanana)              NON-ADOPTIVE diagnostic
S6  C0 관찰 (caption-text 변화 신호)             관찰 전용
S7  v2.1 아키텍처 · 계획 · 수용 기준              설계 문서 · 구현 미착수
```

baseline이 다룬 범위(AAR-v2 STEP A까지)와 **모순되는 수치는 없다.** baseline에는
caption-only 일반화 주장이 없다.

---

## S2. 이 보충 절이 바꾸지 않는 것

```
공식 M8            evaluation COMPLETE · acceptance FAIL   불변
M9                 HOLD · 미실행
official test 39   UNOPENED · 재열람·재계산 없음
M8 C2 라벨          RETIRED_FROM_FUTURE_EVALUATION
검색 파이프라인 성능  변화 없음 (M1~M7 미접촉)
```

**후속 트랙은 전부 downstream AAR 계층이다.** 검색 성능을 개선하지도 악화시키지도
않았다.

---

## S3. 경계 caption-only ablation — 같은 영상, 입력 채널 하나만 제거

사전등록을 **실행 전에** 커밋했다(`ad47dd3`). 모델·청킹·규칙·파서·decoding을
동결하고 `_fmt_seg`의 자막 필드만 제거했다.

```
                     full input    caption-only
Atomic count             66             32
1-segment Atomic         25              1
≤2-segment Atomic        40              2
median 길이(구간)          2              7
```

### 그러나 기전이 예상과 달랐다

효과가 고르지 않았다. **거의 전부 청크 하나였다.**

```
chunk5(220~279) 안     42 → 12
chunk5 제외             24 → 20
```

full-input chunk5의 원본 출력.

```json
["220","224","226",…,"254","255","256",…,"278","279"]
```

간격 4 → 2를 16회 → **1을 25회**, 허용 범위 끝 번호에서 정지. 내용 판단이 아니라
**번호 열거**다. chunk3도 `[110,120,130,140,150]` — 정확히 간격 10의 등차수열이었다.

### 위치는 채널을 바꾸면 크게 달라진다

```
chunk5 제외   full 24 · caption-only 20 · 공통 위치 8
```

개수는 비슷한데 공통 위치가 8개뿐이다. **경계 선택이 내용에 단단히 고정돼 있지 않다.**

---

## S4. Boundary-Content Split prototype v0

원칙 하나만 구현했다.

> **STT는 사건을 쪼갤 권한이 없고, 사건의 의미를 더할 권한만 갖는다.**

```
                         3I7            geoje
구간                      173             327
Episode                    18              32
1구간 Episode                0               1
≤2구간 Episode               2               2
prototype_status           OK              OK
커버리지(겹침0·구멍0)      OK              OK
```

**두 영상 모두 유효 문서가 나왔다.** 계층 프로토타입 v1~v4는 전부 무효였다.

### 오염 전파 0건

```
                        구 계층        BCS v0
3I7  오염 전파            2건            0건
       E07 "마포구청 인터넷 방송국 홈페이지를 방문한 후"
       E15 "다음 영상에서 만나요라는 메시지를 보여주며"
     외국문자 생성        1건            0건
```

3I7의 오염 STT 29건이 결정적 sanitation에서 걸러져 서술 입력에 오르지 않았다.
임계(반복 ≥8)는 패널 18편 전수 실측으로 정했다 — 실제 발화 최다 반복 5회,
오염 9·20·22회.

### STT는 구조를 깨지 않고 의미만 더했다

```
dialogue_note      3I7  0 / 18        geoje  14 / 32
근거 미달 폐기      3I7  0            geoje   2
```

근거 검증이 실제로 작동했다.

```
EP15  cite_not_usable_stt   STT 없는 구간 [210~216]을 근거로 댐 → 폐기
EP20  no_stt_cite           근거 없이 대화 주장 → 폐기
```

### 산출물

```
runs/bcs/bcs_v0_reparsed/wonyi_geoje_bcs_aar.hwpx        45,339 bytes · Episode 32
runs/bcs/bcs_v0_reparsed/m8c2_3I7oGwk6EaQ_bcs_aar.hwpx   36,981 bytes · Episode 18
```

11파트 OWPML 패키지로 생성됐고 다섯 절이 모두 들어 있음을 본문 추출로 확인했다.
**M9 게이트 산출물이 아니다** — 파일명(`_bcs_aar.hwpx`)과 본문에서 분리했다.

### 남은 문제 (고치지 않았다)

```
dialogue_note가 요약이 아니라 발화 나열       14건 중 절반 이상
긴 Episode에서 한 문장 제약이 절 나열로 흡수   3I7 EP03 154자
3I7 요약은 여전히 화면 묘사                   유효 발화 0 조건에서 예상된 결과
문체 혼재                                    ~한다 / ~합니다 / ~이다
```

### 내 파서 결함 2건 — 첫 실행을 왜곡했다

```
① 모델은 stt_cites를 ["seg#55","seg#56"]로 냈는데 파서가 순수 숫자만 받았다
   → dialogue_note 14건이 전부 no_stt_cite로 오탐 폐기 (겉보기 2/32 · 실제 14/32)
② 깨진 JSON에서 맨문장 폴백이 JSON 원문을 요약으로 채택
```

저장된 raw를 고친 파서로 **재파싱**해 정정했다 — LLM 미호출 · GPU 미사용 · 구조 불변.
첫 실행 원본은 지우지 않았다.

---

## S5. 모델 대조 진단 — 판정 Case 4

사전등록(`8975c74`)과 개정(`ad75b5d`) 모두 **실행 전·결과 미열람 상태**에서 커밋했다.
비교 모델은 EXAONE-3.5에서 Kanana-1.5-8B로 교체했다(사유 S5-1).

```
arm                        in_tok  out_tok   bnd  run1  arith@step  parse
Qwen   full   chunk3         8063       34     5     1      5@10     OK
Kanana full   chunk3         7045       23     6     1      4@10     OK
Qwen   cap    chunk3         6397       19     2     1      2@59     OK
Kanana cap    chunk3         5525      176    57    52      3@2      OK  ←
Qwen   full   chunk5         8196      214    42    26     16@2      OK  ←
Kanana full   chunk5         7081       23     5     1      4@10     OK
Qwen   cap    chunk5         6421       50    10     1      4@5      OK
Kanana cap    chunk5         5493      125    40    23      2@2      OK  ←
```

**붕괴가 반대 조건에서 일어난다.**

```
Qwen     full input에서 붕괴        chunk5 연속 정수 26개
Kanana   caption-only에서 붕괴      chunk3 연속 52개 (허용 60구간 중 57개 열거)
```

```
정상 arm에서도 간격 10 등차수열
위치 Jaccard가 어느 쌍에서도 0.2 미만
Kanana가 토큰 12~14% 적어도 붕괴 — 단순 context-length 설명은 약하다
네 arm 모두 PARSE_OK — 파서 문제가 아니다
```

### 결론 — 한 문장

> Boundary selection failure는 model-specific한 방향성을 보였지만, 서로 다른 두
> 한국어 instruction model 모두 입력 조건에 따라 불안정한 위치 선택 또는 열거형
> 출력을 보여, **free-form LLM boundary selection 자체의 안정성 문제**가 더
> 일반적인 설계 위험으로 관찰되었다.

즉 **model × input interaction + task formulation problem**이다.

### S5-1. EXAONE-3.5는 실행 불가로 종결

```
Status              IMPLEMENTATION_BLOCKED
Scientific result   NONE
```

동결 런타임 `transformers 5.14.1`이 EXAONE-3.5의 vendored forward 경로를 네이티브로
지원하지 않는다. 1차 불일치(`create_causal_mask` 인자 개명)는 순수 별칭이라 처리했으나,
2차 불일치(`cache_position` 인자 제거)는 **forward semantics를 추론해 고치는 일**이라
중단했다.

이 진단의 질문이 "모델이 이상 출력을 내는가"이므로, 손으로 적응시킨 forward 경로의
출력은 마스크 결함이 degeneracy를 만들거나 지우는 경우와 구분되지 않는다.

교체 사유는 arm 간 런타임 동일성이다. Kanana는 네이티브 지원·이미 캐시돼 있어
**패치 0**으로 돌았다(`compat_shims []` · `trust_remote_code False`).

### S5-2. 이 결과가 BCS 해석을 좁힌다

```
철회   "caption-only boundary가 안정적이다"
```

> **BCS v0는 Qwen2.5-7B-Instruct와 해당 두 영상 조건에서 유효 문서를 생성한
> frozen product prototype이다. 후속 cross-model diagnostic에서는 caption-only
> boundary selection의 안정성이 다른 모델로 일반화되지 않았으므로, 해당 boundary
> mechanism을 일반적인 사건 검출 방법으로 주장하지 않는다.**

ablation 실측 자체는 유효하다. 바뀌는 것은 **일반화 범위**다.

---

## S6. C0 관찰 — caption-text 변화 신호

LLM 미호출 · GPU 미사용. 저장된 `emb_cap.npy`(KURE-v1)만 읽었다. 임계·최소 간격·
smoothing을 정하지 않았고 provider를 채택하지 않았다.

```
창                 mean     p50     p90     max    국소peak
geoje chunk3      0.3137  0.2982  0.4742  0.6798     10
geoje chunk5      0.2815  0.2830  0.3859  0.5922     12
3I7   seg0~59     0.3053  0.3242  0.4752  0.5591     13
```

```
결론   MIXED_SIGNAL
+  상위 peak 30건 중 26건이 결함 표지 없이 실제 전환으로 읽힌다
+  외형 어휘 요동이 peak를 만든다는 우려는 상위에서 지지되지 않았다 (0/30)
-  분포가 좁아 peak가 배경과 뚜렷이 분리되지 않는다 (p90/median ≈ 1.4~1.6)
-  창별 최대 peak에 캡션 결함이 섞인다 — max·top-K 규칙에 직접 타격
-  LLM 경계와의 peak 적중이 최대 0.214 (qwen_full chunk5 · 9/42)
```

geoje chunk3의 최대 peak(`d=0.6798` · `pct=0.997`)는 VLM이 지시문을 되뱉은 출력이었다.

```
현재  "네, 알겠습니다. 다음은 주어진 요청에 따라 한 문장의 한국어로 객관적인 묘사입니다."
```

**peak 기반 규칙을 쓰려면 캡션 QC가 선행 조건이다.**

### STEP A와의 관계

```
STEP A   GT 경계 대비 recall (K = duration/60 예산 · ±10초)   embedding 0.55 vs uniform 0.25
C0       peak가 의미 있는 변화에 대응하는가 (GT 없음)
```

**모순이 아니다.** 다른 질문을 쟀다.

---

## S7. v2.1 설계 — 이 보충 절 작성 시점에는 구현하지 않았다

작성 시점 상태.

```
v2.1 architecture specification   FROZEN
v2.1 implementation plan          DOCUMENTED
v2.1 acceptance/test matrix       DOCUMENTED
v2.1 Gate A ticket breakdown      READY (11 티켓)
v2.1 implementation               DEFERRED
implementation authorization      NOT GRANTED
```

**이후 같은 날 해제됐다.** 사용자 명시 승인으로 구현이 시작됐고 A-01이 커밋됐다
(`7f5d0f9`). 위 블록은 지우지 않고 작성 시점 기록으로 남긴다.

```
implementation authorization      GRANTED 2026-08-30
v2.1 implementation               IN PROGRESS   Gate A · A-01 COMPLETE
```

사건 기록: `V2_1_IMPLEMENTATION_AUTHORIZATION_2026-08-30.md`.
**이 승인은 아래 S8의 금지 목록을 하나도 바꾸지 않는다** — Gate A는 LLM·GPU를
쓰지 않는 로컬 결정적 코드다.

중심 원칙 둘.

> 생성 모델은 "무슨 일이 있었는지"를 해석하지만, "어디서 사건을 자를지"의 정본을
> 만들지 않는다.

> 정본 시간구조와 사람이 읽는 보고서 구조는 같은 것이 아니다.
> 정본은 겹침 없는 완전 partition, 보고서는 중첩 가능한 의미 단위.

```
canonical default provider   fixed_window_v1
caption_text_change_point    CANDIDATE — 미채택
LLM_FREE_BOUNDARY            canonical path에서 금지
```

`fixed_window`를 default로 두는 근거는 S5다 — 두 모델의 **정상 arm도 간격 10의
등차수열**을 냈다. LLM이 붕괴하지 않을 때 내놓는 것도 사실상 균등 분할이었다.

착수는 **finalization deliverable 완료 후** 별도 승인으로 한다(ADDENDUM OPEN-8).

---

## S8. 이 보충 절에서 하지 않는 말

```
M8 실패가 해결됐다                      말하지 않는다
BCS가 M8을 대체한다                     말하지 않는다 — 공식 판정 불변
caption-only가 일반적으로 안전하다        말하지 않는다 — S5-2에서 철회
change-point가 검증됐다                 말하지 않는다 — MIXED_SIGNAL · 미채택
Kanana가 Qwen보다 낫다/나쁘다            말하지 않는다 — 채점하지 않았다
v2.1이 구현됐다                         말하지 않는다 — 설계 문서만
검색 성능이 개선됐다                     말하지 않는다 — M1~M7 미접촉
사람 작성 보고서를 기준으로 평가했다        말하지 않는다 — 형식 참조이며 GT 아님
```

---

## S9. 표본 한계

```
ablation        영상 1편 · 청크 6 · 1회 실행
BCS v0          영상 2편 · 각 1회
모델 진단        영상 1편 · 청크 2 · 모델 2 · 각 조건 1회
C0              창 3개 · 상위 peak 30건 수작업 분류
```

greedy(`do_sample=False`)라 통제된 조건에서 결정적이지만 **반복 실행으로 확인하지
않았다.** 어느 결과도 모델·영상 일반화를 주장하지 않는다.

---

## S10. 산출물 경로

```
runs/m8_hier/m8_hier_boundary_ablation/        ablation raw · 경계 · 대조
runs/bcs/bcs_v0/                               첫 실행 원본 (파서 결함 포함 · 보존)
runs/bcs/bcs_v0_reparsed/                      정정본 · MD · HWPX 2편
runs/model_diag/geoje_boundary_degeneracy.json raw 8건 · 토큰 수 · 안정성
runs/c0/c0_boundary_signal.json                분포 · peak · LLM 경계 4종 대조
```

문서 지도는 `RESEARCH_TRACK_STATUS_2026-08-30.md` §7.

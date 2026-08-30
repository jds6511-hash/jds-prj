# BCS core FREEZE + 정본/표현 분리 (2026-08-29)

```
결정   BCS v0 core를 제품형 AAR의 핵심 경로로 채택하고 동결한다
상태   FREEZE CANDIDATE
근거   BCS_PROTOTYPE_RESULT_2026-08-29.md · M8_HIER_BOUNDARY_ABLATION_RESULT_2026-08-29.md
```

공식 M8 판정(FAIL)은 그대로다. 이 경로는 그것을 바꾸지 않는다.

---

## 1. 동결 대상 — 이 네 층을 흔들지 않는다

```
① STT sanitation        결정적 판정만 (임계 8 · URL/방송국 · 크레딧 · 외국문자)
② caption-only 경계 pass  ablation이 지지한 프롬프트 그대로
③ Episode 분할           코드 · 겹침 0 · 구멍 0 · 전 구간 1회
④ 근거·인용 검증          dialogue_note는 usable STT 인용을 통과해야 남는다
```

**`dialogue_note` 가독성 때문에 이 넷을 다시 흔들지 않는다.** 현재의 발화 나열은
가독성 문제이지 근거 무결성 문제가 아니다 — 모두 실제 STT에 기반해 있고 인용이
검증됐다. "의미를 추상적으로 요약하라"로 프롬프트를 바꾸면 `결정했다`·`의도했다`를
모델이 과잉 보충할 위험이 있다.

동시에 확보된 것.

```
시간축 overlap/gap 없음        달성
5초 조각화 억제                달성   geoje 1구간 25 → 1
STT가 boundary를 쪼개지 않음    달성   경계 pass 6/6 degeneracy 없음
유효 대화는 의미 보강에 사용     달성   3I7 0 · geoje 14
오염 STT의 claim 승격 차단      달성   양쪽 0건
근거 없는 대화 claim 제거       달성   실제 2건 폐기
두 조건 모두 유효 문서 생성      달성   v1~v4는 전부 무효였다
사람이 바로 읽는 문체           표현 계층에서 처리
```

---

## 2. 정본과 표현의 분리

```
segments.json
    ↓ 결정적 STT sanitation
    ↓ caption-only 경계 pass          (LLM)
    ↓ 결정적 Episode 분할
    ↓ caption + usable STT 내용 pass   (LLM)
    ↓ claim/source/citation 검증
BCS canonical JSON        ← 여기까지가 정본
    ↓ 결정적 렌더러
Markdown · HWPX           ← 표현물
```

```
정본   runs/bcs/bcs_v0_reparsed/<vid>.json
표현   src/bcs_present.py → scripts/bcs_hwpx.py
```

**표현 계층 규칙.**

```
금지   LLM 호출 · 생성 문장 수정 · 지표 재계산 · 정본 수정
허용   형식 변환 · 레이블 통일 · 서식
```

이 분리로 **제목 하나가 빠지거나 예쁜 문체 생성이 실패해도 문서 전체가 무효가
되지 않는다** — v3(title 12/16)·v4·softyeon이 그렇게 죽었다.

정본이 무효면 표현하지 않는다(`ViewError`). fallback 문서를 만들지 않는 원칙은 유지한다.

---

## 3. 문서 구조

```
영상 개요            대상 · 길이 · 구간 수 · 기록 수 · heuristic 고지 · M9 아님 고지
주요 흐름            EP 목록과 시각
구간별 기록          EP마다 주요 내용 / 대화 요지(있을 때) / 근거
특이사항 및 확인 불가  제외한 오염 발화 수 · 근거 미달로 버린 대화 주장 · 형식 이상
근거 및 생성 정보     정본 · commit · 모델 · revision · decoding · 규격 · 인용된 발화
```

```
문체    레이블에서만 통일한다. 생성 문장의 어미를 고쳐 쓰지 않는다 —
        고치는 순간 그것은 표현이 아니라 새 서술이다.
대화    3I7처럼 유효 발화가 없으면 `대화 요지` 절을 만들지 않는다.
부록    **검증을 통과한 대화의 근거만** 싣는다. 기각한 주장의 인용을 제시하지 않는다.
```

---

## 4. M9 산출물과 구분한다

`POST_M9_DELIVERABLE_SPEC_2026-08-27.md`의 산출물은 **M9 완료를 전제**하며 M9는
HOLD다. 혼동을 막기 위해 분리한다.

```
파일명   <vid>_bcs_aar.hwpx        (M9 산출물은 <vid>_aar_report.hwpx)
본문     "제품 prototype 산출물이며 M9 검증을 거친 최종 산출물이 아니다(M9는 미실행)"
```

---

## 5. 산출물 (실측)

```
runs/bcs/bcs_v0_reparsed/wonyi_geoje_bcs_aar.hwpx        45,339 bytes · Episode 32
runs/bcs/bcs_v0_reparsed/m8c2_3I7oGwk6EaQ_bcs_aar.hwpx   36,981 bytes · Episode 18
                         <vid>_bcs_aar.md                같은 내용의 Markdown
```

HWPX는 11파트 OWPML 패키지로 생성됐고 다섯 절이 모두 들어 있음을 본문 추출로 확인했다.
HWPX 생성은 한글 COM이 있는 로컬에서만 돈다(`pyhwpx` 1.7.2). Markdown은 어디서나 나온다.

---

## 6. 나중으로 미루는 것

```
dialogue_note 추상 요약        표현 전용 필드로만. 정본을 대체하지 않는다.
                              실패해도 검증된 dialogue_note를 그대로 표시한다.
긴 요약의 short_summary        표시 전용. 정본 summary를 대체하지 않는다.
경계 수 상한                   두지 않는다
embedding 결정적 경계 (C)      future work
Dual-stream 전면 (D)          하지 않는다
```

---

## 7. 경계

```
공식 M8/M9 변경  NO    test 접근  NO    새 GT·라벨  NO    push  NO
프롬프트 수정    NO    세 번째 영상 NO   core 재설계  NO
```

---

## 적용 범위 — 2026-08-30 좁혀졌다

cross-model diagnostic(`MODEL_DEGENERACY_DIAG_RESULT_2026-08-30.md`)에서 Kanana는
**caption-only 조건에서 붕괴**했다(chunk3 연속 52개 · 허용 60구간 중 57개 열거).
Qwen과 정반대 방향이다.

```
철회   "caption-only boundary가 안정적이다"라는 일반화
```

> **BCS v0는 Qwen2.5-7B-Instruct와 해당 두 영상 조건에서 유효 문서를 생성한
> frozen product prototype이다. 후속 cross-model diagnostic에서는 caption-only
> boundary selection의 안정성이 다른 모델로 일반화되지 않았으므로, 해당 boundary
> mechanism을 일반적인 사건 검출 방법으로 주장하지 않는다.**

ablation 실측 자체는 유효하다 — 같은 모델·같은 영상에서 채널만 뺐고 조각화가
사라졌다. 바뀌는 것은 일반화 범위이지 관측이 아니다.

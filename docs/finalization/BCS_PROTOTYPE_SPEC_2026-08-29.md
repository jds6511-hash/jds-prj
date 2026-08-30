# Boundary-Content Split prototype v0 — 규격 (2026-08-29)

```
성격   제품 설계 prototype
아님   공식 M8 · 성능 실험 · acceptance · 새 GT
근거   M8_HIER_BOUNDARY_ABLATION_RESULT_2026-08-29.md
```

**공식 M8과 이름을 섞지 않는다.** 공식 M8 판정(FAIL)은 그대로다.

---

## 1. 구현하는 원칙 — 딱 하나

> **STT는 사건을 쪼갤 권한이 없고, 사건의 의미를 더할 권한만 갖는다.**

ablation 실측(같은 영상, 입력 채널 하나만 제거).

```
Atomic       66 → 32        1구간   25 → 1        median 2 → 7
chunk5       42 → 12        연속 정수 열거 26개 → 없음
```

```
PASS 1  caption만 보고 Episode 경계 선택        LLM · 청크당 1회
PASS 2  span 구성 · 근거 앵커                   코드
PASS 3  Episode 내용 — caption + 사용가능 STT    LLM · Episode당 1회
PASS 4  렌더                                    코드
```

Atomic/Major 2계층을 버린다. **Episode 한 층**이다.

---

## 2. 하지 않는 것 (HOLD)

```
경계 수 상한            새 임의 임계를 만든다 — 두지 않는다
embedding 결정적 경계    future work (STEP A 신호 0.55 vs uniform 0.25)
Dual-stream 전면 구현    하지 않는다
key_actions 자유 리스트  v1 실패 모드가 돌아온다 — Episode당 서술 1개
새 GT · M8/M9 변경      금지
```

`degeneracy`는 **탐지만** 한다.

```
연속 정수 run ≥ 5   →   boundary_output_status = DEGENERATE
자동으로 경계를 자르거나 버리지 않는다
```

---

## 3. Episode 경계의 지위

> **제품 구조를 만들기 위한 heuristic segmentation이다. ground-truth event
> detection이 아니다.**

같은 영상에서 입력 채널만 바꿔도 공통 위치가 24개 중 8개였다(결과 §3). 렌더된
문서 머리말에도 이 문장을 넣는다.

---

## 4. STT sanitation — 결정적 판정만

`raw_stt`를 보존하고 `clean_stt`·`stt_status`를 덧붙인다. 내용을 보고 고르지 않는다.

```
CREDIT                  common.is_subtitle_credit (기존, 완전일치)
OVERLAY_OR_URL          홈페이지|https?://|www\.|\.com|\.co\.kr|방송국
REPEATED_CONTAMINATION  영상 전체 완전일치 출현 ≥ 8회
FOREIGN_SCRIPT          한자·가나 3자 이상
EMPTY / USABLE
```

### 임계 8의 근거 — 패널 18편 전수 실측

```
실제 발화의 최다 반복    5회   kbs_banff · e2e_interview (40자 이상 문장)
오염의 반복             9 / 20 / 22회   3I7 x2 · softyeon (12~17자)
wonyi_geoje 최다 반복    2회   ≥3배 0건
```

### `is_corrupted_caption`을 STT에 그대로 쓰지 않는다

그 함수의 반복 규칙은 **VLM 캡션 붕괴용**이다. dry-run에서 geoje 실제 발화 11건을
지웠다.

```
"나 잡았어!!! 나 잡았어!!! 나 잡았어!!!"
"넣어라, 넣어라 넣어라 언니 넣어라, 넣어라"
"리셋네 리셋네 원이님! 아이돌! 빨리 빨리 빨리!"
```

**오탐이 곧 발화 삭제다.** STT에서는 외국문자만 본다.

### 적용 결과 (실측)

```
m8c2_3I7oGwk6EaQ   EMPTY 140 · USABLE 4 · REPEATED 20 · OVERLAY_OR_URL 9
wonyi_geoje        EMPTY  12 · USABLE 315 · 제거 0
```

3I7은 33건 중 29건이 제거돼 **기능적으로 caption-dominant**가 된다.
남는 4건(`이 시각 세계였습니다.` x2 · `기상캐스터 배혜지` x2)은 오염이지만
**일반 규칙으로 못 잡는다** — 특정 문자열 blocklist는 내용 기반 선별이라 만들지 않는다.

**이 필터는 M8 산출 계층에만 있다.** 인덱스·`is_subtitle_credit`·캡션 QC를 바꾸지
않으므로 재색인 승인 사건이 아니다.

---

## 5. citation 검증 — 이 층에 이빨을 준다

모델이 `source: stt`라고 자기 신고하는 것으로는 부족하다. 코드가 확인한다.

```
dialogue_note가 있으면
  stt_cites 비어 있음            → 버림  no_stt_cite
  cite가 span 밖                 → 버림  cite_outside_span
  cite한 구간의 stt_status ≠ USABLE → 버림  cite_not_usable_stt
```

**버리는 것은 `dialogue_note`뿐이다.** `summary`는 caption만으로 성립하므로
STT 인용을 요구하지 않는다(3I7 같은 caption-dominant 사례).

---

## 6. 형식 실패 대책

v1·v3·v4·softyeon은 전부 **출력 형식**에서 죽었다. 그래서

```
필수 필드는 summary 하나        title 없음 · key_actions 없음
JSON이 아니어도 문장 하나를 받는다  표기 관용 — 구조는 코드가 갖는다
dialogue_note는 선택            없으면 없는 대로 유효
```

`summary`가 비면 문서가 무효고 **렌더를 거부한다**. fallback 문서를 만들지 않는다.

---

## 7. 성공 질문 (개수를 최적화하지 않는다)

```
구조   두 영상 모두에서 5초 조각화가 일어나지 않는가
오염   오염 STT가 서술에 오르지 않는가
의미   대화가 경계가 아니라 내용을 풍부하게 하는가 (geoje에서 dialogue_note)
사용   보고서가 5초 로그가 아니라 시간 흐름으로 읽히는가
```

기대.

```
3I7    구조는 굵게 유지 · dialogue_note 거의 없음 · 서술은 화면 기반으로 제한적
geoje  구조는 조각나지 않음 · 결정·계획이 dialogue_note로 들어옴
```

성립하면 이 트랙의 핵심 주장이 확인된다.

> 정보량이 달라도 시간 구조는 비교적 안정적이고, STT는 구조를 깨지 않으면서
> 의미만 더한다.

---

## 8. 경계

```
공식 M8/M9 변경  NO    test 접근   NO    새 GT·라벨   NO
경계 수 상한     NO    C 구현      NO    D 구현       NO
push            NO    세 번째 영상 NO
```

산출물: `runs/bcs/bcs_v0/<vid>.json` · `.md`. 공식 `report.json`에 쓰지 않는다.

# M8 C2 판정 패널 N=8 — 동결 기록 (2026-08-27)

기계가 읽는 정본은 `m8_c2_panel_manifest_2026-08-27.json`이다. 이 문서는 그 근거와
판단을 사람이 읽게 적은 것이다.

```
패널 목적     M8 구조 acceptance gate C1~C3 판정
확률표본 아님   "한국어 장영상 전체를 대표한다"는 주장에 쓰지 않는다
표현          사전 정의된 적격 조건과 deterministic selection rule로 고정한
             M8 구조 판정 패널
```

관련 문서: [M8_M9_DECISIONS](M8_M9_DECISIONS_2026-08-26.md) ·
[M8_C2_SOURCING_RULE](M8_C2_SOURCING_RULE_2026-08-27.md) ·
[M8_M9_PROTOCOL](M8_M9_PROTOCOL_2026-08-26.md)

---

## 1. 왜 이렇게 골랐나

앞선 논의에서 부족한 2편을 사람이 지정하는 안(A)과 규칙으로 뽑는 안(B)을 놓고
**B로 확정**했다. 이유는 하나다 — pilot에서 `recall@0.3 = 0.3019`를 **이미 본 뒤**이므로,
사람이 후보를 훑어 고르면 "쉬워 보이는 영상을 골랐다"는 의심을 절차로 반박할 수 없다.

그래서 순서를 뒤집을 수 없게 만들었다.

```
1  sourcing rule 동결       후보를 하나도 보기 전에 커밋 (66b0f93)
2  후보 조회                metadata만 — 재생·캡션·자막·순위 열람 없음
3  적격 필터 E1~E13
4  후보 풀 동결 + sha256     ← 여기까지 끝난 뒤에야
5  seed 해시 정렬            선정이 계산된다
```

4번과 5번의 순서가 이 절차의 전부다. 순위를 먼저 보고 풀을 손대면 "자동 선정"이라는
말이 성립하지 않는다. `scripts/m8_c2_panel.py --verify`가 풀 해시를 다시 계산해 대조한다.

## 2. 기존 6편 — 그대로 유지

신규 선정 결과를 보고 기존 구성을 다시 조정하지 않았다. 다양성을 이유로 교체하는 것도
결과를 본 뒤의 개입이 될 수 있어 하지 않았다.

| 영상 | 구간 | 판정 | 비고 |
|---|---|---|---|
| `baekmansonghee_jirisan` | 183 | ELIGIBLE | |
| `softyeon_ceramics` | 192 | ELIGIBLE | |
| `jissi_farm` | 211 | ELIGIBLE | 정규 재캡셔닝 수행 — §3 |
| `kbs_banff` | 316 | ELIGIBLE | 2026-08-27 취득·인덱싱 |
| `wonyi_gyeongju` | 345 | ELIGIBLE | 2026-08-27 취득·인덱싱 |
| `wonyi_geoje` | 327 | ELIGIBLE | 2026-08-27 취득·인덱싱 · `wonyi_gyeongju`와 동일 채널 |

## 3. jissi_farm — 정규 절차 결과와 판정

```
대상       자동 판정된 오염 캡션 2건 (구간 14 · 117 / 총 211구간 = 0.95%)
수행       m3 --recaption-corrupted → m4     (사람이 캡션을 보고 고르지 않았다)
결과       VLM이 실제로 실행됐고 **출력이 동일**했다. text_hash 불변, 오염 2건 잔존
판정       ELIGIBLE
```

같은 프레임에 같은 모델·같은 commit이면 greedy 생성은 결정적이다(2026-08-18에 AI Hub
2,328구간 재생성으로 확인된 사실). 즉 재시도가 실패한 것이지 절차가 안 돈 것이 아니다.
`pipeline-verify` 규약이 이 경우를 이미 규정해 뒀다 — **재캡셔닝 대상 목록에 있었던
잔존은 "재시도 실패 시 greedy 유지" 규약에 따른 정상 동작**이고 감지 휴리스틱 버그가
아니다.

ELIGIBLE로 둔 근거 셋:

```
① 정규 절차를 수행했고, 잔존은 기존 규약이 정상 동작으로 규정한 경우다
② 패널 수준의 오염 허용 임계는 사전에 정의된 적이 없다. 지금 만들면
   "어느 영상에 걸리는지 안 뒤에 만든 기준"이 된다
③ 캡션이 깨끗한 영상만 남기면 M8 입력 난이도가 낮은 쪽으로 표본이 쏠려 C2가
   위로 편향된다. 0.95%를 이유로 빼는 것은 그 방향의 개입이다
```

반대 판정(`PREDEFINED_AUTOMATIC_QC_FAILURE`로 보고 reserve 교체)도 논리적으로 가능하다.
그렇게 하려면 **기준을 새로 만들어야 하고**, 그 기준은 이 영상을 안 뒤에 만들어진다.
그래서 만들지 않았다. 이 판단은 manifest에 사유와 함께 남아 있으므로 뒤집을 수 있다.

## 4. 배제한 영상과 사유

사유가 서로 다르므로 하나로 뭉뚱그리지 않는다.

| 영상 | 코드 | 사유 |
|---|---|---|
| `gwaktube_soviet_apartment` | `SAMPLE_CONSUMED_PILOT` | 2026-08-18 pilot 사용 · 확증 표본 재사용 금지 선언 |
| `kheritage_grave_excavation` | `SAMPLE_CONSUMED_PILOT` | 동일 |
| `_10_000_…_Wilderness` | `NO_INDEPENDENT_REFERENCE` | 사건 수가 로그에 노출돼 독립 reference 작성 불가 |
| `pland_costco_hosting` | `PRIOR_EXPOSURE_RISK` | §5 |
| test 4편 | `TEST_SPLIT` | 절대규칙 1 |
| `e2e_*` 4편 | `E2E_ONLY` | 외부 E2E 전용 자원 |

## 5. `pland_costco_hosting` — "오염 확정"이 아니라 회피 가능한 위험

```
사실  M8 report 생성 이력 없음 · 표본 소비 선언 대상 아님
      다만 케이스 스터디에서 캡션 · 검색 결과 · 특정 프레임을 상세히 열람했다
```

reference 사건의 입도가 기존 파이프라인 산출물 쪽으로 끌릴 가능성을 배제하기 어렵다.
이것을 **오염 확정**이라고 쓰지 않는다. 정확한 표현은
**independent reference labeling에 대한 avoidable prior-exposure risk**다 — 회피할 수
있는 위험이고, 대체 후보가 있으므로 회피했다.

## 6. 신규 2편 선정

```
namespace   M8-C2-N8-v1
seed        f035073            선정 전에 이미 존재하던 commit
algorithm   SHA256(namespace | seed | source_id)   오름차순
```

`source_id`는 공백만 제거하고 **casefold하지 않는다**. YouTube ID는 대소문자를 구분하므로
접으면 서로 다른 영상이 같은 키가 될 수 있다.

후보 풀은 62편(고유 채널 47)이고 탈락 0건이었다. 조회 120건 중 58건은 재생 시간
750~2000초 범위 밖이라 metadata 보강 단계 이전에 걸러졌다.

### 6-1. 확정된 신규 2편

| rank | video_id | source_id | 구간 | 재생 | 채널 |
|---|---|---|---|---|---|
| PRIMARY_1 | `m8c2_3I7oGwk6EaQ` | `3I7oGwk6EaQ` | 173 | 864초 | 알로에베라 |
| PRIMARY_2 | `m8c2_cIxG7OHYMPU` | `cIxG7OHYMPU` | 328 | 1,638초 | 산타는 아재-등산.MTB라이딩 |

reserve는 rank 순으로 `0PYvd7jliwA` · `pw-k3s1mWGU` · `r8kYXd5U_mY` · `K8IDIzVS_Xo` ·
`YSlGx47reNg` … 이며 manifest에 전량 기록돼 있다.

**프로젝트 video_id는 내용이 아니라 `source_id`에서 땄다.** 제목을 보고 이름을 지으면
선정 단계에 내용 판단이 섞인 것처럼 보인다.

`m8c2_3I7oGwk6EaQ`는 인덱싱 후 자동 판정으로 오염 캡션 3건이 나와 §3과 **같은 정규
절차**를 밟았다 — 구간 29·126은 회복, 구간 1은 재시도 실패로 greedy 유지(잔존률 0.58%).
판정은 같은 근거로 `ELIGIBLE`이다.

### 6-2. 최종 패널 8편

```
baekmansonghee_jirisan  183      kbs_banff          316
softyeon_ceramics       192      wonyi_gyeongju     345
jissi_farm              211      wonyi_geoje        327
m8c2_3I7oGwk6EaQ        173      m8c2_cIxG7OHYMPU   328
                                 ─────────────────────
                                 합계 2,075구간
```

## 7. 채널 조건

```
C1  신규 2편 서로 다른 채널          PASS
C2  신규 2편 ≠ 기존 패널 채널        PASS (채널을 아는 3편 기준)
```

**기존 6편 중 3편은 취득 시점에 출처를 기록하지 않아 채널을 모른다**
(`baekmansonghee_jirisan` · `softyeon_ceramics` · `jissi_farm`). 추측해 채우지 않는다 —
registry의 legacy 규칙과 같다. 따라서 C2는 검증 가능한 범위에서만 강제됐고, 나머지
3편에 대해서는 **검증 불가**로 기록한다.

한계로 그대로 남긴다:

> 8편 중 2편(`wonyi_gyeongju` · `wonyi_geoje`)은 동일 채널이다.

C2 계산법은 바꾸지 않는다 — 중앙값 그대로다. channel clustering 보정도, weighting도
새로 만들지 않는다. 신규 2편에서 채널 중복을 더 늘리지 않는 것으로 끝낸다.

## 8. 교체 규칙

primary가 실패해도 사람이 새 영상을 고르지 않고 reserve 순서를 그대로 쓴다.
허용 사유는 기술적 실패와 권리 문제, 사전 정의된 자동 QC 실패뿐이다. "사건이 적어
보임"·"결과가 낮음"·"결과 균형 조정"은 사유가 될 수 없다.

교체가 발생하면 manifest를 덮어쓰지 않고 `replacements` 레코드를 추가한다.

## 9. 이 단계에서 하지 않은 것

```
M8 report 생성 · Event Recall 계산 · M9 · 공식 test 접촉        하지 않았다
caption · subtitle · retrieval 기반 선정                       하지 않았다
사람의 난이도 판단                                             하지 않았다
N · threshold · 통계량 변경                                    하지 않았다
push                                                          하지 않았다
```

## 10. 다음 단계

패널이 FROZEN이면 **그때부터** reference-event 라벨링을 시작할 수 있다. 라벨러에게
보여주는 것은 프레임 이미지와 시각뿐이고, 캡션·자막·검색 결과·순위·M8 리포트·pilot
결과는 도구 차원에서 차단한다.

M9 공식 test 개방은 그 뒤에도 **별도 승인 사건**이다.

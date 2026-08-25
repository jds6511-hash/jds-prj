# 캡션 → 검색 케이스 스터디 계획 (2026-08-25) — **결과 열람 전 동결**

튜터 피드백(2026-08-25 회의)에 답하기 위한 **정성 사례 연구**다.
"어느 모델이 이겼는가"가 아니라 **"캡션의 표현 차이가 검색 순위에 어떤 경로로
전달되는가"**를 사람이 한눈에 보게 만드는 것이 목적이다.

기계 판독본: `docs/finalization/caption_retrieval_casestudy_plan.json`

---

## 0. 성격과 경계 — 먼저 읽어라

```
qualitative / illustrative · one-video case study · outcome-blind query construction
공식 model selection experiment가 아니다
```

| 하지 않는 것 | |
|---|---|
| 유의성 검정 · 신뢰구간 | 안 한다 |
| 공식 MRR 추정 | 안 한다 |
| 4B 채택 판단 | 안 한다 |
| 배포 변경 · α 재조정 · α sweep | 안 한다 |
| 결과를 보고 scene/query 교체 | 안 한다 |

**이 케이스 스터디 결과와 무관하게 유지되는 것:**
과학적 우열 **미해결** · 배포 **3B 유지** · 4B **후보이며 채택 아님**.

**사용 금지 자원:** test39 · test 확장 33건 · P2 · P3 · M9 · E2E 전용 영상 · dev 3편.

---

## 1. 대상 영상

```
video_id        pland_costco_hosting
segments        395 · 마지막 end 1971.63s (32:52) · seg_len 5s
frames          395장 (M2 산출물)
3B 캡션          기존 저장 산출물을 그대로 사용 (재생성하지 않는다)
4B 캡션          없음 → 이번 작업에서 이 영상에 한해 생성 승인
```

**경계 확인 실측:** 이 영상을 참조하는 질의 0건 · dev/test split 미배정 ·
P2 표본 아님 · E2E manifest 미포함.

**제약 1건 — provenance는 `legacy_exempt`다.** "출처 URL·ID 없이 인덱싱된 기존 영상"으로
등록돼 있고, 사후에 출처를 붙이면 추측이 되므로 붙이지 않는다.
따라서 **프레임 artifact는 튜터 논의 한정**이고 공개·배포에 쓰지 않는다.

---

## 2. 장면 선정 규칙 (내용을 보고 고르지 않는다)

```
영상을 segment 인덱스 기준 5등분 → 각 구간의 시작 idx부터 순서대로
"첫 적격 segment" 1개씩 선택. 구간 크기 79, 시작 idx [0, 79, 158, 237, 316]
```

적격 판정은 **원본 대표 프레임만** 보고 한다. 캡션·자막·검색 결과를 보지 않았다.

**제외 사유(사전 정의):** black frame · transition/fade · severe blur ·
decoding failure · 거의 동일한 정지화면 · 화면 내용 식별 불가.
제외가 필요하면 그 구간의 다음 eligible segment로 이동한다.

**실제 적용 결과: 5개 구간 모두 시작 idx의 첫 후보가 적격이라 이동이 없었다.**

| scene | idx | 시각 | 프레임 내용 (원본만 보고 기술) |
|---|---|---|---|
| scene01 | 0 | 0:00~0:05 | 노란 프라이팬에 기름, 가운데 새우 튀김 한 점. 오른쪽 위 식힘망과 손. 화면 중앙에 채널 로고 오버레이 |
| scene02 | 79 | 6:35~6:40 | 창고형 매장 부감. 파란 대형 배너, 유리문 냉장 진열장, 적재 상자·팔레트 |
| scene03 | 158 | 13:10~13:15 | 주방. 흰 티셔츠를 입은 사람이 도마 위 흰색 원형 재료를 식칼로 썬다 |
| scene04 | 237 | 19:45~19:50 | 장갑 낀 손이 노란 무쇠 냄비 뚜껑을 들어 올린다. 안에 소스 끼얹은 고기와 다진 파. 화면 자막 있음 |
| scene05 | 316 | 26:20~26:25 | 재봉틀 작업대. 손이 남색 물방울 무늬 천을 잡고 있다. 왼쪽 가위, 오른쪽 나무 자 |

scene01의 로고 오버레이, scene04의 화면 자막은 **제외 사유가 아니다**(내용 식별 가능).
다만 캡션에 영향을 줄 수 있는 속성이므로 기록해 둔다.

---

## 3. 질의 작성 규칙

**장면당 3개 · 총 15개.** 유형은 Q1 object/scene · Q2 action · Q3 relation/context.

```
작성 근거   원본 대표 프레임만
작성 시점   3B/4B 캡션과 검색 결과를 열람하기 전
어휘        모델 캡션 어휘를 베끼지 않는다 (캡션을 읽지 않았으므로 베낄 수도 없다)
```

| scene | Q1 object | Q2 action | Q3 relation |
|---|---|---|---|
| 01 | 기름이 가득한 프라이팬 안의 새우 튀김 | 새우를 기름에 넣어 튀기는 장면 | 주방에서 튀김 요리를 하는 장면 |
| 02 | 대형 마트 안에 걸린 파란 광고 배너 | 매장 안에서 사람이 지나가는 장면 | 냉장 진열장과 쌓인 상자가 있는 창고형 매장 내부 |
| 03 | 나무 도마 위에 놓인 흰색 재료와 식칼 | 칼로 재료를 썰고 있는 손 | 주방 조리대에서 재료를 손질하는 사람 |
| 04 | 노란색 뚜껑이 있는 무쇠 냄비 | 냄비 뚜껑을 손으로 들어 올리는 장면 | 완성된 조림 요리를 냄비에서 확인하는 장면 |
| 05 | 물방울 무늬가 있는 남색 천 | 재봉틀 앞에서 천을 손으로 잡고 있는 장면 | 작업대 위에 재봉틀과 가위가 놓인 작업 공간 |

---

## 4. 검색 조건

```
PRIMARY     caption-only · alpha = 0.0
            자막 채널을 제거해 캡션 차이가 순위에 미친 영향을 직접 본다
SECONDARY   deployment fusion · alpha = 0.5 (선택)
            실제 시스템에서 자막까지 섞이면 어떻게 보이는지 참고용일 뿐이고
            primary 해석을 뒤집는 공식 판정이 아니다
alpha sweep 금지 · 후보 풀은 그 영상의 395 segment 전체 · top3까지 기록
```

---

## 5. 4B 생성 조건

기존 비교 조건과 **동일하게** 맞춘다. 새 프롬프트를 만들지 않고, 4B에 유리하게
튜닝하지 않는다. 3B 캡션은 **기존 저장 산출물을 그대로** 쓴다(재생성하지 않는다).

기록할 항목: 모델 revision · prompt = 기존 P0 · prompt hash · effective quantization ·
decoding config · max output token · segment count · caption row count · 소요.

**격리:** 별도 namespace에 생성한다. production/dev/test 인덱스, P2/P3 artifact,
배포 config, 현행 3B incumbent 상태를 **변경하지 않는다.**
4B 생성 때문에 본 인덱스를 재생성하지 않는다.

---

## 6. 해석 규칙

허용: `likely contributor` · `plausible lexical/semantic match` ·
`omission may have contributed` · `caption emphasis may have shifted ranking`.

금지: `proven causal mechanism` · `모델이 영상을 더 잘 이해했다` ·
`이 사례로 4B가 더 좋다는 것이 증명됐다` · `타율이 높으니 채택해야 한다`.

**top-1 hit count는 계산하되 반드시 병기한다** —
*"이 값은 한 영상의 5개 장면, 15개 illustrative query에서 나온 case-study count이며
일반적인 모델 정확도나 superiority estimate가 아니다."*
표기는 `illustrative top-1 hit count`로 고정한다.

---

## 7. 결과가 밋밋해도 바꾸지 않는다

두 모델 순위가 전부 같거나, 차이가 거의 없거나, 기대와 반대여도
**scene·query를 교체하지 않는다.** "보여주기 좋은 사례"를 결과 보고 다시 고르지 않는다.

기존 AI Hub 사례(`여자가 몸을 숙인다` 등)는 **historical illustration**으로 역할이
다르다. 이 케이스 스터디와 섞어 새 formal performance result를 만들지 않는다.

---

## 8. 오염 발견 시

4B 생성물에서 instruction echo · mixed-script · truncation이 나와도
**detector rule·recaption rule을 바꾸지 않고, scene/query를 교체하지 않고,
사후 정리를 하지 않는다.** 정성 관측으로만 기록한다.

---

## 9. 실행 순서

```
1  provenance / 3B artifact 감사                     ← 완료
2  5개 장면 선정 (원본 프레임만)                       ← 완료
3  장면당 질의 3개 작성 (총 15개)                      ← 완료
4  계획 commit                                       ← 이 문서. 여기까지 캡션·결과 미열람
5  격리된 4B 캡션 생성 (395 segment)
6  3B / 4B caption-only 검색
7  target rank + wrong top1 장면 추출
8  정성 해석 작성
9  (선택) deployment α=0.5 secondary view
10 결과 artifact 정리
```

**4단계까지 3B/4B 캡션과 검색 결과를 열지 않았다.** 이 문서를 커밋한 뒤에 연다.

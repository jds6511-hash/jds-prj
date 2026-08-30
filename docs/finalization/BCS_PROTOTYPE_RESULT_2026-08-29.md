# 결과 — Boundary-Content Split prototype v0 (2026-08-29)

```
성격   제품 설계 prototype 실행 결과
아님   성능 실험 · acceptance · 공식 M8 변경 · 새 GT
규격   BCS_PROTOTYPE_SPEC_2026-08-29.md
실행본  5dc5030 · Qwen2.5-7B-Instruct · llm_4bit false · greedy
```

**두 영상 모두 처음으로 유효 문서가 나왔다.** 프로토타입 v1~v4는 전부 무효였다.

---

## 1. 결과

```
                         3I7            geoje
구간                      173             327
Episode                    18              32
1구간 Episode                0               1
≤2구간 Episode               2               2
길이 median / p25 / p75  6 / 3 / 17      7 / 4 / 11
prototype_status           OK              OK
커버리지(겹침0·구멍0)      OK              OK
```

STT 상태.

```
3I7    EMPTY 140 · USABLE   4 · REPEATED 20 · OVERLAY_OR_URL 9
geoje  EMPTY  12 · USABLE 315 · 제거 0
```

---

## 2. 이전 계층 구조와의 대조

```
                    구 계층(v3/서술)      BCS v0
3I7  사건 수              16                18
     1구간 사건            1                 0
geoje 사건 수             66                32
     1구간 사건           25                 1
     ≤2구간 사건          40                 2
     median 길이           2                 7
```

**5초 조각화가 두 영상 모두에서 사라졌다.** geoje에서 1구간 사건이 25 → 1이다.
경계 pass 6회 전부 `boundary_output_status = OK` — 연속 정수 열거가 없었다.

---

## 3. 오염 전파 — 0건

```
                        구 계층        BCS v0
3I7  오염 전파            2건            0건
       E07 "마포구청 인터넷 방송국 홈페이지를 방문한 후"
       E15 "다음 영상에서 만나요라는 메시지를 보여주며"
     외국문자 생성        1건            0건
geoje 오염 전파           0건            0건
```

3I7의 오염 STT 29건이 sanitation에서 걸러져 **서술 입력에 오르지 않았다.**

---

## 4. STT는 구조를 깨지 않고 의미만 더했다 — 예측한 비대칭

```
dialogue_note      3I7  0 / 18        geoje  14 / 32
근거 미달로 버림     3I7  0            geoje   2  (cite_not_usable_stt 1 · no_stt_cite 1)
```

3I7은 사용 가능한 STT가 4건뿐(전부 잔존 오염)이라 대화 노트가 **한 건도 생기지
않았다.** geoje에서는 14건이 근거 검증을 통과했다.

검증이 실제로 작동한 사례.

```
EP15  cite_not_usable_stt   모델이 STT 없는 구간 [210~216]을 근거로 댔다 → 버림
EP20  no_stt_cite           근거 없이 대화 주장 → 버림
```

**구조는 두 영상에서 안정적이고, 대화는 경계가 아니라 내용에만 들어갔다.**
규격 §7의 핵심 주장이 두 사례에서 성립한다.

---

## 5. 남은 문제 — 정직하게

### 5-1. dialogue_note가 요약이 아니라 인용이다

절반 이상이 발화를 그대로 붙여 놓는다.

```
EP03  "거제 사람들이 이런 사람 보면 무슨 일 할까요? / 이상한 거 하나 거제 들어왔다 / …"
EP11  "대충 이런 꽃게 같은 거 라면에 넣어주면 맛있어요 / 시원하게 한 번 젖히고 …"
EP29  "우리 치킨에는 맥주 치맥 해야지, 맛있어, 맛있어, 이거는 상큼, …"
```

제대로 된 것도 있다.

```
EP05  "도포의 위치, 전자나무, 거제 버스의 조용함, 저녁 식사 계획에 대한 이야기를 나눕니다."
EP31  "내일 시내 보여드릴게요, 진짜 시장 시절 코스부터 시내 코스까지"
```

프롬프트는 "결정·계획·약속을 한 문장"으로 요구하지만 모델이 발화 나열로 답한다.
**고치지 않았다** — 프롬프트 수정은 별도 결정이다.

### 5-2. 일부 요약이 한 문장 제약을 열거로 우회한다

```
3I7 EP03  "…터널을 지나, …작업하는 사람을 보고, …등불을 들고 걷는 사람을 본 후,
           …작은 동물이 움직이는 것을 목격하고, …글씨를 발견한다."  (154자)
```

긴 Episode에서 나타난다. 한 문장 제약이 절 나열로 흡수됐다.

### 5-3. 3I7 요약은 여전히 화면 묘사다

```
EP01  "화면은 차례로 어두운 밤 풍경, 저녁녘 풍경, 숲속 계곡, 산의 모습을 보여준다."
EP18  "도로와 도시의 전경이 보였다가 화면이 검게 변했습니다."
```

유효 발화가 없는 조건에서는 예상된 결과다(규격 §7 기대와 일치). 다만 이 트랙에서
**caption만으로 사건 서술을 만드는 문제는 여전히 미해결**이다.

### 5-4. 문체가 섞인다

`~한다` / `~합니다` / `~이다`가 Episode마다 다르다. 최종 문서로 쓰려면 정리가 필요하다.

---

## 6. 내 결함 2건 — 첫 실행을 무효로 만들 뻔했다

첫 실행 결과는 두 파서 결함으로 왜곡돼 있었다. **모델 탓이 아니다.**

```
① stt_cites 표기
   모델은 ["seg#55", "seg#56"]로 냈고 파서는 순수 숫자만 받았다
   → dialogue_note 14건이 전부 `no_stt_cite`로 오탐 폐기
   → 겉보기 수율 2/32 (실제 14/32)

② 깨진 JSON의 폴백
   EP21에서 모델이 `"dialogue_note": "stt_cites": [...]`로 값 하나를 빠뜨렸다
   맨문장 폴백이 **JSON 원문을 그대로 요약으로 채택**해 문서에 노출됐다
```

v2 canary의 "맨 배열" 사고와 같은 부류다 — **표기를 계약으로 착각한 것**이다.

정정은 **저장된 raw를 고친 파서로 다시 읽어** 했다. LLM을 부르지 않았고 GPU를
쓰지 않았으며 경계·span·근거 앵커는 손대지 않았다.

```
구조            불변 (Episode 18 · 32)
dialogue_note   2 → 14
버림 사유        no_stt_cite 14  →  cite_not_usable_stt 1 · no_stt_cite 1
요약이 바뀐 것    EP21 하나 (salvaged_summary)
parse_mode      geoje json 31 · salvaged_summary 1 / 3I7 json 18
```

`parse_mode`를 산출물에 남겨 어느 경로로 읽었는지 사후에 가릴 수 있게 했다.

---

## 7. 성공 질문에 대한 답

```
구조   두 영상 모두 5초 조각화 없음                        YES
오염   오염 STT가 서술에 오르지 않음                        YES (양쪽 0건)
의미   대화가 경계가 아니라 내용을 풍부하게 함               YES (3I7 0 · geoje 14)
사용   5초 로그가 아니라 시간 흐름으로 읽힘                  부분 — §5 문제 남음
```

---

## 8. 경계

```
공식 M8/M9 변경  NO    test 접근    NO    새 GT·라벨   NO    push          NO
경계 수 상한     NO    C 구현       NO    D 구현       NO    세 번째 영상   NO
프롬프트 수정    NO (§5-1은 기록만)
```

산출물.

```
runs/bcs/bcs_v0/<vid>.json           첫 실행 원본 (파서 결함 포함 · 보존)
runs/bcs/bcs_v0_reparsed/<vid>.json  정정본 + .md   ← 읽을 것은 이쪽
scripts/bcs_prototype.py             실행 (LLM)
scripts/bcs_reparse.py               재파싱 (LLM 미사용)
src/bcs.py                           sanitation · 경계 · 내용 · 검증 · 렌더
```

첫 실행 원본을 지우지 않는다 — 결함이 무엇이었는지 대조할 수 있어야 한다.

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

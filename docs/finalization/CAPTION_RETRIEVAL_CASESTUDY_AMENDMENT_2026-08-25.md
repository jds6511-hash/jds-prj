# 케이스 스터디 설계 보강 (2026-08-25) — **outcome-blind amendment**

원 계획: `CAPTION_RETRIEVAL_CASESTUDY_PLAN_2026-08-25.md` (commit `31b5b02`)

---

## 0. 이 보강이 post-hoc 수정이 아닌 이유

```
캡션 내용 열람        아직 없음
검색 결과 열람        아직 없음
장면 5개 · 질의 15개   원 계획대로 동결 유지 (해시 불변)
```

**결과를 보기 전에 대조 조건만 강화한 것이다.** 결과가 나온 뒤에는 arm을 재생성하거나
조건을 바꾸지 않는다.

---

## 1. 결정

**기존 2026-07 저장 3B 캡션을 이번 직접 대조에 사용하지 않는다.
오늘 4B와 동일한 실행 환경에서 3B도 새로 생성한다.**

이번 케이스 스터디의 대조는 **fresh 3B q4 vs fresh 4B q4**다.

---

## 2. 이유

기존 3B 캡션은 **caption provenance 기능(`17516fb`, 2026-08-17) 도입 이전 산출물**이라
생성 시점·기계·라이브러리 조건이 기록돼 있지 않다. 파일 시각으로 2026-07-12~14로
보이지만 그것뿐이다.

그 상태로 비교하면 튜터 질문에 이런 반론이 항상 남는다.

> "그 차이가 모델 때문인지, 7월과 오늘의 실행 환경·라이브러리 차이 때문인지
> 어떻게 아나요?"

3B를 오늘 다시 생성하면 이 케이스 스터디에 한해 이렇게 말할 수 있다.

> **같은 영상·같은 프레임·같은 노트북·같은 실행 코드·같은 P0 프롬프트·같은 4bit
> 조건에서 모델만 3B ↔ 4B로 다르게 했다.**

이는 CLAUDE.md 후보 검증 규약 4번(**동시점 대조군**)이 요구하는 조건이다.
원 계획은 이 조건을 만족하지 못했고, 이번 보강으로 만족시킨다.

---

## 3. Fresh paired conditions

```
VIDEO      pland_costco_hosting · 동일 395 segment · 동일 프레임 입력
ENV        같은 RTX 3060 Laptop 6GB · 같은 repository commit·코드 경로
           같은 Python/라이브러리 환경 · 같은 frame artifact · 같은 namespace
```

| | 3B arm | 4B arm |
|---|---|---|
| 모델 | `Qwen/Qwen2.5-VL-3B-Instruct` | `Qwen/Qwen3-VL-4B-Instruct` |
| revision | 실행 시 실측 기록 | 실행 시 실측 기록 (2×2 기록값 `ebb281ec70b05090…`) |
| 프롬프트 | P0 | P0 |
| prompt_sha256 | 실측 기록 | 실측 기록 (기대값 `b7c2598ade97784d…`) |
| effective_quantized | true | true |
| decoding / max token | 동일 | 동일 |

**두 arm은 `scripts/casestudy_make_config.py`가 `config.yaml`에서 재생성한 config로만
돌린다.** 그 스크립트는 `caption_prompt`·`vlm_max_new_tokens`·`vlm_rep_penalty`·
`vlm_max_pixels`·`vlm_4bit`·`embed_model`·`seg_len_sec`·`static_threshold`가
생성 전후로 동일한지 `assert`로 확인한다. **어느 arm에도 유리하게 튜닝하지 않는다.**

---

## 4. 격리

```
runs/casestudy_caption_retrieval/cs_20260825/
  config_3b.yaml   → 3b_fresh/work · 3b_fresh/results
  config_4b.yaml   → 4b_fresh/work · 4b_fresh/results
  run_arm.sh       (arm 인자 하나로 두 arm을 같은 코드 경로로 돌린다)
```

**기존 3B production/historical 캡션은:** 덮어쓰지 않음 · 삭제하지 않음 ·
이번 paired 비교에 사용하지 않음 · historical artifact로 그대로 보존.

새 산출물은 production/dev/test/P2/P3 인덱스와 **완전 분리**한다.

---

## 5. 양자화 표기

이번 케이스 스터디는 **3B q4 vs 4B q4**다. 6GB 노트북에서 4B bf16이 들어가지 않고,
무엇보다 **배포와 같은 조건**이라 케이스 스터디 목적에 더 맞는다.

**과거 AI Hub 2×2의 `4B bf16` 결과와 직접 수치 비교하지 않는다.**

---

## 6. 작업 순서

```
1  amendment 문서 작성 및 commit                    ← 이 문서
2  scene 5개 / query 15개 freeze 상태 재확인          해시 대조
3  fresh 3B generation                              약 53분
4  fresh 4B generation                              약 39분
5  두 arm provenance/config equality 검사
6  그 이후에만 caption/retrieval outcome 접근
```

**결과가 나온 뒤 arm을 재생성하거나 조건을 변경하지 않는다.**

---

## 7. 원 계획에서 바뀌지 않은 것

장면 선정 규칙·5개 장면·질의 15개·질의 동결 해시·primary α=0 / secondary α=0.5 ·
α sweep 금지 · 해석 표현 규칙 · 오염 발견 시 규칙 불변 · top-1 hit count 표기 제약 ·
결과가 밋밋해도 교체 금지 · incumbent 결론 유지(3B 배포·4B 후보·우열 미해결).

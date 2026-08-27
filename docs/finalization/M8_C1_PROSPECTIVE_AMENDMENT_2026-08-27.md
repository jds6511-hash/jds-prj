# C1 `early_stop` — post-official-run prospective amendment (2026-08-27)

**과거 결과를 구제하는 수정이 아니다.** 공식 실행의 C1 판정은 그대로 두고,
**다음 fresh confirmation에만** 적용할 규격을 고친다.

```
공식 실행 (m8_official_0827)          변경 없음
  C1 = FAIL · early_stop PRESENT 4/8
  M8 evaluation COMPLETE · M8 acceptance FAIL
  이 문서가 그 값을 다시 계산하지 않는다
```

---

## 1. 왜 고치는가 — 알려진 evaluator 결함

사전등록 산문과 동결 구현이 어긋나 있었고, 공식 실행 결과로 그 어긋남이
**구체적으로 드러났다.**

```
사전등록 문구 (규격 §1-1)
  "정상 report completion 전에 생성이 **종료되어** schema상 필요한 출력의
   **뒷부분**이 만들어지지 않은 경우"

동결 구현 (src/m8_c1.detect_early_stop)
  truncated_tail · **미복구 청크** · sentences 0건
```

공식 실행에서 걸린 것은 미복구 청크뿐이고, 사후 분류 결과는 이렇다.

```
kbs_banff          실패 청크 [0, 2] / 총 6 (마지막 5)   MID_STREAM_EMPTY_CHUNK
m8c2_3I7oGwk6EaQ   실패 청크 [2]    / 총 4 (마지막 3)   MID_STREAM_EMPTY_CHUNK
m8c2_cIxG7OHYMPU   실패 청크 [4]    / 총 6 (마지막 5)   MID_STREAM_EMPTY_CHUNK
wonyi_geoje        실패 청크 [5]    / 총 6 (마지막 5)   TAIL_TERMINATION
```

**4건 중 3건은 tail termination이 아니었다.** `truncated_tail`은 8편 전부 None이다.

즉 동결 구현이 "생성이 끝까지 진행됐지만 중간에 구멍이 생긴 것"까지 파국으로
셌다. 그것은 실패이긴 하지만 사전등록이 지목한 실패가 아니다.

---

## 2. 다음 confirmation에 적용할 규격

```
early_stop (catastrophic)
  생성이 **실제로 종료**되어 required report tail이 만들어지지 않은 경우만.
  기계 증거: truncated_tail · finish_reason · 마지막 청크의 미복구 · sentences 0건

generation_hole (신규, catastrophic 아님)
  생성은 끝까지 진행됐으나 중간 청크의 유효 사건이 0으로 남은 경우.
  **진단으로 별도 기록**하고 C1 파국 수에 넣지 않는다.
```

`language_drift`·`repetition_loop`는 **그대로다.** 유형 3개 목록도 그대로이고
`generation_hole`은 C1 유형이 아니라 별도 진단 필드다.

`PRESENT / ABSENT / UNCLEAR` 3-state와 `UNCLEAR`는 통과가 아니라는 규칙,
그리고 `C1 PASS = catastrophic 0/8`도 그대로다.

---

## 3. 이 amendment의 성격

```
과거 판정 재계산      하지 않는다
임계 변경            없다 (0편 유지)
유형 목록 변경        없다 (language_drift · early_stop · repetition_loop)
새 임계 신설          없다 (비율·유사도 임계 만들지 않음)
적용 시점            redesign 후 **fresh confirmation부터**
```

방어 논리는 하나다 — **알려진 evaluator 결함을 다음 표본을 보기 전에 고치는 것**은
결과를 보고 관문을 느슨하게 만드는 것과 다르다. 전자는 공식 판정을 그대로 두고
후속 절차를 바로잡는 것이고, 후자는 이미 나온 판정을 뒤집는 것이다.

**그리고 이 수정은 이번 FAIL을 되돌리지 않는다** — C1을 좁게 읽어도
C2(0.3311)·C3(7.00)이 FAIL이므로 acceptance는 그대로 FAIL이다. 그 사실이
이 amendment가 결과 구제 목적이 아니라는 증거다.

---

## 4. 구현 시점과 해시

**아직 구현하지 않았다.** `src/m8_c1.detect_early_stop`은 공식 실행 당시 상태
그대로이고, evaluator 동결본의 C1 함수 해시 `a9d29100b3b9…`도 그대로다.

fresh confirmation용 evaluator를 동결할 때 다음을 함께 기록한다.

```
old C1 spec hash    a9d29100b3b9…      (공식 실행에 쓰인 것)
new C1 spec hash    (구현 후 산출)
amendment 문서      이 파일
```

두 해시를 나란히 남겨야 "어느 판정이 어느 규격으로 나왔는가"가 사후에 갈린다.

---

## 5. 적용 범위

```
적용     redesign된 M8의 fresh N=8 confirmation
미적용   공식 실행 m8_official_0827 · 그 결과를 인용하는 모든 문서
```

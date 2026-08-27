# M8 공식 생성·관문 판정 — 2026-08-27

```
M8 evaluation   COMPLETE      8편 전부 생성됐고 세 관문을 규격대로 계산했다
M8 acceptance   FAIL          C1·C2·C3 전부 미달
```

둘을 분리해 적는다(`M8_M9_DECISIONS_2026-08-26` D2-1). 기계가 읽는 정본은
`m8_official_result_2026-08-27.json`.

**임계·통계량·지표·taxonomy를 고치지 않았다.** 사전등록 §2-4가 "결과가 나빠도
임계를 고치지 않는다"고 적었고, 이 문서가 그것을 지킨다.

---

## 1. 판정

| 관문 | 값 | 임계 | 결과 |
|---|---|---|---|
| **C1** | 파국 **4/8편** (UNCLEAR 0) | 0편 | **FAIL** |
| **C2** | median(`event_temporal_alignment`) = **0.3311** | ≥ 0.70 | **FAIL** |
| **C3** | max(Compression) = **7.00** | ≤ 2.0 | **FAIL** |

```
video                      문장  GT  compr  align  @0.3  @0.5  @0.7   C1
baekmansonghee_jirisan      15    7   2.14  0.520  0.86  0.71  0.14  ABSENT
softyeon_ceramics            6   12   0.50  0.217  0.25  0.17  0.17  ABSENT
jissi_farm                  11   11   1.00  0.428  0.73  0.55  0.27  ABSENT
kbs_banff                   14   10   1.40  0.102  0.20  0.10  0.00  PRESENT
wonyi_gyeongju              16   10   1.60  0.561  0.90  0.70  0.40  ABSENT
wonyi_geoje                 10    8   1.25  0.547  0.88  0.62  0.38  PRESENT
m8c2_3I7oGwk6EaQ             7    1   7.00  0.225  0.00  0.00  0.00  PRESENT
m8c2_cIxG7OHYMPU            14    9   1.56  0.234  0.33  0.11  0.00  PRESENT
```

`@0.3/0.5/0.7`은 **진단 전용**이다(규격 §2A). 판정에 쓰지 않았다.

### 1-1. C3는 1건 영상 때문만이 아니다

`m8c2_3I7oGwk6EaQ`의 7.00은 GT가 1건이라 나온 값이다. 그것을 빼도
**max = 2.14**(`baekmansonghee_jirisan`)로 여전히 임계를 넘는다. 즉 C3 FAIL은
그 한 편에 의존하지 않는다.

### 1-2. C1 4편은 전부 `early_stop`이다

```
video                 drift   early_stop  repetition   미복구 청크
kbs_banff            ABSENT   PRESENT     ABSENT       [0, 2]
wonyi_geoje          ABSENT   PRESENT     ABSENT       [5]
m8c2_3I7oGwk6EaQ     ABSENT   PRESENT     ABSENT       [2]
m8c2_cIxG7OHYMPU     ABSENT   PRESENT     ABSENT       [4]
```

`language_drift` 0편 · `repetition_loop` 0편 · `truncated_tail` 전 영상 None.
근거는 전부 **청크 재생성 실패**다 — 유효 사건 0건인 청크를 1회 재생성했는데
그것도 0건이라, 그 구간 출력이 만들어지지 않았다.

---

## 2. 구현과 규격 문구의 간극 — 결과를 보고 고치지 않았다

규격 §1-1의 `early_stop` 문구는 이렇다.

> 정상 report completion 전에 생성이 **종료되어** schema상 필요한 출력의
> **뒷부분**이 만들어지지 않은 경우

`src/m8_c1.detect_early_stop`은 세 신호를 본다 — `truncated_tail` ·
**미복구 청크** · `sentences` 0건. 이번에 걸린 것은 두 번째뿐이고, 그것은
"생성이 종료된 것"도 "뒷부분"도 아니다. **영상 중간의 구멍**이다.
즉 구현이 문구보다 넓게 발동한다.

**그래도 고치지 않는다.** 지금 좁히면 결과를 보고 관문을 느슨하게 만든 것이 된다.
구현은 `m8_evaluator_freeze_2026-08-27.json`의 C1 함수 해시
`a9d29100b3b9…`로 **결과를 보기 전에 동결됐고**, 그 상태의 판정이 위 표다.

**이 간극은 acceptance 결론을 바꾸지 않는다.** C1을 문구대로 좁게 읽어
`early_stop` 0편이 되어도 C2(0.3311)와 C3(7.00)이 그대로 FAIL이다.
따라서 재해석 여부는 acceptance가 아니라 **원인 진단**의 문제다.

---

## 3. 생성 provenance

```
script           scripts/m8_official.py  (구조 경로 generate_report_structured)
config           config_server.yaml
model            Qwen/Qwen2.5-7B-Instruct  rev a09a3545…
dtype            torch.bfloat16 · quantized False · do_sample False (greedy)
max_new_tokens   16384
chunk            60 / overlap 5
생성              8/8편 · 실패 0편 · 확정 report.json 덮어쓰기 0건
```

**실행 코드 동일성은 git commit이 아니라 소스 해시로 보장된다.** push가 금지라
서버는 `git archive`로 동기화했고, 그래서 리포트의 `provenance.env.git_head`는
서버의 마지막 commit(`41875218`)이며 **실제로 실행된 코드의 commit이 아니다.**
전송된 트리는 로컬 `b92dc07`이고, 생성기 3파일 해시가 서버=로컬로 일치했다.

```
src/m8_report.py  87c2dfcbdf0a25c6…
src/llm.py        ed4d1f82cd5acd93…
src/common.py     a52156354df5f752…
```

`m8_official.py`의 pre-run 게이트가 이 대조를 통과해야만 생성을 시작한다.

### 3-1. PRE-RUN 게이트 기록

```
evaluator --verify        불일치 0
GT aggregate 해시          68a079ba17eb…      동결값과 일치
evaluator freeze_id       m8_evaluator_2026-08-27
기존 canonical report      0건               (첫 공식 실행)
생성기 소스 해시            3/3 일치
```

### 3-2. CANARY — 내용을 보지 않고 구조만

1편·2청크(120구간). 배치 계획 §배치B의 차단 조건이 `uncited_evaluable_sentences`였다.

```
uncited_evaluable_sentences   0     ← D4 차단 조건 해제
chunk_retries 0 · rejected 0 · structural_assert None
C1 세 유형 전부 ABSENT
확정 경로 report.json 미생성          ← 쓰기 경계 실측
```

FULL 중에도 내용을 열지 않았다 — run manifest는 수와 상태만 담고 서술 문자열과
C1 evidence를 담지 않는다(도구가 강제).

---

## 4. 진단 — 관문이 아니다

`Redundancy`는 미구현이다(규격 §4-1). 기계로 셀 수 있는 것만 적는다.
**이 표는 2026-08-27에 정정됐다** — 최초 판에서 미매칭 수 4행을 손으로 잘못 옮겼다(`softyeon 8→6` · `kbs_banff 7→8` · `3I7OgwK 1→0` · `cIxG 6→2`). 값은 정본 JSON에서 생성한다.

```
video                      미매칭 GT  미매칭 생성  span 커버  거부
baekmansonghee_jirisan           1          9      1.000      0
softyeon_ceramics                6          0      0.974      1
jissi_farm                       3          3      0.919      0
kbs_banff                        8         12      0.636      5
wonyi_gyeongju                   1          7      0.861      0
wonyi_geoje                      1          3      0.829      1
m8c2_3I7oGwk6EaQ                 0          6      0.711      1
m8c2_cIxG7OHYMPU                 2          7      0.774      3

거부 사유 합계   too_many_evidence 6 · evidence_outside_span 4 · bad_span 1
```

`span 커버`는 `timeline_span_coverage`(생성 사건 span 합집합 ÷ 전체 구간)다 —
**진단이고 coverage 지표로 쓰지 않는다**(긴 span 하나로 올릴 수 있다).

---

## 5. 이 결과로 하지 않은 것

```
임계·통계량·지표·taxonomy 수정         하지 않았다
C1 구현 재해석                       하지 않았다 (§2)
프롬프트·config·모델 변경             하지 않았다
재생성                              하지 않았다
M9 test opening                     하지 않았다
push                                하지 않았다
```

---

## 6. 다음 판단은 사람 몫

`M8 evaluation COMPLETE`는 확정이다. `acceptance FAIL`이므로
`m8_freeze.py` → `M9_READY_FOR_TEST_OPENING`으로 자동 진행하지 않는다.
FAIL 상태에서 M9로 갈지, 원인 진단을 먼저 할지는 **별도 결정 사건**이다.

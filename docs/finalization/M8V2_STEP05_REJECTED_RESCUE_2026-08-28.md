# M8-v2 STEP 0.5 — Rejected-candidate Rescue Reachability Pilot (2026-08-28)

```
판정   NO-GO
       A 회수 4 / 22  (필요 ≥5)          미충족
       B 회수 영상 2편 (필요 ≥2)          충족
       C 최대 영상 점유 0.75 (허용 ≤0.60)  미충족

→ M8-v2 미착수. fresh 영상·라벨 확보로 넘어가지 않는다.
```

**이 NO-GO는 아슬아슬한 게 아니라 구조적이다.** §E-1을 보라 — 적격 후보 분포상
A와 C는 **애초에 동시에 만족할 수 없었다.**

---

## A. Provenance

```
source_commit          c654f39d
step0_commit           c654f39
step0_artifact_sha256  2a938d7249ab6da4…
trigger                T2@0.7   accepted_span_coverage < 0.7   (§23에 따라 고정)
triggered_chunks       8 / 41
baseline_gt_unmatched  22
matcher                m8_metrics.match_events (frozen · 새 임계 없음)
new_labels 0 · generation 0 · LLM 0 · GPU 0
```

baseline report 8/8은 lineage sha256과 대조 후 진행했다(불일치면 중단).

산출물: `runs/m8v2_step05/` — `step05_manifest.json` · `candidate_audit.json` ·
`repair_results.json` · `gt_reachability.json` · `step05_summary.json`

---

## B. Evidence-order audit (§15 — 실행 전 확정)

```
schema               rejected 레코드는 {event(120자 절단) · span · evidence_segments · reason}
                     description이 없다 → 그대로는 재검증 불가
복원                 map_raw_outputs 재파싱으로 완전 후보를 되살리고
                     같은 validator를 태워 저장된 거부 목록과 대조(fail-closed)
score/rank 필드      없다
ordering_semantics   parse_events가 모델 출력 순서를 보존하고, rejected에 그 순서
                     그대로 저장된다(accepted만 sorted 처리)
canonical_rule       generation_order_first_4 — 생성 순서 앞 4개
GT-independent       예. GT는 repair 함수의 인자로도 들어가지 않는다(테스트로 강제)
result               규칙 하나만 쓰고 대안 규칙과 비교하지 않았다 (rule shopping 금지)
```

추가 확인 — `validate_events`는 **elif 체인**이라 `reason`이 집합이 아니다.

```
empty_event → no_segments → bad_span → seg_out_of_range → too_many_evidence
→ duplicate_evidence → evidence_outside_span → foreign_language → thin_description
```

`too_many_evidence`로 기록됐다는 것은 **앞 4개는 통과했고 뒤 4개는 평가된 적이 없다**는
뜻이다. 그래서 "고쳤다고 치고" 통과시키지 않고 **현행 validator를 그대로 다시 태웠다**.
다른 사유가 드러나면 STILL_REJECTED로 남긴다(§4·§7 준수).

---

## C. Candidate inventory

```
triggered chunks                 8
triggered raw candidates        16
triggered rejected candidates    9
  too_many_evidence              6      ← 적격
  evidence_outside_span          3      ← 비적격. 고치지 않는다
eligible_for_repair              6
```

적격 후보의 영상 분포.

```
kbs_banff           4    (ch0 ×3 · ch2 ×1)
m8c2_cIxG7OHYMPU    1    (ch4)
m8c2_3I7oGwk6EaQ    1    (ch2)
```

---

## D. Repair

```
attempted         6
validator PASS    5
still rejected    1     kbs_banff ch0 span[29,38] → evidence_outside_span
added events      5
```

절단 결과.

```
video              ch  원 evidence  retained            결과
kbs_banff           0        6      [0, 5, 13, 16]      VALID
kbs_banff           0        6      [22, 23, 26, 27]    STILL_REJECTED
kbs_banff           0       16      [41, 42, 45, 46]    VALID
kbs_banff           2       27      [110, 112, 114, 116] VALID
m8c2_3I7oGwk6EaQ    2       19      [110, 116, 117, 118] VALID
m8c2_cIxG7OHYMPU    4       21      [220, 223, 226, 230] VALID
```

evidence 16·19·21·27개짜리 후보가 있었다 — 규칙 위반 폭이 컸다.

---

## E. GT recovery

```
newly matched GT     4 / 22
videos recovered     2      kbs_banff 3 · m8c2_cIxG7OHYMPU 1
largest video share  0.75
rescued events       5
rescued 중 GT 미매칭  0      ← 추가된 사건이 전부 정답 사건에 붙었다
```

편별.

```
video               B0 → R1   회수 / 그 영상 미매칭
kbs_banff           14 → 17     3 / 8
m8c2_cIxG7OHYMPU    14 → 15     1 / 2
m8c2_3I7oGwk6EaQ     7 →  8     0 / 0
그 외 5편            변화 없음
panel               93 → 98   (+5.4%)
```

### E-1. A와 C는 동시에 만족할 수 없었다 — 구조적 NO-GO

적격 후보가 세 영상에만 있고, 그중 `m8c2_3I7oGwk6EaQ`는 **미매칭 GT가 0건**이라
회수에 기여할 수 없다. 따라서 회수 가능 상한은 다음이 전부다.

```
kbs_banff           최대 4
m8c2_cIxG7OHYMPU    최대 1
합계 상한            5
```

A(≥5)를 채우려면 `kbs_banff`가 4를 다 채워야 하고, 그러면
C의 점유율은 `4/5 = 0.80 > 0.60`이 되어 반드시 위반이다.

```
A 충족 ⇒ C 위반
```

**즉 이 intervention 정의로는 동결된 gate를 통과할 방법이 없었다.**
실측(4 / 0.75)은 그 상한 안에서 나온 값이다.

---

## F. Failure-mode coverage

```
kbs_banff           최대 기여자(미매칭 8). 3건 회수. 남은 5건은
                    적격 후보가 없거나(비적격 evidence_outside_span 1건) 회수 실패
m8c2_cIxG7OHYMPU    1건 회수 / 미매칭 2
m8c2_3I7oGwk6EaQ    사건 1건 추가됐으나 미매칭 GT가 0건이라 회수 기여 없음
softyeon_ceramics   미매칭 6건. accepted span coverage 1.0/1.0/1.0/0.81로
                    T2가 발화하지 않는다 — **이번 대상이 아니다**
그 외 4편            발화 없음 · 변화 없음
```

`softyeon_ceramics`의 short-GT swallowing(거대 span이 짧은 사건을 삼키는 모드)은
**이번 intervention이 다루지 않은 별개 실패 모드**다. T2가 발화하지 않는다는 이유로
그 실패를 없는 것으로 취급하지 않는다.

---

## G. Gate

```
A  newly matched GT >= 5        4 / 22        FAIL
B  videos recovered >= 2        2             PASS
C  max video share <= 0.60      0.75          FAIL
D  (보고 항목) rescued 중 GT 미매칭 = 0        대량 오탐 아님
```

```
STEP 0.5   NO-GO
```

---

## H. 해석

이 pilot은 **기전이 작동한다는 것과, 그 기전으로는 부족하다는 것을 동시에** 보였다.
`too_many_evidence` 거부는 결정적 절단만으로 6건 중 5건이 유효해졌고, 추가된 5개
사건은 **하나도 남김없이 정답 사건에 매칭됐다**(오탐 0). 그러나 회수량은 22건 중
4건에 그쳤고, 그중 3건이 한 영상에 몰려 점유율 0.75가 됐다. 더 중요한 것은 적격
후보의 분포상 A와 C가 **처음부터 동시에 만족될 수 없었다**는 점이다. 이 pilot이
보여주지 못한 것은 성능 개선·일반화·M8-v1 판정의 변경 가능성이며, 보여준 것은
"선택된 low-coverage 영역에서 지배적 거부 기전을 결정적으로 복구해도 최소 recall
목표에 필요한 분산된 회수 능력을 확보하지 못한다"는 것뿐이다.

---

## I. Boundaries

```
M8-v1 verdict changed   NO
ROUND 3                 NO
new labels              NO
new GT                  NO
generation              NO
LLM                     NO
GPU                     NO
prompt / parameter 변경   NO
M9                      NO
official test           NO
fresh data              NO
push                    NO
```

동결 산출물(M8-v1 결과 · ROUND1/2 · STEP 0 · M9 문서 · consumed GT)은 수정하지
않았다. STEP 0.5는 새 artifact로만 기록했다.

§22에 따라 확장하지 않았다 — evidence cap 4→5, `evidence_outside_span` 동시 수정,
span 조정, 고재현율 재생성 추가, T2 threshold 교체(`T2@0.8`·`T4@60`), T2 OR T5,
H5/H7 **전부 하지 않는다.** 그것은 STEP 0.5가 아니라 새 가설이다.

통계 해석도 하지 않는다(§24) — CI·p-value·유의성·일반화 없음. count와 결정적
도달량만 보고한다.

---

## J. Tests / git

```
tests   tests/test_m8v2_step05.py 24건 (지침 §20 8항목 + 경계 guard)
전체    2,299 passed · 1 skipped · exit 0
commit  (아래 커밋 참조)
push    NO
```

---

## K. Next action

```
CASE B — NO-GO
  1. M8-v2 미착수
  2. fresh label 확보하지 않음
  3. fresh video 확보 작업도 중단
  4. 결론:
     "selective low-coverage trigger had structural reach, but deterministic
      rejection rescue did not provide sufficient distributed recovery capacity."
  5. 남은 기간을 final report · demo · presentation · closure로 전환
```

M8-v2 후속 feasibility 라인은 여기서 닫는다. STEP 0(GO)과 STEP 0.5(NO-GO)는
consumed panel diagnostic이며 fresh performance evidence로 사용하지 않는다.

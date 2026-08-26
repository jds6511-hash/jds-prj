# M8/M9 방법론 결정 — 승인 기록 (2026-08-26)

이 문서는 **결과를 보기 전에** 고정한 결정이다. 기준 문서이며 결과에 맞춰 고치지 않는다.

```
승인 시점      2026-08-26
승인 기준 커밋  f035073
승인 대상      docs/finalization/M8_M9_PROTOCOL_2026-08-26.md §3-B의 D1~D6
결정 당시 열람  M8 판정 표본의 M8 산출물 0건 (work/ 전수 확인 — report.json은 gwaktube 1편뿐)
              test 결과 열람 없음 · test 지표 계산 없음
```

관련: [M8_M9_PROTOCOL_2026-08-26](M8_M9_PROTOCOL_2026-08-26.md) ·
`docs/preregistration/M8_구조변경_사전등록_2026-08-16.md` ·
`docs/재분석_M8pilot_2026-08-18.md`

---

## D1 — Event Recall 판정 주체: **사람 (HUMAN)**

```
reference 사건 목록   사람이 작성
matching·판정         사람
judge 모델            C2 reference 판정자로 쓰지 않는다
```

근거: `M8_구조변경_사전등록_2026-08-16.md` §4가 "judge를 쓰면 judge 자체를 먼저
검증해야 한다 — M9에서 판정자가 고장나 있던 전례가 있다"고 남겨둔 미결 사항을,
판정자 검증 부담을 지지 않는 쪽으로 닫는다.

절차는 **기존 frozen human-labeling/matching protocol을 우선한다**
(`docs/preregistration/event_inventory_사전등록_2026-08-18.md` · `scripts/event_inventory_kit.py`).
새 규칙을 즉석에서 만들지 않는다. 기존 규약이 덮지 못하는 사항이 나오면 그때 별도
사전등록한다.

## D2 — 판정 표본: **경로 A · fixed_N = 8**

권고했던 경로 B(C2 미집행 명시)는 **기각됐다.** 사유(사용자 판단):

> M8·M9까지 완료해야 프로젝트 완료라고 종료선을 다시 정했으므로, 동결된 M8 완료조건에
> C2가 있는데 C2를 수행하지 않은 채 freeze하면 `M8 COMPLETE`라고 말하기 어렵다.
> 경로 C는 pilot에서 `recall@0.3 = 0.3019`를 이미 본 뒤 C2를 관문에서 내리는 amendment라
> 결과에 반응해 기준을 제거했다는 의심을 피하기 어렵다.

```
N                     8  (고정. 결과를 본 뒤 9~12편 top-up 금지)
selection rule        결과 보기 전에 고정 · 별도 manifest로 동결
reference events      M8 산출물을 보지 않고 작성 (labeler blind)
C2 판정               8편 Event Recall 중앙값
threshold             기존 0.70 유지 (낮추지 않는다)
outcome-based top-up  NO
교체                  사전 정의한 기술적 제외 사유(파일 손상 등)에만 허용
소비 표본             gwaktube · kheritage는 C2 확증에 재사용 금지
pilot 0.3019          참고 관찰. C2 판정에 포함하지 않는다
```

**결과가 0.70 미만이면 그대로 C2 FAIL이다.** 기준을 낮추지 않는다. 그 뒤 dev에서 M8을
개선할지, 실패 상태로 평가를 종료할지는 별도 판단이다.

### D2-1. `M8 evaluation COMPLETE`와 `M8 acceptance PASS`를 분리한다

```
M8 evaluation COMPLETE   8편을 프로토콜대로 끝까지 판정했다
M8 acceptance PASS       C1·C2·C3를 전부 통과했다
```

8편을 끝까지 평가했는데 C2가 0.70 미만이면 **평가는 COMPLETE, acceptance는 FAIL**이다.
그 상태에서 M9를 열 수 있는지는 **기존 설계가 `M8 PASS`를 전제로 하는지 확인한 뒤**
결정한다(미확인 사항 — §미결 참조).

### D2-2. pilot 0.3019 표기 규칙

> 소비된 2개 pilot 영상에서 `recall@IoU≥0.3 = 0.3019`가 관찰되었으나, 해당 영상은 사전
> 선언에 따라 확증 표본으로 재사용하지 않으며 C2 판정에도 포함하지 않는다.

이 값을 근거로 threshold 0.70을 낮추지 않는다. 실무적으로는 **fresh 8편에서 C2 FAIL
가능성이 상당하다는 위험 신호**로만 취급한다. 실패해도 그것이 연구 결과다.

## D3 — M9 groundedness threshold: **절차만 확정, 값은 미정**

값을 지금 정하지 않는다. **dev 분포에 맞춰 optimize하지 않는다** — dev는 threshold를
튜닝하는 데이터가 아니라 "이 threshold가 터무니없는지" sanity check하는 데이터다.

```
1  frozen M8 generator로 dev report 생성
2  실제 judge 실행 (스텁 아님)
3  사람 spot-check로 judge 신뢰성 확인
4  dev 분포 확인
5  사용 목적에 맞는 policy threshold 후보 작성
6  test 개방 전 사용자 승인
7  freeze
```

후보표는 PROTOCOL §4에 있다. **승인 전에는 freeze하지 않는다.**

## D4 — 인용 없는 evaluable 문장: **구조 오류로 통일**

`aar_view` 쪽이 맞다. M8 출력 계약은 "`segments.json` → `[seg#N]` 인용이 붙은 문장
집합"이므로, 인용 없는 factual 문장은 근거성이 낮은 정상 문장이 아니라 **계약 위반**이다.

```
M8 validator          uncited evaluable sentence  →  INVALID
M9 structural precheck uncited evaluable sentence  →  STRUCTURAL FAIL
M9 groundedness        구조 검증을 통과한 claim만 평가
```

**exempt**: evidence claim이 아닌 필드는 스키마에 명시적으로 citation exempt로 둔다
(metadata · title · 명시적 non-evaluable limitation field). 모든 문자열에 인용을 강제하는
것이 아니라 **평가 대상 factual sentence에만 citation mandatory**다.

M9의 현행 "citation 없음 → 자동 ungrounded 점수화"는 freeze 전에 위 의미로 통일한다.

## D5 — taxonomy: **2층 병기, 기존 6분류 유지**

**Layer 1 — 사건 정렬 (동결됨, 그대로 유지)**

```
overmerge · boundary_too_wide · boundary_shift · missed_event · spurious_event · reasonable_match
```

용도: C1·C2·C3 및 사건 구조 평가.

**Layer 2 — claim grounding 진단 (보조 reason code)**

```
unsupported_detail · wrong_object · wrong_action · wrong_entity · temporal_merge
unsupported_causality · citation_mismatch · overgeneralization · insufficient_evidence
```

용도: M9 groundedness에서 **왜 지원되지 않았는지**를 설명한다.

```
groundedness 판정   primary
error reason        secondary diagnostic
```

**Layer 2를 새 metric이나 acceptance criterion으로 만들지 않는다.** 기존 C1~C3 또는 M9
acceptance 지표를 대체하지도, 추가 점수화하지도 않는다.

## D6 — GPU 배치: **GO**

7B 서버 M8 dev 생성을 `PLAN → CANARY → FULL`로 진행한다. 공식 test는 접근하지 않는다.

### 실행 순서 (승인된 순서 그대로)

```
 1  D1·D2·D4·D5를 outcome-blind로 문서에 고정          ← 이 문서
 2  fixed_N=8 selection manifest freeze
 3  사람 reference-event labeling 시작 (M8 output blind)
 4  동시에 기존 dev에서 7B PLAN / CANARY
 5  structural·provenance 문제 없으면 FULL
 6  실제 judge를 dev에 실행
 7  human spot-check로 judge validation
 8  D3 threshold proposal
 9  사용자 승인
10  M8 metric·acceptance spec freeze
11  신규 8편 C1~C3 공식 판정
12  M8 PASS / FAIL 판정
13  scripts/m8_freeze.py
14  M9_READY_FOR_TEST_OPENING
```

**3번과 5번의 분리가 이 순서의 핵심이다.** 라벨러가 M8 report를 먼저 보면 reference
사건 자체가 M8에 끌려간다.

---

## 미결 — 이 문서가 정하지 않은 것

```
D3 값                 dev judge validation 후 후보 제시 → 사용자 승인
N=8 구성              후보 풀이 6편뿐이다(§아래). 2편 추가 확보가 선행한다
M9 개방 전제          "M8 acceptance FAIL이어도 M9를 여는가"는 기존 설계에 없다.
                     D2-1이 두 상태를 분리했으므로 별도 결정 사항이다
공식 M9 test 개방      금지 (별도 승인 사건)
```

### fixed_N=8 후보 풀 현황 (2026-08-26 실측)

`work/` 전수 + `data/queries/queries.jsonl` 대조:

| 영상 | 구간 | 상태 | 적격 |
|---|---|---|---|
| `baekmansonghee_jirisan` | 183 | 질의 없음 · 오염 0 · M8 산출물 없음 | 적격 |
| `softyeon_ceramics` | 192 | 질의 없음 · 오염 0 · M8 산출물 없음 | 적격 |
| `jissi_farm` | 211 | 질의 없음 · **오염 캡션 2건** · M8 산출물 없음 | 조건부 — 정규 `--recaption-corrupted` 선행 |
| `pland_costco_hosting` | 395 | 질의 없음 · 오염 2건 · **케이스 스터디로 내용 상세 노출** | **제외 권고** — 라벨러 blind가 깨진다 |
| `_10_000_…_Wilderness` | 314 | dev 질의 있음 · `reference_status = not_applicable` | 제외 (사전 선언) |
| `gwaktube_soviet_apartment` | 149 | pilot 소비 선언 | 제외 |
| `kheritage_grave_excavation` | 192 | pilot 소비 선언 | 제외 |
| test 4편 | — | test split | 제외 (절대규칙 1) |
| `e2e_*` 4편 | — | 외부 E2E 전용 | 제외 |
| 신규 3편 (2026-08-26 요청) | — | 미취득 | 취득 후 적격 |

```
적격 즉시            2편  (baekmansonghee_jirisan · softyeon_ceramics)
조건부               1편  (jissi_farm — 재캡셔닝 선행)
신규 취득 예정        3편
────────────────────────
확보 가능             6편   →  N=8에 2편 부족
```

**N=8은 고정값이고 결과를 본 뒤 늘리지 않기로 했으므로, 2편은 라벨링 시작 전에
확보해야 한다.** 지금 6편으로 시작한 뒤 나중에 2편을 붙이는 것은 top-up과 구별되지
않는다.

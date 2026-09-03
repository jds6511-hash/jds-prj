# v3 paired 결과 — R0(v2) vs R1(v3) · 같은 41 episode (2026-09-03)

```
primary metric   표현 자격 episode 수 / 41
R0 (v2)          2 / 41        ← 2026-09-03 실측 baseline을 그대로 재현했다
R1 (v3)          39 / 41

mechanism        dialogue grounding 실패로 표현에서 빠진 구간
R0               38
R1               0             ← mechanism closure 성립
```

산출물: `runs/v3_paired/{r0_v2,r1_v3}/` · 지표 JSON `runs/v3_paired/paired_metrics.json`
실행: `scripts/v2_1_v3_paired_run.sh` (한 스크립트에서 두 arm 연속) · commit `f81be81`

## 1. 무엇을 고정했고 무엇만 바꿨는가

```
고정   b1_segments.json  sha256 aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92
      config_server.yaml sha256 bb0d2299aabab800ee71495478cb5df23676152f2b00cd93c78227dd4f32578d
      code_revision f81be81… (두 arm 동일) · Qwen2.5-7B-Instruct · bf16 · llm_4bit false
      do_sample false · max_new_tokens 512 · fixed_window_v1 window_sec 60 → episode 41
      grounding 규칙 · OPEN-12 표현 자격 · presentation builder · A2' 렌더러

바뀐 것 prompt_version  episode_content_v2 → episode_content_v3_summary_only
       prompt_hash     beaa322ea0200d3d… → a08e3c3c4988daa66…
```

입력 해시가 2026-09-03 R0 본 실행과 같다. `held_constant`는 config·code·model 세 항목
모두 true다.

**R0를 보고 v3를 고쳐 R1을 돌리지 않았다.** 합성 게이트 → 계약 freeze(commit) → 한
스크립트에서 R0 → R1 순으로 끝냈다.

## 2. primary

```
                    R0 (v2)      R1 (v3)
표현 자격 episode      2 / 41       39 / 41
highlight AVAILABLE    2            39
highlight NO_RELIABLE  39           2
보고서 크기 (md)        5,640 B      24,681 B
```

R0 paired arm이 이전 본 실행과 **완전히 같은 수를 냈다**(eligible 2, VALID_PARSE 40,
grounding FAIL 38, reason `unsupported_anchor` 329 · `no_support_ref` 12 ·
`no_evidence_at_segment` 8). 즉 이 비교의 대조군은 재현된 것이다.

## 3. mechanism

```
                                  R0      R1
grounding NOT_APPLICABLE           3       41
grounding FAIL_*                  38        0
grounding reason 총건수           349        0
dialogue 때문에 표현에서 빠진 구간   38        0
정본에 남은 dialogue_note           0        0
```

`정본에 남은 dialogue_note`가 R0에서도 0인 것은 v2가 dialogue를 생성하지 않았다는 뜻이
**아니다.** R0는 41건 전부에 dialogue를 생성했고, 실패한 dialogue는 `apply_grounding`이
정본에서 제거한다 — 사라진 것은 문장이 아니라 **표현 자격**이다. 생성 여부는 raw에
남아 있다(R0 raw 41건 보존).

따라서 이 결과가 지지하는 문장은 하나다.

```
The optional-dialogue failure path no longer suppresses otherwise present
canonical summaries.
```

## 4. 보조 지표 — 좋아지지 않은 것도 적는다

```
                          R0            R1
parse VALID_PARSE          40            39
parse CONTRACT_FAILURE      1             2      ← v3에서 1건 늘었다
정본 비어있지 않은 summary   40            39
summary_mode              MODEL_ABSTRACTIVE 41   양쪽 동일 (sparse 0건)
LLM call / failure / retry 41 / 0 / 0    41 / 0 / 0
raw 보존                   41 / 41       41 / 41
episode wall (초)          mean 2.95     mean 1.55   (총 121.0 → 63.6)
VRAM peak (MiB)            15,941        15,799     / 24,564 · OOM 0
```

늘어난 parse 실패 2건의 raw를 직접 봤다.

```
EP35   summary 문자열 중간에서 중국어로 이탈한 뒤 JSON 블록을 두 번 냈다
EP39   summary 문자열 중간에서 중국어로 이탈하고 잘렸다(92 B에서 끝)
```

둘 다 **언어 이탈·절단**이고 계약 형태와 직접 연결되지 않는다. 다만 이 실행에서
v3 쪽이 1건 더 실패한 것은 사실이므로 그대로 적는다. 단일 실행 차이이고, 이것을
"v3가 parse를 악화시킨다"로 일반화할 근거는 없다(41 episode · 1건 차이).

생성 시간이 절반인 것은 출력이 짧아졌기 때문이며, 품질 주장이 아니다.

## 5. 실물 확인 (로컬 한글)

```
                    R0            R1
구조 validator       PASS          PASS
한글 Open()          True          True
PDF export          True          True (134,935 B)
box glyph           ■5 ┌41 │205 └41   양쪽 동일 · 깨짐 0
본문 NO_RELIABLE     39            2
```

## 6. 판정

```
mechanism closure    성립   dialogue 생성 0 · dialogue 기인 표현 제외 0
                          OPEN-12 무변경 · grounding 규칙 무변경 · GRD-004 P1 WAIVED 유지
                          TRI-005 sparse safe mode 무변경(이번 실행에서 해당 0건)
product outcome      2 / 41 → 39 / 41   (H-R2 지지)
```

## 7. 이 결과가 주장하지 않는 것

```
요약이 모두 사실이다            아니다 — summary는 애초에 entailment 검증 대상이 아니다
grounding 문제가 해결됐다       아니다 — 검사 대상 표면을 없앤 것이다
semantic entailment가 해결됐다  아니다 — GRD-004는 P1 WAIVED 그대로다
unsupported content가 줄었다    아니다 — dialogue field 자체가 없으므로 그 실패 표면이 없다
보고서 품질이 좋아졌다           측정하지 않았다 — 이번 건은 mechanism repair다
v3를 기본 계약으로 승격했다      아니다 — 기본값은 여전히 v2다(`--contract v3`로만 선택)
```

```
v2.1 IMPLEMENTATION_COMPLETE = YES   baseline 6e79ac3
M9 HOLD · official test UNOPENED · GRD-004 P1 WAIVED
SUBMISSION_READY                     YES · 제출 arm = R1(v3)
                                     상태 정본: V2_1_SUBMISSION_STATUS_2026-09-03.md
```

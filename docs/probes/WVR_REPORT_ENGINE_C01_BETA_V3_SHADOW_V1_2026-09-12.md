# WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1 — 실행 결과 (2026-09-12)

사전등록: `docs/preregistration/WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1_2026-09-12.md`

```
실행 시 상태   EXECUTED / REVIEW_PENDING
최종 상태      CLOSED / BETA_V3_INTEGRATION_PASS   (2026-09-13 reviewer 판정 — §K)
```

**A~J는 관측값만 적는다. 판정은 §K에만 있다.** 보고서 품질 PASS · production 채택 ·
overlap vs non-overlap 선택 · C02~C05 실행 여부 · M9 실행 여부는 전부 reviewer
결정이다(사전등록 §10).

---

## A. 실행 요약

```
호스트          kixlab2 · RTX 4090 (실행 직전 유휴 40MiB)
격리 클론       /ssd/daeseok/jds-prj-rei-c01  (선행 사건 클론 재사용)
code_git_head   6e64fe3a2c1cdbc7df8d5bd40200219557ed840f
모델            Qwen/Qwen2.5-7B-Instruct · llm_4bit false · do_sample false
cell            b_beta_v3  ·  NONOVERLAP_VIEW × Engine β × contract v3
시작~종료       2026-09-12T14:04:53Z ~ 14:05:15Z   exit 0
새 visual inference 0 · 새 STT 0 · retry 0 · 실행 1회
```

static gate T1~T9 전부 PASS 후 실행했다. preflight(모델 미적재)에서
`n_segments=24 · seg_len=24 · contract=episode_content_v3_summary_only` 확인.

입력은 선행 사건 산출물을 그대로 썼다 — `segments.json` sha256
`53d660c05097e97f8d152e24a231bc1744cc83d91bca84e2ac1157451a1786ae`, 서버 복사본
해시도 동일. **새 adapter 실행 없음.**

---

## B. 측정 결과 (v3-Q1 ~ v3-Q10)

```
v3-Q1  prompt contract   episode_content_v3_summary_only  ← 의도한 계약으로 돌았다
v3-Q2  canonical         canonical 10 / expected 10 · S0~S7 전부 _SUCCESS
                         llm_calls 10 · prompt_refusals 0 · llm_failures 0 · retries 0
                         parse_status VALID_PARSE 10 · content_status VALID_PARSE 10
v3-Q3  grounding         NOT_APPLICABLE 10/10 · reason code 0건
                         (v3에는 dialogue_note가 없어 dialogue grounding 자체가 없다)
v3-Q4  presentation      episodes 10 · eligible 9 · excluded_by_dialogue_grounding 0
v3-Q5  본문              highlight 2개 전부 summary_status = AVAILABLE
                         NO_RELIABLE_CONTENT 0회 · report.md 3200 bytes
                         synthesis source_episode_ids 9개 (EP01~EP09)
                         제외 1건 — EP10 (OUTPUT_LANGUAGE_DRIFT)
v3-Q6  HWPX              생성 O · 5552 bytes · zip open OK · 엔트리 6 ·
                         mimetype 존재 · 손상 엔트리 없음
v3-Q7  section           5/5 존재 (개요 · 주요 사건 및 내용 · 핵심 내용 분석 ·
                         결론 · 근거 및 생성 정보)
v3-Q8  timestamp         H01 0.0–312.0 · H02 312.0–600.0 · 인접 겹침 0.0초
v3-Q9  인용/근거         anchor_cites 24건 · unique 24건 ·
                         존재하지 않는 segment 인용 0건
v3-Q10 fallback          prompt_refusal 0 · llm_failure 0 · retry 0 ·
                         empty report 없음 · 단계 부분 성공 없음
```

---

## C. 선행 사건과의 차이 (같은 입력 · contract만 다름)

```
                              b_beta (v2)          b_beta_v3 (v3)
prompt_version                episode_content_v2   episode_content_v3_summary_only
canonical episodes            10 / 10              10 / 10
grounding                     FAIL_UNSUPPORTED 9   NOT_APPLICABLE 10
                              FAIL_NO_SUPPORT 1
excluded_by_dialogue_grounding 10                  0
presentation eligible         0 / 10               9 / 10
highlight summary_status      NO_RELIABLE_CONTENT  AVAILABLE · AVAILABLE
NO_RELIABLE_CONTENT 출현      4회                  0회
report.md 크기                1061 bytes           3200 bytes
HWPX                          생성 O (4328 bytes)  생성 O (5552 bytes)
```

입력 파일은 **byte 단위로 동일**하다. 달라진 것은 `--contract` 하나뿐이다.

### 대조 (read-only, 판단 없이 병기)

```
runs/v3_paired/r1_v3   eligible 39 / 41 · grounding NOT_APPLICABLE 41
runs/v3_paired/r0_v2   eligible  2 / 41
runs/rei_c01/b_beta    eligible  0 / 10   (v2 contract, 같은 입력)
이번 b_beta_v3         eligible  9 / 10
```

**대조군은 입력 격자와 규모가 다르다**(41 episode 5초 격자 대 10 episode WVR 24초
격자). 수치를 나란히 적되 차이를 단일 원인으로 귀속하지 않는다.

---

## D. 관측된 제외 1건 — EP10 OUTPUT_LANGUAGE_DRIFT

```
episode        EP10  ·  552.0–600.0초  ·  anchor_cites [23]
content_status VALID_PARSE  ·  grounding_status NOT_APPLICABLE
summary        "주인공은今天的身体状况较好，计划外出逛逛光化门市场…"
판정 주체      src/v2_1_output_quality.py REASON_LANGUAGE_DRIFT
렌더 표기      "제외 구간: EP10 (OUTPUT_LANGUAGE_DRIFT)" (src/v2_1_render.py:87)
```

모델이 한국어 요약 대신 중국어 혼용 문장을 냈고, 엔진의 출력 품질 게이트가
그 구간을 요약 출처에서 제외했다. **숨겨진 fallback이 아니라 표시된 제외다** —
report.md·presentation.json 양쪽에 남는다.

이것이 v3 계약 고유의 문제인지, 이 구간(마지막 48초, subtitle 1건)의 문제인지,
모델 일반의 산발적 drift인지는 **이번 1회 실행으로 구분되지 않는다.**

---

## E. 참고 관찰 (gate 아님)

생성된 본문에 STT 오인식이 그대로 실린다.

```
"발화자가 '이생 pierws 시킬 드디어 이생 pierws 시킬 드디어'라고 반복한 후"
```

이는 M3 STT 산출물이 그대로 근거로 쓰인 결과다. semantic quality는 이번 사건의
gate가 아니므로 관찰로만 남긴다.

H02의 시간 표기는 `05:12–10:00`으로, NONOVERLAP 입력대로 H01과 겹치지 않는다.
선행 사건의 OVERLAP cell에서는 같은 자리에서 24초가 겹쳤다.

---

## F. Baseline 보호 확인

```
config.yaml                                72475952bbf56581…   불변
work_full/full_xekZO4n4QuE/segments.json   aa008317023c884a…   불변
runs/v3_paired/submission_manifest.json    073942ee212a5b22…   불변
scripts/v2_1_b2_orchestrate.py · src/v2_1_prompt.py ·
src/v2_1_grounding.py · src/v2_1_render_hwpx.py · src/v2_1_segments.py  불변
```

쓰기는 `runs/rei_c01_beta_v3/` · `work_rei_c01/`에만 일어났다.
선행 사건 산출물 `runs/rei_c01/`은 건드리지 않았다.
official test 미접촉 · M9 미호출 · 새 adapter 실행 없음.

---

## G. 사전등록 대비 편차

```
없음. §3 invocation을 그대로 썼고 --max-new-tokens · --window-sec 는 인자를
주지 않았다(기본값 512 / 60.0). 실행 1회, retry 0.
```

---

## H. 산출물

```
runs/rei_c01_beta_v3/static_gate.json         T1~T9 PASS
runs/rei_c01_beta_v3/measurements.json        본 문서 수치 원본
runs/rei_c01_beta_v3/b_beta_v3/segments.json  입력 사본 (추적 제외 — 원문 포함)
runs/rei_c01_beta_v3/b_beta_v3/b2run/         S0~S7 · raw · run_manifest ·
                                              gpu_poll · S7/report.hwpx · report.md
runs/rei_c01_beta_v3/b_beta_v3/execution_record.json
scripts/rei_c01_beta_v3_gate.py · rei_c01_beta_v3_run.sh · rei_c01_beta_v3_measure.py
tests/test_rei_c01_beta_v3_gate.py
```

---

## I. executor가 결정하지 않은 것

```
보고서 품질 PASS · production 채택 · overlap vs non-overlap 선택
C02~C05 실행 여부 · M9 실행 여부 · v2 재실행 여부
EP10 drift의 원인 귀속
```

---

## J. 상태

```
WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1
EXECUTED / REVIEW_PENDING
```

reviewer가 `BETA_V3_INTEGRATION_PASS` / `_HOLD` / `_INCONCLUSIVE` 중 하나를
결정한다. PASS면 C02~C05 실행 승인 단계로 이동한다.

---

## K. Reviewer 판정 (2026-09-13)

```
WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1
CLOSED / BETA_V3_INTEGRATION_PASS
```

근거로 채택된 관측값:

```
frozen NONOVERLAP input byte-identical      excluded_by_dialogue_grounding 0
β/v3 summary-only contract 정상 적용         presentation eligible 9/10
exit 0 / retry 0                            highlight AVAILABLE
NO_RELIABLE_CONTENT 0                       report body 생성
HWPX 생성 · valid zip                        section 5/5
adjacent highlight overlap 0.0초             baseline / engine source unchanged
official test untouched · M9 not invoked     new visual inference 0 · new STT 0
```

EP10 `OUTPUT_LANGUAGE_DRIFT` 1건은 **integration blocker로 판정하지 않는다** —
quality gate가 탐지했고, 해당 source를 제외했고, exclusion reason이 report에
명시됐기 때문이다.

### 금지된 주장

```
language drift resolved
v3 always produces Korean
EP10 source interval is the cause
```

### 확정된 결론의 범위

```
C01 frozen WVR input → β / v3 summary-only → usable report body → HWPX
```

integration이 성립했다는 것까지다. 그 이상을 이 결과로 주장하지 않는다.

### Production candidate (확정)

```
Video
→ Qwen3-VL broad visual understanding
→ deterministic WVR→report adapter
→ β / v3 summary-only
→ report
→ HWPX

Engine α / m8_report.py  =  citation / traceability R&D asset
```

### 다음 단계 승인

```
NEXT STAGE APPROVED — C02~C05 Qwen3-VL broad visual observation
```

목적은 새 구조 연구가 아니라 **C01에서 검증한 구조를 2424.186485초 전체 source로
확장하는 것**이다. official test · M9는 계속 금지.

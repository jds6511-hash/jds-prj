# WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1 사전등록 (2026-09-12)

승인: reviewer 판정 `WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1
CLOSED / REPORT_ENGINE_INTEGRATION_HOLD` 에서 지시된 **마지막 integration 확인**.

**이 문서는 실행 전에 커밋한다. 결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

선행 문서:
`docs/preregistration/WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1_2026-09-11.md` ·
`docs/probes/WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1_2026-09-11.md` §L ·
`docs/구조결정_M8vNext_2026-09-11.md` §10 errata 4

---

## 0. 이 사건이 답하는 질문

```
C01 frozen WVR input을 **현재 제출 baseline과 같은 contract**(β / v3 summary-only)로
연결했을 때, 비어 있지 않은 보고서 본문과 HWPX가 나오는가.
```

선행 사건은 `--contract`가 동결되지 않아 기본값 v2로 돌았고, 그 결과
eligible 0/10 · 본문 NO_RELIABLE_CONTENT였다. v2 contract에서의 대량 제외는
baseline 자체에서도 관측된다(`runs/v3_paired/r0_v2` eligible 2/41). 따라서 이번
사건은 **production 후보 contract로 같은 입력을 한 번 통과시키는 것**이다.

답하지 않는 질문: overlap vs non-overlap 우열 · α vs β 우열 · 보고서 semantic
품질 PASS · C02~C05 실행 여부 · M9 실행 여부. **전부 reviewer 결정이다.**

---

## 1. 범위 — 1 cell 뿐이다

```
                    NONOVERLAP_VIEW
Engine β / v2.1-B2  contract v3 summary-only      ← 이번 사건의 전부
```

2×2 재실행을 하지 않는다. OVERLAP_VIEW는 이번 사건에 없다.

`NONOVERLAP_VIEW 우선`은 **production adapter의 보수적 기본 선택**이다 —
선행 사건에서 overlap이 highlight span까지 전파됨이 측정됐고(H01 0–336 대 0–312),
같은 시간대를 두 번 먹이는 이점이 아직 없기 때문이다.
**"non-overlap이 semantic하게 더 우수하다"는 판정이 아니며 이 문서는 그것을
주장하지 않는다.**

---

## 2. Frozen input (결과 보기 전 해시 기록)

새 adapter 실행도, 새 inference도 하지 않는다. **선행 사건의 산출물을 그대로
재사용한다.**

```
segments.json   runs/rei_c01/b_beta/segments.json
                53d660c05097e97f8d152e24a231bc1744cc83d91bca84e2ac1157451a1786ae
                24 segment · start == idx*24 · end == (i<23 ? start+24 : 600)
                temporal coverage 600.0초 · duplicate coverage 0.0초
                subtitle populated 23/24 · caption populated 24/24

config          configs/rei_c01_beta.yaml
                d6cf9521e3dfdcd247046ebfe81adc3d476fe0f9321ac691b74d91576914068c

상위 계보       WVR_VIDEO_TO_OVERVIEW_PREVIEW_V2 C01 [0,600) frozen artifact
                + work_full/full_xekZO4n4QuE/segments.json (M3 STT, read-only)
                해시는 선행 사전등록 §2에 동결돼 있다.
```

이 파일을 수정하지 않는다. 재생성하지 않는다.

---

## 3. Engine invocation (동결)

```
python scripts/v2_1_b2_orchestrate.py
  --segments   runs/rei_c01_beta_v3/b_beta_v3/segments.json
  --run-dir    runs/rei_c01_beta_v3/b_beta_v3/b2run
  --config     configs/rei_c01_beta.yaml
  --video-id   rei_c01_nonoverlap
  --run-id     rei-c01-b_beta_v3
  --producer-version 18d9dce            (adapter commit — 선행 사건과 같은 값)
  --model-id   Qwen/Qwen2.5-7B-Instruct
  --contract   v3                        ← 이번 사건의 유일한 변경점
  --poll-gpu --clean
```

`--max-new-tokens`와 `--window-sec`는 **인자를 주지 않는다.** 기본값
512 / `src/v2_1_fixed_window.py:WINDOW_SEC = 60.0` 이며 선행 사건·baseline
v3_paired와 같은 값이다. 결과를 보고 바꾸지 않는다.

**engine source·HWPX renderer·prompt contract를 수정하지 않는다.**
실패하면 그대로 기록한다. **좋은 결과를 얻으려는 retry 금지 — 실행은 1회다.**

---

## 4. Isolation (동결)

```
run root        runs/rei_c01_beta_v3/
cell dir        runs/rei_c01_beta_v3/b_beta_v3/
work root       work_rei_c01/        (config 기존 값, 선행 사건과 동일)
results root    results_rei_c01/
서버 클론       /ssd/daeseok/jds-prj-rei-c01   (선행 사건 클론 재사용)
```

`runs/rei_c01/`(선행 사건 산출물)에 쓰지 않는다. 본 `config.yaml` · 본 `work/` ·
`work_full/` · `runs/v3_paired/` · Track A 인덱스에 쓰지 않는다.

---

## 5. Static gate — 서버 실행 전에 전부 PASS해야 한다

```
T1  입력 segments.json 해시가 §2와 일치
T2  config 해시가 §2와 일치
T3  segment 24개 · idx 연속 0…23 · start == idx*24
T4  duplicate temporal coverage == 0초 · temporal coverage == 600초
T5  subtitle·caption 필드 전 segment 존재
T6  baseline 경로 해시 불변 (config.yaml · work_full · runs/v3_paired)
T7  engine source 해시 불변 (v2_1_b2_orchestrate · v2_1_prompt · v2_1_grounding ·
                             v2_1_render_hwpx · v2_1_segments)
T8  resolve_contract("v3") 가 PROMPT_VERSION_V3 를 돌려준다
    (알 수 없는 이름이 조용히 v2로 떨어지지 않음을 확인)
T9  official test 경로 미접근 · M9 미호출
```

하나라도 실패하면 **서버 실행을 하지 않고 STOP.**

---

## 6. 측정 항목 (판정하지 않는다)

```
v3-Q1  prompt contract 적용   run_manifest.fingerprint.prompt_version 이
                             episode_content_v3_summary_only 인가
v3-Q2  canonical 생성        canonical_episodes / expected · llm_calls ·
                             prompt_refusals · llm_failures · retries · parse_status
v3-Q3  grounding 분포        grounding_status 분포 (v3에서는 NOT_APPLICABLE 기대
                             — 기대일 뿐 gate가 아니다)
v3-Q4  presentation          episodes · eligible · excluded_by_dialogue_grounding
                             · 제외 사유
v3-Q5  본문 존재 여부        highlight summary_status 분포 ·
                             NO_RELIABLE_CONTENT 출현 횟수 ·
                             synthesis source_episode_ids
v3-Q6  HWPX                  생성 여부 · zip open · 엔트리 수 · mimetype ·
                             손상 엔트리 · 바이트 수
v3-Q7  section completion    report.md 5개 섹션 존재 여부
v3-Q8  timestamp             highlight start/end · 인접 highlight 겹침 초
v3-Q9  인용/근거             anchor_cites 수 · unique · 존재하지 않는 segment 인용 수
v3-Q10 fallback              §7 목록의 발생 여부
```

### 대조로 병기할 기존 수치 (read-only, 판단 없이)

```
runs/v3_paired/r1_v3     eligible 39 / 41 · grounding NOT_APPLICABLE 41
runs/v3_paired/r0_v2     eligible  2 / 41
runs/rei_c01/b_beta      eligible  0 / 10 (선행 사건, v2 contract)
```

**대조군은 입력도 규모도 다르다**(41 episode 원본 5초 격자 대 10 episode
WVR 24초 격자). 수치를 나란히 적되 차이를 단일 원인으로 귀속하지 않는다.

---

## 7. No silent fallback

발생하면 반드시 기록한다.

```
empty report · concat fallback · missing section fallback · citation stripping
parse recovery · retry · prompt refusal · 단계 부분 성공
```

기술적 실패는 실패로 적는다.

---

## 8. 금지 (재확인)

```
새 Qwen3-VL visual inference · C02~C05 visual inference · 새 STT
새 adapter 실행 · 입력 segments.json 재생성 · OVERLAP_VIEW 실행
v2 contract 재실행 · Track A index/caption 재생성 · official test 접촉 · M9 실행
engine source · prompt contract · HWPX renderer 수정
결과를 보고 contract·window·token 상한 변경
결과가 나쁘다는 이유의 retry · 결과가 좋다는 이유의 production 승격
```

---

## 9. 필수 산출물

```
runs/rei_c01_beta_v3/b_beta_v3/segments.json          (§2 입력 사본)
runs/rei_c01_beta_v3/b_beta_v3/b2run/                 S0~S7 · raw · run_manifest ·
                                                      gpu_poll · S7/report.hwpx · report.md
runs/rei_c01_beta_v3/b_beta_v3/execution_record.json
runs/rei_c01_beta_v3/static_gate.json
runs/rei_c01_beta_v3/measurements.json
docs/probes/WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1_2026-09-12.md
```

자막·캡션 원문을 담는 파일(`segments.json` · `b2run/raw/` · `run.log`)은
publication safety 규칙대로 추적하지 않는다 — 해시와 계측값만 추적한다.

---

## 10. executor가 결정하지 않는 것

```
보고서 품질 PASS · production 채택 · overlap vs non-overlap 선택
C02~C05 실행 여부 · M9 실행 여부 · v2 재실행 여부
```

executor 보고 상태는 다음까지만이다.

```
WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1
EXECUTED / REVIEW_PENDING
```

reviewer가 이후 다음 중 하나를 결정한다.

```
BETA_V3_INTEGRATION_PASS        → C02~C05 실행 승인 단계로 이동
BETA_V3_INTEGRATION_HOLD
BETA_V3_INTEGRATION_INCONCLUSIVE
```

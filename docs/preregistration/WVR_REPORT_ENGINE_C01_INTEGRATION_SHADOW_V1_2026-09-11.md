# WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1 사전등록 (2026-09-11)

승인: 리뷰어 결정 — `APPROVED / ENGINE α+β · SERVER TEXT-GENERATION 포함`.
**이 문서는 실행 전에 커밋한다. 결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

선행 문서: `docs/구조결정_M8vNext_2026-09-11.md` (errata 1·2·3) ·
`docs/작업현황_2026-09-11.md`

기존 명칭 `WVR_M8VNEXT_C01_INTEGRATION_SHADOW_V1`은 `ENGINE_IDENTITY_AMBIGUOUS
CONFIRMED` 판정으로 본 명칭으로 확장됐다. 초안·승인 기록은 provenance로 남는다.

---

## 0. 이 사건이 답하는 질문

```
C02~C05 GPU visual inference 전에,
기존 C01 frozen WVR artifact만으로
WVR broad visual understanding을 기존 보고서 엔진의 입력으로 연결했을 때
각 엔진에서 기술적으로 성립하는가.
```

답하지 않는 질문: 어느 엔진이 더 나은가 · 보고서 품질이 좋은가 ·
최종 production engine이 무엇인가. **이것들은 전부 reviewer 결정이다.**

---

## 1. 2×2 characterization

```
                        OVERLAP_VIEW      NONOVERLAP_VIEW
Engine α / m8_report         Aα                 Bα
Engine β / v2.1-B2           Aβ                 Bβ
```

winner selection이 아니다. 각 조합의 integration behavior를 측정한다.

---

## 2. Frozen source (결과 보기 전 해시 기록)

```
Visual — C01 [0,600) · WVR_VIDEO_TO_OVERVIEW_PREVIEW_V2
  video_overview_v2_segment_summaries.json
    35c964e30c35d05957b717fd24aba3225ec2082c50addcebed61c081fc217edc
  video_overview_v2_segments.json
    b4dac6ce532f1a37bf31392fe14f7b557b2b9e3b786dbcd8d84d765f2068bef0
  video_overview_v2_record.json
    da4d1fd9996c61739e74881fe5cb3b43d3d3455c2bc6cf85172aae24dba21113

STT — M3 파생 5초 구간 (read-only)
  work_full/full_xekZO4n4QuE/segments.json
    aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92
    485구간 · subtitle 296/485 · caption 485/485
    ※ 이 해시는 runs/v3_paired/submission_manifest.json 의
       input.segments_sha256 과 동일하다 — 제출 baseline 입력 본체다.
       읽기만 한다. 이 경로에 쓰지 않는다.

video sha256  ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
```

새 inference로 재생성하지 않는다.

---

## 3. Adapter geometry (동결)

WVR 관측 기하: `window 48초 · stride 24초 · 창 24개 · 범위 [0,600)`
창 `S01…S24` → adapter idx `0…23` (오름차순 1:1, 재정렬 금지).

### 3-1. OVERLAP_VIEW (Arm A) — WVR native geometry 보존

```
idx    i                      i = 0 … 23
start  i * 24                 0, 24, 48, …, 552
end    min(start + 48, 600)   48, 72, …, 576, 600
```

인접 adapter segment는 24초를 공유한다. **그 중복 자체가 characterization 대상이다.**

### 3-2. NONOVERLAP_VIEW (Arm B) — 중복 제거, 새 inference 없음

동일 frozen summary를 쓴다. 시간 구간만 stride 폭으로 좁힌다.

```
idx    i                      i = 0 … 23
start  i * 24                 0, 24, …, 552
end    (i < 23) ? start + 24 : 600
```

즉 `[0,24) [24,48) … [528,552) [552,600)`.

```
duplicate temporal coverage  0초
총 커버리지                   [0,600) 빈틈 없음
segment 수                    24 (Arm A와 동일)
창↔segment 대응               1:1 동일 (S(i+1) → idx i)
caption 텍스트                Arm A와 동일 — 시간 구간만 다르다
```

**두 arm의 semantic source는 동일하다.** engine마다 유리하게 다시 쓰지 않는다.

두 view 모두 `start == idx * 24`를 만족한다 → Engine α의 `seg_len_sec: 24`
config 사본에서 `common.load_segments` 불변식을 통과한다.

---

## 4. Caption source rule (동결)

각 adapter segment의 `caption`은 대응 창의 **broad visual summary**로만 만든다.
Local Event 전체 목록을 다시 넣지 않는다.

```
source     video_overview_v2_segment_summaries.json 의 해당 segment_id 항목
사용 필드   BROAD_ACTIVITY · OBSERVED_CHANGE          (이 순서)
제외 필드   CONTEXT_INFERENCE · UNCERTAINTY
           → V2가 Overview 합성에서 제외한 계층이므로 adapter도 넣지 않는다
직렬화     BROAD_ACTIVITY 항목을 " · " 로 결합
           OBSERVED_CHANGE 가 비어 있지 않으면 " / 변화: " + " · "결합 을 덧붙인다
           양쪽 모두 비면 caption = "(관측 요약 없음)"
원문 수정   금지 — 요약 문자열을 재작성·요약·번역하지 않는다
```

### lineage (필수 보존)

```
WVR window(segment_id, start_sec, end_sec)
  → broad visual summary (BROAD_ACTIVITY / OBSERVED_CHANGE 원본 리스트)
    → adapter segment(idx, start, end, caption)
      → engine input
```

adapter manifest에 창별로 위 4단계를 전부 기록한다.

---

## 5. Subtitle rule (동결)

새 Whisper 실행 금지. 기존 M3 STT를 deterministic하게 재집계한다.

### boundary inclusion rule

adapter segment 구간 `[s, e)` 에 대해, `work_full` 5초 구간 `j = [sj, ej)` 를

```
포함 조건   min(ej, e) - max(sj, s) > 0        (양의 겹침 · 접점 제외)
정렬        sj 오름차순 (원본 idx 순)
결합        strip 후 빈 문자열 제외, 단일 공백 " " 으로 join
없으면      subtitle = ""                       (빈 문자열 허용)
```

경계 접점(`ej == s` 또는 `sj == e`)은 **포함하지 않는다.**
5초 격자와 24초 경계가 어긋나는 구간(예: `[20,25)` vs `[24,48)`)은 양의 겹침이 있으므로
**포함되며, Arm A·B 모두에서 인접 segment에 중복 등장할 수 있다** — 의도된 동작이고
계측 대상이다.

원문 자막 텍스트를 수정·정규화·요약하지 않는다.

---

## 6. Engine invocation (동결)

### Engine α

```
python src/m8_report.py --config <config 사본> --video-id <cell video_id>
입력   <work>/<video_id>/segments.json
출력   <work>/<video_id>/report.json
config seg_len_sec: 24 · report_model: Qwen/Qwen2.5-7B-Instruct · llm_4bit: false
```

### Engine β

```
python scripts/v2_1_b2_orchestrate.py
  --segments <adapter segments.json> --run-dir <cell run dir>
  --config <config 사본> --video-id <cell video_id> --run-id <cell run id>
  --producer-version <기록> --model-id Qwen/Qwen2.5-7B-Instruct
출력   canonical / highlights / synthesis / HWPX
```

**두 엔진의 source code를 수정하지 않는다.** HWPX renderer도 수정하지 않는다.
실패하면 그대로 기록한다. 좋은 결과를 얻으려는 retry 금지.

### 실행 순서 (동결)

```
1. Aα   2. Bα   3. Aβ   4. Bβ
```

---

## 7. Isolation (동결)

```
config 사본        configs/rei_c01_alpha.yaml · configs/rei_c01_beta.yaml
work root          work_rei_c01/
results root       results_rei_c01/
cell video_id      rei_c01_overlap · rei_c01_nonoverlap
run dir            runs/rei_c01/{a_alpha,b_alpha,a_beta,b_beta}/
```

본 `config.yaml` · 본 `work/` · `work_full/` · `runs/v3_paired/` · Track A 인덱스에
**쓰지 않는다.**

---

## 8. Static gate — 서버 generation 전에 전부 PASS해야 한다

```
S1  frozen source 4개 해시가 §2와 일치
S2  adapter 결정성 — 2회 실행 산출물 byte 동일
S3  lineage 완전 — 24창 전부 4단계 기록
S4  idx 연속 0…23 · start == idx*24 (두 view 모두)
S5  Arm A end == min(start+48,600) · Arm B end == (i<23 ? start+24 : 600)
S6  Arm B duplicate temporal coverage == 0초
S7  subtitle/caption 필드 전 segment 존재
S8  subtitle 재집계 결정성 — 2회 실행 동일
S9  isolated work/results 경로만 사용
S10 baseline 경로 해시 불변 (work_full · runs/v3_paired · config.yaml)
S11 engine source 해시 불변 (m8_report.py · v2_1_* · HWPX renderer)
S12 official test 경로 미접근 · M9 미호출
```

하나라도 실패하면 **서버 text generation을 하지 않고 STOP.**

### negative check (RED가 나와야 정상)

```
subtitle 필드 제거 → RED    idx 불연속 → RED    start 불변식 위반 → RED
lineage 누락 → RED          baseline 경로 쓰기 시도 → RED
official-test 경로 접근 → RED
```

---

## 9. 측정 항목

### Engine α

```
α-Q1 loader/schema compatibility      α-Q2 report.json completion
α-Q3 map/reduce completion            α-Q4 [seg#N] citation behavior
α-Q5 overlap duplication behavior     α-Q6 subtitle integration
```

HWPX completion을 α의 gate로 요구하지 않는다 — α에 HWPX path가 없다.

### Engine β

```
β-Q1 segments input compatibility     β-Q2 canonical generation completion
β-Q3 highlights/synthesis completion  β-Q4 HWPX generation completion
β-Q5 timestamp/display behavior       β-Q6 overlap duplication behavior
β-Q7 subtitle integration
```

### citation semantics는 엔진별로 분리해 감사한다

```
α   [seg#N]의 source/time meaning
β   β가 실제로 쓰는 canonical/evidence/time representation
    → β에 없는 [seg#N] 계약을 억지로 요구하지 않는다
```

### 공통 비교 지표

```
segment count · temporal coverage · duplicate temporal coverage
subtitle populated count · caption populated count
generation completion · fallback usage
citation count · unique citation count · citation time ranges
section completion · HWPX generated · HWPX open/structural validation
```

semantic quality는 **참고 관찰만 기록**하고 gate로 만들지 않는다.

---

## 10. No silent fallback

engine에서 fallback이 발생하면 반드시 기록한다.

```
empty report · concat fallback · missing section fallback
citation stripping · parse recovery · retry 발생
```

숨기지 않는다. 기술적 실패는 실패로 적는다.

---

## 11. 금지 (재확인)

```
새 Qwen3-VL visual inference · C02~C05 visual inference · 새 STT
Track A index/caption 재생성 · official test 접촉 · M9 실행
engine source 수정 · HWPX renderer 수정
결과를 보고 adapter rule 변경 · 좋은 arm 선택 후 production 승격
Overview/Analysis/Conclusion prompt 튜닝 · event/chapter 연구 재개
```

---

## 12. 필수 산출물

```
runs/rei_c01/adapter_manifest.json
runs/rei_c01/{a_alpha,b_alpha}/segments.json · report.json · execution_record.json
runs/rei_c01/{a_beta,b_beta}/segments.json · canonical·중간 artifact · HWPX · execution_record.json
runs/rei_c01/static_gate.json
runs/rei_c01/integration_matrix.json
docs/probes/WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1_2026-09-11.md
```

---

## 13. executor가 결정하지 않는 것

```
최종 production engine · α vs β winner · 최종 report quality PASS
C02~C05 실행 여부 · M9 실행 여부
```

executor 보고 상태는 다음까지만이다.

```
WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1
EXECUTED / REVIEW_PENDING
```

reviewer가 이후 다음 중 하나를 결정한다.

```
REPORT_ENGINE_INTEGRATION_PASS
REPORT_ENGINE_INTEGRATION_HOLD
REPORT_ENGINE_INTEGRATION_INCONCLUSIVE
```

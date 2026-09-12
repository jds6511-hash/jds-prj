# WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1 사전등록 (2026-09-13)

승인: reviewer 판정 `WVR_CHUNK_OVERVIEW_V2_C02_C05 CLOSED / CHUNK_EXPANSION_PASS`
의 `NEXT STAGE APPROVED`.

**이 문서는 실행 전에 커밋한다. 결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**
특히 **중복 제거 규칙은 synthesis 전에 동결한다**(reviewer §3).

선행 문서:
`docs/probes/WVR_CHUNK_OVERVIEW_V2_C02_C05_2026-09-13.md` §N ·
`docs/preregistration/WVR_CHUNK_OVERVIEW_V2_C02_C05_2026-09-13.md` ·
`docs/preregistration/WHOLE_VIDEO_REPORT_LIGHT_V1_2026-09-08.md` §5

---

## 0. 이 사건이 답하는 질문

```
frozen C01~C05 WVR observation만으로 중복 없는 whole-video temporal
representation을 만들고, 2424초 전체 Overview를 생성할 수 있는가.
```

**새 Qwen3-VL visual inference를 하지 않는다.** 새 STT도 하지 않는다.

답하지 않는 질문: Overview 품질 PASS · 어느 chunk 관찰이 더 나은가 ·
semantic completeness. 전부 reviewer 결정이다.

---

## 1. Input (read-only)

```
C01   runs/wvr_video_overview_preview_v2/
      video_overview_v2_segment_summaries.json
        35c964e30c35d05957b717fd24aba3225ec2082c50addcebed61c081fc217edc
      video_overview_v2_segments.json
        b4dac6ce532f1a37bf31392fe14f7b557b2b9e3b786dbcd8d84d765f2068bef0

C02   runs/wvr_chunk_overview_v2/C02/
      summaries a91eb783b07b97d3781f99e9d3365404d69291842c340104c535db5f1642c4d0
      segments  2a82080e3d3da802033fee228e40a3493c2630b6abb0e9bc510eb4d5e1f20947

C03   summaries cc0a0ebaf906987ee4ebffb1983e97b6297cb4cee21d31bd4768fbbc753f6569
      segments  6bc7380319fb62612f85e2a5e7183b82bec6e9970a7e4b38abbd152ed2697927

C04   summaries 06f3a17c95716da3418d59a879a3eae0dccc3d38bd0edc3c4bec6b12297ec8f3
      segments  3bdb9e584fbbca7ef85fd0fa80dd61213fc587e62936244eef8ba837ed89828e

C05   summaries d6e74b0652028d99165ade269bd5f3d2de9891163cf9f1ed5e288f2d9201e9b4
      segments  5f1f4c7b7a53f0858be9618ea2adb12a1aefd78c8a867bf47bb247a1237059d6
```

**C01~C05 재실행 금지. 이 경로에 쓰지 않는다.**

---

## 2. Merge source

chunk-level final prose summary(`video_overview_v2_result.json`의 overview)를
**단순 concat하지 않는다.** 우선 source는 각 chunk의 window-level
`BROAD_ACTIVITY` 관찰이다.

각 관찰을 원본 영상 absolute timestamp로 정규화한다. window의 `start_sec` ·
`end_sec`는 이미 절대 시각이다(chunk plan이 절대 좌표로 창을 깔았다) —
**추가 오프셋을 더하지 않는다.** 이 사실을 gate G2가 검증한다.

---

## 3. 중복 제거 규칙 (동결 · synthesis 전)

두 층의 중복을 각각 결정적으로 제거한다. **결과를 보고 바꾸지 않는다.**

### 3-1. window overlap (chunk 내부) — NONOVERLAP 정규화

chunk 안의 창은 48초 · stride 24초이므로 인접 창이 24초를 공유한다.
window `i`(0-based, chunk 내 창 수 `n`)의 timeline 구간을 이렇게 정한다.

```
i < n-1     [s_i, s_{i+1})            = [s_i, s_i + 24)
i == n-1    [s_i, e_i)                = 마지막 창의 관찰 끝 시각
```

즉 각 창은 자기 stride만 대표하고, 마지막 창만 자기 관찰 구간 끝까지 대표한다.
이는 `rei_c01_adapter`의 NONOVERLAP_VIEW와 같은 규칙이다.

**NONOVERLAP을 semantic winner selection으로 해석하지 않는다.** duplicated
temporal exposure를 제거하기 위한 report-input normalization이다(reviewer §4).

### 3-2. chunk overlap (인접 chunk 120초) — 낮은 index chunk가 소유한다

```
절대 시각 t의 소유 chunk = t를 포함하는 chunk 중 index가 가장 낮은 것
```

결과적으로 소유 구간은 다음과 같다.

```
C01  [0, 600)        C02  [600, 1080)     C03  [1080, 1560)
C04  [1560, 2040)    C05  [2040, 2424)
```

**내용을 보고 고르지 않는다** — index만 본다. 이 규칙은 관찰 텍스트와 무관하다.

경계 정렬(실행 전 산술 확인): 각 chunk의 창 시작은 `chunk_start + 24k`이고
chunk stride는 480초 = 24 × 20이므로, 소유 경계(600 · 1080 · 1560 · 2040)는
전부 해당 chunk의 창 경계와 정확히 일치한다. 따라서 **구간을 잘라내는 일이
없다** — 소유 밖 구간은 통째로 버려진다.

### 3-3. terminal remainder

```
[2424, 2424.186485)   0.186485초
```

관찰된 창이 없다. **별도 known remainder로 기록하고 timeline entry를 만들지
않는다.** 새 visual inference 사건으로 만들지 않는다(reviewer 판정 §N).

---

## 4. 산출 artifact (synthesis 전에 만들고 검증한다)

```
runs/wvr_whole_video_merge_v1/whole_video_activity_timeline.json
runs/wvr_whole_video_merge_v1/whole_video_activity_timeline.md
runs/wvr_whole_video_merge_v1/timeline_lineage.json
runs/wvr_whole_video_merge_v1/merge_gate.json
```

timeline entry가 보존할 최소 필드:

```
entry_index                 0부터 연속
start_sec · end_sec         절대 시각 (반열린 구간)
broad_activity              해당 창의 BROAD_ACTIVITY label 리스트 (원문 그대로)
source_chunk                C01 … C05
source_window               segment_id (S01 …) + 창의 원래 [start_sec, end_sec)
source_artifact_sha256      그 chunk의 summaries · segments 해시
```

`[0, 2424)` 안의 모든 시각이 정확히 하나의 entry로 추적 가능해야 한다.

**원문 label을 재작성·요약·번역하지 않는다.**

---

## 5. Whole-video synthesis (timeline 검증 후 1회)

gate G1~G10이 전부 PASS한 뒤에만 text synthesis를 **1회** 수행한다.

```
모델        Qwen/Qwen3-VL-8B-Instruct  revision 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
호출        runtime.synthesize(prompt)   — 텍스트 전용 호출, 영상 프레임 없음
프롬프트    wvr_video_overview_preview_v2.synthesis_prompt() 그대로
            (SHORT OVERVIEW / DETAILED OVERVIEW 두 heading · 새 프롬프트 작성 금지)
압축        wvr_video_overview_preview_v2.compress_activity_timeline() 그대로
파싱        wvr_video_overview_preview_v2.parse_overview() 그대로
생성 파라미터  do_sample False · num_beams 1 · max_new_tokens 1024
```

**새 visual prompt를 만들지 않는다. 새 sampling을 하지 않는다.**
synthesis 입력은 §4 timeline을 압축한 BROAD_ACTIVITY 시퀀스뿐이다.

Overview 질문은 "영상 전체에서 어떤 활동 흐름이 나타나는가?"에 집중한다 —
V2 synthesis 프롬프트가 이미 그 질문이고 세부 event log 나열을 금지한다.

`retry 금지.` 실패하면 실패로 기록한다.

---

## 6. Context / uncertainty 보충 금지

source의 `CONTEXT_INFERENCE` · `UNCERTAINTY` · `OBSERVED_CHANGE`가 전부 비어 있다.
**synthesis model이 이를 임의로 보충하게 만들지 않는다.**

```
보이지 않은 맥락을 추가하지 않는다.
예: 병원 퇴원 · 직장 시간 · 휴가 · 시장 방문 계획
```

V2 synthesis 프롬프트가 이미 "사람의 상황, 일정, 직업, 의료 정보, 계획, 감정,
의도를 추론하지 마십시오"를 규칙으로 갖고 있다 — 그대로 쓰고 고치지 않는다.
빈 `OBSERVED_CHANGE`는 빈 채로 넘긴다.

---

## 7. 금지 (재확인)

```
새 Qwen3-VL visual inference · 새 STT · C01~C05 rerun
Event Map 재개 · Semantic Chapter · Boundary Candidate · 새 stitching 연구
새 visual prompt · 새 visual sampling · synthesis 프롬프트 수정
chunk-level prose summary 단순 concat
결과를 보고 중복 제거 규칙 변경 · 좋은 결과를 위한 retry
official test 접촉 · M9 실행
executor의 Overview 품질 PASS 선언
```

---

## 8. Gate (synthesis 전에 전부 PASS해야 한다)

```
G1   C01~C05 source 해시가 §1과 일치 (unchanged)
G2   absolute time 변환 유효 — entry 시각이 source 창 시각에서 파생되고
     source 창 범위를 벗어나지 않는다
G3   duplicate source-time exposure 제거 — entry 간 겹침 0초
G4   [0, 2424) temporal coverage — 빈틈 0 · union == 2424.0
G5   source lineage 완전 — 모든 entry가 chunk·window·artifact 해시를 갖는다
G6   deterministic merge — 2회 실행 산출물 byte 동일
G7   no visual inference — merge 단계 inference 0
G8   no STT inference — 0
G9   official test 경로 미접근
G10  M9 미호출
```

하나라도 실패하면 **synthesis를 하지 않고 STOP.**

---

## 9. 보고 항목

```
timeline entry count
temporal coverage
duplicate coverage before normalization
duplicate coverage after normalization
source lineage completeness
SHORT_OVERVIEW · DETAILED_OVERVIEW
synthesis inference count · retry count
```

---

## 10. executor가 결정하지 않는 것

```
Overview 품질 PASS · semantic completeness · chunk 관찰 우열
다음 단계(Analysis / Conclusion / β-v3 report / HWPX) 진행 여부
M9 실행 여부 · official test 개방 여부
```

executor 보고 상태는 다음까지만이다.

```
WVR_WHOLE_VIDEO_TEMPORAL_MERGE_OVERVIEW_V1
EXECUTED / REVIEW_PENDING
```

그리고 STOP한다.

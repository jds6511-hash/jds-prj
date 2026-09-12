# WVR_CHUNK_OVERVIEW_V2 — C02~C05 사전등록 (2026-09-13)

승인: reviewer 판정 `WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1
CLOSED / BETA_V3_INTEGRATION_PASS` 의 `NEXT STAGE APPROVED`.

**이 문서는 실행 전에 커밋한다. 결과를 본 뒤 아래 어떤 항목도 바꾸지 않는다.**

선행 문서:
`docs/probes/WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1_2026-09-12.md` §K ·
`docs/preregistration/WHOLE_VIDEO_REPORT_LIGHT_V1_2026-09-08.md` §5~§7 ·
`docs/구조결정_M8vNext_2026-09-11.md` §10 errata 4

---

## 0. 이 사건이 답하는 질문

```
C01에서 검증한 관찰 구조를 나머지 chunk(C02~C05)에 그대로 적용했을 때
2424.186485초 전체 source에 대한 chunk-level broad summary가 확보되는가.
```

**새 구조 연구가 아니다.** 답하지 않는 질문: 어느 chunk가 더 좋은가 ·
관찰 품질 PASS · chunk별 프롬프트 개선 · 최종 Overview 품질.
전부 reviewer 결정이거나 이 사건의 범위 밖이다.

---

## 1. 동결 유지 대상 (reviewer 지정)

```
Qwen3-VL model / revision         Qwen/Qwen3-VL-8B-Instruct
                                  0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
visual observation prompt/schema  wvr_video_overview_preview_v2 그대로
window / stride semantics         48초 창 · 24초 stride · 0.5fps · 창당 24프레임
broad visual summary contract     BROAD_ACTIVITY / OBSERVED_CHANGE /
                                  CONTEXT_INFERENCE / UNCERTAINTY
adapter semantics                 rei_c01_adapter 규칙 (이번 사건에서 실행하지 않음)
β/v3 summary-only production target
NONOVERLAP report-input 원칙
```

새 chapter · event-map · boundary 연구를 **재개하지 않는다.**

**이번 사건에서 바뀌는 것은 시간 범위 하나뿐이다.**

### 증거 — 확장 코드가 C01 계획을 그대로 재현한다

```
wvr_chunk_overview_v2.segments("C01")
  == runs/wvr_video_overview_preview_v2/video_overview_v2_segments.json
  (테스트 test_wvr_cov_05, 실행 전 통과 확인)
```

`wvr_video_overview_preview_v2_run.run`에는 `plan=None` 기본값을 가진 선택 인자만
추가했다. plan을 주지 않으면 **C01 동작은 문자 그대로 이전과 같다.**

---

## 2. Frozen source

```
video        data/videos/full_xekZO4n4QuE.mp4
             sha256 ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
             duration 2424.186485초 · 1920×1080 · 30fps
chunk plan   wvr_contract.chunk_plan(2424.186485)  — 유일한 출처
```

```
C01   0.0    – 600.0        (선행 산출물 사용 · 이번 사건에서 재실행하지 않는다)
C02   480.0  – 1080.0
C03   960.0  – 1560.0
C04   1440.0 – 2040.0
C05   1920.0 – 2424.186
chunk 600 / overlap 120 / stride 480
```

C01 산출물: `runs/wvr_video_overview_preview_v2/` (WVR_VIDEO_TO_OVERVIEW_PREVIEW_V2,
`GENERATED / REVIEW_REQUESTED`). **읽기만 한다.**

---

## 3. 창 기하 (동결 · 결과 보기 전 기록)

각 chunk 안에서 chunk start부터 48초 창 · 24초 stride로 tile한다.

```
chunk   범위                창 수   첫 창              마지막 창          덮이지 않은 꼬리
C02     480.0 – 1080.0      24     [480, 528)         [1032, 1080)       0.0초
C03     960.0 – 1560.0      24     [960, 1008)        [1512, 1560)       0.0초
C04     1440.0 – 2040.0     24     [1440, 1488)       [1992, 2040)       0.0초
C05     1920.0 – 2424.186   20     [1920, 1968)       [2376, 2424)       0.186초
```

총 창 수 `24+24+24+20 = 92`. 프레임 `92 × 24 = 2,208`.
추론 횟수 = 창 92 + chunk 합성 4 = **96회**.

### C05 꼬리 규칙 (동결)

chunk 끝에 48초가 안 남으면 **그 꼬리는 창을 만들지 않는다.** 창 길이를 줄여
다른 창과 비교 불가능한 관찰을 만들지 않기 위해서다. C05의 덮이지 않은 꼬리는
0.186초이고 이는 0.5fps 표집 간격(2.0초)보다 짧아 **표집되는 프레임이 없다.**
이 값은 산출물에 `uncovered_tail_sec`으로 기록한다.

**결과를 보고 이 규칙을 바꾸지 않는다.**

---

## 4. 실행 (동결)

```
python scripts/wvr_chunk_overview_v2_run.py --chunk <CHUNK>
  video      data/videos/full_xekZO4n4QuE.mp4
  runs root  runs/wvr_chunk_overview_v2/<CHUNK>/
  생성 파라미터  do_sample False · num_beams 1 · max_new_tokens 1024
                (wvr_video_overview_preview_v2 상수 그대로)
  runtime 검증  bfloat16 · sdpa · RTX 4090 — 불일치 시 RUNTIME_MISMATCH로 거부
```

### 실행 순서 (동결)

```
0. canary   C02 --plan-only        GPU 미사용 · 창 계획·기하만 확인
1. canary   C02 본 실행            1 chunk · 검증 후에만 다음으로 간다
2.          C03
3.          C04
4.          C05
```

canary 검증 항목(§6 gate)이 하나라도 실패하면 **C03 이후를 실행하지 않고 STOP.**

**좋은 결과를 얻으려는 retry 금지.** 실패하면 실패로 기록한다.
V2 runner의 `--resume`은 **pre-synthesis 실패 실행을 이어붙이는 경우에만**
허용되며(해시·프롬프트 일치 검사를 통과해야 한다), 재시도 횟수를 산출물에 적는다.

---

## 5. Isolation (동결)

```
쓰기 허용   runs/wvr_chunk_overview_v2/<CHUNK>/
쓰기 금지   runs/wvr_video_overview_preview_v2/   (C01 frozen)
            runs/rei_c01/ · runs/rei_c01_beta_v3/ · runs/v3_paired/
            work/ · work_full/ · config.yaml · Track A 인덱스
```

---

## 6. Gate — canary(C02) 후 확인하고, 각 chunk마다 다시 확인한다

```
G1  record.status == "GENERATED / REVIEW_REQUESTED"
G2  segment_count == §3의 창 수 · segment_inference_count == 창 수
G3  inference_count == 창 수 + 1 (chunk 합성 1회)
G4  runtime_provenance: model_id·revision이 §1과 일치 · bfloat16 · sdpa · 4090
G5  segment_summaries 개수 == 창 수 · 전부 4개 필드(BROAD_ACTIVITY /
    OBSERVED_CHANGE / CONTEXT_INFERENCE / UNCERTAINTY) 보유
G6  BROAD_ACTIVITY label이 전부 동결 label 집합 안에 있다
G7  창 시각이 §3 표와 일치 (첫 창·마지막 창·창 수)
G8  video_sha256 == §2
G9  C01 산출물 경로 해시 불변
G10 official test 경로 미접근 · M9 미호출
```

G1~G10은 **기술적 완주 여부**만 본다. 관찰 내용의 품질은 gate가 아니다.

---

## 7. 측정 항목 (판정하지 않는다)

```
chunk별   창 수 · 프레임 수 · 추론 횟수 · retry 횟수 · elapsed_sec
          peak VRAM · 창당 infer_wall_sec(min/max/mean) · input/output tokens
          BROAD_ACTIVITY label 분포 · OBSERVED_CHANGE 건수
          CONTEXT_INFERENCE 건수 · UNCERTAINTY 건수
          파싱 실패 건수 · 스키마 위반 건수 · 빈 출력 건수
전체      C01~C05 chunk-level summary 확보 여부 · 총 커버리지 ·
          chunk 간 겹침 120초 유지 여부 · 덮이지 않은 구간 총합
```

**chunk별 결과를 개별 튜닝하지 않는다.** 프롬프트·표집·창을 chunk마다 조정하는
행위는 이 사건에서 금지다.

---

## 8. No silent fallback

발생하면 반드시 기록한다.

```
파싱 실패 · 스키마 위반 · 빈 출력 · label 집합 이탈 · resume 발생 · retry 발생
RUNTIME_MISMATCH · VRAM OOM · 프레임 디코드 실패 · 창 수 불일치
```

---

## 9. 금지 (재확인)

```
C01 재실행 · 프롬프트/스키마 수정 · 창·stride·fps 변경 · 모델·revision 변경
chunk별 개별 튜닝 · chapter/event-map/boundary 연구 재개
official test 접촉 · M9 실행 · Track A 재생성
결과를 보고 §3 꼬리 규칙 변경 · 좋은 결과를 위한 retry
executor의 최종 품질 PASS 선언
```

---

## 10. 필수 산출물

```
runs/wvr_chunk_overview_v2/<CHUNK>/chunk_geometry.json
runs/wvr_chunk_overview_v2/<CHUNK>/video_overview_v2_segments.json
runs/wvr_chunk_overview_v2/<CHUNK>/video_overview_v2_segment_summaries.json
runs/wvr_chunk_overview_v2/<CHUNK>/video_overview_v2_result.json
runs/wvr_chunk_overview_v2/<CHUNK>/video_overview_v2_record.json
runs/wvr_chunk_overview_v2/<CHUNK>/video_overview_v2_packet.md
runs/wvr_chunk_overview_v2/chunk_gate.json          G1~G10 결과
runs/wvr_chunk_overview_v2/measurements.json        §7 계측
docs/probes/WVR_CHUNK_OVERVIEW_V2_C02_C05_2026-09-13.md
```

---

## 11. executor가 결정하지 않는 것

```
관찰 품질 PASS · chunk 재실행 여부 · 프롬프트 개선 여부
whole-video merge 방식 · Overview/Analysis/Conclusion 품질
M9 실행 여부 · official test 개방 여부
```

executor 보고 상태는 다음까지만이다.

```
WVR_CHUNK_OVERVIEW_V2 (C02~C05)
EXECUTED / REVIEW_PENDING
```

그리고 STOP한다.

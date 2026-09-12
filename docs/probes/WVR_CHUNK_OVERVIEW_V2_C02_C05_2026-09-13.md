# WVR_CHUNK_OVERVIEW_V2 — C02~C05 실행 결과 (2026-09-13)

사전등록: `docs/preregistration/WVR_CHUNK_OVERVIEW_V2_C02_C05_2026-09-13.md`

```
상태   EXECUTED / REVIEW_PENDING
```

**이 문서는 관측값만 적는다.** 관찰 품질 PASS · chunk 재실행 여부 · 프롬프트 개선 ·
whole-video merge 방식 · Overview/Analysis/Conclusion 품질 · M9 실행 여부는 전부
reviewer 결정이다(사전등록 §11).

---

## A. 실행 요약

```
호스트          kixlab2 · RTX 4090 24GB (실행 직전 유휴 40MiB)
격리 클론       /ssd/daeseok/jds-prj-chunkov-v2  (신규 · 기존 클론 미접촉)
code_git_head   ff888daeda1a0be658f2a1de7949dd414d2ec6f6
모델            Qwen/Qwen3-VL-8B-Instruct
                revision 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
                bfloat16 · sdpa · do_sample False · num_beams 1 · max_new_tokens 1024
영상            full_xekZO4n4QuE.mp4 · sha256 ea0e9f4866…5676cc (서버 실물 확인)
```

동결 순서대로 실행했고 전부 exit 0이다.

```
단계            대상    시작(UTC)              종료(UTC)              결과
0 plan-only     C02     —                      —                      PLAN_ONLY_OK (GPU 미사용)
1 canary        C02     (미기록)               (미기록)               exit 0 · elapsed 149.153초 · gate 10/10 PASS
2               C03     2026-09-12T15:17:12Z   2026-09-12T15:19:48Z   exit 0
3               C04     2026-09-12T15:19:48Z   2026-09-12T15:22:08Z   exit 0
4               C05     2026-09-12T15:22:08Z   2026-09-12T15:24:04Z   exit 0

C02는 단독 실행이라 배치 로그의 시작/종료 타임스탬프가 없다 — elapsed_sec만 있다.
C03~C05는 한 배치로 돌아 타임스탬프가 남았다.
```

canary gate가 10/10 PASS한 뒤에만 C03 이후로 넘어갔다. **retry 0 · resume 0.**

---

## B. Gate G1~G10 — 4 chunk 전부 PASS (40/40)

```
G1  status == GENERATED / REVIEW_REQUESTED          C02·C03·C04·C05 PASS
G2  segment_count · segment_inference_count == 창 수  PASS
G3  inference_count == 창 수 + 1                     PASS
G4  runtime 동결 모델·revision · bfloat16 · sdpa · 4090 PASS
G5  summary 개수 == 창 수 · 4개 필드 보유             PASS
G6  BROAD_ACTIVITY label이 동결 집합 안              PASS (집합 이탈 0건)
G7  창 시각이 사전등록 §3 표와 일치                   PASS
G8  video_sha256 == 동결 원본                        PASS
G9  C01 산출물 읽기 전용                             PASS
G10 official test 미접근 · M9 미호출                 PASS
```

gate는 기술적 완주만 본다. 관찰 내용의 품질은 gate가 아니다.

---

## C. 창 기하 — 사전등록 §3과 실측 일치

```
chunk   범위                창 수   첫 창          마지막 창        덮이지 않은 꼬리
C02     480.0 – 1080.0      24     [480, 528)     [1032, 1080)     0.0초
C03     960.0 – 1560.0      24     [960, 1008)    [1512, 1560)     0.0초
C04     1440.0 – 2040.0     24     [1440, 1488)   [1992, 2040)     0.0초
C05     1920.0 – 2424.186   20     [1920, 1968)   [2376, 2424)     0.186초
```

이번 사건 실행분: 창 92 · 프레임 2,208 · 추론 96회(창 92 + chunk 합성 4).
C01(창 24 · 추론 25)은 선행 산출물을 그대로 썼고 **재실행하지 않았다.**

---

## D. 런타임 계측 (판정 아님)

```
chunk   창   프레임   elapsed(초)  peak VRAM(MiB)  창당 추론(초, 평균)  input tok   output tok
C02     24    576      149.153       17446.0            1.958           56,962       1,082
C03     24    576      151.418       17446.0            1.966           57,202       1,121
C04     24    576      136.498       17446.0            1.797           57,216         999
C05     20    480      111.678       17446.0            1.816           47,680         824
```

4 chunk 합계 약 549초. peak VRAM은 네 chunk 모두 17,446 MiB로 동일하며
24GB 한도 안이다. retry 0 · resume 0 · 파싱 실패 0 · 스키마 위반 0 · 빈 출력 0.

참고: C01(선행)은 elapsed 70.7초였으나 그 실행은 중간 실패 후 resume한 기록이라
이번 4 chunk와 같은 축으로 비교하지 않는다.

---

## E. 관찰 산출물 계측 (판정 아님)

BROAD_ACTIVITY label 분포 — 동결 label 집합 이탈 0건.

```
C02   구매 또는 둘러보기 18 · 외출 준비 5 · 이동 5 · 식사 4 · 포장 작업 3 · 음식 준비 및 조리 2
C03   구매 또는 둘러보기 19 · 음식 준비 및 조리 8 · 식사 5 · 이동 3 · 외출 준비 2 ·
      포장 작업 1 · 정리 작업 1
C04   음식 준비 및 조리 18 · 식사 4 · 구매 또는 둘러보기 2 · 외출 준비 1 ·
      포장 작업 1 · 기타 명확한 주요 활동 1
C05   음식 준비 및 조리 18 · 식사 2
```

빈 BROAD_ACTIVITY 창 0개 (4 chunk 전부).

### OBSERVED_CHANGE / CONTEXT_INFERENCE / UNCERTAINTY 가 전부 0건이다

```
C02·C03·C04·C05   OBSERVED_CHANGE 0 · CONTEXT_INFERENCE 0 · UNCERTAINTY 0
C01 (선행 산출물)  OBSERVED_CHANGE 0 · CONTEXT_INFERENCE 0 · UNCERTAINTY 0
```

**C01에서도 같다.** 즉 이번 확장이 만든 현상이 아니라 V2 관찰 계약에서 이미
나타나던 동작이다. 원본 raw 출력이 그렇게 나온다.

```
raw 예 (C02 S01)
{
  "BROAD_ACTIVITY": ["음식 준비 및 조리", "외출 준비"],
  "OBSERVED_CHANGE": [],
  "CONTEXT_INFERENCE": [],
  "UNCERTAINTY": []
}
```

**원인 귀속을 하지 않는다** — 프롬프트 때문인지, 모델 때문인지, 관찰 대상 구간이
실제로 그런지는 이번 사건의 계측으로 구분되지 않는다. 사전등록 §9대로 프롬프트를
고치지 않았다.

---

## F. 전체 영상 커버리지

```
video_duration_sec     2424.186485
covered_sec            2424.0        (C01~C05 창 union = [0, 2424))
uncovered_sec          0.186485
chunk 쌍 겹침           120.0 · 120.0 · 120.0 · 120.0   (동결 계획대로)
chunk-level summary     C01 · C02 · C03 · C04 · C05     5/5 확보
전체 창 수              116 (C01 24 + 이번 92)
```

덮이지 않은 0.186485초는 C05 꼬리이며 0.5fps 표집 간격(2.0초)보다 짧아
표집되는 프레임이 없다. 사전등록 §3에 실행 전 동결한 규칙 그대로다.

---

## G. chunk-level Overview 생성 여부

4 chunk 모두 `video_overview_v2_result.json` 의 `status` 가
`GENERATED / REVIEW_REQUESTED` 이고 `overview.detailed_overview` 가 채워졌다.
**내용 평가는 하지 않는다** — reviewer가 본다.

```
runs/wvr_chunk_overview_v2/C02/video_overview_v2_result.json
runs/wvr_chunk_overview_v2/C03/video_overview_v2_result.json
runs/wvr_chunk_overview_v2/C04/video_overview_v2_result.json
runs/wvr_chunk_overview_v2/C05/video_overview_v2_result.json
runs/wvr_video_overview_preview_v2/video_overview_v2_result.json   (C01, 선행)
```

---

## H. 동결 유지 확인

```
Qwen3-VL model / revision          불변 (G4 실측)
visual observation prompt/schema   불변 — V2 모듈을 그대로 호출했다
window / stride / fps              불변 — shadow 상수에서 가져온다
broad visual summary contract      불변 — 4개 필드 스키마 그대로
```

확장 코드가 C01 계획을 그대로 재현하는 것을 테스트로 고정했다.

```
wvr_chunk_overview_v2.segments("C01")
  == runs/wvr_video_overview_preview_v2/video_overview_v2_segments.json
  (test_wvr_cov_05)
```

`wvr_video_overview_preview_v2_run.run` 에는 기본값 `None` 인 `plan` 인자만
추가했다 — plan을 주지 않으면 C01 동작은 이전과 문자 그대로 같다(test_wvr_cov_14).

chapter · event-map · boundary 연구를 재개하지 않았다.
chunk별 개별 튜닝을 하지 않았다 — 4 chunk 모두 같은 프롬프트·표집·창으로 돌았다.

---

## I. 사전등록 대비 편차

```
없음. §4 실행 순서(C02 plan-only → C02 canary → gate → C03 → C04 → C05)를
그대로 따랐고, retry 0 · resume 0이다.
```

---

## J. Baseline 보호

```
runs/wvr_video_overview_preview_v2/   읽기만 — 파일 수·내용 불변 (G9)
runs/rei_c01/ · runs/rei_c01_beta_v3/ · runs/v3_paired/   미접촉
config.yaml · work/ · work_full/ · Track A 인덱스          미접촉
official test 경로 미접근 · M9 미호출 (G10)
```

쓰기는 `runs/wvr_chunk_overview_v2/<CHUNK>/` 에만 일어났다.

---

## K. 산출물

```
runs/wvr_chunk_overview_v2/<C02|C03|C04|C05>/
    chunk_geometry.json · video_overview_v2_segments.json
    video_overview_v2_segment_summaries.json · video_overview_v2_result.json
    video_overview_v2_record.json · video_overview_v2_packet.md
    video_overview_v2_compressed_timeline.json
    video_overview_v2_segment_S**_prompt.txt · _raw.txt
    video_overview_v2_synthesis_prompt.txt · video_overview_v2_overview_raw.txt
runs/wvr_chunk_overview_v2/chunk_gate.json        G1~G10 결과
runs/wvr_chunk_overview_v2/measurements.json      §7 계측 + whole_video 커버리지
src/wvr_chunk_overview_v2.py · scripts/wvr_chunk_overview_v2_run.py ·
scripts/wvr_chunk_overview_v2_gate.py · tests/test_wvr_chunk_overview_v2.py
```

---

## L. executor가 결정하지 않은 것

```
관찰 품질 PASS · chunk 재실행 여부 · 프롬프트 개선 여부
OBSERVED_CHANGE/CONTEXT_INFERENCE/UNCERTAINTY 0건의 원인 귀속
whole-video merge 방식 · Overview/Analysis/Conclusion 품질
M9 실행 여부 · official test 개방 여부
```

---

## M. 상태

```
WVR_CHUNK_OVERVIEW_V2 (C02~C05)
EXECUTED / REVIEW_PENDING
```

# 프로젝트 개요와 현재 파이프라인 (2026-09-09 기준)

이 문서는 **지도**다. 수치의 최종 출처는 `DESIGN_SPEC.md`와 `results/`·`runs/` JSON이고,
진행 상황은 `docs/작업현황_*.md` 최신판이다. 여기 적힌 값은 그 파일에서 가져왔으며,
근거 경로를 옆에 붙였다.

## 1. 한 문장

한국어 영상에서 **자연어 질의로 장면(모먼트)을 찾고**, 같은 영상 이해 결과로
**한국어 보고서(HWPX)를 생성**하는 파이프라인. 두 산출물이 하나의 색인 위에 올라간다.

```
mp4 → 구간 분할 → 자막(STT) + 캡션(VLM) → 임베딩 색인
        ├── 검색: 질의 → 융합 랭킹 → 구간 반환          (M1~M7)
        └── 보고서: 1분 episode → 근거 결속 → HWPX      (V2.1 S0~S7)
```

## 2. 트랙 세 개와 현재 상태

```
TRACK A  검색·모먼트 (M1~M7)          확정 · test 39건 공식 평가 종료
TRACK B  보고서 생성 (V2.1 S0~S7)     IMPLEMENTATION_COMPLETE · 제출 arm 확정
                                     M9(보고서 평가)는 test 접촉이라 HOLD
TRACK C  전체영상 리포트 탐색 (WVR)     표집·용량 probe 진행 중 · event extraction HOLD
```

근거: `docs/finalization/V2_1_FINAL_ACCEPTANCE_2026-09-02.md`,
`docs/finalization/V2_1_SUBMISSION_QUALITY_PROMOTION_2026-09-08.md`,
`docs/probes/WVR_*`.

## 3. 데이터 규모

```
영상 provenance 등재       42건        data/provenance/videos.json
색인된 작업 디렉터리        20편        work/            (E2E fixture·M8 사례 포함)
AI Hub 보조 집합           194편       work_aihub/      (환경·모델 확증용)
질의                       135건       data/queries/queries.jsonl
  dev  96건 / 영상 3편     장면형 38 · 복합형 34 · 자막형 24
  test 39건 / 영상 4편     장면형 13 · 복합형 14 · 자막형 12
```

질의 유형 세 가지는 채널 의존도를 가른다 — `자막형`(발화 중심),
`장면형`(시각 중심), `복합형`(둘 다).

## 4. 배포 확정 구성

```
캡션 VLM        Qwen2.5-VL-3B-Instruct · 프롬프트 P0 · 4bit(NF4) · rep_penalty 1.1
                프레임 표집 3fps · 캡션은 화면 글자를 옮기지 않는 지시가 프롬프트에 포함
자막 STT        faster-whisper-large-v3
보고서 LLM       Qwen2.5-7B-Instruct (로컬 6GB 실행 불가 실측 · 서버 GPU 전용)
임베더          KURE-v1 (질의·자막·캡션 동일 모델 강제)
융합 정규화      per-query z-score          (minmax는 유의 열세 실측 · 2026-07-13 개정)
α (융합 가중)    0.5                        results/alpha_search_dev.json · tie_set [0.2, 0.4, 0.5]
                config에 없다 — CLI `--alpha` 주입
static_threshold 0 (캡션→자막 치환 off)
abstention       max(sub, cap) · τ = 0.55   results/abstention_calibration_maxch.json
```

`Qwen3-VL-4B`는 **후보이며 채택 상태가 아니다.** WVR 트랙이 쓰는
`Qwen3-VL-8B-Instruct`는 진단 전용이고 배포 구성이 아니다.

## 5. TRACK A — 검색 파이프라인 (M1~M7)

| 단계 | 모듈 | 하는 일 | 산출물 |
|---|---|---|---|
| M1 | `src/m1_preprocess.py` | mp4 → 16kHz mono wav + 구간 분할 | `audio.wav`, `segments.json`(idx·start·end) |
| M2 | `src/m2_keyframe.py` | 구간별 대표 프레임 선택(차분 L2 → 평활 → argmax), 정적 구간은 중간 프레임 fallback | `rep_frame`, `is_static`, `motion_score` |
| M3 | `src/m3_generate.py` | 자막(faster-whisper) + 캡션(Qwen2.5-VL) 생성 | `segments.json`의 `subtitle`·`caption` |
| M4 | `src/m4_index.py` | 자막·캡션 임베딩 (L2 정규화 float32) | `emb_sub.npy`·`emb_cap.npy` (n, 1024), `meta.json`의 `text_hash` |
| M5 | `src/m5_search.py` | 코사인 → per-query z-score → (치환) → α 가중합 | 랭킹 · abstention |
| M6 | `src/m6_evaluate.py` | dev grid search로 α 고정 → test 단발 평가 | `results/alpha_search_dev.json`, `results/eval_test.json` |
| M7 | `src/m7_demo.py`·`m7_webui.py` | 데모 UI (백엔드는 `m5_search.search`를 그대로 import) | — |

### 5-1. 실행 순서 불변식

```
m3(재캡셔닝 포함) → m4 → m6
```

재캡셔닝 후 m4를 건너뛰면 임베딩이 낡는다. `meta.json`의 `text_hash`가 불일치를
M5 로드에서 `ValueError`로 막지만, **배치 안에서 m4까지 도는 것이 규약**이다.
`--force`는 필요 없다(해시가 변경을 감지한다).

### 5-2. 확정 성능 (test 39건 · α=0.5 · 비가역 자원)

```
지표         baseline(α=1.0 · 자막 단독)   proposed(융합 α=0.5)
hit@1               0.5641                    0.7692
hit@5               0.7692                    0.8718
MRR                 0.6489                    0.8286
IoU@0.5 R@1         0.5641                    0.7692
```

유형별로 보면 이득의 출처와 대가가 같이 보인다.

```
유형     baseline hit@1 / MRR      proposed hit@1 / MRR
자막형     0.9167 / 0.9583           0.8333 / 0.8802     ← 소폭 손실
복합형     0.7857 / 0.8246           0.8571 / 0.8869
장면형     0.0000 / 0.1741           0.6154 / 0.7183     ← 이득의 대부분
```

즉 융합은 자막 단독이 원리적으로 못 푸는 `장면형`을 여는 대신 `자막형`에서 조금
내놓는다(전문: `results/eval_test.json`).

**test는 재평가하지 않는다.** 접촉 이력은 확정 절차 공식 평가 7회(검색 M6 5회 +
리포트 M9 2회)로 `DESIGN_SPEC` 8-6에 사유까지 적혀 있고, 39→72 확장은 준비돼 있으나
별도 test-opening 승인 사건으로 HOLD다.

## 6. TRACK B — 보고서 생성 파이프라인 (V2.1)

M8 v1은 2026-08-27 공식 판정에서 **생성은 COMPLETE, acceptance는 FAIL**
(C1 파국 4/8편 · C2 median align 0.3311 · C3 max compression 7.00)이었고,
임계를 고치지 않고 구조를 재설계한 결과가 V2.1이다
(`docs/finalization/M8_OFFICIAL_RESULT_2026-08-27.md`).

| 단계 | 하는 일 |
|---|---|
| S0 | ingest — 5초 구간의 ASR·VLM raw 적재 (`raw/asr`, `raw/vlm` 소유) |
| S1 | episode 경계 — `fixed_window_v1` 60초 고정 분할 |
| S2 | raw LLM 생성 (Qwen2.5-7B-Instruct · `raw/llm` 소유) |
| S3 | content 파싱 — 계약 위반은 `PARSE_CONTRACT_FAILURE`로 남긴다 |
| S4 | grounding — 인용이 실제 evidence에 있는지 검사 |
| S5 | canonical 조립 — `aar_canonical.json` (여기까지가 정본) |
| S6 | presentation — 표현 계층(그룹핑·제목)은 canonical을 수정하지 않는다 |
| S7 | 렌더 — MD/HWPX (`A2'` 순수 Python OWPML 경로) |

핵심 계약: **`chunk boundary ≠ report boundary`**, canonical에 자유 증식 필드를 두지
않는다, Highlight·Global Synthesis는 canonical 밖에서 validated 입력만 쓴다
(`docs/finalization/V2_1_ARCHITECTURE_SPEC_2026-08-30.md`).

### 6-1. 현행 제출 arm

```
arm            R1-VAD0-QUALITY
정책 3층        episode_content_v3_summary_only + STT_VAD0 + output_quality_v1
표현 상수       presentation grouping 300초
artifact       runs/quality_candidate/S7/report.hwpx
               sha256 5732075871fd…  ·  tag submission-quality-2026-09-08
canonical      41 episode (fixed_window 60초) · segments sha aa008317…
상태           READ-ONLY / NO PROMOTION
rollback       4e10aaab… (submission-vad0-2026-09-07) · f874f643… (submission-ready-2026-09-03)
```

`M9`(보고서 평가)는 `split=="test"`가 하드코딩돼 **돌리는 것 자체가 test 접촉**이므로
승인 없이 실행 금지다. `semantic entailment`는 UNVERIFIED, `GRD-004`는 P1 WAIVED.

## 7. TRACK C — WVR (전체영상 리포트) 탐색 현황

10분 chunk를 Qwen3-VL-8B로 한 번에 이해시키려는 경로의 **용량·표집 특성**을 재는
탐색 트랙이다. 사건마다 사전등록 → 커밋 → 실행 순서를 지킨다.

```
C01 capacity                    CLOSED / CAPACITY_FAIL      300프레임 prefill OOM
WVR_CAPACITY_ALLOC_V1           CLOSED / CAPACITY_FAIL      expandable_segments 적용되나 부족
WVR_CAPACITY_SAMPLING_V1        CLOSED / CAPACITY_PASS      0.25fps·150프레임 완주
density Stage 1                 REVIEWED / PASS             0.25fps ⊂ 0.5fps 포함관계
density Stage 2 (V1·V1B)        CLOSED / INCONCLUSIVE       절단 · 표현 축퇴
density V2                      CLOSED / PAIRED_OUTPUT_STABILITY_HOLD
EVIDENCE_RESOLUTION_V1          CLOSED / BRANCH_C_EVIDENCE_INCONCLUSIVE
SHORT_WINDOW_V1                 CLOSED / SHORT_WINDOW_PAIRED_STABILITY_HOLD
                                48초에서도 divergence 재현 → long-context-only 가설 기각
FRAME_ADJUDICATION_V1           packet 생성 완료 · 리뷰어 판정 대기
```

정리된 사실:

```
0.25fps semantic sufficiency    NOT ESTABLISHED
0.5fps                          higher-density reference · factual authority 아님
WVR event extraction            HOLD (chapter·highlight·report 포함)
```

## 8. 방법론 규율 (요약 — 전문은 `CLAUDE.md`)

```
① test 재평가 금지. 모든 튜닝·ablation은 dev 전용. test-opening은 별도 승인 사건
② 캡션 수동 편집 금지. 자동 오염 판정분만 `m3 --recaption-corrupted`로 재생성
③ 라벨 작성 시 검색 결과 참조 금지. 라벨 도구는 `scripts/label_guard.py`
   allowlist(idx·start·end·rep_frame)만 통과 — caption·subtitle을 도구가 막는다
④ 변형 실험은 config 사본 + paths.work/results 동시 분리로 격리
⑤ 속도는 채택 기각 사유가 아니다. 정확도 우열이 애매할 때만 타이브레이커
⑥ 후보 모델 검증 5항목: 채널 격리 · 검출 한계 병기 · 현행 전용 설정 재탐색 ·
   동시점 대조군 · 생성물 전량 저장
⑦ 사전등록 → 커밋 → 실행. 결과를 본 뒤 파라미터·게이트·판정 어휘를 바꾸지 않는다
⑧ 정식 GPU 배치는 git에 등록된 스크립트로. 진행 판정은 완료 마커 + validator PASS로
   (프로세스 유무로 판정하지 않는다). 수치는 UTF-8 JSON에서 읽는다(콘솔 cp949)
```

## 9. 어디를 보면 되는가

```
재시작           docs/작업현황_*.md 최신판 → docs/README.md(문서 지도)
수치의 출처       DESIGN_SPEC.md · results/*.json · runs/**/[결과].json
제출 상태         docs/finalization/V2_1_SUBMISSION_QUALITY_PROMOTION_2026-09-08.md
사전등록          docs/preregistration/  (내용을 고치지 않는 문서)
probe 결과        docs/probes/
서버 접속값       SERVER_LOCAL.md (git 추적 안 함 · 문서에는 자리표시자만)
검증 절차         .claude/skills/pipeline-verify · .claude/skills/gpu-batch
```

# 세션 인수 (자동 생성)

> **직접 편집하지 마라.** `scripts/make_handoff.py`로 다시 생성한다. 이 도구는 수집기이고 해석기가 아니다 — 수치를 보고 판정을 만들지 않고, 각 항목에 출처를 붙인다.
> 판정·근거는 출처 문서에서 읽어라.

> **작업 트리가 dirty다.** 아래 사실은 커밋되지 않은 변경을 포함한 상태에서 수집됐다 — 재현하려면 `git status`를 먼저 봐라.

## git HEAD

`9907a6430ad2cbe2f69396e5358e4431e2b67651`

source: git rev-parse HEAD

## 작업 트리 dirty

`True`

source: git status --porcelain

## 최근 커밋

```
9907a64 feat(infra): CANARY 커버리지·세션 인수·provenance registry·실행 상태 판독기
ab73e1c fix(p2): 타이밍 플래그를 버전으로 추측하지 않고 실제로 돌려서 고른다
e328823 fix(p2): AV1 입력을 H.264로 옮기고 CANARY가 입력 종류를 전부 밟게 한다
5fd70b9 fix(p2): video_id가 하이픈으로 시작하면 argparse가 옵션으로 읽는다
b6f4f65 fix(p2): 산출물 이름을 stage에 귀속시킨다
```

source: git log -5 --oneline

## 기준 작업현황

`docs\작업현황_2026-08-22.md`

source: scripts/make_handoff.py latest_status_doc()
note: 파일명 날짜가 가장 큰 작업현황이다

## GO

```
I1   83프레임 A labeling — label_kit/i1_validation/labels_v.csv
P2   질의 315건 + GT 라벨 — docs/P2_질의쿼터_2026-08-20.md 배정표대로
     허용 도구 label_contact_sheet · label_intake만
     금지 3B/4B 캡션 · 검색 결과 · frame_human_kit
P2   CANARY m4 완료 → validate
P2   validator PASS 이후 FULL → 완주 후 validate → PASS면 RUN_COMPLETE → 산출물 요약
```

source: docs\작업현황_2026-08-22.md **GO**

## HOLD

```
CANARY validator PASS 전 FULL 진입 — 승인 문자열이 있어도 선행조건이 우선이다
test 접촉·개방 (M9 실행 포함 — M8 확정만으로 권한이 생기지 않는다)
4B 채택 — P2가 어떻게 나오든 자동으로 열리지 않는다
결과를 보고 reservoir·질의·GT·config 수정
I1 validation 결과 후 detector 재튜닝
39 → 72 확장(신규 33건) — 준비돼 있으나 별도 test-opening 이벤트
```

source: docs\작업현황_2026-08-22.md **HOLD**

## 다음 승인 지점

```
1  FULL 완주 → validator PASS → 산출물 보고 (여기까지 자동)
2  [승인 필요] P2 질의·GT 완성 후 평가 실행 여부는 승인 ② 범위 안이지만,
   결과가 4B 채택 논의로 넘어가는 순간 별도 승인 사건이다
3  [완전 별도 승인] test-opening — P2 결과와 무관하게 자동으로 열리지 않는다
```

source: docs\작업현황_2026-08-22.md 9. 다음 승인 지점

## 현재 실행 상태

관측하지 못했다 (null)

source: C:\Users\UserK\Desktop\prj\docs\probes\_scratch\launcher_runs
note: 마커는 관측일 뿐이다 — 완료 근거는 RUN_COMPLETE.json 하나이고, 같은 run_id의 CANARY 마커를 FULL 완료로 읽지 마라

## 테스트 결과

관측하지 못했다 (null)

source: python -m pytest tests/ -q
note: 이 실행에서 돌리지 않았으면 null이다 — 낡은 값을 옮기지 않는다

## 배포 config

```
seg_len_sec: 5
frame_sample_fps: 3
static_threshold: 0           # 정적 치환 off — dev 스윕에서 치환이 유의하게 손해 확인 (2026-07-11, ablation_plan 2-4-2)
gaussian_sigma: 1.0
seed: 42

stt_model: "large-v3"         # faster-whisper. 부족 시 "turbo"
stt_language: "ko"

caption_model: "Qwen/Qwen2.5-VL-3B-Instruct"  # 서버(대용량 VRAM)에서는 Qwen2.5-VL-7B-Instruct
vlm_4bit: true                # 서버(대용량 VRAM)에서는 false (로컬 6GB VRAM은 true, NF4, 기존 caption 실험 검증)
vlm_max_pixels: 602112        # 768*28*28 (기존 실험: 비전 토큰 폭증 방지)
vlm_max_new_tokens: 128       # 8-3(a) config화(하드코딩 이전, 기본값 유지=동작 불변). 실험 3에서 192~256 상향 가능
vlm_rep_penalty: 1.1          # 1.3은 3B-4bit에서 문자혼입(한자·가나) 유발 확인(2026-07-09 rp 실험: 혼입 8/10→3/10, 반복 붕괴는 1.0에서도 미발생) — 보험으로 1.1
caption_truncate_incomplete: false  # 8-3(b) 미완결 문장 절단. 기본 off(현행 인덱스·평가 불변) — 켜면 재임베딩+test 재평가 절차 필요
caption_normalize_cjk: false        # 8-3(c) 잔여 한자·가나 제거+caption_raw 보존. 기본 off(동일 절차 조건)
caption_prompt: "이 장면을 한 문장의 한국어로 객관적으로 묘사하라. 화면에 보이지 않는 것은 쓰지 마라. 화면에 자막이나 글자가 보이더라도 그 글자를 그대로 옮겨 적지 말고, 인물의 행동과 배경 등 시각적 내용만 묘사하라."

embed_model: "nlpai-lab/KURE-v1"   # dev에서 BAAI/bge-m3와 비교 후 확정 [v2 8-5]
embed_batch_size: 32

abstention_tau: 0.55          # max(raw_sub_max, raw_cap_max) 기준 무관련 경고 임계값 — dev 96 vs 무관 20 재캘리브레이션(2026-07-13, 8-2 개정: sub 단독은 장면형 오배제 편향, 오배제 2/96→0/96·감지 13→14/20). KURE-v1 종속: embed_model 교체 시 재캘리브레이션 필수

alpha_grid: [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
alpha_select_metric: "mrr"    # hit@5는 소표본 계단형·동률 다발로 α* 불안정 [8-1(a)]
bootstrap_B: 2000              # 쌍체 차이 부트스트랩 재표집 횟수 [8-1(b)]
alpha_tiebreak: "larger"      # 동률 시 자막 우선 [v2 9-1(a)]
eval_k: [1, 5, 10]
iou_thresholds: [0.5, 0.3]

report_model: "Qwen/Qwen2.5-7B-Instruct"  # 로컬 6GB 실행 불가 실측(4bit로도 embed·lm_head 비양자화분 초과) — 서버 GPU 전용. 3B 하향은 프롬프트 예시 문장 복사 오염으로 기각(2026-07-11, 평가분석 문서 참조)
report_max_new_tokens: 16384   # llm.py 기본 2048은 reduce 출력을 잘랐다(dev 3영상 전부 꼬리 절단 실측, 2026-08-06) [8-5(6)]
llm_4bit: true                # 서버(대용량 VRAM)에서는 false (로컬 6GB VRAM 대응) [m8m9-prompt-critique B-7]
judge_model: "Qwen/Qwen2.5-7B-Instruct"  # 잠정: 다른 패밀리 1순위는 서버 GPU 확정 대기 — 그때까지 report_model과 동일 모델 자기평가(편향 한계를 결과에 명시) [v2 17-6 2순위]
same_model_judge: true        # 위 잠정 조치의 명시적 선언 — 미선언 시 M9가 거부 [v2 17-6]
map_chunk_size: 60
map_chunk_overlap: 5
human_check_n: 20

paths:
  data: "data"
  work: "work"
  results: "results"
```

source: config.yaml
note: 파일 내용을 옮긴 것이다. CLI 주입값은 여기에 없다

## 고치지 않는 문서

```
8회차_개방게이트_2026-08-16.md
I1_detector_보충1_development절차_2026-08-20.md
I1_detector_보충2_validation표집_2026-08-20.md
I1_detector_보충3_표집확정_2026-08-20.md
I1_detector_보충4_판정근거_2026-08-20.md
I1_detector_재설계_사전등록_2026-08-18.md
I1검증셋_보충2_B단계_C0생략_2026-08-18.md
I1검증셋_보충_B단계경계_2026-08-18.md
I1검증셋_사전등록_2026-08-18.md
M8_dev예비실행_사전등록_2026-08-18.md
M8_event지표_보충_2026-08-18.md
M8_개선_사전등록_2026-08-14.md
M8_구조변경_사전등록_2026-08-16.md
alpha곡선_2x2_사전등록_2026-08-18.md
caption_2x2_사전등록_2026-08-17.md
dev_precision_3arm_보충_CI해석_2026-08-18.md
dev_precision_3arm_사전등록_2026-08-18.md
event_inventory_사전등록_2026-08-18.md
test_재평가_프로토콜_2026-08-13.md
부호역전_조사_사전등록_2026-08-18.md
부호역전_확증_보충1_P1설계_2026-08-18.md
부호역전_확증_보충2_P2설계_2026-08-20.md
부호역전_확증_보충3_P2표집범위_2026-08-20.md
부호역전_확증_보충4_P2표집틀검증_2026-08-20.md
부호역전_확증_사전등록_2026-08-18.md
융합feature진단_사전등록_2026-08-18.md
```

source: docs/preregistration/
note: 내용을 고치지 않는 문서다. 이탈은 보충으로 적는다

## 문서 지도

`docs/README.md`

source: docs/README.md


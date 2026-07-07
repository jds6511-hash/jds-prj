**모듈별 상세 설계서 (v1)**

*영상 장면 검색 및 AAR 보고서 자동 생성 시스템 — API·입출력·데이터 스키마 명세*

구현가이드 v2(0~17장)의 확정 로직을 코드 수준 계약으로 환원한 문서. 이 문서와 구현가이드 v2가 충돌하면 v2가 우선하며, 충돌 발견 시 본 문서를 수정한다.

정대석 · KAIST 김주호 교수님 연구실

# 1. 설계 원칙 (v2에서 상속하는 확정 결정)

본 설계서의 모든 모듈은 아래 확정 결정을 전제로 한다. 각 항목의 근거는 괄호의 v2 장 번호를 참조한다.

- 5초 고정 세그먼트 분할 (v2 1장)
- VLM은 캡션 생성기로만 사용, 검색은 임베딩 코사인 (v2 7-2, 7-9)
- 자막·캡션·질의는 동일 임베딩 모델로 인코딩 (v2 7-8)
- 연산 순서 고정: 유사도 계산 → per-query min-max 정규화(단일 영상 범위) → 정적 세그먼트 s_cap_norm ← s_sub_norm 치환 → α 가중합 (v2 8-2, 8-4)
- α grid search는 dev셋에서만 수행 후 고정 (v2 9-1)
- 주지표 = 세그먼트 인덱스 기반 Hit/Recall@k·MRR, IoU@0.5/0.3은 보조 (v2 8-3)
- 클라우드 API 배제, 전 처리 온프레미스 (v2 7-8)
- baseline은 동일 파이프라인의 α=1.0 특수 경우 — 별도 코드 경로 금지 (v2 8-4)

추가로 본 설계서가 새로 정하는 공학 원칙 두 가지:

- **모듈 간 통신은 파일(JSON/JSONL/NPY)로만 한다.** 각 모듈은 독립 실행 가능한 CLI 스크립트이며, 앞 모듈의 산출 파일만 읽는다. 중간 산출물이 전부 파일로 남아 디버깅·재현·부분 재실행이 쉬워진다.
- **모든 모듈은 멱등(idempotent)하게 설계한다.** 같은 입력·같은 config로 다시 실행하면 같은 출력을 덮어쓴다. 난수가 개입하는 지점(없는 것이 원칙)은 config의 seed로 고정한다.

# 2. 디렉터리·파일 구조

```
project/
├── config.yaml                  # 전역 설정 (7장)
├── data/
│   ├── videos/                  # 원본 mp4 (영상ID = 파일명 stem)
│   │   └── {video_id}.mp4
│   └── queries/
│       └── queries.jsonl        # 평가 질의셋 (3-3)
├── work/                        # 모듈별 중간 산출물 (영상ID별 하위 폴더)
│   └── {video_id}/
│       ├── audio.wav            # M1: 16kHz mono
│       ├── segments.json        # M1→M2→M3 순으로 필드가 채워짐 (3-1)
│       ├── frames/              # M2: 대표 프레임 이미지
│       │   └── seg_{idx:04d}.jpg
│       ├── emb_sub.npy          # M4: (N_seg, D) float32
│       ├── emb_cap.npy          # M4: (N_seg, D) float32
│       └── report.json          # M8: AAR 리포트 (3-5)
├── results/
│   ├── alpha_search_dev.json    # M6: dev셋 grid search 결과
│   ├── eval_test.json           # M6: 최종 평가 결과 (3-4)
│   └── report_eval.json         # M9: AAR 평가 결과
└── src/
    ├── m1_preprocess.py
    ├── m2_keyframe.py
    ├── m3_generate.py
    ├── m4_index.py
    ├── m5_search.py
    ├── m6_evaluate.py
    ├── m7_demo.py
    ├── m8_report.py
    └── m9_report_eval.py
```

# 3. 공용 데이터 스키마

모듈 간 계약의 핵심. 스키마를 어기는 파일을 만들거나 읽는 모듈은 즉시 실패(fail-fast)해야 한다.

## 3-1. segments.json — 세그먼트 마스터 레코드

M1이 생성하고 M2·M3가 필드를 추가하는 단일 파일. 각 모듈은 자신이 채울 필드가 이미 있으면 덮어쓴다.

```
{
  "video_id": "vlog_001",
  "duration_sec": 632.4,
  "fps": 30.0,
  "n_segments": 127,
  "segments": [
    {
      "idx": 0,                      // M1: 0부터 연속 정수
      "start": 0,                    // M1: 정수 초 (내림)
      "end": 5,                      // M1: min(start+5, duration)
      "rep_frame": "frames/seg_0000.jpg",  // M2
      "is_static": false,            // M2: 프레임 차분 평균 < static_threshold
      "motion_score": 0.183,         // M2: 차분 L2 norm 평균 (판정 근거 기록)
      "subtitle": "재료를 미리 준비해 두세요",   // M3: 없으면 ""
      "caption": "주방에 재료들이 나무 도마 위에 놓여 있다"  // M3
    }
  ]
}
```

규칙:

- `idx`는 0부터 빈틈없는 연속 정수. `start = idx * 5` 불변식이 항상 성립해야 하며, 어기면 로드 시 예외.
- `subtitle`이 빈 문자열인 세그먼트(무발화)는 정상 케이스다. M4는 빈 문자열도 그대로 임베딩한다(별도 처리 금지 — baseline과 proposed의 대칭성 유지).
- `is_static` 판정 근거(`motion_score`)를 함께 기록해 11주차 임계값 ablation 때 재판정 없이 재실험할 수 있게 한다.

## 3-2. 오버랩 자막 귀속 규칙 (M3, v2 8-1)

Whisper 발화가 세그먼트 경계를 가로지르면: 발화 시간이 더 많이 걸친 세그먼트에 귀속하되, 경계에 걸친 문장은 양쪽 세그먼트의 `subtitle`에 중복 포함을 허용한다. 구현은 Whisper의 word-level timestamp로 발화별 [t0, t1]을 구해 각 세그먼트와의 겹침 길이를 비교한다.

## 3-3. queries.jsonl — 평가 질의셋

한 줄 = 질의 하나. 데이터 명세서(Excel)에서 export하는 형식이며, 라벨링은 명세서에서 하고 이 파일은 산출물이다.

```
{"query_id": "q001", "video_id": "vlog_001",
 "text": "도마 위에 재료가 놓여 있는 장면",
 "type": "장면형",                    // 자막형 | 장면형 | 복합형
 "gt_start": 33.0, "gt_end": 38.5,   // 정답 구간 타임스탬프
 "gt_seg_idx": [6, 7],               // 정답 세그먼트 인덱스 (주지표용, v2 8-3)
 "split": "dev"}                     // dev | test (영상 단위 분리, v2 5-1)
```

규칙:

- `gt_seg_idx`는 정답 구간과 가장 많이 겹치는 세그먼트(들)의 리스트. 산출 규칙: 정답 구간과 1초 이상 겹치는 모든 세그먼트를 포함하되 최소 1개 보장(겹침 최대 세그먼트).
- `split`은 **video_id 단위로만** 배정한다(같은 영상의 질의가 dev/test에 갈라지면 누수). 배정 시 질의 type 비율이 두 split에서 유사하도록 층화한다 (v2 5-1).

## 3-4. eval_test.json — 평가 결과

```
{
  "alpha_from_dev": 0.6,
  "n_queries": {"total": 60, "자막형": 20, "장면형": 20, "복합형": 20},
  "metrics": {
    "baseline": {                     // α=1.0
      "hit@1": 0.55, "hit@5": 0.78, "hit@10": 0.87, "mrr": 0.64,
      "iou@0.5_r@1": 0.42, "iou@0.3_r@1": 0.58,     // 보조지표
      "by_type": {"자막형": {...}, "장면형": {...}, "복합형": {...}}
    },
    "proposed": { ... }               // α=alpha_from_dev, 동일 구조
  },
  "per_query": [ {"query_id": "q001", "baseline_rank": 3, "proposed_rank": 1}, ... ]
}
```

`per_query`는 오류 분석(10주차)용 원자료. 질의별 랭크를 남겨야 "장면 결합이 도운/해친 질의"를 사례로 뽑을 수 있다.

## 3-5. report.json — AAR 리포트 (M8, v2 15장)

```
{
  "video_id": "vlog_001",
  "model": "Qwen2.5-...-Instruct",
  "map_chunk_size": 60,               // map 단계 청크당 세그먼트 수
  "sentences": [
    {"sent_id": 0,
     "text": "영상 초반, 화자가 조리 재료를 도마 위에 준비한다",
     "cites": [6, 7]}                 // [seg#N] 인용을 파싱한 인덱스 리스트
  ],
  "raw_output": "..."                 // LLM 원문 (파싱 실패 검증용 보존)
}
```

규칙: `cites`가 빈 리스트인 문장도 저장은 하되(검열 금지), M9에서 자동으로 ungrounded 처리된다 (v2 15-1).

# 4. 모듈별 명세

각 모듈은 `python src/mN_*.py --config config.yaml --video-id {id}` 형태의 CLI로 실행한다. 공통 옵션: `--force`(산출물 있어도 재생성).

## 4-1. M1 전처리 (v2 1장)

- **입력:** `data/videos/{video_id}.mp4`
- **출력:** `work/{video_id}/audio.wav`, `segments.json`(idx/start/end만 채움)
- **핵심 함수:**

```
def extract_audio(video_path: Path, out_wav: Path,
                  sr: int = 16000, mono: bool = True) -> None
def make_segments(duration_sec: float, seg_len: int = 5) -> list[dict]
    # start = idx*5 (정수 초 내림), end = min(start+5, duration)  [v2 9-1(d)]
```

- **검증 포인트:** 마지막 세그먼트 end == duration(반올림 오차 0.5초 이내), n_segments == ceil(duration/5).

## 4-2. M2 대표 프레임 선택 (v2 2장)

- **입력:** mp4, `segments.json`
- **출력:** `frames/seg_{idx:04d}.jpg`, `segments.json`에 rep_frame/is_static/motion_score 추가
- **핵심 함수:**

```
def select_rep_frame(frames: list[np.ndarray],
                     sigma: float = 1.0) -> tuple[int, float]
    # returns (rep_idx, motion_score)
    # diffs = L2(frame[i]-frame[i-1]) → gaussian_filter(sigma) → argmax+1
def is_static(motion_score: float, threshold: float) -> bool
    # True면 rep_frame = 중간 프레임으로 fallback  [v2 2장 주의]
```

- **확정 로직:** 정적 판정 시에도 캡션은 생성한다(M3). 캡션을 버리는 것이 아니라 M5에서 점수를 치환하는 것이 확정 처방이다 (v2 8-4). M2는 플래그만 기록한다.
- **검증 포인트:** 모든 세그먼트에 rep_frame 파일 존재. is_static 비율을 로그로 출력(비율이 50%를 넘으면 threshold 재검토 경고).

## 4-3. M3 자막·캡션 생성 (v2 3장)

- **입력:** audio.wav, frames/, `segments.json`
- **출력:** `segments.json`에 subtitle/caption 추가
- **핵심 함수:**

```
def transcribe(wav: Path, model: str = "large-v3") -> list[Utterance]
    # Utterance = {text, t0, t1, words:[{w, t0, t1}]}
def assign_subtitles(utts: list[Utterance],
                     segments: list[dict]) -> None
    # 3-2 오버랩 귀속 규칙 구현. 경계 문장 양쪽 중복 허용
def caption_frame(image: Path, prompt: str, model) -> str
    # 프롬프트는 config의 caption_prompt 1종 고정 (다중 프롬프트는 11주차)
```

- **캡션 프롬프트 (config 기본값):** "이 장면을 한 문장의 한국어로 객관적으로 묘사하라. 화면에 보이지 않는 것은 쓰지 마라." — 캡션 언어 = 질의 언어 = 한국어 원칙 (v2 7-8).
- **검증 포인트:** caption 빈 문자열 0건(생성 실패 시 재시도 1회 후 실패 목록 출력). subtitle 커버리지(비어있지 않은 비율)를 로그로 남긴다.

## 4-4. M4 임베딩·인덱싱 (v2 3장)

- **입력:** `segments.json`
- **출력:** `emb_sub.npy`, `emb_cap.npy` — 둘 다 shape (N_seg, D), float32, L2 정규화 저장
- **핵심 함수:**

```
def embed_texts(texts: list[str], model_name: str,
                batch_size: int = 32) -> np.ndarray   # L2-normalized
```

- **확정 로직:** 자막·캡션·(추후 질의)는 반드시 같은 model_name으로 임베딩 (v2 7-8). model_name은 config 한 곳에서만 정의하고 M4·M5가 공유한다.
- **검증 포인트:** row 수 == n_segments. norm 편차 < 1e-4. 임베딩 모델명·차원 D를 npy 옆 meta.json에 기록(모델 교체 실험 시 혼입 방지).

## 4-5. M5 검색 (v2 4장 + 8-2 + 8-4 확정 로직)

- **입력:** 질의 문자열, `segments.json`, emb_sub.npy, emb_cap.npy, α
- **출력:** 랭킹 리스트 `[(idx, score, start), ...]`
- **확정 시그니처와 로직 (이 순서를 어기는 구현은 리젝):**

```
def search(query: str, video: VideoIndex, alpha: float) -> list[Result]:
    q = embed_texts([query], cfg.embed_model)[0]
    s_sub = video.emb_sub @ q            # 1) 코사인 (L2 정규화 완료 상태)
    s_cap = video.emb_cap @ q
    s_sub = minmax(s_sub)                # 2) per-query, 단일 영상 범위 [8-2]
    s_cap = minmax(s_cap)
    s_cap[video.static_mask] = s_sub[video.static_mask]  # 3) 치환 [8-4]
    score = alpha * s_sub + (1 - alpha) * s_cap          # 4) 가중합
    return rank(score)

def minmax(x: np.ndarray) -> np.ndarray:
    rng = x.max() - x.min()
    return np.zeros_like(x) if rng < 1e-9 else (x - x.min()) / rng
    # rng≈0 (모든 점수 동일) 엣지 케이스: 0 벡터 반환으로 균등 처리
```

- **baseline 규정:** `search(query, video, alpha=1.0)`. 별도 함수 금지 — 정규화·치환 인프라가 동일해야 비교가 대칭 (v2 8-4).
- **정규화 범위:** 반드시 해당 단일 영상의 세그먼트 배열 단위. 멀티 영상 DB라도 영상 경계를 넘는 minmax 금지 (v2 8-2).

## 4-6. M6 평가 (v2 5장 + 8-3)

- **입력:** queries.jsonl, 영상별 인덱스, config
- **출력:** alpha_search_dev.json, eval_test.json
- **핵심 함수:**

```
def hit_at_k(ranked: list[Result], gt_seg_idx: list[int], k: int) -> float
    # 주지표: top-k 인덱스와 gt_seg_idx의 교집합 존재 여부 [8-3]
def mrr(ranked, gt_seg_idx) -> float
    # gt_seg_idx 중 하나가 처음 등장하는 랭크의 역수
def iou_recall_at_k(ranked, gt_start, gt_end, k, thr) -> float
    # 보조지표: thr ∈ {0.5, 0.3}
def grid_search_alpha(dev_queries) -> float
    # α ∈ {0.0,0.1,...,1.0}, 기준 = dev hit@5 (config로 변경 가능)
    # 동률 시 α가 큰 값(자막 우선) 선택 [v2 9-1(a)]
```

- **실행 순서 강제:** ① dev로 grid_search_alpha → alpha_search_dev.json 저장 → ② test 평가는 그 α만 사용. M6는 test 질의로 α를 재탐색하는 코드 경로를 갖지 않는다(누수 원천 차단, v2 9-1).
- **검증 포인트:** dev/test에 같은 video_id가 없는지 로드 시 assert.

## 4-7. M7 프로토타입 (v2 6장)

- **입력:** 사용자 질의(웹 UI), 인덱스 일체, α(= eval에서 고정한 값)
- **출력:** 화면 — 결과 목록(top-3), 클릭 시 해당 초로 점프 + 자막 표시

```
def format_output(ranked: list[Result], segments, k: int = 3) -> dict:
    return {"jump_to": int(ranked[0].start),
            "subtitle": segments[ranked[0].idx]["subtitle"],
            "windows": [[int(r.start), int(r.end)] for r in ranked[:k]]}
    # 정수 초 [[시작,끝],...] 형식 고정 [v2 6장, Chrono 근거]
```

- 구현 스택 자유(Gradio 권장 — 영상 플레이어 + 텍스트박스로 충분). 백엔드는 M5의 search()를 그대로 import하며 재구현 금지.

## 4-8. M8 AAR 리포트 생성 (v2 15장)

- **입력:** `segments.json`
- **출력:** `report.json` (3-5)
- **핵심 함수:**

```
def build_map_prompt(chunk: list[dict]) -> str
    # [seg#N] 인용 강제 규칙 4개 포함 [v2 15-1 골격]
def build_reduce_prompt(partial_reports: list[str]) -> str
    # 중복 제거 + 시간순 재정렬만. "새 사실 추가 금지" 명시 [v2 15-2]
def parse_citations(text: str) -> list[Sentence]
    # 정규식 r"\[seg#(\d+)(?:,\s*seg#(\d+))*\]" 파싱, 실패 문장은 cites=[]
def generate_report(segments, llm, chunk_size: int = 60) -> Report
```

- **map-reduce 발동 조건:** n_segments > chunk_size일 때만 map-reduce, 이하면 단일 호출. chunk_size는 config(LLM 컨텍스트 한도에 맞춰 조정).
- **검증 포인트:** cites가 존재하는 문장의 인덱스가 [0, n_segments) 범위인지 assert. raw_output 항상 보존.

## 4-9. M9 AAR 평가 (v2 16~17장)

- **입력:** report.json, segments.json, queries.jsonl(test), judge LLM
- **출력:** report_eval.json — {coverage_rate, groundedness_rate, per_sentence, per_gt_segment}
- **핵심 함수:**

```
def judge_coverage(report, gt_seg_idx, judge_llm) -> bool
    # "리포트가 이 세그먼트 내용을 언급했는가" 이진 판정 [v2 16-1]
def judge_grounded(sentence, cited_segments, judge_llm) -> bool
    # G-Eval식 3단계 CoT: ①문장 요약 → ②인용 seg 요약 → ③일치 판정 [v2 16-4]
    # 프롬프트에 "확신 없으면 false로 보수 판정" 명시 [v2 17-4 원칙]
def eval_report(report, segments, queries) -> ReportEval
    # cites==[] 문장은 judge 호출 없이 자동 ungrounded [v2 15-1]
```

- **judge 모델 규정 (v2 17-6 우선순위):** config의 `judge_model`은 `report_model`과 다른 패밀리를 1순위로 한다. 동일 모델 사용 시 config에 `same_model_judge: true`를 명시적으로 켜야 실행되며(무의식적 동일 사용 방지), 이 경우 사람 스팟체크 샘플(기본 20문장)을 자동 추출해 `human_check_sample.json`으로 내보낸다.

# 5. 모듈 간 계약 요약과 실행 순서

```
M1 → M2 → M3 → M4  (영상별 인덱싱, 3~4주차)
                └→ M5 ← queries.jsonl
                    ├→ M6 (dev grid search → test 평가, 6~10주차)
                    └→ M7 (데모, 9·12주차)
M3 산출(segments.json) → M8 → M9  (AAR, 8주차 이후·GPU 확인 후)
```

계약 위반 시 동작: 각 모듈은 시작 시 입력 파일 스키마를 검증하고, 필수 필드 누락이면 어떤 모듈을 먼저 실행해야 하는지 명시한 에러로 즉시 종료한다. 예: M4가 caption 누락을 발견하면 "run m3_generate.py first".

# 6. config.yaml — 전역 고정값

실험 재현성의 단일 진실 공급원. 보고서의 "실험 설정" 절은 이 파일을 그대로 옮겨 적는다 (v2 9-1).

```
seg_len_sec: 5
frame_sample_fps: 3
static_threshold: 0.05        # motion_score 기준, dev에서 1회 보정 후 고정
gaussian_sigma: 1.0
stt_model: "whisper-large-v3"
caption_model: "Qwen2.5-VL-7B-Instruct"   # 메모리 부족 시 3B
caption_prompt: "이 장면을 한 문장의 한국어로 객관적으로 묘사하라. ..."
embed_model: "KURE"           # dev에서 BGE-M3와 비교 후 확정 [v2 8-5]
alpha_grid: [0.0, 0.1, ..., 1.0]
alpha_select_metric: "hit@5"
alpha_tiebreak: "larger"      # 동률 시 자막 우선 [v2 9-1(a)]
eval_k: [1, 5, 10]
iou_thresholds: [0.5, 0.3]    # 보조지표
report_model: "Qwen2.5-Instruct"    # GPU 확인 후 확정
judge_model: null             # report_model과 다른 패밀리 지정 [v2 17-6]
same_model_judge: false
map_chunk_size: 60
human_check_n: 20
```

# 7. 주차 일정 매핑

| 모듈 | 주차 | 완료 기준 (Definition of Done) |
| --- | --- | --- |
| M1·M2 | 3주차 | 수집 영상 전체에 segments.json + frames 생성, 검증 포인트 통과 |
| M3·M4 | 4주차 | subtitle/caption/임베딩 완성, queries.jsonl 라벨링 완료 |
| M5 + baseline | 6주차 | α=1.0 검색 동작, dev 1차 성능 측정 |
| M5 proposed + M6 | 7~8주차 | grid search 완료, α 고정 |
| M7 통합 | 9주차 | mp4 업로드→검색→점프 end-to-end (중간발표) |
| M6 최종 | 10주차 | eval_test.json + 유형별 분석 표 |
| M8·M9 | 8주차 착수~11주차 | GPU 확인 후. report_eval + 사람 스팟체크 |
| 고도화 | 11주차 | 세그먼트 길이·정적 threshold·프롬프트 다양화 ablation |

*비고: M8·M9는 4순위이므로 M5·M6 일정과 충돌 시 뒤로 미룬다. 단 M9의 judge 모델 분리 여부(GPU)는 8주차 전에 튜터와 확정해야 config를 잠글 수 있다.*

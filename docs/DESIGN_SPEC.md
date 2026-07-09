**모듈별 상세 설계서 (v1.1)**

*영상 장면 검색 및 AAR 보고서 자동 생성 시스템 — API·입출력·데이터 스키마 명세*

구현가이드 v2(0~17장)의 확정 로직을 코드 수준 계약으로 환원한 문서. 이 문서와 구현가이드 v2가 충돌하면 v2가 우선하며, 충돌 발견 시 본 문서를 수정한다.

표기 규약: **[예정]** 태그가 붙은 항목은 설계 확정·구현 전 상태다. 태그 없는 항목은 현행 코드와 일치해야 하며, 불일치 발견 시 즉시 문서 또는 코드를 수정한다(2026-07-09 정합성 감사 이후 유지 원칙).

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
      "motion_score": 0.183,         // M2: 차분 RMS(픽셀 수로 정규화한 L2) 평균 (판정 근거 기록)
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

Whisper 발화 [t0, t1]이 겹치는 시간이 0초를 초과하는 **모든** 세그먼트의 `subtitle`에 해당 문장을 중복 귀속한다(발화가 길면 3곳 이상 세그먼트에 걸쳐 중복될 수 있다). "더 많이 걸친 세그먼트"는 이 겹침 세그먼트 집합에 자동으로 포함되므로 원래 취지를 상회 충족하며, 검색 recall을 우선한 설계다 — 어느 세그먼트에서 질의해도 hit되어야 하기 때문이다. 구현은 발화별 [t0, t1]과 각 세그먼트 [start, end]의 겹침 길이(`min(t1, end) - max(t0, start)`)가 0보다 큰지로 판정한다.

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
  "raw_output": "...",                // LLM 원문 (파싱 실패 검증용 보존)
  "map_raw_outputs": ["...", "..."]   // map-reduce 경로에서 chunk별 원문 보존(단일 호출이면 [])
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
    # diffs = RMS(frame[i]-frame[i-1])  # L2 norm을 픽셀 수로 정규화한 RMS —
    #   해상도 독립, static_threshold 절대값이 유효하려면 필수
    # → gaussian_filter(sigma) → argmax+1
def is_static(motion_score: float, threshold: float) -> bool
    # True면 rep_frame = 중간 프레임으로 fallback  [v2 2장 주의]
```

- **확정 로직:** 정적 판정 시에도 캡션은 생성한다(M3). 캡션을 버리는 것이 아니라 M5에서 점수를 치환하는 것이 확정 처방이다 (v2 8-4). M2는 플래그만 기록한다.
- **샘플 수집 방식 (2026-07-09 확정):** 세그먼트별 랜덤 시크 대신 영상 1회 순차 디코딩(`sample_segments_sequential`)으로 샘플 프레임을 수집한다. OpenCV POS_MSEC 시크의 실측 의미론(프레임 `floor(t*fps+0.5)` 반환)을 재현해 시크 방식과 동일한 프레임을 채택하며, 두 실영상(31·314세그먼트)에서 motion_score(|Δ|<1e-6)·is_static·t_rep 완전 일치가 검증됐다. 대표 프레임 jpg 저장만 세그먼트당 1회 시크. 샘플링 방식을 다시 바꾸는 구현은 같은 동등성 검증을 통과해야 한다.
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
    # 3-2 오버랩 귀속 규칙 구현. 겹치는 모든 세그먼트에 중복 허용
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
- **출력:** 랭킹 리스트 `[(idx, score, start, end), ...]`
- **확정 시그니처와 로직 (이 순서를 어기는 구현은 리젝):**

```
def search(query: str, video: VideoIndex, alpha: float, cfg: dict) -> list[Result]:
    q = embed_texts([query], cfg["embed_model"])[0]
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
- **raw 통계 동반 반환 (2026-07-09 추가):**

```
def search_with_stats(query, video, alpha, cfg) -> tuple[list[Result], dict]
    # search와 동일 랭킹 + 정규화 '이전' raw 코사인 통계:
    # {"raw_sub_max", "raw_sub_mean", "raw_cap_max", "raw_cap_mean"}
    # search(...)는 search_with_stats(...)[0] — 랭킹 계약 불변(테스트로 고정)
```

  근거: per-query min-max는 무관련 질의도 최고점을 1.0으로 끌어올려 "관련 없음" 신호를 지운다(실측: 유관 질의 raw_sub_max ≈ 0.62 vs 무관 질의 ≈ 0.47). raw 통계는 사용자에게 노출하지 않고 8-2의 abstention 임계값 설계 데이터로만 축적한다. 웹 서버(M7-W)는 매 질의를 `results/search_log.jsonl`에 1줄 append한다(스키마는 8-2, 로깅 실패는 무시 — 검색을 죽이지 않는다).

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
def derive_gt_seg_idx(gt_start, gt_end, n_segments, seg_len: int) -> list[int]
    # (gt_start, gt_end, n_segments, seg_len) → 1초 이상 겹치는 세그먼트 전부,
    # 없으면 최대 겹침 세그먼트 1개를 보장 [3-3]
```

- **실행 순서 강제:** ① dev로 grid_search_alpha → alpha_search_dev.json 저장 → ② test 평가는 그 α만 사용. M6는 test 질의로 α를 재탐색하는 코드 경로를 갖지 않는다(누수 원천 차단, v2 9-1).
- **검증 포인트:** dev/test에 같은 video_id가 없는지 로드 시 assert.
- **[예정] α 안정화:** M6 정식 실행(60질의) 전에 8-1의 부트스트랩 CI·선택 지표 변경을 반드시 적용한다. 현행 hit@5 단독 선택은 소표본에서 α*가 요동함이 실측됐다(8-1 참조).

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
    # 줄(line) 단위로 분리해 각 줄을 후보 문장으로 처리(빈 줄 제외, 선행 "-" 제거).
    # 문장 내 인용은 정규식 r"seg#(\d+)"로 전량 findall(중복 제거 후 정렬).
    # 반복그룹 정규식 r"\[seg#(\d+)(?:,\s*seg#(\d+))*\]"은 Python re가 반복 그룹의
    # 마지막 매치만 캡처하는 특성 때문에 인용 3개 이상인 문장에서 중간 값이
    # 유실된다 — 사용 금지. 인용이 없는 문장은 cites=[]
def generate_report(segments, llm, chunk_size: int = 60) -> Report
```

- **map-reduce 발동 조건:** n_segments > chunk_size일 때만 map-reduce, 이하면 단일 호출. chunk_size는 config(LLM 컨텍스트 한도에 맞춰 조정).
- **검증 포인트:** cites가 존재하는 문장의 인덱스가 [0, n_segments) 범위인지 assert. raw_output 항상 보존.

## 4-9. M9 AAR 평가 (v2 16~17장)

- **입력:** report.json, segments.json, queries.jsonl(test), judge LLM
- **출력:** report_eval.json — {video_id, judge_model, coverage_rate, groundedness_rate, per_sentence, per_gt_segment}
  - `per_sentence` 항목: {sent_id, cites, grounded, judge_parse_ok} — `judge_parse_ok`(bool)는 judge 응답에서 판정값 파싱 성공 여부(truncation 편향 진단용). cites==[]인 문장은 judge 호출 없이 grounded=false, judge_parse_ok=true로 기록된다.
- **핵심 함수:**

```
def judge_coverage(report, gt_seg_idx, judge_llm) -> bool
    # "리포트가 이 세그먼트 내용을 언급했는가" 이진 판정 [v2 16-1]
def judge_grounded(sentence, cited_segments, judge_llm) -> bool
    # G-Eval식 3단계 CoT: ①문장 요약 → ②인용 seg 요약 → ③일치 판정 [v2 16-4]
    # 프롬프트에 "확신 없으면 false로 보수 판정" 명시 [v2 17-4 원칙]
def eval_report(report, segments, queries) -> ReportEval
    # cites==[] 문장은 judge 호출 없이 자동 ungrounded [v2 15-1]
def check_judge_config(cfg: dict) -> None
    # judge_model 미지정, 또는 report_model과 동일한데 same_model_judge 미설정 시
    # fail-fast [v2 17-6]
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
seed: 42

stt_model: "large-v3"         # faster-whisper. 부족 시 "turbo"
stt_language: "ko"

caption_model: "Qwen/Qwen2.5-VL-3B-Instruct"  # 서버(대용량 VRAM)에서는 Qwen2.5-VL-7B-Instruct
vlm_4bit: true                # 서버(대용량 VRAM)에서는 false (로컬 6GB VRAM은 true, NF4, 기존 caption 실험 검증)
vlm_max_pixels: 602112        # 768*28*28 (기존 실험: 비전 토큰 폭증 방지)
vlm_rep_penalty: 1.1          # 1.3은 3B-4bit에서 문자혼입(한자·가나) 유발 확인(2026-07-09 rp 실험: 혼입 8/10→3/10, 반복 붕괴는 1.0에서도 미발생) — 보험으로 1.1
caption_prompt: "이 장면을 한 문장의 한국어로 객관적으로 묘사하라. 화면에 보이지 않는 것은 쓰지 마라."

embed_model: "nlpai-lab/KURE-v1"   # dev에서 BAAI/bge-m3와 비교 후 확정 [v2 8-5]
embed_batch_size: 32

alpha_grid: [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
alpha_select_metric: "hit@5"
alpha_tiebreak: "larger"      # 동률 시 자막 우선 [v2 9-1(a)]
eval_k: [1, 5, 10]
iou_thresholds: [0.5, 0.3]    # 보조지표

report_model: "Qwen/Qwen2.5-7B-Instruct"
llm_4bit: true                # 서버(대용량 VRAM)에서는 false (로컬 6GB VRAM 대응)
judge_model: null             # report_model과 다른 패밀리 지정 [v2 17-6]
same_model_judge: false
map_chunk_size: 60
map_chunk_overlap: 5
human_check_n: 20

paths:
  data: "data"
  work: "work"
  results: "results"
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

**진행 현황 (2026-07-09, 3주차):** M1~M9 전 모듈 + 웹 UI(M7-W) 구현·테스트 완료 — 표 기준 약 6주 선행. 잔여 병목은 구현이 아니라 (a) 질의 라벨링(18/60), (b) judge 모델용 GPU 확정(튜터), (c) 8장의 고도화 설계 실행이다. 일정표는 원 계획 기록으로 보존한다.

# 8. 고도화 설계 (v1.1 추가 — 전 항목 [예정], 구현 착수 시 태그 제거)

정합성 감사(docs/설계점검_2026-07-09.md)의 HIGH-3·MEDIUM-4~6과 ablation 계획(docs/ablation_plan_draft.md)의 미결 결정 3건을 계약 수준으로 확정한다. 공통 원칙: **현행 계약(1~7장)을 깨는 항목은 없다** — 전부 추가 경로 또는 config 확장이며, baseline/proposed 대칭성과 dev-only 탐색 원칙(9-1)을 상속한다.

## 8-1. α 안정화 (M6 정식 실행 전 필수)

**문제 실측:** dev 12질의(영상 1개)에서 α*가 캡션 버전에 따라 0.5↔0.3 요동, test 전이 불량. 원인 두 가지 — ① hit@5는 소표본에서 계단형(동률 다발)이라 선택이 불안정, ② dev가 영상 1개라 영상 특성이 α에 새어 들어감.

**처방 (a) 선택 지표 변경:** `alpha_select_metric` 기본값을 `"hit@5"` → `"mrr"`로 변경. MRR은 연속 지표라 α 간 순서가 계단에 덜 갇힌다. hit@1/5/10은 계속 산출·보고하되 선택에는 쓰지 않는다. 동률 tiebreak(`larger`, 자막 우선)는 유지.

**처방 (b) 부트스트랩 신뢰구간 — 쌍체 차이(paired difference) 방식:** grid_search_alpha가 α별 per-query 점수를 보존하고, **질의 단위로 하나의 재표집 인덱스를 뽑아 모든 α에 공유 적용**한 뒤(B=2000, config `seed` 고정), α마다 per-query `지표(α) − 지표(α_best_point)` **차이**를 부트스트랩해 95% CI를 계산한다. **선택 규칙: 차이의 CI가 0을 포함하는 α만 동률 집합에 넣고 tiebreak를 적용한다.** 주변(marginal) CI 겹침 판정은 금지 — 모든 α가 같은 dev 질의로 평가되어 질의 난이도를 통해 강하게 상관하므로, 상관을 무시한 주변 CI는 차이의 CI보다 훨씬 넓어 소표본에서 동률 집합을 그리드 전체로 팽창시키고, 그 결과 tiebreak(`larger`)가 α*를 1.0(=baseline)으로 끌어 proposed 우위 판정을 스스로 훼손한다. 쌍체 차이 CI는 "α*가 baseline(α=1.0)과 통계적으로 구분되는가"에도 같은 방식으로 답한다(α=1.0의 차이 CI를 그대로 보고). alpha_search_dev.json 스키마 확장:

```
{
  "select_metric": "mrr",
  "bootstrap": {"B": 2000, "seed": 42, "method": "paired-diff"},
  "alpha_best_point": 0.5,          // 점 추정 1위 (차이의 기준점)
  "per_alpha": [
    {"alpha": 0.5, "mrr": 0.63, "hit@5": 0.83,
     "diff_vs_best_ci95": [0.0, 0.0],       // 기준점 자신은 [0,0]
     "per_query_rr": [1.0, 0.5, ...]},      // 재표집 재현용 원자료
    {"alpha": 0.6, "mrr": 0.61, "hit@5": 0.83,
     "diff_vs_best_ci95": [-0.09, 0.04]},   // 0 포함 → 동률 집합
    ...
  ],
  "tie_set": [0.4, 0.5, 0.6],      // 차이 CI가 0을 포함한 α들
  "alpha_star": 0.6                 // tie_set에 tiebreak 적용 결과
}
```

보고 규칙: 선택은 MRR로 하되 헤드라인 표에는 hit@5·MRR을 항상 병기하고, 두 지표의 우열이 갈리면 per_query 원자료로 사례 해석을 덧붙인다(지표 간 불일치를 숨기지 않는다).

**처방 (c) dev 다양화:** dev 영상을 3개로 확대(확정치는 8-6의 단일 표를 따른다). 영상 간 α* 편차를 alpha_search_dev.json에 영상별 분해로 병기해 "α가 영상 특성의 함수인지"를 보고 자료로 남긴다.

config 예정 키: `alpha_select_metric: "mrr"`(기존 키 값 변경), `bootstrap_B: 2000`(신규). §6에는 구현 시점에 반영한다(문서-코드 동기 원칙).

## 8-2. 무관련 질의 판정 — abstention (데이터 축적 후 발동)

**문제:** 4-5의 정규화는 "이 영상에 관련 구간이 없다"는 신호를 구조적으로 지운다. 무관련 질의("에어컨수리")도 0.9대 확신 점수가 표시된다.

**현행(구현 완료, HIGH-2):** search_with_stats + `results/search_log.jsonl` 로깅. 스키마(1질의 1줄, ensure_ascii=False):

```
{"ts": 1720..., "video_id": "...", "query": "...", "alpha": 0.5,
 "raw_sub_max": 0.62, "raw_sub_mean": 0.41,
 "raw_cap_max": 0.55, "raw_cap_mean": 0.38,
 "top1_idx": 27, "top1_score": 1.0}
```

**임계값 결정 절차 [예정]:** ① 60질의 라벨 완료 후, 유관 질의의 raw_sub_max 분포(dev)와 무관 질의 분포를 대조한다. 무관 질의는 **별도 파일 `data/queries/queries_negative.jsonl`**(대상 영상과 무관함이 자명한 질의 20개, gt 없음)로 관리 — 기존 지표 계산에 절대 섞지 않으며, gt·split 필수 필드를 검증하는 기존 질의 로더(M6 load_queries)와 스키마가 비호환이므로 **그 로더를 거치지 않는 전용 경로로만 읽는다**. ② 두 분포의 분리도를 보고 τ(raw_sub_max 기준, 필요시 raw_cap_max 병용)를 dev에서 결정한다. **τ 확정 후 dev 유관 질의 중 τ 미달 비율(오배제율, false-abstention)을 반드시 함께 보고**하고, n≈20 대조의 CI 폭도 병기한다 — "자명히 무관"한 질의로만 캘리브레이션하면 미묘한 무관련에 과대허용되는 selection bias가 있음을 한계로 명시. ③ **동작 계약: 랭킹·지표·기존 API 응답은 불변.** τ 미달 시 UI 표시 계층에서만 "이 영상에 관련 구간이 없을 수 있습니다" 배너를 결과 위에 추가한다(결과 은폐 금지 — 연구 도구로서 오판 사례 관찰이 필요).

**주의:** τ는 임베딩 모델의 anisotropy에 종속(KURE-v1 실측 기준). embed_model 교체(BGE-M3 비교 등) 시 재캘리브레이션 필수 — meta.json의 embed_model과 τ를 쌍으로 기록한다.

## 8-3. 캡션 생성 상한·후처리 (MEDIUM-4·5, ablation 실험 3의 전제)

**(a) max_new_tokens config화:** 현행 m3의 `max_new_tokens=128` 하드코딩을 config 키 `vlm_max_new_tokens: 128`로 이동(기본값 유지 — 동작 불변). 실험 3에서 192~256 상향을 변형 축으로 포함. 근거: 캡션 29% 잘림 의심 실측 — 상세형 프롬프트(P1)가 이 상한에서 confound된다.

**(b) 미완결 문장 절단:** 생성 텍스트가 문장 중간에서 끊긴 경우 마지막 완결 문장 경계(。.!?…)까지만 저장하는 후처리. 절단 발생 여부를 세그먼트별 로그로 남긴다(빈도가 높으면 상한 재조정 신호).

**(c) 혼입 문자 정규화:** 잔여 한자·가나 혼입(rp와 무관한 모델 고유 어휘, 예: "카모フラ주" 26건)은 CPU 정규화 테이블로 교정한다. **저장 계약: 정규화는 M3 저장 시 적용하되 원문을 `caption_raw` 필드로 보존**(raw 보존 원칙 — M8 raw_output과 일관). 기존 산출물에는 재캡션 없이 후처리 스크립트 + M4 재임베딩(분 단위)만으로 적용 가능해야 한다.

## 8-4. 결합 임베딩 제3 arm (MEDIUM-6, 시간 여유 시)

가이드 3장 원안(자막+캡션을 한 텍스트로 임베딩) vs 현행(분리 임베딩 + α 결합)의 정량 비교용.

- M4 확장: config `emb_joint: true`일 때 `emb_joint.npy` 추가 산출 — 입력 텍스트는 `"자막: {subtitle}\n장면: {caption}"` 템플릿 고정(빈 자막도 템플릿 유지 — 대칭성).
- M5 확장: `search_joint(query, video)` — s_joint 코사인 → minmax 단독 사용(치환·α 없음, 이 arm의 정의상 결합이 임베딩 내부에서 일어남).
- 비교는 dev에서만, 결과는 eval에 `"joint"` arm으로 병기. **α 결합 경로와 코드 공유 강제 없음** — 연산 구조 자체가 다르므로 별도 함수가 정당하나, 정규화 함수(minmax)와 지표 함수는 공유한다. 주: 4-5의 "별도 코드 경로 금지"는 baseline↔proposed **대칭성**을 위한 규칙이다 — joint arm은 통제 비교가 아닌 방법 비교이므로 이 금지의 적용 대상이 아니다(모순 아님).

## 8-5. Ablation 실행 규약 (ablation_plan_draft.md [검토 필요] 3건 확정)

**(1) 변형 실험 산출물 격리 — paths.work·paths.results 동시 분리를 표준으로 한다.** 변형마다 config 사본(`config_{variant}.yaml`)을 만들고 `paths.work`와 `paths.results`를 함께 교체한다(예: `work_seg3/` + `results_seg3/`). work만 바꾸면 인덱싱 산출물(M1~M4)은 격리되지만 M6가 고정 파일명(`alpha_search_dev.json`, `eval_test.json`)으로 기록하고 M7-W가 `search_log.jsonl`에 append하므로 변형 실행이 기준 실행의 결과 파일을 덮어쓴다. 근거: 기존 모듈 무수정으로 동작하고, 전례 2회(work_rp13/, work_bge/)로 검증됐다(당시는 M6 미실행이라 results 충돌이 드러나지 않았을 뿐이다). video_id에 suffix를 붙이는 방식은 기각 — M5·M7의 video_id 기반 경로 조립과 얽히고, data/videos/{video_id}.mp4 원본 참조가 깨진다. queries.jsonl의 video_id도 불변으로 유지된다.

**(2) static_threshold 스윕 — config 스키마 불변, 평가 시점 재판정.** config는 절대값 1개(`static_threshold`)를 유지한다(6장 "dev에서 1회 보정 후 고정" 계약). 스윕 메커니즘: **M5·M6 공통 진입점인 `VideoIndex.load`에 `static_threshold: float | None = None` 인자를 추가**해, 지정 시 저장된 `is_static` 대신 `motion_score < thr`로 static_mask를 재계산한다(이때 segments.json 로드의 require에 motion_score 추가). M6 CLI의 `--static-threshold`가 이 값을 인덱스 로드까지 관통시키되, **스윕 실행은 M6 main(dev 탐색+test 평가)이 아니라 dev 질의만으로 evaluate()를 호출하는 스윕 스크립트(또는 M6 `--dev-only` 모드)로 한다** — threshold 후보마다 test가 평가되면 dev-only 원칙(v2 9-1, 8-6) 위반이다. 스윕 결과는 고정 파일명(alpha_search_dev.json 등)을 덮어쓰지 않도록 threshold별로 단일 파일(예: `results/static_sweep_dev.json`)에 누적 기록한다. segments.json 저장 필드는 건드리지 않아 멱등 안전. 분위수(P10/P25/P50)는 **후보값 산출 방법론**일 뿐 config에 들어가지 않는다(dev 분포에서 절대값으로 환산해 스윕). 알려진 한계를 결과에 명시: rep_frame·캡션은 thr=0.05 기준 산출물이라 재판정과 비대칭.

**(3) 실험 3(프롬프트)의 부분 재실행 — M3에 `--captions-only` 옵션 추가.** Whisper 전사·자막 귀속(M3(a))을 건너뛰고 caption만 재생성한다. 절차 계약: ① 대상 work 디렉터리에 subtitle·rep_frame이 채워진 segments.json과 frames/가 **선재해야 한다** — (1)의 변형 디렉터리는 비어 있으므로 기준 `work/{video_id}/`의 segments.json·frames/를 복사해 seeding하는 단계가 선행된다(audio.wav·npy는 불필요). ② `--captions-only`는 **caption 필드만 초기화한 뒤 재생성**한다 — 현행 캡션 생성이 caption 존재 시 건너뛰는 resume 동작이므로, 초기화 없이는 no-op가 된다. subtitle·rep_frame은 불변. ③ 현행 `--force`는 전체 재실행이므로 실험 3에서 사용 금지(Whisper ~수십 분 낭비 + 자막 재현성 위험). 멱등성은 greedy 디코딩(do_sample=False) 전제에서 성립.

## 8-6. 평가 프로토콜 확정치

- **데이터 규모 단일 표** (8-1(c)·ablation 계획이 전부 이 표를 파생 참조한다 — 다른 수치 인용 금지):

| | 영상 수 | 질의 수 | 유형 구성 |
|---|---|---|---|
| dev | 3 | 36 | 자막형/장면형/복합형 12/12/12 |
| test | 2 | 24 | 자막형/장면형/복합형 8/8/8 |
| 합계 | 5 | 60 | 20/20/20 (전체 질의 구성 기준) |

  주의: 3-4 eval_test.json의 `n_queries`는 **test 질의만의 카운트**이므로 실제 파일에는 `total: 24, 8/8/8`로 기록된다 — 예시의 60/20은 전체 구성 서술이다. 현재 dev 1영상 12질의 / test 1영상 6질의 (18/60) — 추가 라벨링 요건: dev 영상 2개(+24질의), test 영상 1개(+18질의). ablation 실험 1(세그먼트 길이)은 비용 제약상 **dev 3영상 중 1~2개로 축소 실행을 허용**한다(전량이 원칙이 아님을 결과 표에 명시). 유형별 셀 표본 20(유형별 분해의 보고 가치 기준)은 dev+test 합산에서 성립한다.
- **무관 질의 20개**는 위 60개와 별도(8-2, queries_negative.jsonl) — Hit/MRR 계산에서 완전히 제외.
- **재측정 트리거:** 60질의 확보 시점에 ① static_threshold 재실측(8-5(2) 방식, 사전 실측은 ablation_plan_draft 2-4-1), ② α 재탐색(8-1 적용 후), ③ KURE vs BGE-M3 비교(work_bge/ 인덱스 기존 산출 재활용)를 일괄 실행한다 — 세 건 모두 dev-only.
- **베이스라인 고정:** 위 재측정 전까지 데모·중간발표 수치는 "α=0.5(잠정), thr=0.05, KURE-v1, 18질의 예비 평가" 표기를 유지한다 — 잠정치가 확정치처럼 인용되는 것을 방지.

# 9. 변경 이력

- **v1.1 (2026-07-09):** 정합성 감사 반영(3-2 오버랩 규칙 재기술, 4-2 RMS 명시, §6 config 동기화, 4-6 derive_gt_seg_idx·4-9 check_judge_config 등재, 스키마 필드 보강). M2 순차 디코딩 확정(4-2), M5 search_with_stats 등재(4-5). 8장 신설: α 안정화·abstention·캡션 후처리·emb_joint·ablation 실행 규약·평가 프로토콜 확정치. [예정] 태그 규약 도입.
- **v1 (2026-07-07):** 최초 작성.

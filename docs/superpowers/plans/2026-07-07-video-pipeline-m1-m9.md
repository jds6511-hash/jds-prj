# 영상 장면 검색 파이프라인 (M1~M9) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** docs/IMPLEMENTATION_GUIDE.md(v2)·docs/DESIGN_SPEC.md 계약대로 M1(전처리)~M9(AAR 평가) 9개 CLI 모듈을 구현한다. baseline(α=1.0) vs proposed(α 결합) 검색 비교와 AAR 리포트 생성·평가까지.

**Architecture:** 모듈 간 통신은 파일(JSON/NPY)로만. 각 모듈은 `python src/mN_*.py --config config.yaml --video-id {id}` 독립 CLI. GPU 의존부(Whisper·VLM·임베딩·LLM)는 함수 주입/지연 로딩으로 분리해 순수 로직만 pytest로 TDD한다.

**Tech Stack:** Python 3.12, ffmpeg, OpenCV, scipy, faster-whisper, transformers+bitsandbytes(Qwen2.5-VL), sentence-transformers(KURE/BGE-M3), numpy, Gradio, pytest

**기존 코드 재사용·수정 결정 (사용자 요청 "기존에 만든 것 참고, 수정사항 반영"):**

| 기존 자산 | 결정 |
|---|---|
| `stt_test/stt_local.py` | 전사부 차용: GPU 폴백 사다리(fp16→int8_float16→cpu), `condition_on_previous_text=False` + `hallucination_silence_threshold=1.0`(한국어 환각 방지), `vad_filter 금지`(대사 잘림), 전사 캐시, cuBLAS DLL 주입, atomic_write_json. **화자분리(pyannote)는 파이프라인에 불필요 → 제외** |
| `caption/qwen_caption_test/test_caption.py` | VLM 로딩 차용: 4-bit NF4 옵션(로컬 6GB VRAM), max_pixels 제한, do_sample=False, repetition_penalty(기존 rp13 실험 → 1.3 채택), 프레임별 에러 격리, resume. **import 시 모델 로드 → 함수 안 지연 로딩으로 구조 변경** |
| `caption/.../extract_frames.py` | 중간 프레임만 추출 → **M2는 SMART STC(3fps 샘플·차분 L2·가우시안 평활·argmax)로 교체**, 중간 프레임은 정적 fallback으로만 |
| `caption/.../prompts.py` | 다중 프롬프트 실험 → config의 `caption_prompt` 1종 고정(DESIGN_SPEC 4-3). 다중 프롬프트는 11주차 ablation |
| 모델명 구체화 | KURE → `nlpai-lab/KURE-v1`, BGE-M3 대안 → `BAAI/bge-m3`, VLM → `Qwen/Qwen2.5-VL-7B-Instruct`(서버) / `Qwen/Qwen2.5-VL-3B-Instruct`+4bit(로컬 6GB) |

## Global Constraints (DESIGN_SPEC·PROJECT_RULES 절대 규칙)

- 검색 연산 순서 고정: 코사인 → 각각 per-query min-max(단일 영상 범위) → 정적 s_cap_norm←s_sub_norm 치환 → α 가중합. 순서 변경 금지
- baseline = `search(α=1.0)` 특수 경우. 별도 코드 경로 금지
- α grid search는 dev셋 전용. test로 α를 고르는 코드 경로 자체를 만들지 않음. 동률 시 α 큰 값
- minmax에서 `max-min < 1e-9` → 0 벡터 반환
- 자막·캡션·질의 임베딩 모델 동일, `embed_model`은 config 한 곳에서만
- dev/test는 video_id 단위 분리, 로드 시 assert
- 세그먼트: `start = idx*5` 불변식, `end = min(start+5, duration)`, n_segments == ceil(duration/5)
- 무발화 세그먼트 subtitle="" 그대로 임베딩 (특별 처리 금지)
- 정적 세그먼트도 캡션은 생성 (M5에서 점수만 치환)
- cites==[] 문장은 저장하되 M9에서 자동 ungrounded. raw_output 항상 보존
- 클라우드 API 금지, 전부 온프레미스
- 모든 모듈 멱등, 공통 옵션 `--force`, 스키마 위반 시 "run mX first" fail-fast
- gt_seg_idx: 정답 구간과 1초 이상 겹치는 모든 세그먼트, 최소 1개(최대 겹침) 보장
- 캡션 언어 = 질의 언어 = 한국어

---

### Task 1: 프로젝트 스캐폴드 + common.py (config·segments 계약)

**Files:**
- Create: `.gitignore`, `config.yaml`, `requirements.txt`, `src/common.py`, `tests/conftest.py`
- Test: `tests/test_common.py`

**Interfaces:**
- Produces: `common.load_config(path) -> dict`, `common.atomic_write_json(path, obj)`, `common.work_dir(cfg, video_id) -> Path`, `common.load_segments(path, require: list[str] = []) -> dict`(스키마 검증 fail-fast), `common.save_segments(path, doc)`
- 이후 모든 태스크가 이 함수들을 사용한다.

- [ ] **Step 1: git init + 스캐폴드 파일 작성**

```bash
cd c:/Users/UserK/Desktop/prj && git init
```

`.gitignore`:
```
work/
results/
data/videos/
__pycache__/
*.npy
*.mp4
*.wav
.env
.pytest_cache/
```

`requirements.txt`:
```
numpy
scipy
opencv-python
pyyaml
pytest
faster-whisper
transformers>=4.49
accelerate
bitsandbytes
qwen-vl-utils
sentence-transformers
gradio
```

`config.yaml` (DESIGN_SPEC 6장 + 기존 실험 채택값):
```yaml
seg_len_sec: 5
frame_sample_fps: 3
static_threshold: 0.05        # motion_score 기준, dev에서 1회 보정 후 고정
gaussian_sigma: 1.0
seed: 42

stt_model: "large-v3"         # faster-whisper. 부족 시 "turbo"
stt_language: "ko"

caption_model: "Qwen/Qwen2.5-VL-7B-Instruct"  # 로컬 6GB VRAM이면 3B로 교체
vlm_4bit: false               # 로컬 6GB VRAM이면 true (NF4, 기존 caption 실험 검증)
vlm_max_pixels: 602112        # 768*28*28 (기존 실험: 비전 토큰 폭증 방지)
vlm_rep_penalty: 1.3          # 기존 rp13 실험 채택 (반복 붕괴 억제)
caption_prompt: "이 장면을 한 문장의 한국어로 객관적으로 묘사하라. 화면에 보이지 않는 것은 쓰지 마라."

embed_model: "nlpai-lab/KURE-v1"   # dev에서 BAAI/bge-m3와 비교 후 확정 [v2 8-5]
embed_batch_size: 32

alpha_grid: [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
alpha_select_metric: "hit@5"
alpha_tiebreak: "larger"      # 동률 시 자막 우선 [v2 9-1(a)]
eval_k: [1, 5, 10]
iou_thresholds: [0.5, 0.3]

report_model: "Qwen/Qwen2.5-7B-Instruct"
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

`tests/conftest.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
```

- [ ] **Step 2: 실패하는 테스트 작성** — `tests/test_common.py`

```python
import json, pytest
from pathlib import Path
import common

def _doc(n=3, dur=14.0, extra=None):
    segs = []
    for i in range(n):
        s = {"idx": i, "start": i * 5, "end": min(i * 5 + 5, dur)}
        if extra:
            s.update(extra)
        segs.append(s)
    return {"video_id": "v1", "duration_sec": dur, "fps": 30.0,
            "n_segments": n, "segments": segs}

def test_load_segments_ok(tmp_path):
    p = tmp_path / "segments.json"
    common.atomic_write_json(p, _doc())
    doc = common.load_segments(p)
    assert doc["n_segments"] == 3

def test_load_segments_rejects_broken_idx(tmp_path):
    d = _doc(); d["segments"][2]["idx"] = 5          # 연속성 위반
    p = tmp_path / "segments.json"; common.atomic_write_json(p, d)
    with pytest.raises(ValueError, match="idx"):
        common.load_segments(p)

def test_load_segments_rejects_start_invariant(tmp_path):
    d = _doc(); d["segments"][1]["start"] = 7        # start = idx*5 위반
    p = tmp_path / "segments.json"; common.atomic_write_json(p, d)
    with pytest.raises(ValueError, match="start"):
        common.load_segments(p)

def test_load_segments_missing_field_names_module(tmp_path):
    p = tmp_path / "segments.json"; common.atomic_write_json(p, _doc())
    with pytest.raises(ValueError, match="m2_keyframe"):
        common.load_segments(p, require=["rep_frame"])
    with pytest.raises(ValueError, match="m3_generate"):
        common.load_segments(p, require=["caption"])

def test_atomic_write_and_config(tmp_path):
    p = tmp_path / "x.json"
    common.atomic_write_json(p, {"a": 1})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}
    cfg = common.load_config(Path(__file__).parents[1] / "config.yaml")
    assert cfg["seg_len_sec"] == 5 and cfg["alpha_tiebreak"] == "larger"
```

- [ ] **Step 3: 실패 확인** — Run: `python -m pytest tests/test_common.py -v` / Expected: FAIL (`ModuleNotFoundError: common`)

- [ ] **Step 4: 구현** — `src/common.py`

```python
"""공용 유틸: config 로드, 원자적 JSON 저장, segments.json 계약 검증 (DESIGN_SPEC 3-1)."""
import json, os
from pathlib import Path
import yaml

# 필드 → 그 필드를 채우는 모듈 (fail-fast 에러 메시지용, DESIGN_SPEC 5장)
FIELD_OWNER = {
    "rep_frame": "m2_keyframe.py", "is_static": "m2_keyframe.py",
    "motion_score": "m2_keyframe.py",
    "subtitle": "m3_generate.py", "caption": "m3_generate.py",
}


def load_config(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def work_dir(cfg: dict, video_id: str) -> Path:
    return Path(cfg["paths"]["work"]) / video_id


def atomic_write_json(path, obj) -> None:
    path = str(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_segments(path, require: list[str] | None = None) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} 없음 — run m1_preprocess.py first")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    segs = doc["segments"]
    if doc["n_segments"] != len(segs):
        raise ValueError(f"n_segments={doc['n_segments']} != len(segments)={len(segs)}")
    for i, s in enumerate(segs):
        if s["idx"] != i:
            raise ValueError(f"segments[{i}].idx={s['idx']} — idx는 0부터 연속 정수여야 함")
        if s["start"] != i * 5:
            raise ValueError(f"segments[{i}].start={s['start']} — start = idx*5 불변식 위반")
    for field in (require or []):
        missing = [s["idx"] for s in segs if field not in s]
        if missing:
            owner = FIELD_OWNER.get(field, "이전 모듈")
            raise ValueError(
                f"'{field}' 누락 세그먼트 {len(missing)}개 (예: idx {missing[:3]}) — run {owner} first")
    return doc


def save_segments(path, doc) -> None:
    atomic_write_json(path, doc)
```

- [ ] **Step 5: 통과 확인** — Run: `python -m pytest tests/test_common.py -v` / Expected: 5 PASS

- [ ] **Step 6: Commit**

```bash
git add .gitignore config.yaml requirements.txt src/common.py tests/
git commit -m "feat: 프로젝트 스캐폴드 + segments.json 계약 검증(common.py)"
```

---

### Task 2: M1 전처리 (오디오 추출 + 5초 세그먼트 분할)

**Files:**
- Create: `src/m1_preprocess.py`
- Test: `tests/test_m1.py`

**Interfaces:**
- Consumes: `common.*`
- Produces: `make_segments(duration_sec: float, seg_len: int = 5) -> list[dict]`, `extract_audio(video_path, out_wav, sr=16000) -> None`(ffmpeg), `get_video_info(video_path) -> tuple[float, float]`(duration, fps). 산출: `work/{id}/audio.wav`, `segments.json`(idx/start/end)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_m1.py`

```python
import math
from m1_preprocess import make_segments

def test_make_segments_basic():
    segs = make_segments(14.0)
    assert len(segs) == math.ceil(14.0 / 5) == 3
    assert [s["start"] for s in segs] == [0, 5, 10]
    assert segs[-1]["end"] == 14.0                    # end = min(start+5, duration)
    assert segs[0]["end"] == 5

def test_make_segments_exact_multiple():
    segs = make_segments(15.0)
    assert len(segs) == 3 and segs[-1]["end"] == 15.0

def test_make_segments_idx_contiguous():
    segs = make_segments(632.4)
    assert len(segs) == 127                            # ceil(632.4/5)
    assert all(s["idx"] == i and s["start"] == i * 5 for i, s in enumerate(segs))
    assert abs(segs[-1]["end"] - 632.4) < 1e-9
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_m1.py -v` / Expected: FAIL (import error)

- [ ] **Step 3: 구현** — `src/m1_preprocess.py`

```python
"""M1 전처리: mp4 → audio.wav(16kHz mono) + segments.json(idx/start/end). [DESIGN_SPEC 4-1]"""
import argparse, math, subprocess, sys
from pathlib import Path
import cv2
import common


def make_segments(duration_sec: float, seg_len: int = 5) -> list[dict]:
    segs = []
    for start in range(0, math.ceil(duration_sec), seg_len):
        segs.append({"idx": len(segs), "start": start,
                     "end": min(start + seg_len, duration_sec)})
    return segs


def get_video_info(video_path) -> tuple[float, float]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"영상 열기 실패: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    n_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return n_frames / fps, fps


def extract_audio(video_path, out_wav, sr: int = 16000) -> None:
    cmd = ["ffmpeg", "-y", "-i", str(video_path),
           "-vn", "-ac", "1", "-ar", str(sr), "-f", "wav", str(out_wav)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패:\n{r.stderr[-800:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    cfg = common.load_config(args.config)

    video = Path(cfg["paths"]["data"]) / "videos" / f"{args.video_id}.mp4"
    wdir = common.work_dir(cfg, args.video_id)
    wdir.mkdir(parents=True, exist_ok=True)
    seg_path = wdir / "segments.json"
    if seg_path.exists() and not args.force:
        print(f"이미 존재: {seg_path} (--force로 재생성)"); return

    duration, fps = get_video_info(video)
    extract_audio(video, wdir / "audio.wav")
    segs = make_segments(duration, cfg["seg_len_sec"])

    # 검증 포인트 [DESIGN_SPEC 4-1]
    assert len(segs) == math.ceil(duration / cfg["seg_len_sec"])
    assert abs(segs[-1]["end"] - duration) < 0.5

    common.save_segments(seg_path, {
        "video_id": args.video_id, "duration_sec": duration, "fps": fps,
        "n_segments": len(segs), "segments": segs})
    print(f"M1 완료: {len(segs)}개 세그먼트, duration={duration:.1f}s → {seg_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_m1.py -v` / Expected: 3 PASS

- [ ] **Step 5: 실제 영상 스모크** — 스파이더맨 예고편(가장 짧음)을 데이터 폴더로 복사 후 실행:

```bash
mkdir -p data/videos
cp "caption/[스파이더맨_ 브랜드 뉴 데이] 메인 예고편.mp4" data/videos/spiderman_trailer.mp4
python src/m1_preprocess.py --config config.yaml --video-id spiderman_trailer
```
Expected: `work/spiderman_trailer/audio.wav` + `segments.json` 생성, "M1 완료" 출력

- [ ] **Step 6: Commit**

```bash
git add src/m1_preprocess.py tests/test_m1.py
git commit -m "feat: M1 전처리 — 오디오 추출 + 5초 세그먼트 분할"
```

---

### Task 3: M2 대표 프레임 선택 (SMART STC 차용)

**Files:**
- Create: `src/m2_keyframe.py`
- Test: `tests/test_m2.py`

**Interfaces:**
- Consumes: `common.load_segments(require=[])`
- Produces: `select_rep_frame(frames: list[np.ndarray], sigma: float = 1.0) -> tuple[int, float]`(rep_idx, motion_score), `is_static(motion_score, threshold) -> bool`, `sample_frames(cap, start, end, fps_sample, video_fps) -> list[np.ndarray]`. 산출: `frames/seg_{idx:04d}.jpg`, segments.json에 rep_frame/is_static/motion_score

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_m2.py`

```python
import numpy as np
from m2_keyframe import select_rep_frame, is_static

def _frame(v):  # 단색 8x8 그레이 프레임 (float 0~1)
    return np.full((8, 8), v, dtype=np.float32)

def test_rep_frame_picks_most_dynamic():
    # 프레임 3→4 사이 변화가 가장 큼 → rep_idx는 diff argmax + 1 = 4
    frames = [_frame(v) for v in (0.0, 0.05, 0.1, 0.15, 0.9, 0.9, 0.9)]
    rep_idx, score = select_rep_frame(frames, sigma=0.0)  # sigma=0: 평활 없이 순수 검증
    assert rep_idx == 4
    assert score > 0

def test_static_segment_falls_back_to_middle():
    frames = [_frame(0.5)] * 7                        # 완전 정적
    rep_idx, score = select_rep_frame(frames)
    assert score == 0.0
    assert is_static(score, threshold=0.05)
    # 정적 판정 시 호출부에서 중간 프레임으로 fallback (rep_idx는 그대로 반환)

def test_single_frame_segment():
    rep_idx, score = select_rep_frame([_frame(0.3)])  # 마지막 짧은 세그먼트
    assert rep_idx == 0 and score == 0.0

def test_motion_score_scale_independent_of_size():
    # 픽셀 수로 정규화되어야 threshold(0.05)가 해상도 무관하게 유효
    small = [_frame(0.0), _frame(1.0)]
    big = [np.full((64, 64), 0.0, np.float32), np.full((64, 64), 1.0, np.float32)]
    _, s1 = select_rep_frame(small); _, s2 = select_rep_frame(big)
    assert abs(s1 - s2) < 1e-6
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_m2.py -v` / Expected: FAIL (import error)

- [ ] **Step 3: 구현** — `src/m2_keyframe.py`

```python
"""M2 대표 프레임 선택: SMART STC 1단계 차용(차분 L2 → 가우시안 평활 → argmax).
정적 세그먼트는 중간 프레임 fallback + is_static 기록. [DESIGN_SPEC 4-2, v2 2장·8-4]"""
import argparse
from pathlib import Path
import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d
import common


def select_rep_frame(frames: list, sigma: float = 1.0) -> tuple[int, float]:
    """returns (rep_idx, motion_score). motion_score = 인접 차분 RMS 평균(픽셀 정규화)."""
    if len(frames) < 2:
        return 0, 0.0
    diffs = np.array([
        float(np.sqrt(np.mean((frames[i] - frames[i - 1]) ** 2)))
        for i in range(1, len(frames))])
    motion_score = float(diffs.mean())
    if sigma > 0:
        diffs = gaussian_filter1d(diffs, sigma=sigma)   # 지터 억제 [v2 2장]
    rep_idx = int(np.argmax(diffs)) + 1
    return rep_idx, motion_score


def is_static(motion_score: float, threshold: float) -> bool:
    return motion_score < threshold


def sample_frames(cap, start: float, end: float, fps_sample: float) -> list:
    """[start, end)에서 fps_sample 간격으로 그레이스케일 float(0~1) 프레임 샘플."""
    frames, t = [], start
    while t < end:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if ok:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
            frames.append((g, t))
        t += 1.0 / fps_sample
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    cfg = common.load_config(args.config)

    wdir = common.work_dir(cfg, args.video_id)
    doc = common.load_segments(wdir / "segments.json")
    if "rep_frame" in doc["segments"][0] and not args.force:
        print("이미 완료 (--force로 재생성)"); return

    video = Path(cfg["paths"]["data"]) / "videos" / f"{args.video_id}.mp4"
    frames_dir = wdir / "frames"; frames_dir.mkdir(exist_ok=True)
    cap = cv2.VideoCapture(str(video))

    n_static = 0
    for seg in doc["segments"]:
        sampled = sample_frames(cap, seg["start"], seg["end"], cfg["frame_sample_fps"])
        grays = [g for g, _ in sampled]
        rep_idx, motion = select_rep_frame(grays, cfg["gaussian_sigma"])
        static = is_static(motion, cfg["static_threshold"])
        if static:
            rep_idx = len(sampled) // 2               # 중간 프레임 fallback [v2 2장]
            n_static += 1
        # 저장은 컬러 원본으로 다시 읽음
        t_rep = sampled[rep_idx][1] if sampled else seg["start"]
        cap.set(cv2.CAP_PROP_POS_MSEC, t_rep * 1000)
        ok, color = cap.read()
        out = frames_dir / f"seg_{seg['idx']:04d}.jpg"
        if ok:
            cv2.imwrite(str(out), color)
        if not out.exists():
            raise RuntimeError(f"프레임 저장 실패: seg {seg['idx']}")
        seg["rep_frame"] = f"frames/seg_{seg['idx']:04d}.jpg"
        seg["is_static"] = static
        seg["motion_score"] = round(motion, 6)
    cap.release()

    ratio = n_static / doc["n_segments"]
    print(f"M2 완료: is_static 비율 {ratio:.1%} ({n_static}/{doc['n_segments']})")
    if ratio > 0.5:
        print("⚠️ is_static 비율 50% 초과 — static_threshold 재검토 필요 [DESIGN_SPEC 4-2]")
    common.save_segments(wdir / "segments.json", doc)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_m2.py -v` / Expected: 4 PASS

- [ ] **Step 5: 실제 영상 스모크** — Run: `python src/m2_keyframe.py --config config.yaml --video-id spiderman_trailer`
Expected: `work/spiderman_trailer/frames/seg_*.jpg` 전 세그먼트 생성 + is_static 비율 로그

- [ ] **Step 6: Commit**

```bash
git add src/m2_keyframe.py tests/test_m2.py
git commit -m "feat: M2 대표 프레임 선택 (SMART STC + 정적 fallback)"
```

---

### Task 4: M3(a) 자막 — Whisper 전사 + 오버랩 귀속

**Files:**
- Create: `src/m3_generate.py` (자막부 먼저, 캡션부는 Task 5)
- Test: `tests/test_m3_subtitle.py`

**Interfaces:**
- Consumes: `common.*`, `work/{id}/audio.wav`
- Produces: `transcribe(wav: Path, model_name: str, lang: str) -> list[dict]` — utterance `{"text", "t0", "t1"}` 리스트(캐시 지원), `assign_subtitles(utts: list[dict], segments: list[dict]) -> None`(segments 각각에 `subtitle` 채움, 오버랩 중복 허용)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_m3_subtitle.py`

```python
from m3_generate import assign_subtitles

def _segs(n, dur=None):
    return [{"idx": i, "start": i * 5, "end": min(i * 5 + 5, dur or n * 5)}
            for i in range(n)]

def test_utterance_within_one_segment():
    segs = _segs(2)
    assign_subtitles([{"text": "안녕하세요", "t0": 1.0, "t1": 3.0}], segs)
    assert segs[0]["subtitle"] == "안녕하세요"
    assert segs[1]["subtitle"] == ""

def test_boundary_utterance_duplicated_both_sides():
    # 4~8초 발화: seg0(1s)·seg1(3s) 모두 걸침 → 양쪽 중복 포함 [DESIGN_SPEC 3-2, v2 8-1]
    segs = _segs(2)
    assign_subtitles([{"text": "경계 발화", "t0": 4.0, "t1": 8.0}], segs)
    assert "경계 발화" in segs[0]["subtitle"]
    assert "경계 발화" in segs[1]["subtitle"]

def test_multiple_utterances_ordered_and_joined():
    segs = _segs(1)
    assign_subtitles([{"text": "첫째", "t0": 0.5, "t1": 1.0},
                      {"text": "둘째", "t0": 2.0, "t1": 3.0}], segs)
    assert segs[0]["subtitle"] == "첫째 둘째"

def test_silent_segment_gets_empty_string():
    segs = _segs(3)
    assign_subtitles([], segs)
    assert all(s["subtitle"] == "" for s in segs)   # 무발화는 "" 정상 케이스
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_m3_subtitle.py -v` / Expected: FAIL (import error)

- [ ] **Step 3: 구현** — `src/m3_generate.py` (자막부. 기존 stt_local.py의 검증된 설정 차용)

```python
"""M3 자막·캡션 생성. 자막: faster-whisper(stt_test/stt_local.py 검증 설정 차용),
캡션: Qwen2.5-VL(caption/qwen_caption_test 검증 설정 차용). [DESIGN_SPEC 4-3]"""
import argparse, json, os, sys
from pathlib import Path
import common

# Windows 콘솔(cp949) 크래시 방지 [stt_local.py 차용]
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

# Windows: ctranslate2용 cuBLAS(CUDA 12) DLL 주입. cudnn은 절대 추가 금지 [stt_local.py 차용]
if os.name == "nt":
    import site
    for _base in (site.getusersitepackages(), *site.getsitepackages()):
        _dir = os.path.join(_base, "nvidia", "cublas", "bin")
        if os.path.isdir(_dir):
            os.add_dll_directory(_dir)
            break


def transcribe(wav: Path, model_name: str = "large-v3", lang: str = "ko",
               force: bool = False) -> list[dict]:
    """utterance = {text, t0, t1} 리스트. 캐시: audio.wav 옆 stt_cache.json."""
    cache = wav.parent / "stt_cache.json"
    meta = {"model": model_name, "lang": lang,
            "mtime": os.path.getmtime(wav), "size": os.path.getsize(wav)}
    if not force and cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        if d.get("meta") == meta:
            print(f"캐시된 전사 사용: {cache}")
            return d["utterances"]

    from faster_whisper import WhisperModel

    def run(device, compute):
        model = WhisperModel(model_name, device=device, compute_type=compute)
        # 한국어 환각 방지 2중 장치 + VAD 금지 [stt_local.py에서 검증됨]
        raw, _ = model.transcribe(
            str(wav), language=lang, word_timestamps=True,
            condition_on_previous_text=False,
            hallucination_silence_threshold=1.0)
        return [{"text": s.text.strip(), "t0": float(s.start), "t1": float(s.end)}
                for s in raw if s.text.strip()]

    # GPU 폴백 사다리 [stt_local.py 차용]
    ladder = [("cuda", "float16"), ("cuda", "int8_float16"), ("cpu", "int8")]
    utts = None
    for device, compute in ladder:
        try:
            print(f"faster-whisper {model_name} ({device}/{compute}) 전사 중...")
            utts = run(device, compute)
            break
        except Exception as e:
            if (device, compute) == ladder[-1]:
                raise
            print(f"  {device}/{compute} 불가({type(e).__name__}) → 폴백")

    common.atomic_write_json(cache, {"meta": meta, "utterances": utts})
    return utts


def assign_subtitles(utts: list[dict], segments: list[dict]) -> None:
    """오버랩 귀속: 발화가 겹치는 모든 세그먼트에 포함(경계 문장 양쪽 중복 허용).
    최대 겹침 세그먼트가 자동 포함되므로 '더 많이 걸친 쪽 귀속'을 상회 충족. [3-2]"""
    parts = {s["idx"]: [] for s in segments}
    for u in utts:
        for s in segments:
            if min(u["t1"], s["end"]) - max(u["t0"], s["start"]) > 0:
                parts[s["idx"]].append(u["text"])
    for s in segments:
        s["subtitle"] = " ".join(parts[s["idx"]])
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_m3_subtitle.py -v` / Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/m3_generate.py tests/test_m3_subtitle.py
git commit -m "feat: M3(a) Whisper 전사 + 오버랩 자막 귀속"
```

---

### Task 5: M3(b) 캡션 — Qwen2.5-VL + CLI 통합

**Files:**
- Modify: `src/m3_generate.py` (캡션부 + main 추가)
- Test: `tests/test_m3_caption.py`

**Interfaces:**
- Consumes: Task 4의 `transcribe`/`assign_subtitles`, `segments.json`(rep_frame 필요)
- Produces: `load_vlm(cfg) -> (model, processor)`, `caption_frame(image_path, prompt, model, processor, cfg) -> str`, `caption_all(doc, wdir, cfg, captioner) -> list[int]`(실패 idx 목록; captioner 주입으로 테스트 가능). 산출: segments.json에 subtitle/caption 완성

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_m3_caption.py`

```python
from m3_generate import caption_all

def _doc(n=3):
    segs = [{"idx": i, "start": i * 5, "end": i * 5 + 5,
             "rep_frame": f"frames/seg_{i:04d}.jpg", "is_static": False,
             "subtitle": ""} for i in range(n)]
    return {"video_id": "v", "duration_sec": n * 5.0, "fps": 30.0,
            "n_segments": n, "segments": segs}

def test_caption_all_fills_every_segment(tmp_path):
    doc = _doc()
    failed = caption_all(doc, tmp_path, {}, captioner=lambda p: "캡션")
    assert failed == []
    assert all(s["caption"] == "캡션" for s in doc["segments"])

def test_caption_retry_once_then_report_failure(tmp_path):
    doc = _doc(2)
    calls = []
    def flaky(p):
        calls.append(p)
        if "0000" in str(p):
            raise RuntimeError("VLM 실패")
        return "ok"
    failed = caption_all(doc, tmp_path, {}, captioner=flaky)
    assert failed == [0]                              # 재시도 1회 후 실패 목록 [4-3]
    assert str(calls).count("0000") == 2              # 정확히 2회 시도
    assert doc["segments"][0]["caption"] == ""        # 실패 시 빈 문자열 기록
    assert doc["segments"][1]["caption"] == "ok"

def test_caption_resume_skips_existing(tmp_path):
    doc = _doc(2)
    doc["segments"][0]["caption"] = "기존"
    called = []
    caption_all(doc, tmp_path, {}, captioner=lambda p: (called.append(p) or "새로"))
    assert doc["segments"][0]["caption"] == "기존" and len(called) == 1

def test_static_segment_still_captioned(tmp_path):
    doc = _doc(1); doc["segments"][0]["is_static"] = True
    caption_all(doc, tmp_path, {}, captioner=lambda p: "정적 캡션")
    assert doc["segments"][0]["caption"] == "정적 캡션"   # 캡션 버리기 금지 [v2 8-4]
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_m3_caption.py -v` / Expected: FAIL

- [ ] **Step 3: 구현** — `src/m3_generate.py`에 추가

```python
def load_vlm(cfg):
    """Qwen2.5-VL 로딩. 4bit NF4·max_pixels 설정은 기존 caption 실험 검증값 차용."""
    import torch
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
    kwargs = dict(device_map="auto")
    if cfg.get("vlm_4bit"):
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
    else:
        kwargs["torch_dtype"] = torch.bfloat16
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(cfg["caption_model"], **kwargs)
    processor = AutoProcessor.from_pretrained(
        cfg["caption_model"], min_pixels=256 * 28 * 28, max_pixels=cfg["vlm_max_pixels"])
    return model, processor


def caption_frame(image_path, prompt, model, processor, cfg) -> str:
    import torch
    from qwen_vl_utils import process_vision_info
    messages = [{"role": "user", "content": [
        {"type": "image", "image": str(image_path)},
        {"type": "text", "text": prompt}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    imgs, vids = process_vision_info(messages)
    inputs = processor(text=[text], images=imgs, videos=vids,
                       padding=True, return_tensors="pt").to(model.device)
    gen_kwargs = dict(max_new_tokens=128, do_sample=False)
    if cfg.get("vlm_rep_penalty", 1.0) != 1.0:
        gen_kwargs["repetition_penalty"] = cfg["vlm_rep_penalty"]
    with torch.inference_mode():
        gen = model.generate(**inputs, **gen_kwargs)
    out = processor.batch_decode(gen[:, inputs.input_ids.shape[1]:],
                                 skip_special_tokens=True)[0]
    return out.strip()


def caption_all(doc, wdir, cfg, captioner) -> list[int]:
    """전 세그먼트 캡션. 실패 시 1회 재시도 후 실패 idx 반환. resume 지원. [4-3]"""
    failed = []
    for seg in doc["segments"]:
        if seg.get("caption"):                        # resume: 이미 있으면 건너뜀
            continue
        img = Path(wdir) / seg["rep_frame"]
        cap_text = ""
        for attempt in range(2):                      # 최초 1회 + 재시도 1회
            try:
                cap_text = captioner(img)
                break
            except Exception as e:
                if attempt == 1:
                    print(f"seg {seg['idx']} 캡션 실패: {type(e).__name__}: {e}")
        if not cap_text:
            failed.append(seg["idx"])
        seg["caption"] = cap_text
    return failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    wdir = common.work_dir(cfg, args.video_id)
    doc = common.load_segments(wdir / "segments.json", require=["rep_frame", "is_static"])

    if args.force:
        for s in doc["segments"]:
            s.pop("subtitle", None); s.pop("caption", None)

    # (a) 자막
    utts = transcribe(wdir / "audio.wav", cfg["stt_model"], cfg["stt_language"],
                      force=args.force)
    assign_subtitles(utts, doc["segments"])
    covered = sum(1 for s in doc["segments"] if s["subtitle"])
    print(f"자막 커버리지: {covered}/{doc['n_segments']} ({covered/doc['n_segments']:.1%})")

    # (b) 캡션
    model, processor = load_vlm(cfg)
    failed = caption_all(doc, wdir, cfg,
                         captioner=lambda p: caption_frame(p, cfg["caption_prompt"],
                                                           model, processor, cfg))
    common.save_segments(wdir / "segments.json", doc)
    if failed:
        print(f"⚠️ 캡션 실패 세그먼트 {len(failed)}개: {failed}")  # 검증 포인트 [4-3]
        sys.exit(1)
    print("M3 완료: caption 빈 문자열 0건")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_m3_caption.py tests/test_m3_subtitle.py -v` / Expected: 8 PASS

- [ ] **Step 5: 실제 영상 스모크 (GPU 필요 — 로컬이면 config에서 3B+4bit로 변경)**

```bash
python src/m3_generate.py --config config.yaml --video-id spiderman_trailer
```
Expected: 자막 커버리지 로그 + "M3 완료: caption 빈 문자열 0건"

- [ ] **Step 6: Commit**

```bash
git add src/m3_generate.py tests/test_m3_caption.py
git commit -m "feat: M3(b) Qwen2.5-VL 캡션 + CLI 통합 (재시도·resume)"
```

---

### Task 6: M4 임베딩·인덱싱

**Files:**
- Create: `src/m4_index.py`
- Test: `tests/test_m4.py`

**Interfaces:**
- Consumes: `segments.json`(subtitle/caption 필요)
- Produces: `embed_texts(texts: list[str], model_name: str, batch_size: int = 32) -> np.ndarray`(L2 정규화 float32; M5가 질의 임베딩에 재사용). 산출: `emb_sub.npy`, `emb_cap.npy`, `meta.json`({model, dim, n_segments})

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_m4.py`

```python
import numpy as np
import m4_index

def test_embed_texts_l2_normalized(monkeypatch):
    # sentence-transformers를 가짜 인코더로 대체 (GPU 불필요 단위 테스트)
    class FakeModel:
        def encode(self, texts, batch_size, normalize_embeddings, show_progress_bar=False):
            assert normalize_embeddings is True
            rng = np.random.default_rng(0)
            v = rng.normal(size=(len(texts), 8)).astype(np.float32)
            return v / np.linalg.norm(v, axis=1, keepdims=True)
    monkeypatch.setattr(m4_index, "_load_model", lambda name: FakeModel())
    out = m4_index.embed_texts(["안녕", "", "세 번째"], "any-model")
    assert out.shape == (3, 8) and out.dtype == np.float32
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-4)  # norm 편차 [4-4]

def test_empty_string_embedded_as_is(monkeypatch):
    # 무발화 subtitle="" 도 그대로 임베딩 (특별 처리 금지) [3-1]
    seen = []
    class FakeModel:
        def encode(self, texts, **kw):
            seen.extend(texts)
            return np.ones((len(texts), 4), dtype=np.float32) * 0.5
    monkeypatch.setattr(m4_index, "_load_model", lambda name: FakeModel())
    m4_index.embed_texts(["", "텍스트"], "m")
    assert seen == ["", "텍스트"]
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_m4.py -v` / Expected: FAIL

- [ ] **Step 3: 구현** — `src/m4_index.py`

```python
"""M4 임베딩·인덱싱: subtitle/caption → emb_sub.npy·emb_cap.npy (L2 정규화, float32).
자막·캡션·질의는 반드시 같은 embed_model. [DESIGN_SPEC 4-4, v2 7-8]"""
import argparse
from pathlib import Path
import numpy as np
import common

_model_cache = {}


def _load_model(model_name: str):
    if model_name not in _model_cache:
        from sentence_transformers import SentenceTransformer
        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


def embed_texts(texts: list[str], model_name: str, batch_size: int = 32) -> np.ndarray:
    model = _load_model(model_name)
    emb = model.encode(texts, batch_size=batch_size,
                       normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(emb, dtype=np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    wdir = common.work_dir(cfg, args.video_id)
    doc = common.load_segments(wdir / "segments.json", require=["subtitle", "caption"])

    if (wdir / "emb_sub.npy").exists() and not args.force:
        print("이미 존재 (--force로 재생성)"); return

    subs = [s["subtitle"] for s in doc["segments"]]
    caps = [s["caption"] for s in doc["segments"]]
    emb_sub = embed_texts(subs, cfg["embed_model"], cfg["embed_batch_size"])
    emb_cap = embed_texts(caps, cfg["embed_model"], cfg["embed_batch_size"])

    # 검증 포인트 [4-4]: row 수, norm 편차
    for name, emb in (("emb_sub", emb_sub), ("emb_cap", emb_cap)):
        assert emb.shape[0] == doc["n_segments"], f"{name} rows != n_segments"
        norms = np.linalg.norm(emb, axis=1)
        nonzero = norms > 0                      # 빈 문자열 임베딩이 0벡터인 모델 대비
        assert np.abs(norms[nonzero] - 1.0).max() < 1e-4, f"{name} norm 편차 초과"

    np.save(wdir / "emb_sub.npy", emb_sub)
    np.save(wdir / "emb_cap.npy", emb_cap)
    common.atomic_write_json(wdir / "meta.json", {
        "embed_model": cfg["embed_model"], "dim": int(emb_sub.shape[1]),
        "n_segments": doc["n_segments"]})
    print(f"M4 완료: ({emb_sub.shape[0]}, {emb_sub.shape[1]}) x2 저장")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_m4.py -v` / Expected: 2 PASS

- [ ] **Step 5: 실제 스모크** — Run: `python src/m4_index.py --config config.yaml --video-id spiderman_trailer` / Expected: "M4 완료" + meta.json에 모델명·차원

- [ ] **Step 6: Commit**

```bash
git add src/m4_index.py tests/test_m4.py
git commit -m "feat: M4 임베딩 인덱싱 (L2 정규화 + meta 기록)"
```

---

### Task 7: M5 검색 (확정 연산 순서)

**Files:**
- Create: `src/m5_search.py`
- Test: `tests/test_m5.py`

**Interfaces:**
- Consumes: `m4_index.embed_texts`, `emb_*.npy`, `meta.json`, `segments.json`
- Produces: `minmax(x: np.ndarray) -> np.ndarray`, `combine_scores(s_sub, s_cap, static_mask, alpha) -> np.ndarray`(정규화→치환→가중합 핵심), `VideoIndex`(dataclass: segments/emb_sub/emb_cap/static_mask, `VideoIndex.load(cfg, video_id)`), `search(query: str, video: VideoIndex, alpha: float, cfg) -> list[Result]`, `Result`(NamedTuple: idx, score, start, end). M6·M7이 `search`·`VideoIndex` 그대로 import (재구현 금지)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_m5.py`

```python
import numpy as np
from m5_search import minmax, combine_scores

def test_minmax_basic():
    out = minmax(np.array([1.0, 3.0, 2.0]))
    assert np.allclose(out, [0.0, 1.0, 0.5])

def test_minmax_degenerate_returns_zeros():
    # max==min → 0 벡터 (균등 처리) [DESIGN_SPEC 4-5]
    assert np.allclose(minmax(np.array([0.7, 0.7, 0.7])), 0.0)

def test_combine_order_substitution_after_normalization():
    # 핵심 계약 [v2 8-4]: 치환은 '정규화 이후'. 정규화 전에 치환하면
    # 정적 세그먼트의 원본 s_cap이 min/max를 오염시킨다.
    s_sub = np.array([0.2, 0.4, 0.6])
    s_cap = np.array([0.9, 0.1, 0.5])   # idx0가 정적: s_cap 0.9는 무시되어야 함
    static = np.array([True, False, False])
    out = combine_scores(s_sub, s_cap, static, alpha=0.5)
    # 정규화: s_sub_n=[0,.5,1], s_cap_n=[1,0,.5] → 치환: s_cap_n[0]=0
    # 가중합: [0, .25, .75]
    assert np.allclose(out, [0.0, 0.25, 0.75])

def test_alpha_1_is_baseline_pure_subtitle():
    s_sub = np.array([0.1, 0.9]); s_cap = np.array([0.9, 0.1])
    out = combine_scores(s_sub, s_cap, np.array([False, False]), alpha=1.0)
    assert np.allclose(out, minmax(s_sub))          # baseline = α=1.0 특수 경우

def test_static_substitution_makes_score_equal_subtitle():
    # 정적 세그먼트는 score = s_sub_norm (α와 무관) [v2 8-4]
    s_sub = np.array([0.3, 0.8]); s_cap = np.array([0.5, 0.2])
    for alpha in (0.0, 0.3, 0.7):
        out = combine_scores(s_sub, s_cap, np.array([True, True]), alpha)
        assert np.allclose(out, minmax(s_sub))
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_m5.py -v` / Expected: FAIL

- [ ] **Step 3: 구현** — `src/m5_search.py`

```python
"""M5 검색: 확정 연산 순서 — 코사인 → per-query minmax(단일 영상 범위) →
정적 s_cap_norm←s_sub_norm 치환 → α 가중합. baseline = α=1.0. [DESIGN_SPEC 4-5]"""
import argparse, json
from dataclasses import dataclass
from typing import NamedTuple
import numpy as np
import common
from m4_index import embed_texts


class Result(NamedTuple):
    idx: int
    score: float
    start: float
    end: float


def minmax(x: np.ndarray) -> np.ndarray:
    rng = x.max() - x.min()
    return np.zeros_like(x) if rng < 1e-9 else (x - x.min()) / rng


def combine_scores(s_sub: np.ndarray, s_cap: np.ndarray,
                   static_mask: np.ndarray, alpha: float) -> np.ndarray:
    s_sub_n = minmax(s_sub)                      # 2) 각각 정규화 (단일 영상 범위)
    s_cap_n = minmax(s_cap)
    s_cap_n = s_cap_n.copy()
    s_cap_n[static_mask] = s_sub_n[static_mask]  # 3) 정규화 '이후' 치환 [v2 8-4]
    return alpha * s_sub_n + (1 - alpha) * s_cap_n  # 4) 가중합


@dataclass
class VideoIndex:
    segments: list
    emb_sub: np.ndarray
    emb_cap: np.ndarray
    static_mask: np.ndarray

    @classmethod
    def load(cls, cfg: dict, video_id: str) -> "VideoIndex":
        wdir = common.work_dir(cfg, video_id)
        doc = common.load_segments(wdir / "segments.json",
                                   require=["subtitle", "caption", "is_static"])
        for name in ("emb_sub.npy", "emb_cap.npy"):
            if not (wdir / name).exists():
                raise FileNotFoundError(f"{name} 없음 — run m4_index.py first")
        meta = json.loads((wdir / "meta.json").read_text(encoding="utf-8"))
        if meta["embed_model"] != cfg["embed_model"]:   # 모델 혼입 방지 [4-4]
            raise ValueError(f"임베딩 모델 불일치: index={meta['embed_model']} "
                             f"config={cfg['embed_model']} — run m4_index.py --force")
        return cls(segments=doc["segments"],
                   emb_sub=np.load(wdir / "emb_sub.npy"),
                   emb_cap=np.load(wdir / "emb_cap.npy"),
                   static_mask=np.array([s["is_static"] for s in doc["segments"]]))


def search(query: str, video: VideoIndex, alpha: float, cfg: dict) -> list[Result]:
    q = embed_texts([query], cfg["embed_model"])[0]
    s_sub = video.emb_sub @ q                    # 1) 코사인 (L2 정규화 완료 상태)
    s_cap = video.emb_cap @ q
    score = combine_scores(s_sub, s_cap, video.static_mask, alpha)
    order = np.argsort(-score)
    return [Result(int(i), float(score[i]),
                   video.segments[i]["start"], video.segments[i]["end"])
            for i in order]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--topk", type=int, default=5)
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    video = VideoIndex.load(cfg, args.video_id)
    for r in search(args.query, video, args.alpha, cfg)[:args.topk]:
        sub = video.segments[r.idx]["subtitle"][:40]
        print(f"[{r.idx:4d}] {r.score:.3f}  {int(r.start)}s~{int(r.end)}s  {sub}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_m5.py -v` / Expected: 5 PASS

- [ ] **Step 5: 실제 스모크** — Run: `python src/m5_search.py --config config.yaml --video-id spiderman_trailer --query "스파이더맨이 나오는 장면" --alpha 0.5` / Expected: top-5 랭킹 출력

- [ ] **Step 6: Commit**

```bash
git add src/m5_search.py tests/test_m5.py
git commit -m "feat: M5 검색 — 확정 연산 순서(정규화→치환→가중합)"
```

---

### Task 8: M6 평가 (지표 + dev grid search → test)

**Files:**
- Create: `src/m6_evaluate.py`
- Test: `tests/test_m6.py`

**Interfaces:**
- Consumes: `m5_search.search`/`VideoIndex`/`Result`, `data/queries/queries.jsonl`
- Produces: `hit_at_k(ranked, gt_seg_idx, k) -> float`, `mrr(ranked, gt_seg_idx) -> float`, `iou_recall_at_k(ranked, gt_start, gt_end, k, thr) -> float`, `derive_gt_seg_idx(gt_start, gt_end, n_segments, seg_len=5) -> list[int]`, `load_queries(path) -> list[dict]`(dev/test video_id 교집합 assert), `grid_search_alpha(dev_queries, indexes, cfg, search_fn) -> tuple[float, dict]`, `evaluate(queries, indexes, alpha, cfg, search_fn) -> dict`. 산출: `results/alpha_search_dev.json`, `results/eval_test.json`(3-4 스키마)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_m6.py`

```python
import json, pytest
from m5_search import Result
from m6_evaluate import (hit_at_k, mrr, iou_recall_at_k, derive_gt_seg_idx,
                         load_queries, grid_search_alpha)

def _r(indexes):  # Result 리스트 헬퍼 (idx→start=idx*5)
    return [Result(i, 1.0 - n * 0.1, i * 5, i * 5 + 5) for n, i in enumerate(indexes)]

def test_hit_at_k():
    ranked = _r([3, 7, 1])
    assert hit_at_k(ranked, [7], k=1) == 0.0
    assert hit_at_k(ranked, [7], k=2) == 1.0
    assert hit_at_k(ranked, [9, 1], k=3) == 1.0       # 교집합 존재 여부

def test_mrr_first_gt_rank():
    assert mrr(_r([3, 7, 1]), [7]) == 0.5             # 첫 등장 랭크 2 → 1/2
    assert mrr(_r([3, 7, 1]), [1, 7]) == 0.5          # gt 중 처음 등장
    assert mrr(_r([3]), [9]) == 0.0

def test_iou_recall():
    ranked = _r([0])                                   # 예측 0~5초
    assert iou_recall_at_k(ranked, 0.0, 5.0, k=1, thr=0.5) == 1.0
    assert iou_recall_at_k(ranked, 3.0, 7.0, k=1, thr=0.5) == 0.0  # IoU 2/9

def test_derive_gt_seg_idx():
    assert derive_gt_seg_idx(3.0, 7.0, n_segments=3) == [0, 1]   # 둘 다 2s 겹침 ≥1s
    assert derive_gt_seg_idx(4.8, 5.4, n_segments=3) == [1]      # 최대 겹침 1개 보장
    assert derive_gt_seg_idx(33.0, 38.5, n_segments=10) == [6, 7]

def test_load_queries_asserts_split_leak(tmp_path):
    p = tmp_path / "queries.jsonl"
    rows = [{"query_id": "q1", "video_id": "v1", "text": "t", "type": "자막형",
             "gt_start": 0.0, "gt_end": 5.0, "gt_seg_idx": [0], "split": "dev"},
            {"query_id": "q2", "video_id": "v1", "text": "t", "type": "장면형",
             "gt_start": 0.0, "gt_end": 5.0, "gt_seg_idx": [0], "split": "test"}]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    with pytest.raises(AssertionError, match="video_id"):        # 누수 차단 [5-1]
        load_queries(p)

def test_grid_search_tiebreak_larger_alpha():
    queries = [{"query_id": "q1", "video_id": "v1", "gt_seg_idx": [0],
                "gt_start": 0.0, "gt_end": 5.0, "type": "자막형", "split": "dev"}]
    cfg = {"alpha_grid": [0.0, 0.5, 1.0], "alpha_select_metric": "hit@5",
           "alpha_tiebreak": "larger", "eval_k": [1, 5, 10], "iou_thresholds": [0.5, 0.3]}
    fake_search = lambda q, video, alpha, cfg: _r([0, 1, 2])     # 모든 α 동률
    best, table = grid_search_alpha(queries, {"v1": None}, cfg, search_fn=fake_search)
    assert best == 1.0                                            # 동률 → α 큰 값 [9-1(a)]
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_m6.py -v` / Expected: FAIL

- [ ] **Step 3: 구현** — `src/m6_evaluate.py`

```python
"""M6 평가: dev grid search로 α 고정 → test 평가. test로 α를 고르는 경로는
존재하지 않는다(누수 원천 차단). [DESIGN_SPEC 4-6, v2 9-1]"""
import argparse, json
from collections import defaultdict
from pathlib import Path
import common
from m5_search import VideoIndex, search


def hit_at_k(ranked, gt_seg_idx, k: int) -> float:
    return 1.0 if set(r.idx for r in ranked[:k]) & set(gt_seg_idx) else 0.0


def mrr(ranked, gt_seg_idx) -> float:
    gt = set(gt_seg_idx)
    for rank, r in enumerate(ranked, 1):
        if r.idx in gt:
            return 1.0 / rank
    return 0.0


def _iou(a0, a1, b0, b1) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    union = (a1 - a0) + (b1 - b0) - inter
    return inter / union if union > 0 else 0.0


def iou_recall_at_k(ranked, gt_start, gt_end, k: int, thr: float) -> float:
    return 1.0 if any(_iou(r.start, r.end, gt_start, gt_end) >= thr
                      for r in ranked[:k]) else 0.0


def derive_gt_seg_idx(gt_start, gt_end, n_segments, seg_len: int = 5) -> list[int]:
    """1초 이상 겹치는 모든 세그먼트, 없으면 최대 겹침 1개. [3-3]"""
    overlaps = []
    for i in range(n_segments):
        s, e = i * seg_len, (i + 1) * seg_len
        overlaps.append((i, max(0.0, min(e, gt_end) - max(s, gt_start))))
    idx = [i for i, ov in overlaps if ov >= 1.0]
    return idx if idx else [max(overlaps, key=lambda t: t[1])[0]]


def load_queries(path) -> list[dict]:
    qs = [json.loads(line) for line in
          Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    dev_v = {q["video_id"] for q in qs if q["split"] == "dev"}
    test_v = {q["video_id"] for q in qs if q["split"] == "test"}
    leak = dev_v & test_v
    assert not leak, f"dev/test에 같은 video_id 존재(누수): {leak}"   # [5-1]
    for q in qs:
        assert q["gt_seg_idx"], f"{q['query_id']}: gt_seg_idx 비어있음"
    return qs


def _rank_of(ranked, gt_seg_idx) -> int:
    gt = set(gt_seg_idx)
    for rank, r in enumerate(ranked, 1):
        if r.idx in gt:
            return rank
    return 0    # not found


def evaluate(queries, indexes, alpha, cfg, search_fn=search) -> dict:
    """질의셋 평균 지표 + per_query 랭크. by_type 분리 집계 포함. [3-4]"""
    per_q, buckets = [], defaultdict(list)
    for q in queries:
        ranked = search_fn(q["text"], indexes[q["video_id"]], alpha, cfg) \
            if "text" in q else search_fn(None, indexes[q["video_id"]], alpha, cfg)
        row = {"query_id": q["query_id"], "type": q["type"],
               "rank": _rank_of(ranked, q["gt_seg_idx"]),
               **{f"hit@{k}": hit_at_k(ranked, q["gt_seg_idx"], k) for k in cfg["eval_k"]},
               "mrr": mrr(ranked, q["gt_seg_idx"]),
               **{f"iou@{t}_r@1": iou_recall_at_k(ranked, q["gt_start"], q["gt_end"], 1, t)
                  for t in cfg["iou_thresholds"]}}
        per_q.append(row); buckets[q["type"]].append(row)

    def _mean(rows):
        keys = [k for k in rows[0] if k not in ("query_id", "type", "rank")]
        return {k: round(sum(r[k] for r in rows) / len(rows), 4) for k in keys}

    metrics = _mean(per_q)
    metrics["by_type"] = {t: _mean(rows) for t, rows in buckets.items()}
    return {"metrics": metrics, "per_query": per_q}


def grid_search_alpha(dev_queries, indexes, cfg, search_fn=search):
    """dev 전용 α 탐색. 동률 시 α 큰 값(자막 우선). [4-6, v2 9-1(a)]"""
    metric = cfg["alpha_select_metric"]
    table = {}
    for alpha in cfg["alpha_grid"]:
        table[alpha] = evaluate(dev_queries, indexes, alpha, cfg, search_fn)["metrics"][metric]
    best = max(table, key=lambda a: (table[a], a))   # 동률 → larger
    assert cfg["alpha_tiebreak"] == "larger"
    return best, table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--queries", default="data/queries/queries.jsonl")
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    queries = load_queries(args.queries)
    dev = [q for q in queries if q["split"] == "dev"]
    test = [q for q in queries if q["split"] == "test"]
    indexes = {vid: VideoIndex.load(cfg, vid) for vid in {q["video_id"] for q in queries}}
    rdir = Path(cfg["paths"]["results"]); rdir.mkdir(exist_ok=True)

    # ① dev grid search → 저장
    alpha, table = grid_search_alpha(dev, indexes, cfg)
    common.atomic_write_json(rdir / "alpha_search_dev.json",
                             {"best_alpha": alpha, "metric": cfg["alpha_select_metric"],
                              "table": {str(a): v for a, v in table.items()}})
    print(f"dev grid search: α*={alpha}")

    # ② test 평가는 그 α만 사용 (baseline=1.0 vs proposed=α*)
    base = evaluate(test, indexes, 1.0, cfg)
    prop = evaluate(test, indexes, alpha, cfg)
    n_by_type = defaultdict(int)
    for q in test:
        n_by_type[q["type"]] += 1
    common.atomic_write_json(rdir / "eval_test.json", {
        "alpha_from_dev": alpha,
        "n_queries": {"total": len(test), **n_by_type},
        "metrics": {"baseline": base["metrics"], "proposed": prop["metrics"]},
        "per_query": [{"query_id": b["query_id"],
                       "baseline_rank": b["rank"], "proposed_rank": p["rank"]}
                      for b, p in zip(base["per_query"], prop["per_query"])]})
    print(f"M6 완료: eval_test.json (baseline hit@5={base['metrics']['hit@5']}, "
          f"proposed hit@5={prop['metrics']['hit@5']})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_m6.py -v` / Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add src/m6_evaluate.py tests/test_m6.py
git commit -m "feat: M6 평가 — 지표·gt 산출·dev grid search·test 평가"
```

---

### Task 9: M7 데모 (Gradio)

**Files:**
- Create: `src/m7_demo.py`
- Test: `tests/test_m7.py`

**Interfaces:**
- Consumes: `m5_search.search`/`VideoIndex` (그대로 import, 재구현 금지)
- Produces: `format_output(ranked, segments, k=3) -> dict`({jump_to, subtitle, windows}) — 정수 초 `[[시작,끝],...]` 고정

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_m7.py`

```python
from m5_search import Result
from m7_demo import format_output

def test_format_output_contract():
    ranked = [Result(6, 0.9, 30, 35), Result(7, 0.8, 35, 40), Result(2, 0.7, 10, 15.5)]
    segments = {2: {"subtitle": "셋"}, 6: {"subtitle": "여섯"}, 7: {"subtitle": "일곱"}}
    segs = [dict(idx=i, subtitle=segments.get(i, {}).get("subtitle", "")) for i in range(8)]
    out = format_output(ranked, segs, k=3)
    assert out["jump_to"] == 30                       # int
    assert out["subtitle"] == "여섯"
    assert out["windows"] == [[30, 35], [35, 40], [10, 15]]   # 정수 초 [v2 6장]
    assert all(isinstance(v, int) for w in out["windows"] for v in w)
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_m7.py -v` / Expected: FAIL

- [ ] **Step 3: 구현** — `src/m7_demo.py`

```python
"""M7 데모: Gradio. 백엔드는 m5_search.search를 그대로 import(재구현 금지). [4-7]"""
import argparse
from pathlib import Path
import common
from m5_search import VideoIndex, search


def format_output(ranked, segments, k: int = 3) -> dict:
    return {"jump_to": int(ranked[0].start),
            "subtitle": segments[ranked[0].idx]["subtitle"],
            "windows": [[int(r.start), int(r.end)] for r in ranked[:k]]}


def main():
    import gradio as gr
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--alpha", type=float, required=True,
                    help="eval에서 고정한 α (results/alpha_search_dev.json)")
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    video = VideoIndex.load(cfg, args.video_id)
    mp4 = Path(cfg["paths"]["data"]) / "videos" / f"{args.video_id}.mp4"

    def run(query):
        ranked = search(query, video, args.alpha, cfg)
        out = format_output(ranked, video.segments)
        lines = [f"{i+1}. {w[0]}초~{w[1]}초" for i, w in enumerate(out["windows"])]
        return (str(mp4), out["jump_to"]), out["subtitle"], "\n".join(lines)

    with gr.Blocks(title="영상 장면 검색") as app:
        q = gr.Textbox(label="질의")
        player = gr.Video(str(mp4), label="영상")
        sub = gr.Textbox(label="자막", interactive=False)
        tops = gr.Textbox(label="Top-3 구간", interactive=False)
        q.submit(run, q, [player, sub, tops])
    app.launch()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_m7.py -v` / Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/m7_demo.py tests/test_m7.py
git commit -m "feat: M7 Gradio 데모 (M5 search 재사용)"
```

---

### Task 10: M8 AAR 리포트 생성

**Files:**
- Create: `src/llm.py`, `src/m8_report.py`
- Test: `tests/test_m8.py`

**Interfaces:**
- Consumes: `segments.json`(subtitle/caption)
- Produces: `llm.make_llm(model_name: str) -> Callable[[str], str]`(transformers 지연 로딩; M9도 사용), `build_map_prompt(chunk: list[dict]) -> str`, `build_reduce_prompt(partials: list[str]) -> str`, `parse_citations(text: str) -> list[dict]`(`{"sent_id", "text", "cites"}`), `generate_report(segments, llm, chunk_size, overlap) -> dict`. 산출: `work/{id}/report.json`(3-5 스키마)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_m8.py`

```python
from m8_report import build_map_prompt, build_reduce_prompt, parse_citations, generate_report

def _segs(n):
    return [{"idx": i, "start": i * 5, "end": i * 5 + 5,
             "subtitle": f"자막{i}", "caption": f"캡션{i}"} for i in range(n)]

def test_map_prompt_contains_rules_and_segments():
    p = build_map_prompt(_segs(2))
    assert "[seg#N]" in p and "[seg#0]" in p and "[seg#1]" in p
    assert "추측" in p                                 # 규칙 2 [13-1]
    assert "자막0" in p and "캡션1" in p

def test_reduce_prompt_forbids_new_facts():
    p = build_reduce_prompt(["부분1", "부분2"])
    assert "새로운 사실" in p and "부분1" in p         # [13-2]

def test_parse_citations():
    text = "- 화자가 재료를 준비한다 [seg#6, seg#7]\n- 근거 없는 문장\n- 요리를 시작한다 [seg#9]"
    sents = parse_citations(text)
    assert [s["cites"] for s in sents] == [[6, 7], [], [9]]
    assert sents[0]["sent_id"] == 0
    assert sents[1]["cites"] == []                     # 저장은 하되 자동 ungrounded [15-1]

def test_generate_report_single_call_when_small():
    calls = []
    def llm(prompt):
        calls.append(prompt)
        return "- 사건 [seg#0]"
    rep = generate_report(_segs(3), llm, chunk_size=60, overlap=5)
    assert len(calls) == 1                             # n<=chunk_size → 단일 호출
    assert rep["sentences"][0]["cites"] == [0]
    assert rep["raw_output"] == "- 사건 [seg#0]"      # raw 보존

def test_generate_report_map_reduce_and_subset_check():
    def llm(prompt):
        if "부분 리포트" in prompt:                    # reduce 호출
            return "- 통합 사건 [seg#1]\n- 유령 인용 [seg#99]"
        return "- 부분 사건 [seg#1]"                   # map 호출
    rep = generate_report(_segs(10), llm, chunk_size=4, overlap=1)
    cites = [s["cites"] for s in rep["sentences"]]
    assert [1] in cites
    # reduce의 [seg#99]는 map 인용 집합에 없음 → 걸러짐 [13-2 안전장치]
    assert [99] not in cites
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_m8.py -v` / Expected: FAIL

- [ ] **Step 3: 구현** — `src/llm.py`

```python
"""로컬 LLM 로더 (M8 리포트 생성·M9 judge 공용). 클라우드 API 금지."""
_cache = {}


def make_llm(model_name: str, max_new_tokens: int = 2048):
    """prompt -> str 생성 함수 반환. 모델은 최초 1회만 로딩."""
    def generate(prompt: str) -> str:
        if model_name not in _cache:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            tok = AutoTokenizer.from_pretrained(model_name)
            mdl = AutoModelForCausalLM.from_pretrained(
                model_name, torch_dtype=torch.bfloat16, device_map="auto")
            _cache[model_name] = (tok, mdl)
        tok, mdl = _cache[model_name]
        msgs = [{"role": "user", "content": prompt}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        import torch
        inputs = tok([text], return_tensors="pt").to(mdl.device)
        with torch.inference_mode():
            out = mdl.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        return tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
    return generate
```

`src/m8_report.py`:

```python
"""M8 AAR 리포트 생성: [seg#N] 인용 강제 + map-reduce. [DESIGN_SPEC 4-8, v2 13장]"""
import argparse, re
import common
from llm import make_llm

_SYSTEM = """당신은 영상 사후검토(AAR) 리포트 작성자입니다.
아래는 5초 단위 세그먼트별 자막(subtitle)과 장면 캡션(caption)입니다.
규칙:
1. 모든 문장은 반드시 하나 이상의 [seg#N] 인용을 포함할 것.
2. 세그먼트에 없는 내용은 절대 추측해 쓰지 말 것. 근거가 없으면 문장 자체를 생략할 것.
3. 시간 순서대로 사건을 서술할 것.
4. 인용한 seg#의 내용과 문장이 실제로 일치해야 함 (사후 검증됨).

출력 형식 (한 줄에 한 문장):
- 사건 서술 문장 [seg#N]
- 사건 서술 문장 [seg#N, seg#M]
"""


def _fmt_seg(s) -> str:
    def hms(t):
        t = int(t); return f"{t//60:02d}:{t%60:02d}"
    return (f'[seg#{s["idx"]}] {hms(s["start"])}-{hms(s["end"])} '
            f'subtitle: "{s["subtitle"]}" caption: "{s["caption"]}"')


def build_map_prompt(chunk: list[dict]) -> str:
    return _SYSTEM + "\n입력:\n" + "\n".join(_fmt_seg(s) for s in chunk)


def build_reduce_prompt(partials: list[str]) -> str:
    joined = "\n\n---\n\n".join(partials)
    return (
        "아래는 같은 영상의 구간별 부분 리포트들입니다. 하나의 최종 리포트로 통합하세요.\n"
        "규칙:\n"
        "1. 중복 사건은 하나로 합칠 것.\n"
        "2. 시간 순서([seg#N] 번호 순)로 재정렬할 것.\n"
        "3. 부분 리포트에 없는 새로운 사실을 절대 추가하지 말 것.\n"
        "4. 각 문장의 [seg#N] 인용은 부분 리포트의 인용을 그대로 유지할 것.\n"
        "출력 형식은 동일: '- 문장 [seg#N]'\n\n부분 리포트:\n" + joined)


def parse_citations(text: str) -> list[dict]:
    """줄 단위 파싱. [seg#N, seg#M] → cites 리스트, 인용 없으면 cites=[]. [4-8]"""
    sents = []
    for line in text.splitlines():
        line = line.strip().lstrip("-").strip()
        if not line:
            continue
        cites = [int(m) for m in re.findall(r"seg#(\d+)", line)]
        sents.append({"sent_id": len(sents), "text": line, "cites": sorted(set(cites))})
    return sents


def generate_report(segments: list[dict], llm, chunk_size: int = 60,
                    overlap: int = 5) -> dict:
    if len(segments) <= chunk_size:                    # 단일 호출 [4-8]
        raw = llm(build_map_prompt(segments))
        return {"sentences": parse_citations(raw), "raw_output": raw,
                "map_raw_outputs": []}
    # Map: overlap 세그먼트를 두고 청크 분할 [13-2]
    partials, start = [], 0
    while start < len(segments):
        chunk = segments[start:start + chunk_size]
        partials.append(llm(build_map_prompt(chunk)))
        if start + chunk_size >= len(segments):
            break
        start += chunk_size - overlap
    # Reduce + 안전장치: reduce 인용 ⊆ map 인용 검사 [13-2]
    map_cites = {c for p in partials for s in parse_citations(p) for c in s["cites"]}
    raw = llm(build_reduce_prompt(partials))
    sents = parse_citations(raw)
    for s in sents:
        dropped = [c for c in s["cites"] if c not in map_cites]
        if dropped:
            print(f"⚠️ reduce 인용 유실/오귀속 필터: sent {s['sent_id']} {dropped}")
            s["cites"] = [c for c in s["cites"] if c in map_cites]
    return {"sentences": sents, "raw_output": raw, "map_raw_outputs": partials}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    wdir = common.work_dir(cfg, args.video_id)
    doc = common.load_segments(wdir / "segments.json", require=["subtitle", "caption"])
    out = wdir / "report.json"
    if out.exists() and not args.force:
        print("이미 존재 (--force로 재생성)"); return

    llm = make_llm(cfg["report_model"])
    rep = generate_report(doc["segments"], llm,
                          cfg["map_chunk_size"], cfg["map_chunk_overlap"])
    n = doc["n_segments"]
    for s in rep["sentences"]:                          # 검증 포인트 [4-8]
        assert all(0 <= c < n for c in s["cites"]), f"인용 범위 위반: {s}"
    common.atomic_write_json(out, {"video_id": args.video_id,
                                   "model": cfg["report_model"],
                                   "map_chunk_size": cfg["map_chunk_size"], **rep})
    print(f"M8 완료: 문장 {len(rep['sentences'])}개 → {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_m8.py -v` / Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/llm.py src/m8_report.py tests/test_m8.py
git commit -m "feat: M8 AAR 리포트 생성 — 인용 강제 + map-reduce + 인용 부분집합 검사"
```

---

### Task 11: M9 AAR 평가 (LLM-judge)

**Files:**
- Create: `src/m9_report_eval.py`
- Test: `tests/test_m9.py`

**Interfaces:**
- Consumes: `report.json`, `segments.json`, `queries.jsonl`(test), `llm.make_llm`, `m6_evaluate.load_queries`
- Produces: `judge_grounded(sentence: dict, cited_segments: list[dict], judge) -> bool`(G-Eval 3단계 CoT), `judge_coverage(report_text: str, segment: dict, judge) -> bool`, `eval_report(report, segments, gt_seg_indices, judge) -> dict`, `check_judge_config(cfg) -> None`(same-model 가드). 산출: `results/report_eval.json`, (동일 모델 시) `results/human_check_sample.json`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_m9.py`

```python
import pytest
from m9_report_eval import eval_report, check_judge_config, judge_grounded

def _segs(n):
    return [{"idx": i, "start": i * 5, "end": i * 5 + 5,
             "subtitle": f"자막{i}", "caption": f"캡션{i}"} for i in range(n)]

def _report(sent_specs):
    return {"video_id": "v", "sentences": [
        {"sent_id": i, "text": t, "cites": c} for i, (t, c) in enumerate(sent_specs)]}

def test_uncited_sentence_auto_ungrounded_without_judge_call():
    calls = []
    judge = lambda prompt: (calls.append(prompt) or '{"match": true}')
    rep = _report([("근거 없는 문장", [])])
    out = eval_report(rep, _segs(3), gt_seg_indices=[0], judge=judge)
    assert out["per_sentence"][0]["grounded"] is False   # 자동 ungrounded [15-1]
    # coverage judge 1회만 호출 (groundedness는 judge 호출 없음)
    assert all("일치" not in p or "문장" not in p for p in calls) or len(calls) == 1

def test_rates_computed():
    # cites 있는 문장은 judge true → grounded, coverage는 seg0만 언급됨
    def judge(prompt):
        return '{"match": true}' if "seg#0" in prompt or "자막0" in prompt \
            else '{"match": false}'
    rep = _report([("사건 [seg#0]", [0]), ("무근거", [])])
    out = eval_report(rep, _segs(3), gt_seg_indices=[0, 1], judge=judge)
    assert out["groundedness_rate"] == 0.5               # 2문장 중 1개 grounded
    assert out["coverage_rate"] == 0.5                   # gt 2개 중 1개 커버

def test_judge_grounded_conservative_on_parse_failure():
    judge = lambda prompt: "잘 모르겠습니다"              # JSON 아님 → 보수 판정 false
    ok = judge_grounded({"text": "문장", "cites": [0]}, _segs(1), judge)
    assert ok is False                                    # [v2 17-4]

def test_same_model_judge_guard():
    cfg = {"report_model": "Qwen/Qwen2.5-7B-Instruct",
           "judge_model": "Qwen/Qwen2.5-7B-Instruct", "same_model_judge": False}
    with pytest.raises(ValueError, match="same_model_judge"):
        check_judge_config(cfg)
    cfg["same_model_judge"] = True
    check_judge_config(cfg)                               # 명시하면 통과
    cfg2 = {"report_model": "Qwen/Qwen2.5-7B-Instruct", "judge_model": None,
            "same_model_judge": False}
    with pytest.raises(ValueError, match="judge_model"):
        check_judge_config(cfg2)
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_m9.py -v` / Expected: FAIL

- [ ] **Step 3: 구현** — `src/m9_report_eval.py`

```python
"""M9 AAR 평가: Coverage(LLM-judge 이진) + Groundedness(G-Eval 3단계 CoT).
cites==[] 문장은 judge 없이 자동 ungrounded. [DESIGN_SPEC 4-9, v2 14·17장]"""
import argparse, json, random, re
from pathlib import Path
import common
from llm import make_llm
from m6_evaluate import load_queries

_GROUNDED_PROMPT = """당신은 영상 리포트 검증자입니다. 아래 3단계로 판정하세요.
① 검증 대상 문장이 주장하는 내용을 먼저 요약하라.
② 인용된 세그먼트들의 실제 내용(자막·캡션)을 요약하라.
③ 두 내용이 일치하는지 근거를 들어 판정하라.
확신이 없으면 반드시 false로 보수 판정하라.
마지막 줄에 JSON으로만 답하라: {{"match": true}} 또는 {{"match": false}}

검증 대상 문장: {sentence}

인용된 세그먼트 내용:
{segments}
"""

_COVERAGE_PROMPT = """아래 리포트가 다음 세그먼트의 내용을 언급했는지 판정하세요.
확신이 없으면 반드시 false로 보수 판정하라.
마지막 줄에 JSON으로만 답하라: {{"match": true}} 또는 {{"match": false}}

세그먼트 (idx {idx}): subtitle: "{subtitle}" caption: "{caption}"

리포트:
{report}
"""


def _parse_verdict(text: str) -> bool:
    """judge 출력에서 최종 판정 파싱. 실패 시 보수적으로 False. [v2 17-4]"""
    matches = re.findall(r'"match"\s*:\s*(true|false)', text, re.IGNORECASE)
    return matches[-1].lower() == "true" if matches else False


def _fmt_segs(segs) -> str:
    return "\n".join(f'[seg#{s["idx"]}] subtitle: "{s["subtitle"]}" '
                     f'caption: "{s["caption"]}"' for s in segs)


def judge_grounded(sentence: dict, cited_segments: list[dict], judge) -> bool:
    """복수 인용은 전부 함께 제공(개별 대조 시 정당한 종합 서술이 오분류됨). [14-2]"""
    prompt = _GROUNDED_PROMPT.format(sentence=sentence["text"],
                                     segments=_fmt_segs(cited_segments))
    return _parse_verdict(judge(prompt))


def judge_coverage(report_text: str, segment: dict, judge) -> bool:
    prompt = _COVERAGE_PROMPT.format(idx=segment["idx"], subtitle=segment["subtitle"],
                                     caption=segment["caption"], report=report_text)
    return _parse_verdict(judge(prompt))


def eval_report(report: dict, segments: list[dict], gt_seg_indices: list[int],
                judge) -> dict:
    by_idx = {s["idx"]: s for s in segments}
    per_sentence = []
    for s in report["sentences"]:
        if not s["cites"]:
            grounded = False                            # 자동 ungrounded, judge 호출 없음
        else:
            grounded = judge_grounded(s, [by_idx[c] for c in s["cites"]], judge)
        per_sentence.append({"sent_id": s["sent_id"], "cites": s["cites"],
                             "grounded": grounded})
    report_text = "\n".join(s["text"] for s in report["sentences"])
    per_gt = [{"seg_idx": i, "covered": judge_coverage(report_text, by_idx[i], judge)}
              for i in sorted(set(gt_seg_indices))]
    return {
        "groundedness_rate": round(
            sum(p["grounded"] for p in per_sentence) / max(len(per_sentence), 1), 4),
        "coverage_rate": round(
            sum(p["covered"] for p in per_gt) / max(len(per_gt), 1), 4),
        "per_sentence": per_sentence, "per_gt_segment": per_gt}


def check_judge_config(cfg: dict) -> None:
    """judge 모델 규정 [v2 17-6]: 다른 패밀리 1순위, 동일 시 same_model_judge 명시 필수."""
    if not cfg.get("judge_model"):
        raise ValueError("judge_model 미지정 — report_model과 다른 패밀리로 지정하라 [v2 17-6]")
    if cfg["judge_model"] == cfg["report_model"] and not cfg.get("same_model_judge"):
        raise ValueError("report_model과 judge_model이 동일 — 의도라면 config에 "
                         "same_model_judge: true를 명시하라 [v2 17-6]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--queries", default="data/queries/queries.jsonl")
    args = ap.parse_args()
    cfg = common.load_config(args.config)
    check_judge_config(cfg)
    wdir = common.work_dir(cfg, args.video_id)
    doc = common.load_segments(wdir / "segments.json", require=["subtitle", "caption"])
    report = json.loads((wdir / "report.json").read_text(encoding="utf-8"))
    n = doc["n_segments"]
    for s in report["sentences"]:                       # 검증 포인트 [4-9]
        assert all(0 <= c < n for c in s["cites"]), f"cites 범위 위반: {s}"

    test_qs = [q for q in load_queries(args.queries)
               if q["split"] == "test" and q["video_id"] == args.video_id]
    gt_idx = [i for q in test_qs for i in q["gt_seg_idx"]]

    judge = make_llm(cfg["judge_model"], max_new_tokens=512)
    out = eval_report(report, doc["segments"], gt_idx, judge)
    rdir = Path(cfg["paths"]["results"]); rdir.mkdir(exist_ok=True)
    common.atomic_write_json(rdir / "report_eval.json",
                             {"video_id": args.video_id,
                              "judge_model": cfg["judge_model"], **out})
    print(f"M9 완료: coverage={out['coverage_rate']} groundedness={out['groundedness_rate']}")

    if cfg.get("same_model_judge"):                     # 사람 스팟체크 자동 추출 [4-9]
        rng = random.Random(cfg["seed"])
        pool = [s for s in report["sentences"]]
        sample = rng.sample(pool, min(cfg["human_check_n"], len(pool)))
        common.atomic_write_json(rdir / "human_check_sample.json", sample)
        print(f"same_model_judge=true → 사람 스팟체크 {len(sample)}문장 추출")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_m9.py -v` / Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/m9_report_eval.py tests/test_m9.py
git commit -m "feat: M9 AAR 평가 — G-Eval judge + same-model 가드 + 스팟체크"
```

---

### Task 12: 전체 테스트 + E2E 스모크 (M1→M5)

**Files:**
- Create: `data/queries/queries.jsonl` (스모크용 소규모 질의 2~3개, 수동 작성)

**Interfaces:**
- Consumes: 전 모듈

- [ ] **Step 1: 전체 단위 테스트** — Run: `python -m pytest tests/ -v` / Expected: 전부 PASS

- [ ] **Step 2: E2E (GPU 필요 단계는 로컬 3B+4bit 또는 서버에서)**

```bash
python src/m1_preprocess.py --video-id spiderman_trailer
python src/m2_keyframe.py   --video-id spiderman_trailer
python src/m3_generate.py   --video-id spiderman_trailer
python src/m4_index.py      --video-id spiderman_trailer
python src/m5_search.py     --video-id spiderman_trailer --query "스파이더맨이 건물 사이를 날아다니는 장면" --alpha 0.5
```
Expected: 각 모듈 완료 로그 + 최종 top-5 랭킹. `--config config.yaml`은 기본값.

- [ ] **Step 3: 검증 체크리스트 (PROJECT_RULES.md) 대조**

- M1: n_segments == ceil(duration/5), 마지막 end == duration(±0.5s)
- M2: 전 세그먼트 rep_frame 존재, is_static 비율 로그
- M3: caption 빈 문자열 0건
- M4: npy row == n_segments, norm 편차 < 1e-4, meta.json 기록
- 스키마 위반 시 "run mX first" 에러 확인: `python src/m4_index.py --video-id 없는id` → FileNotFoundError 메시지 확인

- [ ] **Step 4: Commit**

```bash
git add data/queries/queries.jsonl
git commit -m "chore: E2E 스모크 질의셋 + 전체 파이프라인 검증"
```

---

## Self-Review 결과

- **스펙 커버리지:** DESIGN_SPEC 4-1~4-9 전 모듈 → Task 2~11. 스키마 3-1~3-5 → common.py·각 모듈 산출. 절대 규칙 10개 → Global Constraints + 해당 태스크 테스트로 강제.
- **미포함(의도적):** queries.jsonl 본 라벨링(데이터 명세서 Excel에서 export — 코드 아님), 샷 경계 표시(v2 1장 "선택"), KURE vs BGE-M3 비교 실험(코드는 config 교체로 지원, 실험은 7~8주차), 11주차 ablation.
- **타입 일관성:** `Result(idx, score, start, end)` — M5 정의, M6·M7 공유 확인. `embed_texts` — M4 정의, M5 재사용 확인. `make_llm` — llm.py 정의, M8·M9 공유 확인.

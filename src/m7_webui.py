"""M7-W 웹 UI 서버: 업로드 → M1~M4 서브프로세스 인덱싱 → 채팅 검색.
검색은 m5_search.search를 그대로 import (재구현 금지).
[docs/superpowers/specs/2026-07-07-webui-design.md]"""
import argparse, json, re, subprocess, sys, threading, time
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

import common
from m5_search import VideoIndex, search, search_with_stats

PIPELINE = ("m1_preprocess.py", "m2_keyframe.py", "m3_generate.py", "m4_index.py")
STAGE = {"m1_preprocess.py": "m1", "m2_keyframe.py": "m2",
         "m3_generate.py": "m3", "m4_index.py": "m4"}


def sanitize_video_id(stem: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", stem)


def run_module_subprocess(script: str, config_path: str, video_id: str) -> None:
    """M1~M4 CLI 한 단계 실행. 실패 시 stderr 꼬리를 담아 RuntimeError."""
    proc = subprocess.run(
        [sys.executable, str(Path("src") / script),
         "--config", config_path, "--video-id", video_id],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-5:])
        raise RuntimeError(f"{script} 실패:\n{tail}")


class JobStore:
    """인덱싱 상태 저장소. GPU 자원 보호를 위해 동시 1건만 허용."""
    def __init__(self):
        self._lock = threading.Lock()
        self._status: dict[str, dict] = {}
        self._busy = False
        self._current: str | None = None

    def try_start(self, video_id: str) -> bool:
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            self._current = video_id
            self._status[video_id] = {"stage": "m1", "detail": "시작 대기"}
            return True

    def set(self, video_id: str, stage: str, detail: str = "") -> None:
        with self._lock:
            self._status[video_id] = {"stage": stage, "detail": detail}
            if stage in ("done", "error"):
                self._busy = False

    def get(self, video_id: str) -> dict | None:
        with self._lock:
            return self._status.get(video_id)

    def current(self) -> str | None:
        with self._lock:
            return self._current


def _read_segments_progress(cfg: dict, video_id: str, count_fn) -> dict | None:
    """segments.json 기반 진행률 {n, total} 계산. 없거나 읽기 실패 시 None(진행률 생략)."""
    seg_path = common.work_dir(cfg, video_id) / "segments.json"
    if not seg_path.exists():
        return None
    try:
        doc = json.loads(seg_path.read_text(encoding="utf-8"))
        return {"n": count_fn(doc), "total": doc["n_segments"]}
    except Exception:                         # 쓰기 도중 등 읽기 실패 → progress 생략
        return None


def _progress_m2(cfg: dict, video_id: str) -> dict | None:
    frames_dir = common.work_dir(cfg, video_id) / "frames"
    n_frames = len(list(frames_dir.glob("*.jpg"))) if frames_dir.exists() else 0
    return _read_segments_progress(cfg, video_id, lambda doc: n_frames)


def _progress_m3(cfg: dict, video_id: str) -> dict | None:
    return _read_segments_progress(
        cfg, video_id,
        lambda doc: sum(1 for s in doc["segments"] if s.get("caption")))


def _log_search(cfg: dict, video_id: str, query: str, alpha: float,
                stats: dict, top1) -> None:
    """검색 1건을 search_log.jsonl에 append. 무관련 질의 판정 근거 축적용 [HIGH-2].
    로깅은 best-effort — 실패해도 검색 응답에 영향 없음."""
    try:
        results_dir = Path(cfg["paths"]["results"])
        results_dir.mkdir(parents=True, exist_ok=True)
        tau = cfg.get("abstention_tau")
        entry = {"ts": time.time(), "video_id": video_id, "query": query,
                 "alpha": alpha, **stats,
                 # 당시 tau·배너 판정을 함께 기록 — tau 재캘리브레이션 후에도 "사용자가
                 # 실제로 본 경고"를 복원 가능하게 [리뷰 2026-07-11 Minor]
                 "abstention_tau": tau,
                 "low_relevance": (bool(stats["raw_sub_max"] < tau)
                                   if tau is not None else None),
                 "top1_idx": top1.idx if top1 is not None else None,
                 "top1_score": top1.score if top1 is not None else None}
        with open(results_dir / "search_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def create_app(cfg: dict, config_path: str, alpha: float,
               run_module=run_module_subprocess,
               search_fn=search, load_index=VideoIndex.load,
               search_stats_fn=None) -> FastAPI:
    app = FastAPI()
    jobs = JobStore()
    index_cache: dict[str, VideoIndex] = {}
    videos_dir = Path(cfg["paths"]["data"]) / "videos"
    html_path = Path(__file__).parent / "webui" / "index.html"

    def _pipeline(video_id: str) -> None:
        try:
            for script in PIPELINE:
                jobs.set(video_id, STAGE[script], f"{script} 실행 중")
                run_module(script, config_path, video_id)
            index_cache.pop(video_id, None)      # 재인덱싱 시 캐시 무효화
            jobs.set(video_id, "done")
        except Exception as e:                   # 단계 실패 → UI에 원인 표시
            jobs.set(video_id, "error", str(e))

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse(html_path.read_text(encoding="utf-8"))

    @app.post("/api/upload")
    async def upload(file: UploadFile):
        if not (file.filename or "").lower().endswith(".mp4"):
            raise HTTPException(400, "mp4 파일만 업로드할 수 있어요")
        video_id = sanitize_video_id(Path(file.filename).stem)
        if not jobs.try_start(video_id):
            raise HTTPException(409, "다른 영상 인덱싱 중이에요 — 잠시 후 다시 시도하세요")
        try:
            videos_dir.mkdir(parents=True, exist_ok=True)
            (videos_dir / f"{video_id}.mp4").write_bytes(await file.read())
        except Exception as e:
            jobs.set(video_id, "error", f"업로드 저장 실패: {e}")
            raise HTTPException(500, f"업로드 저장 실패: {e}")
        threading.Thread(target=_pipeline, args=(video_id,), daemon=True).start()
        return {"video_id": video_id}

    @app.get("/api/status/{video_id}")
    def status(video_id: str):
        st = jobs.get(video_id)
        if st is None:
            raise HTTPException(404, f"{video_id}: 업로드 기록 없음")
        result = dict(st)
        progress = None
        if st["stage"] == "m2":
            progress = _progress_m2(cfg, video_id)
        elif st["stage"] == "m3":
            progress = _progress_m3(cfg, video_id)
        if progress is not None:
            result["progress"] = progress
        return result

    @app.get("/api/current")
    def current():
        video_id = jobs.current()
        if video_id is None:
            return {"video_id": None}
        st = jobs.get(video_id)
        return {"video_id": video_id, "stage": st["stage"], "detail": st["detail"]}

    @app.get("/api/segments/{video_id}")
    def segments(video_id: str):
        video_id = sanitize_video_id(video_id)
        path = common.work_dir(cfg, video_id) / "segments.json"
        if not path.exists():
            raise HTTPException(404, f"{video_id}: 인덱스 없음")
        try:
            doc = common.load_segments(path, require=["subtitle", "caption"],
                                       seg_len=cfg["seg_len_sec"])
        except ValueError as e:                  # 불변식/필드 누락 → 안내
            raise HTTPException(404, str(e))
        keys = ("idx", "start", "end", "subtitle", "caption")
        return {"segments": [{k: s[k] for k in keys} for s in doc["segments"]]}

    @app.post("/api/search")
    def do_search(body: dict):
        video_id = sanitize_video_id(body.get("video_id", ""))
        query = body.get("query", "")
        if not query.strip():
            raise HTTPException(400, "질의가 비어 있어요")
        st = jobs.get(video_id)
        if st is not None and st["stage"] == "error":
            raise HTTPException(409, "인덱싱이 실패했어요 — 영상을 다시 업로드해 주세요")
        if st is not None and st["stage"] != "done":
            raise HTTPException(409, "인덱싱이 끝나면 검색할 수 있어요")
        if video_id not in index_cache:
            try:
                index_cache[video_id] = load_index(cfg, video_id)
            except (FileNotFoundError, ValueError) as e:   # 산출물 미존재/불일치 → 안내
                raise HTTPException(404, str(e))
        video = index_cache[video_id]
        # stats 우선: search_stats_fn이 지정됐거나 search_fn이 기본값(search)이면
        # search_with_stats로 raw 코사인 통계를 얻는다. search_fn만 스텁 주입된
        # 경우(기존 M6/M7 테스트 패턴)는 stats 없이 결과만 사용 — 하위호환.
        stats_fn = search_stats_fn or (search_with_stats if search_fn is search else None)
        stats = None
        if stats_fn is not None:
            results, stats = stats_fn(query, video, alpha, cfg)
        else:
            results = search_fn(query, video, alpha, cfg)
        top = results[:3]
        response = {"results": [
            {"idx": r.idx, "start": int(r.start), "end": int(r.end),
             "score": round(r.score, 3),
             "subtitle": video.segments[r.idx]["subtitle"],
             "caption": video.segments[r.idx]["caption"]} for r in top]}
        if stats is not None:
            response["raw"] = stats
            # 8-2 abstention: 랭킹·기존 필드 불변, 표시 계층용 추가 필드만 부기.
            # τ 미달 = "이 영상에 관련 구간이 없을 수 있음" 경고(결과 은폐 금지).
            tau = cfg.get("abstention_tau")
            if tau is not None:
                response["low_relevance"] = bool(stats["raw_sub_max"] < tau)
            _log_search(cfg, video_id, query, alpha, stats, top[0] if top else None)
        return response

    @app.get("/api/video/{video_id}")
    def video_file(video_id: str):
        p = videos_dir / f"{sanitize_video_id(video_id)}.mp4"
        if not p.exists():
            raise HTTPException(404, "영상 파일 없음")
        return FileResponse(p, media_type="video/mp4")   # starlette Range 지원

    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--alpha", type=float, required=True,
                    help="M6 grid search로 확정한 alpha_star 값(results/alpha_search_dev.json 참조)")
    ap.add_argument("--port", type=int, default=7860)
    args = ap.parse_args()
    import uvicorn
    cfg = common.load_config(args.config)
    uvicorn.run(create_app(cfg, args.config, args.alpha),
                host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()

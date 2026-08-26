"""M7-W 웹 UI 서버: 업로드 → M1~M4 서브프로세스 인덱싱 → 채팅 검색.
검색은 m5_search.search를 그대로 import (재구현 금지).
[docs/superpowers/specs/2026-07-07-webui-design.md]"""
import argparse, json, re, subprocess, sys, threading, time
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

import common
import deployment
import eligibility
from m5_search import VideoIndex, search, search_with_stats

PIPELINE = ("m1_preprocess.py", "m2_keyframe.py", "m3_generate.py", "m4_index.py")
DEFAULT_TOP_K = 3           # 기존 동작 불변. 요청으로만 늘린다

STAGE = {"m1_preprocess.py": "m1", "m2_keyframe.py": "m2",
         "m3_generate.py": "m3", "m4_index.py": "m4"}


_DISPLAY_REP = re.compile(r"(\S{1,15})(?:\s+\1){2,}")
_DISPLAY_CJK = re.compile(r"[一-鿿぀-ヿ]+")


def display_clean(text: str) -> str:
    """표시 계층 전용 정리: Whisper 반복 환각 collapse(3회 이상 연속 반복 → 1회) +
    오염 판정 임계 미만의 잔여 한자·가나 제거. 인덱스·임베딩·랭킹·평가에는 불개입
    [실사용 테스트 2026-07-13]."""
    return _DISPLAY_CJK.sub("", _DISPLAY_REP.sub(r"\1", text))


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


def low_relevance_flag(stats: dict, tau) -> bool | None:
    """abstention 배너 판정 — **응답과 로그가 같은 값을 쓰도록 한 곳에서 계산한다.**

    이전에는 두 곳에서 따로 계산했고, 8-2 개정(sub 단독 → max(sub, cap)) 때 응답만
    바뀌어 로그가 다른 판정을 기록했다. 기존 테스트가 그 옛 판정을 정답으로 고정하고
    있었다 [정합성 감사 2026-08-26]. 규칙이 또 바뀌어도 갈라지지 않게 함수로 묶는다.
    """
    if tau is None:
        return None
    return bool(max(stats["raw_sub_max"], stats["raw_cap_max"]) < tau)


def _log_search(cfg: dict, video_id: str, query: str, alpha: float,
                stats: dict, top1, low_relevance=None) -> None:
    """검색 1건을 search_log.jsonl에 append. 무관련 질의 판정 근거 축적용 [HIGH-2].
    로깅은 best-effort — 실패해도 검색 응답에 영향 없음."""
    try:
        results_dir = Path(cfg["paths"]["results"])
        results_dir.mkdir(parents=True, exist_ok=True)
        tau = cfg.get("abstention_tau")
        # per_seg는 표시 전용(타임라인 리본)이라 로그에서 뺀다 — 검색 1건마다
        # 세그먼트 수만큼의 배열 3개가 쌓이면 시연 몇 번에 로그가 수 MB가 된다.
        loggable = {k: v for k, v in stats.items() if k != "per_seg"}
        entry = {"ts": time.time(), "video_id": video_id, "query": query,
                 "alpha": alpha, **loggable,
                 # 당시 tau·배너 판정을 함께 기록 — tau 재캘리브레이션 후에도 "사용자가
                 # 실제로 본 경고"를 복원 가능하게 [리뷰 2026-07-11 Minor]
                 # 판정은 호출부가 응답에 쓴 값을 그대로 받는다 — 여기서 다시 계산하면
                 # 규칙이 바뀔 때 또 갈라진다. 호출부가 안 넘기면 같은 함수로 계산한다.
                 "abstention_tau": tau,
                 "low_relevance": (low_relevance if low_relevance is not None
                                   else low_relevance_flag(stats, tau)),
                 "top1_idx": top1.idx if top1 is not None else None,
                 "top1_score": top1.score if top1 is not None else None}
        with open(results_dir / "search_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def create_app(cfg: dict, config_path: str, alpha: float,
               run_module=run_module_subprocess,
               search_fn=search, load_index=VideoIndex.load,
               search_stats_fn=None, enforce_demo_policy: bool = True) -> FastAPI:
    """`enforce_demo_policy`는 **기본 True다(fail-closed)**.

    진입점(`scripts/demo.py`)의 preflight는 시작 시 `--video-id` 하나만 본다. 그런데
    이 API는 요청 본문의 `video_id`를 그대로 받으므로, 서버가 뜬 뒤에는 test split
    영상도 조회·재생됐다(2026-08-26 설계 정합성 감사에서 발견). 자격 판정을 **요청
    경로에서도** 한다 — 선언이 아니라 강제 지점이 있어야 한다.
    """
    app = FastAPI()
    jobs = JobStore()
    index_cache: dict[str, VideoIndex] = {}
    videos_dir = Path(cfg["paths"]["data"]) / "videos"
    html_path = Path(__file__).parent / "webui" / "index.html"

    def _guard(video_id: str) -> None:
        if not enforce_demo_policy:
            return
        reason = eligibility.demo_block_reason(video_id)
        if reason:
            raise HTTPException(403, reason)

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
        _guard(video_id)
        # 조회 금지와 **덮어쓰기 금지**는 다른 문제다. 같은 이름 업로드로 확정 인덱스의
        # 원본 영상을 갈아치울 수 있으면 배포 정합성이 무너지고, text_hash·embed_model은
        # 둘 다 인덱스만 보므로 이것을 잡지 못한다 [경계 감사 2026-08-26]
        if (videos_dir / f"{video_id}.mp4").exists() or common.work_dir(cfg, video_id).is_dir():
            raise HTTPException(
                409, f"{video_id}는 이미 있는 영상이다 — 기존 산출물을 덮지 않는다. "
                     f"다시 인덱싱하려면 파일 이름을 바꿔 올려라")
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
        # 이 route도 video_id를 받고, m2·m3 단계에서 **segments.json·frames를 읽는다**.
        # 상태만 돌려준다고 해서 예외를 두지 않는다 — 기준은 "guard를 거치지 않고
        # restricted 영상에 도달하는 route가 0개"다 [경계 감사 2026-08-26]
        video_id = sanitize_video_id(video_id)
        _guard(video_id)
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

    @app.get("/api/meta")
    def meta():
        """확정 설정 표시용. alpha는 config에 없고 CLI 주입값이라(절대규칙 5)
        서버만 알고 있다 — 헤더에 띄워 두면 발표 중 되묻지 않아도 된다."""
        return {"alpha": alpha, "seg_len_sec": cfg["seg_len_sec"],
                "embed_model": cfg["embed_model"]}

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
        _guard(video_id)
        path = common.work_dir(cfg, video_id) / "segments.json"
        if not path.exists():
            raise HTTPException(404, f"{video_id}: 인덱스 없음")
        try:
            doc = common.load_segments(path, require=["subtitle", "caption"],
                                       seg_len=cfg["seg_len_sec"])
        except ValueError as e:                  # 불변식/필드 누락 → 안내
            raise HTTPException(404, str(e))
        return {"segments": [
            {"idx": s["idx"], "start": s["start"], "end": s["end"],
             "subtitle": display_clean(s["subtitle"]),
             "caption": display_clean(s["caption"])} for s in doc["segments"]]}

    @app.post("/api/search")
    def do_search(body: dict):
        video_id = sanitize_video_id(body.get("video_id", ""))
        _guard(video_id)
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
        n_seg = len(video.segments)
        # top_k는 표시 계층 파라미터다 — 랭킹·점수·평가에 영향이 없다.
        try:
            top_k = int(body.get("top_k", DEFAULT_TOP_K))
        except (TypeError, ValueError):
            raise HTTPException(400, "top_k가 정수가 아니에요")
        if top_k < 1:
            raise HTTPException(400, "top_k는 1 이상이어야 해요")
        top_k = min(top_k, n_seg)
        # stats 우선: search_stats_fn이 지정됐거나 search_fn이 기본값(search)이면
        # search_with_stats로 raw 코사인 통계를 얻는다. search_fn만 스텁 주입된
        # 경우(기존 M6/M7 테스트 패턴)는 stats 없이 결과만 사용 — 하위호환.
        stats_fn = search_stats_fn or (
            (lambda q, v, al, c: search_with_stats(q, v, al, c, with_per_seg=True))
            if search_fn is search else None)
        stats = None
        if stats_fn is not None:
            results, stats = stats_fn(query, video, alpha, cfg)
        else:
            results = search_fn(query, video, alpha, cfg)
        top = results[:top_k]
        # 응답에 rank·seek_to·질의 echo를 담는다 — 결과를 파일로 남기거나 보고서에
        # 옮길 때 배열 순서에 의존하지 않게 한다 [FINALIZATION-P1].
        response = {
            "video_id": video_id, "query": query, "alpha": alpha,
            "top_k": top_k, "n_segments": n_seg,
            "duration_sec": int(video.segments[-1]["end"]) if n_seg else 0,
            "results": [
                {"rank": i + 1, "idx": r.idx,
                 "start": int(r.start), "end": int(r.end),
                 "seek_to": int(r.start), "score": round(r.score, 3),
                 "subtitle": display_clean(video.segments[r.idx]["subtitle"]),
                 "caption": display_clean(video.segments[r.idx]["caption"])}
                for i, r in enumerate(top)]}
        if stats is not None:
            response["raw"] = stats
            # 8-2 abstention: 랭킹·기존 필드 불변, 표시 계층용 추가 필드만 부기.
            # τ 미달 = "이 영상에 관련 구간이 없을 수 있음" 경고(결과 은폐 금지).
            # 채널은 max(sub, cap) — sub 단독은 무발화 장면을 찾는 장면형 유관 질의
            # (자막과 원래 안 붙음)를 무관 질의와 구분 못 해 오배제가 장면형에 쏠린다
            # [8-2 개정, 2026-07-13 설계 점검 1]
            flag = low_relevance_flag(stats, cfg.get("abstention_tau"))
            if flag is not None:
                response["low_relevance"] = flag
            _log_search(cfg, video_id, query, alpha, stats,
                        top[0] if top else None, low_relevance=flag)
        return response

    @app.get("/api/video/{video_id}")
    def video_file(video_id: str):
        video_id = sanitize_video_id(video_id)
        _guard(video_id)
        p = videos_dir / f"{video_id}.mp4"
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
    ap.add_argument("--allow-nondeployment-alpha", action="store_true",
                    help="배포 확정 α가 아닌 값으로 띄운다(진단 전용) — 그 실행은 배포 구성이 아니다")
    args = ap.parse_args()
    # README가 이 실행을 함께 안내하므로 **지원 진입점**이다. preflight는 없어도
    # 배포 identity의 α는 여기서 강제한다 — 진입점에 따라 identity가 달라지면 안 된다
    # [감사 2026-08-26]
    try:
        deployment.check_alpha(args.alpha, args.allow_nondeployment_alpha)
    except deployment.DeploymentIdentityError as e:
        raise SystemExit(str(e))
    import uvicorn
    cfg = common.load_config(args.config)
    # 검색 역할 필수 키 — abstention_tau가 없으면 저관련 경고가 조용히 꺼진다
    try:
        deployment.validate_production_config(cfg, roles=("search",))
    except deployment.ConfigContractError as e:
        raise SystemExit(str(e))
    uvicorn.run(create_app(cfg, args.config, args.alpha),
                host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()

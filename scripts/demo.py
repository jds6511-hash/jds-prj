"""데모 단일 진입점 — preflight 후 현행 배포 시스템을 띄운다.

`python scripts/demo.py --video-id <id>` 하나로 끝난다. 새 검색 구현을 만들지 않고
`src/m5_search.search`와 `src/m7_webui`를 그대로 쓴다.

**fail-closed.** 모델·양자화·임베딩 모델·α·인덱스 정합이 배포 구성과 다르면 시작하지
않는다. "일단 실행하고 이상하면 알림"을 금지하는 것이 이 파일의 목적이다.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common                                                       # noqa: E402
import deployment                                                   # noqa: E402
import eligibility                                                  # noqa: E402

# 현행 배포 구성은 `src/deployment.py`가 단일 출처다. 값을 여기에 다시 적지 않는다 —
# 같은 dict가 demo.py와 e2e_external.py에 복사돼 있었고 표류 위험이 있었다
# (감사 2026-08-26). 이름은 기존 호출부 호환을 위해 유지한다.
DEPLOYMENT = deployment.DEPLOYMENT
DEPLOYMENT_ALPHA = deployment.ALPHA

REQUIRED_ARTIFACTS = ("segments.json", "emb_sub.npy", "emb_cap.npy", "meta.json")

# 자격 정책은 `src/eligibility.py`가 단일 출처다 — 진입점과 웹 API가 같은 함수를 쓴다.
# 2026-08-26 감사: 이 preflight는 시작 시 --video-id 하나만 보므로, 요청 경로
# (m7_webui의 /api/search·/api/segments·/api/video)에도 같은 판정이 걸려 있어야 한다.
TEST_SPLIT_VIDEOS = eligibility.TEST_SPLIT_VIDEOS


def demo_ineligible(video_id: str) -> bool:
    """E2E 전용 등 데모 부적격 여부. 판정은 eligibility 모듈이 한다."""
    return not eligibility.demo_eligible(video_id)


class PreflightError(RuntimeError):
    pass


def _device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _aar_status(wdir: Path) -> dict:
    """AAR 사전 생성물(report.json) 사용 가능 여부. 검색 데모를 막지 않는다.

    M8은 로컬 6GB에서 돌지 않으므로 발표에서는 **서버에서 미리 만든 report.json을
    렌더**하는 경로를 쓴다. 여기서는 그 파일이 지금 인덱스와 맞는지만 본다.
    """
    report = wdir / "report.json"
    if not report.is_file():
        return {"available": False,
                "reason": f"{report.name}이 없다 — 서버에서 M8을 돌려 받아와야 한다",
                "path": str(report)}
    from aar_view import check_precomputed
    st = check_precomputed(report, wdir / "segments.json")
    return {"available": st["ok"], "reason": st["reason"], "path": str(report),
            "n_sentences": st.get("n_sentences"),
            "cited_segments": st.get("cited_segments")}


def available_videos(cfg: dict) -> list:
    """인덱스가 완성된 영상만. 부분 산출물은 후보에 넣지 않는다."""
    work = Path(cfg["paths"]["work"])
    if not work.is_dir():
        return []
    return sorted(d.name for d in work.iterdir()
                  if d.is_dir() and all((d / f).is_file()
                                        for f in REQUIRED_ARTIFACTS))


def preflight(cfg: dict, video_id: str, alpha: float) -> dict:
    """시작 전 전수 확인. 통과하지 못하면 예외를 던지고 실행하지 않는다."""
    checks, warnings = 0, []

    block = eligibility.demo_block_reason(video_id)
    if block:
        raise PreflightError(block)
    checks += 1

    if not eligibility.manifest_available():
        warnings.append(f"{eligibility.E2E_MANIFEST.name}이 없다 — E2E 전용 영상 "
                        f"차단이 동작하지 않는다")
    checks += 1

    if abs(float(alpha) - DEPLOYMENT_ALPHA) > 1e-9:
        raise PreflightError(
            f"alpha={alpha}는 배포 확정값이 아니다 (배포 alpha={DEPLOYMENT_ALPHA}). "
            f"데모는 배포 구성으로만 돌린다 — α 탐색은 이 진입점의 일이 아니다")
    checks += 1

    # 값 대조 전에 **키가 있는지** 본다. `.get(key, default)` 경로는 키가 없어도 조용히
    # 돌아가므로(예: abstention_tau 부재 → 저관련 경고가 꺼진다) 여기서 먼저 막는다.
    # 항목 수는 늘리지 않는다 — 아래 identity 루프의 일부로 센다 [fallback 감사 2026-08-26]
    deployment.validate_production_config(cfg, roles=("identity", "search"))

    for key, want in DEPLOYMENT.items():
        got = cfg.get(key)
        if got != want:
            raise PreflightError(
                f"config의 {key}={got!r}가 배포 구성 {want!r}과 다르다 — "
                f"배포 구성 변경은 별도 승인 사건이다")
        checks += 1

    wdir = common.work_dir(cfg, video_id)
    if not wdir.is_dir():
        raise PreflightError(f"{video_id}: 인덱스 디렉터리가 없다 ({wdir}) — "
                             f"M1~M4를 먼저 돌려라")
    missing = [f for f in REQUIRED_ARTIFACTS if not (wdir / f).is_file()]
    if missing:
        raise PreflightError(f"{video_id}: 인덱스 산출물 누락 {missing} — "
                             f"M1~M4를 먼저 돌려라")
    checks += 1

    doc = common.load_segments(wdir / "segments.json",
                              require=["subtitle", "caption", "motion_score"],
                              seg_len=cfg["seg_len_sec"])
    n = len(doc["segments"])
    meta = json.loads((wdir / "meta.json").read_text(encoding="utf-8"))

    want_hash = common.index_text_hash(doc)
    if meta.get("text_hash") != want_hash:
        raise PreflightError(
            f"{video_id}: text_hash 불일치 — 캡션·자막이 바뀐 뒤 m4를 돌리지 "
            f"않았다. 임베딩이 낡았으므로 검색 결과가 무의미하다")
    checks += 1

    if meta.get("embed_model") not in (None, cfg["embed_model"]):
        raise PreflightError(
            f"{video_id}: 인덱스의 embed_model={meta['embed_model']!r}가 현재 "
            f"config {cfg['embed_model']!r}와 다르다 — 점수가 비교 불가다")
    checks += 1

    # 캡션 identity — text_hash는 "캡션과 임베딩이 같은 시점인가"만 본다. 어느 모델이
    # 그 캡션을 썼는지는 `caption_provenance`에만 있고, 그건 2026-08-17 도입이라
    # 확정 인덱스 11편에는 없다(채우려면 재색인). 불일치는 m5가 막고, **증거가 없다는
    # 사실 자체를 여기서 보이게 한다** — 없는 것을 있는 것처럼 넘기지 않는다 [감사 2026-08-26]
    prov = doc.get("caption_provenance")
    if not prov:
        warnings.append(
            f"{video_id}: 캡션 생성 기록(caption_provenance)이 없다 — 이 인덱스의 "
            f"캡션이 config의 caption_model로 만들어졌다는 것을 산출물로 확인할 수 없다")
    # 게이트가 아니라 공시다 — `checks`를 올리지 않는다(mp4·AAR 경고와 같은 취급).

    embs = {}
    for name in ("emb_sub", "emb_cap"):
        a = np.load(wdir / f"{name}.npy")
        if a.ndim != 2 or a.shape[0] != n:
            raise PreflightError(
                f"{video_id}: {name} 행 수 {a.shape}가 구간 수 {n}과 다르다")
        embs[name] = a
    if embs["emb_sub"].shape[1] != embs["emb_cap"].shape[1]:
        raise PreflightError(
            f"{video_id}: 두 채널 임베딩 차원이 다르다 "
            f"{embs['emb_sub'].shape[1]} vs {embs['emb_cap'].shape[1]}")
    checks += 1

    mp4 = Path(cfg["paths"]["data"]) / "videos" / f"{video_id}.mp4"
    playback = mp4.is_file()
    if not playback:
        warnings.append(f"{mp4}가 없다 — 검색은 되지만 재생·구간 이동은 안 된다")

    dev = _device()
    if dev == "cpu":
        warnings.append("CUDA를 찾지 못했다 — 검색은 CPU로도 되지만 인덱싱은 매우 느리다")

    # 발표 fallback: 미리 만들어 둔 report.json이 지금 이 인덱스로 렌더되는가.
    # 없거나 낡아도 **검색 데모는 막지 않는다** — AAR만 못 보여줄 뿐이다.
    aar = _aar_status(wdir)
    if not aar["available"]:
        warnings.append(f"AAR 사전 생성물을 쓸 수 없다 — {aar['reason']}")

    return {
        "ok": True, "video_id": video_id, "alpha": float(alpha),
        "caption_model": cfg["caption_model"], "vlm_4bit": cfg["vlm_4bit"],
        "embed_model": cfg["embed_model"],
        "seg_len_sec": cfg["seg_len_sec"],
        "static_threshold": cfg["static_threshold"],
        "abstention_tau": cfg.get("abstention_tau"),
        "n_segments": n, "text_hash": want_hash,
        "embedding_dim": int(embs["emb_sub"].shape[1]),
        "playback_available": playback,
        "video_path": str(mp4) if playback else None,
        "device": dev, "work_dir": str(wdir), "aar": aar,
        "checks_passed": checks, "warnings": warnings,
        "phase": "FINALIZATION",
        "note": ("배포 구성 데모다. 연구 비교 실험이 아니고 평가 결과를 만들지 "
                 "않는다"),
    }


def _print(r: dict) -> None:
    print(f"preflight PASS — 확인 {r['checks_passed']}항목")
    for k in ("video_id", "n_segments", "caption_model", "vlm_4bit", "embed_model",
              "alpha", "seg_len_sec", "static_threshold", "abstention_tau",
              "embedding_dim", "device", "playback_available"):
        print(f"  {k:20s} {r[k]}")
    print(f"  text_hash            {r['text_hash'][:16]}…")
    a = r["aar"]
    print(f"  AAR 사전 생성물        "
          + (f"사용 가능 (문장 {a['n_sentences']} · 인용 구간 "
             f"{a['cited_segments']})" if a["available"] else "없음/사용 불가"))
    for w in r["warnings"]:
        print(f"  [경고] {w}")


def main():
    ap = argparse.ArgumentParser(
        description="데모 진입점 — preflight 후 배포 구성으로 웹 UI를 띄운다")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id")
    ap.add_argument("--alpha", type=float, default=DEPLOYMENT_ALPHA)
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("--check-only", action="store_true",
                    help="preflight만 하고 서버를 띄우지 않는다")
    ap.add_argument("--list", action="store_true",
                    help="인덱스가 완성된 영상 목록")
    a = ap.parse_args()

    cfg = common.load_config(a.config)
    if a.list or not a.video_id:
        vids = available_videos(cfg)
        demo_ok = [v for v in vids
                   if v not in TEST_SPLIT_VIDEOS and not demo_ineligible(v)]
        print("인덱스 완성 영상:")
        for v in vids:
            if v in TEST_SPLIT_VIDEOS:
                tag = "  (test split — 데모 불가)"
            elif demo_ineligible(v):
                tag = "  (external E2E 전용 — 데모 불가)"
            else:
                tag = ""
            print(f"  {v}{tag}")
        if not a.video_id:
            print("\n--video-id 를 지정해라. 예: "
                  f"python scripts/demo.py --video-id {demo_ok[0]}"
                  if demo_ok else "\n데모 가능한 영상이 없다 — M1~M4를 먼저 돌려라")
            return 0 if a.list else 2

    try:
        r = preflight(cfg, a.video_id, a.alpha)
    except PreflightError as e:
        print(f"preflight FAIL — 실행하지 않는다\n  {e}", file=sys.stderr)
        return 1
    _print(r)

    if a.check_only:
        return 0

    print(f"\n웹 UI 시작 — http://127.0.0.1:{a.port}  (alpha={r['alpha']})")
    import uvicorn
    from m7_webui import create_app
    uvicorn.run(create_app(cfg, a.config, a.alpha),
                host="127.0.0.1", port=a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

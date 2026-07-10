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
    def load(cls, cfg: dict, video_id: str,
              static_threshold: float | None = None) -> "VideoIndex":
        wdir = common.work_dir(cfg, video_id)
        require = ["subtitle", "caption", "is_static"]
        if static_threshold is not None:
            require.append("motion_score")   # [8-5(2)]
        doc = common.load_segments(wdir / "segments.json", require=require,
                                   seg_len=cfg["seg_len_sec"])
        for name in ("emb_sub.npy", "emb_cap.npy", "meta.json"):
            if not (wdir / name).exists():
                raise FileNotFoundError(f"{name} 없음 — run m4_index.py first")
        meta = json.loads((wdir / "meta.json").read_text(encoding="utf-8"))
        if meta["embed_model"] != cfg["embed_model"]:   # 모델 혼입 방지 [4-4]
            raise ValueError(f"임베딩 모델 불일치: index={meta['embed_model']} "
                             f"config={cfg['embed_model']} — run m4_index.py --force")
        emb_sub = np.load(wdir / "emb_sub.npy")
        emb_cap = np.load(wdir / "emb_cap.npy")
        n_seg = len(doc["segments"])
        if meta["n_segments"] != n_seg or emb_sub.shape[0] != n_seg or emb_cap.shape[0] != n_seg:
            # segments.json이 M4 이후 재생성되었는데 임베딩이 갱신 안 된 경우 방지
            raise ValueError(f"세그먼트 수 불일치: meta.n_segments={meta['n_segments']} "
                             f"segments.json={n_seg} emb_sub={emb_sub.shape[0]} "
                             f"emb_cap={emb_cap.shape[0]} — run m4_index.py --force")
        if static_threshold is None:
            static_mask = np.array([s["is_static"] for s in doc["segments"]])
        else:
            # segments.json은 읽기 전용 — 저장 필드(is_static)는 불변, 재계산은 메모리상에서만 [8-5(2)]
            static_mask = np.array([s["motion_score"] < static_threshold
                                    for s in doc["segments"]])
        return cls(segments=doc["segments"], emb_sub=emb_sub, emb_cap=emb_cap,
                   static_mask=static_mask)


def search_with_stats(query: str, video: VideoIndex, alpha: float,
                      cfg: dict) -> tuple[list[Result], dict]:
    """search와 동일 랭킹 + 정규화 이전 raw 코사인 통계 반환.
    무관련 질의 판정(향후 abstention 임계값 설계)의 근거 데이터용 [HIGH-2]."""
    q = embed_texts([query], cfg["embed_model"])[0]
    s_sub = video.emb_sub @ q                    # 1) 코사인 (L2 정규화 완료 상태)
    s_cap = video.emb_cap @ q
    score = combine_scores(s_sub, s_cap, video.static_mask, alpha)
    order = np.argsort(-score, kind="stable")
    results = [Result(int(i), float(score[i]),
                      video.segments[i]["start"], video.segments[i]["end"])
              for i in order]
    stats = {"raw_sub_max": float(s_sub.max()), "raw_sub_mean": float(s_sub.mean()),
             "raw_cap_max": float(s_cap.max()), "raw_cap_mean": float(s_cap.mean())}
    return results, stats


def search(query: str, video: VideoIndex, alpha: float, cfg: dict) -> list[Result]:
    return search_with_stats(query, video, alpha, cfg)[0]


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

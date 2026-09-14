"""M5 검색: 확정 연산 순서 — 코사인 → per-query z-score(단일 영상 범위; minmax에서
2026-07-13 개정) → 정적 s_cap_norm←s_sub_norm 치환 → α 가중합. baseline = α=1.0.
질의 확장(expand_query)은 config query_synonyms 사전이 있을 때만 활성(기본 off).
[DESIGN_SPEC 4-5]"""
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


def zscore(x: np.ndarray) -> np.ndarray:
    sd = x.std()
    return np.zeros_like(x) if sd < 1e-9 else (x - x.mean()) / sd


def combine_scores(s_sub: np.ndarray, s_cap: np.ndarray,
                   static_mask: np.ndarray, alpha: float) -> np.ndarray:
    # α 범위 검증 — CLI `--alpha`에는 검증이 없어 1.5·NaN도 그대로 흘러든다. 가중합이라
    # 예외 없이 "동작"하고 랭킹만 조용히 무의미해진다. 진입점마다 막지 않고 여기서 한 번
    # 막는다 — 모든 검색·평가 경로가 이 함수를 지난다 [감사 2026-08-26]
    if not (0.0 <= float(alpha) <= 1.0):   # NaN도 걸린다(모든 비교가 False)
        raise ValueError(f"alpha={alpha}는 [0, 1] 밖이다 — 융합 가중치 범위 위반")
    # 2) 채널별 z-score 정규화 (단일 영상 범위). minmax에서 개정(2026-07-13):
    #    per-query 극값이 유효 범위를 압축해 dev 96에서 유의 손실(-0.065 mrr, CI 0
    #    배제)을 만드는 것이 실측됨 — docs/probes/fusion_alternatives_probe.py.
    s_sub_n = zscore(s_sub)
    s_cap_n = zscore(s_cap)
    s_cap_n = s_cap_n.copy()
    s_cap_n[static_mask] = s_sub_n[static_mask]  # 3) 정규화 '이후' 치환 [v2 8-4]
    return alpha * s_sub_n + (1 - alpha) * s_cap_n  # 4) 가중합


def _check_caption_identity(cfg: dict, doc: dict, video_id: str) -> None:
    """인덱스의 캡션이 **지금 config가 주장하는 모델·프롬프트로 생성됐는지** 대조한다.

    `text_hash`는 "캡션과 임베딩이 같은 시점인가"만 본다 — 어느 모델이 그 캡션을
    썼는지는 보지 않는다. 4B로 만든 인덱스를 3B config로 열면 두 해시가 모두 맞으므로
    통과하고, 그 검색 결과가 "3B 배포"로 보고된다 [감사 2026-08-26].

    증거가 없는 인덱스는 통과시킨다 — `caption_provenance`는 2026-08-17 도입이라
    확정 인덱스 11편에는 없고, 채우려면 재색인이 필요하다. **있는 것은 반드시 본다.**
    """
    prov = doc.get("caption_provenance")
    if not prov:
        return
    want_model = cfg.get("caption_model")
    got_model = prov.get("config_caption_model") or prov.get("model_id")
    if want_model and got_model and want_model != got_model:
        raise ValueError(
            f"캡션 모델 불일치: index={got_model} config={want_model} "
            f"({video_id}) — 다른 모델이 만든 캡션이다")
    want_prompt = cfg.get("caption_prompt")
    got_prompt = prov.get("prompt_sha256")
    if want_prompt and got_prompt:
        import hashlib
        h = hashlib.sha256(want_prompt.encode("utf-8")).hexdigest()
        if h != got_prompt:
            raise ValueError(
                f"캡션 프롬프트 불일치: index={got_prompt[:12]} config={h[:12]} "
                f"({video_id}) — 다른 프롬프트로 만든 캡션이다")


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
        if static_threshold is None:
            # config가 단일 출처 — 저장된 is_static(M2 실행 당시 threshold 산물)에 의존하면
            # config의 static_threshold 변경이 평가에 반영되지 않는다 [8-5(2) 확장, 2026-07-11]
            static_threshold = cfg["static_threshold"]
        doc = common.load_segments(wdir / "segments.json",
                                   require=["subtitle", "caption", "motion_score"],
                                   seg_len=cfg["seg_len_sec"])
        for name in ("emb_sub.npy", "emb_cap.npy", "meta.json"):
            if not (wdir / name).exists():
                raise FileNotFoundError(f"{name} 없음 — run m4_index.py first")
        meta = json.loads((wdir / "meta.json").read_text(encoding="utf-8"))
        if meta["embed_model"] != cfg["embed_model"]:   # 모델 혼입 방지 [4-4]
            raise ValueError(f"임베딩 모델 불일치: index={meta['embed_model']} "
                             f"config={cfg['embed_model']} — run m4_index.py --force")
        # 재캡셔닝 후 임베딩 미갱신 감지 — 구버전 meta(해시 없음)는 하위호환 허용
        # [리뷰 2026-07-11 Major]
        if "text_hash" in meta and meta["text_hash"] != common.index_text_hash(doc):
            raise ValueError("segments.json 텍스트와 임베딩 불일치(재캡셔닝 후 미갱신) "
                             "— run m4_index.py --force")
        _check_caption_identity(cfg, doc, video_id)
        emb_sub = np.load(wdir / "emb_sub.npy")
        emb_cap = np.load(wdir / "emb_cap.npy")
        n_seg = len(doc["segments"])
        if meta["n_segments"] != n_seg or emb_sub.shape[0] != n_seg or emb_cap.shape[0] != n_seg:
            # segments.json이 M4 이후 재생성되었는데 임베딩이 갱신 안 된 경우 방지
            raise ValueError(f"세그먼트 수 불일치: meta.n_segments={meta['n_segments']} "
                             f"segments.json={n_seg} emb_sub={emb_sub.shape[0]} "
                             f"emb_cap={emb_cap.shape[0]} — run m4_index.py --force")
        # segments.json은 읽기 전용 — 저장 필드(is_static)는 M2 실행 기록으로 보존,
        # static_mask는 항상 메모리상 재판정 [8-5(2)]
        static_mask = np.array([s["motion_score"] < static_threshold
                                for s in doc["segments"]])
        return cls(segments=doc["segments"], emb_sub=emb_sub, emb_cap=emb_cap,
                   static_mask=static_mask)


def expand_query(query: str, cfg: dict) -> list[str]:
    """질의 확장: cfg['query_synonyms'](term→[동의어]) 사전으로 term 치환 변형을 덧붙인다.
    사전 미설정/미적중이면 [query] 단독 — 확장 off와 완전 동일(공식 경로 불변).
    근거·한계: 임베딩의 외래어-고유어 동의어 갭(cos(초밥,스시)=0.48<cos(초밥,김밥)=0.75),
    프로토타입 실측 초밥→스시 21→2위 — docs/probes/synonym_expansion_probe.py. 정식 채택은
    dev 검증→승인→test 재평가 절차 대상이라 기본 off로만 통합."""
    syn = cfg.get("query_synonyms") or {}
    variants = [query]
    for term, alts in syn.items():
        if term in query:
            for alt in alts:
                v = query.replace(term, alt)
                if v not in variants:
                    variants.append(v)
    return variants


def search_with_stats(query: str, video: VideoIndex, alpha: float,
                      cfg: dict, with_per_seg: bool = False) -> tuple[list[Result], dict]:
    """search와 동일 랭킹 + 정규화 이전 raw 코사인 통계 반환.
    무관련 질의 판정(향후 abstention 임계값 설계)의 근거 데이터용 [HIGH-2].

    with_per_seg=True면 세그먼트별 채널 점수를 stats["per_seg"]에 덧붙인다 —
    **표시 계층 전용**(웹 UI 타임라인 리본)이고 랭킹에 관여하지 않는다.
    기본값이 False인 이유: stats는 search_log.jsonl에 통째로 기록되므로
    세그먼트 수만큼의 배열이 기본으로 들어가면 로그가 폭증한다."""
    variants = expand_query(query, cfg)
    if len(variants) == 1:
        q = embed_texts([query], cfg["embed_model"])[0]
        s_sub = video.emb_sub @ q                # 1) 코사인 (L2 정규화 완료 상태)
        s_cap = video.emb_cap @ q
    else:
        # 변형 간 raw 코사인 max 풀링(정규화 이전 — 동일 임베딩 공간이라 스케일 호환).
        # 프로브에서 정규화 이후 풀링(21→10)보다 우세(21→2) 확인.
        qs = embed_texts(variants, cfg["embed_model"])
        s_sub = np.max(video.emb_sub @ qs.T, axis=1)
        s_cap = np.max(video.emb_cap @ qs.T, axis=1)
    score = combine_scores(s_sub, s_cap, video.static_mask, alpha)
    order = np.argsort(-score, kind="stable")
    results = [Result(int(i), float(score[i]),
                      video.segments[i]["start"], video.segments[i]["end"])
              for i in order]
    stats = {"raw_sub_max": float(s_sub.max()), "raw_sub_mean": float(s_sub.mean()),
             "raw_cap_max": float(s_cap.max()), "raw_cap_mean": float(s_cap.mean()),
             # zscore의 sd<1e-9 분기 발동 여부 — 발동 빈도 미기록 gap 보완 [2026-07-14]
             "sub_degenerate": bool(s_sub.std() < 1e-9),
             "cap_degenerate": bool(s_cap.std() < 1e-9)}
    if with_per_seg:
        stats["per_seg"] = {"sub": [float(x) for x in s_sub],
                            "cap": [float(x) for x in s_cap],
                            "fused": [float(x) for x in score]}
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

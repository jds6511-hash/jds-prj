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

    outputs = ("emb_sub.npy", "emb_cap.npy", "meta.json")
    if all((wdir / f).exists() for f in outputs) and not args.force:
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

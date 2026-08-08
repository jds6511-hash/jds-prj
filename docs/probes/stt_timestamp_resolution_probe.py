"""[자막 타임스탬프 해상도가 검색에 미치는 영향 — dev 전용, 채택 아님]

**왜 이걸 재나.** KconfSpeech CER 실측(2026-08-07)에서 Qwen3-ASR이 현행 Whisper를
유의하게 이겼다(ΔCER −0.028, 상대 −17.7%). 그런데 공개된 `Qwen3-ASR-1.7B-hf`는
**발화별 타임스탬프를 내지 않는다** — `config.json`에 `timestamp_token_id: 151705`가
있지만 그 id는 토크나이저에 없고(`convert_ids_to_tokens` → None, 실제 마지막 특수토큰은
151704 `<asr_text>`), `chat_template.jinja`에 timestamp 언급이 0건이며,
`apply_transcription_request` 시그니처와 `batch_decode`에도 관련 인자가 없다.

우리 파이프라인은 `assign_subtitles`가 발화의 `{t0,t1}`을 5초 세그먼트와 **겹침으로
귀속**시킨다. 타임스탬프가 없으면 오디오를 고정 길이로 잘라 **청크 시각**을 쓰는 수밖에
없고, 그러면 한 청크 안의 모든 세그먼트가 **같은 자막 문자열**을 갖는다.

**이 프로브는 그 손실만 분리해서 잰다.** ASR을 바꾸지 않는다 — **현행 Whisper 전사를
그대로 두고 귀속 해상도만** 청크 단위로 낮춘다. 그래야 "텍스트 품질"과 "시각 해상도"가
섞이지 않는다. 즉 여기서 나오는 하락은 **어떤 ASR을 쓰든 타임스탬프가 없으면 치르는
비용**의 하한이다(실제로는 CER 차이가 더해진다).

지표는 자막 채널 단독 α=1.0을 주로 본다(후보 검증 규약 (1) 채널 격리, DESIGN_SPEC 8-7).
융합 α=0.5도 병기한다. work/·results/ 불변, 재임베딩은 메모리에서만, test 미접촉.

재현: python docs/probes/stt_timestamp_resolution_probe.py
"""
import json, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                          # noqa: E402
from m3_generate import assign_subtitles               # noqa: E402
from m4_index import embed_texts                       # noqa: E402
from m5_search import VideoIndex                       # noqa: E402
from m6_evaluate import evaluate                       # noqa: E402

OUT = Path(__file__).resolve().parent / "_scratch"
CHUNKS = [5, 10, 30, 60]          # 초. 5는 세그먼트와 같아 손실 하한 확인용


def chunk_utts(utts: list[dict], chunk_sec: int, dur: float) -> list[dict]:
    """발화를 고정 길이 청크로 뭉친다 — 타임스탬프 없는 ASR이 낼 수 있는 최선.

    청크에 겹치는 발화의 텍스트를 순서대로 이어 붙이고, 시각은 **청크 경계**를 준다.
    실제 시스템이라면 청크 단위로 ASR을 돌리므로 텍스트는 조금 달라지겠지만,
    **시각 해상도 손실**은 이 시뮬레이션과 동일하다.
    """
    out = []
    t = 0.0
    while t < dur:
        end = min(t + chunk_sec, dur)
        txt = " ".join(u["text"] for u in utts
                       if min(u["t1"], end) - max(u["t0"], t) > 0)
        if txt.strip():
            out.append({"text": txt, "t0": t, "t1": end})
        t = end
    return out


def main():
    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})

    base = {v: VideoIndex.load(cfg, v) for v in vids}
    rep = {"note": "dev-only, 채택 아님. 현행 Whisper 전사를 유지하고 귀속 해상도만 낮춘다.",
           "why": ("Qwen3-ASR-1.7B-hf가 타임스탬프를 내지 않아 청크 시각을 쓸 수밖에 "
                   "없을 때의 비용 하한. ASR 텍스트 품질 차이는 포함하지 않는다."),
           "seed": cfg["seed"], "by_chunk": {}, "contrasts": {}}

    def subs_for(v, chunk_sec):
        wdir = Path(common.work_dir(cfg, v))
        cache = json.loads((wdir / "stt_cache.json").read_text(encoding="utf-8"))
        doc = json.loads((wdir / "segments.json").read_text(encoding="utf-8"))
        segs = [dict(s) for s in doc["segments"]]
        dur = max(s["end"] for s in segs)
        utts = (cache["utterances"] if chunk_sec is None
                else chunk_utts(cache["utterances"], chunk_sec, dur))
        assign_subtitles(utts, segs)
        return [s["subtitle"] for s in segs]

    vecs = {}
    for key in ["current"] + [f"chunk{c}s" for c in CHUNKS]:
        chunk_sec = None if key == "current" else int(key[5:-1])
        idx, distinct, nonblank, total = {}, 0, 0, 0
        for v in vids:
            texts = subs_for(v, chunk_sec)
            distinct += len({t for t in texts if t.strip()})
            nonblank += sum(1 for t in texts if t.strip())
            total += len(texts)
            idx[v] = VideoIndex(segments=base[v].segments,
                                emb_sub=embed_texts(texts, cfg["embed_model"]),
                                emb_cap=base[v].emb_cap,
                                static_mask=base[v].static_mask)
        blk = {"n_segments": total, "subtitled": nonblank, "distinct_subtitles": distinct}
        for alpha, name in ((1.0, "subtitle_only"), (0.5, "fused")):
            r = evaluate(dev, idx, alpha, cfg)
            blk[f"mrr_{name}"] = r["metrics"]["mrr"]
            vecs[(key, name)] = np.array([x["mrr"] for x in r["per_query"]])
        rep["by_chunk"][key] = blk
        print(f"[{key:9s}] 서로 다른 자막 {distinct:4d}/{nonblank:4d} | "
              f"자막단독 {blk['mrr_subtitle_only']:.4f} | 융합 {blk['mrr_fused']:.4f}",
              flush=True)

    n, B = len(dev), cfg["bootstrap_B"]
    ib = np.random.default_rng(cfg["seed"]).integers(0, n, size=(B, n))
    for c in CHUNKS:
        for name in ("subtitle_only", "fused"):
            b, k = vecs[("current", name)], vecs[(f"chunk{c}s", name)]
            d = k[ib].mean(1) - b[ib].mean(1)
            lo, hi = np.percentile(d, [2.5, 97.5])
            rep["contrasts"][f"chunk{c}s_vs_current/{name}"] = {
                "delta": round(float(k.mean() - b.mean()), 4),
                "ci95": [round(float(lo), 4), round(float(hi), 4)],
                "significant": bool(lo > 0 or hi < 0)}

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "stt_timestamp_resolution.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print("->", p)


if __name__ == "__main__":
    main()

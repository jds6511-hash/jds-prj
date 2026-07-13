"""[#3 캡션 후처리 (b)(c) dev MRR 델타 — 채택 아님, 켤 가치 판단용]
8-3 (b)미완결 절단 + (c)잔여 한자·가나 제거를 켰을 때 dev 성능이 오르는지만 측정한다.
캡션 재임베딩은 메모리에서만 수행(work/·results/ 미변경), config 불변, test 미접촉.
출력: scratchpad JSON. 재현: python docs/probes/caption_postproc_dev_delta.py
"""
import json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import common
from m5_search import VideoIndex
from m4_index import embed_texts
from m6_evaluate import evaluate


def rr_vec(res):
    return np.array([r["mrr"] for r in res["per_query"]])


def main():
    cfg = common.load_config("config.yaml")
    # 후처리 강제 on 한 cfg 사본
    cfg_pp = dict(cfg); cfg_pp["caption_truncate_incomplete"] = True; cfg_pp["caption_normalize_cjk"] = True
    alpha = 0.5

    qs = [json.loads(l) for l in
          Path("data/queries/queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})

    idx_cur, idx_pp = {}, {}
    changed, corrupt_before, corrupt_after = 0, 0, 0
    total_caps = 0
    for v in vids:
        vi = VideoIndex.load(cfg, v)
        idx_cur[v] = vi
        caps_pp = []
        for s in vi.segments:
            raw = s.get("caption") or ""
            total_caps += 1
            if common.is_corrupted_caption(raw):
                corrupt_before += 1
            clean, _ = common.postprocess_caption(raw, cfg_pp)
            if clean != raw:
                changed += 1
            if common.is_corrupted_caption(clean):
                corrupt_after += 1
            caps_pp.append(clean)
        emb_cap_pp = embed_texts(caps_pp, cfg["embed_model"])   # 재임베딩(메모리)
        idx_pp[v] = VideoIndex(segments=vi.segments, emb_sub=vi.emb_sub,
                               emb_cap=emb_cap_pp, static_mask=vi.static_mask)

    res_cur = evaluate(dev, idx_cur, alpha, cfg)
    res_pp = evaluate(dev, idx_pp, alpha, cfg)

    # paired bootstrap: pp - current (per-query mrr)
    b = rr_vec(res_cur); p = rr_vec(res_pp)
    n = len(dev); B = cfg["bootstrap_B"]
    rng = np.random.default_rng(cfg["seed"]); ib = rng.integers(0, n, size=(B, n))
    diffs = p[ib].mean(1) - b[ib].mean(1)
    ci = [round(float(x), 4) for x in np.percentile(diffs, [2.5, 97.5])]

    def bt(res):
        return {t: {"mrr": m["mrr"]} for t, m in res["metrics"]["by_type"].items()}

    out = {
        "note": "dev-only, 채택 아님. 재임베딩 메모리 한정(work/·results/ 불변).",
        "alpha": alpha,
        "caption_change_profile": {
            "total_captions": total_caps, "changed_by_postproc": changed,
            "changed_frac": round(changed / total_caps, 3),
            "corrupted_before": corrupt_before, "corrupted_after": corrupt_after},
        "dev_mrr": {"current": res_cur["metrics"]["mrr"], "postproc": res_pp["metrics"]["mrr"],
                    "delta": round(res_pp["metrics"]["mrr"] - res_cur["metrics"]["mrr"], 4),
                    "ci95_paired": ci, "significant": not (ci[0] <= 0 <= ci[1])},
        "by_type_current": bt(res_cur), "by_type_postproc": bt(res_pp),
    }
    dest = Path("C:/Users/UserK/AppData/Local/Temp/claude/"
                "c--Users-UserK-Desktop-prj/f443ead9-6036-4c8c-8abc-28dc150439d3/"
                "scratchpad/caption_postproc_delta.json")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written:", dest)
    print("change:", out["caption_change_profile"], "\ndev_mrr:", out["dev_mrr"])


if __name__ == "__main__":
    main()

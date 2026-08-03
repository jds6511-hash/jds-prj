"""[Qwen3-VL-4B-Instruct vs Qwen2.5-VL-3B-4bit 캡션 dev 비교 — 채택 아님, 실측용]
dev 3영상 기존 rep_frame으로 Qwen3-VL 캡션을 새로 생성해 (a) 오염률(is_corrupted_caption),
(b) dev MRR(재임베딩은 메모리에서만, work/·results/ 미변경)을 기존(Qwen2.5-VL-3B-4bit)과
비교한다. config 불변, test 미접촉. 출력: scratchpad JSON.
스모크 결과(docs/probes/qwen3vl_smoke.py) 양호 확인 후 진행 — varco_caption_probe.py와
동일 구조.
재현: python docs/probes/qwen3vl_caption_probe.py
"""
import json, sys
from pathlib import Path
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import common
from m5_search import VideoIndex
from m4_index import embed_texts
from m6_evaluate import evaluate

QWEN3VL_MODEL = "Qwen/Qwen3-VL-4B-Instruct"


def load_qwen3vl(cfg):
    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
    kwargs = dict(device_map={"": 0})
    if cfg.get("vlm_4bit"):
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
    else:
        kwargs["torch_dtype"] = torch.bfloat16
    model = Qwen3VLForConditionalGeneration.from_pretrained(QWEN3VL_MODEL, **kwargs)
    processor = AutoProcessor.from_pretrained(
        QWEN3VL_MODEL, min_pixels=256 * 28 * 28, max_pixels=cfg["vlm_max_pixels"])
    return model, processor


def caption_frame_qwen3vl(image_path, prompt, model, processor, max_new_tokens) -> str:
    from qwen_vl_utils import process_vision_info
    messages = [{"role": "user", "content": [
        {"type": "image", "image": str(image_path)},
        {"type": "text", "text": prompt}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    imgs, vids = process_vision_info(messages)
    inputs = processor(text=[text], images=imgs, videos=vids,
                       padding=True, return_tensors="pt").to(model.device)
    with torch.inference_mode():
        gen = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    out = processor.batch_decode(gen[:, inputs.input_ids.shape[1]:],
                                 skip_special_tokens=True)[0]
    return out.strip()


def rr_vec(res):
    return np.array([r["mrr"] for r in res["per_query"]])


def main():
    cfg = common.load_config("config.yaml")
    alpha = 0.5

    qs = [json.loads(l) for l in
          Path("data/queries/queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})

    print("Qwen3-VL-4B-Instruct 로딩 중...")
    model, processor = load_qwen3vl(cfg)
    print("로딩 완료, 캡션 생성 시작")

    idx_cur, idx_q3 = {}, {}
    corrupt_before, corrupt_after = 0, 0
    total_caps = 0
    samples = []
    for v in vids:
        vi = VideoIndex.load(cfg, v)
        idx_cur[v] = vi
        wdir = common.work_dir(cfg, v)
        caps_q3 = []
        for i, s in enumerate(vi.segments):
            old_cap = s.get("caption") or ""
            total_caps += 1
            if common.is_corrupted_caption(old_cap):
                corrupt_before += 1
            img_path = Path(wdir) / s["rep_frame"]
            new_cap = caption_frame_qwen3vl(img_path, cfg["caption_prompt"], model, processor,
                                            cfg["vlm_max_new_tokens"])
            if common.is_corrupted_caption(new_cap):
                corrupt_after += 1
            caps_q3.append(new_cap)
            if i < 3:
                samples.append({"video_id": v, "seg_idx": s["idx"],
                                "qwen25_caption": old_cap, "qwen3vl_caption": new_cap})
        emb_cap_q3 = embed_texts(caps_q3, cfg["embed_model"])
        idx_q3[v] = VideoIndex(segments=vi.segments, emb_sub=vi.emb_sub,
                               emb_cap=emb_cap_q3, static_mask=vi.static_mask)
        print(f"{v}: {len(caps_q3)}개 완료")

    res_cur = evaluate(dev, idx_cur, alpha, cfg)
    res_q3 = evaluate(dev, idx_q3, alpha, cfg)

    b = rr_vec(res_cur); p = rr_vec(res_q3)
    n = len(dev); B = cfg["bootstrap_B"]
    rng = np.random.default_rng(cfg["seed"]); ib = rng.integers(0, n, size=(B, n))
    diffs = p[ib].mean(1) - b[ib].mean(1)
    ci = [round(float(x), 4) for x in np.percentile(diffs, [2.5, 97.5])]

    def bt(res):
        return {t: {"mrr": m["mrr"]} for t, m in res["metrics"]["by_type"].items()}

    out = {
        "note": "dev-only, 채택 아님. 재임베딩 메모리 한정(work/·results/ 불변). test 미접촉.",
        "model": QWEN3VL_MODEL, "alpha": alpha,
        "corruption": {"total_captions": total_caps,
                       "corrupted_qwen25": corrupt_before, "corrupted_qwen3vl": corrupt_after,
                       "qwen25_rate": round(corrupt_before / total_caps, 4),
                       "qwen3vl_rate": round(corrupt_after / total_caps, 4)},
        "dev_mrr": {"qwen25_current": res_cur["metrics"]["mrr"], "qwen3vl": res_q3["metrics"]["mrr"],
                    "delta": round(res_q3["metrics"]["mrr"] - res_cur["metrics"]["mrr"], 4),
                    "ci95_paired": ci, "significant": not (ci[0] <= 0 <= ci[1])},
        "by_type_qwen25": bt(res_cur), "by_type_qwen3vl": bt(res_q3),
        "sample_captions": samples,
    }
    dest = Path(__file__).resolve().parent / "_scratch" / "qwen3vl_caption_probe.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written:", dest)
    print("corruption:", out["corruption"], "\ndev_mrr:", out["dev_mrr"])


if __name__ == "__main__":
    main()

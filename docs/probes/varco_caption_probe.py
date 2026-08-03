"""[VARCO-VISION-2.0-1.7B vs Qwen2.5-VL-3B-4bit 캡션 dev 비교 — 채택 아님, 실측용]
dev 3영상 기존 rep_frame으로 VARCO 캡션을 새로 생성해 (a) 오염률(is_corrupted_caption),
(b) dev MRR(재임베딩은 메모리에서만, work/·results/ 미변경)을 기존(Qwen2.5-VL-3B-4bit)과
비교한다. config 불변, test 미접촉. 출력: scratchpad JSON.
재현: python docs/probes/varco_caption_probe.py
"""
import json, sys
from pathlib import Path
import numpy as np
import torch
from PIL import Image
from transformers import AutoProcessor, LlavaOnevisionForConditionalGeneration

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import common
from m5_search import VideoIndex
from m4_index import embed_texts
from m6_evaluate import evaluate

VARCO_MODEL = "NCSOFT/VARCO-VISION-2.0-1.7B"


def load_varco():
    # device_map="auto"가 이 모델 구조를 잘못 프로파일링해 일부 파라미터(예: image_newline)를
    # meta device로 남기고 CPU 오프로드 — 비전 경로가 깨져 이미지와 무관한 동일 출력을
    # 내고 속도도 급락하는 것이 실측됨. 1.7B는 6GB에 통째로 올라가므로 명시적 단일 GPU 배치.
    model = LlavaOnevisionForConditionalGeneration.from_pretrained(
        VARCO_MODEL, torch_dtype=torch.float16, attn_implementation="sdpa",
        device_map={"": 0})
    processor = AutoProcessor.from_pretrained(VARCO_MODEL)
    return model, processor


def _resize_to_max_pixels(img: Image.Image, max_pixels: int) -> Image.Image:
    """Qwen 경로(vlm_max_pixels)와 동등 비교 위해 VARCO 입력도 동일 상한으로 캡.
    원본 rep_frame이 1920x1080이라 무캡 시 vision 토큰 폭증으로 세그먼트당
    수 분씩 걸리는 것이 실측됨(87개/4시간) — 리사이즈 없이는 655개 처리 불가."""
    w, h = img.size
    if w * h <= max_pixels:
        return img
    scale = (max_pixels / (w * h)) ** 0.5
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)


def caption_frame_varco(image_path, prompt, model, processor, max_pixels: int) -> str:
    img = Image.open(image_path).convert("RGB")
    img = _resize_to_max_pixels(img, max_pixels)
    conversation = [{"role": "user", "content": [
        {"type": "image", "image": img},
        {"type": "text", "text": prompt}]}]
    inputs = processor.apply_chat_template(
        conversation, add_generation_prompt=True, tokenize=True,
        return_dict=True, return_tensors="pt").to(model.device, torch.float16)
    with torch.inference_mode():
        gen = model.generate(**inputs, max_new_tokens=128, do_sample=False)
    out = processor.batch_decode(gen[:, inputs["input_ids"].shape[1]:],
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

    print("VARCO-VISION-2.0-1.7B 로딩 중...")
    model, processor = load_varco()
    print("로딩 완료, 캡션 생성 시작")

    idx_cur, idx_varco = {}, {}
    corrupt_before, corrupt_after = 0, 0
    total_caps = 0
    samples = []
    for v in vids:
        vi = VideoIndex.load(cfg, v)
        idx_cur[v] = vi
        wdir = common.work_dir(cfg, v)
        caps_varco = []
        for i, s in enumerate(vi.segments):
            old_cap = s.get("caption") or ""
            total_caps += 1
            if common.is_corrupted_caption(old_cap):
                corrupt_before += 1
            img_path = Path(wdir) / s["rep_frame"]
            new_cap = caption_frame_varco(img_path, cfg["caption_prompt"], model, processor,
                                          cfg["vlm_max_pixels"])
            if common.is_corrupted_caption(new_cap):
                corrupt_after += 1
            caps_varco.append(new_cap)
            if i < 3:
                samples.append({"video_id": v, "seg_idx": s["idx"],
                                "qwen_caption": old_cap, "varco_caption": new_cap})
        emb_cap_varco = embed_texts(caps_varco, cfg["embed_model"])
        idx_varco[v] = VideoIndex(segments=vi.segments, emb_sub=vi.emb_sub,
                                  emb_cap=emb_cap_varco, static_mask=vi.static_mask)
        print(f"{v}: {len(caps_varco)}개 완료")

    res_cur = evaluate(dev, idx_cur, alpha, cfg)
    res_varco = evaluate(dev, idx_varco, alpha, cfg)

    b = rr_vec(res_cur); p = rr_vec(res_varco)
    n = len(dev); B = cfg["bootstrap_B"]
    rng = np.random.default_rng(cfg["seed"]); ib = rng.integers(0, n, size=(B, n))
    diffs = p[ib].mean(1) - b[ib].mean(1)
    ci = [round(float(x), 4) for x in np.percentile(diffs, [2.5, 97.5])]

    def bt(res):
        return {t: {"mrr": m["mrr"]} for t, m in res["metrics"]["by_type"].items()}

    out = {
        "note": "dev-only, 채택 아님. 재임베딩 메모리 한정(work/·results/ 불변). test 미접촉.",
        "model": VARCO_MODEL, "alpha": alpha,
        "corruption": {"total_captions": total_caps,
                       "corrupted_qwen": corrupt_before, "corrupted_varco": corrupt_after,
                       "qwen_rate": round(corrupt_before / total_caps, 4),
                       "varco_rate": round(corrupt_after / total_caps, 4)},
        "dev_mrr": {"qwen_current": res_cur["metrics"]["mrr"], "varco": res_varco["metrics"]["mrr"],
                    "delta": round(res_varco["metrics"]["mrr"] - res_cur["metrics"]["mrr"], 4),
                    "ci95_paired": ci, "significant": not (ci[0] <= 0 <= ci[1])},
        "by_type_qwen": bt(res_cur), "by_type_varco": bt(res_varco),
        "sample_captions": samples,
    }
    dest = Path(__file__).resolve().parent / "_scratch" / "varco_caption_probe.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written:", dest)
    print("corruption:", out["corruption"], "\ndev_mrr:", out["dev_mrr"])


if __name__ == "__main__":
    main()

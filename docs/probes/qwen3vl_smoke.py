"""[Qwen3-VL-4B-Instruct 스모크 — 채택 검토 전 1차 확인, dev-only]
기존 VARCO/Qwen2.5 스모크와 동일 세그먼트(Wilderness seg0/1/2, kheritage seg0)로
캡션·속도·VRAM만 우선 확인. config 불변, work/·results/ 미변경, test 미접촉.
전체 dev 비교(재임베딩+MRR)는 이 스모크 결과 보고 나서 별도 스크립트로 진행.
재현: python docs/probes/qwen3vl_smoke.py
"""
import time
from pathlib import Path

import torch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import common

MODEL = "Qwen/Qwen3-VL-4B-Instruct"
TARGETS = [
    ("_10_000_Every_Day_You_Survive_In_The_Wilderness", 0),
    ("_10_000_Every_Day_You_Survive_In_The_Wilderness", 1),
    ("_10_000_Every_Day_You_Survive_In_The_Wilderness", 2),
    ("kheritage_grave_excavation", 0),
]


def load_qwen3vl(cfg):
    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
    kwargs = dict(device_map={"": 0})
    if cfg.get("vlm_4bit"):
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
    else:
        kwargs["torch_dtype"] = torch.bfloat16
    model = Qwen3VLForConditionalGeneration.from_pretrained(MODEL, **kwargs)
    processor = AutoProcessor.from_pretrained(
        MODEL, min_pixels=256 * 28 * 28, max_pixels=cfg["vlm_max_pixels"])
    return model, processor


def caption_frame_qwen3vl(image_path, prompt, model, processor, max_new_tokens):
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


def main():
    cfg = common.load_config("config.yaml")

    t0 = time.time()
    print("Qwen3-VL-4B-Instruct 로딩 중...")
    model, processor = load_qwen3vl(cfg)
    print(f"로딩 {time.time() - t0:.1f}초")
    print(f"VRAM 할당 {torch.cuda.memory_allocated() / 1e9:.2f}GB / "
          f"예약 {torch.cuda.memory_reserved() / 1e9:.2f}GB")

    for video_id, seg_idx in TARGETS:
        wdir = common.work_dir(cfg, video_id)
        doc = common.load_segments(wdir / "segments.json", require=["rep_frame"],
                                   seg_len=cfg["seg_len_sec"])
        seg = next(s for s in doc["segments"] if s["idx"] == seg_idx)
        img_path = Path(wdir) / seg["rep_frame"]
        t1 = time.time()
        cap = caption_frame_qwen3vl(img_path, cfg["caption_prompt"], model, processor,
                                    cfg["vlm_max_new_tokens"])
        dt = time.time() - t1
        print(f"{video_id} seg {seg_idx}: {dt:.1f}초 | {cap}")
        print(f"  (기존 Qwen2.5 캡션: {seg.get('caption', '')})")


if __name__ == "__main__":
    main()

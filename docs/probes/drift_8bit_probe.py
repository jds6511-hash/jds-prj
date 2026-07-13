# 캡션 중국어 드리프트의 양자화 가설 검증 — 4bit(NF4)에서 greedy 오염이 확정된
# 프레임 21장을 8bit로 재추론해 드리프트 재현율을 비교한다.
# 4bit greedy 오염율은 구성상 21/21 (이 프레임들은 4bit greedy 출력이 오염 판정돼
# 재캡셔닝 대상이 된 이력 — DESIGN_SPEC 8-5(4)). 8bit에서 유의하게 낮으면
# "저비트 양자화가 언어 일관성을 깬다" 가설이 실측으로 지지된다.
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, "src")
import common
from m3_generate import caption_frame

# 4bit greedy 오염 확정 프레임 (재캡셔닝 이력 target 목록)
TARGETS = {
    "_10_000_Every_Day_You_Survive_In_The_Wilderness": [2, 31, 121, 160, 177],
    "kheritage_grave_excavation": [22, 93, 110, 136, 173, 174, 175, 176],
    "gwaktube_soviet_apartment": [37],
    "panibottle_vietnam1": [112, 173],
    "gemini_promo": [67],
    "yunnamnopo_tongyeong": [22, 175],
    "pland_costco_hosting": [125, 234],
}

cfg = common.load_config("config.yaml")

def load_vlm_8bit(cfg):
    import torch
    from transformers import (Qwen2_5_VLForConditionalGeneration, AutoProcessor,
                              BitsAndBytesConfig)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        cfg["caption_model"], device_map="auto",
        quantization_config=BitsAndBytesConfig(load_in_8bit=True))
    processor = AutoProcessor.from_pretrained(
        cfg["caption_model"], min_pixels=256 * 28 * 28, max_pixels=cfg["vlm_max_pixels"])
    return model, processor

model, processor = load_vlm_8bit(cfg)
total = drift = 0
for vid, idxs in TARGETS.items():
    wdir = common.work_dir(cfg, vid)
    doc = json.load(open(wdir / "segments.json", encoding="utf-8"))
    for i in idxs:
        frame = wdir / doc["segments"][i]["rep_frame"]
        cap = caption_frame(str(frame), cfg["caption_prompt"], model, processor, cfg)
        bad = common.is_corrupted_caption(cap)
        total += 1
        drift += bad
        print(f"{'DRIFT' if bad else 'clean'} | {vid[:20]:20s} seg{i:4d} | {cap[:46]}")

print(f"\n8bit greedy 오염: {drift}/{total} ({drift/total:.0%})  |  4bit greedy 오염(이력): {total}/{total} (100%)")

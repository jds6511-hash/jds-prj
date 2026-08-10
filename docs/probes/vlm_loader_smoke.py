"""[신규 VLM 로더 스모크 테스트 — 본 배치 전에 API를 실증한다]

**왜 필요한가.** kanana를 벽 5개 끝에 제외했다(로더 클래스 → einops/timm →
flash-attn 강제 → 벤더 fallback 파손 → chat template 없음 → 결국 빈 캡션).
그 과정을 본 배치 안에서 겪으면 GPU 시간을 통째로 날린다. **새 계열 모델은
2프레임으로 먼저 확인하고, 통과한 것만 본 배치에 넣는다.**

**전략을 추측하지 않고 순서대로 시도해 실증한다.**
  S1  AutoModelForImageTextToText + AutoProcessor + apply_chat_template  (표준 경로)
  S2  AutoModel(trust_remote_code) + model.chat()                        (MiniCPM 계열)
  S3  AutoModel(trust_remote_code) + apply_chat_template                 (벤더 혼합형)

먼저 성공한 전략을 기록하고, 그걸 스윕 로더에 옮긴다.

**빈 캡션과 이미지 무시를 둘 다 잡는다.** kanana는 "적재 성공"이었지만 빈 문자열을
냈다. 그리고 이미지를 무시하고 텍스트만 보고 답하는 모델은 캡션이 그럴듯해도
검색에 쓸모가 없다. 그래서 **서로 다른 두 프레임**을 주고 출력이 달라지는지 본다
(`vision_sanity`) — 스윕의 동일 검사와 같은 원칙이다.

**통과 기준 (실행 전 확정).**
  - 두 프레임 모두 **비어 있지 않은** 한국어 출력
  - 두 출력이 **서로 다름**(vision_sanity) — 같으면 이미지를 안 보는 것이다
  - 위 둘을 만족해야 본 배치 후보. 실패는 사유와 함께 기록하고 **제외**한다.

VRAM·프레임당 시간도 같이 재서 본 배치 소요를 추정한다. 생성 시간은 모델 크기가
아니라 **출력 길이**가 지배한다(실측: 7B/P1 17.0분 < 4B/P1 27.4분).

work/·results/ 불변, test 미접촉. 캡션 미저장.
재현: python docs/probes/vlm_loader_smoke.py [--models a,b,c]
"""
import argparse
import io
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
TARGETS = {
    "qwen3vl_8b":          "Qwen/Qwen3-VL-8B-Instruct",
    "minicpm_v45":         "openbmb/MiniCPM-V-4_5",
    "hyperclovax_omni_8b": "naver-hyperclovax/HyperCLOVAX-SEED-Omni-8B",
    "hyperclovax_3b":      "naver-hyperclovax/HyperCLOVAX-SEED-Vision-Instruct-3B",
    "glm41v_9b":           "THUDM/GLM-4.1V-9B-Thinking",
}


def pick_two_frames(cfg):
    """서로 확실히 다른 두 프레임 — 다른 영상에서 하나씩 고른다."""
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    vids = sorted({q["video_id"] for q in qs if q["split"] == "dev"})[:2]
    out = []
    for v in vids:
        wdir = Path(common.work_dir(cfg, v))
        segs = json.loads((wdir / "segments.json").read_text(encoding="utf-8"))
        segs = segs["segments"] if isinstance(segs, dict) else segs
        out.append(wdir / segs[len(segs) // 2]["rep_frame"])
    return out


def try_s1(mid, cfg, frames, prompt):
    """표준 경로 — AutoModelForImageTextToText."""
    import torch
    from PIL import Image
    from transformers import AutoModelForImageTextToText, AutoProcessor
    model = AutoModelForImageTextToText.from_pretrained(
        mid, dtype=torch.bfloat16, device_map={"": 0}, trust_remote_code=True).eval()
    proc = AutoProcessor.from_pretrained(mid, trust_remote_code=True)
    outs = []
    for f in frames:
        msgs = [{"role": "user", "content": [
            {"type": "image"}, {"type": "text", "text": prompt}]}]
        text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inp = proc(text=[text], images=[Image.open(f).convert("RGB")],
                   return_tensors="pt").to(model.device)
        with torch.inference_mode():
            g = model.generate(**inp, max_new_tokens=96, do_sample=False)
        outs.append(proc.batch_decode(g[:, inp["input_ids"].shape[1]:],
                                      skip_special_tokens=True)[0].strip())
    return model, outs


def try_s2(mid, cfg, frames, prompt):
    """MiniCPM 계열 — 벤더 model.chat()."""
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoTokenizer
    model = AutoModel.from_pretrained(mid, trust_remote_code=True,
                                      dtype=torch.bfloat16).eval().cuda()
    tok = AutoTokenizer.from_pretrained(mid, trust_remote_code=True)
    outs = []
    for f in frames:
        img = Image.open(f).convert("RGB")
        r = model.chat(image=img, msgs=[{"role": "user", "content": [img, prompt]}],
                       tokenizer=tok, sampling=False)
        outs.append((r if isinstance(r, str) else str(r)).strip())
    return model, outs


def try_s3(mid, cfg, frames, prompt):
    """벤더 혼합형 — AutoModel + chat template."""
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoProcessor
    model = AutoModel.from_pretrained(mid, dtype=torch.bfloat16, device_map={"": 0},
                                      trust_remote_code=True).eval()
    proc = AutoProcessor.from_pretrained(mid, trust_remote_code=True)
    outs = []
    for f in frames:
        msgs = [{"role": "user", "content": [
            {"type": "image"}, {"type": "text", "text": prompt}]}]
        text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inp = proc(text=[text], images=[Image.open(f).convert("RGB")],
                   return_tensors="pt").to(model.device)
        with torch.inference_mode():
            g = model.generate(**inp, max_new_tokens=96, do_sample=False)
        outs.append(proc.batch_decode(g[:, inp["input_ids"].shape[1]:],
                                      skip_special_tokens=True)[0].strip())
    return model, outs


STRATEGIES = [("S1_ImageTextToText", try_s1), ("S2_vendor_chat", try_s2),
              ("S3_AutoModel_template", try_s3)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(TARGETS))
    ap.add_argument("--config", default="config.yaml")
    a = ap.parse_args()

    import torch
    cfg = common.load_config(str(ROOT / a.config))
    frames = pick_two_frames(cfg)
    prompt = cfg["caption_prompt"]
    print(f"프레임 2장: {[f.name for f in frames]}", flush=True)

    rep = {"note": "신규 VLM 로더 실증. 본 배치 전 관문. test 미접촉.",
           "prereg": {"pass": "두 프레임 모두 비어있지 않고 서로 다를 것(vision_sanity)",
                      "declared_before_run": True},
           "frames": [str(f) for f in frames], "models": {}}

    for key in [m.strip() for m in a.models.split(",") if m.strip()]:
        mid = TARGETS[key]
        print(f"\n=== {key} ({mid}) ===", flush=True)
        blk = {"id": mid, "attempts": []}
        for sname, fn in STRATEGIES:
            model = None
            try:
                torch.cuda.reset_peak_memory_stats()
                t0 = time.time()
                model, outs = fn(mid, cfg, frames, prompt)
                el = time.time() - t0
                nonempty = all(bool(o) for o in outs)
                differ = outs[0] != outs[1]
                ok = nonempty and differ
                blk["attempts"].append({
                    "strategy": sname, "ok": ok, "nonempty": nonempty,
                    "vision_sanity": differ,
                    "vram_peak_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
                    "sec_per_frame": round(el / len(frames), 2),
                    "samples": [o[:90] for o in outs]})
                print(f"  [{sname}] 비어있지않음={nonempty} 이미지반영={differ} "
                      f"VRAM={blk['attempts'][-1]['vram_peak_gb']}GB "
                      f"{blk['attempts'][-1]['sec_per_frame']}초/장", flush=True)
                if ok:
                    blk["winner"] = sname
                    blk["sec_per_frame"] = blk["attempts"][-1]["sec_per_frame"]
                    blk["vram_peak_gb"] = blk["attempts"][-1]["vram_peak_gb"]
                    break
            except Exception as e:
                blk["attempts"].append({
                    "strategy": sname, "ok": False,
                    "error": f"{type(e).__name__}: {str(e)[:300]}",
                    "tb_tail": traceback.format_exc().strip().splitlines()[-1][:200]})
                print(f"  [{sname}] 실패 — {type(e).__name__}: {str(e)[:160]}", flush=True)
            finally:
                if model is not None:
                    del model
                torch.cuda.empty_cache()
        blk["passed"] = "winner" in blk
        rep["models"][key] = blk
        print(f"  -> {key}: {'통과 (' + blk['winner'] + ')' if blk['passed'] else '제외'}",
              flush=True)

    ok = [k for k, v in rep["models"].items() if v["passed"]]
    rep["passed_models"] = ok
    rep["excluded_models"] = [k for k in rep["models"] if k not in ok]
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "vlm_loader_smoke.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"통과 {len(ok)}/{len(rep['models'])}: {ok}")
    if rep["excluded_models"]:
        print(f"제외: {rep['excluded_models']}")
    print("->", p)


if __name__ == "__main__":
    main()

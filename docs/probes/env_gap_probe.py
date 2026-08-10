"""[생성 환경 격차 1단계 — 입력이 같은가 (GPU 불필요, 결과 전 커밋)]

**무엇을 푸는가.** 같은 모델·4bit·프롬프트·그리디인데 노트북(RTX 3060) 생성분과
서버(RTX 4090) 생성분의 캡션 완전일치가 25.6%뿐이고, 서버 생성분의 dev 캡션단독
MRR이 0.09 낮다. 서버에서 **따로 두 번** 생성했는데 둘 다 낮았다
(2026-08-07 Δ−0.0879 CI [−0.158, −0.023] / 2026-08-10 Δ−0.0926 CI [−0.1608, −0.0252]).
이 0.09가 후보 모델의 이득 +0.0913을 통째로 상쇄한다(`deploy_delta.py`).

**출발점: 그리디는 결정적이어야 한다.** `do_sample=False`면 같은 입력·같은 가중치에
대해 항상 같은 출력이 나와야 한다. 그렇지 않다는 것은 둘 중 하나다.

  (가) **입력이 다르다** — 프레임 파일 자체, 또는 전처리 결과 텐서
  (나) **수치 연산이 다르다** — 커널·리덕션 순서·아키텍처

**이 스크립트는 (가)만 판정한다.** 전처리는 전부 CPU에서 돌아가므로 GPU가 필요
없고, 여기서 갈리면 (나)를 볼 필요도 없이 원인이 확정된다. 지금까지 아무도 이
단계를 보지 않았다 — 계속 (나)만 의심하고 있었다.

`m3_generate.caption_frame`과 **똑같은 경로**를 쓴다(`process_vision_info` →
`processor`). 재현용으로 따로 만든 경로면 그 경로의 차이를 재게 되므로 의미가 없다.

**무엇을 해시하는가.**
  1. `frame_sha`      프레임 JPEG 파일 자체 — 다르면 M2 산출물부터 다르다
  2. `input_ids`      텍스트 토큰화 — 토크나이저 버전 차이
  3. `grid_thw`       리사이즈 목표 격자. `max_pixels`에서 패치 배수로 반올림한
                      결과라 transformers 버전이 바뀌면 여기서 갈린다
  4. `pixel_values`   전처리된 픽셀 텐서. **1비트라도 다르면 그 뒤는 전부 다르다.**
                      PIL 버전·리샘플링 필터·디코더가 바뀌면 갈린다

**사전 등록한 판정 규칙 (결과 보기 전 확정, 2026-08-10).**
  - `frame_sha` 불일치가 하나라도 있으면 → **원인 확정: M2 산출물이 다르다.**
    2·3·4는 보지 않는다(입력이 다르니 당연히 다르다).
  - 프레임은 같은데 `pixel_values`가 **10% 이상** 불일치 → **원인 확정: 전처리.**
    `grid_thw`가 같이 갈리면 반올림, 안 갈리면 디코드·리샘플링이다.
  - `pixel_values`가 **전부 일치** → (가) 배제. 2단계(로짓 분기점)로 넘어간다.
  - 그 사이(0 초과 10% 미만)면 **혼재**로 보고하고 갈린 항목의 격자·용량을 병기한다.
  - 결과를 보고 임계값을 바꾸지 않는다.

**두 결과 모두 쓸모가 있다.** 고칠 수 있는 원인이면 맞춰서 재생성하면 후보 모델의
+0.09가 실현된다. 고칠 수 없는 환경 자체가 원인이면, 노트북 생성분이 높은 것이
품질이 아니라 뽑기이므로 올바른 비교는 서버 대 서버가 되고 채택이 정당화된다.

**환경 정보도 같이 남긴다** — 3단계에서 어느 요인을 바꿀지가 여기서 정해진다.

work/·results/ 불변, test 미접촉. GPU 불필요.
재현:
  (양쪽에서) python docs/probes/env_gap_probe.py --stage hash --out env_<곳>.json
  (한쪽에서) python docs/probes/env_gap_probe.py --compare env_A.json env_B.json
"""
import argparse
import hashlib
import io
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
N_FRAMES = 200
PIXEL_MISMATCH_GATE = 0.10
# 프롬프트는 config의 caption_prompt를 그대로 쓴다. 전처리 해시에 텍스트도 들어가므로
# 실제 생성에 쓴 것과 한 글자라도 다르면 비교가 무의미해진다(하드코딩 금지).


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def env_info():
    import numpy
    import PIL
    import torch
    import transformers
    info = {"python": platform.python_version(), "platform": platform.platform(),
            "torch": torch.__version__, "transformers": transformers.__version__,
            "numpy": numpy.__version__, "pillow": PIL.__version__}
    for mod in ("torchvision", "qwen_vl_utils", "bitsandbytes", "accelerate"):
        try:
            info[mod] = __import__(mod).__version__
        except Exception as e:                      # 없거나 __version__이 없을 수 있다
            info[mod] = f"<{type(e).__name__}>"
    try:
        info["cuda"] = torch.version.cuda
        info["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:
        info["cuda"], info["gpu"] = None, None
    return info


def pick_frames(cfg):
    """dev 3편에서 앞쪽 세그먼트를 결정적으로 고른다(무작위 없음 — 양쪽이 같아야 한다)."""
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    vids = sorted({q["video_id"] for q in qs if q["split"] == "dev"})
    per = max(1, N_FRAMES // len(vids))
    picked = []
    for v in vids:
        wdir = Path(common.work_dir(cfg, v))
        segs = json.loads((wdir / "segments.json").read_text(encoding="utf-8"))
        segs = segs["segments"] if isinstance(segs, dict) else segs
        for s in segs[:per]:
            picked.append((v, s["rep_frame"], wdir / s["rep_frame"]))
    return picked


def stage_hash(out_path: Path):
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor

    cfg = common.load_config(str(ROOT / "config.yaml"))
    prompt = cfg["caption_prompt"]
    proc = AutoProcessor.from_pretrained(
        cfg["caption_model"], min_pixels=256 * 28 * 28, max_pixels=cfg["vlm_max_pixels"])

    rows = {}
    frames = pick_frames(cfg)
    print(f"프레임 {len(frames)}장, 전처리 해시 중 (GPU 미사용)", flush=True)
    for i, (vid, rel, path) in enumerate(frames):
        key = f"{vid}/{rel}"
        if not path.exists():
            rows[key] = {"error": "프레임 없음"}
            continue
        msgs = [{"role": "user", "content": [
            {"type": "image", "image": str(path)}, {"type": "text", "text": prompt}]}]
        text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        imgs, vids_ = process_vision_info(msgs)
        inp = proc(text=[text], images=imgs, videos=vids_, padding=True, return_tensors="pt")
        pv = inp["pixel_values"]
        rows[key] = {
            "frame_sha": sha(path.read_bytes()),
            "input_ids": sha(inp["input_ids"].numpy().tobytes()),
            "grid_thw": [int(x) for x in inp["image_grid_thw"][0].tolist()],
            "pixel_values": sha(pv.numpy().tobytes()),
            "pixel_shape": list(pv.shape),
            "pixel_dtype": str(pv.dtype),
        }
        if i % 50 == 0:
            print(f"  {i}/{len(frames)}", flush=True)

    rep = {"note": "생성 환경 격차 1단계 — 입력 동일성. dev only, test 미접촉.",
           "prompt": prompt, "n_frames": len(frames),
           "vlm_max_pixels": cfg["vlm_max_pixels"], "caption_model": cfg["caption_model"],
           "env": env_info(), "frames": rows}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {out_path}")


def stage_compare(pa: Path, pb: Path):
    A = json.loads(pa.read_text(encoding="utf-8"))
    B = json.loads(pb.read_text(encoding="utf-8"))
    if A["prompt"] != B["prompt"] or A["vlm_max_pixels"] != B["vlm_max_pixels"]:
        raise ValueError("프롬프트·max_pixels가 다르다 — 비교 불가")

    keys = sorted(set(A["frames"]) & set(B["frames"]))
    only = sorted(set(A["frames"]) ^ set(B["frames"]))
    fields = ["frame_sha", "input_ids", "grid_thw", "pixel_values"]
    mism = {f: [] for f in fields}
    usable = 0
    for k in keys:
        a, b = A["frames"][k], B["frames"][k]
        if "error" in a or "error" in b:
            continue
        usable += 1
        for f in fields:
            if a[f] != b[f]:
                mism[f].append(k)

    rate = {f: (len(v) / usable if usable else None) for f, v in mism.items()}
    rep = {"note": "1단계 비교 — 입력이 같은가", "n_compared": usable,
           "n_only_one_side": len(only),
           "env_a": A["env"], "env_b": B["env"],
           "mismatch_count": {f: len(v) for f, v in mism.items()},
           "mismatch_rate": {f: (round(r, 4) if r is not None else None)
                             for f, r in rate.items()},
           "examples": {f: v[:5] for f, v in mism.items() if v}}

    if rate["frame_sha"]:
        rep["verdict"] = ("원인 확정 — 프레임 파일부터 다르다. M2 산출물이 서로 다른 "
                          "것이므로 캡션 비교 자체가 성립하지 않았다")
    elif rate["pixel_values"] >= PIXEL_MISMATCH_GATE:
        why = "격자 반올림" if rate["grid_thw"] else "이미지 디코드·리샘플링"
        rep["verdict"] = (f"원인 확정 — 전처리가 다르다({why}). "
                          f"pixel_values 불일치 {rate['pixel_values']:.1%}")
    elif rate["pixel_values"] == 0:
        rep["verdict"] = ("입력은 완전히 동일 — (가) 배제. 원인은 수치 연산 쪽이다. "
                          "2단계(로짓 분기점)로 넘어간다")
    else:
        rep["verdict"] = (f"혼재 — pixel_values 불일치 {rate['pixel_values']:.1%}"
                          f"(임계 {PIXEL_MISMATCH_GATE:.0%} 미만)")

    p = OUT / "env_gap_stage1.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"비교 {usable}장 (한쪽에만 있는 것 {len(only)})")
    for f in fields:
        print(f"  {f:14s} 불일치 {len(mism[f]):4d}  ({rate[f]:.1%})")
    print()
    for k in ("torch", "transformers", "pillow", "torchvision", "qwen_vl_utils", "gpu"):
        if A["env"].get(k) != B["env"].get(k):
            print(f"  환경 차이 {k}: {A['env'].get(k)}  vs  {B['env'].get(k)}")
    print()
    print("판정:", rep["verdict"])
    print("->", p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["hash"])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--compare", nargs=2, type=Path)
    a = ap.parse_args()
    if a.compare:
        stage_compare(*a.compare)
    elif a.stage == "hash":
        stage_hash(a.out or (OUT / "env_hash.json"))
    else:
        ap.error("--stage hash 또는 --compare 중 하나가 필요하다")


if __name__ == "__main__":
    main()

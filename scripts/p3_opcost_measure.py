"""`p3_opcost_v1` 실측 — 배포 정밀도에서 3B와 4B의 **생성 비용만** 잰다.

동결된 프로토콜(`docs/P3_운영비_2026-08-24.json`의 `measurement_protocol`)을 그대로
실행한다. 검색 성능은 재지 않고, 인덱스에 아무것도 쓰지 않으며, **캡션 문자열을
저장하지 않는다**(길이·토큰 수만). 내용을 남기면 GT·프롬프트 조정 통로가 열린다.

```
같게 두는 것   기기 · 프레임 목록(동결) · max_pixels · max_new_tokens · rep_penalty ·
              프롬프트(P0) · 정밀도(양 arm 4bit) · 코드 경로(m3_generate)
다른 것        caption_model 하나뿐
배치           arm 블록을 교대로 돈다 (웜업 편향 제거)
재는 것        로드 시간 · 로드 후 VRAM · peak VRAM · 프레임당 시간 · 실패/OOM ·
              모델 저장 바이트 · 출력 길이/토큰 수
안 재는 것     retrieval 성능 · 캡션 품질 · MRR·RR·순위 · GT 관련 어떤 것도
```

재현:
  python scripts/p3_opcost_measure.py freeze --n 40
  python scripts/p3_opcost_measure.py run --stage canary
  python scripts/p3_opcost_measure.py run --stage full
"""
import argparse
import datetime
import gc
import hashlib
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROTOCOL = "p3_opcost_v1"
SEED = 20260824
FRAMES_FILE = ROOT / "docs" / "probes" / "_scratch" / "p3_opcost_frames.json"
OUT_DIR = ROOT / "docs" / "probes" / "_scratch"
STAGES = ("canary", "full")

ARM_MODEL = {"3b": "Qwen/Qwen2.5-VL-3B-Instruct",
             "4b": "Qwen/Qwen3-VL-4B-Instruct"}
ARM_ORDER = ("3b", "4b")

PROVENANCE_FIELDS = ("model_id", "model_revision", "dtype_effective",
                     "quantized_effective", "attn_implementation",
                     "vlm_max_pixels", "vlm_max_new_tokens",
                     "vlm_rep_penalty", "prompt_sha256", "torch",
                     "transformers", "python", "gpu", "vram_total_gb",
                     "vram_free_at_start_gb", "commit")
COST_FIELDS = ("load_sec_median", "load_sec_all", "vram_after_load_gb",
               "vram_peak_gb", "vram_peak_reserved_gb", "vram_min_free_gb",
               "headroom_min_gb", "sec_per_frame_median", "sec_per_frame_mean",
               "sec_per_frame_all", "n_frames", "n_frames_attempted",
               "n_failures", "oom", "model_storage_bytes", "out_chars_mean",
               "out_tokens_mean")

LOAD_REPEATS = 3
GB = 1024 ** 3


class MeasureError(RuntimeError):
    pass


def _git(*args) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                           text=True)
        return r.stdout.strip()
    except Exception:
        return ""


def _cfg() -> dict:
    import yaml
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def arm_config(arm: str) -> dict:
    """배포 config에서 **caption_model 하나만** 바꾼다. 양 arm 4bit."""
    if arm not in ARM_MODEL:
        raise MeasureError(f"알 수 없는 arm {arm!r} — {list(ARM_MODEL)}만 쓴다")
    cfg = _cfg()
    cfg["caption_model"] = ARM_MODEL[arm]
    cfg["vlm_4bit"] = True
    return cfg


def block_order(blocks: int = 2) -> list:
    """arm 블록 교대 순서. 웜업·써멀 편향이 한쪽에 쏠리지 않게 한다."""
    if blocks < 1:
        raise MeasureError("blocks는 1 이상이어야 한다")
    return [a for _ in range(blocks) for a in ARM_ORDER]


def select_frames(n: int, seed: int = SEED) -> list:
    """프레임을 결정적으로 고른다. **파일 경로만 본다** — 내용 신호를 쓰지 않는다."""
    paths = sorted(str(p.relative_to(ROOT)).replace("\\", "/")
                   for p in ROOT.glob("work/*/frames/seg_*.jpg"))
    if not paths:
        raise MeasureError("프레임이 없다 — work/*/frames/seg_*.jpg")
    if n > len(paths):
        raise MeasureError(f"프레임 {len(paths)}장뿐인데 {n}장을 요구했다")
    keyed = sorted(paths, key=lambda p: hashlib.blake2b(
        f"{seed}|{p}".encode("utf-8"), digest_size=8).hexdigest())
    return sorted(keyed[:n])


def freeze_frames(n: int, out=None, seed: int = SEED) -> dict:
    """실행 **전에** 프레임 목록과 설정을 동결한다. 덮어쓰지 않는다."""
    p = Path(out) if out is not None else FRAMES_FILE
    if p.exists():
        raise MeasureError(f"이미 동결돼 있다: {p} — 결과를 보고 고치지 않는다")
    cfg = _cfg()
    doc = {"protocol": PROTOCOL, "n": n, "seed": seed,
           "frames": select_frames(n, seed),
           "vlm_max_pixels": cfg["vlm_max_pixels"],
           "vlm_max_new_tokens": cfg["vlm_max_new_tokens"],
           "vlm_rep_penalty": cfg["vlm_rep_penalty"],
           "quantized": True,
           "arms": dict(ARM_MODEL),
           "commit": _git("rev-parse", "HEAD"),
           "git_dirty": bool(_git("status", "--porcelain")),
           "frozen_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "note": ("경로만 보고 결정적으로 골랐다. 캡션·자막·검색 결과를 선정 신호로 "
                    "쓰지 않는다")}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    return doc


def load_frozen(path=None) -> dict:
    p = Path(path) if path is not None else FRAMES_FILE
    if not p.is_file():
        raise MeasureError(f"동결 파일이 없다: {p} — freeze를 먼저 돌려라")
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("protocol") != PROTOCOL:
        raise MeasureError(f"다른 프로토콜 파일이다: {doc.get('protocol')!r}")
    missing = [f for f in doc["frames"] if not (ROOT / f).is_file()]
    if missing:
        raise MeasureError(f"동결 프레임 {len(missing)}장이 없다 (예: {missing[:2]})")
    return doc


def out_path(stage: str) -> Path:
    if stage not in STAGES:
        raise MeasureError(f"알 수 없는 stage {stage!r} — {list(STAGES)}만 쓴다")
    return OUT_DIR / f"p3_opcost_{stage}.json"


def summarize_output(s: str, n_tokens: int) -> dict:
    """**길이와 토큰 수만** 남긴다. 문자열은 버린다."""
    return {"chars": len(s or ""), "n_tokens": int(n_tokens)}


def _storage_bytes(model_id: str) -> int:
    import huggingface_hub
    try:
        d = Path(huggingface_hub.snapshot_download(model_id,
                                                   local_files_only=True))
    except Exception:
        return -1
    return sum(p.stat().st_size for p in d.rglob("*") if p.is_file())


def _vram():
    import torch
    free, total = torch.cuda.mem_get_info()
    return free / GB, total / GB


def measure_arm(arm: str, frames: list, load_repeats: int = LOAD_REPEATS,
                warmup: int = 1) -> dict:
    """한 arm의 생성 비용. **여기서만 GPU를 쓴다.**"""
    import torch
    import m3_generate as G

    cfg = arm_config(arm)
    free0, total = _vram()

    load_secs, model, processor = [], None, None
    for i in range(load_repeats):
        if model is not None:
            del model, processor
            gc.collect()
            torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        model, processor = G.load_vlm(cfg)
        load_secs.append(round(time.time() - t0, 3))
    after_load = torch.cuda.max_memory_allocated() / GB

    prompt = cfg.get("caption_prompt")
    if not prompt:
        raise MeasureError("config에 caption_prompt가 없다 — 프롬프트를 지어내지 않는다")

    torch.cuda.reset_peak_memory_stats()
    secs, outs, failures, oom = [], [], 0, False
    min_free = None
    for i, rel in enumerate(frames):
        path = ROOT / rel
        try:
            t0 = time.time()
            s = G.caption_frame(path, prompt, model, processor, cfg)
            dt = time.time() - t0
            if i >= warmup:                      # 첫 장은 워밍업으로 버린다
                secs.append(round(dt, 3))
                ids = processor.tokenizer(s or "")["input_ids"]
                outs.append(summarize_output(s, len(ids)))
            del s
        except torch.cuda.OutOfMemoryError:
            oom, failures = True, failures + 1
        except Exception:
            failures += 1
        # 프레임마다 **실제 남은 VRAM**을 본다. allocated peak은 allocator가 잡아둔
        # 예약분과 CUDA 컨텍스트를 빼고 세므로 그것만으로 headroom을 말할 수 없다
        free_now, _ = _vram()
        min_free = free_now if min_free is None else min(min_free, free_now)
    peak = torch.cuda.max_memory_allocated() / GB
    peak_reserved = torch.cuda.max_memory_reserved() / GB

    prov = G.caption_provenance(cfg, model, prompt, PROTOCOL)
    del model, processor
    gc.collect()
    torch.cuda.empty_cache()

    return {
        "arm": arm,
        "provenance": {
            "model_id": prov.get("model_id") or cfg["caption_model"],
            "model_revision": prov.get("model_revision"),
            # 실효값이다. 요청값(config_vlm_4bit)과 갈리면 그 자체가 사고다
            "dtype_effective": prov.get("dtype"),
            "quantized_effective": prov.get("quantized"),
            "quantized_requested": cfg["vlm_4bit"],
            "quantization_mismatch": bool(prov.get("quantized")) != bool(
                cfg["vlm_4bit"]),
            "attn_implementation": prov.get("attn_implementation"),
            "vlm_max_pixels": cfg["vlm_max_pixels"],
            "vlm_max_new_tokens": cfg["vlm_max_new_tokens"],
            "vlm_rep_penalty": cfg["vlm_rep_penalty"],
            "prompt_sha256": prov.get("prompt_sha256"),
            "torch": torch.__version__,
            "transformers": __import__("transformers").__version__,
            "python": sys.version.split()[0],
            "gpu": torch.cuda.get_device_name(0),
            "vram_total_gb": round(total, 2),
            "vram_free_at_start_gb": round(free0, 2),
            "commit": _git("rev-parse", "HEAD"),
        },
        "cost": {
            "load_sec_median": statistics.median(load_secs),
            "load_sec_all": load_secs,
            "vram_after_load_gb": round(after_load, 3),
            "vram_peak_gb": round(peak, 3),
            "vram_peak_reserved_gb": round(peak_reserved, 3),
            "vram_min_free_gb": (round(min_free, 3)
                                 if min_free is not None else None),
            "headroom_min_gb": (round(min_free, 3)
                                if min_free is not None else None),
            "sec_per_frame_median": (round(statistics.median(secs), 3)
                                     if secs else None),
            "sec_per_frame_mean": (round(statistics.fmean(secs), 3)
                                   if secs else None),
            "sec_per_frame_all": secs,
            "n_frames": len(secs),
            "n_frames_attempted": len(frames),
            "n_failures": failures,
            "oom": oom,
            "model_storage_bytes": _storage_bytes(cfg["caption_model"]),
            "out_chars_mean": (round(statistics.fmean(
                [o["chars"] for o in outs]), 1) if outs else None),
            "out_tokens_mean": (round(statistics.fmean(
                [o["n_tokens"] for o in outs]), 1) if outs else None),
        },
    }


def run(stage: str, blocks: int = 2, frames_path=None, out=None) -> dict:
    frozen = load_frozen(frames_path)
    frames = frozen["frames"]
    if stage == "canary":
        frames, blocks = frames[:3], 1
    p = Path(out) if out is not None else out_path(stage)
    if p.exists():
        raise MeasureError(f"이미 결과가 있다: {p} — 새로 돌리려면 치우고 시작하라")

    order, blocks_out = block_order(blocks), []
    for i, arm in enumerate(order):
        print(f"=== block {i + 1}/{len(order)} arm={arm} "
              f"frames={len(frames)} ({time.strftime('%H:%M:%S')}) ===",
              flush=True)
        blocks_out.append(dict(measure_arm(arm, frames), block=i))

    per_arm = {}
    for arm in ARM_ORDER:
        rows = [b for b in blocks_out if b["arm"] == arm]
        med = [r["cost"]["sec_per_frame_median"] for r in rows
               if r["cost"]["sec_per_frame_median"] is not None]
        per_arm[arm] = {
            "blocks": len(rows),
            "sec_per_frame_median_of_blocks": (statistics.median(med)
                                               if med else None),
            "vram_peak_gb_max": max(r["cost"]["vram_peak_gb"] for r in rows),
            "vram_after_load_gb_max": max(r["cost"]["vram_after_load_gb"]
                                          for r in rows),
            "load_sec_median": statistics.median(
                [r["cost"]["load_sec_median"] for r in rows]),
            "n_failures": sum(r["cost"]["n_failures"] for r in rows),
            "oom": any(r["cost"]["oom"] for r in rows),
            "model_storage_bytes": rows[0]["cost"]["model_storage_bytes"],
            "out_chars_mean": rows[0]["cost"]["out_chars_mean"],
            "out_tokens_mean": rows[0]["cost"]["out_tokens_mean"],
        }

    doc = {
        "probe": "p3_opcost_measure", "protocol": PROTOCOL, "stage": stage,
        "frames_frozen": {"file": str(Path(frames_path or FRAMES_FILE)
                                      .name),
                          "n_declared": frozen["n"], "n_used": len(frames),
                          "seed": frozen["seed"],
                          "frozen_commit": frozen.get("commit")},
        "block_order": order,
        "blocks": blocks_out,
        "per_arm": per_arm,
        "caption_text_stored": False,
        "reads_retrieval_outcome": False,
        "wrote_to_index": False,
        "labels_used": 0,
        "commit": _git("rev-parse", "HEAD"),
        "measured_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "note": ("배포 정밀도(양 arm 4bit)·배포 기기에서 잰 생성 비용이다. "
                 "검색 성능·캡션 품질은 재지 않았다"),
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    print(f"-> {p}")
    return doc


def summary(doc: dict) -> dict:
    """arm별 보고표. **평균 하나로 뭉개지 않는다** — 블록별 값과 순서 효과를 같이 낸다."""
    out, per = {}, doc["per_arm"]
    for arm in ARM_ORDER:
        rows = [b for b in doc["blocks"] if b["arm"] == arm]
        c = [r["cost"] for r in rows]
        p = rows[0]["provenance"]
        out[arm] = {
            "model_id": p["model_id"], "model_revision": p["model_revision"],
            "quantized_effective": p["quantized_effective"],
            "quantization_mismatch": p.get("quantization_mismatch"),
            "dtype_effective": p["dtype_effective"],
            "sec_per_frame_median_per_block": [x["sec_per_frame_median"]
                                               for x in c],
            "sec_per_frame_median": per[arm]["sec_per_frame_median_of_blocks"],
            "frames_per_sec": (round(1.0 / per[arm][
                "sec_per_frame_median_of_blocks"], 4)
                if per[arm]["sec_per_frame_median_of_blocks"] else None),
            "vram_peak_allocated_gb_per_block": [x["vram_peak_gb"] for x in c],
            "vram_peak_reserved_gb_per_block": [x.get("vram_peak_reserved_gb")
                                                for x in c],
            # 이름을 관찰 범위로 제한한다 — load 구간은 샘플링하지 않았다
            "minimum_generation_free_vram_gb_per_block": [
                x.get("vram_min_free_gb") for x in c],
            "vram_total_gb": p["vram_total_gb"],
            "vram_free_at_start_gb": p["vram_free_at_start_gb"],
            "load_sec_per_block": [x["load_sec_all"] for x in c],
            "n_frames_attempted": [x.get("n_frames_attempted") for x in c],
            "n_frames_timed": [x["n_frames"] for x in c],
            "n_failures": per[arm]["n_failures"], "oom": per[arm]["oom"],
            "out_chars_mean": per[arm]["out_chars_mean"],
            "out_tokens_mean": per[arm]["out_tokens_mean"],
            # frame당 시간이 짧은 것이 **연산 효율** 때문인지 **출력이 짧은** 때문인지
            # 가른다. 배포 비용의 지표는 frame당 시간이지만, 기전을 오독하면 안 된다.
            # 분모가 전체 caption wall-clock(전처리·prefill·고정 오버헤드 포함)이므로
            # decoder token-generation speed가 아니다 — 이름에 범위를 박는다
            "end_to_end_output_tokens_per_sec": (
                round(per[arm]["out_tokens_mean"] /
                      per[arm]["sec_per_frame_median_of_blocks"], 3)
                if per[arm]["out_tokens_mean"] and
                per[arm]["sec_per_frame_median_of_blocks"] else None),
            "model_storage_gb": (round(per[arm]["model_storage_bytes"] / GB, 2)
                                 if per[arm]["model_storage_bytes"] and
                                 per[arm]["model_storage_bytes"] > 0 else None),
            # 같은 arm의 블록 간 차이 — 웜업·써멀 드리프트 점검
            "block_drift_sec_per_frame": (
                round(max(x["sec_per_frame_median"] for x in c) -
                      min(x["sec_per_frame_median"] for x in c), 3)
                if all(x["sec_per_frame_median"] is not None for x in c)
                else None),
        }
    b, cd = out["3b"], out["4b"]
    ratio = None
    if b["sec_per_frame_median"] and cd["sec_per_frame_median"]:
        ratio = {
            "sec_per_frame_candidate_over_base": round(
                cd["sec_per_frame_median"] / b["sec_per_frame_median"], 4),
            "vram_peak_reserved_delta_gb": (
                round(max(x for x in cd["vram_peak_reserved_gb_per_block"]
                          if x is not None) -
                      max(x for x in b["vram_peak_reserved_gb_per_block"]
                          if x is not None), 3)
                if any(x is not None
                       for x in cd["vram_peak_reserved_gb_per_block"])
                else None),
            "out_tokens_candidate_over_base": (
                round(cd["out_tokens_mean"] / b["out_tokens_mean"], 4)
                if b["out_tokens_mean"] else None),
            "end_to_end_output_tokens_per_sec_candidate_over_base": (
                round(cd["end_to_end_output_tokens_per_sec"] /
                      b["end_to_end_output_tokens_per_sec"], 4)
                if b["end_to_end_output_tokens_per_sec"] and
                cd["end_to_end_output_tokens_per_sec"] else None),
        }
    return {
        "protocol": PROTOCOL, "stage": doc["stage"],
        "block_order": doc["block_order"], "arms": out, "ratio": ratio,
        "caption_text_stored": doc["caption_text_stored"],
        "measurement_grade": ("deployment operational feasibility의 descriptive "
                              "measurement다. 통계적 모집단 추정이 아니다"),
        "wording_rule": ("wall-clock이 짧은 것과 운영비가 낮은 것은 다르다 — 전력·"
                         "실제 비용은 측정하지 않았다. '계산적으로 더 효율적'이라고 "
                         "쓰지 않는다 — 출력 길이 차이가 섞여 있다. 더 짧은 출력이 "
                         "frame-level wall-clock 감소와 함께 관측됐고 그 차이에 "
                         "실질적으로 기여한 것으로 일관된다고까지만 쓴다 — generation "
                         "kernel 속도를 분리 측정하지 않았으므로 '대부분 출력 길이 "
                         "때문'이라는 인과 배분은 쓰지 않는다"),
        "token_rate_scope_note": ("end_to_end_output_tokens_per_sec는 출력 토큰 수를 "
                                  "전체 caption wall-clock으로 나눈 값이다. 이미지 "
                                  "전처리·prefill·고정 오버헤드가 분모에 들어가므로 "
                                  "decoder token-generation speed가 아니다. '토큰당 "
                                  "처리속도'가 아니라 '전체 caption wall-clock 대비 "
                                  "출력 토큰 rate'로 쓴다"),
        "headroom_note": ("allocated peak은 allocator 예약분과 CUDA 컨텍스트를 빼고 "
                          "센다. fit 판단은 reserved peak과 생성 중 최소 free VRAM으로 "
                          "한다"),
        "free_vram_sampling_scope": "generation_loop_only",
        "free_vram_scope_note": ("model load 구간·CUDA workspace 생성 순간은 "
                                 "샘플링하지 않았다. 로드 자체는 arm별 3회×2블록 전부 "
                                 "성공했고 OOM 0이므로 load feasibility는 관측됐으나 "
                                 "그 구간의 free VRAM 수치는 없다"),
        "order_effect_rule": ("블록 2개로 'order effect 없음'을 통계적으로 주장하지 "
                              "않는다. 드리프트 크기만 기술한다"),
    }


def main():
    ap = argparse.ArgumentParser(description=f"{PROTOCOL} 실측")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--n", type=int, default=40)
    f.add_argument("--out", default=None)
    r = sub.add_parser("run")
    r.add_argument("--stage", choices=STAGES, required=True)
    r.add_argument("--blocks", type=int, default=2)
    r.add_argument("--frames", default=None)
    r.add_argument("--out", default=None)
    s = sub.add_parser("report")
    s.add_argument("--result", required=True)
    s.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.cmd == "freeze":
        d = freeze_frames(a.n, out=a.out)
        print(f"동결 {d['n']}장 · seed {d['seed']} · commit {d['commit'][:7]}")
        return 0
    if a.cmd == "report":
        doc = json.loads(Path(a.result).read_text(encoding="utf-8"))
        r2 = summary(doc)
        print(json.dumps(r2, ensure_ascii=False, indent=2))
        if a.out:
            Path(a.out).write_text(json.dumps(r2, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        return 0
    run(a.stage, blocks=a.blocks, frames_path=a.frames, out=a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

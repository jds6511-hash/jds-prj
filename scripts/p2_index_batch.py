"""P2 두 arm 색인 배치 — 신규 표본 35편을 격리 경로에 색인한다.

사전등록: `docs/preregistration/부호역전_확증_사전등록_2026-08-18.md` +
`보충2_P2설계` + `보충3_P2표집범위` + `보충4_P2표집틀검증`.
결정 문서: `docs/P2_승인1_규모확정_2026-08-20.md` · `docs/P2_선정표본_2026-08-20.md`.

```
PRIMARY   Δ_deploy = MRR_caption(qwen3vl_4b_q4/P0) − MRR_caption(qwen25_3b_4bit/P0)
          캡션 단독 α=0.0. 이 배치는 **색인만** 만든다 — 평가는 GT 라벨 뒤다
```

**이 배치가 지키는 것은 성능이 아니라 비교 가능성이다.** 두 arm이 바꾸는 것은
`caption_model` 하나뿐이어야 한다. 그래서 프레임과 자막을 **한 번만 만들고 복제**한다
— 각 arm에서 따로 만들면 생성 흔들림이 모델 차이로 오독될 여지가 생긴다(같은 조건에서
greedy는 결정적이라고 2026-08-18에 실측했지만, 조건이 같다는 것을 코드로 보장하는 편이
싸다).

```
m1_segments     구간 분할 + provenance 기록 (fail-closed)
m2_frames       구간당 대표 프레임 1장
mirror_frames   3b work → 4b work 복제 (프레임·segments, 캡션 제외)
m3_subtitles    STT 1회 — 3b에서만 돌리고 4b로 복제한다
m3_captions     arm별 캡션 생성  ← 유일한 arm 차이
m4_index        arm별 임베딩·색인
```

**본 인덱스(`work/`·`results/`)를 건드리지 않는다.** 변형 config는 항상
`config.yaml`에서 재생성한다(CLAUDE.md 실무 규칙 4번, threshold confound 전례).

정식 실행은 `exp_launcher.py`가 감싼다 — 이 스크립트를 직접 nohup으로 돌리지 마라.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PRIMARY = ("Δ_deploy = MRR_caption(qwen3vl_4b_q4/P0) − "
           "MRR_caption(qwen25_3b_4bit/P0), 캡션 단독 α=0.0")
SELECTED_REL = "docs/P2_선정표본_2026-08-20.json"

# 사전등록 §2가 고정한 arm. **결과를 보고 바꾸지 않는다.**
# 정밀도는 양쪽 4bit — PRIMARY가 배포 경로 비교로 정의돼 있다(보충2 §2).
ARMS = {
    "3b": {"caption_model": "Qwen/Qwen2.5-VL-3B-Instruct", "vlm_4bit": True},
    "4b": {"caption_model": "Qwen/Qwen3-VL-4B-Instruct", "vlm_4bit": True},
}
BASE_ARM = "3b"          # 프레임·자막을 만드는 arm. 여기서 복제한다

        # `--subtitles-only`는 캡션이 이미 있는 인덱스에만 쓸 수 있다(8-5(7): STT 설정
# 비교용). 신규 인덱스에서는 거부되므로 기준 arm은 기본 모드로 STT와 캡션을 함께
# 만들고, 그 자막을 후보 arm으로 복제한 뒤 후보는 `--captions-only`로 캡션만 만든다.
# 결과적으로 STT는 1회이고 두 arm의 자막이 바이트 단위로 같다.
STAGES = (
    {"name": "m1_segments", "module": "m1_preprocess", "arms": (BASE_ARM,)},
    {"name": "m2_frames", "module": "m2_keyframe", "arms": (BASE_ARM,)},
    {"name": "m3_base", "module": "m3_generate", "arms": (BASE_ARM,)},
    {"name": "mirror_frames", "module": None, "arms": ()},
    {"name": "m3_captions", "module": "m3_generate",
     "arms": tuple(a for a in ARMS if a != BASE_ARM),
     "extra": ["--captions-only"]},
    {"name": "m4_index", "module": "m4_index", "arms": tuple(ARMS)},
)

# 복제 대상. 캡션은 **포함하지 않는다** — arm마다 새로 만드는 유일한 값이다
MIRROR_SEG_DROP = ("caption",)
MIRROR_FILES = ("audio.wav", "stt_cache.json")


class BatchError(RuntimeError):
    pass


def _tag(stage: str) -> str:
    return "p2c" if stage == "canary" else "p2"


def make_configs(base_config, out_dir, stage: str = "full") -> dict:
    """`config.yaml`에서 arm별 config를 **재생성**한다. 손으로 고치지 않는다."""
    base = yaml.safe_load(Path(base_config).read_text(encoding="utf-8"))
    tag = _tag(stage)
    out = {}
    for arm, over in ARMS.items():
        cfg = json.loads(json.dumps(base))          # 깊은 복사
        cfg.update(over)
        cfg["paths"] = dict(cfg.get("paths") or {})
        cfg["paths"]["work"] = f"work_{tag}_{arm}"
        cfg["paths"]["results"] = f"results_{tag}_{arm}"
        p = Path(out_dir) / f"config_{tag}_{arm}.yaml"
        p.write_text(
            "# 자동 생성 — scripts/p2_index_batch.py. 손으로 고치지 마라.\n"
            f"# 원본: {Path(base_config).name} · arm: {arm} · stage: {stage}\n"
            + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
            encoding="utf-8")
        out[arm] = str(p)
    return out


def video_ids(selected: list, stage: str = "full") -> list:
    if stage == "canary":
        # 전 경로를 돌리면서 GPU를 가장 적게 쓰는 영상 하나
        return [min(selected, key=lambda r: r["n_segments"])["source_id"]]
    return [r["source_id"] for r in selected]


def mirror(src_vdir, dst_vdir) -> None:
    """프레임·자막을 복제한다. **캡션은 옮기지 않는다.**"""
    src, dst = Path(src_vdir), Path(dst_vdir)
    doc = json.loads((src / "segments.json").read_text(encoding="utf-8"))
    existing = dst / "segments.json"
    if existing.exists():
        cur = json.loads(existing.read_text(encoding="utf-8"))
        if any((s.get("caption") or "").strip() for s in cur.get("segments", [])):
            raise BatchError(
                f"{dst}에 이미 캡션이 있다 — 복제가 그것을 덮는다. 새 run_id를 써라")
    for s in doc.get("segments", []):
        for k in MIRROR_SEG_DROP:
            s.pop(k, None)
    doc.pop("caption_provenance", None)
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "segments.json").write_text(
        json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    if (src / "frames").is_dir():
        shutil.copytree(src / "frames", dst / "frames", dirs_exist_ok=True)
    for f in MIRROR_FILES:
        if (src / f).is_file():
            shutil.copyfile(src / f, dst / f)


def _run_module(module: str, config: str, video_id: str, extra=None) -> None:
    cmd = [sys.executable, str(ROOT / "src" / f"{module}.py"),
           "--config", config, "--video-id", video_id, *(extra or [])]
    print(f"    $ {' '.join(cmd[1:])}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        raise BatchError(f"{module} 실패 (video={video_id}, rc={r.returncode})")


def _work(config: str) -> Path:
    cfg = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
    return ROOT / cfg["paths"]["work"]


def _env_provenance() -> dict:
    """어느 기계·어느 commit·어느 라이브러리로 만든 색인인지. 08-17 추적 실패의 교훈."""
    import platform
    def _g(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True,
                              encoding="utf-8", errors="replace").stdout.strip()
    prov = {"git_head": _g("rev-parse", "HEAD"),
            "git_dirty": bool(_g("status", "--porcelain")),
            "host": platform.node(), "python": platform.python_version(),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        import torch
        prov["torch"] = torch.__version__
        prov["cuda"] = torch.version.cuda
        prov["gpu"] = (torch.cuda.get_device_name(0)
                       if torch.cuda.is_available() else None)
    except Exception as e:                                  # noqa: BLE001
        prov["torch_error"] = str(e)[:200]
    try:
        import transformers
        prov["transformers"] = transformers.__version__
    except Exception as e:                                  # noqa: BLE001
        prov["transformers_error"] = str(e)[:200]
    return prov


def _collect(configs: dict, vids: list, expected: dict) -> dict:
    """산출물 실측 — 검증 훅이 읽는다. 여기서 판정하지 않는다."""
    import numpy as np
    import common
    import hashlib
    arms = {}
    for arm, cfgp in configs.items():
        w = _work(cfgp)
        videos, prov = {}, None
        for vid in vids:
            d = w / vid
            doc = json.loads((d / "segments.json").read_text(encoding="utf-8"))
            segs = doc.get("segments", [])
            subs = "\n".join(s.get("subtitle") or "" for s in segs)
            row = {
                "n_segments": doc.get("n_segments"),
                "expected_n_segments": expected.get(vid),
                "captions_nonempty": sum(1 for s in segs
                                         if (s.get("caption") or "").strip()),
                "subtitle_sha256": hashlib.sha256(
                    subs.encode("utf-8")).hexdigest(),
                "provenance_present": bool(doc.get("provenance")),
            }
            meta_p = d / "meta.json"
            if meta_p.is_file():
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
                row["text_hash_matches_meta"] = (
                    meta.get("text_hash") == common.index_text_hash(doc))
                shapes = {}
                for k in ("emb_sub", "emb_cap"):
                    f = d / f"{k}.npy"
                    shapes[k] = list(np.load(f).shape) if f.is_file() else None
                row["emb_shapes"] = shapes
            prov = doc.get("caption_provenance") or prov
            videos[vid] = row
        arms[arm] = {"videos": videos, "caption_provenance": prov or {}}
    return arms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("canary", "full"), required=True)
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--selected", default=SELECTED_REL)
    ap.add_argument("--run-dir", required=True,
                    help="launcher가 주는 run 디렉터리 — 산출물·마커를 여기 남긴다")
    ap.add_argument("--only-stage", action="append",
                    help="디버깅용: 특정 단계만. 기본은 전 단계")
    a = ap.parse_args()

    run_dir = Path(a.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    sel = json.loads((ROOT / a.selected).read_text(encoding="utf-8"))["selected"]
    vids = video_ids(sel, a.stage)
    expected = {r["source_id"]: r["n_segments"] for r in sel}
    configs = make_configs(ROOT / a.config, ROOT, a.stage)
    print(f"[P2] stage={a.stage}  영상 {len(vids)}편  arms={list(configs)}",
          flush=True)

    t0 = time.time()
    timing = {}
    for st in STAGES:
        if a.only_stage and st["name"] not in a.only_stage:
            continue
        ts = time.time()
        print(f"=== {st['name']} ({time.strftime('%H:%M:%S')}) ===", flush=True)
        if st["name"] == "mirror_frames":
            for arm in ARMS:
                if arm == BASE_ARM:
                    continue
                for vid in vids:
                    mirror(_work(configs[BASE_ARM]) / vid,
                           _work(configs[arm]) / vid)
        else:
            for arm in st["arms"]:
                for vid in vids:
                    _run_module(st["module"], configs[arm], vid,
                                st.get("extra"))
        timing[st["name"]] = round(time.time() - ts, 1)
        (run_dir / f"STAGE_{st['name']}_DONE").write_text(
            json.dumps({"elapsed_sec": timing[st["name"]]}), encoding="utf-8")

    rep = {"probe": "p2_index_batch", "stage": a.stage.upper(),
           "primary": PRIMARY, "n_videos": len(vids), "video_ids": vids,
           "configs": {k: Path(v).name for k, v in configs.items()},
           "timing_sec": timing, "total_sec": round(time.time() - t0, 1),
           "provenance": _env_provenance(),
           "arms": _collect(configs, vids, expected),
           "note": "색인만 만든다 — 평가는 GT 라벨 뒤 별도 단계다"}
    # **stage별 파일명.** launcher는 CANARY와 FULL이 같은 run_id를 공유하고, 같은
    # 이름을 쓰면 FULL 진입에서 CANARY 산출물이 "부분 산출물"로 잡혀 막힌다. 이름이
    # stage에 귀속되지 않으면 반대 사고(1편짜리 CANARY 결과가 FULL 결과 행세)도 난다.
    out = run_dir / f"p2_index_batch_run_{a.stage}.json"
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"[P2] 완료 {rep['total_sec']}s → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

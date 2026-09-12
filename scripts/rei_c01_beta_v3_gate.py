"""WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1 — 입력 준비 + static gate T1~T9.

사전등록: `docs/preregistration/WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1_2026-09-12.md`

**서버 실행 전에 이 스크립트가 PASS해야 한다.** 하나라도 실패하면
`runs/rei_c01_beta_v3/static_gate.json`에 FAIL로 적고 종료 코드 1로 멈춘다.

새 inference 없음. 새 adapter 실행 없음 — 선행 사건 산출물을 그대로 복사한다.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

EVENT = "WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1"
PREREG = ("docs/preregistration/"
          "WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1_2026-09-12.md")

SRC_SEGMENTS = ROOT / "runs" / "rei_c01" / "b_beta" / "segments.json"
SRC_CONFIG = ROOT / "configs" / "rei_c01_beta.yaml"

RUN_ROOT = ROOT / "runs" / "rei_c01_beta_v3"
CELL_DIR = RUN_ROOT / "b_beta_v3"

# §2 동결 해시
FROZEN_SHA256 = {
    "segments.json":
        "53d660c05097e97f8d152e24a231bc1744cc83d91bca84e2ac1157451a1786ae",
    "configs/rei_c01_beta.yaml":
        "d6cf9521e3dfdcd247046ebfe81adc3d476fe0f9321ac691b74d91576914068c",
}

# §5 T6
BASELINE_PATHS = [
    "config.yaml",
    "work_full/full_xekZO4n4QuE/segments.json",
    "runs/v3_paired/submission_manifest.json",
]
# §5 T7 — v2 사건보다 넓다. prompt/grounding까지 포함한다.
ENGINE_SOURCES = [
    "scripts/v2_1_b2_orchestrate.py",
    "src/v2_1_prompt.py",
    "src/v2_1_grounding.py",
    "src/v2_1_render_hwpx.py",
    "src/v2_1_segments.py",
]

STRIDE_SEC = 24.0
RANGE_END_SEC = 600.0
EXPECTED_SEGMENTS = 24


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8")


def coverage(rows: list[dict]) -> tuple[float, float]:
    """(중복 제거 커버리지, 인접 겹침 총합)."""
    dup = sum(max(0.0, a["end"] - b["start"]) for a, b in zip(rows, rows[1:]))
    merged: list[list[float]] = []
    for r in sorted(rows, key=lambda x: x["start"]):
        if merged and r["start"] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], r["end"])
        else:
            merged.append([r["start"], r["end"]])
    return round(sum(e - s for s, e in merged), 6), round(dup, 6)


def main() -> int:
    checks: list[dict] = []

    def check(cid: str, desc: str, ok: bool, detail=None) -> bool:
        checks.append({"id": cid, "desc": desc,
                       "result": "PASS" if ok else "FAIL", "detail": detail})
        return ok

    def bail(msg: str) -> int:
        write_json(RUN_ROOT / "static_gate.json",
                   {"event": EVENT, "prereg": PREREG, "gate": "FAIL",
                    "code_git_head": git_head(), "checks": checks})
        print(msg)
        return 1

    # ── T1 · T2 frozen 해시 ────────────────────────────────────────
    if not SRC_SEGMENTS.exists():
        check("T1", "입력 segments.json 존재", False, str(SRC_SEGMENTS))
        return bail("T1 FAIL — 입력 없음. 중단")
    seg_hash = sha(SRC_SEGMENTS)
    if not check("T1", "입력 segments.json 해시가 prereg §2와 일치",
                 seg_hash == FROZEN_SHA256["segments.json"], seg_hash):
        return bail("T1 FAIL — 중단")

    cfg_hash = sha(SRC_CONFIG)
    if not check("T2", "config 해시가 prereg §2와 일치",
                 cfg_hash == FROZEN_SHA256["configs/rei_c01_beta.yaml"], cfg_hash):
        return bail("T2 FAIL — 중단")

    baseline_before = {p: sha(ROOT / p) for p in BASELINE_PATHS}
    engine_before = {p: sha(ROOT / p) for p in ENGINE_SOURCES}

    # ── T3 · T4 · T5 입력 구조 ─────────────────────────────────────
    doc = json.loads(SRC_SEGMENTS.read_text(encoding="utf-8"))
    segs = doc["segments"]

    idx_ok = ([s["idx"] for s in segs] == list(range(EXPECTED_SEGMENTS))
              and all(s["start"] == s["idx"] * STRIDE_SEC for s in segs))
    check("T3", "segment 24개 · idx 연속 0…23 · start == idx*24",
          len(segs) == EXPECTED_SEGMENTS and idx_ok, len(segs))

    cov, dup = coverage(segs)
    check("T4", "duplicate coverage == 0초 · temporal coverage == 600초",
          dup == 0.0 and cov == RANGE_END_SEC, {"coverage": cov, "duplicate": dup})

    check("T5", "subtitle·caption 필드 전 segment 존재",
          all("subtitle" in s and "caption" in s for s in segs),
          {"subtitle_populated": sum(1 for s in segs if s["subtitle"]),
           "caption_populated": sum(1 for s in segs if s["caption"])})

    # ── T8 contract 해석 (모델 미적재) ─────────────────────────────
    try:
        import v2_1_prompt as vp
        resolved = vp.resolve_contract("v3")
        t8_ok = resolved["version"] == vp.PROMPT_VERSION_V3
        detail = {"resolved_version": resolved["version"],
                  "optional_keys": list(resolved["output"]["optional"])}
        # 모르는 이름이 조용히 v2로 떨어지지 않는다
        try:
            vp.resolve_contract("v2.5")
            t8_ok = False
            detail["unknown_name"] = "예외가 나지 않았다"
        except vp.PromptError:
            detail["unknown_name"] = "PromptError — 정상"
    except Exception as exc:                           # noqa: BLE001
        t8_ok, detail = False, str(exc)
    check("T8", 'resolve_contract("v3") == PROMPT_VERSION_V3', t8_ok, detail)

    # ── 입력 배치 (격리 경로에만 쓴다) ─────────────────────────────
    CELL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC_SEGMENTS, CELL_DIR / "segments.json")
    work_dir = ROOT / "work_rei_c01" / doc.get("video_id", "rei_c01_nonoverlap")
    work_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC_SEGMENTS, work_dir / "segments.json")

    copied_ok = (sha(CELL_DIR / "segments.json") == seg_hash
                 and sha(work_dir / "segments.json") == seg_hash)
    check("T3b", "복사본 해시가 원본과 동일", copied_ok)

    # ── T6 · T7 불변 (쓰기 후 재계산) ──────────────────────────────
    check("T6", "baseline 경로 해시 불변",
          {p: sha(ROOT / p) for p in BASELINE_PATHS} == baseline_before)
    check("T7", "engine source 해시 불변",
          {p: sha(ROOT / p) for p in ENGINE_SOURCES} == engine_before)

    # ── T9 금지 경로 ───────────────────────────────────────────────
    m9 = ROOT / "src" / "m9_report_eval.py"
    eval_test = ROOT / "results" / "eval_test.json"
    base_mtime = RUN_ROOT.stat().st_mtime if RUN_ROOT.exists() else 0
    touched = [str(p.relative_to(ROOT)) for p in (eval_test, m9)
               if p.exists() and p.stat().st_mtime > base_mtime]
    check("T9", "official test 경로 미접근 · M9 미호출", not touched, touched)

    gate = "PASS" if all(c["result"] == "PASS" for c in checks) else "FAIL"
    write_json(RUN_ROOT / "static_gate.json",
               {"event": EVENT, "prereg": PREREG, "gate": gate,
                "code_git_head": git_head(),
                "input_sha256": {"segments.json": seg_hash,
                                 "configs/rei_c01_beta.yaml": cfg_hash},
                "baseline_sha256_before": baseline_before,
                "engine_source_sha256_before": engine_before,
                "new_inference_count": 0,
                "checks": checks})

    for c in checks:
        print(f"{c['id']:4s} {c['result']:4s}  {c['desc']}")
    print(f"\nSTATIC GATE: {gate}")
    return 0 if gate == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

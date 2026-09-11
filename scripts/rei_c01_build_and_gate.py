"""WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1 — adapter 실행 + static gate.

사전등록 §7 isolation · §8 static gate S1~S12.
**서버 text generation 전에 이 스크립트가 PASS해야 한다.** 하나라도 실패하면
`static_gate.json`에 FAIL로 적고 종료 코드 1로 멈춘다 — generation을 시작하지 않는다.

새 inference 없음. 읽기: frozen WVR artifact · work_full segments.json(read-only).
쓰기: work_rei_c01/ · results_rei_c01/ · runs/rei_c01/ · configs/ 뿐이다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import rei_c01_adapter as ad  # noqa: E402

RUN_ROOT = ROOT / "runs" / "rei_c01"
WORK_ROOT = ROOT / "work_rei_c01"
RESULTS_ROOT = ROOT / "results_rei_c01"
CONFIG_DIR = ROOT / "configs"

WVR_DIR = ROOT / "runs" / "wvr_video_overview_preview_v2"
M3_PATH = ROOT / "work_full" / "full_xekZO4n4QuE" / "segments.json"

CELLS = [
    # (cell, view, engine, video_id)
    ("a_alpha", ad.OVERLAP_VIEW, "alpha", "rei_c01_overlap"),
    ("b_alpha", ad.NONOVERLAP_VIEW, "alpha", "rei_c01_nonoverlap"),
    ("a_beta", ad.OVERLAP_VIEW, "beta", "rei_c01_overlap"),
    ("b_beta", ad.NONOVERLAP_VIEW, "beta", "rei_c01_nonoverlap"),
]

# §8 S10 — 불변이어야 하는 baseline 경로
BASELINE_PATHS = [
    "config.yaml",
    "work_full/full_xekZO4n4QuE/segments.json",
    "runs/v3_paired/submission_manifest.json",
]
# §8 S11 — 불변이어야 하는 engine source
ENGINE_SOURCES = [
    "src/m8_report.py",
    "src/v2_1_render_hwpx.py",
    "src/v2_1_segments.py",
    "scripts/v2_1_b2_orchestrate.py",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8")


def build_configs(base_cfg: dict) -> dict:
    """engine별 config 사본. paths.work·paths.results를 동시에 분리한다(규칙 4)."""
    made = {}
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    for engine in ("alpha", "beta"):
        cfg = dict(base_cfg)
        cfg["seg_len_sec"] = int(ad.STRIDE_SEC)      # 24 — adapter 기하와 일치
        cfg["llm_4bit"] = False                       # 서버 24GB
        cfg["paths"] = dict(base_cfg.get("paths", {}))
        cfg["paths"]["work"] = WORK_ROOT.name
        cfg["paths"]["results"] = RESULTS_ROOT.name
        cfg["_provenance"] = {
            "event": ad.EVENT, "prereg": ad.PREREG, "engine": engine,
            "derived_from": "config.yaml", "isolated": True,
        }
        out = CONFIG_DIR / f"rei_c01_{engine}.yaml"
        try:
            import yaml
            out.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                           encoding="utf-8")
        except ImportError:
            out = out.with_suffix(".json")
            write_json(out, cfg)
        made[engine] = out
    return made


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--twice", action="store_true",
                    help="결정성(S2·S8) 확인을 위해 adapter를 2회 실행")
    args = ap.parse_args()

    checks: list[dict] = []

    def check(cid: str, desc: str, ok: bool, detail=None):
        checks.append({"id": cid, "desc": desc,
                       "result": "PASS" if ok else "FAIL", "detail": detail})
        return ok

    # ── S1 frozen source 해시 ───────────────────────────────────────
    try:
        loaded = ad.load_sources(WVR_DIR, M3_PATH)
        check("S1", "frozen source 4개 해시가 prereg §2와 일치", True,
              loaded["source_sha256"])
    except Exception as exc:                      # noqa: BLE001
        check("S1", "frozen source 해시 일치", False, str(exc))
        write_json(RUN_ROOT / "static_gate.json",
                   {"event": ad.EVENT, "gate": "FAIL", "checks": checks})
        print("S1 FAIL — 중단")
        return 1

    # ── baseline / engine source 해시 (S10·S11) ────────────────────
    baseline_hashes = {p: sha(ROOT / p) for p in BASELINE_PATHS}
    engine_hashes = {p: sha(ROOT / p) for p in ENGINE_SOURCES}

    # ── adapter 실행 ───────────────────────────────────────────────
    views: dict[str, dict] = {}
    for view in ad.VIEWS:
        views[view] = ad.build_view(loaded["summaries"], loaded["plan"],
                                    loaded["m3_segments"], view)

    if args.twice:
        same = True
        for view in ad.VIEWS:
            again = ad.build_view(loaded["summaries"], loaded["plan"],
                                  loaded["m3_segments"], view)
            a = json.dumps(views[view], ensure_ascii=False, sort_keys=True)
            b = json.dumps(again, ensure_ascii=False, sort_keys=True)
            same = same and (a == b)
        check("S2", "adapter 결정성 — 2회 산출물 동일", same)
        check("S8", "subtitle 재집계 결정성", same)
    else:
        check("S2", "adapter 결정성 (--twice 미지정)", False, "skipped")
        check("S8", "subtitle 재집계 결정성 (--twice 미지정)", False, "skipped")

    # ── S3~S7 구조 검증 ────────────────────────────────────────────
    lineage_ok = all(
        len(v["lineage"]) == ad.EXPECTED_WINDOW_COUNT
        and all(set(r) == {"adapter_idx", "wvr_window", "broad_visual_summary",
                           "adapter_segment", "subtitle_source_m3_idx"}
                for r in v["lineage"])
        for v in views.values())
    check("S3", "lineage 완전 — 24창 전부 4단계 기록", lineage_ok)

    idx_ok = all([s["idx"] for s in v["doc"]["segments"]] == list(range(24))
                 and all(s["start"] == s["idx"] * ad.STRIDE_SEC
                         for s in v["doc"]["segments"])
                 for v in views.values())
    check("S4", "idx 연속 0…23 · start == idx*24 (두 view)", idx_ok)

    a_rows = views[ad.OVERLAP_VIEW]["doc"]["segments"]
    b_rows = views[ad.NONOVERLAP_VIEW]["doc"]["segments"]
    end_ok = (all(s["end"] == min(s["start"] + ad.WINDOW_SEC, ad.RANGE_END_SEC)
                  for s in a_rows)
              and all(s["end"] == (ad.RANGE_END_SEC if s["idx"] == 23
                                   else s["start"] + ad.STRIDE_SEC)
                      for s in b_rows))
    check("S5", "arm별 end 동결 규칙 준수", end_ok)

    dup_b = ad.duplicate_coverage_sec(b_rows)
    check("S6", "NONOVERLAP_VIEW duplicate coverage == 0초", dup_b == 0.0, dup_b)

    fields_ok = all(("subtitle" in s and "caption" in s)
                    for v in views.values() for s in v["doc"]["segments"])
    check("S7", "subtitle/caption 필드 전 segment 존재", fields_ok)

    # ── 산출물 기록 (isolated 경로에만 쓴다) ────────────────────────
    base_cfg_path = ROOT / "config.yaml"
    try:
        import yaml
        base_cfg = yaml.safe_load(base_cfg_path.read_text(encoding="utf-8"))
    except ImportError:
        base_cfg = {}
    cfg_paths = build_configs(base_cfg or {})

    manifest = {"event": ad.EVENT, "prereg": ad.PREREG,
                "code_git_head": git_head(),
                "new_inference_count": 0,
                "source_sha256": loaded["source_sha256"],
                "baseline_sha256_before": baseline_hashes,
                "engine_source_sha256_before": engine_hashes,
                "views": {v: views[v]["stats"] for v in ad.VIEWS},
                "lineage": {v: views[v]["lineage"] for v in ad.VIEWS}}
    write_json(RUN_ROOT / "adapter_manifest.json", manifest)

    for cell, view, engine, video_id in CELLS:
        doc = json.loads(json.dumps(views[view]["doc"], ensure_ascii=False))
        doc["video_id"] = video_id
        cell_dir = RUN_ROOT / cell
        write_json(cell_dir / "segments.json", doc)
        wdir = WORK_ROOT / video_id
        wdir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cell_dir / "segments.json", wdir / "segments.json")
        write_json(cell_dir / "cell.json",
                   {"cell": cell, "view": view, "engine": engine,
                    "video_id": video_id,
                    "config": str(cfg_paths[engine].relative_to(ROOT)),
                    "work_dir": str(wdir.relative_to(ROOT)),
                    "stats": views[view]["stats"]})

    # ── S9 isolation ───────────────────────────────────────────────
    iso_ok = (WORK_ROOT.exists() and RUN_ROOT.exists()
              and str(WORK_ROOT).startswith(str(ROOT))
              and WORK_ROOT.name != "work")
    check("S9", "isolated work/results 경로만 사용", iso_ok,
          {"work": WORK_ROOT.name, "results": RESULTS_ROOT.name})

    # ── S10·S11 불변 확인 (쓰기 후 재계산) ─────────────────────────
    base_after = {p: sha(ROOT / p) for p in BASELINE_PATHS}
    eng_after = {p: sha(ROOT / p) for p in ENGINE_SOURCES}
    check("S10", "baseline 경로 해시 불변", base_after == baseline_hashes)
    check("S11", "engine source 해시 불변", eng_after == engine_hashes)

    # ── S12 금지 경로 ──────────────────────────────────────────────
    forbidden = [ROOT / "results" / "eval_test.json", ROOT / "src" / "m9_report_eval.py"]
    touched = [str(p.relative_to(ROOT)) for p in forbidden
               if p.exists() and p.stat().st_mtime > (RUN_ROOT.stat().st_mtime
                                                      if RUN_ROOT.exists() else 0)]
    check("S12", "official test 경로 미접근 · M9 미호출", not touched, touched)

    gate = "PASS" if all(c["result"] == "PASS" for c in checks) else "FAIL"
    write_json(RUN_ROOT / "static_gate.json",
               {"event": ad.EVENT, "prereg": ad.PREREG, "gate": gate,
                "code_git_head": git_head(), "checks": checks,
                "views": {v: views[v]["stats"] for v in ad.VIEWS}})

    for c in checks:
        print(f"{c['id']:4s} {c['result']:4s}  {c['desc']}")
    print(f"\nSTATIC GATE: {gate}")
    return 0 if gate == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

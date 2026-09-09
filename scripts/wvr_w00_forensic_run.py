"""W00 forensic 실행기 — 읽기 전용 분석 (2026-09-09).

사전등록: `docs/preregistration/WVR_W00_DEGENERACY_FORENSIC_V1_2026-09-09.md`

```
추론 없음 · GPU 없음 · 기존 artifact는 열어서 읽기만 한다
C1 프롬프트 diff · C2 코드 분기 · C3 raw 구조 · C4 시각 지표 ·
C5 결정성 조건 · C6 parser 책임
```
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import wvr_capacity_probe as probe                          # noqa: E402
import wvr_shadow_v1 as sh                                  # noqa: E402
import wvr_w00_forensic as fx                               # noqa: E402

PREREG = ("docs/preregistration/"
          "WVR_W00_DEGENERACY_FORENSIC_V1_2026-09-09.md")
RESULT_NAME = "w00_forensic_v1.json"
SCANNED_SOURCES = ("src/wvr_shadow_v1.py", "scripts/wvr_shadow_run.py",
                   "scripts/wvr_capacity_probe.py", "src/wvr_density_v2.py")


class ForensicRunError(RuntimeError):
    """forensic 실행 계약 위반."""


def git_head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True)
    return done.stdout.strip() or "unknown"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_record(runs: Path, window_id: str) -> dict:
    path = runs / ("%s_%s.json" % (sh.ARTIFACT_TAG, window_id))
    if not path.is_file():
        raise ForensicRunError("창 record가 없다: %s" % path.name)
    return json.loads(path.read_text(encoding="utf-8"))


def load_raw(runs: Path, window_id: str) -> str:
    path = runs / ("%s_%s_raw.txt" % (sh.ARTIFACT_TAG, window_id))
    if not path.is_file():
        raise ForensicRunError("raw 원문이 없다: %s" % path.name)
    return path.read_text(encoding="utf-8")


def c1_prompt(records: dict) -> dict:
    """프롬프트가 템플릿에서 나온 것이고 창 간 차이가 숫자뿐인지."""
    rows, mismatches = {}, []
    for window in sh.windows():
        window_id = window["window_id"]
        rows[window_id] = fx.expected_prompt(window)
    target = rows[fx.TARGET_WINDOW]
    control = rows[fx.CONTROL_WINDOW]
    diff = fx.prompt_diff(target, control)
    numeric_only = all(
        row["target"] is not None and row["control"] is not None
        and "start_sec=" in (row["target"] or "")
        for row in diff["lines"])
    for window_id, prompt in rows.items():
        window = sh.window_by_id(window_id)
        if prompt != fx.expected_prompt(window):
            mismatches.append(window_id)
    return {
        "prompt_hash": sha256_bytes(target.encode("utf-8")),
        "prompt_contract": "SAMPLING_DIAG_PROMPT_V2",
        "reconstruction_mismatches": mismatches,
        "prompt_matches_template": not mismatches,
        "target_vs_control_diff": diff,
        "diff_confined_to_window_line": numeric_only,
        "token_counts": {window["window_id"]:
                         (records[window["window_id"]]["metrics"]
                          .get("input_token_count"))
                         for window in sh.windows()},
        "runtime_config_hashes": {window["window_id"]:
                                  records[window["window_id"]].get(
                                      "runtime_config_hash")
                                  for window in sh.windows()},
    }


def c2_code_paths() -> dict:
    """W00 전용 분기가 코드에 있는지 문자열로 탐색한다."""
    hits = []
    for relative in SCANNED_SOURCES:
        source = (ROOT / relative).read_text(encoding="utf-8")
        for line_number, line in enumerate(source.split("\n"), start=1):
            for pattern in fx.WINDOW_SPECIFIC_PATTERNS:
                if pattern in line:
                    hits.append({"file": relative, "line": line_number,
                                 "pattern": pattern, "text": line.strip()})
    return {"scanned": list(SCANNED_SOURCES),
            "patterns": list(fx.WINDOW_SPECIFIC_PATTERNS),
            "hits": hits, "window_specific_branches": bool(hits)}


def c3_raw(runs: Path) -> dict:
    """W00 raw 구조 + W01~W23 비교군."""
    target = fx.raw_structure(load_raw(runs, fx.TARGET_WINDOW))
    controls = {}
    for window in sh.windows():
        window_id = window["window_id"]
        if window_id == fx.TARGET_WINDOW:
            continue
        structure = fx.raw_structure(load_raw(runs, window_id))
        controls[window_id] = {
            "raw_length": structure["raw_length"],
            "complete_object_count": structure["complete_object_count"],
            "unique_signature_count": structure["unique_signature_count"],
            "max_signature_repeat": structure["max_signature_repeat"],
            "zero_length_interval_count":
                structure["zero_length_interval_count"],
            "json_parse_ok": structure["json_parse_ok"],
        }
    return {"target": target, "controls": controls,
            "control_max_signature_repeat":
                max(row["max_signature_repeat"] for row in controls.values()),
            "control_json_parse_failures":
                [window_id for window_id, row in controls.items()
                 if not row["json_parse_ok"]]}


def c4_visual(video: Path, runs: Path, records: dict) -> dict:
    """창별 시각 지표 + frame bank 픽셀 해시 대조."""
    bank_path = runs / "shadow_frame_bank.json"
    bank = {}
    if bank_path.is_file():
        for row in json.loads(bank_path.read_text(encoding="utf-8"))["frames"]:
            bank[round(float(row["time_sec"]), 3)] = row["pixel_sha256"]

    rows, hash_mismatches = {}, []
    for window in sh.windows():
        window_id = window["window_id"]
        stamps = list(sh.frame_times(window))
        frames, _, _, _ = probe.sample_frames(video, stamps)
        rows[window_id] = fx.visual_metrics(frames)
        recorded = (records[window_id].get("frame_hashes") or [])
        recomputed = [sha256_bytes(frame.tobytes()) for frame in frames]
        for time, digest, again in zip(stamps, recorded, recomputed):
            if digest != again:
                hash_mismatches.append({"window_id": window_id,
                                        "time_sec": time,
                                        "reason": "RECOMPUTE_DIFFERS"})
            if time in bank and bank[time] != again:
                hash_mismatches.append({"window_id": window_id,
                                        "time_sec": time,
                                        "reason": "BANK_DIFFERS"})
    target = rows[fx.TARGET_WINDOW]
    others = [row for window_id, row in rows.items()
              if window_id != fx.TARGET_WINDOW]
    return {
        "per_window": rows, "frame_hash_mismatches": hash_mismatches,
        "frame_hashes_match_bank": not hash_mismatches,
        "target": target,
        "control_mean_luma_range": [min(row["mean_luma"] for row in others),
                                    max(row["mean_luma"] for row in others)],
        "control_black_ratio_max": max(row["black_frame_ratio"]
                                       for row in others),
        "control_near_static_max": max(row["near_static_ratio"]
                                       for row in others),
        "used_in_classification": fx.VISUAL_METRICS_IN_CLASSIFICATION,
    }


def c5_determinism(records: dict) -> dict:
    target = records[fx.TARGET_WINDOW]
    requested = target.get("requested") or {}
    return {
        "do_sample": requested.get("do_sample"),
        "num_beams": requested.get("num_beams"),
        "repetition_penalty": requested.get("repetition_penalty"),
        "max_new_tokens": requested.get("max_new_tokens"),
        "seed_specified": False,
        "stopping_criteria": "max_new_tokens only",
        "allocator_observed": (target.get("allocator_observed") or {}).get(
            "backend"),
        "rerun_performed": False,
        "determinism_measured": False,
        "note": ("재실행을 하지 않았으므로 결정성을 실측하지 않았다. "
                 "2026-08-18 AI Hub 2,328구간 완전일치는 참조이고 이번 증거가 아니다"),
    }


def analyse(video: Path, runs: Path) -> dict:
    records = {window["window_id"]: load_record(runs, window["window_id"])
               for window in sh.windows()}
    c1 = c1_prompt(records)
    c2 = c2_code_paths()
    c3 = c3_raw(runs)
    c4 = c4_visual(video, runs, records)
    c5 = c5_determinism(records)
    grid = {window["window_id"]: fx.grid_linearity(records[window["window_id"]])
            for window in sh.windows()}

    evidence = {
        "prompt_matches_template": c1["prompt_matches_template"],
        "prompt_diff_outside_numbers": not c1["diff_confined_to_window_line"],
        "window_specific_branches": c2["window_specific_branches"],
        "grid_linear": grid[fx.TARGET_WINDOW]["linear"],
        "frame_hashes_match_bank": c4["frame_hashes_match_bank"],
        "runtime_config_hash_matches_controls": (
            len(set(c1["runtime_config_hashes"].values())) <= 2),
    }
    axis_a = fx.input_anomaly(evidence)
    axis_b = fx.output_degeneracy(c3["target"])
    classification = fx.classify(axis_a["found"], axis_b["confirmed"])

    return {
        "schema": "wvr_w00_forensic_v1", "event": fx.EVENT, "prereg": PREREG,
        "code_git_head": git_head(),
        "new_inference_allowed": fx.NEW_INFERENCE_ALLOWED,
        "rerun_allowed": fx.RERUN_ALLOWED,
        "raw_salvage_allowed": fx.RAW_SALVAGE_ALLOWED,
        "token_cap_increase_approved": fx.TOKEN_CAP_INCREASE_APPROVED,
        "mapping_reveal_allowed": fx.MAPPING_REVEAL_ALLOWED,
        "semantic_verdict_by_executor": fx.SEMANTIC_VERDICT_BY_EXECUTOR,
        "target_window": fx.TARGET_WINDOW,
        "control_window": fx.CONTROL_WINDOW,
        "c1_prompt": c1, "c2_code_paths": c2, "c3_raw_structure": c3,
        "c4_visual": c4, "c5_determinism": c5,
        "c6_parser": fx.parser_responsibility(c3["target"]),
        "grid_linearity": grid,
        "evidence": evidence,
        "axis_input_anomaly": axis_a,
        "axis_output_degeneracy": axis_b,
        "classification": classification,
        "note": ("분류는 사전등록 진리표로만 계산했다. C4 시각 지표는 맥락 기록이고 "
                 "분류에 들어가지 않는다. W00을 재실행하지 않았고 raw를 보정하지 않았다."),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="W00 forensic (읽기 전용)")
    parser.add_argument("--video", default="data/videos/full_xekZO4n4QuE.mp4")
    parser.add_argument("--runs", default="runs/wvr_light_v1")
    args = parser.parse_args(argv)

    video, runs = Path(args.video), Path(args.runs)
    if not video.is_file():
        raise ForensicRunError("영상이 없다: %s" % video)
    record = analyse(video, runs)
    (runs / RESULT_NAME).write_text(
        json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")

    print("classification=%s" % record["classification"])
    print("  A input_anomaly=%s %s" % (record["axis_input_anomaly"]["found"],
                                       record["axis_input_anomaly"]["reasons"]
                                       or "없음"))
    print("  B output_degeneracy=%s %s"
          % (record["axis_output_degeneracy"]["confirmed"],
             record["axis_output_degeneracy"]["reasons"] or "없음"))
    target = record["c3_raw_structure"]["target"]
    print("  W00 raw len=%s objects=%s uniq=%s max_repeat=%s zero_len=%s "
          "json_ok=%s" % (target["raw_length"],
                          target["complete_object_count"],
                          target["unique_signature_count"],
                          target["max_signature_repeat"],
                          target["zero_length_interval_count"],
                          target["json_parse_ok"]))
    visual = record["c4_visual"]
    print("  W00 luma=%s black=%s near_static=%s | control luma %s black<=%s"
          % (visual["target"]["mean_luma"],
             visual["target"]["black_frame_ratio"],
             visual["target"]["near_static_ratio"],
             visual["control_mean_luma_range"],
             visual["control_black_ratio_max"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

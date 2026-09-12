"""WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1 — 계측 집계 (v3-Q1~Q10).

사전등록 §6 측정 항목만 계산한다. **판정하지 않는다** — PASS/HOLD·production 채택은
reviewer 몫이고 여기서는 관측값만 `runs/rei_c01_beta_v3/measurements.json`에 적는다.

새 inference 없음. 이미 생성된 artifact만 읽는다.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EVENT = "WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1"
PREREG = ("docs/preregistration/"
          "WVR_REPORT_ENGINE_C01_BETA_V3_SHADOW_V1_2026-09-12.md")

CELL = ROOT / "runs" / "rei_c01_beta_v3" / "b_beta_v3"
B2 = CELL / "b2run"
STAGES = ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7"]
MD_SECTIONS = ["## 개요", "## 주요 사건 및 내용", "## 핵심 내용 분석",
               "## 결론", "## 근거 및 생성 정보"]
NO_CONTENT = "NO_RELIABLE_CONTENT"


def jload(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def highlight_overlap_sec(highlights: list[dict]) -> float:
    """인접 highlight 간 겹침 총합(초). v2 OVERLAP cell에서는 24초였다."""
    rows = sorted(highlights, key=lambda h: h["start_sec"])
    return round(sum(max(0.0, a["end_sec"] - b["start_sec"])
                     for a, b in zip(rows, rows[1:])), 6)


def main() -> int:
    man = jload(B2 / "run_manifest.json")
    dist = man.get("distributions", {})
    segs = jload(CELL / "segments.json")["segments"]
    grounded = jload(B2 / "S4" / "grounded.json")["episodes"]
    pres = jload(B2 / "S6" / "presentation.json")
    md = B2 / "S7" / "report.md"
    md_text = md.read_text(encoding="utf-8") if md.exists() else ""

    cites = [c for e in grounded for c in (e.get("anchor_cites") or [])]
    known = {s["idx"] for s in segs}

    reason_codes: dict[str, int] = {}
    for e in grounded:
        for r in e.get("grounding_reasons") or []:
            reason_codes[r["code"]] = reason_codes.get(r["code"], 0) + 1

    excluded: dict[str, list[str]] = {}
    for h in pres.get("highlights", []):
        for ep in h.get("excluded_summary_episode_ids") or []:
            excluded.setdefault(h["highlight_id"], []).append(ep)

    hwpx = B2 / "S7" / "report.hwpx"
    hw: dict = {"generated": hwpx.exists()}
    if hwpx.exists():
        hw["bytes"] = hwpx.stat().st_size
        try:
            with zipfile.ZipFile(hwpx) as z:
                names = z.namelist()
                hw.update({"zip_open_ok": True, "entry_count": len(names),
                           "has_mimetype": "mimetype" in names,
                           "bad_entry": z.testzip()})
        except Exception as exc:                       # noqa: BLE001
            hw.update({"zip_open_ok": False, "error": str(exc)})

    out = {
        "event": EVENT,
        "prereg": PREREG,
        "status": "EXECUTED / REVIEW_PENDING",
        "note": ("관측값만 적는다. 보고서 품질 PASS · production 채택 · "
                 "C02~C05 실행 여부는 executor가 판단하지 않는다 (사전등록 §10)."),
        "execution_record": jload(CELL / "execution_record.json"),
        "new_visual_inference": 0,
        "new_stt": 0,
        "retry_count": 0,
        "input": {
            "view": "NONOVERLAP_VIEW",
            "segment_count": len(segs),
            "subtitle_populated": sum(1 for s in segs if s["subtitle"]),
            "caption_populated": sum(1 for s in segs if s["caption"]),
        },
        # v3-Q1
        "prompt_contract": {
            "prompt_version": man["fingerprint"].get("prompt_version"),
            "prompt_hash": man["fingerprint"].get("prompt_hash"),
            "model_id": man["fingerprint"].get("model_id"),
            "code_revision": man["fingerprint"].get("code_revision"),
        },
        # v3-Q2
        "canonical": {
            "expected_episodes": dist.get("expected_episodes"),
            "canonical_episodes": dist.get("canonical_episodes"),
            "counters": dist.get("counters"),
            "parse_status": dist.get("parse_status"),
            "content_status": dist.get("content_status"),
            "summary_mode": dist.get("summary_mode"),
            "stages_success": {s: (B2 / s / "_SUCCESS.json").exists()
                               for s in STAGES},
        },
        # v3-Q3
        "grounding": {
            "status_distribution": dist.get("grounding_status"),
            "reason_codes": reason_codes,
        },
        # v3-Q4
        "presentation": dict(dist.get("presentation") or {}),
        # v3-Q5
        "body": {
            "highlight_summary_status": [h.get("summary_status")
                                         for h in pres.get("highlights", [])],
            "excluded_summary_episode_ids": excluded,
            # 제외 사유는 renderer가 `EP10 (OUTPUT_LANGUAGE_DRIFT)` 형태로 적는다
            # (src/v2_1_render.py:87). 그 문자열에서 그대로 읽는다.
            "excluded_summary_reasons": dict(
                re.findall(r"(EP\d+)\s*\(([A-Z_]+)\)", md_text)),
            "synthesis_source_episode_ids":
                pres.get("synthesis", {}).get("source_episode_ids"),
            "no_reliable_content_count": md_text.count(NO_CONTENT),
            "report_md_bytes": len(md_text.encode("utf-8")),
        },
        # v3-Q6
        "hwpx": hw,
        # v3-Q7
        "section_completion": {sec: (sec in md_text) for sec in MD_SECTIONS},
        # v3-Q8
        "timestamps": {
            "highlights": [{"id": h["highlight_id"], "start_sec": h["start_sec"],
                            "end_sec": h["end_sec"]}
                           for h in pres.get("highlights", [])],
            "adjacent_overlap_sec": highlight_overlap_sec(
                pres.get("highlights", [])),
        },
        # v3-Q9
        "citations": {
            "anchor_cite_count": len(cites),
            "unique_anchor_cite_count": len(set(cites)),
            "citations_to_unknown_segment": sorted(set(cites) - known),
        },
        # v3-Q10 — §7 no silent fallback
        "fallback": {
            "prompt_refusals": (dist.get("counters") or {}).get("prompt_refusals"),
            "llm_failures": (dist.get("counters") or {}).get("llm_failures"),
            "retries": (dist.get("counters") or {}).get("retries"),
            "empty_report": md_text.count(NO_CONTENT) > 0,
            "stage_partial_success": [s for s in STAGES
                                      if not (B2 / s / "_SUCCESS.json").exists()],
        },
        # 대조 (read-only, 판단 없이 병기)
        "reference_baselines": {
            "runs/v3_paired/r1_v3": {"eligible": 39, "episodes": 41,
                                     "grounding": "NOT_APPLICABLE 41"},
            "runs/v3_paired/r0_v2": {"eligible": 2, "episodes": 41},
            "runs/rei_c01/b_beta (v2)": {"eligible": 0, "episodes": 10},
            "주의": "입력 격자와 규모가 다르다 — 차이를 단일 원인으로 귀속하지 않는다.",
        },
    }

    path = ROOT / "runs" / "rei_c01_beta_v3" / "measurements.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8")
    print("wrote", path)
    print("prompt_version:", out["prompt_contract"]["prompt_version"])
    print("eligible:", out["presentation"].get("eligible"),
          "/", out["presentation"].get("episodes"))
    print("NO_RELIABLE_CONTENT:", out["body"]["no_reliable_content_count"])
    print("hwpx:", out["hwpx"].get("generated"), out["hwpx"].get("zip_open_ok"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

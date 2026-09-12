"""WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1 — 2×2 계측 집계.

사전등록 §9 측정 항목만 계산한다. **판정하지 않는다** — PASS/HOLD/우열은
reviewer 몫이고 여기서는 관측값만 `runs/rei_c01/integration_matrix.json`에 적는다.

새 inference 없음. 이미 생성된 artifact만 읽는다.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import rei_c01_adapter as ad  # noqa: E402

RUNS = ROOT / "runs" / "rei_c01"
CELLS = {
    "a_alpha": ("alpha", ad.OVERLAP_VIEW),
    "b_alpha": ("alpha", ad.NONOVERLAP_VIEW),
    "a_beta": ("beta", ad.OVERLAP_VIEW),
    "b_beta": ("beta", ad.NONOVERLAP_VIEW),
}
BETA_STAGES = ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7"]
MD_SECTIONS = ["## 개요", "## 주요 사건 및 내용", "## 핵심 내용 분석",
               "## 결론", "## 근거 및 생성 정보"]


def jload(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def cite_time_ranges(cites, segments):
    """인용 segment idx를 시간 구간으로 되돌린다. 없는 idx는 따로 센다."""
    by_idx = {s["idx"]: s for s in segments}
    spans, unknown = [], []
    for c in sorted(set(cites)):
        if c in by_idx:
            spans.append([by_idx[c]["start"], by_idx[c]["end"]])
        else:
            unknown.append(c)
    return spans, unknown


def measure_common(cell: str, view: str) -> dict:
    segs = jload(RUNS / cell / "segments.json")["segments"]
    return {
        "view": view,
        "segment_count": len(segs),
        "temporal_coverage_sec": ad.temporal_coverage_sec(segs),
        "duplicate_temporal_coverage_sec": ad.duplicate_coverage_sec(segs),
        "subtitle_populated": sum(1 for s in segs if s["subtitle"]),
        "caption_populated": sum(1 for s in segs
                                 if s["caption"] and s["caption"] != ad.EMPTY_CAPTION),
    }


def measure_alpha(cell: str) -> dict:
    rp = RUNS / cell / "report.json"
    if not rp.exists():
        return {"report_json_present": False}
    rep = jload(rp)
    segs = jload(RUNS / cell / "segments.json")["segments"]
    cites = [c for s in rep["sentences"] for c in s.get("cites", [])]
    spans, unknown = cite_time_ranges(cites, segs)
    prov = rep.get("provenance", {})
    return {
        "report_json_present": True,
        "schema_version": rep.get("schema_version"),
        "sentence_count": len(rep["sentences"]),
        "sentences_without_cite": sum(1 for s in rep["sentences"]
                                      if not s.get("cites")),
        "citation_count": len(cites),
        "unique_citation_count": len(set(cites)),
        "citation_time_ranges": spans,
        "citations_to_unknown_segment": unknown,
        "map_chunk_size": rep.get("map_chunk_size"),
        "map_chunk_count": len(rep.get("map_raw_outputs") or []),
        # m8_report.generate_report: len(segments) <= chunk_size 면 단일 호출 경로다.
        # map/reduce 분할은 이 입력 크기에서 애초에 실행되지 않는다.
        "generation_path": ("SINGLE_CALL"
                            if len(rep.get("map_raw_outputs") or []) == 0
                            else "MAP_REDUCE"),
        # §10 fallback 계측 — 숨기지 않는다
        "map_retries": rep.get("map_retries"),
        "reduce_retry": rep.get("reduce_retry"),
        "degenerate_dropped": rep.get("degenerate_dropped"),
        "truncated_tail": rep.get("truncated_tail"),
        "model_loaded": prov.get("model_loaded"),
        "effective_model_id": prov.get("effective_model_id"),
        "effective_model_revision": prov.get("effective_model_revision"),
        "requested_4bit": prov.get("requested_4bit"),
    }


def measure_beta(cell: str) -> dict:
    b2 = RUNS / cell / "b2run"
    if not (b2 / "run_manifest.json").exists():
        return {"run_manifest_present": False}
    man = jload(b2 / "run_manifest.json")
    dist = man.get("distributions", {})
    segs = jload(RUNS / cell / "segments.json")["segments"]

    grounded = jload(b2 / "S4" / "grounded.json")["episodes"]
    cites = [c for e in grounded for c in (e.get("anchor_cites") or [])]
    spans, unknown = cite_time_ranges(cites, segs)
    reason_codes: dict[str, int] = {}
    for e in grounded:
        for r in e.get("grounding_reasons") or []:
            reason_codes[r["code"]] = reason_codes.get(r["code"], 0) + 1

    pres = jload(b2 / "S6" / "presentation.json")
    hwpx = b2 / "S7" / "report.hwpx"
    md = b2 / "S7" / "report.md"
    md_text = md.read_text(encoding="utf-8") if md.exists() else ""

    hw = {"generated": hwpx.exists()}
    if hwpx.exists():
        hw["bytes"] = hwpx.stat().st_size
        try:
            with zipfile.ZipFile(hwpx) as z:
                names = z.namelist()
                hw["zip_open_ok"] = True
                hw["entry_count"] = len(names)
                hw["has_mimetype"] = "mimetype" in names
                hw["bad_entry"] = z.testzip()
        except Exception as exc:                       # noqa: BLE001
            hw["zip_open_ok"] = False
            hw["error"] = str(exc)

    return {
        "run_manifest_present": True,
        "prompt_version": man["fingerprint"].get("prompt_version"),
        "model_id": man["fingerprint"].get("model_id"),
        "code_revision": man["fingerprint"].get("code_revision"),
        "stages_success": {s: (b2 / s / "_SUCCESS.json").exists()
                           for s in BETA_STAGES},
        "expected_episodes": dist.get("expected_episodes"),
        "canonical_episodes": dist.get("canonical_episodes"),
        "counters": dist.get("counters"),
        "parse_status": dist.get("parse_status"),
        "content_status": dist.get("content_status"),
        "grounding_status": dist.get("grounding_status"),
        "grounding_reason_codes": reason_codes,
        "summary_mode": dist.get("summary_mode"),
        "presentation": {k: v for k, v in (dist.get("presentation") or {}).items()},
        "citation_count": len(cites),
        "unique_citation_count": len(set(cites)),
        "citation_time_ranges": spans,
        "citations_to_unknown_segment": unknown,
        "highlights": [{"id": h["highlight_id"], "start_sec": h["start_sec"],
                        "end_sec": h["end_sec"],
                        "summary_status": h.get("summary_status")}
                       for h in pres.get("highlights", [])],
        "synthesis_source_episode_ids": pres.get("synthesis", {})
                                            .get("source_episode_ids"),
        "section_completion": {sec: (sec in md_text) for sec in MD_SECTIONS},
        "no_reliable_content_count": md_text.count("NO_RELIABLE_CONTENT"),
        "hwpx": hw,
    }


def main() -> int:
    matrix = {}
    for cell, (engine, view) in CELLS.items():
        rec_path = RUNS / cell / "execution_record.json"
        row = {"engine": engine,
               "execution_record": jload(rec_path) if rec_path.exists() else None,
               "common": measure_common(cell, view)}
        row["engine_measurements"] = (measure_alpha(cell) if engine == "alpha"
                                      else measure_beta(cell))
        matrix[cell] = row

    out = {
        "event": ad.EVENT,
        "prereg": ad.PREREG,
        "status": "EXECUTED / REVIEW_PENDING",
        "note": ("관측값만 적는다. engine 우열·production 채택·품질 PASS는 "
                 "executor가 판단하지 않는다 (사전등록 §13)."),
        "new_visual_inference": 0,
        "retry_count": 0,
        "matrix": matrix,
    }
    (RUNS / "integration_matrix.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")
    print("wrote", RUNS / "integration_matrix.json")
    for cell in CELLS:
        m = matrix[cell]
        print(cell, m["engine"], "exit",
              (m["execution_record"] or {}).get("exit_code"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

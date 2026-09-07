"""Tier 2 paired 비교 — S0(control) vs S1(shadow_vad0).

사전등록: `docs/preregistration/STT_VAD_ONLY_SHADOW_V1_2026-09-07.md`

```
hard gate   partition 동일 · 입력 동일 · 계약/모델 동일
            zero-overlap STT가 S1 근거에 0건
            LLM 호출 수 · 신규 PromptError · 구조 실패
            presentation eligible  S1 >= S0
            parse contract failure S1 <= S0
```

`removed-ASR-only lexical carryover`는 **환각 판정이 아니라 evidence-dependence
proxy**다. 사람이 문장을 고르지 않는다 — 제거된 ASR에만 있고 남은 근거에는 없는
토큰이 요약에 나타나는지를 기계적으로 센다.

사용:
    python scripts/v2_1_vad0_compare.py --s0 runs/vad0_paired/s0_control \\
        --s1 runs/vad0_paired/s1_shadow \\
        --measurements runs/stt_sanitation_v1/full_xekZO4n4QuE/measurements.json \\
        --out runs/vad0_paired/paired_metrics.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_WS = re.compile(r"\s+")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _first(run: Path, *relatives: str) -> Path:
    for relative in relatives:
        if (run / relative).is_file():
            return run / relative
    raise SystemExit("%s: %r 를 찾지 못했다" % (run, relatives))


def arm(run: Path) -> dict:
    manifest = _read(run / "run_manifest.json")
    document = _read(_first(run, "S5/aar_canonical.json", "aar_canonical.json"))
    index = _read(_first(run, "S2/raw_index.json", "raw_index.json"))
    ingest = _read(_first(run, "S0/ingest.json", "ingest.json"))
    episodes_meta = _read(_first(run, "S1/episodes.json", "episodes.json"))
    return {
        "run_dir": str(run),
        "fingerprint": manifest["fingerprint"],
        "evidence_policy": manifest.get("evidence_policy", {}),
        "distributions": manifest["distributions"],
        "counters": index.get("counters", {}),
        "spans": episodes_meta["spans"],
        "prompt": document["prompt"],
        "source_segments_sha256": ingest["source_segments_sha256"],
        "episodes": {e["episode_id"]: e for e in document["episodes"]},
        "raw_rows": {row["episode_id"]: row for row in index["episodes"]},
        "channels": {source: {int(k): v for k, v in channel.items()}
                     for source, channel in ingest["channels"].items()},
    }


def _tokens(text: str) -> set[str]:
    return {token for token in _WS.sub(" ", (text or "").strip()).split()
            if token}


def carryover(s0: dict, s1: dict, overlaps: dict) -> dict:
    """제거된 ASR에만 있는 토큰이 각 arm의 요약에 나타나는 수.

    정의는 셋뿐이다.
      1. S1에서 빠진 ASR(=overlap 0이며 원래 사용 가능했던 구간)의 토큰
      2. 그 episode의 **남은 근거**(캡션 등)에는 없는 토큰
      3. 그 토큰이 요약에 문자열로 나타나는가
    """
    rows, totals = [], {"s0": 0, "s1": 0, "episodes_with_removed_asr": 0}
    for episode_id, episode in s0["episodes"].items():
        start, end = episode["start_seg"], episode["end_seg"]
        removed, retained = set(), set()
        for segment_id in range(start, end + 1):
            asr = s0["channels"]["asr"].get(segment_id, "")
            vlm = s0["channels"]["vlm"].get(segment_id, "")
            retained |= _tokens(vlm)
            if asr.strip() and overlaps.get(segment_id, None) == 0:
                removed |= _tokens(asr)
            else:
                retained |= _tokens(asr)
        only_removed = {token for token in removed - retained if len(token) >= 2}
        if not only_removed:
            continue
        totals["episodes_with_removed_asr"] += 1
        left = (s0["episodes"][episode_id].get("summary") or "")
        right = (s1["episodes"].get(episode_id, {}).get("summary") or "")
        in_s0 = sorted(token for token in only_removed if token in left)
        in_s1 = sorted(token for token in only_removed if token in right)
        totals["s0"] += len(in_s0)
        totals["s1"] += len(in_s1)
        rows.append({"episode_id": episode_id,
                     "removed_only_tokens": len(only_removed),
                     "in_s0_summary": in_s0, "in_s1_summary": in_s1})
    return {"definition": "removed-ASR-only lexical carryover "
                          "(evidence-dependence proxy · 환각 판정 아님)",
            "totals": totals, "episodes": rows}


def episode_table(s0: dict, s1: dict) -> list[dict]:
    rows = []
    for episode_id, left in s0["episodes"].items():
        right = s1["episodes"].get(episode_id, {})
        left_raw = s0["raw_rows"].get(episode_id, {})
        right_raw = s1["raw_rows"].get(episode_id, {})
        left_summary = left.get("summary") or ""
        right_summary = right.get("summary") or ""
        rows.append({
            "episode_id": episode_id,
            "summary_same": left_summary == right_summary,
            "summary_len_s0": len(left_summary),
            "summary_len_s1": len(right_summary),
            "summary_len_delta": len(right_summary) - len(left_summary),
            "source_s0": left.get("source"),
            "source_s1": right.get("source"),
            "eligible_s0": left_raw.get("eligible_evidence_count"),
            "eligible_s1": right_raw.get("eligible_evidence_count"),
            "evidence_hash_same": (left_raw.get("eligible_evidence_hash")
                                   == right_raw.get("eligible_evidence_hash")),
            "prompt_hash_same": (left_raw.get("rendered_prompt_hash")
                                 == right_raw.get("rendered_prompt_hash")),
            "content_status_s0": left.get("content_status"),
            "content_status_s1": right.get("content_status"),
            "grounding_s0": left.get("grounding_status"),
            "grounding_s1": right.get("grounding_status"),
        })
    return rows


def gates(s0: dict, s1: dict, overlaps: dict, rows: list[dict]) -> dict:
    left = s0["distributions"]["presentation"]
    right = s1["distributions"]["presentation"]
    parse_s0 = s0["distributions"]["content_status"].get(
        "PARSE_CONTRACT_FAILURE", 0)
    parse_s1 = s1["distributions"]["content_status"].get(
        "PARSE_CONTRACT_FAILURE", 0)
    # zero-overlap STT가 S1 근거에 남아 있는지: 근거 수가 늘어난 episode가 있으면 위반
    grew = [row["episode_id"] for row in rows
            if (row["eligible_s1"] or 0) > (row["eligible_s0"] or 0)]
    return {
        "partition_equal": s0["spans"] == s1["spans"],
        "same_input": (s0["source_segments_sha256"]
                       == s1["source_segments_sha256"]),
        "same_contract": s0["prompt"] == s1["prompt"],
        "same_model": (s0["fingerprint"]["model_id"]
                       == s1["fingerprint"]["model_id"]),
        "policy_differs": (s0["fingerprint"]["evidence_policy"]
                           != s1["fingerprint"]["evidence_policy"]),
        "no_evidence_growth": not grew,
        "llm_calls_s0": s0["counters"].get("llm_calls"),
        "llm_calls_s1": s1["counters"].get("llm_calls"),
        "new_prompt_refusals": (s1["counters"].get("prompt_refusals", 0)
                                - s0["counters"].get("prompt_refusals", 0)),
        "llm_failures_s1": s1["counters"].get("llm_failures", 0),
        "presentation_eligible_s0": left["eligible"],
        "presentation_eligible_s1": right["eligible"],
        "presentation_non_regression": right["eligible"] >= left["eligible"],
        "parse_failure_s0": parse_s0,
        "parse_failure_s1": parse_s1,
        "parse_non_regression": parse_s1 <= parse_s0,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s0", required=True)
    parser.add_argument("--s1", required=True)
    parser.add_argument("--measurements", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    left, right = arm(Path(args.s0)), arm(Path(args.s1))
    measurements = _read(Path(args.measurements))
    overlaps = {row["segment_id"]: row["speech_overlap_ratio"]
                for row in measurements["segments"]}

    rows = episode_table(left, right)
    report = {
        "gates": gates(left, right, overlaps, rows),
        "summary_changed": sum(1 for row in rows if not row["summary_same"]),
        "summary_same": sum(1 for row in rows if row["summary_same"]),
        "evidence_changed": sum(1 for row in rows
                                if not row["evidence_hash_same"]),
        "prompt_changed": sum(1 for row in rows if not row["prompt_hash_same"]),
        "source_transition": _counts((row["source_s0"], row["source_s1"])
                                     for row in rows),
        "grounding_s0": left["distributions"]["grounding_status"],
        "grounding_s1": right["distributions"]["grounding_status"],
        "presentation_s0": left["distributions"]["presentation"],
        "presentation_s1": right["distributions"]["presentation"],
        "carryover": carryover(left, right, overlaps),
        "episodes": rows,
        "arms": {"s0": {k: left[k] for k in
                        ("run_dir", "fingerprint", "evidence_policy",
                         "counters", "prompt")},
                 "s1": {k: right[k] for k in
                        ("run_dir", "fingerprint", "evidence_policy",
                         "counters", "prompt")}},
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps({"gates": report["gates"],
                      "summary_changed": report["summary_changed"],
                      "carryover_totals": report["carryover"]["totals"]},
                     ensure_ascii=True, indent=1))
    return 0


def _counts(pairs) -> dict:
    result: dict[str, int] = {}
    for left, right in pairs:
        key = "%s->%s" % (left, right)
        result[key] = result.get(key, 0) + 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())

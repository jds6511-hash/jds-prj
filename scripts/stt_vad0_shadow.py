"""Tier 1 — VAD-only shadow abstention (LLM 없음 · 결정적 계층까지).

사전등록: `docs/preregistration/STT_VAD_ONLY_SHADOW_V1_2026-09-07.md`

```
SUSPECT_STT_VAD0 := existing status == VALID AND speech_overlap_ratio == 0
```

**production 판정을 바꾸지 않는다.** 원본 판정은 그대로 두고 counterfactual 결과를
새 객체로 만든다 — shadow 버그가 production evidence로 새는 경로를 만들지 않기
위해서다. 기본값은 off이며, 명시적으로 켤 때만 적용된다.

```
raw text · raw artifact · 원본 status   변경 0
바뀌는 것                                shadow 계산의 claim eligibility 하나뿐
판정 입력                                speech_overlap_ratio **하나뿐**
                                        gap·라틴·반복은 이 규칙에 들어가지 않는다
```

사용:
    python scripts/stt_vad0_shadow.py \\
        --segments work_full/full_xekZO4n4QuE/segments.json \\
        --measurements runs/stt_sanitation_v1/full_xekZO4n4QuE/measurements.json \\
        --out runs/stt_sanitation_v1/tier1_vad0 --window-sec 60 --shadow-vad0
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v2_1_episode import build_episodes                           # noqa: E402
from v2_1_fixed_window import FixedWindowV1                       # noqa: E402
from v2_1_prompt import split_evidence                            # noqa: E402
from v2_1_sanitation import SUSPECT, VALID, classify_channel      # noqa: E402
from v2_1_segments import legacy_segments_to_canonical            # noqa: E402
from v2_1_timeline import build_timeline                          # noqa: E402

#: 기본은 off. 켜야만 counterfactual이 계산된다.
SHADOW_VAD0_DEFAULT = False

SHADOW_REASON = "vad_zero_overlap"


@dataclass(frozen=True, slots=True)
class ShadowRow:
    """원본과 counterfactual을 **나란히** 들고 있는다. 덮어쓰지 않는다."""

    segment_id: int
    original_status: str
    original_usable_for_claims: bool
    shadow_status: str
    shadow_usable_for_claims: bool
    shadow_reason: str | None
    speech_overlap_ratio: float
    transitioned: bool


def shadow_rows(judged, overlaps) -> list[ShadowRow]:
    """규칙을 적용한 결과를 행으로 만든다. 입력 판정은 읽기만 한다."""
    rows = []
    for segment_id in sorted(judged):
        verdict = judged[segment_id]
        ratio = overlaps[segment_id]            # 없으면 KeyError — 0으로 넘기지 않는다
        abstain = verdict.status == VALID and ratio == 0
        rows.append(ShadowRow(
            segment_id=segment_id,
            original_status=verdict.status,
            original_usable_for_claims=bool(verdict.usable_for_claims),
            shadow_status=SUSPECT if abstain else verdict.status,
            shadow_usable_for_claims=(False if abstain
                                      else bool(verdict.usable_for_claims)),
            shadow_reason=SHADOW_REASON if abstain else None,
            speech_overlap_ratio=ratio,
            transitioned=abstain,
        ))
    return rows


def shadow_judgements(judged, overlaps) -> dict:
    """counterfactual 판정 사전. 원본과 **다른 객체**다."""
    result = {}
    for row in shadow_rows(judged, overlaps):
        verdict = judged[row.segment_id]
        result[row.segment_id] = dataclasses.replace(
            verdict,
            status=row.shadow_status,
            reason=row.shadow_reason if row.transitioned else verdict.reason,
            usable_for_claims=row.shadow_usable_for_claims,
        )
    return result


def evaluate(judged, overlaps, *, shadow_vad0: bool = SHADOW_VAD0_DEFAULT) -> dict:
    """flag가 off면 아무것도 바꾸지 않은 행을 돌려준다."""
    if not shadow_vad0:
        rows = []
        for segment_id in sorted(judged):
            verdict = judged[segment_id]
            usable = bool(verdict.usable_for_claims)
            rows.append(ShadowRow(
                segment_id=segment_id,
                original_status=verdict.status,
                original_usable_for_claims=usable,
                shadow_status=verdict.status,
                shadow_usable_for_claims=usable,
                shadow_reason=None,
                speech_overlap_ratio=overlaps[segment_id],
                transitioned=False))
    else:
        rows = shadow_rows(judged, overlaps)
    return {"rows": rows, "transitions": sum(1 for row in rows if row.transitioned)}


# ── episode 계층 ─────────────────────────────────────────────────────────
def _channels(legacy):
    segments = legacy_segments_to_canonical(legacy)
    asr, vlm = {}, {}
    for segment, row in zip(segments, legacy):
        asr[segment.segment_id] = row.get("subtitle") or ""
        vlm[segment.segment_id] = row.get("caption") or ""
    return segments, asr, vlm


def _spans(segments, window_sec):
    provider = FixedWindowV1()
    boundary = provider(segments, config={"window_sec": window_sec} if window_sec
                        else {})
    positions = list(boundary.boundary_positions) + [len(segments)]
    return [(positions[i], positions[i + 1] - 1)
            for i in range(len(positions) - 1)]


def _counts(episode, timeline):
    claim, _ = split_evidence(episode, timeline)
    by_source: dict[str, int] = {}
    for ref in claim:
        by_source[ref.source_type] = by_source.get(ref.source_type, 0) + 1
    return len(claim), by_source


def episode_counterfactual(legacy, overlaps, *, window_sec: float = 60.0) -> dict:
    """두 arm을 **같은 입력**으로 계산한다. 경계는 ASR과 무관해야 한다.

    LLM을 부르지 않는다. `eligible == 0`은 프롬프트가 거부될 구간이며(ERR-009),
    여기서는 그 전환을 결정적으로 센다.
    """
    segments, asr, vlm = _channels(legacy)
    control = {"asr": classify_channel(asr, "asr"),
               "vlm": classify_channel(vlm, "vlm")}
    shadowed = {"asr": shadow_judgements(control["asr"], overlaps),
                "vlm": control["vlm"]}

    spans = _spans(segments, window_sec)
    control_timeline = build_timeline(segments, control)
    shadow_timeline = build_timeline(segments, shadowed)
    control_episodes = build_episodes(list(spans), segments,
                                      timeline=control_timeline)
    shadow_episodes = build_episodes(list(spans), segments,
                                     timeline=shadow_timeline)

    rows = []
    for control_episode, shadow_episode in zip(control_episodes, shadow_episodes):
        original, original_by = _counts(control_episode, control_timeline)
        shadowed_count, shadow_by = _counts(shadow_episode, shadow_timeline)
        rows.append({
            "episode_id": control_episode.episode_id,
            "start_seg": control_episode.start_seg,
            "end_seg": control_episode.end_seg,
            "original_eligible": original,
            "shadow_eligible": shadowed_count,
            "original_asr_eligible": original_by.get("asr", 0),
            "shadow_asr_eligible": shadow_by.get("asr", 0),
            "lost_all_asr": (original_by.get("asr", 0) > 0
                             and shadow_by.get("asr", 0) == 0),
            "lost_all_evidence": original > 0 and shadowed_count == 0,
            "source_original": control_episode.source,
            "source_shadow": shadow_episode.source,
        })

    return {
        "spans": [list(span) for span in spans],
        "partition_equal": (
            [ (e.start_seg, e.end_seg) for e in control_episodes ]
            == [ (e.start_seg, e.end_seg) for e in shadow_episodes ]),
        "episodes": rows,
        "new_err_009": sum(1 for row in rows if row["lost_all_evidence"]),
        "episodes_losing_all_asr": sum(1 for row in rows if row["lost_all_asr"]),
    }


# ── 실행 ─────────────────────────────────────────────────────────────────
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_revision() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True)
    return out.stdout.strip() or "unknown"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segments", required=True, help="저장된 B1 segments.json")
    parser.add_argument("--measurements", required=True,
                        help="Phase A measurements.json (구간별 overlap)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--window-sec", type=float, default=60.0)
    parser.add_argument("--shadow-vad0", action="store_true",
                        help="counterfactual을 계산한다. 없으면 CONTROL만 본다")
    args = parser.parse_args(argv)

    segments_path = Path(args.segments)
    measurements_path = Path(args.measurements)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    document = json.loads(segments_path.read_text(encoding="utf-8"))
    legacy = document["segments"]
    measurements = json.loads(measurements_path.read_text(encoding="utf-8"))
    overlaps = {row["segment_id"]: row["speech_overlap_ratio"]
                for row in measurements["segments"]}

    segments, asr, _ = _channels(legacy)
    control = classify_channel(asr, "asr")
    result = evaluate(control, overlaps, shadow_vad0=args.shadow_vad0)
    rows = [dataclasses.asdict(row) for row in result["rows"]]

    episodes = (episode_counterfactual(legacy, overlaps,
                                       window_sec=args.window_sec)
                if args.shadow_vad0 else None)

    usable_before = sum(1 for row in result["rows"]
                        if row.original_usable_for_claims)
    usable_after = sum(1 for row in result["rows"]
                       if row.shadow_usable_for_claims)
    summary = {
        "track": "STT_VAD_ONLY_SHADOW_V1",
        "tier": 1,
        "shadow_vad0": bool(args.shadow_vad0),
        "rule": "existing VALID AND speech_overlap_ratio == 0 -> SUSPECT",
        "code_revision": code_revision(),
        "inputs": {
            "segments_sha256": sha256_file(segments_path),
            "measurements_sha256": sha256_file(measurements_path),
            "window_sec": args.window_sec,
        },
        "segments": {
            "n": len(rows),
            "usable_for_claims_before": usable_before,
            "usable_for_claims_after": usable_after,
            "valid_to_shadow_suspect": result["transitions"],
        },
        "episodes": None if episodes is None else {
            "n": len(episodes["episodes"]),
            "partition_equal": episodes["partition_equal"],
            "new_err_009": episodes["new_err_009"],
            "episodes_losing_all_asr": episodes["episodes_losing_all_asr"],
            "eligible_before": sum(row["original_eligible"]
                                   for row in episodes["episodes"]),
            "eligible_after": sum(row["shadow_eligible"]
                                  for row in episodes["episodes"]),
        },
        "not_done": ["summary 생성", "aar 재작성", "presentation 재생성",
                     "환각 제거율 계산", "사람 라벨링", "임계값 조정"],
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "segment_rows.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    if episodes is not None:
        (out / "episodes.json").write_text(
            json.dumps(episodes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

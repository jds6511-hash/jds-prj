"""Behavior contract for the direct video-to-Overview Preview."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import wvr_video_overview_preview_v1 as ov

ROOT = Path(__file__).resolve().parents[1]


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _module(ROOT / "scripts/wvr_video_overview_preview_run.py",
                 "video_overview_preview_runner")


SEGMENT_RAW = json.dumps({
    "segment_id": "SXX",
    "broad_activities": ["주요 작업이 이어진다."],
    "important_changes": [],
    "notable_context": ["실내 작업 공간"],
    "uncertain_or_ambiguous": [],
}, ensure_ascii=False)

OVERVIEW_RAW = """SHORT OVERVIEW

관찰 가능한 구간에서는 주요 준비 작업이 이어진다.
이후 다른 활동으로 흐름이 전환된다.
중후반에는 또 다른 종류의 작업이 진행된다.
마지막에는 장소와 활동 맥락이 바뀐다.

DETAILED OVERVIEW

관찰 가능한 앞부분에는 하나의 주요 작업이 지속된다. 이후에는 다른 활동으로 자연스럽게 전환된다.

중후반에는 앞선 작업과 구분되는 활동이 이어진다. 후반에는 장소와 활동 맥락이 달라진다.
"""


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def observe(self, video, segment, prompt):
        self.calls.append(("segment", segment["segment_id"]))
        payload = json.loads(SEGMENT_RAW)
        payload["segment_id"] = segment["segment_id"]
        return json.dumps(payload, ensure_ascii=False)

    def synthesize(self, prompt):
        self.calls.append(("synthesis", None))
        return OVERVIEW_RAW

    def provenance(self):
        return {"effective_model_id": ov.MODEL_ID,
                "effective_model_revision": ov.MODEL_REVISION,
                "effective_dtype": "torch.bfloat16",
                "attn_implementation": "sdpa",
                "device_name": "NVIDIA GeForce RTX 4090"}

    def metrics(self):
        return {"peak_vram_allocated_mib": 100.0,
                "peak_vram_reserved_mib": 200.0,
                "segments": []}


def test_segment_plan_reuses_48_second_24_overlap_video_windows():
    rows = ov.segments()
    assert len(rows) == 24
    assert rows[0] == {
        "segment_id": "S01", "start_sec": 0.0, "end_sec": 48.0,
        "frame_times": [float(value) for value in range(0, 48, 2)]}
    assert rows[1]["start_sec"] == 24.0
    assert rows[-1]["start_sec"] == 552.0
    assert rows[-1]["end_sec"] == 600.0
    assert all(len(row["frame_times"]) == 24 for row in rows)


def test_segment_parser_keeps_only_broad_summary_schema():
    raw = SEGMENT_RAW.replace("SXX", "S01")
    parsed = ov.parse_segment(raw, "S01")
    assert parsed["broad_activities"] == ["주요 작업이 이어진다."]
    assert set(parsed) == {"segment_id", "broad_activities",
                           "important_changes", "notable_context",
                           "uncertain_or_ambiguous"}
    bad = json.loads(raw)
    bad["local_events"] = ["작은 행동"]
    with pytest.raises(ov.PreviewError, match="SEGMENT_SCHEMA"):
        ov.parse_segment(json.dumps(bad, ensure_ascii=False), "S01")


def test_synthesis_prompt_uses_summaries_not_event_map_or_track_a():
    summary = ov.parse_segment(SEGMENT_RAW.replace("SXX", "S01"), "S01")
    prompt = ov.synthesis_prompt([summary])
    assert "주요 작업이 이어진다" in prompt
    for forbidden in ("source_event_ids", "event map", "caption", "stt",
                      "actor", "object_or_state"):
        assert forbidden not in prompt.lower()


def test_overview_parser_accepts_three_to_five_sentences_and_two_to_three_paragraphs():
    parsed = ov.parse_overview(OVERVIEW_RAW)
    assert len(parsed["short_sentences"]) == 4
    assert len(parsed["detailed_paragraphs"]) == 2
    with pytest.raises(ov.PreviewError, match="SHORT_COUNT"):
        ov.parse_overview(OVERVIEW_RAW.replace(
            "이후 다른 활동으로 흐름이 전환된다.\n", "").replace(
            "중후반에는 또 다른 종류의 작업이 진행된다.\n", ""))


def test_run_persists_24_segment_raws_then_synthesizes_once(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"frozen-video-fixture")
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    monkeypatch.setattr(ov, "VIDEO_SHA256", digest)
    monkeypatch.setattr(runner.ov, "VIDEO_SHA256", digest)
    runs = tmp_path / "runs"
    runtime = FakeRuntime()

    result = runner.run(video, runs, runtime_factory=lambda: runtime)

    assert runtime.calls == [
        ("segment", "S%02d" % index) for index in range(1, 25)
    ] + [("synthesis", None)]
    assert result["status"] == "GENERATED / REVIEW_REQUESTED"
    assert len(list(runs.glob("video_overview_v1_segment_S*_raw.txt"))) == 24
    assert (runs / ov.OVERVIEW_RAW_NAME).read_text(encoding="utf-8") == OVERVIEW_RAW
    assert (runs / ov.RECORD_NAME).is_file()
    record = json.loads((runs / ov.RECORD_NAME).read_text(encoding="utf-8"))
    assert record["inference_count"] == 25
    assert record["segment_inference_count"] == 24
    assert record["synthesis_inference_count"] == 1
    assert record["retry_count"] == 0
    assert record["track_a_used"] is False
    packet = (runs / ov.PACKET_NAME).read_text(encoding="utf-8")
    assert packet.startswith("WVR_VIDEO_TO_OVERVIEW_PREVIEW_V1\n\nSHORT OVERVIEW")
    assert packet.index("DETAILED OVERVIEW") < packet.index("BROAD SEGMENT SUMMARIES")
    with pytest.raises(runner.RunError, match="already exists"):
        runner.run(video, runs, runtime_factory=lambda: FakeRuntime())

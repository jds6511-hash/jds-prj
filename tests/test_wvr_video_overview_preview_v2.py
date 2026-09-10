"""Quality-path contract for WVR_VIDEO_TO_OVERVIEW_PREVIEW_V2."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import wvr_video_overview_preview_v2 as ov

ROOT = Path(__file__).resolve().parents[1]


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _module(ROOT / "scripts/wvr_video_overview_preview_v2_run.py",
                 "video_overview_preview_v2_runner")


OVERVIEW_RAW = """SHORT OVERVIEW

영상에서는 음식 준비와 식사에 이어 의류 작업이 진행된다. 후반에는 외출 준비와 포장 작업으로 흐름이 바뀐다.

DETAILED OVERVIEW

관찰 가능한 앞부분에는 음식 준비와 조리가 이어지고 이후 식사로 전환된다. 중후반에는 의류를 정리하고 수선하는 활동이 진행된다. 후반에는 외출을 준비하고 물건을 포장하는 활동으로 이어진다.
"""


def summary(segment_id, activities, changes=None, context=None, uncertainty=None):
    return {
        "segment_id": segment_id,
        "BROAD_ACTIVITY": activities,
        "OBSERVED_CHANGE": changes or [],
        "CONTEXT_INFERENCE": context or [],
        "UNCERTAINTY": uncertainty or [],
    }


def segment_raw(activities, changes=None, context=None, uncertainty=None):
    return json.dumps({
        "BROAD_ACTIVITY": activities,
        "OBSERVED_CHANGE": changes or [],
        "CONTEXT_INFERENCE": context or [],
        "UNCERTAINTY": uncertainty or [],
    }, ensure_ascii=False)


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def observe(self, video, segment, prompt):
        self.calls.append(("segment", segment["segment_id"]))
        index = int(segment["segment_id"][1:])
        if index <= 10:
            activities = ["음식 준비 및 조리"]
        elif index <= 12:
            activities = ["식사"]
        elif index <= 16:
            activities = ["이동"]
        elif index <= 19:
            activities = ["의류 작업 및 수선"]
        elif index <= 21:
            activities = ["외출 준비"]
        else:
            activities = ["포장 작업"]
        context = ["병원 퇴원 상황으로 추정"] if index == 12 else []
        uncertainty = ["장소가 명확하지 않음"] if index == 13 else []
        return segment_raw(activities, context=context,
                           uncertainty=uncertainty)

    def synthesize(self, prompt):
        self.calls.append(("synthesis", prompt))
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
                "segments": [], "synthesis": {}}


def test_v2_reuses_frozen_video_model_and_24_segment_geometry():
    rows = ov.segments()
    assert ov.MODEL_ID == "Qwen/Qwen3-VL-8B-Instruct"
    assert ov.MODEL_REVISION == "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"
    assert len(rows) == 24
    assert (rows[0]["start_sec"], rows[0]["end_sec"]) == (0.0, 48.0)
    assert rows[1]["start_sec"] == 24.0
    assert rows[-1]["end_sec"] == 600.0
    assert all(len(row["frame_times"]) == 24 for row in rows)


def test_segment_output_accepts_only_canonical_broad_labels():
    raw = segment_raw(
        ["음식 준비 및 조리", "식사"],
        ["음식 준비 및 조리 → 식사"],
        ["외부 일정으로 보임"], ["장소가 불명확함"])
    parsed = ov.parse_segment(raw, "S01")
    assert parsed["BROAD_ACTIVITY"] == ["음식 준비 및 조리", "식사"]
    assert set(parsed) == {"segment_id", "BROAD_ACTIVITY", "OBSERVED_CHANGE",
                           "CONTEXT_INFERENCE", "UNCERTAINTY"}
    bad = segment_raw(["감자 크림 커리 우동 만들기"])
    with pytest.raises(ov.PreviewError, match="BROAD_ACTIVITY"):
        ov.parse_segment(bad, "S01")


def test_segment_can_preserve_three_distinct_broad_activities():
    raw = segment_raw([
        "식사", "음식 준비 및 조리", "구매 또는 둘러보기"])
    parsed = ov.parse_segment(raw, "S14")
    assert parsed["BROAD_ACTIVITY"] == [
        "식사", "음식 준비 및 조리", "구매 또는 둘러보기"]


def test_temporal_compression_merges_overlap_repetition_and_keeps_changes():
    rows = [
        summary("S01", ["음식 준비 및 조리"]),
        summary("S02", ["음식 준비 및 조리"]),
        summary("S03", ["음식 준비 및 조리", "식사"],
                ["음식 준비 및 조리 → 식사"]),
        summary("S04", ["음식 준비 및 조리", "식사"]),
        summary("S05", ["식사"]),
        summary("S06", ["의류 작업 및 수선"]),
        summary("S07", ["의류 작업 및 수선"]),
    ]
    compressed = ov.compress_activity_timeline(rows)
    assert [(row["broad_activity"], row["first_segment"], row["last_segment"])
            for row in compressed["activity_runs"]] == [
        ("음식 준비 및 조리", "S01", "S04"),
        ("식사", "S03", "S05"),
        ("의류 작업 및 수선", "S06", "S07"),
    ]
    assert compressed["observed_changes"] == [
        "음식 준비 및 조리 → 식사"]


def test_synthesis_input_excludes_context_uncertainty_and_segment_identity():
    rows = [summary(
        "S01", ["이동"], context=["병원 퇴원 상황으로 추정"],
        uncertainty=["시장인지 확실하지 않음"])]
    compressed = ov.compress_activity_timeline(rows)
    prompt = ov.synthesis_prompt(compressed)
    assert "이동" in prompt
    for forbidden in ("병원", "퇴원", "시장인지", "CONTEXT_INFERENCE",
                      "UNCERTAINTY", "S01", "first_segment", "last_segment",
                      "event map", "caption", "stt"):
        assert forbidden.lower() not in prompt.lower()


def test_overview_parser_does_not_reject_two_sentences_or_one_paragraph():
    parsed = ov.parse_overview(OVERVIEW_RAW)
    assert parsed["short_overview"].count(".") == 2
    assert len(parsed["detailed_paragraphs"]) == 1


def test_run_generates_24_segments_compresses_then_synthesizes_once(
        tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"frozen-video-fixture-v2")
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    monkeypatch.setattr(ov, "VIDEO_SHA256", digest)
    monkeypatch.setattr(runner.ov, "VIDEO_SHA256", digest)
    runs = tmp_path / "runs"
    runtime = FakeRuntime()

    result = runner.run(video, runs, runtime_factory=lambda: runtime)

    assert [row[:2] for row in runtime.calls[:24]] == [
        ("segment", "S%02d" % index) for index in range(1, 25)]
    assert runtime.calls[-1][0] == "synthesis"
    synth_prompt = runtime.calls[-1][1]
    assert "병원 퇴원" not in synth_prompt
    assert "장소가 명확하지 않음" not in synth_prompt
    assert result["status"] == "GENERATED / REVIEW_REQUESTED"
    assert len(result["compressed_timeline"]["activity_runs"]) == 6
    assert len(list(runs.glob("video_overview_v2_segment_S*_raw.txt"))) == 24
    record = json.loads((runs / ov.RECORD_NAME).read_text(encoding="utf-8"))
    assert record["segment_inference_count"] == 24
    assert record["synthesis_inference_count"] == 1
    assert record["inference_count"] == 25
    assert record["retry_count"] == 0
    assert record["track_a_used"] is False
    assert record["event_map_used"] is False
    packet = (runs / ov.PACKET_NAME).read_text(encoding="utf-8")
    assert packet.index("SHORT OVERVIEW") < packet.index("DETAILED OVERVIEW")
    assert packet.index("DETAILED OVERVIEW") < packet.index(
        "COMPRESSED ACTIVITY TIMELINE")
    assert "CONTEXT INFERENCES EXCLUDED FROM OVERVIEW" in packet
    assert "UNCERTAINTIES" in packet


def test_resume_reuses_persisted_raw_without_retrying_completed_segments(
        tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"frozen-video-resume-fixture-v2")
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    monkeypatch.setattr(ov, "VIDEO_SHA256", digest)
    monkeypatch.setattr(runner.ov, "VIDEO_SHA256", digest)
    runs = tmp_path / "runs"

    class StopsAfterTwo(FakeRuntime):
        def observe(self, video, segment, prompt):
            if segment["segment_id"] == "S03":
                raise RuntimeError("simulated process interruption")
            return super().observe(video, segment, prompt)

    with pytest.raises(RuntimeError, match="simulated process interruption"):
        runner.run(video, runs, runtime_factory=StopsAfterTwo)
    assert len(list(runs.glob("video_overview_v2_segment_S*_raw.txt"))) == 2

    resumed = FakeRuntime()
    result = runner.run(video, runs, runtime_factory=lambda: resumed,
                        resume=True)
    assert resumed.calls[0] == ("segment", "S03")
    assert resumed.calls[-1][0] == "synthesis"
    assert result["status"] == "GENERATED / REVIEW_REQUESTED"
    record = json.loads((runs / ov.RECORD_NAME).read_text(encoding="utf-8"))
    assert record["inference_count"] == 25
    assert record["retry_count"] == 0
    assert record["resumed_existing_segment_raw_count"] == 2

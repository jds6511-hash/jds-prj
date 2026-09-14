"""Tutor-facing public API and repository navigation contract."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_scene_search_public_api_exposes_entrypoints():
    from jds_video import scene_search

    assert callable(scene_search.search)
    assert callable(scene_search.search_with_stats)
    assert callable(scene_search.create_app)
    assert scene_search.VideoIndex.__name__ == "VideoIndex"


def test_whole_video_report_public_api_exposes_entrypoints():
    from jds_video import whole_video_report

    assert whole_video_report.MODEL_ID == "Qwen/Qwen3-VL-8B-Instruct"
    assert callable(whole_video_report.analysis_prompt)
    assert callable(whole_video_report.conclusion_prompt)
    assert callable(whole_video_report.machine_checks)
    assert callable(whole_video_report.final_report_markdown)


def test_src_root_contains_only_the_public_package():
    names = sorted(path.name for path in (ROOT / "src").iterdir()
                   if path.name != "__pycache__")
    assert names == ["jds_video"]


def test_start_here_points_to_both_public_pipelines():
    text = (ROOT / "START_HERE.md").read_text(encoding="utf-8")
    assert "src/jds_video/scene_search.py" in text
    assert "src/jds_video/whole_video_report.py" in text

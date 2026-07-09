"""M3 CLI(main) 테스트 — --captions-only [DESIGN_SPEC 8-5(3)]. GPU 로딩 금지:
load_vlm·caption_frame은 스텁으로 대체하고 transcribe는 호출 자체가 없음을 스파이로 검증."""
import json
import sys
import pytest
import common
import m3_generate


def _seed_work_dir(tmp_path, video_id="v1", filled=True):
    wdir = tmp_path / "work" / video_id
    wdir.mkdir(parents=True)
    segs = [{"idx": i, "start": i * 5, "end": i * 5 + 5,
            "rep_frame": f"frames/seg_{i:04d}.jpg", "is_static": False,
            "motion_score": 0.1, "subtitle": "자막", "caption": "이전 캡션"}
           for i in range(2)]
    if not filled:
        for s in segs:
            del s["subtitle"]
    common.save_segments(wdir / "segments.json", {"n_segments": 2, "segments": segs})
    return wdir


def _cfg(tmp_path):
    return {"paths": {"work": str(tmp_path / "work")},
            "stt_model": "large-v3", "stt_language": "ko",
            "caption_model": "m", "caption_prompt": "p",
            "vlm_max_pixels": 1, "vlm_4bit": False}


def test_captions_only_regenerates_caption_keeps_subtitle_never_transcribes(
        tmp_path, monkeypatch):
    video_id = "v1"
    wdir = _seed_work_dir(tmp_path, video_id, filled=True)
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(common, "load_config", lambda path: cfg)
    monkeypatch.setattr(m3_generate, "load_vlm", lambda cfg: (None, None))
    monkeypatch.setattr(m3_generate, "caption_frame",
                        lambda p, prompt, model, processor, cfg: "새 캡션")

    def _no_transcribe(*a, **kw):
        raise AssertionError("--captions-only는 transcribe를 호출하면 안 됨 [8-5(3)]")
    monkeypatch.setattr(m3_generate, "transcribe", _no_transcribe)
    monkeypatch.setattr(sys, "argv", ["m3_generate.py", "--config", "c.yaml",
                                      "--video-id", video_id, "--captions-only"])

    m3_generate.main()

    doc = json.loads((wdir / "segments.json").read_text(encoding="utf-8"))
    assert all(s["caption"] == "새 캡션" for s in doc["segments"])     # 재생성됨
    assert all(s["subtitle"] == "자막" for s in doc["segments"])       # 불변
    assert all(s["is_static"] is False for s in doc["segments"])       # 불변
    assert all(s["motion_score"] == 0.1 for s in doc["segments"])      # 불변


def test_captions_only_fails_fast_when_subtitle_missing(tmp_path, monkeypatch):
    # segments.json에 subtitle·rep_frame이 채워져 있지 않으면 fail-fast +
    # seeding 안내 메시지 [8-5(3)①]
    video_id = "v1"
    _seed_work_dir(tmp_path, video_id, filled=False)
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(common, "load_config", lambda path: cfg)
    monkeypatch.setattr(sys, "argv", ["m3_generate.py", "--config", "c.yaml",
                                      "--video-id", video_id, "--captions-only"])
    with pytest.raises(SystemExit, match="seeding"):
        m3_generate.main()


def test_captions_only_and_force_mutually_exclusive(monkeypatch):
    # --force(전체 재실행)와 --captions-only는 상호 배타 [8-5(3)③]
    monkeypatch.setattr(sys, "argv", ["m3_generate.py", "--video-id", "v1",
                                      "--captions-only", "--force"])
    with pytest.raises(SystemExit):
        m3_generate.main()

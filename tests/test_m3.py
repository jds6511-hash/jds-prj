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
    return {"paths": {"work": str(tmp_path / "work")}, "seg_len_sec": 5,
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
                        lambda p, prompt, model, processor, cfg, sample=False: "새 캡션")

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


# ── --subtitles-only + 디코딩 파라미터 캐시 무효화 [8-5(7)] ─────────────────
# 근거: KconfSpeech CER 실측(2026-08-07)에서 빔 5보다 그리디가 유의하게 나았고
# Qwen3-ASR이 현행을 이겼다. 둘 다 검증하려면 **캡션은 그대로 두고 자막만** 다시
# 만들어야 한다 — 캡션 재생성은 환경이 바뀌면 인덱스를 열화시킨다(캡션 3차 실측,
# 완전일치 25.6%). --captions-only의 반대 방향 경로가 필요하다.

def test_subtitles_only_regenerates_subtitle_keeps_caption_never_loads_vlm(
        tmp_path, monkeypatch):
    video_id = "v1"
    wdir = _seed_work_dir(tmp_path, video_id, filled=True)
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(common, "load_config", lambda path: cfg)
    monkeypatch.setattr(m3_generate, "transcribe",
                        lambda *a, **kw: [{"text": "새 자막", "t0": 0.0, "t1": 9.0}])

    def _no_vlm(*a, **kw):
        raise AssertionError("--subtitles-only는 VLM을 로드하면 안 됨")
    monkeypatch.setattr(m3_generate, "load_vlm", _no_vlm)
    monkeypatch.setattr(sys, "argv", ["m3_generate.py", "--config", "c.yaml",
                                      "--video-id", video_id, "--subtitles-only"])

    m3_generate.main()

    doc = json.loads((wdir / "segments.json").read_text(encoding="utf-8"))
    assert all(s["subtitle"] == "새 자막" for s in doc["segments"])   # 재생성됨
    assert all(s["caption"] == "이전 캡션" for s in doc["segments"])  # 불변


def test_subtitles_only_fails_fast_when_caption_missing(tmp_path, monkeypatch):
    # 캡션이 없는 상태로 돌면 캡션 없는 인덱스가 만들어진다 — 먼저 막는다.
    video_id = "v1"
    wdir = _seed_work_dir(tmp_path, video_id, filled=True)
    doc = json.loads((wdir / "segments.json").read_text(encoding="utf-8"))
    for s in doc["segments"]:
        del s["caption"]
    common.save_segments(wdir / "segments.json", doc)
    monkeypatch.setattr(common, "load_config", lambda path: _cfg(tmp_path))
    monkeypatch.setattr(sys, "argv", ["m3_generate.py", "--config", "c.yaml",
                                      "--video-id", video_id, "--subtitles-only"])
    with pytest.raises(SystemExit, match="caption"):
        m3_generate.main()


@pytest.mark.parametrize("other", ["--captions-only", "--recaption-corrupted", "--force"])
def test_subtitles_only_mutually_exclusive(monkeypatch, other):
    monkeypatch.setattr(sys, "argv", ["m3_generate.py", "--video-id", "v1",
                                      "--subtitles-only", other])
    with pytest.raises(SystemExit):
        m3_generate.main()


def _fake_whisper(monkeypatch, calls, text="전사"):
    """faster_whisper를 가짜로 끼워넣는다. 호출 횟수를 calls에 기록."""
    import types

    class _Seg:
        def __init__(self):
            self.text, self.start, self.end = text, 0.0, 1.0

    class _Model:
        def __init__(self, name, device=None, compute_type=None):
            pass

        def transcribe(self, wav, **kw):
            calls.append(kw)
            return [_Seg()], None

    monkeypatch.setitem(sys.modules, "faster_whisper",
                        types.SimpleNamespace(WhisperModel=_Model))


def test_transcribe_cache_invalidated_when_beam_size_changes(tmp_path, monkeypatch):
    # 디코딩 파라미터가 캐시 키에 없으면 빔을 바꿔도 옛 전사가 조용히 재사용된다.
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"x" * 16)
    calls = []
    _fake_whisper(monkeypatch, calls)

    m3_generate.transcribe(wav, "large-v3", "ko", beam_size=5)
    assert len(calls) == 1
    m3_generate.transcribe(wav, "large-v3", "ko", beam_size=5)
    assert len(calls) == 1                      # 같은 설정 → 캐시 사용
    m3_generate.transcribe(wav, "large-v3", "ko", beam_size=1)
    assert len(calls) == 2                      # 빔이 바뀌면 재전사
    assert calls[-1]["beam_size"] == 1          # 실제로 전달됐는지


def test_transcribe_old_cache_without_decoding_keys_still_valid(tmp_path, monkeypatch):
    # 기존 stt_cache.json에는 beam_size 키가 없다. 기본값 설정에서 그 캐시가
    # 무효가 되면 확정 인덱스 7편이 전부 재전사된다 — 환경이 다르면 자막이
    # 달라질 수 있으므로 하위호환을 지킨다.
    import os
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"x" * 16)
    old = {"meta": {"model": "large-v3", "lang": "ko",
                    "mtime": os.path.getmtime(wav), "size": os.path.getsize(wav)},
           "utterances": [{"text": "옛 전사", "t0": 0.0, "t1": 1.0}]}
    common.atomic_write_json(tmp_path / "stt_cache.json", old)
    calls = []
    _fake_whisper(monkeypatch, calls)

    utts = m3_generate.transcribe(wav, "large-v3", "ko")
    assert calls == []                                  # 재전사 없음
    assert utts[0]["text"] == "옛 전사"

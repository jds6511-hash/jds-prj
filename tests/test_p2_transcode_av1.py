"""AV1 → H.264 변환. **구간 격자를 바꾸면 통과시키지 않는다.**

서버 cv2가 AV1을 디코드하지 못해 넣은 절차다(2026-08-21 실측). 변환이 허용되는 조건은
하나뿐이다 — 사전등록된 `n_segments`가 그대로일 때. 달라지면 표집틀 검증값과 어긋나므로
되돌리고 멈춘다.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_transcode_av1 as T                                      # noqa: E402


def test_settings_keep_audio_and_timing():
    assert "-c:a" in T.ACODEC and "copy" in T.ACODEC, "오디오를 재인코딩하면 자막이 바뀐다"
    assert T.SUFFIX == ".av1source.mp4"
    assert T.SEG_LEN == 5


def test_timing_flag_is_probed_not_guessed(monkeypatch):
    """서버 ffmpeg는 4.4.2라 `-fps_mode`를 모른다 — 버전 문자열로 추측하지 않는다."""
    class R:
        def __init__(self, rc):
            self.returncode = rc

    monkeypatch.setattr(T.subprocess, "run", lambda *a, **k: R(0))
    assert T.timing_flags() == T.TIMING_NEW
    monkeypatch.setattr(T.subprocess, "run", lambda *a, **k: R(1))
    assert T.timing_flags() == T.TIMING_OLD
    assert T.TIMING_OLD == ["-vsync", "0"]


def test_transcode_command_includes_a_timing_flag(tmp_path, monkeypatch):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"av1-bytes")
    _fake_av1(monkeypatch, tmp_path, segs_after=100)
    monkeypatch.setattr(T, "timing_flags", lambda: ["-vsync", "0"])
    row = T.transcode(f, 100)
    assert "-vsync 0" in row["ffmpeg_cmd"]


def test_non_av1_is_skipped(tmp_path, monkeypatch):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    monkeypatch.setattr(T, "probe_codec", lambda p: "h264")
    row = T.transcode(f, 100)
    assert row["status"] == "skipped_not_av1"
    assert f.read_bytes() == b"x"                # 손대지 않는다


def _fake_av1(monkeypatch, tmp_path, segs_after, readable=True):
    monkeypatch.setattr(T, "probe_codec",
                        lambda p: "av1" if str(p).endswith(".mp4")
                        and ".tmp" not in str(p) else "h264")
    monkeypatch.setattr(T, "cv2_segments",
                        lambda p: (500.0, 30.0, segs_after, readable))

    def fake_run(cmd, **kw):
        # timing_flags()의 능력 탐지도 이 fake를 타고 오는데 그 명령은 `-f null -`로
        # 끝난다 — 그때 파일을 만들면 **저장소 루트에 `-`가 생긴다**(실제로 생겼다).
        if str(cmd[-1]).endswith(".mp4"):
            Path(cmd[-1]).write_bytes(b"transcoded")

        class R:
            returncode = 0
        return R()
    monkeypatch.setattr(T.subprocess, "run", fake_run)


def test_segment_drift_is_reverted(tmp_path, monkeypatch):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"av1-bytes")
    _fake_av1(monkeypatch, tmp_path, segs_after=101)
    with pytest.raises(T.TranscodeError, match="n_segments"):
        T.transcode(f, 100)
    assert f.read_bytes() == b"av1-bytes"        # 원본 그대로
    assert not list(tmp_path.glob("*.tmp.mp4"))  # 임시 파일도 남기지 않는다
    assert not list(tmp_path.glob("*av1source*"))


def test_unreadable_result_is_reverted(tmp_path, monkeypatch):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"av1-bytes")
    _fake_av1(monkeypatch, tmp_path, segs_after=100, readable=False)
    with pytest.raises(T.TranscodeError, match="cv2가 못 읽는다"):
        T.transcode(f, 100)
    assert f.read_bytes() == b"av1-bytes"


def test_success_keeps_the_original_and_records_both_hashes(tmp_path, monkeypatch):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"av1-bytes")
    _fake_av1(monkeypatch, tmp_path, segs_after=100)
    row = T.transcode(f, 100)
    assert row["status"] == "transcoded"
    assert f.read_bytes() == b"transcoded"
    kept = tmp_path / "v.av1source.mp4"
    assert kept.read_bytes() == b"av1-bytes", "원본을 지우면 안 된다"
    assert row["sha256_before"] != row["sha256_after"]
    assert row["ffmpeg_cmd"].startswith("ffmpeg")


def test_double_transcode_is_refused(tmp_path, monkeypatch):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"av1-bytes")
    (tmp_path / "v.av1source.mp4").write_bytes(b"older")
    _fake_av1(monkeypatch, tmp_path, segs_after=100)
    with pytest.raises(T.TranscodeError, match="두 번 변환"):
        T.transcode(f, 100)

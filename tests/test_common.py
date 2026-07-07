import json, pytest
from pathlib import Path
import common

def _doc(n=3, dur=14.0, extra=None):
    segs = []
    for i in range(n):
        s = {"idx": i, "start": i * 5, "end": min(i * 5 + 5, dur)}
        if extra:
            s.update(extra)
        segs.append(s)
    return {"video_id": "v1", "duration_sec": dur, "fps": 30.0,
            "n_segments": n, "segments": segs}

def test_load_segments_ok(tmp_path):
    p = tmp_path / "segments.json"
    common.atomic_write_json(p, _doc())
    doc = common.load_segments(p)
    assert doc["n_segments"] == 3

def test_load_segments_rejects_broken_idx(tmp_path):
    d = _doc(); d["segments"][2]["idx"] = 5          # 연속성 위반
    p = tmp_path / "segments.json"; common.atomic_write_json(p, d)
    with pytest.raises(ValueError, match="idx"):
        common.load_segments(p)

def test_load_segments_rejects_start_invariant(tmp_path):
    d = _doc(); d["segments"][1]["start"] = 7        # start = idx*5 위반
    p = tmp_path / "segments.json"; common.atomic_write_json(p, d)
    with pytest.raises(ValueError, match="start"):
        common.load_segments(p)

def test_load_segments_missing_field_names_module(tmp_path):
    p = tmp_path / "segments.json"; common.atomic_write_json(p, _doc())
    with pytest.raises(ValueError, match="m2_keyframe"):
        common.load_segments(p, require=["rep_frame"])
    with pytest.raises(ValueError, match="m3_generate"):
        common.load_segments(p, require=["caption"])

def test_atomic_write_and_config(tmp_path):
    p = tmp_path / "x.json"
    common.atomic_write_json(p, {"a": 1})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}
    cfg = common.load_config(Path(__file__).parents[1] / "config.yaml")
    assert cfg["seg_len_sec"] == 5 and cfg["alpha_tiebreak"] == "larger"

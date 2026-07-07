import threading
import time
from pathlib import Path
from fastapi.testclient import TestClient
from m7_webui import create_app, sanitize_video_id


def make_cfg(tmp_path):
    return {"paths": {"data": str(tmp_path / "data"), "work": str(tmp_path / "work")},
            "embed_model": "stub-model"}


def make_client(tmp_path, run_module=lambda script, cfgp, vid: None, **kw):
    cfg = make_cfg(tmp_path)
    app = create_app(cfg, "config.yaml", alpha=0.5, run_module=run_module, **kw)
    return TestClient(app), cfg


def wait_stage(client, vid, target, timeout=2.0):
    deadline = time.time() + timeout
    st = None
    while time.time() < deadline:
        st = client.get(f"/api/status/{vid}").json()
        if st["stage"] == target:
            return st
        time.sleep(0.01)
    raise AssertionError(f"stage '{target}' 도달 실패: {st}")


def test_sanitize_video_id():
    assert sanitize_video_id("my video! (1)") == "my_video___1_"
    assert sanitize_video_id("clip_01-final") == "clip_01-final"


def test_upload_rejects_non_mp4(tmp_path):
    client, _ = make_client(tmp_path)
    r = client.post("/api/upload", files={"file": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 400


def test_upload_runs_pipeline_to_done(tmp_path):
    calls = []
    client, cfg = make_client(tmp_path,
                              run_module=lambda s, c, v: calls.append(s))
    r = client.post("/api/upload",
                    files={"file": ("My Clip.mp4", b"\x00\x01", "video/mp4")})
    assert r.status_code == 200
    vid = r.json()["video_id"]
    assert vid == "My_Clip"
    wait_stage(client, vid, "done")
    assert calls == ["m1_preprocess.py", "m2_keyframe.py",
                     "m3_generate.py", "m4_index.py"]
    assert (Path(cfg["paths"]["data"]) / "videos" / "My_Clip.mp4").read_bytes() \
        == b"\x00\x01"


def test_pipeline_failure_reports_stage_and_detail(tmp_path):
    def boom(script, cfgp, vid):
        if script == "m3_generate.py":
            raise RuntimeError("m3_generate.py 실패:\nCUDA OOM")
    client, _ = make_client(tmp_path, run_module=boom)
    vid = client.post("/api/upload",
                      files={"file": ("v.mp4", b"\x00", "video/mp4")}).json()["video_id"]
    st = wait_stage(client, vid, "error")
    assert "m3_generate.py 실패" in st["detail"]


def test_second_upload_while_busy_is_409(tmp_path):
    gate = threading.Event()
    client, _ = make_client(tmp_path, run_module=lambda s, c, v: gate.wait(1))
    r1 = client.post("/api/upload", files={"file": ("a.mp4", b"\x00", "video/mp4")})
    assert r1.status_code == 200
    r2 = client.post("/api/upload", files={"file": ("b.mp4", b"\x00", "video/mp4")})
    assert r2.status_code == 409
    gate.set()
    wait_stage(client, "a", "done")   # 정리: 잡 완료 후 종료


def test_status_unknown_video_404(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.get("/api/status/nope").status_code == 404

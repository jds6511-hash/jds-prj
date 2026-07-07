import json
import threading
import time
import warnings
from pathlib import Path
from types import SimpleNamespace

from starlette.exceptions import StarletteDeprecationWarning

# StarletteDeprecationWarning(UserWarning 하위)이 fastapi.testclient import 시점에
# 발생함(DeprecationWarning이 아니므로 pytest filterwarnings 마커로는 못 잡음).
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=StarletteDeprecationWarning)
    from fastapi.testclient import TestClient
from m5_search import Result
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


def test_upload_write_failure_releases_busy(tmp_path, monkeypatch):
    orig_write_bytes = Path.write_bytes
    calls = {"n": 0}

    def flaky_write_bytes(self, data):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("디스크 가득 참")
        return orig_write_bytes(self, data)

    monkeypatch.setattr(Path, "write_bytes", flaky_write_bytes)
    client, _ = make_client(tmp_path)

    r1 = client.post("/api/upload", files={"file": ("a.mp4", b"\x00", "video/mp4")})
    assert r1.status_code == 500

    r2 = client.post("/api/upload", files={"file": ("b.mp4", b"\x00", "video/mp4")})
    assert r2.status_code == 200


def test_status_unknown_video_404(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.get("/api/status/nope").status_code == 404


def write_segments(cfg, vid, n=3):
    wdir = Path(cfg["paths"]["work"]) / vid
    wdir.mkdir(parents=True)
    doc = {"video_id": vid, "duration_sec": n * 5.0, "fps": 30.0, "n_segments": n,
           "segments": [{"idx": i, "start": i * 5, "end": i * 5 + 5,
                         "rep_frame": "", "is_static": False, "motion_score": 0.1,
                         "subtitle": f"자막{i}", "caption": f"설명{i}"}
                        for i in range(n)]}
    (wdir / "segments.json").write_text(
        json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def _stub_index(n=3):
    return SimpleNamespace(segments=[
        {"idx": i, "start": i * 5, "end": i * 5 + 5,
         "subtitle": f"자막{i}", "caption": f"설명{i}"} for i in range(n)])


def test_segments_endpoint_returns_list(tmp_path):
    client, cfg = make_client(tmp_path)
    write_segments(cfg, "v1")
    r = client.get("/api/segments/v1")
    assert r.status_code == 200
    segs = r.json()["segments"]
    assert len(segs) == 3
    assert segs[0] == {"idx": 0, "start": 0, "end": 5,
                       "subtitle": "자막0", "caption": "설명0"}


def test_segments_missing_index_404(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.get("/api/segments/nope").status_code == 404


def test_search_returns_top3_cards(tmp_path):
    ranked = [Result(2, 0.9, 10, 15), Result(0, 0.8, 0, 5),
              Result(1, 0.7, 5, 10), Result(3, 0.1, 15, 20)]
    client, _ = make_client(tmp_path,
                            search_fn=lambda q, v, a, c: ranked,
                            load_index=lambda cfg, vid: _stub_index(4))
    r = client.post("/api/search", json={"video_id": "v1", "query": "질의"})
    assert r.status_code == 200
    res = r.json()["results"]
    assert len(res) == 3                                  # Top-3 고정
    assert res[0] == {"idx": 2, "start": 10, "end": 15, "score": 0.9,
                      "subtitle": "자막2", "caption": "설명2"}


def test_search_empty_query_400(tmp_path):
    client, _ = make_client(tmp_path)
    r = client.post("/api/search", json={"video_id": "v1", "query": "  "})
    assert r.status_code == 400


def test_search_while_indexing_409(tmp_path):
    gate = threading.Event()
    client, _ = make_client(tmp_path, run_module=lambda s, c, v: gate.wait(1))
    vid = client.post("/api/upload",
                      files={"file": ("v.mp4", b"\x00", "video/mp4")}).json()["video_id"]
    r = client.post("/api/search", json={"video_id": vid, "query": "질의"})
    assert r.status_code == 409
    assert "인덱싱" in r.json()["detail"]
    gate.set()
    wait_stage(client, vid, "done")


def test_search_no_index_files_409(tmp_path):
    def missing(cfg, vid):
        raise FileNotFoundError("emb_sub.npy 없음 — run m4_index.py first")
    client, _ = make_client(tmp_path, load_index=missing)
    r = client.post("/api/search", json={"video_id": "v1", "query": "질의"})
    assert r.status_code == 409


def test_video_route_404_when_missing(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.get("/api/video/nope").status_code == 404


def test_root_serves_html(tmp_path):
    client, _ = make_client(tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "영상 장면 검색" in r.text
    assert "text/html" in r.headers["content-type"]

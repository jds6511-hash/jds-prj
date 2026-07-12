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
    return {"paths": {"data": str(tmp_path / "data"), "work": str(tmp_path / "work"),
                      "results": str(tmp_path / "results")},
            "embed_model": "stub-model", "seg_len_sec": 5, "static_threshold": 0.05}


def make_client(tmp_path, run_module=lambda script, cfgp, vid: None, cfg=None, **kw):
    cfg = cfg or make_cfg(tmp_path)
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


def test_upload_non_oserror_failure_releases_busy(tmp_path, monkeypatch):
    # 비-OSError 예외(멀티파트 파싱 오류, 클라이언트 절단 등)도 busy를 해제해야 함
    def boom_write_bytes(self, data):
        raise RuntimeError("클라이언트 연결 끊김")

    monkeypatch.setattr(Path, "write_bytes", boom_write_bytes)
    client, _ = make_client(tmp_path)

    r1 = client.post("/api/upload", files={"file": ("a.mp4", b"\x00", "video/mp4")})
    assert r1.status_code == 500

    monkeypatch.undo()
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


def test_segments_invariant_violation_404(tmp_path):
    # common.load_segments가 던지는 ValueError(불변식/필드 누락)도 404로 매핑돼야 함
    client, cfg = make_client(tmp_path)
    wdir = Path(cfg["paths"]["work"]) / "v1"
    wdir.mkdir(parents=True)
    bad_doc = {"video_id": "v1", "duration_sec": 5.0, "fps": 30.0, "n_segments": 2,
               "segments": [{"idx": 0, "start": 0, "end": 5, "rep_frame": "",
                             "is_static": False, "motion_score": 0.1,
                             "subtitle": "자막0", "caption": "설명0"}]}
    (wdir / "segments.json").write_text(
        json.dumps(bad_doc, ensure_ascii=False), encoding="utf-8")
    r = client.get("/api/segments/v1")
    assert r.status_code == 404


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


def test_search_no_index_files_404(tmp_path):
    def missing(cfg, vid):
        raise FileNotFoundError("emb_sub.npy 없음 — run m4_index.py first")
    client, _ = make_client(tmp_path, load_index=missing)
    r = client.post("/api/search", json={"video_id": "v1", "query": "질의"})
    assert r.status_code == 404


def test_search_index_mismatch_valueerror_404(tmp_path):
    # VideoIndex.load가 임베딩 모델/세그먼트 수 불일치 시 던지는 ValueError도 404 + 원인 포함
    def mismatch(cfg, vid):
        raise ValueError("임베딩 모델 불일치: index=a config=b — run m4_index.py --force")
    client, _ = make_client(tmp_path, load_index=mismatch)
    r = client.post("/api/search", json={"video_id": "v1", "query": "질의"})
    assert r.status_code == 404
    assert "임베딩 모델 불일치" in r.json()["detail"]


def test_search_after_indexing_error_is_409_with_failure_message(tmp_path):
    def boom(script, cfgp, vid):
        raise RuntimeError("m1_preprocess.py 실패:\n뭔가 잘못됨")
    client, _ = make_client(tmp_path, run_module=boom)
    vid = client.post("/api/upload",
                      files={"file": ("v.mp4", b"\x00", "video/mp4")}).json()["video_id"]
    wait_stage(client, vid, "error")
    r = client.post("/api/search", json={"video_id": vid, "query": "질의"})
    assert r.status_code == 409
    assert "실패" in r.json()["detail"]


def test_search_video_id_traversal_is_sanitized_to_404(tmp_path):
    client, _ = make_client(tmp_path)
    r = client.post("/api/search", json={"video_id": "../etc", "query": "질의"})
    assert r.status_code == 404


def test_search_returns_raw_stats_and_logs_search(tmp_path):
    # search_stats_fn 스텁 주입 → 응답에 raw 4개 키 + search_log.jsonl에 줄 추가 [HIGH-2]
    stats = {"raw_sub_max": 0.9, "raw_sub_mean": 0.5,
             "raw_cap_max": 0.8, "raw_cap_mean": 0.4}
    ranked = [Result(0, 0.9, 0, 5)]
    client, cfg = make_client(
        tmp_path,
        search_stats_fn=lambda q, v, a, c: (ranked, stats),
        load_index=lambda cfg, vid: _stub_index(1))
    r = client.post("/api/search", json={"video_id": "v1", "query": "질의"})
    assert r.status_code == 200
    body = r.json()
    assert body["raw"] == stats

    log_path = Path(cfg["paths"]["results"]) / "search_log.jsonl"
    assert log_path.exists()
    line = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert line["video_id"] == "v1"
    assert line["query"] == "질의"
    assert line["alpha"] == 0.5
    assert line["top1_idx"] == 0
    assert line["top1_score"] == 0.9
    for k, v in stats.items():
        assert line[k] == v


def _search_with_tau(tmp_path, raw_sub_max, tau, raw_cap_max=0.5):
    stats = {"raw_sub_max": raw_sub_max, "raw_sub_mean": 0.4,
             "raw_cap_max": raw_cap_max, "raw_cap_mean": 0.3}
    ranked = [Result(0, 0.9, 0, 5)]
    cfg = make_cfg(tmp_path)
    if tau is not None:
        cfg["abstention_tau"] = tau
    client, _ = make_client(tmp_path, cfg=cfg,
                            search_stats_fn=lambda q, v, a, c: (ranked, stats),
                            load_index=lambda cfg, vid: _stub_index(1))
    r = client.post("/api/search", json={"video_id": "v1", "query": "질의"})
    assert r.status_code == 200
    return r.json()


def test_search_low_relevance_banner_flag(tmp_path):
    # [8-2 개정 2026-07-13] max(raw_sub_max, raw_cap_max) < tau → low_relevance=True.
    # 결과 목록은 그대로(은폐 금지).
    body = _search_with_tau(tmp_path, raw_sub_max=0.40, raw_cap_max=0.50, tau=0.55)
    assert body["low_relevance"] is True
    assert len(body["results"]) == 1          # 결과는 여전히 반환

    body = _search_with_tau(tmp_path, raw_sub_max=0.60, raw_cap_max=0.50, tau=0.55)
    assert body["low_relevance"] is False


def test_search_low_relevance_caption_channel_rescues_scene_query(tmp_path):
    # 장면형 질의 시나리오: 무발화 장면이라 자막 코사인은 낮지만(0.40) 캡션이 붙으면(0.60)
    # 유관 — sub 단독 채널이었다면 오배제됐을 케이스가 max 채널에서는 배너 없음
    # [설계 점검 1, 2026-07-13]
    body = _search_with_tau(tmp_path, raw_sub_max=0.40, raw_cap_max=0.60, tau=0.55)
    assert body["low_relevance"] is False


def test_search_no_tau_key_omits_low_relevance(tmp_path):
    # abstention_tau 미설정 config(구버전)에서는 필드 자체가 없어야 함 — 하위호환
    body = _search_with_tau(tmp_path, raw_sub_max=0.40, tau=None)
    assert "low_relevance" not in body


def test_search_still_works_when_results_path_missing(tmp_path):
    # cfg에 results 경로가 없거나 로그 기록이 실패해도 검색 응답은 500이 아니어야 함
    # (로깅은 best-effort) [HIGH-2]
    cfg = make_cfg(tmp_path)
    del cfg["paths"]["results"]
    stats = {"raw_sub_max": 0.9, "raw_sub_mean": 0.5,
             "raw_cap_max": 0.8, "raw_cap_mean": 0.4}
    ranked = [Result(0, 0.9, 0, 5)]
    app = create_app(cfg, "config.yaml", alpha=0.5,
                     search_stats_fn=lambda q, v, a, c: (ranked, stats),
                     load_index=lambda cfg, vid: _stub_index(1))
    client = TestClient(app)
    r = client.post("/api/search", json={"video_id": "v1", "query": "질의"})
    assert r.status_code == 200
    assert r.json()["raw"] == stats


def test_search_fn_stub_without_stats_omits_raw(tmp_path):
    # 기존 search_fn 스텁 주입 패턴(stats 없음)은 그대로 동작하고 raw 필드가 없다 —
    # 하위호환 확인 [HIGH-2]
    ranked = [Result(0, 0.9, 0, 5)]
    client, _ = make_client(tmp_path,
                            search_fn=lambda q, v, a, c: ranked,
                            load_index=lambda cfg, vid: _stub_index(1))
    r = client.post("/api/search", json={"video_id": "v1", "query": "질의"})
    assert r.status_code == 200
    assert "raw" not in r.json()


def test_video_route_404_when_missing(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.get("/api/video/nope").status_code == 404


def test_root_serves_html(tmp_path):
    client, _ = make_client(tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "영상 장면 검색" in r.text
    assert "text/html" in r.headers["content-type"]
    assert "/api/current" in r.text   # 재접속 복원 로직 존재 스모크


def test_status_progress_during_m2(tmp_path):
    gate = threading.Event()

    def run_module(script, cfgp, vid):
        if script == "m2_keyframe.py":
            gate.wait(2)

    client, cfg = make_client(tmp_path, run_module=run_module)
    vid = client.post("/api/upload",
                      files={"file": ("v.mp4", b"\x00", "video/mp4")}).json()["video_id"]
    wait_stage(client, vid, "m2")
    write_segments(cfg, vid, n=4)
    frames_dir = Path(cfg["paths"]["work"]) / vid / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    (frames_dir / "seg_0000.jpg").write_bytes(b"")
    (frames_dir / "seg_0001.jpg").write_bytes(b"")
    st = client.get(f"/api/status/{vid}").json()
    assert st["progress"] == {"n": 2, "total": 4}
    gate.set()
    wait_stage(client, vid, "done")


def test_status_progress_absent_when_no_segments(tmp_path):
    gate = threading.Event()

    def run_module(script, cfgp, vid):
        if script == "m1_preprocess.py":
            gate.wait(2)

    client, cfg = make_client(tmp_path, run_module=run_module)
    vid = client.post("/api/upload",
                      files={"file": ("v.mp4", b"\x00", "video/mp4")}).json()["video_id"]
    st = wait_stage(client, vid, "m1")
    assert "progress" not in st
    gate.set()
    wait_stage(client, vid, "done")


def test_current_returns_active_job(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.get("/api/current").json() == {"video_id": None}
    r = client.post("/api/upload", files={"file": ("v.mp4", b"\x00", "video/mp4")})
    vid = r.json()["video_id"]
    cur = client.get("/api/current").json()
    assert cur["video_id"] == vid


def test_search_log_records_tau_and_low_relevance(tmp_path):
    # tau 재캘리브레이션 후에도 "사용자가 실제로 본 배너"를 복원할 수 있도록
    # 당시 tau와 판정을 로그에 기록 [리뷰 2026-07-11 Minor]
    stats = {"raw_sub_max": 0.40, "raw_sub_mean": 0.3,
             "raw_cap_max": 0.5, "raw_cap_mean": 0.3}
    ranked = [Result(0, 0.9, 0, 5)]
    cfg = make_cfg(tmp_path)
    cfg["abstention_tau"] = 0.48
    client, _ = make_client(tmp_path, cfg=cfg,
                            search_stats_fn=lambda q, v, a, c: (ranked, stats),
                            load_index=lambda cfg, vid: _stub_index(1))
    r = client.post("/api/search", json={"video_id": "v1", "query": "질의"})
    assert r.status_code == 200
    line = json.loads((Path(cfg["paths"]["results"]) / "search_log.jsonl")
                      .read_text(encoding="utf-8").strip().splitlines()[-1])
    assert line["abstention_tau"] == 0.48
    assert line["low_relevance"] is True

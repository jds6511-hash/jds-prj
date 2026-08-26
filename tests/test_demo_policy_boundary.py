"""자격 경계를 **우회할 수 있는 경로가 0개인지** 본다.

앞선 감사에서 "요청 경로 4곳에 403을 넣었다"로 닫으려 했는데, 기준은 그게 아니다 —
**guard를 거치지 않고 restricted 영상에 도달할 수 있는 route가 없어야** 한다.
그래서 여기서는 endpoint를 하나하나 적는 대신 **route table을 열거**한다.

여기서 잡는 것 넷.

1. route 열거 — `{video_id}`를 받는 모든 GET route가 restricted ID에 403을 낸다
2. 대소문자 변형 — `Gemini_Promo`. Windows 파일시스템은 대소문자를 구분하지 않으므로
   판정이 대소문자를 구분하면 **막은 영상의 캡션이 그대로 나간다**
3. 403이 artifact를 읽기 **전에** 나온다 — 응답만 막고 내부에서 읽으면 접촉이다
4. upload — 조회 금지와 **덮어쓰기 금지**는 다른 문제다
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import common  # noqa: E402
import eligibility  # noqa: E402
from m7_webui import create_app, sanitize_video_id  # noqa: E402

RESTRICTED = "gemini_promo"          # test split
CASE_VARIANTS = ("Gemini_Promo", "GEMINI_PROMO", "gEmini_promo")


def _cfg(tmp_path):
    return {"seg_len_sec": 5, "embed_model": "nlpai-lab/KURE-v1",
            "abstention_tau": 0.55, "static_threshold": 0,
            "paths": {"data": str(tmp_path / "data"),
                      "work": str(tmp_path / "work"),
                      "results": str(tmp_path / "results")}}


def _client(cfg, **kw):
    app = create_app(cfg, "config.yaml", alpha=0.5, run_module=lambda *a: None, **kw)
    return TestClient(app), app


def _plant_restricted_index(cfg, video_id=RESTRICTED, n=3):
    """restricted 영상의 산출물을 실제로 깔아 둔다.

    산출물이 없으면 404가 403을 가려서 "막혔다"를 잘못 읽는다.
    """
    w = Path(cfg["paths"]["work"]) / video_id
    (w / "frames").mkdir(parents=True, exist_ok=True)
    doc = {"n_segments": n, "segments": [
        {"idx": i, "start": i * 5, "end": (i + 1) * 5,
         "subtitle": "이건 test split 자막 %d" % i,
         "caption": "이건 test split 캡션 %d" % i,
         "motion_score": 0.5} for i in range(n)]}
    (w / "segments.json").write_text(json.dumps(doc, ensure_ascii=False),
                                     encoding="utf-8")
    for name in ("emb_sub", "emb_cap"):
        np.save(w / f"{name}.npy", np.zeros((n, 4), dtype=np.float32))
    (w / "meta.json").write_text(json.dumps(
        {"embed_model": cfg["embed_model"], "n_segments": n,
         "text_hash": common.index_text_hash(doc)}), encoding="utf-8")
    d = Path(cfg["paths"]["data"]) / "videos"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{video_id}.mp4").write_bytes(b"\x00" * 8)
    return w


# --------------------------------------------------------- 1. route 열거

def _video_id_routes(app):
    return sorted({r.path for r in app.routes
                   if "{video_id}" in getattr(r, "path", "")})


def test_every_video_id_route_is_guarded(tmp_path):
    """route table을 열거한다 — 새 endpoint가 생기면 여기서 걸린다."""
    cfg = _cfg(tmp_path)
    _plant_restricted_index(cfg)
    c, app = _client(cfg)
    paths = _video_id_routes(app)
    assert paths, "video_id를 받는 route가 하나도 없다 — 열거가 깨졌다"
    for path in paths:
        r = c.get(path.replace("{video_id}", RESTRICTED))
        assert r.status_code == 403, f"{path} → {r.status_code} {r.text[:120]}"


def test_body_video_id_routes_are_guarded(tmp_path):
    """경로 파라미터가 아니라 **본문**으로 video_id를 받는 route."""
    cfg = _cfg(tmp_path)
    _plant_restricted_index(cfg)
    c, _ = _client(cfg)
    assert c.post("/api/search",
                  json={"video_id": RESTRICTED, "query": "질의"}).status_code == 403


def test_routes_without_video_id_do_not_leak_restricted_ids(tmp_path):
    """`/api/meta`·`/api/current`는 video_id를 받지 않는다 — 값이 새지 않는지 본다."""
    cfg = _cfg(tmp_path)
    _plant_restricted_index(cfg)
    c, _ = _client(cfg)
    for path in ("/api/meta", "/api/current"):
        body = c.get(path).text
        assert RESTRICTED not in body, path


# ------------------------------------------------- 2. 대소문자 변형 우회

@pytest.mark.parametrize("vid", CASE_VARIANTS)
def test_case_variants_are_blocked_in_policy(vid):
    """Windows 파일시스템은 대소문자를 구분하지 않는다 — 판정이 구분하면 우회다."""
    assert not eligibility.demo_eligible(vid), vid


@pytest.mark.parametrize("vid", CASE_VARIANTS)
def test_case_variants_are_blocked_on_every_route(tmp_path, vid):
    cfg = _cfg(tmp_path)
    _plant_restricted_index(cfg)
    c, app = _client(cfg)
    for path in _video_id_routes(app):
        r = c.get(path.replace("{video_id}", vid))
        assert r.status_code == 403, f"{path} {vid} → {r.status_code}"
    assert c.post("/api/search",
                  json={"video_id": vid, "query": "질의"}).status_code == 403


def test_prefix_rule_is_case_insensitive_too():
    assert not eligibility.demo_eligible("P2_sample_01")
    assert not eligibility.demo_eligible("P3_Pilot_A")


# ------------------------------------- 3. 403이 artifact 읽기 전에 나온다

def test_403_happens_before_any_artifact_is_read(tmp_path, monkeypatch):
    """403 응답을 주면서 내부에서 segments.json을 읽으면 그것도 접촉이다."""
    cfg = _cfg(tmp_path)
    w = _plant_restricted_index(cfg)
    reads = []
    real = Path.read_text

    def spy(self, *a, **kw):
        if w in self.parents or self.parent == w:
            reads.append(self.name)
        return real(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", spy)
    c, app = _client(cfg)
    for path in _video_id_routes(app):
        c.get(path.replace("{video_id}", RESTRICTED))
    c.post("/api/search", json={"video_id": RESTRICTED, "query": "질의"})
    assert reads == [], f"403인데 읽었다: {reads}"


# ------------------------------------------------------------ 4. upload

def test_upload_cannot_overwrite_an_existing_video(tmp_path):
    """조회 금지와 덮어쓰기 금지는 다른 문제다.

    확정 인덱스의 원본 영상을 같은 이름 업로드로 갈아치울 수 있으면 배포 정합성이
    무너진다 — text_hash도 embed_model도 이것을 잡지 못한다(둘 다 인덱스만 본다).
    """
    cfg = _cfg(tmp_path)
    d = Path(cfg["paths"]["data"]) / "videos"
    d.mkdir(parents=True, exist_ok=True)
    (d / "gwaktube_soviet_apartment.mp4").write_bytes(b"original")
    c, _ = _client(cfg)
    r = c.post("/api/upload", files={
        "file": ("gwaktube_soviet_apartment.mp4", b"replaced", "video/mp4")})
    assert r.status_code == 409, r.text
    assert (d / "gwaktube_soviet_apartment.mp4").read_bytes() == b"original"


@pytest.mark.parametrize("name", [
    "gemini_promo.mp4", "Gemini_Promo.mp4", "p2_new_sample.mp4"])
def test_upload_rejects_restricted_ids(tmp_path, name):
    cfg = _cfg(tmp_path)
    c, _ = _client(cfg)
    assert c.post("/api/upload",
                  files={"file": (name, b"\x00", "video/mp4")}).status_code == 403


@pytest.mark.parametrize("name", [
    "../../etc/passwd.mp4", "a/b.mp4", "..\\..\\win.mp4", "..mp4", "a b.mp4",
])
def test_upload_id_has_no_path_traversal(name):
    """디렉터리는 `Path(...).stem`이 떨어내고, 남은 글자는 [a-zA-Z0-9_-]로 축약된다."""
    got = sanitize_video_id(Path(name).stem)
    assert got and "/" not in got and "\\" not in got and ".." not in got
    assert all(ch.isalnum() or ch in "_-" for ch in got), got


# ------------------------------- manifest 부재의 의미를 정확히 분리한다

def test_known_restricted_stays_blocked_when_manifest_is_missing(tmp_path, monkeypatch):
    """manifest를 못 읽어도 **알려진** restricted는 계속 막힌다."""
    monkeypatch.setattr(eligibility, "E2E_MANIFEST", tmp_path / "없는_manifest.json")
    assert not eligibility.manifest_available()
    assert not eligibility.demo_eligible(RESTRICTED)
    assert not eligibility.demo_eligible("p2_x")


def test_ordinary_video_still_runs_when_manifest_is_missing(tmp_path, monkeypatch):
    """"manifest가 없으니 전부 막는다"가 아니다 — 배포본에는 planning/이 없을 수 있다.

    대신 E2E 차단이 동작하지 않는다는 사실을 preflight가 경고로 노출한다.
    """
    monkeypatch.setattr(eligibility, "E2E_MANIFEST", tmp_path / "없는_manifest.json")
    assert eligibility.demo_eligible("gwaktube_soviet_apartment")
    sys.path.insert(0, str(ROOT / "scripts"))
    import demo
    cfg = _cfg(tmp_path)
    cfg.update({"caption_model": "Qwen/Qwen2.5-VL-3B-Instruct", "vlm_4bit": True,
                "seg_len_sec": 5, "static_threshold": 0})
    _plant_restricted_index(cfg, "gwaktube_soviet_apartment", n=3)
    r = demo.preflight(cfg, "gwaktube_soviet_apartment", demo.DEPLOYMENT_ALPHA)
    assert r["ok"] is True
    assert any("manifest" in w or "E2E" in w for w in r["warnings"])


def test_e2e_only_video_is_blocked_when_manifest_is_present():
    """manifest가 있을 때는 그 선언이 실제로 판정에 쓰인다."""
    if not eligibility.manifest_available():
        pytest.skip("이 환경에는 manifest가 없다")
    assert not eligibility.demo_eligible("e2e_cooking_1")

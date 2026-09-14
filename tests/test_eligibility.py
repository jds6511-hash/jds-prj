"""데모 자격 정책이 **선언이 아니라 강제**되는지 본다.

같은 유형의 사고가 두 번 났다.
1. manifest에 `eligible_for_public_demo: false`를 적었는데 진입점이 막지 않았다.
2. 진입점 preflight가 시작 시 `--video-id` 하나만 봤고, 웹 API는 요청 본문의
   `video_id`를 그대로 받아 test split 영상도 조회·재생됐다.

여기서 막는 것은 셋이다 — 정책의 단일 출처, test split 목록의 drift, 요청 경로 강제.
"""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import eligibility  # noqa: E402
from m7_webui import create_app  # noqa: E402

QUERIES = ROOT / "data/queries/queries.jsonl"
MANIFEST = ROOT / "planning/e2e_external_manifest.json"


# ------------------------------------------------------------------ 정책 자체

def test_test_split_list_matches_the_query_file():
    """하드코딩된 목록이 실제 test split과 어긋나면 실패한다.

    새 test 영상을 추가하면 여기서 깨진다 — 그때 guard도 같이 갱신하라는 신호다.
    질의 문구는 읽지 않는다(split·video_id만).
    """
    if not QUERIES.is_file():
        pytest.skip("질의 파일이 없는 환경이다")
    got = set()
    for line in QUERIES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        q = json.loads(line)
        if q.get("split") == "test" and q.get("video_id"):
            got.add(q["video_id"])
    assert got == set(eligibility.TEST_SPLIT_VIDEOS), (
        "test split 영상 목록이 어긋났다: 파일=%s 코드=%s"
        % (sorted(got), sorted(eligibility.TEST_SPLIT_VIDEOS)))


def test_manifest_declared_e2e_only_videos_are_blocked():
    if not MANIFEST.is_file():
        pytest.skip("E2E manifest가 없는 환경이다")
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    declared = [v["e2e_id"] for v in m.get("videos", [])
                if v.get("e2e_only") or v.get("eligible_for_public_demo") is False]
    assert declared, "manifest에 E2E 전용 선언이 하나도 없다 — 검사가 무의미해진다"
    for vid in declared:
        assert not eligibility.demo_eligible(vid), vid
        assert vid in eligibility.demo_block_reason(vid)


def test_test_split_videos_are_blocked():
    for vid in eligibility.TEST_SPLIT_VIDEOS:
        assert not eligibility.demo_eligible(vid), vid
        assert "test split" in eligibility.demo_block_reason(vid)


def test_p2_p3_name_prefixes_are_blocked():
    for vid in ("p2_sample_01", "p3_pilot_a"):
        assert not eligibility.demo_eligible(vid)


def test_ordinary_dev_video_is_eligible():
    assert eligibility.demo_eligible("gwaktube_soviet_apartment")
    assert eligibility.demo_block_reason("gwaktube_soviet_apartment") is None


def test_empty_video_id_is_blocked():
    assert not eligibility.demo_eligible("")


# ------------------------------------------------------- 진입점이 같은 정책을 쓴다

def test_demo_entrypoint_uses_the_shared_policy():
    """`scripts/demo.py`가 자체 목록을 다시 들고 있으면 표류한다."""
    import demo
    assert demo.TEST_SPLIT_VIDEOS is eligibility.TEST_SPLIT_VIDEOS
    for vid in eligibility.TEST_SPLIT_VIDEOS:
        assert demo.demo_ineligible(vid), vid


def test_demo_preflight_rejects_blocked_video(tmp_path):
    import demo
    cfg = {"caption_model": "Qwen/Qwen2.5-VL-3B-Instruct", "vlm_4bit": True,
           "embed_model": "nlpai-lab/KURE-v1", "seg_len_sec": 5,
           "static_threshold": 0,
           "paths": {"data": str(tmp_path), "work": str(tmp_path / "work"),
                     "results": str(tmp_path / "results")}}
    with pytest.raises(demo.PreflightError) as e:
        demo.preflight(cfg, eligibility.TEST_SPLIT_VIDEOS[0], demo.DEPLOYMENT_ALPHA)
    assert "test split" in str(e.value)


# --------------------------------------------------- 요청 경로에서도 강제된다

def _client(tmp_path, **kw):
    cfg = {"seg_len_sec": 5, "embed_model": "nlpai-lab/KURE-v1",
           "abstention_tau": 0.55,
           "paths": {"data": str(tmp_path), "work": str(tmp_path / "work"),
                     "results": str(tmp_path / "results")}}
    app = create_app(cfg, "config.yaml", alpha=0.5,
                     run_module=lambda *a: None, **kw)
    return TestClient(app)


BLOCKED = ("gemini_promo", "e2e_cooking_1")


@pytest.mark.parametrize("vid", BLOCKED)
def test_search_endpoint_rejects_blocked_video(tmp_path, vid):
    c = _client(tmp_path)
    r = c.post("/api/search", json={"video_id": vid, "query": "질의"})
    assert r.status_code == 403, r.text


@pytest.mark.parametrize("vid", BLOCKED)
def test_segments_endpoint_rejects_blocked_video(tmp_path, vid):
    """캡션·자막 전문을 노출하는 경로다 — 여기서 새면 인덱스 내용이 그대로 나간다."""
    c = _client(tmp_path)
    assert c.get("/api/segments/%s" % vid).status_code == 403


@pytest.mark.parametrize("vid", BLOCKED)
def test_video_endpoint_rejects_blocked_video(tmp_path, vid):
    c = _client(tmp_path)
    assert c.get("/api/video/%s" % vid).status_code == 403


@pytest.mark.parametrize("vid", BLOCKED)
def test_upload_rejects_blocked_video_id(tmp_path, vid):
    c = _client(tmp_path)
    r = c.post("/api/upload",
               files={"file": ("%s.mp4" % vid, b"\x00", "video/mp4")})
    assert r.status_code == 403, r.text


def test_guard_is_on_by_default(tmp_path):
    """기본값이 fail-closed여야 한다 — 켜는 것을 잊으면 막히지 않는다."""
    c = _client(tmp_path)
    assert c.post("/api/search",
                  json={"video_id": "gemini_promo", "query": "q"}).status_code == 403


def test_guard_can_be_disabled_only_explicitly(tmp_path):
    """정책을 끄는 경로가 있는지 명시적으로 문서화한다(테스트·오프라인 진단용).

    끄면 403이 사라지고 그 뒤 단계(인덱스 로드)로 넘어간다 — 여기서는 인덱스가
    없으므로 404가 나오는 것이 정상이다.
    """
    def _no_index(cfg, vid):
        raise FileNotFoundError("인덱스 없음")

    c = _client(tmp_path, enforce_demo_policy=False, load_index=_no_index)
    r = c.post("/api/search", json={"video_id": "gemini_promo", "query": "q"})
    assert r.status_code == 404, r.text

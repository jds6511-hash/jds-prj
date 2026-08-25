"""external E2E — manifest 계약과 연구 격리 가드.

**네트워크에 의존하지 않는다.** 실제 YouTube 접근·다운로드는 별도 실행이고,
여기서는 스키마·격리·경계 계산만 mock으로 검증한다. 영상이 삭제돼도 이 테스트는
깨지지 않아야 한다.
"""
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import e2e_external as E                                            # noqa: E402


def _video(**over):
    v = {"e2e_id": "e2e_x", "phase": 1, "class": "scene", "role": "r",
         "source_url": "https://www.youtube.com/watch?v=AAAAAAAAAAA",
         "source_video_id": "AAAAAAAAAAA", "title": "t", "uploader": "u",
         "upload_date": "20260101", "duration_sec": 300,
         "availability": "public", "probed_at": "2026-08-25",
         "local_file": None, "local_file_sha256": None, "audio_present": None,
         "status": "manifest_only", "e2e_only": True,
         "eligible_for_research_evaluation": False, "eligible_for_p2": False,
         "eligible_for_p3": False, "eligible_for_test": False,
         "eligible_for_public_demo": False}
    v.update(over)
    return v


def _manifest(videos=None, **over):
    m = {"schema_version": 1, "e2e_suite_id": "s1", "purpose": "p",
         "deployment_identity": dict(E.DEPLOYMENT_IDENTITY),
         "acquisition": {"tool": "yt-dlp", "bypass_used": False},
         "research_metrics_generated": False,
         "videos": videos if videos is not None else [_video()],
         "excluded": [], "optional_candidates": [], "optional_rule": "x",
         "phase_order": ["e2e_x"], "phase_order_reason": "y"}
    m.update(over)
    return m


# ---- 스키마 allowlist ------------------------------------------------------

def test_video_keys_are_allowlisted():
    m = _manifest([_video(secret_field="x")])
    with pytest.raises(E.E2EError) as e:
        E.validate(m)
    assert "secret_field" in str(e.value)


def test_missing_required_video_key_is_refused():
    v = _video()
    del v["duration_sec"]
    with pytest.raises(E.E2EError) as e:
        E.validate(_manifest([v]))
    assert "duration_sec" in str(e.value)


def test_unknown_schema_version_is_refused():
    with pytest.raises(E.E2EError):
        E.validate(_manifest(schema_version=99))


def test_valid_manifest_passes():
    assert E.validate(_manifest())["n_videos"] == 1


# ---- 연구 격리 -------------------------------------------------------------

def test_e2e_only_must_be_true():
    with pytest.raises(E.E2EError) as e:
        E.validate(_manifest([_video(e2e_only=False)]))
    assert "e2e_only" in str(e.value)


@pytest.mark.parametrize("flag", [
    "eligible_for_research_evaluation", "eligible_for_p2", "eligible_for_p3",
    "eligible_for_test", "eligible_for_public_demo"])
def test_every_research_eligibility_must_be_false(flag):
    with pytest.raises(E.E2EError) as e:
        E.validate(_manifest([_video(**{flag: True})]))
    assert flag in str(e.value)


def test_research_metrics_flag_must_be_false():
    with pytest.raises(E.E2EError):
        E.validate(_manifest(research_metrics_generated=True))


def test_bypass_flag_must_be_false():
    with pytest.raises(E.E2EError) as e:
        E.validate(_manifest(acquisition={"tool": "yt-dlp",
                                          "bypass_used": True}))
    assert "bypass" in str(e.value)


@pytest.mark.parametrize("vid", [
    "panibottle_vietnam1", "gemini_promo", "gwaktube_soviet_apartment",
    "kheritage_grave_excavation"])
def test_research_video_ids_are_refused(vid):
    """dev·test 영상을 E2E 이름으로 끌어오지 않는다."""
    with pytest.raises(E.E2EError) as e:
        E.validate(_manifest([_video(e2e_id=vid)]))
    assert "연구" in str(e.value) or "research" in str(e.value)


def test_e2e_id_must_carry_the_prefix():
    with pytest.raises(E.E2EError):
        E.validate(_manifest([_video(e2e_id="scene_fast")]))


# ---- 중복 -----------------------------------------------------------------

def test_duplicate_e2e_id_is_refused():
    with pytest.raises(E.E2EError) as e:
        E.validate(_manifest([_video(), _video(source_video_id="BBBBBBBBBBB")]))
    assert "중복" in str(e.value)


def test_duplicate_source_url_is_refused():
    with pytest.raises(E.E2EError):
        E.validate(_manifest([_video(), _video(e2e_id="e2e_y")]))


# ---- 배포 identity ---------------------------------------------------------

def test_deployment_identity_must_match_production():
    m = _manifest()
    m["deployment_identity"]["caption_model"] = "Qwen/Qwen3-VL-4B-Instruct"
    with pytest.raises(E.E2EError) as e:
        E.validate(m)
    assert "caption_model" in str(e.value)


def test_alpha_must_be_exactly_the_deployment_value():
    m = _manifest()
    m["deployment_identity"]["alpha"] = 0.6
    with pytest.raises(E.E2EError) as e:
        E.validate(m)
    assert "alpha" in str(e.value)


def test_declared_identity_is_the_production_one():
    assert E.DEPLOYMENT_IDENTITY["caption_model"] == \
        "Qwen/Qwen2.5-VL-3B-Instruct"
    assert E.DEPLOYMENT_IDENTITY["embed_model"] == "nlpai-lab/KURE-v1"
    assert E.DEPLOYMENT_IDENTITY["alpha"] == 0.5


# ---- 로컬 파일 -------------------------------------------------------------

def test_missing_local_file_is_reported_not_raised(tmp_path):
    v = _video(local_file=str(tmp_path / "nope.mp4"), status="acquired")
    st = E.local_file_status(v)
    assert st["ok"] is False and "없다" in st["reason"]


def test_sha_mismatch_is_refused(tmp_path):
    f = tmp_path / "a.mp4"
    f.write_bytes(b"hello")
    v = _video(local_file=str(f), local_file_sha256="0" * 64)
    st = E.local_file_status(v)
    assert st["ok"] is False and "sha256" in st["reason"]


def test_matching_sha_passes(tmp_path):
    f = tmp_path / "a.mp4"
    f.write_bytes(b"hello")
    import hashlib
    v = _video(local_file=str(f),
               local_file_sha256=hashlib.sha256(b"hello").hexdigest())
    st = E.local_file_status(v)
    assert st["ok"] is True and st["size_bytes"] == 5


def test_file_without_recorded_sha_is_recorded_not_failed(tmp_path):
    f = tmp_path / "a.mp4"
    f.write_bytes(b"hello")
    st = E.local_file_status(_video(local_file=str(f)))
    assert st["ok"] is True and len(st["sha256"]) == 64


# ---- 경계 계산 -------------------------------------------------------------

def test_segment_bounds_check():
    ok = E.check_segment_bounds(
        [{"idx": 0, "start": 0, "end": 5}, {"idx": 1, "start": 5, "end": 10}],
        duration_sec=10, seg_len=5)
    assert ok["ok"] is True and ok["n_segments"] == 2


def test_segment_beyond_duration_fails():
    r = E.check_segment_bounds([{"idx": 0, "start": 0, "end": 5}],
                               duration_sec=3, seg_len=5)
    assert r["ok"] is False and "duration" in r["reason"]


def test_zero_segments_fails():
    r = E.check_segment_bounds([], duration_sec=10, seg_len=5)
    assert r["ok"] is False


def test_embedding_dimension_check():
    assert E.check_embedding(rows=10, dim=1024, n_segments=10)["ok"] is True
    assert E.check_embedding(rows=10, dim=768, n_segments=10)["ok"] is False
    assert E.check_embedding(rows=9, dim=1024, n_segments=10)["ok"] is False


def test_rank_schema_check():
    good = [{"rank": 1, "idx": 0, "start": 0, "end": 5, "seek_to": 0,
             "score": 1.0, "subtitle": "a", "caption": "b"},
            {"rank": 2, "idx": 1, "start": 5, "end": 10, "seek_to": 5,
             "score": 0.5, "subtitle": "", "caption": "c"}]
    assert E.check_results(good, duration_sec=10, n_segments=2)["ok"] is True


def test_rank_must_be_sequential():
    bad = [{"rank": 1, "idx": 0, "start": 0, "end": 5, "seek_to": 0,
            "score": 1.0, "subtitle": "", "caption": ""},
           {"rank": 3, "idx": 1, "start": 5, "end": 10, "seek_to": 5,
            "score": 0.5, "subtitle": "", "caption": ""}]
    r = E.check_results(bad, duration_sec=10, n_segments=2)
    assert r["ok"] is False and "rank" in r["reason"]


def test_seek_out_of_bounds_fails():
    bad = [{"rank": 1, "idx": 0, "start": 0, "end": 5, "seek_to": 99,
            "score": 1.0, "subtitle": "", "caption": ""}]
    r = E.check_results(bad, duration_sec=10, n_segments=2)
    assert r["ok"] is False and "seek_to" in r["reason"]


def test_non_finite_score_fails():
    bad = [{"rank": 1, "idx": 0, "start": 0, "end": 5, "seek_to": 0,
            "score": float("nan"), "subtitle": "", "caption": ""}]
    assert E.check_results(bad, duration_sec=10, n_segments=2)["ok"] is False


def test_segment_index_out_of_range_fails():
    bad = [{"rank": 1, "idx": 99, "start": 0, "end": 5, "seek_to": 0,
            "score": 1.0, "subtitle": "", "caption": ""}]
    assert E.check_results(bad, duration_sec=10, n_segments=2)["ok"] is False


# ---- functional / semantic 분리 --------------------------------------------

def test_semantic_observation_never_becomes_a_metric():
    obs = E.semantic_observation(query="q", anchor=(1465, 1495),
                                 results=[{"rank": 1, "start": 1470,
                                           "end": 1475}])
    assert obs["status"] in E.SEMANTIC_STATUSES
    assert "accuracy" not in obs and "score" not in obs
    assert obs["is_research_metric"] is False


def test_anchor_hit_is_observed_within_window():
    obs = E.semantic_observation(query="q", anchor=(1465, 1495),
                                 results=[{"rank": 2, "start": 1470,
                                           "end": 1475}])
    assert obs["anchor_in_topk"] is True and obs["anchor_rank"] == 2


def test_anchor_miss_is_observed_not_failed():
    obs = E.semantic_observation(query="q", anchor=(1465, 1495),
                                 results=[{"rank": 1, "start": 10, "end": 15}])
    assert obs["anchor_in_topk"] is False
    assert obs["status"] == "REVIEW"          # FAIL이 아니다


def test_level2_query_without_anchor_is_observed():
    obs = E.semantic_observation(query="q", anchor=None,
                                 results=[{"rank": 1, "start": 10, "end": 15}])
    assert obs["level"] == 2 and obs["status"] == "OBSERVED"
    assert obs["anchor_in_topk"] is None


def test_functional_verdict_is_independent_of_semantic():
    v = E.functional_verdict({"ingest": True, "stt": True, "caption": True,
                              "embedding": True, "index": True,
                              "search": True, "playback": True})
    assert v["verdict"] == "PASS"
    v2 = E.functional_verdict({"ingest": True, "stt": False, "caption": True,
                               "embedding": True, "index": True,
                               "search": True, "playback": True})
    assert v2["verdict"] == "FAIL" and v2["failed_stages"] == ["stt"]


# ---- 실행 순서 -------------------------------------------------------------

def test_phase_order_puts_the_longest_last():
    m = json.loads((ROOT / "planning" /
                    "e2e_external_manifest.json").read_text(encoding="utf-8"))
    E.validate(m)
    order = m["phase_order"]
    dur = {v["e2e_id"]: v["duration_sec"] for v in m["videos"]}
    assert order[-1] == "e2e_interview"
    assert dur[order[-1]] == max(dur.values())
    assert dur[order[0]] == min(dur.values())


def test_real_manifest_has_no_long_named_speech_entry():
    m = json.loads((ROOT / "planning" /
                    "e2e_external_manifest.json").read_text(encoding="utf-8"))
    ids = [v["e2e_id"] for v in m["videos"]]
    assert "e2e_speech_medium" in ids and "e2e_speech_long" not in ids


def test_real_manifest_records_the_excluded_candidate():
    m = json.loads((ROOT / "planning" /
                    "e2e_external_manifest.json").read_text(encoding="utf-8"))
    ex = {e["e2e_id"]: e for e in m["excluded"]}
    assert ex["e2e_kfood"]["status"] == "EXCLUDED"
    assert "authentication" in ex["e2e_kfood"]["reason"]


# ---- 누출·의존 경계 --------------------------------------------------------

def test_module_does_not_import_research_metric_paths():
    src = (ROOT / "scripts" / "e2e_external.py").read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not ({"m6_evaluate", "m9_report_eval", "p2_retrieve", "p2_evaluate",
                 "p3_design_sensitivity", "scipy"} & mods)


def test_module_declares_no_research_metrics():
    src = (ROOT / "scripts" / "e2e_external.py").read_text(encoding="utf-8")
    for bad in ("def mrr", "def recall_at", "def ndcg", "bootstrap_ci"):
        assert bad not in src, bad


def test_raw_video_paths_are_not_tracked_by_git():
    import subprocess
    out = subprocess.run(["git", "ls-files", "runs/e2e_external"],
                         cwd=ROOT, capture_output=True, text=True)
    assert not [p for p in out.stdout.splitlines()
                if p.endswith((".mp4", ".webm", ".mkv"))]


def test_ci_tests_need_no_network():
    """이 파일도 대상 모듈도 네트워크 라이브러리를 import하지 않는다.

    YouTube가 삭제되거나 네트워크가 끊겨도 기존 test suite가 깨지면 안 된다.
    """
    net = {"requests", "urllib", "httpx", "aiohttp", "socket"}
    for path in (Path(__file__), ROOT / "scripts" / "e2e_external.py"):
        mods = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
        assert not (net & mods), (path.name, net & mods)

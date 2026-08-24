"""데모 진입점 preflight — fail-closed 계약.

시작 전에 모델·config·인덱스 identity를 확인한다. "일단 실행하고 이상하면 알림"을
금지하는 것이 목적이다. 잘못된 index/model/config 조합은 실행되지 않는다.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import common                                                       # noqa: E402
import demo as D                                                    # noqa: E402

DEPLOY = {"caption_model": "Qwen/Qwen2.5-VL-3B-Instruct", "vlm_4bit": True,
          "embed_model": "nlpai-lab/KURE-v1", "seg_len_sec": 5,
          "static_threshold": 0, "abstention_tau": 0.55,
          "caption_prompt": "P0"}


def _cfg(tmp_path, **over):
    cfg = dict(DEPLOY)
    cfg.update({"paths": {"data": str(tmp_path / "data"),
                          "work": str(tmp_path / "work"),
                          "results": str(tmp_path / "results")}})
    cfg.update(over)
    return cfg


def _segments(n=4, seg_len=5):
    return {"n_segments": n, "segments": [
        {"idx": i, "start": i * seg_len, "end": (i + 1) * seg_len,
         "subtitle": f"자막 {i}", "caption": f"캡션 {i}",
         "motion_score": 0.5} for i in range(n)]}


def _index(cfg, video_id, n=4, text_hash=None, dim=8, mp4=True):
    w = Path(cfg["paths"]["work"]) / video_id
    (w / "frames").mkdir(parents=True, exist_ok=True)
    doc = _segments(n, cfg["seg_len_sec"])
    (w / "segments.json").write_text(json.dumps(doc, ensure_ascii=False),
                                     encoding="utf-8")
    for name in ("emb_sub", "emb_cap"):
        np.save(w / f"{name}.npy", np.zeros((n, dim), dtype=np.float32))
    (w / "meta.json").write_text(json.dumps(
        {"text_hash": text_hash or common.index_text_hash(doc),
         "embed_model": cfg["embed_model"], "n_segments": n}),
        encoding="utf-8")
    if mp4:
        d = Path(cfg["paths"]["data"]) / "videos"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{video_id}.mp4").write_bytes(b"\x00")
    return w


# ---- 배포 identity ---------------------------------------------------------

def test_deployment_identity_is_declared():
    for k, v in (("caption_model", "Qwen/Qwen2.5-VL-3B-Instruct"),
                 ("embed_model", "nlpai-lab/KURE-v1"),
                 ("vlm_4bit", True), ("seg_len_sec", 5),
                 ("static_threshold", 0)):
        assert D.DEPLOYMENT[k] == v, k
    assert D.DEPLOYMENT_ALPHA == 0.5


def test_alpha_must_be_the_deployment_value(tmp_path):
    cfg = _cfg(tmp_path)
    _index(cfg, "v")
    with pytest.raises(D.PreflightError) as e:
        D.preflight(cfg, "v", alpha=0.7)
    assert "alpha" in str(e.value)


def test_deployment_alpha_passes(tmp_path):
    cfg = _cfg(tmp_path)
    _index(cfg, "v")
    r = D.preflight(cfg, "v", alpha=0.5)
    assert r["ok"] is True and r["alpha"] == 0.5


def test_wrong_caption_model_is_refused(tmp_path):
    cfg = _cfg(tmp_path, caption_model="Qwen/Qwen3-VL-4B-Instruct")
    _index(cfg, "v")
    with pytest.raises(D.PreflightError) as e:
        D.preflight(cfg, "v", alpha=0.5)
    assert "caption_model" in str(e.value)


def test_wrong_quantization_is_refused(tmp_path):
    cfg = _cfg(tmp_path, vlm_4bit=False)
    _index(cfg, "v")
    with pytest.raises(D.PreflightError):
        D.preflight(cfg, "v", alpha=0.5)


def test_wrong_embed_model_is_refused(tmp_path):
    cfg = _cfg(tmp_path, embed_model="BAAI/bge-m3")
    _index(cfg, "v")
    with pytest.raises(D.PreflightError):
        D.preflight(cfg, "v", alpha=0.5)


def test_static_threshold_change_is_refused(tmp_path):
    """치환 off는 dev 실측 확정값이다."""
    cfg = _cfg(tmp_path, static_threshold=0.2)
    _index(cfg, "v")
    with pytest.raises(D.PreflightError):
        D.preflight(cfg, "v", alpha=0.5)


# ---- 인덱스 존재·정합 -----------------------------------------------------

def test_missing_index_is_refused(tmp_path):
    cfg = _cfg(tmp_path)
    Path(cfg["paths"]["work"]).mkdir(parents=True)
    with pytest.raises(D.PreflightError) as e:
        D.preflight(cfg, "nope", alpha=0.5)
    assert "인덱스" in str(e.value)


@pytest.mark.parametrize("missing", ["segments.json", "emb_sub.npy",
                                     "emb_cap.npy", "meta.json"])
def test_each_required_artifact_is_checked(tmp_path, missing):
    cfg = _cfg(tmp_path)
    w = _index(cfg, "v")
    (w / missing).unlink()
    with pytest.raises(D.PreflightError) as e:
        D.preflight(cfg, "v", alpha=0.5)
    assert missing in str(e.value)


def test_stale_text_hash_is_refused(tmp_path):
    """재캡셔닝 후 m4 미실행 — M5가 던지기 전에 preflight가 막는다."""
    cfg = _cfg(tmp_path)
    _index(cfg, "v", text_hash="0" * 64)
    with pytest.raises(D.PreflightError) as e:
        D.preflight(cfg, "v", alpha=0.5)
    assert "text_hash" in str(e.value)


def test_embedding_row_count_must_match_segments(tmp_path):
    cfg = _cfg(tmp_path)
    w = _index(cfg, "v", n=4)
    np.save(w / "emb_cap.npy", np.zeros((3, 8), dtype=np.float32))
    with pytest.raises(D.PreflightError) as e:
        D.preflight(cfg, "v", alpha=0.5)
    assert "행 수" in str(e.value)


def test_embedding_dims_must_match_each_other(tmp_path):
    cfg = _cfg(tmp_path)
    w = _index(cfg, "v", n=4, dim=8)
    np.save(w / "emb_sub.npy", np.zeros((4, 16), dtype=np.float32))
    with pytest.raises(D.PreflightError):
        D.preflight(cfg, "v", alpha=0.5)


def test_index_embed_model_mismatch_is_refused(tmp_path):
    """인덱스를 만든 임베딩 모델과 지금 config가 다르면 점수가 무의미하다."""
    cfg = _cfg(tmp_path)
    w = _index(cfg, "v")
    m = json.loads((w / "meta.json").read_text(encoding="utf-8"))
    m["embed_model"] = "BAAI/bge-m3"
    (w / "meta.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(D.PreflightError) as e:
        D.preflight(cfg, "v", alpha=0.5)
    assert "embed_model" in str(e.value)


# ---- 재생 대상 ------------------------------------------------------------

def test_missing_mp4_is_reported_not_fatal(tmp_path):
    """재생은 못 하지만 검색은 된다 — 경고로 남기고 막지 않는다."""
    cfg = _cfg(tmp_path)
    _index(cfg, "v", mp4=False)
    r = D.preflight(cfg, "v", alpha=0.5)
    assert r["ok"] is True
    assert any("재생" in w for w in r["warnings"])
    assert r["playback_available"] is False


def test_playback_available_when_mp4_present(tmp_path):
    cfg = _cfg(tmp_path)
    _index(cfg, "v")
    assert D.preflight(cfg, "v", alpha=0.5)["playback_available"] is True


# ---- 보고 내용 ------------------------------------------------------------

def test_report_records_identity_and_counts(tmp_path):
    cfg = _cfg(tmp_path)
    _index(cfg, "v", n=4)
    r = D.preflight(cfg, "v", alpha=0.5)
    assert r["video_id"] == "v" and r["n_segments"] == 4
    assert r["caption_model"] == DEPLOY["caption_model"]
    assert r["embed_model"] == DEPLOY["embed_model"]
    assert r["text_hash"] and len(r["text_hash"]) == 64
    assert r["device"] in ("cuda", "cpu")
    assert r["checks_passed"] >= 8


def test_report_lists_available_videos(tmp_path):
    cfg = _cfg(tmp_path)
    _index(cfg, "a")
    _index(cfg, "b")
    assert D.available_videos(cfg) == ["a", "b"]


# ---- 연구 경계 ------------------------------------------------------------

def test_demo_refuses_test_split_videos(tmp_path):
    """test 영상으로 데모를 돌리지 않는다 — 공표된 결과 인용만 허용한다."""
    cfg = _cfg(tmp_path)
    _index(cfg, "panibottle_vietnam1")
    with pytest.raises(D.PreflightError) as e:
        D.preflight(cfg, "panibottle_vietnam1", alpha=0.5)
    assert "test" in str(e.value)


def test_test_video_ids_are_declared():
    assert set(D.TEST_SPLIT_VIDEOS) == {
        "gemini_promo", "itsub_viral_gadgets", "panibottle_vietnam1",
        "yunnamnopo_tongyeong"}


def test_module_does_not_import_evaluation_or_research_paths():
    import ast
    src = (ROOT / "scripts" / "demo.py").read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not ({"m6_evaluate", "m9_report_eval", "p2_retrieve", "p2_evaluate",
                 "p3_design_sensitivity"} & mods)

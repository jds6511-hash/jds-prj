"""배포 identity가 **선언이 아니라 런타임에서** 강제되는지 본다.

`scripts/demo.py`는 preflight에서 caption_model·vlm_4bit·α를 대조하지만,
컴포넌트 진입점(`m5_search`·`m7_demo`·`m7_webui`)을 직접 실행하면 그 대조를
거치지 않는다. 여기서 막는 것은 셋이다.

1. **인덱스 ↔ config 캡션 identity** — `text_hash`는 "captions와 embeddings가
   같은 시점인가"만 본다. **어느 모델이 그 캡션을 썼는가는 보지 않는다.**
   4B로 만든 인덱스를 3B config로 읽어도 두 해시가 모두 맞으므로 통과한다.
2. **α 값 범위** — CLI `--alpha`에 검증이 없어 1.5·NaN도 그대로 가중합에 들어간다.
3. **자격 경계** — `m7_demo`가 요청 경로 guard 없이 임의 video_id를 연다.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import common  # noqa: E402
import m7_demo  # noqa: E402
from m5_search import VideoIndex, combine_scores  # noqa: E402

MODEL_3B = "Qwen/Qwen2.5-VL-3B-Instruct"
MODEL_4B = "Qwen/Qwen3-VL-4B-Instruct"
PROMPT = "이 장면을 한 문장의 한국어로 묘사하라."


def _index(tmp_path, provenance=None, video_id="v1"):
    wdir = tmp_path / video_id
    wdir.mkdir()
    segments = [{"idx": i, "start": i * 5, "end": i * 5 + 5, "subtitle": "s",
                 "caption": "c", "is_static": False, "motion_score": 0.5}
                for i in range(3)]
    doc = {"n_segments": 3, "segments": segments}
    if provenance is not None:
        doc["caption_provenance"] = provenance
    common.save_segments(wdir / "segments.json", doc)
    np.save(wdir / "emb_sub.npy", np.zeros((3, 4), dtype=np.float32))
    np.save(wdir / "emb_cap.npy", np.zeros((3, 4), dtype=np.float32))
    (wdir / "meta.json").write_text(
        json.dumps({"embed_model": "m", "dim": 4, "n_segments": 3}),
        encoding="utf-8")
    return wdir


def _cfg(tmp_path, caption_model=MODEL_3B, prompt=PROMPT):
    return {"embed_model": "m", "static_threshold": 0, "seg_len_sec": 5,
            "caption_model": caption_model, "caption_prompt": prompt,
            "paths": {"work": str(tmp_path)}}


def _prov(model=MODEL_3B, prompt=PROMPT):
    import hashlib
    return {"config_caption_model": model, "model_id": model,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()}


# ------------------------------------------------- 인덱스 ↔ config 캡션 identity

def test_load_rejects_index_built_by_a_different_caption_model(tmp_path):
    """4B가 만든 인덱스를 3B config로 열면 실패해야 한다.

    이것이 통과하면 발표·보고서의 "3B 배포" 주장이 산출물로 뒷받침되지 않는다.
    """
    _index(tmp_path, provenance=_prov(model=MODEL_4B))
    with pytest.raises(ValueError, match="캡션 모델 불일치"):
        VideoIndex.load(_cfg(tmp_path, caption_model=MODEL_3B), "v1")


def test_load_rejects_index_built_with_a_different_prompt(tmp_path):
    """P0는 동결 프롬프트다 — 다른 프롬프트로 만든 캡션은 다른 arm이다."""
    _index(tmp_path, provenance=_prov(prompt="다른 프롬프트"))
    with pytest.raises(ValueError, match="캡션 프롬프트 불일치"):
        VideoIndex.load(_cfg(tmp_path), "v1")


def test_load_accepts_matching_provenance(tmp_path):
    _index(tmp_path, provenance=_prov())
    assert len(VideoIndex.load(_cfg(tmp_path), "v1").segments) == 3


def test_load_accepts_legacy_index_without_provenance(tmp_path):
    """확정 인덱스 11편은 provenance 도입 이전 산출물이다 — 재색인 없이는 채울 수 없다.

    하위호환을 유지하되, **증거가 있는 인덱스는 반드시 검사**한다.
    감사 문서에 '11편은 검사 대상 밖'으로 남긴다.
    """
    _index(tmp_path, provenance=None)
    assert len(VideoIndex.load(_cfg(tmp_path), "v1").segments) == 3


def test_load_skips_check_when_config_has_no_caption_model(tmp_path):
    """평가·유닛 테스트용 최소 cfg를 깨뜨리지 않는다."""
    _index(tmp_path, provenance=_prov())
    cfg = _cfg(tmp_path)
    del cfg["caption_model"]
    del cfg["caption_prompt"]
    assert len(VideoIndex.load(cfg, "v1").segments) == 3


# ------------------------------------------------------------------- α 범위

@pytest.mark.parametrize("alpha", [1.5, -0.1, float("nan")])
def test_combine_scores_rejects_alpha_outside_unit_interval(alpha):
    s = np.array([0.1, 0.2, 0.3])
    with pytest.raises(ValueError, match="alpha"):
        combine_scores(s, s.copy(), np.zeros(3, dtype=bool), alpha)


@pytest.mark.parametrize("alpha", [0.0, 0.5, 1.0])
def test_combine_scores_accepts_the_grid_endpoints(alpha):
    s = np.array([0.1, 0.2, 0.3])
    out = combine_scores(s, s.copy(), np.zeros(3, dtype=bool), alpha)
    assert out.shape == (3,)


# ------------------------------------------------- 선언이 여러 곳에 있으면 표류한다

def test_e2e_runner_identity_matches_the_demo_entrypoint():
    """배포 identity 선언이 `scripts/demo.py`와 `scripts/e2e_external.py` 둘에 있다.

    합치는 것은 리팩터링이라 발표 전에는 하지 않는다 — 대신 **어긋나면 여기서 깨진다**.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import demo
    import e2e_external as E
    for k, v in demo.DEPLOYMENT.items():
        assert E.DEPLOYMENT_IDENTITY[k] == v, k
    assert E.DEPLOYMENT_IDENTITY["alpha"] == demo.DEPLOYMENT_ALPHA


def test_e2e_runner_knows_every_research_split_video():
    """E2E가 연구 영상 이름을 재사용하면 loader가 나중에 섞어 읽는다.

    test split 목록은 `eligibility`가 단일 출처인데 이 집합은 별도로 적혀 있다 —
    한쪽만 늘어나는 것을 막는다.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import eligibility
    import e2e_external as E
    assert set(eligibility.TEST_SPLIT_VIDEOS) <= set(E.RESEARCH_VIDEO_IDS)


# ------------------------------------------------------- m7_demo 자격 경계

def test_m7_demo_refuses_test_split_video(monkeypatch):
    """`scripts/demo.py`를 우회해도 test split 영상은 열리지 않는다."""
    import eligibility
    monkeypatch.setattr(sys, "argv",
                        ["m7_demo", "--video-id", eligibility.TEST_SPLIT_VIDEOS[0],
                         "--alpha", "0.5"])
    with pytest.raises(SystemExit) as e:
        m7_demo.main()
    assert "test split" in str(e.value)

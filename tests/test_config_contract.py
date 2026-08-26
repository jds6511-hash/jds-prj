"""**키가 없어도 조용히 돌아가는 경로**를 막는다.

`cfg.get(key, default)`는 키가 없으면 기본값으로 실행을 계속한다. 그중 결과·정체성을
바꾸는 값이 있으면, 그 실행이 무슨 구성이었는지 사후에 알 수 없다. 2026-08-26
fallback 감사에서 역할별 필수 키를 확정하고 여기서 고정한다.

**기본값 자체를 바꾸지 않는다** — 현재 동작을 명시적으로 고정하는 것이 목적이다.
따라서 아래 테스트는 "빠지면 실패한다"와 "현재 기본값이 이 값이다" 둘을 함께 잡는다.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import common  # noqa: E402
import deployment  # noqa: E402
import m3_generate  # noqa: E402
import m7_webui  # noqa: E402


def _full_cfg(tmp_path=None):
    cfg = {
        "caption_model": "Qwen/Qwen2.5-VL-3B-Instruct", "vlm_4bit": True,
        "caption_prompt": "P0", "vlm_max_pixels": 1003520,
        "vlm_max_new_tokens": 128, "vlm_rep_penalty": 1.05,
        "caption_normalize_cjk": False, "caption_truncate_incomplete": False,
        "embed_model": "nlpai-lab/KURE-v1", "embed_batch_size": 32,
        "seg_len_sec": 5, "static_threshold": 0, "abstention_tau": 0.55,
    }
    if tmp_path is not None:
        cfg["paths"] = {"data": str(tmp_path), "work": str(tmp_path),
                        "results": str(tmp_path)}
    return cfg


# ------------------------------------------------------ A. 필수 키 누락 → 실패

@pytest.mark.parametrize("role,key", [
    (role, key) for role, keys in deployment.REQUIRED_KEYS.items() for key in keys])
def test_missing_required_key_fails_closed(role, key):
    cfg = _full_cfg()
    cfg.pop(key)
    with pytest.raises(deployment.ConfigContractError, match=key):
        deployment.validate_production_config(cfg, roles=(role,))


def test_full_config_passes_every_role():
    cfg = _full_cfg()
    for role in deployment.REQUIRED_KEYS:
        assert deployment.validate_production_config(cfg, roles=(role,)) > 0


def test_unknown_role_is_rejected():
    with pytest.raises(deployment.ConfigContractError, match="역할"):
        deployment.validate_production_config(_full_cfg(), roles=("없는역할",))


def test_the_shipped_config_satisfies_every_role():
    """저장소의 config.yaml이 모든 역할 계약을 만족해야 한다 — 안 그러면 배포가 막힌다."""
    cfg = common.load_config(ROOT / "config.yaml")
    for role in deployment.REQUIRED_KEYS:
        deployment.validate_production_config(cfg, roles=(role,))


# ------------------------------------- B~D. 값이 틀리면 실패 (진입점 대조)

def test_wrong_alpha_is_rejected(tmp_path):
    import demo
    with pytest.raises(demo.PreflightError, match="배포 확정값"):
        demo.preflight(_full_cfg(tmp_path), "gwaktube_soviet_apartment", alpha=0.3)


@pytest.mark.parametrize("key,bad", [
    ("caption_model", "Qwen/Qwen3-VL-4B-Instruct"),
    ("embed_model", "BAAI/bge-m3"),
    ("seg_len_sec", 10),
    ("vlm_4bit", False),
    ("static_threshold", 0.05),
])
def test_wrong_identity_value_is_rejected(tmp_path, key, bad):
    import demo
    cfg = _full_cfg(tmp_path)
    cfg[key] = bad
    with pytest.raises(demo.PreflightError, match=key):
        demo.preflight(cfg, "gwaktube_soviet_apartment", alpha=deployment.ALPHA)


# ------------------------------------- E. 생성 조건 누락 → 캡션 경로가 멈춘다

@pytest.mark.parametrize("key", ["vlm_max_new_tokens", "vlm_rep_penalty",
                                 "caption_normalize_cjk",
                                 "caption_truncate_incomplete"])
def test_caption_generation_stops_when_a_generation_setting_is_missing(
        tmp_path, monkeypatch, key):
    """토큰 상한·후처리 플래그는 캡션 문자열을 바꾼다 — 조용한 기본값을 허용하지 않는다.

    실측 근거: 3B 캡션 57/395가 공용 상한 128 토큰에 닿아 문장이 끊겼다.
    """
    cfg = _full_cfg(tmp_path)
    cfg.pop(key)
    monkeypatch.setattr(common, "load_config", lambda p: cfg)
    monkeypatch.setattr(sys, "argv", ["m3_generate.py", "--video-id", "v1",
                                      "--captions-only"])
    monkeypatch.setattr(m3_generate, "load_vlm",
                        lambda c: pytest.fail("config 검증 전에 모델을 올렸다"))
    with pytest.raises(SystemExit) as e:
        m3_generate.main()
    assert key in str(e.value)


def test_generation_defaults_are_unchanged():
    """감사가 기본값을 바꾸지 않았다는 것을 고정한다."""
    src = (ROOT / "src/m3_generate.py").read_text(encoding="utf-8")
    assert 'cfg.get("vlm_max_new_tokens", 128)' in src
    assert 'cfg.get("vlm_rep_penalty", 1.0)' in src
    assert m3_generate.DEFAULT_BEAM_SIZE == 5


def test_caption_provenance_records_the_settings_that_change_text(tmp_path):
    """캡션 문자열을 바꾸는 값은 산출물에 남아야 한다 — 후처리 플래그가 빠져 있었다."""
    cfg = _full_cfg(tmp_path)
    prov = m3_generate.caption_provenance(cfg, model=None, prompt=cfg["caption_prompt"],
                                          entrypoint="test")
    for key in ("caption_model", "vlm_max_new_tokens", "vlm_rep_penalty",
                "caption_normalize_cjk", "caption_truncate_incomplete"):
        assert f"config_{key}" in prov, key
    assert prov["prompt_sha256"]


def test_stt_beam_size_is_part_of_the_transcription_cache_key():
    """빔만 바꿔도 캐시가 적중하면 옛 전사를 '차이 없음'으로 읽는다."""
    src = (ROOT / "src/m3_generate.py").read_text(encoding="utf-8")
    assert '"beam_size": beam_size' in src
    assert 'cfg.get("stt_beam_size", DEFAULT_BEAM_SIZE)' in src


# ---------------------------------- F. abstention_tau 부재의 기대 동작 고정

def test_search_entrypoints_require_abstention_tau():
    for role in ("search",):
        assert "abstention_tau" in deployment.REQUIRED_KEYS[role]


def test_low_relevance_is_computed_in_one_place():
    """응답과 로그가 같은 함수를 쓴다 — 같은 수식을 두 번 적으면 또 갈라진다."""
    src = (ROOT / "src/m7_webui.py").read_text(encoding="utf-8")
    assert src.count("raw_sub_max") == 1, "판정식이 여러 곳에 있다"
    assert "def low_relevance_flag" in src


@pytest.mark.parametrize("sub,cap,tau,want", [
    (0.40, 0.50, 0.48, False),   # cap이 넘긴다 → 경고 없음
    (0.40, 0.30, 0.48, True),
    (0.60, 0.10, 0.48, False),
])
def test_low_relevance_flag_uses_max_of_both_channels(sub, cap, tau, want):
    stats = {"raw_sub_max": sub, "raw_cap_max": cap}
    assert m7_webui.low_relevance_flag(stats, tau) is want


def test_low_relevance_flag_returns_none_without_tau():
    """τ가 없으면 판정 자체를 하지 않는다 — False로 적으면 '경고 없음'과 구별되지 않는다."""
    assert m7_webui.low_relevance_flag({"raw_sub_max": 0.1, "raw_cap_max": 0.1},
                                       None) is None


# ------------------------ seg_len 기본값이 우연히 맞아떨어지는 구조인지

def test_every_load_segments_call_passes_seg_len_explicitly():
    """`load_segments(seg_len=5)` 기본값에 의존하는 호출부가 없어야 한다.

    기본값 5는 현재 배포와 같아서 **우연히 맞는다**. seg_len ablation처럼 5가 아닌
    config에서 호출부가 인자를 빼면 불변식 검증이 엉뚱한 격자로 돌아간다.
    AST로 훑는다 — 문자열 검사로는 여러 줄 호출을 놓친다.
    """
    offenders = []
    for path in list((ROOT / "src").glob("*.py")) + list((ROOT / "scripts").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            name = getattr(f, "attr", None) or getattr(f, "id", None)
            if name != "load_segments":
                continue
            if not any(k.arg == "seg_len" for k in node.keywords):
                offenders.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}")
    assert offenders == [], f"seg_len 미지정 호출: {offenders}"


def test_load_segments_validates_the_grid_it_was_given():
    """넘긴 seg_len과 artifact의 start가 어긋나면 로드가 실패한다."""
    import json
    doc = {"n_segments": 2, "segments": [
        {"idx": 0, "start": 0, "end": 5, "subtitle": "", "caption": ""},
        {"idx": 1, "start": 5, "end": 10, "subtitle": "", "caption": ""}]}
    p = ROOT / "tests" / "_tmp_seg_grid.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    try:
        assert common.load_segments(p, seg_len=5)["n_segments"] == 2
        with pytest.raises(ValueError, match="불변식 위반"):
            common.load_segments(p, seg_len=10)
    finally:
        p.unlink()


# ------------------------ G. 지원 진입점이 같은 검증을 통과한다

@pytest.mark.parametrize("path", [p for p, m in deployment.SUPPORTED_ENTRYPOINTS.items()
                                  if "eligibility" in m["enforces"]])
def test_search_entrypoints_validate_the_config(path):
    src = (ROOT / path).read_text(encoding="utf-8")
    assert "validate_production_config" in src, path


def test_pipeline_entrypoints_validate_their_role():
    for path, role in (("src/m3_generate.py", "caption_generation"),
                       ("src/m4_index.py", "index")):
        src = (ROOT / path).read_text(encoding="utf-8")
        assert "validate_production_config" in src, path
        assert role in src, path

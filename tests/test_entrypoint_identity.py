"""**공식 지원 진입점마다** 배포 identity가 같게 강제되는지 본다.

감사에서 드러난 것: `scripts/demo.py`만 α=0.5를 강제했고, README가 함께 안내하는
`python src/m7_webui.py --alpha 0.7`은 그대로 떴다. 즉 **진입점을 바꾸면 배포 구성이
아닌 UI가 production처럼 보였다.**

그래서 지원 진입점 목록을 `src/deployment.py`에 두고, 각 진입점이 선언한 `enforces`가
실제로 동작하는지 여기서 확인한다. 목록에 항목을 추가하고 구현을 잊으면 깨진다.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import deployment  # noqa: E402


def test_identity_has_a_single_source():
    """demo.py·e2e_external.py가 사본을 다시 들고 있으면 표류한다."""
    import demo
    import e2e_external as E
    assert demo.DEPLOYMENT is deployment.DEPLOYMENT
    assert demo.DEPLOYMENT_ALPHA == deployment.ALPHA
    for k, v in deployment.DEPLOYMENT.items():
        assert E.DEPLOYMENT_IDENTITY[k] == v, k
    assert E.DEPLOYMENT_IDENTITY["alpha"] == deployment.ALPHA


def test_declared_entrypoints_exist():
    for path in deployment.SUPPORTED_ENTRYPOINTS:
        assert (ROOT / path).is_file(), path


def test_deployment_values_are_the_frozen_ones():
    assert deployment.DEPLOYMENT == {
        "caption_model": "Qwen/Qwen2.5-VL-3B-Instruct",
        "vlm_4bit": True,
        "embed_model": "nlpai-lab/KURE-v1",
        "seg_len_sec": 5,
        "static_threshold": 0,
    }
    assert deployment.ALPHA == 0.5


# ------------------------------------------------------------ α 강제

@pytest.mark.parametrize("alpha", [0.7, 0.0, 1.0])
def test_check_alpha_rejects_nondeployment_values(alpha):
    with pytest.raises(deployment.DeploymentIdentityError, match="배포 확정값"):
        deployment.check_alpha(alpha)


@pytest.mark.parametrize("alpha", [1.5, -0.1, float("nan")])
def test_check_alpha_rejects_out_of_range_even_when_opted_out(alpha):
    with pytest.raises(deployment.DeploymentIdentityError):
        deployment.check_alpha(alpha, allow_nondeployment=True)


def test_check_alpha_opt_out_is_explicit():
    assert deployment.check_alpha(0.7, allow_nondeployment=True) == 0.7
    assert deployment.check_alpha(deployment.ALPHA) == deployment.ALPHA


ALPHA_OPTIONAL = [p for p, m in deployment.SUPPORTED_ENTRYPOINTS.items()
                  if "alpha" in m["enforces"]]
ALPHA_STRICT = [p for p, m in deployment.SUPPORTED_ENTRYPOINTS.items()
                if "alpha_strict" in m["enforces"]]


@pytest.mark.parametrize("path", ALPHA_OPTIONAL)
def test_alpha_enforcing_entrypoints_refuse_nondeployment_alpha(path, monkeypatch):
    """`enforces`에 alpha를 적은 진입점은 실제로 거부해야 한다."""
    mod = __import__(Path(path).stem)
    argv = [Path(path).name, "--alpha", "0.7"]
    if path == "src/m7_demo.py":
        argv += ["--video-id", "gwaktube_soviet_apartment"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as e:
        mod.main()
    assert "배포 확정값" in str(e.value), str(e.value)


@pytest.mark.parametrize("path", ALPHA_OPTIONAL)
def test_alpha_enforcing_entrypoints_declare_the_opt_out_flag(path):
    src = (ROOT / path).read_text(encoding="utf-8")
    assert "allow-nondeployment-alpha" in src, path


@pytest.mark.parametrize("path", ALPHA_STRICT)
def test_strict_entrypoints_have_no_alpha_opt_out(path, tmp_path):
    """배포 진입점에는 우회 플래그가 없어야 한다 — 있으면 그게 우회 경로다."""
    src = (ROOT / path).read_text(encoding="utf-8")
    assert "allow-nondeployment-alpha" not in src, path
    import demo
    with pytest.raises(demo.PreflightError, match="배포 확정값"):
        demo.preflight({"paths": {"work": str(tmp_path)}}, "gwaktube_soviet_apartment",
                       alpha=0.7)


def test_webui_starts_with_the_deployment_alpha(monkeypatch, tmp_path):
    """배포 α면 통과해 서버 기동 단계까지 간다 — 거부가 과하지 않은지 확인한다."""
    import common
    import m7_webui
    started = {}
    monkeypatch.setattr(common, "load_config",
                        lambda p: {"seg_len_sec": 5, "embed_model": "m",
                                   "abstention_tau": 0.55, "static_threshold": 0,
                                   "paths": {"data": str(tmp_path),
                                             "work": str(tmp_path),
                                             "results": str(tmp_path)}})
    import uvicorn
    monkeypatch.setattr(uvicorn, "run",
                        lambda app, **kw: started.update(kw))
    monkeypatch.setattr(sys, "argv", ["m7_webui.py", "--alpha", "0.5",
                                      "--port", "7999"])
    m7_webui.main()
    assert started["port"] == 7999


# ------------------------------------------------- eligibility 강제

ELIGIBILITY_ENFORCING = [p for p, m in deployment.SUPPORTED_ENTRYPOINTS.items()
                         if "eligibility" in m["enforces"]]


@pytest.mark.parametrize("path", ELIGIBILITY_ENFORCING)
def test_eligibility_enforcing_entrypoints_reference_the_policy_module(path):
    src = (ROOT / path).read_text(encoding="utf-8")
    assert "eligibility" in src, path


def test_m7_demo_refuses_restricted_video_before_touching_the_index(monkeypatch):
    import eligibility
    import m7_demo
    monkeypatch.setattr(sys, "argv", ["m7_demo.py", "--alpha", "0.5",
                                      "--video-id", eligibility.TEST_SPLIT_VIDEOS[0]])
    from m5_search import VideoIndex
    monkeypatch.setattr(VideoIndex, "load", classmethod(
        lambda cls, *a, **k: pytest.fail("자격 판정 전에 인덱스를 읽었다")))
    with pytest.raises(SystemExit) as e:
        m7_demo.main()
    assert "test split" in str(e.value)


# ------------------------------------------------- test_opening 강제

OPENING_ENFORCING = [p for p, m in deployment.SUPPORTED_ENTRYPOINTS.items()
                     if "test_opening" in m["enforces"]]


@pytest.mark.parametrize("path", OPENING_ENFORCING)
def test_test_opening_entrypoints_require_a_reason(path):
    src = (ROOT / path).read_text(encoding="utf-8")
    assert "--test-opening" in src or "test_opening" in src, path
    assert "절대규칙 1" in src, path

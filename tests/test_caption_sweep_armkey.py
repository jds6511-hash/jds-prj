"""캡션 스윕의 arm 식별자 — 토큰 상한 덮어쓰기가 캡션 캐시와 섞이면 안 된다.

절단율이 높은 arm(P2 44.4% 실측)을 상한을 올려 재측정할 때, 키가 안 갈리면
128토큰으로 만든 캡션을 그대로 재사용해서 "상한을 올려도 안 변한다"는 완전히
틀린 결론이 나온다. 그 회귀만 막는다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs/probes"))
from caption_model_sweep import arm_key                    # noqa: E402

DEFAULT = 128


def test_no_override_keeps_plain_key():
    assert arm_key("P0", None, DEFAULT) == "P0"


def test_override_equal_to_default_keeps_plain_key():
    """같은 값을 명시했을 뿐인데 키가 갈리면 기존 캡션을 헛되이 재생성한다."""
    assert arm_key("P0", DEFAULT, DEFAULT) == "P0"


def test_override_splits_the_key():
    assert arm_key("P0", 512, DEFAULT) == "P0@512"


def test_distinct_overrides_do_not_collide():
    keys = {arm_key("P2", n, DEFAULT) for n in (None, 256, 512)}
    assert len(keys) == 3


def test_sweep_records_effective_precision_and_vram_axes():
    """정밀도가 주 판정인 배치에서 **실효 양자화**를 남기지 않으면 arm 정체성을
    증명할 수 없다(2026-08-18 prec3_0818a). provenance는 production과 같은 함수로
    읽고, VRAM은 baseline/peak/incremental 3축으로 남긴다."""
    src = (ROOT / "docs" / "probes" / "caption_model_sweep.py").read_text(
        encoding="utf-8")
    assert "from m3_generate import caption_provenance" in src
    for k in ('"provenance": _arm_provenance(', '"generation_failures"',
              '"server_vram_baseline_gb"', '"server_incremental_peak_vram_gb"',
              '"expected_captions"'):
        assert k in src, k
    # arm 경계: 정리 → baseline → peak reset → load 순서여야 한다
    assert src.index("_vram_arm_boundary()") < src.index("cap, close = load_captioner")
    assert "cap.model = locals().get(\"model\")" in src


def test_gen_captions_counts_failures():
    """실패를 빈 문자열로 조용히 넘기면 그 arm이 완주한 것처럼 보인다."""
    src = (ROOT / "docs" / "probes" / "caption_model_sweep.py").read_text(
        encoding="utf-8")
    assert '"failed": failed' in src and '"fail_reasons": fail_reasons' in src
    assert "except Exception as e:" in src

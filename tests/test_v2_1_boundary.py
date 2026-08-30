"""A-07 BoundaryProvider interface + registry.

티켓: `docs/finalization/V2_1_GATE_A_TICKETS_2026-08-30.md` A-07
범위: provider 선택 · identity · config provenance · **silent fallback 금지**
아님: fixed window 알고리즘 자체 (A-08)

핵심은 하나다. **경계를 누가 어떤 설정으로 정했는지가 결과에 남아야 하고,
그 provider가 실패했을 때 조용히 다른 것으로 바뀌면 안 된다.**
"""
import re
from pathlib import Path

import pytest

from v2_1_boundary import (
    DEFAULT_PROVIDER_NAME,
    BoundaryResult,
    ProviderError,
    ProviderRegistry,
    UnknownProviderError,
)
from v2_1_fixtures import scenario

SRC = Path(__file__).resolve().parents[1] / "src/v2_1_boundary.py"


class _Stub:
    """A-08 이전에 인터페이스만 시험하기 위한 대역."""

    name = "stub_v0"
    version = "0"

    def __init__(self, positions=(0, 4, 8), fail=False):
        self._positions = list(positions)
        self._fail = fail

    def __call__(self, segments, *, caption_embeddings=None, boundary_signal=None,
                 config=None):
        if self._fail:
            raise ProviderError("stub refused")
        return BoundaryResult(
            provider_name=self.name,
            provider_version=self.version,
            provider_config=dict(config or {}),
            boundary_positions=list(self._positions),
        )


@pytest.fixture
def registry():
    r = ProviderRegistry()
    r.register(_Stub())
    return r


@pytest.fixture
def segments():
    return scenario("S1").segments


# ── BPI-001 provider identity ────────────────────────────────────────────
def test_bpi_001_provider_identity_is_recorded(registry, segments):
    result = registry.run("stub_v0", segments)
    assert result.provider_name == "stub_v0"
    assert result.provider_version == "0"


def test_bpi_001_result_is_immutable(registry, segments):
    result = registry.run("stub_v0", segments)
    with pytest.raises(Exception):
        result.provider_name = "other"


# ── BPI-002 config provenance ────────────────────────────────────────────
def test_bpi_002_config_is_recorded(registry, segments):
    result = registry.run("stub_v0", segments, config={"window_sec": 5})
    assert result.provider_config == {"window_sec": 5}


def test_bpi_002_absent_config_is_recorded_as_empty_not_missing(registry, segments):
    assert registry.run("stub_v0", segments).provider_config == {}


# ── BPI-003 caption embedding semantics ──────────────────────────────────
def test_bpi_003_embeddings_are_named_caption_not_visual():
    """`emb_cap.npy`는 caption **텍스트** 임베딩이다. 시각 임베딩이 아니다."""
    src = SRC.read_text(encoding="utf-8")
    assert "caption_embeddings" in src
    for forbidden in ("visual_embedding", "visual_emb", "image_embedding"):
        assert forbidden not in src, "임베딩을 시각으로 표기했다: " + forbidden


def test_bpi_003_provider_receives_embeddings_by_that_name(registry, segments):
    seen = {}

    class Named:
        name, version = "named_v0", "0"

        def __call__(self, segments, *, caption_embeddings=None,
                     boundary_signal=None, config=None):
            seen["caption_embeddings"] = caption_embeddings
            return BoundaryResult(self.name, self.version, {}, [0])

    registry.register(Named())
    registry.run("named_v0", segments, caption_embeddings=[[0.1], [0.2]])
    assert seen["caption_embeddings"] == [[0.1], [0.2]]


# ── BPI-004 default is explicit ──────────────────────────────────────────
def test_bpi_004_default_provider_name_is_fixed_window_v1():
    assert DEFAULT_PROVIDER_NAME == "fixed_window_v1"


def test_bpi_004_unspecified_provider_resolves_to_the_default(registry, segments):
    registry.register(_Stub(), name=DEFAULT_PROVIDER_NAME)
    assert registry.run(None, segments).provider_name == "stub_v0"


def test_bpi_004_missing_default_is_an_explicit_error(registry, segments):
    """default가 등록돼 있지 않으면 아무거나 고르지 않고 실패한다."""
    with pytest.raises(UnknownProviderError, match=DEFAULT_PROVIDER_NAME):
        registry.run(None, segments)


# ── BPI-005 no silent substitution ───────────────────────────────────────
def test_bpi_005_provider_failure_is_not_replaced(registry, segments):
    registry.register(_Stub(fail=True), name="broken_v0")
    with pytest.raises(ProviderError, match="stub refused"):
        registry.run("broken_v0", segments)


def test_bpi_005_unknown_provider_does_not_fall_back(registry, segments):
    registry.register(_Stub(), name=DEFAULT_PROVIDER_NAME)
    with pytest.raises(UnknownProviderError, match="nope_v9"):
        registry.run("nope_v9", segments)


def test_bpi_005_source_has_no_fallback_path():
    src = SRC.read_text(encoding="utf-8")
    for forbidden in ("except ProviderError", "fallback", "or DEFAULT_PROVIDER_NAME"):
        assert forbidden not in src, "대체 경로가 있다: " + forbidden


def test_bpi_005_registering_a_name_twice_is_refused(registry):
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_Stub())


# ── 결과 계약 ────────────────────────────────────────────────────────────
def test_boundary_positions_must_be_sorted_and_unique(registry, segments):
    registry.register(_Stub(positions=(4, 0, 4)), name="messy_v0")
    with pytest.raises(ProviderError, match="sorted"):
        registry.run("messy_v0", segments)


def test_boundary_positions_must_exist_in_the_segment_list(registry, segments):
    registry.register(_Stub(positions=(0, 999)), name="ghost_v0")
    with pytest.raises(ProviderError, match="unknown segment"):
        registry.run("ghost_v0", segments)


def test_first_boundary_must_be_the_first_segment(registry, segments):
    registry.register(_Stub(positions=(4, 8)), name="late_v0")
    with pytest.raises(ProviderError, match="first segment"):
        registry.run("late_v0", segments)


def test_a07_does_not_implement_the_window_algorithm():
    """알고리즘은 A-08 책임이다."""
    src = SRC.read_text(encoding="utf-8")
    for forbidden in ("window_sec", "5.0", "def fixed_window"):
        assert forbidden not in src, "A-08 책임을 침범했다: " + forbidden


def test_a07_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)

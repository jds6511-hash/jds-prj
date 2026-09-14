"""v2.1 BoundaryProvider interface + registry (A-07).

경계를 **누가 어떤 설정으로** 정했는지가 결과에 남는다. provider가 실패하면
거기서 멈춘다 — 조용히 다른 provider로 바꾸지 않는다. 자동 대체는 "무엇이
경계를 정했는가"를 사후에 알 수 없게 만든다.

알고리즘은 여기에 없다. `fixed_window_v1`은 A-08이 구현해 등록한다.

```
BoundaryProvider(segments, caption_embeddings=None, boundary_signal=None,
                 config=None) -> BoundaryResult
```

`caption_embeddings`는 **caption 텍스트** 임베딩이다(KURE-v1이 caption 문장을
임베딩한 `emb_cap.npy`). 시각 임베딩이 아니므로 그렇게 부르지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from v2_1_segments import CanonicalSegment

#: 명시하지 않았을 때 쓰는 provider. 암묵이 아니라 이름으로 고정한다.
DEFAULT_PROVIDER_NAME = "fixed_window_v1"


class ProviderError(RuntimeError):
    """provider 실행 실패 또는 결과 계약 위반. 대체하지 않고 그대로 올린다."""


class UnknownProviderError(ProviderError):
    """등록되지 않은 provider 이름."""


@dataclass(frozen=True, slots=True)
class BoundaryResult:
    """경계 하나의 산출물. 재현에 필요한 provenance를 같이 들고 다닌다."""

    provider_name: str
    provider_version: str
    provider_config: Mapping[str, Any]
    boundary_positions: Sequence[int]


def _check(result: BoundaryResult, segments: Sequence[CanonicalSegment]) -> None:
    """provider가 무엇을 냈든 계약을 통과해야 한다."""
    positions = list(result.boundary_positions)
    if not positions:
        raise ProviderError("no boundary positions")
    if positions != sorted(set(positions)):
        raise ProviderError("boundary positions must be sorted and unique")
    known = {s.segment_id for s in segments}
    unknown = [p for p in positions if p not in known]
    if unknown:
        raise ProviderError("unknown segment in boundaries: %r" % (unknown,))
    if positions[0] != segments[0].segment_id:
        raise ProviderError("boundaries must start at the first segment")


class ProviderRegistry:
    """이름 → provider. 조용한 대체가 불가능하도록 조회는 항상 실패하거나 맞는다."""

    def __init__(self) -> None:
        self._providers: dict[str, Any] = {}

    def register(self, provider: Any, *, name: str | None = None) -> None:
        key = name or provider.name
        if key in self._providers:
            raise ValueError("provider already registered: %s" % key)
        self._providers[key] = provider

    def get(self, name: str | None) -> Any:
        key = DEFAULT_PROVIDER_NAME if name is None else name
        try:
            return self._providers[key]
        except KeyError:
            raise UnknownProviderError("no such provider: %s" % key) from None

    def run(
        self,
        name: str | None,
        segments: Sequence[CanonicalSegment],
        *,
        caption_embeddings=None,
        boundary_signal=None,
        config: Mapping[str, Any] | None = None,
    ) -> BoundaryResult:
        """provider를 실행하고 결과 계약을 검사한다. 실패는 그대로 올린다."""
        provider = self.get(name)
        result = provider(
            segments,
            caption_embeddings=caption_embeddings,
            boundary_signal=boundary_signal,
            config=config,
        )
        _check(result, segments)
        return result

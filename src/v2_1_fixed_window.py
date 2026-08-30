"""v2.1 `fixed_window_v1` — 결정적 60초 시간 창 (A-08).

의미는 **"60초가 진짜 사건 경계다"가 아니다.**

> 의미적 경계를 확신할 수 없으므로 canonical 시간 partition을 단순하고 결정적인
> 방식으로 유지한다. 의미 구조는 표현 계층이 담당한다.

근거는 모델 대조 진단이다. 붕괴하지 않은 arm도 간격 10(50초)의 등차수열을 냈다
(Qwen `[110,120,130,140,150]` · Kanana `[225,245,255,265,275]`). 정상으로 보이는
출력조차 사실상 균등 분할이었으므로, 균등 분할을 모델에게 맡길 이유가 없다.

이 모듈은 segment 격자만 본다. 어떤 내용 채널도 읽지 않으므로 모델·재캡셔닝·
STT 교체가 시간축을 바꾸지 못한다.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from v2_1_boundary import DEFAULT_PROVIDER_NAME, BoundaryResult, ProviderError
from v2_1_segments import CanonicalSegment

#: canonical 창 길이. config로 덮어쓸 수 있지만 기본은 명시된 60초다.
WINDOW_SEC = 60.0


def window_spans(
    segments: Sequence[CanonicalSegment], window_sec: float = WINDOW_SEC
) -> list[tuple[int, int]]:
    """segment 격자를 창 단위 폐구간 `(start_id, end_id)`으로 나눈다.

    귀속 규칙은 하나다 — **segment의 시작 시각이 어느 창에 들어가는가.** 창
    경계에 걸친 segment도 시작 시각으로만 정해지므로 애매한 경우가 없다.
    마지막 창은 영상 끝에서 잘리므로 짧을 수 있다.
    """
    if not segments:
        raise ValueError("no segments")
    if window_sec <= 0:
        raise ValueError("window_sec must be > 0")

    origin = segments[0].start_sec
    spans: list[tuple[int, int]] = []
    current = None
    for segment in segments:
        index = int((segment.start_sec - origin) // window_sec)
        if index != current:
            spans.append((segment.segment_id, segment.segment_id))
            current = index
        else:
            start, _ = spans[-1]
            spans[-1] = (start, segment.segment_id)
    return spans


class FixedWindowV1:
    """BoundaryProvider 구현. 내용 채널 인자는 받되 쓰지 않는다."""

    name = DEFAULT_PROVIDER_NAME
    version = "1"

    def __call__(
        self,
        segments: Sequence[CanonicalSegment],
        *,
        caption_embeddings=None,
        boundary_signal=None,
        config: Mapping[str, Any] | None = None,
    ) -> BoundaryResult:
        if not segments:
            raise ProviderError("no segments")
        window_sec = float((config or {}).get("window_sec", WINDOW_SEC))
        try:
            spans = window_spans(segments, window_sec)
        except ValueError as exc:
            raise ProviderError(str(exc)) from None
        return BoundaryResult(
            provider_name=self.name,
            provider_version=self.version,
            provider_config={"window_sec": window_sec},
            boundary_positions=[start for start, _ in spans],
        )

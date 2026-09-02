"""v2.1 표현 실패 정책 — 표현만 줄이고 구조는 복구하지 않는다 (Gate C · C-08).

```
표현 실패   같은 semantic_view를 더 단순한 형식으로 직렬화한다        허용 (RPT-006)
구조 실패   새 구조를 만들어 살리지 않는다. 명시적으로 멈춘다         금지 (RPT-007)
약한 내용   구조·출처는 살아 있고 내용만 비어 있다                   실패가 아니다 (HLT-008)
```

fallback은 **한 방향으로만 흐른다.**

```
canonical → PresentationInput → Highlights → Synthesis → semantic_view → renderer
                                                                            ↓
                                                                  표현 fallback  ← 여기만
```

거슬러 올라가지 않는다 — highlight 재생성 · episode 재분할 · source 교체 ·
fixed-window 재실행 · 빈 구간을 합성 사건으로 채우기는 전부 금지다.

`STRUCTURAL_INVALID`과 `PRIMARY_RENDER_FAILED`를 **같은 상태로 뭉치지 않는다.**
앞의 것은 fallback 대상이 아니고, 뒤의 것만 대상이다.
"""
from __future__ import annotations

from dataclasses import dataclass

from v2_1_render import RenderError, render_markdown, render_preview, semantic_view
from v2_1_render_hwpx import render_hwpx
from v2_1_run import RenderRefused

PRIMARY = "PRIMARY"
PRESENTATION_FALLBACK_USED = "PRESENTATION_FALLBACK_USED"
PRESENTATION_FALLBACK_FAILED = "PRESENTATION_FALLBACK_FAILED"

OUTCOME_STATUSES = (PRIMARY, PRESENTATION_FALLBACK_USED,
                    PRESENTATION_FALLBACK_FAILED)

#: 표현 형식과, 실패했을 때 내려갈 수 있는 더 단순한 형식.
_CHAIN = {
    "hwpx": ("markdown", "preview"),
    "markdown": ("preview",),
    "preview": (),
}

#: 형식별 serializer. 테스트가 실패를 주입할 수 있도록 모듈 수준에 둔다.
_RENDERERS = {
    "hwpx": render_hwpx,
    "markdown": render_markdown,
    "preview": render_preview,
}

FORMATS = tuple(_CHAIN)


class StructuralFailure(RuntimeError):
    """구조가 유효하지 않다. **고쳐서 살리지 않는다.**"""


@dataclass(frozen=True, slots=True)
class RenderOutcome:
    status: str
    format: str | None
    payload: object
    primary_format: str
    primary_error: str | None = None
    fallback_errors: tuple[tuple[str, str], ...] = ()


def render_with_fallback(manifest, highlights, synthesis,
                         primary: str = "hwpx") -> RenderOutcome:
    """정한 형식으로 내보내고, 실패하면 **같은 의미를** 더 단순한 형식으로 낸다.

    구조가 유효하지 않으면 시작조차 하지 않는다. `analysis_mode` 인터록 위반은
    그대로 올려보낸다 — fallback으로 우회할 대상이 아니다.
    """
    if primary not in _CHAIN:
        raise StructuralFailure("unknown render format: %r" % primary)

    # 구조 검증이 먼저다. 여기서 걸리면 어떤 표현도 만들지 않는다.
    try:
        semantic_view(highlights, synthesis)
    except RenderError as exc:
        raise StructuralFailure("STRUCTURAL_INVALID: %s" % exc) from None

    primary_error = None
    failures: list[tuple[str, str]] = []
    for index, name in enumerate((primary, *_CHAIN[primary])):
        try:
            payload = _RENDERERS[name](manifest, highlights, synthesis)
        except RenderRefused:
            # analysis_mode 인터록. 다른 형식으로 우회할 대상이 아니다.
            raise
        except RenderError as exc:
            # 표현 도중에도 구조 위반이 드러날 수 있다. 그것은 fallback 대상이 아니다.
            raise StructuralFailure("STRUCTURAL_INVALID: %s" % exc) from None
        except Exception as exc:  # noqa: BLE001 — 표현 실패는 종류를 가리지 않는다
            message = "%s: %s" % (type(exc).__name__, exc)
            failures.append((name, message))
            if index == 0:
                primary_error = message
            continue
        return RenderOutcome(
            status=PRIMARY if index == 0 else PRESENTATION_FALLBACK_USED,
            format=name,
            payload=payload,
            primary_format=primary,
            primary_error=primary_error,
            fallback_errors=tuple(failures),
        )

    return RenderOutcome(
        status=PRESENTATION_FALLBACK_FAILED,
        format=None,
        payload=None,
        primary_format=primary,
        primary_error=primary_error,
        fallback_errors=tuple(failures),
    )

"""v2.1 Preview / Markdown renderer — 표시만 한다 (Gate C · C-06).

```
manifest + 확정된 표현 객체  →  preview 문자열
                             →  Markdown 문자열
```

**정본 episode를 받지 않는다.** 받지 않으면 경계를 다시 계산할 수도, `dialogue_note`
를 찾아 출력할 수도 없다. 규칙을 지키겠다는 약속이 아니라 **입력에 그것이 없다.**

```
하지 않는 것   경계 계산 · grouping 재계산 · summary 재합성 · grounding 재판정
              analysis_mode 자동 보정 · 임의 보정 · 문장 생성
```

`analysis_mode` 인터록은 A-02의 `require_report_mode`를 그대로 쓴다 — 같은 규칙을
두 곳에 두지 않는다.
"""
from __future__ import annotations

from v2_1_presentation import (
    SECTION_NAMES,
    SUMMARY_NO_RELIABLE_CONTENT,
    SUMMARY_STATUSES,
)
from v2_1_run import require_report_mode


class RenderError(RuntimeError):
    """렌더 입력 계약 위반. 보정하지 않고 멈춘다."""


def _clock(seconds: float) -> str:
    """초를 mm:ss로 적는다. 값을 바꾸지 않는다 — 표기만 한다."""
    total = int(seconds)
    return "%02d:%02d" % (total // 60, total % 60)


def _check(highlights, synthesis) -> None:
    """이미 확정된 값이 서로 어긋나면 거부한다. 고쳐 주지 않는다."""
    if not synthesis.limitation:
        raise RenderError("synthesis limitation is missing")

    for record in highlights:
        label = record.highlight_id
        if record.summary_status not in SUMMARY_STATUSES:
            raise RenderError("%s: unknown summary status %r"
                              % (label, record.summary_status))
        if (record.summary is None) != (
                record.summary_status == SUMMARY_NO_RELIABLE_CONTENT):
            raise RenderError("%s: summary and its status disagree" % label)
        covered = (set(record.summary_source_episode_ids)
                   | set(record.excluded_summary_episode_ids))
        if covered != set(record.source_episode_ids):
            raise RenderError("%s: summary lineage does not cover its sources"
                              % label)


def _summary_cell(record) -> str:
    """요약이 없으면 상태를 적는다. 문장을 지어내지 않는다."""
    return record.summary if record.summary is not None else (
        "(%s)" % SUMMARY_NO_RELIABLE_CONTENT
    )


def semantic_view(highlights, synthesis) -> dict:
    """두 출력이 공통으로 담아야 하는 의미. 서식은 여기 없다."""
    _check(highlights, synthesis)
    return {
        "highlights": [
            {
                "highlight_id": record.highlight_id,
                "label": record.label,
                "start_sec": record.start_sec,
                "end_sec": record.end_sec,
                "summary": record.summary,
                "summary_status": record.summary_status,
                "source_episode_ids": list(record.source_episode_ids),
                "summary_source_episode_ids":
                    list(record.summary_source_episode_ids),
            }
            for record in highlights
        ],
        "overview": synthesis.overview,
        "analysis": list(synthesis.analysis),
        "conclusion": synthesis.conclusion,
        "synthesis_sources": list(synthesis.source_episode_ids),
        "limitation": synthesis.limitation,
    }


def render_preview(manifest, highlights, synthesis) -> str:
    """축약 표현. 서식은 Markdown과 달라도 의미는 같다."""
    view = semantic_view(highlights, synthesis)
    lines = ["%s · %s" % (manifest.video_id, manifest.run_id), ""]
    for record, source in zip(view["highlights"], highlights):
        lines.append(" | ".join((
            record["highlight_id"],
            "%s–%s" % (_clock(record["start_sec"]), _clock(record["end_sec"])),
            record["label"] or "-",
            _summary_cell(source),
            " · ".join(record["source_episode_ids"]),
        )))
    lines += [
        "",
        "종합 출처 구간: %s" % (" · ".join(view["synthesis_sources"]) or "-"),
        view["limitation"],
    ]
    return "\n".join(lines)


def render_markdown(manifest, highlights, synthesis) -> str:
    """정식 보고서 형식. `analysis_mode != report`이면 여기서 멈춘다."""
    require_report_mode(manifest)
    view = semantic_view(highlights, synthesis)

    parts = [
        "# %s" % manifest.video_id,
        "",
        "- run: %s" % manifest.run_id,
        "- config: %s" % manifest.config_hash,
        "- code: %s" % manifest.code_git_head,
        "",
        "## %s" % SECTION_NAMES[0],
        "",
        view["overview"] or "(%s)" % SUMMARY_NO_RELIABLE_CONTENT,
        "",
        "## %s" % SECTION_NAMES[1],
    ]
    for record, source in zip(view["highlights"], highlights):
        parts += [
            "",
            "### %s%s" % (record["highlight_id"],
                          " %s" % record["label"] if record["label"] else ""),
            "- 시간: %s–%s" % (_clock(record["start_sec"]),
                              _clock(record["end_sec"])),
            "- 요약: %s" % _summary_cell(source),
            "- 구성 구간: %s" % " · ".join(record["source_episode_ids"]),
            "- 요약 출처: %s" % (" · ".join(record["summary_source_episode_ids"])
                               or "-"),
        ]
    parts += ["", "## %s" % SECTION_NAMES[2], ""]
    parts += list(view["analysis"]) or ["(%s)" % SUMMARY_NO_RELIABLE_CONTENT]
    parts += [
        "",
        "## %s" % SECTION_NAMES[3],
        "",
        view["conclusion"],
        "",
        "## %s" % SECTION_NAMES[4],
        "",
        "- 종합 출처 구간: %s" % (" · ".join(view["synthesis_sources"]) or "-"),
        "- 한계: %s" % view["limitation"],
    ]
    return "\n".join(parts)

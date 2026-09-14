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


#: 출력 label 어휘. **한 곳에서만 정의한다** — 서식은 renderer마다 달라도 되지만
#: "무엇을 적었는가"를 읽는 이름까지 갈라지면 두 출력을 대조할 수 없다.
LABELS = {
    "time": "시간",
    "summary": "요약",
    "sources": "구성 구간",
    "summary_sources": "요약 출처",
    "excluded": "제외 구간",
    "title": "제목",
    "synthesis_sources": "종합 출처 구간",
    "limitation": "한계",
}


class RenderError(RuntimeError):
    """렌더 입력 계약 위반. 보정하지 않고 멈춘다."""


def format_clock(seconds: float) -> str:
    """초를 mm:ss로 적는다. 값을 바꾸지 않는다 — 표기만 한다.

    HWPX renderer(C-07)도 같은 표기를 써야 하므로 공개한다.
    """
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


def summary_cell(record) -> str:
    """요약이 없으면 상태를 적는다. 문장을 지어내지 않는다.

    이 규칙이 renderer마다 갈라지면 같은 부재가 다르게 읽힌다.
    """
    return record.summary if record.summary is not None else (
        "(%s)" % SUMMARY_NO_RELIABLE_CONTENT
    )


def excluded_cell(record) -> str:
    """`EP13 (OUTPUT_LANGUAGE_DRIFT)` 형태. 두 renderer가 같은 문자열을 쓴다."""
    return " · ".join("%s (%s)" % (episode_id, " · ".join(reasons))
                      for episode_id, reasons in record["excluded_summary_reasons"])


def _chapter_view(chapters) -> dict:
    """group_id → chapter 표현. 합성 계층은 정본 표현 객체를 덮지 않는다."""
    view = {}
    for chapter in chapters or ():
        view[chapter.group_id] = {
            "group_id": chapter.group_id,
            "title": chapter.title,
            "sentences": [{"text": item.text,
                           "source_refs": list(item.source_refs)}
                          for item in chapter.summary_sentences],
            "content_status": chapter.content_status,
            "quality_status": chapter.quality_status,
            "presentable": chapter.presentable,
        }
    return view


def chapter_cell(chapter: dict) -> str:
    """chapter 본문 한 줄. 실패는 상태 코드로 적고 문장을 만들지 않는다."""
    if not chapter["presentable"]:
        return "(%s)" % chapter["content_status"]
    return " ".join(item["text"] for item in chapter["sentences"])


def semantic_view(highlights, synthesis, *, chapters=None,
                  global_synthesis=None) -> dict:
    """두 출력이 공통으로 담아야 하는 의미. 서식은 여기 없다.

    `chapters` · `global_synthesis`를 주면 합성 계층이 본문이 된다. 주지 않으면
    **예전 경로와 완전히 같다** — 두 경로가 공존한다(addendum §3).
    """
    _check(highlights, synthesis)
    view = {
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
                "excluded_summary_reasons": [
                    (episode_id, list(reasons))
                    for episode_id, reasons in record.excluded_summary_reasons],
            }
            for record in highlights
        ],
        "overview": synthesis.overview,
        "overview_sentences": [],
        "analysis": list(synthesis.analysis),
        "conclusion": synthesis.conclusion,
        "synthesis_sources": list(synthesis.source_episode_ids),
        "limitation": synthesis.limitation,
        "synthesis_layer": "episode_concat",
        "chapters": _chapter_view(chapters),
    }
    if global_synthesis is None:
        return view

    view["synthesis_layer"] = "presentation_synthesis_v1"
    if not global_synthesis.presentable:
        view["overview"] = "(%s)" % global_synthesis.content_status
        view["analysis"] = ["(%s)" % global_synthesis.content_status]
        view["conclusion"] = "(%s)" % global_synthesis.content_status
        return view
    view["overview_sentences"] = [
        {"text": item.text, "source_refs": list(item.source_refs)}
        for item in global_synthesis.overview_sentences]
    view["overview"] = " ".join(item["text"]
                                for item in view["overview_sentences"])
    view["analysis"] = [item.text for item in global_synthesis.analysis_points]
    view["analysis_sources"] = [list(item.source_refs)
                                for item in global_synthesis.analysis_points]
    view["conclusion"] = " ".join(item.text for item
                                  in global_synthesis.conclusion_sentences)
    view["global_sources"] = list(global_synthesis.source_highlight_refs)
    return view


def render_preview(manifest, highlights, synthesis) -> str:
    """축약 표현. 서식은 Markdown과 달라도 의미는 같다."""
    view = semantic_view(highlights, synthesis)
    lines = ["%s · %s" % (manifest.video_id, manifest.run_id), ""]
    for record, source in zip(view["highlights"], highlights):
        lines.append(" | ".join((
            record["highlight_id"],
            "%s–%s" % (format_clock(record["start_sec"]), format_clock(record["end_sec"])),
            record["label"] or "-",
            summary_cell(source),
            " · ".join(record["source_episode_ids"]),
        )))
    lines += [
        "",
        "%s: %s" % (LABELS["synthesis_sources"],
                    " · ".join(view["synthesis_sources"]) or "-"),
        "%s: %s" % (LABELS["limitation"], view["limitation"]),
    ]
    return "\n".join(lines)


def render_markdown(manifest, highlights, synthesis, *, chapters=None,
                    global_synthesis=None) -> str:
    """정식 보고서 형식. `analysis_mode != report`이면 여기서 멈춘다."""
    require_report_mode(manifest)
    view = semantic_view(highlights, synthesis, chapters=chapters,
                         global_synthesis=global_synthesis)

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
        chapter = view["chapters"].get(record["highlight_id"])
        parts += [
            "",
            "### %s%s" % (record["highlight_id"],
                          " %s" % record["label"] if record["label"] else ""),
            "- %s: %s–%s" % (LABELS["time"], format_clock(record["start_sec"]),
                             format_clock(record["end_sec"])),
        ]
        # chapter가 있으면 합성 본문을 싣는다. 실패한 chapter는 상태 코드를 싣고
        # **예전 concat으로 되돌리지 않는다**(addendum §8).
        if chapter is not None:
            if chapter["title"]:
                parts.append("- %s: %s" % (LABELS["title"], chapter["title"]))
            parts.append("- %s: %s" % (LABELS["summary"], chapter_cell(chapter)))
        else:
            parts.append("- %s: %s" % (LABELS["summary"], summary_cell(source)))
        parts += [
            "- %s: %s" % (LABELS["sources"],
                          " · ".join(record["source_episode_ids"])),
            "- %s: %s" % (LABELS["summary_sources"],
                          " · ".join(record["summary_source_episode_ids"]) or "-"),
        ]
        # 빠진 구간이 있으면 **구간 이름과 함께** 사유를 적는다. group 단위로
        # 뭉치면 묶음 전체가 실패한 것처럼 읽힌다.
        if record["excluded_summary_reasons"]:
            parts.append("- %s: %s" % (LABELS["excluded"],
                                       excluded_cell(record)))
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
        "- %s: %s" % (LABELS["synthesis_sources"],
                      " · ".join(view["synthesis_sources"]) or "-"),
        "- %s: %s" % (LABELS["limitation"], view["limitation"]),
    ]
    return "\n".join(parts)

"""v2.1 presentation synthesis — episode → chapter → global (2026-09-08).

사전등록: `docs/finalization/PRESENTATION_SYNTHESIS_V1_ADDENDUM_2026-09-08.md`

```
accepted episode summary   →  GroupSynthesizer   →  chapter (title + 1~2문장)
chapter                    →  GlobalSynthesizer  →  overview 3~5 · analysis 3~6
                                                     conclusion 1~2
```

**계층을 강제한다.** GlobalSynthesizer는 episode summary를 보지 못한다 — 입력이
chapter뿐이다. `episode → global` 직행 경로가 코드에 없다.

입력은 그 group의 **표현 자격 있는** episode뿐이다. 자격 없는 구간(품질 FAIL ·
parse 실패)의 문장은 프롬프트에 들어가지 않는다.

**실패는 실패로 남긴다.** 합성이 깨지면 예전 concat으로 되돌리지 않는다 — raw
출력·source·사유를 보존하고 그 상태로 표시한다.

이 모듈은 모델을 올리지 않는다. `prompt -> raw text` 콜러블은 호출부가 준다.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from v2_1_output_quality import (
    FAIL,
    PASS,
    QUALITY_POLICY_VERSION,
    SUSPECT,
    evaluate_summary,
)
from v2_1_presentation_input import exclusion_reasons, summary_eligible_for_presentation

GROUP_CONTRACT_VERSION = "presentation_group_synthesis_v1"
GLOBAL_CONTRACT_VERSION = "presentation_global_synthesis_v1"

VALID_SYNTHESIS = "VALID_SYNTHESIS"
GROUP_SYNTHESIS_FAILURE = "GROUP_SYNTHESIS_FAILURE"
GLOBAL_SYNTHESIS_FAILURE = "GLOBAL_SYNTHESIS_FAILURE"

#: **freeze된 형식.** 결과를 보고 조정하지 않는다(addendum §6).
GROUP_SENTENCE_RANGE = (1, 2)
OVERVIEW_RANGE = (3, 5)
ANALYSIS_RANGE = (3, 6)
CONCLUSION_RANGE = (1, 2)

GROUP_CONTRACT = {
    "version": GROUP_CONTRACT_VERSION,
    "system": "너는 영상 구간 요약들을 한국어 한 장(chapter)으로 정리하는 편집자다.",
    "task": "주어진 구간 요약들을 하나의 흐름으로 압축한다.",
    "rules": [
        "주어진 요약에 있는 내용만 쓴다.",
        "새로운 사건·숫자·사람·장소·제품명을 만들지 않는다.",
        "같은 의미의 반복 활동은 하나로 합친다.",
        "구간을 하나씩 다시 설명하지 않는다.",
        "시간 흐름상 중요한 변화만 남긴다.",
        "source_episode_refs는 주어진 구간 번호 중에서만 고른다.",
    ],
    "output": {
        "format": "JSON",
        "required": ["title", "summary_sentences"],
        "sentence_range": list(GROUP_SENTENCE_RANGE),
        "sentence_fields": ["text", "source_episode_refs"],
    },
}

GLOBAL_CONTRACT = {
    "version": GLOBAL_CONTRACT_VERSION,
    "system": "너는 장(chapter) 요약들로 영상 전체를 한국어로 정리하는 편집자다.",
    "task": "장 요약만 보고 전체 개요·핵심 흐름·결론을 적는다.",
    "rules": [
        "주어진 장 요약에 있는 내용만 쓴다.",
        "새로운 사건·숫자·사람·장소·제품명을 만들지 않는다.",
        "장을 하나씩 다시 나열하지 않는다.",
        "source_highlight_refs는 주어진 장 번호 중에서만 고른다.",
    ],
    "output": {
        "format": "JSON",
        "required": ["overview_sentences", "analysis_points",
                     "conclusion_sentences"],
        "overview_range": list(OVERVIEW_RANGE),
        "analysis_range": list(ANALYSIS_RANGE),
        "conclusion_range": list(CONCLUSION_RANGE),
        "sentence_fields": ["text", "source_highlight_refs"],
    },
}


class SynthesisError(RuntimeError):
    """합성 입력 계약 위반. 보정하지 않고 멈춘다."""


def _hash(contract: dict) -> str:
    return hashlib.sha256(
        json.dumps(contract, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def group_prompt_hash() -> str:
    return _hash(GROUP_CONTRACT)


def global_prompt_hash() -> str:
    return _hash(GLOBAL_CONTRACT)


def _clock(seconds: float) -> str:
    total = int(seconds)
    return "%02d:%02d" % (total // 60, total % 60)


# ── 입력 ────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class GroupSynthesisInput:
    """한 presentation group의 합성 입력. 자격 있는 구간만 담는다."""

    group_id: str
    member_episode_refs: tuple[str, ...]
    eligible_episode_refs: tuple[str, ...]
    episodes: tuple[tuple[str, float, float, str], ...]
    excluded: tuple[tuple[str, tuple[str, ...]], ...]

    @property
    def summaries(self) -> tuple[str, ...]:
        return tuple(summary for _, _, _, summary in self.episodes)

    @property
    def presentable(self) -> bool:
        return bool(self.episodes)


def group_inputs(presented, groups) -> tuple[GroupSynthesisInput, ...]:
    """group별 합성 입력을 만든다. **정본은 읽기만 한다.**

    자격 판정은 표현 계층의 단일 지점(`summary_eligible_for_presentation`)을 쓴다 —
    여기서 조건식을 다시 쓰지 않는다.
    """
    inputs = []
    for index, group in enumerate(groups, start=1):
        members = [presented.episode(ref) for ref in group]
        usable = [episode for episode in sorted(members,
                                                key=lambda item: item.start_seg)
                  if summary_eligible_for_presentation(episode)]
        excluded = tuple(
            (episode.episode_id, exclusion_reasons(episode))
            for episode in sorted(members, key=lambda item: item.start_seg)
            if not summary_eligible_for_presentation(episode))
        inputs.append(GroupSynthesisInput(
            group_id="H%02d" % index,
            member_episode_refs=tuple(group),
            eligible_episode_refs=tuple(item.episode_id for item in usable),
            episodes=tuple((item.episode_id, item.start_sec, item.end_sec,
                            item.summary) for item in usable),
            excluded=excluded))
    return tuple(inputs)


def build_group_prompt(item: GroupSynthesisInput) -> str:
    """group 합성 프롬프트. 자격 있는 구간의 **확정 요약만** 싣는다."""
    if not isinstance(item, GroupSynthesisInput):
        raise SynthesisError("group prompt는 GroupSynthesisInput으로 만든다, got %s"
                             % type(item).__name__)
    if not item.episodes:
        raise SynthesisError("%s: 자격 있는 구간이 없다" % item.group_id)
    lines = [GROUP_CONTRACT["system"], "", GROUP_CONTRACT["task"], ""]
    lines += ["- %s" % rule for rule in GROUP_CONTRACT["rules"]]
    lines += ["", "[구간 요약]"]
    for episode_id, start, end, summary in item.episodes:
        lines.append("%s (%s–%s) %s" % (episode_id, _clock(start), _clock(end),
                                        summary))
    lines += [
        "",
        "출력은 JSON 객체 하나다. 다른 말을 덧붙이지 않는다.",
        '{"title": "한 줄 제목", "summary_sentences": ['
        '{"text": "문장", "source_episode_refs": ["EP01"]}]}',
        "summary_sentences는 %d~%d개다." % GROUP_SENTENCE_RANGE,
    ]
    return "\n".join(lines)


# ── group 결과 ──────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class SynthesisSentence:
    text: str
    source_refs: tuple[str, ...]

    def as_dict(self) -> dict:
        return {"text": self.text, "source_refs": list(self.source_refs)}


@dataclass(frozen=True, slots=True)
class GroupSynthesisResult:
    group_id: str
    title: str | None
    summary_sentences: tuple[SynthesisSentence, ...]
    source_episode_refs: tuple[str, ...]
    content_status: str
    quality_status: str
    quality_reasons: tuple[str, ...]
    raw_model_output: str
    failures: tuple[str, ...] = ()

    @property
    def presentable(self) -> bool:
        """정상 content로 실을 수 있는가. 품질 FAIL은 싣지 않는다."""
        return (self.content_status == VALID_SYNTHESIS
                and self.quality_status != FAIL)

    def as_dict(self) -> dict:
        return {
            "group_id": self.group_id,
            "title": self.title,
            "summary_sentences": [item.as_dict()
                                  for item in self.summary_sentences],
            "source_episode_refs": list(self.source_episode_refs),
            "content_status": self.content_status,
            "quality_status": self.quality_status,
            "quality_reasons": list(self.quality_reasons),
            "quality_policy": QUALITY_POLICY_VERSION,
            "presentable": self.presentable,
            "failures": list(self.failures),
        }


def _quality(texts) -> tuple[str, tuple[str, ...]]:
    """title·문장을 같은 판정기로 본다. 가장 나쁜 상태를 쓴다."""
    status, reasons = PASS, []
    for text in texts:
        verdict = evaluate_summary(text)
        reasons += [reason for reason in verdict.reasons if reason not in reasons]
        if verdict.status == FAIL:
            status = FAIL
        elif verdict.status == SUSPECT and status != FAIL:
            status = SUSPECT
    return status, tuple(reasons)


def _failed_group(item: GroupSynthesisInput, raw: str,
                  failures) -> GroupSynthesisResult:
    """실패 결과. **문장을 만들지 않는다** — concat fallback이 없다."""
    return GroupSynthesisResult(
        group_id=item.group_id, title=None, summary_sentences=(),
        source_episode_refs=(), content_status=GROUP_SYNTHESIS_FAILURE,
        quality_status=FAIL, quality_reasons=(), raw_model_output=raw,
        failures=tuple(failures))


def parse_group(raw: str, item: GroupSynthesisInput) -> GroupSynthesisResult:
    """raw 출력을 chapter로 확정한다. 고쳐 주지 않는다."""
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return _failed_group(item, raw, ["출력이 JSON 객체가 아니다"])
    if not isinstance(payload, dict):
        return _failed_group(item, raw, ["출력이 JSON 객체가 아니다"])

    failures = []
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        failures.append("title이 없다")

    rows = payload.get("summary_sentences")
    if not isinstance(rows, list) or not rows:
        failures.append("summary_sentences가 없다")
        rows = []
    low, high = GROUP_SENTENCE_RANGE
    if rows and not (low <= len(rows) <= high):
        failures.append("summary_sentences가 %d개다 — %d~%d개여야 한다"
                        % (len(rows), low, high))

    allowed = set(item.eligible_episode_refs)
    sentences, used = [], []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append("문장 %d의 형식이 다르다" % index)
            continue
        text = row.get("text")
        refs = row.get("source_episode_refs")
        if not isinstance(text, str) or not text.strip():
            failures.append("문장 %d에 text가 없다" % index)
            continue
        if not isinstance(refs, list) or not refs:
            failures.append("문장 %d에 source_episode_refs가 없다" % index)
            continue
        unknown = [ref for ref in refs if ref not in allowed]
        if unknown:
            failures.append("문장 %d의 참조가 이 group의 자격 있는 구간이 아니다: %r"
                            % (index, unknown))
            continue
        sentences.append(SynthesisSentence(text=text.strip(),
                                           source_refs=tuple(refs)))
        used += [ref for ref in refs if ref not in used]

    if failures:
        return _failed_group(item, raw, failures)

    status, reasons = _quality([title] + [row.text for row in sentences])
    return GroupSynthesisResult(
        group_id=item.group_id, title=title.strip(),
        summary_sentences=tuple(sentences),
        source_episode_refs=tuple(used), content_status=VALID_SYNTHESIS,
        quality_status=status, quality_reasons=reasons, raw_model_output=raw)


def validate_group(result: GroupSynthesisResult,
                   item: GroupSynthesisInput) -> list:
    """확정된 chapter가 입력 계약과 맞는지 다시 본다."""
    failures = list(result.failures)
    if result.content_status != VALID_SYNTHESIS:
        return failures or ["content_status=%s" % result.content_status]
    allowed = set(item.eligible_episode_refs)
    low, high = GROUP_SENTENCE_RANGE
    if not (low <= len(result.summary_sentences) <= high):
        failures.append("문장 수가 %d~%d개 밖이다" % (low, high))
    for sentence in result.summary_sentences:
        unknown = [ref for ref in sentence.source_refs if ref not in allowed]
        if unknown:
            failures.append("허용되지 않은 참조: %r" % unknown)
        if not sentence.source_refs:
            failures.append("참조 없는 문장")
    if result.group_id != item.group_id:
        failures.append("group_id 불일치")
    return failures


# ── global ──────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class GlobalSynthesisResult:
    overview_sentences: tuple[SynthesisSentence, ...]
    analysis_points: tuple[SynthesisSentence, ...]
    conclusion_sentences: tuple[SynthesisSentence, ...]
    source_highlight_refs: tuple[str, ...]
    content_status: str
    quality_status: str
    quality_reasons: tuple[str, ...]
    raw_model_output: str
    failures: tuple[str, ...] = ()

    @property
    def presentable(self) -> bool:
        return (self.content_status == VALID_SYNTHESIS
                and self.quality_status != FAIL)

    def as_dict(self) -> dict:
        return {
            "overview_sentences": [item.as_dict()
                                   for item in self.overview_sentences],
            "analysis_points": [item.as_dict() for item in self.analysis_points],
            "conclusion_sentences": [item.as_dict()
                                     for item in self.conclusion_sentences],
            "source_highlight_refs": list(self.source_highlight_refs),
            "content_status": self.content_status,
            "quality_status": self.quality_status,
            "quality_reasons": list(self.quality_reasons),
            "quality_policy": QUALITY_POLICY_VERSION,
            "presentable": self.presentable,
            "failures": list(self.failures),
        }


def build_global_prompt(chapters) -> str:
    """global 합성 프롬프트. **입력은 chapter뿐이다** — episode를 받지 않는다."""
    if not chapters:
        raise SynthesisError("chapter가 없다")
    for chapter in chapters:
        if not isinstance(chapter, GroupSynthesisResult):
            raise SynthesisError(
                "global 합성 입력은 GroupSynthesisResult뿐이다, got %s"
                % type(chapter).__name__)
    usable = [chapter for chapter in chapters if chapter.presentable]
    if not usable:
        raise SynthesisError("실을 수 있는 chapter가 없다")

    lines = [GLOBAL_CONTRACT["system"], "", GLOBAL_CONTRACT["task"], ""]
    lines += ["- %s" % rule for rule in GLOBAL_CONTRACT["rules"]]
    lines += ["", "[장 요약]"]
    for chapter in usable:
        body = " ".join(sentence.text for sentence in chapter.summary_sentences)
        lines.append("%s %s — %s" % (chapter.group_id, chapter.title, body))
    lines += [
        "",
        "출력은 JSON 객체 하나다. 다른 말을 덧붙이지 않는다.",
        '{"overview_sentences": [{"text": "문장", "source_highlight_refs": ["H01"]}],'
        ' "analysis_points": [...], "conclusion_sentences": [...]}',
        "overview_sentences %d~%d개 · analysis_points %d~%d개 · "
        "conclusion_sentences %d~%d개다."
        % (OVERVIEW_RANGE + ANALYSIS_RANGE + CONCLUSION_RANGE),
    ]
    return "\n".join(lines)


def _rows(payload, key, allowed, bounds, failures) -> tuple:
    rows = payload.get(key)
    low, high = bounds
    if not isinstance(rows, list) or not rows:
        failures.append("%s가 없다" % key)
        return ()
    if not (low <= len(rows) <= high):
        failures.append("%s가 %d개다 — %d~%d개여야 한다"
                        % (key, len(rows), low, high))
        return ()
    sentences = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append("%s %d의 형식이 다르다" % (key, index))
            continue
        text = row.get("text")
        refs = row.get("source_highlight_refs")
        if not isinstance(text, str) or not text.strip():
            failures.append("%s %d에 text가 없다" % (key, index))
            continue
        if not isinstance(refs, list) or not refs:
            failures.append("%s %d에 source_highlight_refs가 없다" % (key, index))
            continue
        unknown = [ref for ref in refs if ref not in allowed]
        if unknown:
            failures.append("%s %d의 참조가 유효한 장이 아니다: %r"
                            % (key, index, unknown))
            continue
        sentences.append(SynthesisSentence(text=text.strip(),
                                           source_refs=tuple(refs)))
    return tuple(sentences)


def parse_global(raw: str, chapters) -> GlobalSynthesisResult:
    """global 결과를 확정한다. 참조는 실을 수 있는 장에서만 온다."""
    allowed = {chapter.group_id for chapter in chapters if chapter.presentable}
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        payload = None
    if not isinstance(payload, dict):
        return GlobalSynthesisResult(
            (), (), (), (), GLOBAL_SYNTHESIS_FAILURE, FAIL, (), raw,
            ("출력이 JSON 객체가 아니다",))

    failures = []
    overview = _rows(payload, "overview_sentences", allowed, OVERVIEW_RANGE,
                     failures)
    analysis = _rows(payload, "analysis_points", allowed, ANALYSIS_RANGE,
                     failures)
    conclusion = _rows(payload, "conclusion_sentences", allowed,
                       CONCLUSION_RANGE, failures)
    if failures:
        return GlobalSynthesisResult(
            (), (), (), (), GLOBAL_SYNTHESIS_FAILURE, FAIL, (), raw,
            tuple(failures))

    used = []
    for sentence in overview + analysis + conclusion:
        used += [ref for ref in sentence.source_refs if ref not in used]
    status, reasons = _quality([sentence.text for sentence
                                in overview + analysis + conclusion])
    return GlobalSynthesisResult(
        overview_sentences=overview, analysis_points=analysis,
        conclusion_sentences=conclusion, source_highlight_refs=tuple(used),
        content_status=VALID_SYNTHESIS, quality_status=status,
        quality_reasons=reasons, raw_model_output=raw)


def validate_global(result: GlobalSynthesisResult, chapters) -> list:
    failures = list(result.failures)
    if result.content_status != VALID_SYNTHESIS:
        return failures or ["content_status=%s" % result.content_status]
    allowed = {chapter.group_id for chapter in chapters if chapter.presentable}
    for name, rows, bounds in (
            ("overview_sentences", result.overview_sentences, OVERVIEW_RANGE),
            ("analysis_points", result.analysis_points, ANALYSIS_RANGE),
            ("conclusion_sentences", result.conclusion_sentences,
             CONCLUSION_RANGE)):
        low, high = bounds
        if not (low <= len(rows) <= high):
            failures.append("%s 개수가 %d~%d개 밖이다" % (name, low, high))
        for sentence in rows:
            unknown = [ref for ref in sentence.source_refs if ref not in allowed]
            if unknown:
                failures.append("%s의 참조가 유효하지 않다: %r" % (name, unknown))
    return failures

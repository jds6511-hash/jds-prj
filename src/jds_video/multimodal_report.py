"""Tutor-facing API for the multimodal report pipeline.

The report is assembled from two evidence channels — what is visible in a
segment and what is said in it — and every row it emits carries the segments it
came from.  Two properties are contractual:

* a row is published only when its evidence audit passes, and
* speech evidence is rewritten into report prose, never pasted in verbatim.

The second property is what `audit_report_style` enforces: a candidate sentence
is rejected when it copies a run of tokens from the transcript, or when it still
reads like speech (question endings, first-person subjects, discourse markers).
Rejection falls back to a constrained regeneration, then to a category-level
summary, and finally withholds the speech row altogether.
"""
from . import _internal as _bootstrap  # noqa: F401

from wvr_report_composer_v2 import (
    APPROVED_DISPLAYS,
    AUDIO,
    MAJOR,
    MINOR,
    SUPPORTING,
    VISUAL,
    VISUAL_AUDIO,
    assign_importance,
    audit_overview,
    audit_title,
    choose_episode_category,
    claim_support,
    compose_fused_summary,
    composer_counts,
    looks_like_transcript,
    modality_clause,
    uncertain_terms,
)
from wvr_speech_report_style_v1 import (
    APPROVED_REPORT_DISPLAYS,
    AUDIO_WITHHELD,
    EVIDENCE_EXTRACTIVE_ONLY,
    SAFE_BROAD_SUMMARY,
    TRANSCRIPT_STYLE_FAIL,
    TRANSCRIPT_STYLE_PASS,
    audit_report_style,
    information_retention,
    leakage_audit,
    resolve_decision,
    safe_broad_summary,
    style_audit,
    style_counts,
)

__all__ = [
    "APPROVED_DISPLAYS",
    "APPROVED_REPORT_DISPLAYS",
    "AUDIO",
    "AUDIO_WITHHELD",
    "EVIDENCE_EXTRACTIVE_ONLY",
    "MAJOR",
    "MINOR",
    "SAFE_BROAD_SUMMARY",
    "SUPPORTING",
    "TRANSCRIPT_STYLE_FAIL",
    "TRANSCRIPT_STYLE_PASS",
    "VISUAL",
    "VISUAL_AUDIO",
    "assign_importance",
    "audit_overview",
    "audit_report_style",
    "audit_title",
    "choose_episode_category",
    "claim_support",
    "compose_fused_summary",
    "composer_counts",
    "information_retention",
    "leakage_audit",
    "looks_like_transcript",
    "modality_clause",
    "resolve_decision",
    "safe_broad_summary",
    "style_audit",
    "style_counts",
    "uncertain_terms",
]

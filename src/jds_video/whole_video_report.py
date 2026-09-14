"""Tutor-facing API for the reviewer-PASS whole-video report V2 baseline.

The public flow is direct video observation -> temporal compression ->
canonical activity flow -> Overview -> Analysis/Conclusion -> report.
"""
from . import _internal as _bootstrap  # noqa: F401

from wvr_overview_synthesis_v2 import canonical_flow
from wvr_video_overview_preview_v2 import (
    compress_activity_timeline,
    parse_overview,
    parse_segment,
    segment_prompt,
    synthesis_prompt,
)
from wvr_whole_video_report_v2 import (
    EVENT,
    MODEL_ID,
    MODEL_REVISION,
    ReportV2Error,
    analysis_prompt,
    clean_body,
    conclusion_prompt,
    final_report_markdown,
    machine_checks,
)

__all__ = [
    "EVENT",
    "MODEL_ID",
    "MODEL_REVISION",
    "ReportV2Error",
    "segment_prompt",
    "parse_segment",
    "compress_activity_timeline",
    "synthesis_prompt",
    "parse_overview",
    "canonical_flow",
    "analysis_prompt",
    "conclusion_prompt",
    "clean_body",
    "machine_checks",
    "final_report_markdown",
]

"""Tutor-facing API for natural-language scene retrieval.

Pipeline: video segmentation -> STT and visual caption -> KURE-v1 embedding
-> normalized channel fusion -> timestamped search results.
"""
from . import _internal as _bootstrap  # noqa: F401

from m5_search import Result, VideoIndex, search, search_with_stats
from m7_webui import create_app

__all__ = [
    "Result",
    "VideoIndex",
    "search",
    "search_with_stats",
    "create_app",
]

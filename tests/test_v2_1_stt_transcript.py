"""STT 전사문 txt 내보내기 — 보고서와 별도 파일.

```
source segments     구간 정렬 자막 (파이프라인이 실제로 쓴 값 · 크레딧 필터 적용분)
source utterances   Whisper 발화 단위 원본 (필터 이전)
```

**텍스트를 고치지 않는다.** 맞춤법·띄어쓰기·중복 정리를 넣는 순간 전사문이 아니라
편집본이 된다. 이 파일이 막는 것이 그것이다.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/v2_1_stt_transcript.py"


def _load():
    spec = importlib.util.spec_from_file_location("stt_transcript", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stt = _load()

MESSY = "  어 그러니까  소스를   두 큰술   "
SEGMENTS = {
    "video_id": "V1",
    "duration_sec": 30.0,
    "n_segments": 4,
    "segments": [
        {"idx": 0, "start": 0, "end": 5, "subtitle": MESSY, "caption": "화면 설명"},
        {"idx": 1, "start": 5, "end": 10, "subtitle": "", "caption": "화면 설명"},
        {"idx": 2, "start": 10, "end": 15, "subtitle": "뚜껑을 덮는다.", "caption": ""},
        {"idx": 3, "start": 15, "end": 20, "subtitle": "   ", "caption": ""},
    ],
}
CACHE = {
    "meta": {"model": "large-v3", "lang": "ko", "beam_size": 5},
    "utterances": [
        {"text": MESSY, "t0": 0.0, "t1": 2.5},
        {"text": "뚜껑을 덮는다.", "t0": 10.2, "t1": 11.9},
    ],
}


@pytest.fixture
def world(tmp_path):
    work = tmp_path / "work" / "V1"
    work.mkdir(parents=True)
    (work / "segments.json").write_text(json.dumps(SEGMENTS, ensure_ascii=False),
                                        encoding="utf-8")
    (work / "stt_cache.json").write_text(json.dumps(CACHE, ensure_ascii=False),
                                         encoding="utf-8")
    return work


# ── 원문 보존 ────────────────────────────────────────────────────────────
def test_the_text_is_carried_over_verbatim(world):
    """앞뒤 공백만 떼고 **내부 문자열은 그대로** 둔다."""
    text = stt.render(world, source="segments")
    assert MESSY.strip() in text
    assert "어 그러니까  소스를   두 큰술" in text     # 내부 다중 공백 유지


def test_no_cleanup_helper_exists_in_the_source():
    """정리 함수가 생기면 다음 사람이 '조금만' 고치기 시작한다."""
    code = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("re.sub", "replace(' '", "normalize", "spell", "correct("):
        assert forbidden not in code, forbidden


def test_the_utterance_source_is_the_unfiltered_original(world):
    text = stt.render(world, source="utterances")
    assert "00:00:00.0 → 00:00:02.5" in text
    assert MESSY.strip() in text


# ── 누락 없음 · 순서 ─────────────────────────────────────────────────────
def test_empty_segments_are_counted_not_silently_dropped(world):
    """비어 있는 구간을 빼고 적으면 '전사가 이만큼 있다'가 부풀려진다."""
    text = stt.render(world, source="segments")
    assert "구간 4 · 발화 있는 구간 2" in text
    assert "seg#1" not in text and "seg#3" not in text     # 본문에는 빈 줄 없음


def test_lines_are_ordered_by_segment(world):
    text = stt.render(world, source="segments")
    assert text.index("seg#0") < text.index("seg#2")


def test_segment_lines_carry_the_time_span(world):
    text = stt.render(world, source="segments")
    line = next(row for row in text.splitlines() if row.startswith("seg#0"))
    assert "00:00:00 – 00:00:05" in line


# ── provenance ───────────────────────────────────────────────────────────
def test_the_header_records_where_the_text_came_from(world):
    text = stt.render(world, source="segments")
    assert "video_id       V1" in text
    assert "source         segments.json · subtitle" in text
    assert "sha256" in text
    assert "large-v3" in text                    # STT 모델
    assert "크레딧 환각 필터 적용분" in text        # 어느 층인지 밝힌다


def test_the_utterance_header_says_it_is_unfiltered(world):
    text = stt.render(world, source="utterances")
    assert "source         stt_cache.json · utterances" in text
    assert "필터 이전" in text


def test_the_export_is_deterministic(world):
    assert stt.render(world, source="segments") == stt.render(world,
                                                              source="segments")


def test_an_unknown_source_is_refused(world):
    with pytest.raises(SystemExit):
        stt.render(world, source="captions")


def test_it_never_reads_the_caption_channel(world):
    """전사문 파일에 캡션이 섞이면 무엇이 발화였는지 알 수 없다."""
    text = stt.render(world, source="segments")
    assert "화면 설명" not in text

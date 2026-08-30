"""A-03 raw artifact store — raw-before-parse.

티켓: `docs/finalization/V2_1_GATE_A_TICKETS_2026-08-30.md` A-03
근거: 2026-08-29 파서 사고 2건 — raw가 없었다면 재파싱으로 복구할 수 없었다.

acceptance 넷.

```
raw가 parse 전에 실제로 durable하게 저장되는가
parse 실패 후에도 원본 그대로 남는가
source_type과 segment_id를 역추적할 수 있는가
parser가 raw artifact를 덮어쓰거나 정상화하지 않는가
```

run layout·manifest는 A-02 책임이다. 이 테스트는 raw_root를 호출자가 준다고 본다.
"""
import json
import re
from pathlib import Path

import pytest

from v2_1_raw_store import (
    EVIDENCE_MODALITIES,
    SOURCE_TYPES,
    RawStore,
    RawStoreError,
    UnknownSourceTypeError,
)

MALFORMED = '{"episodes": [ {"summary": "잘린 JSON'
SRC = Path(__file__).resolve().parents[1] / "src/v2_1_raw_store.py"


@pytest.fixture
def store(tmp_path):
    return RawStore(tmp_path / "raw", run_id="run-001", video_id="wonyi_geoje")


def _put(store, **kw):
    kw.setdefault("segment_id", 55)
    kw.setdefault("source_type", "vlm")
    kw.setdefault("producer", "Qwen2.5-VL-3B")
    kw.setdefault("producer_version", "4bit-P0")
    kw.setdefault("payload", "seg#55 화면: 두 여성이 해변에 앉아 있습니다.")
    return store.store(**kw)


# ── RAW-001 raw before parse ─────────────────────────────────────────────
def test_raw_001_raw_is_on_disk_before_parse_runs(store):
    """parse 콜백이 호출된 시점에 raw가 이미 디스크에 있어야 한다."""
    seen = {}

    def parse(payload):
        record = store.load("vlm", 55)
        seen["path_exists"] = record.raw_path.is_file()
        seen["bytes"] = record.read_bytes()
        return {"ok": True}

    outcome = store.store_then_parse(
        parse,
        segment_id=55,
        source_type="vlm",
        producer="Qwen2.5-VL-3B",
        producer_version="4bit-P0",
        payload="seg#55 화면: 두 여성이 해변에 앉아 있습니다.",
    )
    assert seen["path_exists"] is True
    assert seen["bytes"].decode("utf-8").startswith("seg#55")
    assert outcome.status == "PARSE_OK"
    assert outcome.parsed == {"ok": True}


def test_raw_001_store_precedes_parse_in_source():
    """소스 순서 — 저장이 parse 호출보다 앞에 있어야 한다."""
    body = SRC.read_text(encoding="utf-8").split("def store_then_parse", 1)[1]
    assert body.index("self.store(") < body.index("parse_fn(")


def test_raw_001_write_is_atomic_and_flushed():
    src = SRC.read_text(encoding="utf-8")
    assert "os.replace" in src, "임시 파일 후 원자적 교체가 아니다"
    assert "fsync" in src, "fsync 없이 durable을 주장할 수 없다"


# ── RAW-002 raw survives parse failure ───────────────────────────────────
def test_raw_002_raw_survives_parse_failure(store):
    def parse(payload):
        raise ValueError("Expecting ',' delimiter")

    outcome = store.store_then_parse(
        parse, segment_id=7, source_type="llm", producer="Qwen2.5-7B-Instruct",
        producer_version="bf16", payload=MALFORMED,
    )
    assert outcome.status == "PARSE_FAILED"
    assert outcome.parsed is None
    assert "Expecting" in outcome.error
    assert store.load("llm", 7).read_text() == MALFORMED


def test_raw_002_failure_is_not_silently_swallowed(store):
    def parse(payload):
        raise ValueError("boom")

    outcome = store.store_then_parse(
        parse, segment_id=7, source_type="llm", producer="p", producer_version="v",
        payload=MALFORMED,
    )
    assert outcome.error and outcome.error_type == "ValueError"
    assert outcome.status != "PARSE_OK"


def test_raw_002_empty_payload_is_not_a_parse_failure(store):
    """빈 출력과 파싱 실패는 다르다 (SCH-005의 선행)."""
    record = _put(store, segment_id=8, source_type="asr", payload="")
    assert record.read_bytes() == b""
    assert store.load("asr", 8).read_text() == ""


# ── RAW-003 source type identifiable ─────────────────────────────────────
def test_raw_003_source_type_is_recorded_and_traceable(store):
    for source_type in ("asr", "vlm", "ocr", "llm"):
        _put(store, segment_id=1, source_type=source_type,
             payload="payload-" + source_type)
    for source_type in ("asr", "vlm", "ocr", "llm"):
        record = store.load(source_type, 1)
        assert record.source_type == source_type
        assert record.read_text() == "payload-" + source_type


def test_raw_003_unknown_source_type_is_rejected(store):
    with pytest.raises(UnknownSourceTypeError):
        _put(store, source_type="subtitle")


# ── RAW-004 segment provenance ───────────────────────────────────────────
def test_raw_004_segment_id_is_recoverable(store):
    for segment_id in (0, 7, 55, 279):
        _put(store, segment_id=segment_id, payload="seg#%d" % segment_id)
    assert {r.segment_id for r in store.records()} == {0, 7, 55, 279}
    assert store.load("vlm", 279).read_text() == "seg#279"


def test_raw_004_provenance_survives_a_fresh_store_object(tmp_path):
    root = tmp_path / "raw"
    _put(RawStore(root, run_id="run-001", video_id="wonyi_geoje"), segment_id=55)
    reopened = RawStore(root, run_id="run-001", video_id="wonyi_geoje")
    record = reopened.load("vlm", 55)
    assert record.video_id == "wonyi_geoje"
    assert record.run_id == "run-001"
    assert record.segment_id == 55
    assert record.source_type == "vlm"


def test_raw_004_missing_record_is_an_explicit_error(store):
    with pytest.raises(RawStoreError):
        store.load("vlm", 999)


def test_raw_004_negative_segment_id_is_rejected(store):
    with pytest.raises(RawStoreError):
        _put(store, segment_id=-1)


# ── RAW-005 (P1) producer metadata ───────────────────────────────────────
def test_raw_005_producer_metadata_is_preserved(store):
    _put(store, producer="Qwen2.5-VL-3B", producer_version="4bit-P0")
    record = store.load("vlm", 55)
    assert record.producer == "Qwen2.5-VL-3B"
    assert record.producer_version == "4bit-P0"
    meta = json.loads(record.meta_path.read_text(encoding="utf-8"))
    assert meta["producer_version"] == "4bit-P0"
    assert meta["run_id"] == "run-001"


def test_raw_005_producer_is_required(store):
    with pytest.raises(RawStoreError):
        _put(store, producer="")


# ── RAW-006 (P1) rerun separation ────────────────────────────────────────
def test_raw_006_reruns_do_not_collide(tmp_path):
    """run layout은 A-02 책임 — A-03은 raw_root가 다르면 섞이지 않음만 보장한다."""
    first = RawStore(tmp_path / "run-001", run_id="run-001", video_id="v")
    second = RawStore(tmp_path / "run-002", run_id="run-002", video_id="v")
    _put(first, payload="first")
    _put(second, payload="second")
    assert first.load("vlm", 55).read_text() == "first"
    assert second.load("vlm", 55).read_text() == "second"


def test_raw_006_overwrite_within_one_run_is_refused(store):
    _put(store, payload="first")
    with pytest.raises(RawStoreError, match="overwrite"):
        _put(store, payload="second")
    assert store.load("vlm", 55).read_text() == "first"


# ── parser는 raw를 고치지 않는다 ─────────────────────────────────────────
def test_parser_cannot_normalize_the_raw_artifact(store):
    payload = '  {"a": 1}\r\n\r\n  '

    store.store_then_parse(
        json.loads, segment_id=3, source_type="llm", producer="p",
        producer_version="v", payload=payload,
    )
    assert store.load("llm", 3).read_bytes() == payload.encode("utf-8")


def test_raw_bytes_are_unchanged_by_a_failed_parse(store):
    before = _put(store, segment_id=9, source_type="llm", payload=MALFORMED).read_bytes()
    store.store_then_parse(
        json.loads, segment_id=10, source_type="llm", producer="p",
        producer_version="v", payload=MALFORMED,
    )
    assert store.load("llm", 9).read_bytes() == before


def test_records_are_read_only_views(store):
    record = _put(store)
    with pytest.raises(Exception):
        record.segment_id = 1


# ── A-02 침범 금지 ───────────────────────────────────────────────────────
def test_a03_does_not_implement_a02_run_layout():
    """run layout·manifest는 A-02 책임 — 앞당겨 구현하면 티켓 경계가 깨진다."""
    src = SRC.read_text(encoding="utf-8")
    for forbidden in ("manifest", "analysis_mode", "config_hash", "outputs/v2_1"):
        assert forbidden not in src, "A-02 책임을 침범했다: " + forbidden


def test_a03_does_not_touch_legacy_segment_schema():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r"""\[\s*["'](?:idx|start|end)["']\s*\]""", src)


def test_llm_is_a_producer_not_an_evidence_modality():
    """축이 다르다 — Evidence Timeline(A-06)이 source_type을 통째로 재사용하면
    LLM 출력이 evidence처럼 섞인다. 그것을 막는 것이 EVIDENCE_MODALITIES다."""
    assert "llm" in SOURCE_TYPES
    assert "llm" not in EVIDENCE_MODALITIES
    assert set(EVIDENCE_MODALITIES) < set(SOURCE_TYPES)
    assert EVIDENCE_MODALITIES == ("asr", "vlm", "ocr")

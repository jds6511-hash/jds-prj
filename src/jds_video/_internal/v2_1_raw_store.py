"""v2.1 raw artifact store — raw before parse (Gate A · A-03).

원칙 하나.

```
invocation → raw atomic write → parse → parsed artifact
```

parse는 raw를 소비할 뿐 고치지 않는다. parse가 실패해도 raw는 그대로 남고,
어느 source_type의 어느 segment에서 나온 출력인지 역추적할 수 있다.

2026-08-29에 파서 결함 둘로 dialogue_note 14건이 잘못 버려지고 raw JSON이 요약
필드에 실려 들어갔다. 저장된 raw가 있었기 때문에 GPU 없이 재파싱으로 복구할 수
있었다. 이 모듈은 그 복구 가능성을 계약으로 만든다.

run id와 저장 위치는 **호출자가 준다.** run layout은 A-02 책임이고 여기서 앞당겨
구현하지 않는다.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator


SOURCE_TYPES = ("asr", "vlm", "ocr", "llm")

#: evidence modality — 사람이 관측한 채널. Evidence Timeline(A-06)은 **이것만** 쓴다.
#: `llm`은 downstream producer이지 evidence modality가 아니다. 축이 다르다.
EVIDENCE_MODALITIES = ("asr", "vlm", "ocr")


class RawStoreError(RuntimeError):
    """raw store 계약 위반."""


class UnknownSourceTypeError(RawStoreError):
    """선언되지 않은 source_type. 확장은 계약 변경이므로 티켓이 필요하다."""


@dataclass(frozen=True, slots=True)
class RawRecord:
    """저장된 raw 출력 하나. payload는 파일에 있고 여기에 복제하지 않는다."""

    run_id: str
    video_id: str
    segment_id: int
    source_type: str
    producer: str
    producer_version: str
    raw_path: Path
    meta_path: Path

    def read_bytes(self) -> bytes:
        return self.raw_path.read_bytes()

    def read_text(self) -> str:
        return self.raw_path.read_text(encoding="utf-8")


@dataclass(frozen=True, slots=True)
class ParseOutcome:
    """parse 결과. 실패를 성공처럼 표현하지 않는다."""

    record: RawRecord
    status: str
    parsed: Any = None
    error: str | None = None
    error_type: str | None = None


def _atomic_write(path: Path, data: bytes) -> None:
    """같은 디렉터리에 임시 파일로 쓰고 fsync 후 교체한다."""
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


class RawStore:
    """하나의 run·영상에 대한 raw 저장소.

    `root` 아래 구조만 이 모듈이 소유한다.

    ```
    <root>/<source_type>/seg<segment_id:06d>.raw        payload 바이트 그대로
    <root>/<source_type>/seg<segment_id:06d>.meta.json  추적 정보
    ```
    """

    def __init__(self, root: Path | str, *, run_id: str, video_id: str) -> None:
        if not str(run_id).strip():
            raise RawStoreError("run_id is required")
        if not str(video_id).strip():
            raise RawStoreError("video_id is required")
        self.root = Path(root)
        self.run_id = run_id
        self.video_id = video_id

    # ── 경로 ─────────────────────────────────────────────────────────────
    def _check_source_type(self, source_type: str) -> None:
        if source_type not in SOURCE_TYPES:
            raise UnknownSourceTypeError(
                "unknown source_type %r (declared: %s)"
                % (source_type, ", ".join(SOURCE_TYPES))
            )

    def _stem(self, source_type: str, segment_id: int) -> Path:
        self._check_source_type(source_type)
        if isinstance(segment_id, bool) or not isinstance(segment_id, int):
            raise RawStoreError("segment_id must be an int")
        if segment_id < 0:
            raise RawStoreError("segment_id must be >= 0")
        return self.root / source_type / ("seg%06d" % segment_id)

    # ── 쓰기 ─────────────────────────────────────────────────────────────
    def store(
        self,
        *,
        segment_id: int,
        source_type: str,
        producer: str,
        producer_version: str,
        payload: str | bytes,
    ) -> RawRecord:
        """raw payload를 원자적으로 저장한다. 덮어쓰기는 거부한다."""
        stem = self._stem(source_type, segment_id)
        if not str(producer).strip():
            raise RawStoreError("producer is required")
        if not str(producer_version).strip():
            raise RawStoreError("producer_version is required")

        raw_path = stem.with_suffix(".raw")
        meta_path = stem.with_suffix(".meta.json")
        if raw_path.exists() or meta_path.exists():
            raise RawStoreError(
                "refusing to overwrite existing raw artifact: %s" % raw_path
            )

        stem.parent.mkdir(parents=True, exist_ok=True)
        data = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        _atomic_write(raw_path, data)

        meta = {
            "run_id": self.run_id,
            "video_id": self.video_id,
            "segment_id": segment_id,
            "source_type": source_type,
            "producer": producer,
            "producer_version": producer_version,
            "raw_bytes": len(data),
        }
        _atomic_write(
            meta_path,
            json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        return RawRecord(
            run_id=self.run_id,
            video_id=self.video_id,
            segment_id=segment_id,
            source_type=source_type,
            producer=producer,
            producer_version=producer_version,
            raw_path=raw_path,
            meta_path=meta_path,
        )

    # ── 읽기 ─────────────────────────────────────────────────────────────
    def load(self, source_type: str, segment_id: int) -> RawRecord:
        stem = self._stem(source_type, segment_id)
        meta_path = stem.with_suffix(".meta.json")
        if not meta_path.is_file():
            raise RawStoreError("no raw artifact for %s seg#%s" % (source_type, segment_id))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return RawRecord(
            run_id=meta["run_id"],
            video_id=meta["video_id"],
            segment_id=meta["segment_id"],
            source_type=meta["source_type"],
            producer=meta["producer"],
            producer_version=meta["producer_version"],
            raw_path=stem.with_suffix(".raw"),
            meta_path=meta_path,
        )

    def records(self) -> Iterator[RawRecord]:
        """저장 순서가 아니라 source_type·segment_id 순으로 낸다."""
        for source_type in SOURCE_TYPES:
            directory = self.root / source_type
            if not directory.is_dir():
                continue
            for meta_path in sorted(directory.glob("seg*.meta.json")):
                segment_id = int(meta_path.name[3:9])
                yield self.load(source_type, segment_id)

    # ── 저장 후 파싱 ─────────────────────────────────────────────────────
    def store_then_parse(
        self,
        parse_fn: Callable[[str], Any],
        *,
        segment_id: int,
        source_type: str,
        producer: str,
        producer_version: str,
        payload: str,
    ) -> ParseOutcome:
        """raw를 먼저 저장하고 그 다음에 파싱한다. 순서를 바꾸지 마라.

        parse 실패는 예외로 새어 나가지 않고 `PARSE_FAILED`로 분류되지만,
        원인 문자열과 예외 형은 그대로 보존한다 — 실패를 숨기지 않는다.
        """
        record = self.store(
            segment_id=segment_id,
            source_type=source_type,
            producer=producer,
            producer_version=producer_version,
            payload=payload,
        )
        try:
            parsed = parse_fn(payload)
        except Exception as exc:
            return ParseOutcome(
                record=record,
                status="PARSE_FAILED",
                error=str(exc),
                error_type=type(exc).__name__,
            )
        return ParseOutcome(record=record, status="PARSE_OK", parsed=parsed)

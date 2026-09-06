"""STT 전사문을 별도 txt로 내보낸다 — 최종 보고서의 동반 파일.

보고서(HWPX)는 요약이고, 이 파일은 **전사문 그대로**다. 두 층을 고르게 한다.

```
segments     구간 정렬 자막 — 파이프라인이 실제로 쓴 값(크레딧 환각 필터 적용분)
utterances   Whisper 발화 단위 원본 — 필터 이전
```

**텍스트를 고치지 않는다.** 앞뒤 공백만 떼고 내부 문자열은 그대로 쓴다. 맞춤법·띄어쓰기
정리를 넣는 순간 전사문이 아니라 편집본이 되고, 무엇이 모델 입력이었는지 알 수 없게 된다.

사용:
    python scripts/v2_1_stt_transcript.py --work work_full/full_xekZO4n4QuE \\
        --out runs/v3_paired/stt_transcript_full_xekZO4n4QuE.txt
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v2_1_segments import legacy_segments_to_canonical            # noqa: E402

SOURCES = ("segments", "utterances")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clock(seconds: float, decimals: int = 0) -> str:
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    stamp = "%02d:%02d:%02d" % (hours, minutes, secs)
    if decimals:
        stamp += ".%d" % int(round((seconds - total) * 10))
    return stamp


def render(work: Path, *, source: str = "segments") -> str:
    """전사문 본문을 만든다. 파일로 쓰지 않는다 — 테스트가 문자열을 본다."""
    if source not in SOURCES:
        raise SystemExit("알 수 없는 source %r (가능: %s)"
                         % (source, ", ".join(SOURCES)))
    segments_path = work / "segments.json"
    cache_path = work / "stt_cache.json"
    document = json.loads(segments_path.read_text(encoding="utf-8"))
    cache = (json.loads(cache_path.read_text(encoding="utf-8"))
             if cache_path.is_file() else {"meta": {}, "utterances": []})
    model = cache.get("meta", {}).get("model", "unavailable")

    head = [
        "STT 전사문 — 편집하지 않은 원문",
        "",
        "video_id       %s" % document.get("video_id", work.name),
        "STT 모델       %s (lang %s · beam %s)" % (
            model, cache.get("meta", {}).get("lang", "?"),
            cache.get("meta", {}).get("beam_size", "?")),
    ]

    if source == "segments":
        # 시간·번호는 **adapter를 거친 canonical** 값이다(OPEN-1 / A-01).
        # 자막 문자열만 legacy 행에서 같은 순서로 가져온다.
        legacy = document["segments"]
        canonical = legacy_segments_to_canonical(legacy)
        rows = [(segment, (row.get("subtitle") or "").strip())
                for segment, row in zip(canonical, legacy)]
        spoken = [(segment, text) for segment, text in rows if text]
        head += [
            "source         segments.json · subtitle (크레딧 환각 필터 적용분)",
            "sha256         %s" % sha256_file(segments_path),
            "규모           구간 %d · 발화 있는 구간 %d" % (len(rows), len(spoken)),
            "",
            "발화가 없는 구간은 줄을 만들지 않는다. 위 규모에 그 수가 남아 있다.",
            "-" * 72,
            "",
        ]
        body = ["seg#%-4d %s – %s  %s" % (segment.segment_id,
                                          _clock(segment.start_sec),
                                          _clock(segment.end_sec), text)
                for segment, text in spoken]
    else:
        utterances = cache["utterances"]
        head += [
            "source         stt_cache.json · utterances (필터 이전 원본)",
            "sha256         %s" % sha256_file(cache_path),
            "규모           발화 %d" % len(utterances),
            "",
            "-" * 72,
            "",
        ]
        body = ["%s → %s  %s" % (_clock(item["t0"], 1), _clock(item["t1"], 1),
                                 (item.get("text") or "").strip())
                for item in utterances]

    return "\n".join(head + body) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True,
                        help="work 디렉터리 (segments.json · stt_cache.json)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--source", choices=SOURCES, default="segments")
    args = parser.parse_args(argv)

    text = render(Path(args.work), source=args.source)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(json.dumps({"out": str(out), "bytes": len(text.encode("utf-8")),
                      "lines": text.count("\n"),
                      "sha256": sha256_file(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

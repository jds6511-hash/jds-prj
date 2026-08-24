"""AAR 추적 렌더러 — `report.json`의 각 주장을 시각·근거까지 잇는다.

M8이 만든 리포트를 **읽기만** 한다. LLM을 부르지 않고 새 서술을 만들지 않는다.
목적은 "이 문장의 근거가 영상 어디인가"를 사람이 바로 확인할 수 있게 하는 것이다.

```
report.json  sentences[{sent_id, text, cites:[seg_idx…]}]
segments.json  segments[{idx, start, end, subtitle, caption}]
        ↓
문장 → 인용 세그먼트 → 시각(start~end) → 자막·캡션 근거 → 재생 위치
```

잇지 못하는 인용(범위 밖·인용 없음)은 **fail-closed**로 예외를 던진다 — 조용히 빼면
추적 불가한 주장이 리포트에 남는다.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common                                                       # noqa: E402

SUPPORTED_SCHEMA = (2,)


class TraceError(RuntimeError):
    pass


def _mmss(sec) -> str:
    s = int(sec)
    return f"{s // 60:02d}:{s % 60:02d}"


def _load(path, what: str) -> dict:
    p = Path(path)
    if not p.is_file():
        raise TraceError(f"{what}이 없다: {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise TraceError(f"{what} 파싱 실패: {p} — {e}")


def build(report_path, segments_path, video_id: str | None = None) -> dict:
    rep = _load(report_path, "report.json")
    ver = rep.get("schema_version")
    if ver not in SUPPORTED_SCHEMA:
        raise TraceError(f"지원하지 않는 schema_version={ver} "
                         f"(지원 {SUPPORTED_SCHEMA}) — 렌더러를 맞춰야 한다")
    if video_id is not None and rep.get("video_id") != video_id:
        raise TraceError(f"video_id 불일치: report={rep.get('video_id')!r} "
                         f"요청={video_id!r}")

    doc = _load(segments_path, "segments.json")
    segs = {s["idx"]: s for s in doc["segments"]}
    n = len(doc["segments"])

    out, cited = [], set()
    for s in rep["sentences"]:
        cites = list(s.get("cites") or [])
        if not cites:
            raise TraceError(f"sent {s.get('sent_id')}: 인용이 없다 — 추적 불가한 "
                             f"주장을 리포트에 남기지 않는다")
        bad = [c for c in cites if c not in segs]
        if bad:
            raise TraceError(f"sent {s.get('sent_id')}: 인용 범위 위반 {bad} "
                             f"(구간 0~{n - 1})")
        cited.update(cites)
        spans = [{"idx": c, "start": int(segs[c]["start"]),
                  "end": int(segs[c]["end"])} for c in cites]
        out.append({
            "sent_id": s.get("sent_id"), "text": s["text"], "cites": cites,
            "spans": spans,
            "seek_to": min(sp["start"] for sp in spans),
            "time_range": {"start": min(sp["start"] for sp in spans),
                           "end": max(sp["end"] for sp in spans)},
            "evidence": [{"idx": c,
                          "subtitle": segs[c].get("subtitle", ""),
                          "caption": segs[c].get("caption", "")}
                         for c in cites],
        })

    return {
        "probe": "aar_view",
        "video_id": rep.get("video_id"),
        "report_model": rep.get("model"),
        "report_schema_version": ver,
        "n_segments": n,
        "n_sentences": len(out),
        "cited_segments": len(cited),
        "cited_fraction": round(len(cited) / n, 4) if n else 0.0,
        "coverage_note": ("인용된 구간 비율이다. M9의 coverage 지표가 아니고 "
                          "**평가 지표가 아니다** — 서술 분포를 보는 기술값이다"),
        "sentences": out,
        "timeline": sorted(out, key=lambda s: (s["time_range"]["start"],
                                               s["sent_id"] or 0)),
        "m9_evaluated": False,
        "test_split_used": False,
        "boundary_note": ("이 렌더러는 report.json을 읽기만 한다. LLM 호출·재생성· "
                          "M9 평가·test 접촉이 없다"),
    }


def to_markdown(doc: dict) -> str:
    L = [f"# AAR 추적 — {doc['video_id']}", "",
         f"- 리포트 모델: `{doc['report_model']}` (schema v"
         f"{doc['report_schema_version']})",
         f"- 문장 {doc['n_sentences']}개 · 인용 구간 {doc['cited_segments']}/"
         f"{doc['n_segments']} ({doc['cited_fraction']:.1%})",
         f"- {doc['coverage_note']}",
         f"- {doc['boundary_note']}", ""]
    for s in doc["timeline"]:
        t = s["time_range"]
        L.append(f"### {_mmss(t['start'])}~{_mmss(t['end'])} · sent "
                 f"{s['sent_id']}")
        L.append("")
        L.append(s["text"])
        L.append("")
        L.append(f"근거 (재생 {_mmss(s['seek_to'])}):")
        L.append("")
        for e, sp in zip(s["evidence"], s["spans"]):
            L.append(f"- `seg#{e['idx']}` {_mmss(sp['start'])}~"
                     f"{_mmss(sp['end'])}")
            L.append(f"  - 발화: {e['subtitle'] or '없음'}")
            L.append(f"  - 화면: {e['caption'] or '없음'}")
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(
        description="report.json을 시각·근거까지 추적 가능한 형태로 렌더한다")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--report", help="기본값 work/{video_id}/report.json")
    ap.add_argument("--out-md")
    ap.add_argument("--out-json")
    a = ap.parse_args()

    cfg = common.load_config(a.config)
    wdir = common.work_dir(cfg, a.video_id)
    report = Path(a.report) if a.report else wdir / "report.json"
    try:
        doc = build(report, wdir / "segments.json", video_id=a.video_id)
    except TraceError as e:
        print(f"추적 실패 — {e}", file=sys.stderr)
        return 1

    md = to_markdown(doc)
    print(md if not (a.out_md or a.out_json) else
          f"문장 {doc['n_sentences']} · 인용 {doc['cited_segments']}/"
          f"{doc['n_segments']}")
    if a.out_md:
        Path(a.out_md).write_text(md, encoding="utf-8")
        print(f"-> {a.out_md}")
    if a.out_json:
        Path(a.out_json).write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"-> {a.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

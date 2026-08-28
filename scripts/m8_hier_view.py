"""M8 hierarchical prototype 렌더 — 사람이 읽는 AAR.

**본문은 결정적으로 렌더한다.** LLM이 만든 것은 Atomic 내용, Major 제목,
개요 문장뿐이고 시각·근거·계층은 전부 저장된 구조에서 그대로 나온다.

검증에 실패한 문서는 렌더하지 않는다 — 구조가 깨진 채 읽으면 프로토타입 판단이
오염된다.

사용:
    python scripts/m8_hier_view.py runs/m8_hier/<run_kind>/<vid>.json
"""
import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import m8_hier as H                                                 # noqa: E402

MAX_CITES_SHOWN = 8


class ViewError(RuntimeError):
    """구조가 깨진 문서를 읽기 좋게 포장하지 않는다."""


def hhmmss(seg: int, seg_len: int = 5) -> str:
    t = seg * seg_len
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def _cites(cs: list) -> str:
    shown = cs[:MAX_CITES_SHOWN]
    s = " ".join(f"[seg#{c}]" for c in shown)
    return s + (f" 외 {len(cs) - len(shown)}건" if len(cs) > len(shown) else "")


def render(doc: dict, seg_len: int = 5) -> str:
    fails = H.validate_document(doc, doc.get("video_id"))
    if fails:
        raise ViewError(f"구조 검증 실패 — 렌더하지 않는다: {fails}")
    ov = doc.get("overview") or {}
    by_id = {a["event_id"]: a for a in doc["atomic_events"]}
    L = [f"# {doc['video_id']} — 사건 중심 보고서 (prototype)", ""]
    L += ["```",
          f"schema     {doc.get('schema')}",
          f"run_kind   {doc.get('run_kind')}",
          f"구간        {doc['n_segments']}개 "
          f"({hhmmss(doc['n_segments'], seg_len)})",
          f"주요 사건    {len(doc['major_events'])}개 · "
          f"하위 사건 {len(doc['atomic_events'])}개",
          "성격        제품 설계 prototype · 채점하지 않음 · judge 없음",
          "```", ""]

    L += ["## 1. 영상 개요", ""]
    L += [ov.get("overview", "(없음)"), ""]
    L += [f"근거: {' '.join('[' + m + ']' for m in ov.get('supports', []))}",
          f"(개요 출처: {ov.get('source')})", ""]

    L += ["## 2. 전체 흐름", "", ov.get("flow") or "(없음)", ""]

    L += ["## 3. 주요 사건", ""]
    for m in doc["major_events"]:
        L += [f"### {m['major_event_id']} — {m['title']}", "",
              f"**시간:** {hhmmss(m['start_seg'], seg_len)} ~ "
              f"{hhmmss(m['end_seg'] + 1, seg_len)}"
              f"  (seg#{m['start_seg']}~{m['end_seg']})", "",
              "하위 사건", "", "```"]
        for s in m["subevents"]:
            a = by_id[s]
            L.append(f"{hhmmss(a['start_seg'], seg_len)}  {a['event_id']}  "
                     f"{a['title']}")
        L += ["```", ""]
        for s in m["subevents"]:
            a = by_id[s]
            L.append(f"- **{a['title']}** — {a['description']} {_cites(a['cites'])}")
        L += ["", f"근거: {_cites(m['cites'])}", ""]

    L += ["## 4. 특이사항 · 확인 불가", "", ov.get("notes") or "없음", ""]

    L += ["## 5. 추적성", "", "```"]
    L += [f"주요 사건 {len(doc['major_events'])} → 하위 사건 "
          f"{len(doc['atomic_events'])} → 인용 구간 "
          f"{len({c for a in doc['atomic_events'] for c in a['cites']})}개",
          "모든 하위 사건은 인용 구간을 가지며 그 구간은 자기 시간 범위 안에 있다",
          "주요 사건의 시각·근거는 하위 사건에서 코드가 유도했다 (모델 생성 아님)"]
    d = doc.get("diagnostics") or {}
    if d:
        L += ["", f"청크 {d.get('n_chunks')} · 거부 {d.get('n_atomic_rejected')} "
              f"{d.get('rejection_reasons')} · 중복제거 "
              f"{d.get('n_duplicate_removed')}",
              f"grouping {d.get('grouping')}"]
    L += ["```", ""]
    return "\n".join(L)


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--seg-len", type=int, default=5)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    doc = json.loads(Path(a.path).read_text(encoding="utf-8"))
    md = render(doc, a.seg_len)
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")
        print(f"저장: {a.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""사건 목록 일관성 검토 자료 — **동결 직전 1회.** 판정하지 않고 후보만 모은다.

목적은 하나다.

> **8편에 같은 event-unit 규칙이 적용됐는가.**
> "68건의 분포가 예쁜가"가 아니다.

그래서 이 도구는 수정 지시를 하지 않는다. 사전등록 §2·§3 문구에 **직접 대응하는
자리만** 후보로 띄우고, 판단은 사람이 한다.

```
띄우는 것   길이 이상치 · 이름 형식 이탈 · 30초 병합 규칙 후보 · 경계 관행 ·
            미커버 구간 · unclear · 1건 영상
띄우지 않는 것  "사건 수가 적다/많다" · "커버율이 낮다" — 둘 다 사전등록이
            금지한 수정 사유다(§2 "분량 목표를 두지 않는다")
```

**오염 경계.** 읽는 것은 사람이 쓴 CSV와 `label_guard` allowlist를 지난 구간 시각뿐이다.
캡션·자막·검색 결과·M8 출력은 열지 않는다(CLAUDE.md 절대규칙 3).

산출물은 `label_kit/event_inventory/consistency_review.md`(gitignore 대상).

사용:
    python scripts/label_consistency_review.py
"""
import argparse
import io
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                     # noqa: E402
import label_guard                                                # noqa: E402
from event_inventory_kit import OUT, parse_rows, read_csv_text     # noqa: E402
from label_event_ui import panel_videos                           # noqa: E402

REPORT = OUT / "consistency_review.md"
MERGE_WINDOW = 30.0            # 사전등록 §2. 외부 근거 없음도 §7에 이미 적혀 있다
HOLE_MIN_SEC = 10.0            # 이보다 짧은 틈은 경계 흔들림 범위(§7 ±수 초)
NAME_MAX_CHARS = 25
DESCRIPTIVE_TAIL = ("모습", "장면", "화면", "풍경", "보인다", "있다")
CONJ = ("그리고", " 및 ", ", ", " 후 ", "->")


def _sorted(rows: list) -> list:
    return sorted(rows, key=lambda r: (r["start_sec"], r["end_sec"]))


def durations(rows: list) -> list:
    return [r["end_sec"] - r["start_sec"] for r in rows]


def stats(vals: list) -> dict:
    if not vals:
        return {"n": 0, "min": None, "median": None, "max": None}
    return {"n": len(vals), "min": min(vals),
            "median": statistics.median(vals), "max": max(vals)}


def adjacent_gaps(rows: list) -> list:
    """겹침은 음수로 보여준다 — 사전등록 §2에서 동시 사건은 정상이다."""
    s = _sorted(rows)
    return [{"after": i, "gap": s[i + 1]["start_sec"] - s[i]["end_sec"]}
            for i in range(len(s) - 1)]


def zero_gap_ratio(rows: list) -> float:
    """경계 관행 대리 지표. 1.0에 가까우면 연속 분할, 낮으면 사건 사이를 비웠다."""
    g = adjacent_gaps(rows)
    return sum(1 for x in g if x["gap"] == 0) / len(g) if g else 0.0


def _merged_spans(rows: list) -> list:
    out = []
    for r in _sorted(rows):
        if out and r["start_sec"] <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], r["end_sec"]))
        else:
            out.append((r["start_sec"], r["end_sec"]))
    return out


def uncovered_ranges(rows: list, duration_sec: float,
                     min_sec: float = HOLE_MIN_SEC) -> list:
    """**`unclear`도 커버로 센다** — 사람이 이미 본 구간이다. 미커버로 띄우면
    "커버율을 맞추려 사건을 추가"하는 압력이 생기고, 그건 금지된 수정 사유다."""
    holes, cur = [], 0.0
    for a, b in _merged_spans(rows):
        if a - cur >= min_sec:
            holes.append((cur, a))
        cur = max(cur, b)
    if duration_sec - cur >= min_sec:
        holes.append((cur, duration_sec))
    return holes


def coverage_ratio(rows: list, duration_sec: float) -> float:
    return sum(b - a for a, b in _merged_spans(rows)) / duration_sec


def _norm(name: str) -> str:
    return " ".join(str(name).split())


def merge_rule_candidates(rows: list, window: float = MERGE_WINDOW) -> list:
    """사전등록 §2 "같은 목적의 행위가 30초 이내 간격이면 하나로 본다".

    **같은 이름일 때만** 띄운다. 목적이 같은지는 이름만으로 알 수 없고, 유사도
    임계를 새로 만들면 사전등록에 없는 규칙이 생긴다.
    """
    s, out = _sorted(rows), []
    for i in range(len(s) - 1):
        gap = s[i + 1]["start_sec"] - s[i]["end_sec"]
        if _norm(s[i]["event"]) == _norm(s[i + 1]["event"]) and 0 <= gap <= window:
            out.append({"after": i, "event": _norm(s[i]["event"]), "gap": gap})
    return out


def name_form_candidates(rows: list) -> list:
    """사전등록 §3: `event`는 "한 줄 이름. 서술이 아니라 **무슨 일인지**만"."""
    out = []
    for i, r in enumerate(_sorted(rows)):
        n = _norm(r["event"])
        flags = []
        if any(n.endswith(t) for t in DESCRIPTIVE_TAIL):
            flags.append("화면서술")
        if len(n) > NAME_MAX_CHARS:
            flags.append("긴이름")
        if any(c in n for c in CONJ):
            flags.append("복수사건")
        if flags:
            out.append({"row": i, "event": n, "flags": flags})
    return out


def _t(sec: float) -> str:
    s = int(sec)
    return f"{s // 60}:{s % 60:02d}"


def render_video(video_id: str, rows: list, duration_sec: float,
                 n_segments: int) -> str:
    d = stats(durations(rows))
    L = [f"## {video_id}", ""]
    L.append(f"사건 {d['n']}건 · 영상 {_t(duration_sec)}({duration_sec:.0f}초) · "
             f"구간 {n_segments}개 · 커버 {coverage_ratio(rows, duration_sec):.0%}")
    if d["n"]:
        L.append(f"사건 길이 min {d['min']:.0f}초 · median {d['median']:.0f}초 · "
                 f"max {d['max']:.0f}초 · 인접 간격 0초 비율 {zero_gap_ratio(rows):.0%}")
    if d["n"] == 1:
        # 빈 줄로 끊지 않으면 다음 줄이 blockquote 안으로 빨려 들어간다
        L += ["", "> **사건 1건.** 쪼갤 이유를 찾는 자리가 아니다. 같은 event-unit "
                  "정의를 적용했을 때 정말 하나의 지속 사건인지만 확인한다.", ""]
    L += ["", "```", f"{'#':>3} {'구간':>15}  {'길이':>6}  이름"]
    for i, r in enumerate(_sorted(rows), 1):
        mark = " [unclear]" if r["unclear"] else ""
        L.append(f"{i:>3} {_t(r['start_sec'])}~{_t(r['end_sec']):>7}  "
                 f"{r['end_sec'] - r['start_sec']:>5.0f}초  {_norm(r['event'])}{mark}")
    L.append("```")

    for title, items, fmt in (
        ("이름 형식 후보", name_form_candidates(rows),
         lambda x: f"#{x['row'] + 1} {x['event']} — {'·'.join(x['flags'])}"),
        ("30초 병합 규칙 후보", merge_rule_candidates(rows),
         lambda x: f"#{x['after'] + 1}~{x['after'] + 2} {x['event']} — 간격 {x['gap']:.0f}초"),
        ("미커버 구간 (10초 이상)", uncovered_ranges(rows, duration_sec),
         lambda x: f"{_t(x[0])}~{_t(x[1])} ({x[1] - x[0]:.0f}초)"),
        ("unclear", [r for r in _sorted(rows) if r["unclear"]],
         lambda r: f"{_t(r['start_sec'])}~{_t(r['end_sec'])} {_norm(r['event'])} "
                   f"— 사유가 기존 규칙과 맞는지 확인"),
    ):
        if items:
            L += ["", f"**{title}** ({len(items)})", ""]
            L += [f"- {fmt(x)}" for x in items]
    return "\n".join(L) + "\n"


def render(per_video: list) -> str:
    """per_video: [(video_id, rows, duration_sec, n_segments)]"""
    tot = sum(len(r) for _, r, _, _ in per_video)
    allnames = {}
    for vid, rows, _, _ in per_video:
        for r in rows:
            allnames.setdefault(_norm(r["event"]), []).append(vid)
    shared = {k: sorted(set(v)) for k, v in allnames.items() if len(set(v)) > 1}

    L = ["# 사건 목록 일관성 검토 — 동결 직전", "",
         f"영상 {len(per_video)}편 · 사건 {tot}건. **상태 DRAFT.**", "",
         "## 이 문서를 읽는 법", "",
         "확인할 것은 하나다 — **8편에 같은 event-unit 규칙이 적용됐는가.**",
         "", "```",
         "수정해도 되는 것   사전등록 §2·§3 규칙을 명백히 어긴 라벨",
         "수정하면 안 되는 것 길이가 이상해 보인다 / 커버율이 낮다 / 사건 수가 안 맞는다",
         "                   (§2 \"분량 목표를 두지 않는다\", §7 경계 ±수 초 흔들림)",
         "```", "",
         "아래 \"후보\"는 전부 **자동 판정이 아니다.** 사전등록 문구에 대응하는 자리를",
         "기계적으로 모은 것이고, 정상인 경우가 섞여 있다.", "",
         "## 한눈에", "", "```",
         # 한글 헤더는 고정폭에서 두 칸을 먹어 열이 밀린다 — 머리글만 ASCII로 둔다
         f"{'video':<24}{'n':>3}{'cov':>6}{'med':>6}{'max':>6}"
         f"{'gap0':>6}{'name':>6}{'merge':>6}{'hole':>6}",
         "                        사건  커버  median  max  간격0  이름  병합  구멍"]
    for vid, rows, dur, _ in per_video:
        d = stats(durations(rows))
        L.append(f"{vid:<24}{len(rows):>3}{coverage_ratio(rows, dur):>6.0%}"
                 f"{(d['median'] or 0):>6.0f}{(d['max'] or 0):>6.0f}"
                 f"{zero_gap_ratio(rows):>6.0%}"
                 f"{len(name_form_candidates(rows)):>6}"
                 f"{len(merge_rule_candidates(rows)):>6}"
                 f"{len(uncovered_ranges(rows, dur)):>6}")
    L += ["```", ""]
    if shared:
        L += ["## 영상 간 공통 이름", "",
              "같은 이름이 여러 영상에 나오면 입도가 맞았다는 신호다. "
              "**맞추려고 이름을 바꾸지는 않는다.**", ""]
        L += [f"- `{k}` — {', '.join(v)}" for k, v in sorted(shared.items())]
        L.append("")
    L += [render_video(*x) for x in per_video]
    L += ["## 검토 후", "",
          "```",
          "명백한 규칙 적용 오류만 UI에서 수정 → 재내보내기 → validate",
          "그 다음 freeze 8편 → FROZEN_{video_id}.json → 전체 hash 기록",
          "M8 출력은 freeze 이후에만 연다 (사전등록 §0)",
          "```", ""]
    return "\n".join(L)


def collect(cfg, videos=None) -> list:
    out = []
    for vid in (videos or panel_videos()):
        csv_path = OUT / f"{vid}.csv"
        if not csv_path.is_file():
            raise FileNotFoundError(f"{vid}: CSV가 없다 — UI에서 내보내라")
        rows = parse_rows(read_csv_text(csv_path))
        doc = label_guard.load_segments_for_labeling(
            Path(common.work_dir(cfg, vid)) / "segments.json")
        out.append((vid, rows, float(doc["duration_sec"]),
                    int(doc.get("n_segments") or len(doc["segments"]))))
    return out


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default=str(REPORT))
    a = ap.parse_args()
    per_video = collect(common.load_config(str(ROOT / a.config)))
    Path(a.out).write_text(render(per_video), encoding="utf-8")
    print(f"작성: {a.out}")
    print(f"영상 {len(per_video)}편 · 사건 {sum(len(r) for _, r, _, _ in per_video)}건")
    print("후보는 판정이 아니다 — 규칙 적용 오류만 수정한다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

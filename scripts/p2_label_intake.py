"""P2 질의 라벨 입력 — **동결된 배정표를 양식으로 펼치기만 한다.**

```
배정 source of truth   docs/P2_질의쿼터_2026-08-20.json          (고치지 않는다)
영상 길이·구간 수       docs/P2_선정표본_2026-08-20.json          (사전등록값)
사람이 채우는 것        text · gt_start · gt_end (+선택 note)
자동 파생              gt_seg_idx = common.derive_gt_seg_idx
```

**모델 산출물을 하나도 열지 않는다.** `segments.json`을 아예 읽지 않으므로 allowlist
필터를 통과시킬 일도 없다 — 캡션·자막이 같은 파일에 들어 있고 기확보 4편에는 그것이
이미 존재하기 때문에, 파일 자체를 건드리지 않는 쪽이 강한 조건이다. 프레임을 봐야 할
때 쓰는 도구는 `scripts/label_contact_sheet.py`(프레임+시각만)다.

**본 질의 파일을 자동 병합하지 않는다.** 스테이징 JSONL까지만 만든다. `split`은
`p2`이고 `test`가 아니다 — M9가 `split=="test"`를 하드코딩하고 있어서 이 값이 새면
그 자체가 test 접촉이 된다.

**유형은 배정에서 온다.** 사람이 CSV의 `query_type`을 바꾸면 build가 거부한다. 유형을
질의 내용에 맞춰 옮기면 사전등록된 쿼터가 사후 조정되기 때문이다.

**작업 대상 행 수는 여기에 박지 않는다.** 2026-08-24 amendment로 영상당 9 → 5
(총 175)가 됐고, 단일 출처는 `p2_active_design`이다. `load_allocation()`은 동결
배정표 315행의 불변성 검사로 남고, `make`·`build`는 `active_allocation()`을 쓴다.

재현:
  python scripts/p2_label_intake.py make      # 활성 설계 행 수의 빈 CSV
  python scripts/p2_label_intake.py build     # 채운 CSV → 검증 → 스테이징 JSONL
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import common                                                    # noqa: E402

QUOTA = ROOT / "docs" / "P2_질의쿼터_2026-08-20.json"
SAMPLE = ROOT / "docs" / "P2_선정표본_2026-08-20.json"
VIDEOS = ROOT / "data" / "videos"
KIT = ROOT / "label_kit" / "p2"
CSV_PATH = KIT / "p2_label_intake.csv"
OUT_JSONL = KIT / "p2_queries_staging.jsonl"
COLUMNS = ("query_id", "video_id", "query_type", "text", "gt_start", "gt_end",
           "note")
TYPE_KO = {"mixed": "복합형", "subtitle": "자막형", "scene": "장면형"}
TYPE_ORDER = ("mixed", "subtitle", "scene")
SPLIT = "p2"
N_VIDEOS, PER_VIDEO, TOTAL = 35, 9, 315


class IntakeError(RuntimeError):
    pass


def _quota() -> dict:
    return json.loads(QUOTA.read_text(encoding="utf-8"))


def load_allocation() -> list:
    """배정표를 315행으로 펼친다. **여기서 새로 배정하지 않는다.**

    순서는 배정표가 선언한 `(program, source_id) ascending`이고, 영상 안에서는
    `tie_order`(복합 → 자막 → 장면)다. 그래서 같은 입력에 같은 query_id가 나온다.
    """
    q = _quota()
    per_video, program = q["per_video_quota"], q["program_of"]
    if q["n_videos"] != N_VIDEOS or q["per_video"] != PER_VIDEO \
            or q["total_queries"] != TOTAL:
        raise IntakeError(f"배정표 규모가 다르다: {q['n_videos']}편 × "
                          f"{q['per_video']} = {q['total_queries']}")
    if len(per_video) != N_VIDEOS:
        raise IntakeError(f"배정표 영상 수 {len(per_video)} != {N_VIDEOS}")

    rows, totals = [], {v: 0 for v in TYPE_KO.values()}
    for vid in sorted(per_video, key=lambda v: (program[v], v)):
        alloc = per_video[vid]
        if sum(alloc.values()) != PER_VIDEO:
            raise IntakeError(f"{vid}: 영상당 배정 {sum(alloc.values())} "
                              f"!= {PER_VIDEO}")
        n = 0
        for t in TYPE_ORDER:
            for _ in range(alloc.get(t, 0)):
                n += 1
                rows.append({"query_id": f"p2_{vid}_q{n:02d}",
                             "video_id": vid, "query_type": TYPE_KO[t]})
                totals[TYPE_KO[t]] += 1
    want = {TYPE_KO[k]: v for k, v in q["achieved_type_quota"].items()}
    if totals != want:
        raise IntakeError(f"유형 합이 배정표와 다르다: {totals} != {want}")
    if len(rows) != TOTAL:
        raise IntakeError(f"펼친 행이 {len(rows)}행 != {TOTAL}")
    return rows


def active_allocation() -> list:
    """활성 설계가 유지하는 행만. **배정을 새로 하지 않는다 — mask로 거르기만 한다.**

    2026-08-24 amendment로 영상당 9 → 5(총 175)가 됐다. `load_allocation()`은
    동결 배정표 315행의 불변성 검사로 남겨 두고, 실제 작업 대상은 여기서 만든다.
    규모를 이 파일에 상수로 박지 않는다 — `p2_active_design`이 단일 출처다.
    """
    import p2_active_design as ACTIVE
    alloc = load_allocation()
    kept = set(ACTIVE.load(allocation=alloc)["kept_query_ids"])
    return [r for r in alloc if r["query_id"] in kept]


def active_total() -> int:
    import p2_active_design as ACTIVE
    return ACTIVE.load(allocation=load_allocation())["total_queries"]


def _sample() -> dict:
    return {r["source_id"]: r
            for r in json.loads(SAMPLE.read_text(encoding="utf-8"))["selected"]}


def n_segments_of() -> dict:
    return {k: v["n_segments"] for k, v in _sample().items()}


def _measure_duration(path: Path) -> float:
    """m1과 **같은 경로**로 잰다 — cv2 `frame_count / fps`다.

    ffprobe duration을 쓰면 구간 격자가 m1과 어긋날 수 있다. 프레임을 디코드하지
    않으므로 캡션·자막과 무관하다.
    """
    import cv2
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise IntakeError(f"영상을 열지 못한다: {path}")
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    if not fps:
        raise IntakeError(f"fps를 읽지 못한다: {path}")
    return n / fps


def time_bound_of(seg_len: int) -> dict:
    """gt_end 상한.

    31편은 선정표본에 `duration_sec`이 있다. 기확보 4편은 없다 — 거기서
    `n_segments * seg_len`을 쓰면 마지막 구간이 5초보다 짧을 때 **실제 영상 끝보다
    뒤의 gt_end가 통과**한다(leakage는 아니지만 GT 타당성 문제다). 그래서 그 4편은
    파일을 직접 재고, 사전등록된 구간 수와 격자가 맞는지 대조한다. 파일이 없으면
    느슨한 상한으로 내려가지 않고 멈춘다.
    """
    out = {}
    for vid, rec in _sample().items():
        if rec.get("duration_sec") is not None:
            out[vid] = rec["duration_sec"]
            continue
        f = VIDEOS / f"{vid}.mp4"
        if not f.is_file():
            raise IntakeError(f"{vid}: 영상 파일이 없다 ({f}) — 길이를 추정해 "
                              f"넘어가지 않는다")
        dur = _measure_duration(f)
        got = -(-dur // seg_len)                       # ceil(dur / seg_len)
        if got != rec["n_segments"]:
            raise IntakeError(
                f"{vid}: 재본 길이 {dur:.2f}s의 격자 {int(got)}가 사전등록 "
                f"n_segments {rec['n_segments']}와 다르다")
        out[vid] = dur
    return out


def make(path=CSV_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        for r in active_allocation():
            w.writerow({**r, "text": "", "gt_start": "", "gt_end": "",
                        "note": ""})
    return path


def _num(val, col, qid) -> float:
    try:
        return float(val)
    except ValueError:
        raise IntakeError(f"{qid}: {col}가 숫자가 아니다 — {val!r}")


def build(path=CSV_PATH) -> list:
    """채운 CSV를 검증하고 gt_seg_idx를 파생한다. **하나라도 어긋나면 멈춘다.**"""
    alloc = {r["query_id"]: r for r in active_allocation()}
    seg_len = common.load_config(ROOT / "config.yaml")["seg_len_sec"]
    nseg, dur = n_segments_of(), time_bound_of(seg_len)
    raw = list(csv.DictReader(
        Path(path).read_text(encoding="utf-8-sig").splitlines()))
    want = active_total()
    if len(raw) != want:
        raise IntakeError(f"{len(raw)}행이다 — 활성 설계는 {want}행이고 "
                          f"부분 제출을 받지 않는다")

    out, seen = [], set()
    for r in raw:
        qid = (r.get("query_id") or "").strip()
        if qid in seen:
            raise IntakeError(f"{qid}: query_id 중복")
        seen.add(qid)
        a = alloc.get(qid)
        if a is None:
            raise IntakeError(f"{qid}: 배정에 없다 — query_id를 손으로 만들지 마라")
        vid = (r.get("video_id") or "").strip()
        if vid != a["video_id"]:
            raise IntakeError(f"{qid}: video_id가 배정과 다르다 "
                              f"({vid} != {a['video_id']})")
        if vid not in nseg:
            raise IntakeError(f"{qid}: {vid}가 배정에 없다")
        t = (r.get("query_type") or "").strip()
        if t not in TYPE_KO.values():
            raise IntakeError(f"{qid}: 알 수 없는 유형 {t!r}")
        if t != a["query_type"]:
            raise IntakeError(
                f"{qid}: query_type을 바꿀 수 없다 ({t} != {a['query_type']}) — "
                f"유형은 동결된 배정에서 온다")
        for col in ("text", "gt_start", "gt_end"):
            if not (r.get(col) or "").strip():
                raise IntakeError(f"{qid}: {col}가 비어 있다")
        s = _num(r["gt_start"].strip(), "gt_start", qid)
        e = _num(r["gt_end"].strip(), "gt_end", qid)
        if not 0 <= s < e:
            raise IntakeError(f"{qid}: gt_start < gt_end여야 한다 ({s}, {e})")
        if e > dur[vid]:
            raise IntakeError(f"{qid}: 영상 길이 {dur[vid]}s를 넘는다 (gt_end {e})")
        out.append({"query_id": qid, "video_id": vid,
                    "text": r["text"].strip(), "type": t,
                    "gt_start": s, "gt_end": e,
                    "gt_seg_idx": common.derive_gt_seg_idx(s, e, nseg[vid],
                                                           seg_len),
                    "split": SPLIT,
                    **({"note": r["note"].strip()}
                       if (r.get("note") or "").strip() else {})})
    return out


def write_jsonl(rows: list, path=OUT_JSONL) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["make", "build"])
    ap.add_argument("--csv", default=str(CSV_PATH))
    ap.add_argument("--out", default=str(OUT_JSONL))
    a = ap.parse_args()
    if a.cmd == "make":
        p = make(a.csv)
        rows = load_allocation()
        by_type = {}
        for r in rows:
            by_type[r["query_type"]] = by_type.get(r["query_type"], 0) + 1
        # 콘솔이 cp949라 em dash(U+2014)를 못 찍는다 - 출력은 ASCII 구분자만 쓴다
        print(f"{p} : {len(rows)}행 / " +
              " ".join(f"{k} {v}" for k, v in sorted(by_type.items())))
        print("채울 칸은 text, gt_start, gt_end (+선택 note) 뿐이다")
        return 0
    rows = build(a.csv)
    p = write_jsonl(rows, a.out)
    print(f"{p} : {len(rows)}행 검증 통과 / split={SPLIT}")
    print("**본 질의 파일에 병합하지 않았다** — 병합은 승인 후 별도 단계다")
    return 0


if __name__ == "__main__":
    sys.exit(main())

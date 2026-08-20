"""P2 후보 metadata gate — **재생 시간만 본다.**

규격: `docs/P2_영상후보_스크리닝규격_2026-08-20.md`.

`seg_len_sec = 5`이므로 세그먼트 수가 재생 시간에 정비례한다. 목표 150~400세그는
**750~2,000초**다. 그래서 인덱싱·다운로드 없이 메타데이터만으로 걸러낼 수 있다.

**추측하지 않는다.** 길이를 못 읽으면 `duration_pending`이고 `eligible`은 `None`이다
(`False`가 아니다 — 부적격과 미확인은 다르다). 사용 불가 영상도 지우지 않고
`unavailable`로 남긴다.

**성능을 보지 않는다.** 캡션·검색 점수·모델명이 이 모듈에 들어오지 않는다. 제목도
기록만 하고 판정에 쓰지 않는다 — 제목으로 거르면 그것이 표본 선택 축이 된다.
"""
import argparse
import csv
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SEG_LEN = 5
TARGET_SEGMENTS = (150, 400)
MIN_SEC = TARGET_SEGMENTS[0] * SEG_LEN
MAX_SEC = TARGET_SEGMENTS[1] * SEG_LEN
# 발화 구조가 다르다 — 말하는 사람만 나오는 영상은 캡션 채널이 설명할 화면 변화가
# 적다. 표집 범위에 넣을지는 **사전등록으로 정한다.** 여기서는 분리만 한다
OUT_OF_SCOPE_PENDING = ("lecture_dialog",)


def est_segments(duration_sec: int) -> int:
    return math.ceil(duration_sec / SEG_LEN)


def eligible(duration_sec: int) -> bool:
    return MIN_SEC <= duration_sec <= MAX_SEC


def classify(meta: dict) -> dict:
    """`meta`는 `{"id", "duration", "title"?, "error"?}`. 길이만 판정에 쓴다."""
    d = meta.get("duration")
    out = {"video_id": meta.get("id"), "title": meta.get("title") or "",
           "duration_sec": d, "est_segments": None, "eligible": None,
           "availability": "duration_pending", "error": meta.get("error") or ""}
    if meta.get("error"):
        out["availability"] = "unavailable"
        return out
    if d is None:
        return out
    out["est_segments"] = est_segments(int(d))
    out["eligible"] = eligible(int(d))
    out["availability"] = "ok"
    return out


def probe(ids: list, timeout: int = 900) -> dict:
    """yt-dlp로 메타데이터만 읽는다 — 다운로드하지 않는다."""
    got = {}
    for vid in ids:
        cmd = ["yt-dlp", "--skip-download", "--no-warnings",
               "--print", "%(id)s\t%(duration)s\t%(title)s",
               f"https://www.youtube.com/watch?v={vid}"]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=120, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            got[vid] = {"id": vid, "duration": None, "error": "timeout"}
            continue
        line = (p.stdout or "").strip().splitlines()
        if p.returncode != 0 or not line:
            err = (p.stderr or "").strip().splitlines()
            got[vid] = {"id": vid, "duration": None,
                        "error": (err[-1][:200] if err else "no output")}
            continue
        parts = line[0].split("\t")
        dur = None
        if len(parts) > 1 and parts[1] not in ("NA", "None", ""):
            try:
                dur = int(float(parts[1]))
            except ValueError:
                dur = None
        got[vid] = {"id": vid, "duration": dur,
                    "title": parts[2] if len(parts) > 2 else ""}
    return got


def source_of(family: str) -> str:
    """방송사·출처. `family`의 접두다."""
    return family.split("_")[0]


def summarize(rows: list) -> dict:
    by_family = {}
    for r in rows:
        f = by_family.setdefault(r["family"], {"eligible": 0, "ineligible": 0,
                                               "pending": 0})
        e = r.get("eligible")
        f["eligible" if e is True else
          ("ineligible" if e is False else "pending")] += 1
    elig = [r for r in rows if r.get("eligible") is True]
    fam_counts = Counter(r["family"] for r in elig)
    share = (max(fam_counts.values()) / len(elig)) if elig else 0.0
    # **프로그램별만 보면 방송사 집중을 놓친다.** 실측에서 프로그램 최대 점유가
    # 0.2564인데 EBS 방송사 점유는 0.9091이었다 — 같은 제작 관행·자막 스타일이
    # 표본을 지배하면 그것이 외적 타당도 문제가 된다
    src_counts = Counter(source_of(r["family"]) for r in elig)
    src_share = (max(src_counts.values()) / len(elig)) if elig else 0.0
    in_scope = [r for r in elig if r["family"] not in OUT_OF_SCOPE_PENDING]
    return {
        "n_candidates": len(rows),
        "eligible_total": len(elig),
        "eligible_in_scope": len(in_scope),
        "ineligible_total": sum(1 for r in rows if r.get("eligible") is False),
        "pending_total": sum(1 for r in rows if r.get("eligible") is None),
        "by_family": by_family,
        "max_family_share": round(share, 4),
        "by_source": dict(src_counts),
        "max_source_share": round(src_share, 4),
        "source_concentration_note": ("방송사 단위 집중은 프로그램 단위 지표에 "
                                      "드러나지 않는다. 제작 관행·자막 스타일이 "
                                      "표본을 지배하면 외적 타당도 문제다"),
        "concentration_note": ("한 프로그램이 적격 표본을 지배하면 그 자체가 표본 "
                               "선택 축이다 — 프로그램별 상한을 사전등록으로 정한다"),
        "out_of_scope_pending_decision": list(OUT_OF_SCOPE_PENDING),
        "out_of_scope_note": ("말하는 사람만 나오는 영상은 캡션 채널이 설명할 화면 "
                              "변화가 적다. 표집 범위 포함 여부를 사전등록으로 정한다"),
        "dedup_vs_existing": {
            "method": "program_family_disjointness",
            "id_level_verified": False,
            "reason": ("기존 11편의 work/*/meta.json에 출처 URL·영상 ID가 기록돼 "
                       "있지 않다 — ID 대조가 불가능하다. 방송사 프로그램 계열과 "
                       "기존 크리에이터 채널이 서로 겹치지 않는다는 근거로만 판단한다"),
            "fix": "앞으로 신규 영상은 source_url·source_id를 meta에 기록한다",
        },
        "bounds": {"seg_len_sec": SEG_LEN, "target_segments": list(TARGET_SEGMENTS),
                   "min_sec": MIN_SEC, "max_sec": MAX_SEC},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reservoir",
                    default="docs/probes/_scratch/p2_reservoir_ids.csv")
    ap.add_argument("--out", default="docs/probes/_scratch/p2_video_pool.csv")
    ap.add_argument("--summary",
                    default="docs/probes/_scratch/p2_pool_summary.json")
    ap.add_argument("--limit", type=int, help="canary: first N ids only")
    a = ap.parse_args()
    src = list(csv.DictReader(
        Path(ROOT / a.reservoir).read_text(encoding="utf-8-sig").splitlines()))
    if a.limit:
        src = src[:a.limit]
    metas = probe([r["video_id"] for r in src])
    rows = []
    for r in src:
        c = classify(metas.get(r["video_id"], {"id": r["video_id"],
                                               "duration": None}))
        rows.append({**c, "family": r["family"], "domain": r["domain"]})
    cols = ["video_id", "family", "domain", "duration_sec", "est_segments",
            "eligible", "availability", "title", "error"]
    with Path(ROOT / a.out).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in cols} for r in rows)
    s = summarize(rows)
    Path(ROOT / a.summary).write_text(
        json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"probed: {len(rows)}")
    print(f"eligible: {s['eligible_total']} (in scope {s['eligible_in_scope']})")
    print(f"ineligible: {s['ineligible_total']}  pending: {s['pending_total']}")
    print(f"max family share of eligible: {s['max_family_share']}")
    print(f"max source share of eligible: {s['max_source_share']} {s['by_source']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

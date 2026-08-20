"""신규 test 질의 라벨 입력 → 검증 → 스테이징 JSONL.

**사람이 채우는 것은 5칸뿐이다** — `text` / `type` / `gt_start` / `gt_end` (+선택 `note`).
`query_id`는 미리 채워져 있고 `gt_seg_idx`는 `derive_gt_seg_idx`가 파생한다.
사람이 세그먼트 번호를 손으로 적으면 파생 규칙과 어긋난 예외가 생긴다(wl_q03 전례 —
새 예외를 만들지 않는다, 절대규칙 3).

**본 질의 파일을 자동 병합하지 않는다.** `data/queries/queries.jsonl`은 확정 test
평가의 입력이라, 여기에 자동으로 붙이면 평가 대상이 조용히 바뀐다. 이 스크립트는
`label_kit/queries_new.jsonl`까지만 만들고 **병합은 승인 후 별도 단계**로 남긴다.

**유형 목표를 먼저 등록하고 어긋나면 경고한다**(절대규칙 3: 병합 전 유형별 목표 사전
등록). 목표는 `label_kit/type_targets.json`에 있고, 라벨을 다 쓴 뒤 목표를 고치는 것은
사후 조정이므로 하지 않는다.

검증 항목: 스키마·유형값·시간 순서·영상 길이 초과·중복 query_id·gt_seg_idx 파생 일치.

work/·results/·config·queries.jsonl 불변.
재현:
  python scripts/label_intake.py make                 # 빈 CSV + 목표 생성
  python scripts/label_intake.py build                # 채운 CSV → 검증 → JSONL
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402
import label_guard                                        # noqa: E402
# **순수 파생 함수 하나만** 가져온다 — 시각 -> 세그먼트 번호.
# 순위·검색·점수에 닿지 않는다. CLAUDE.md 절대규칙 3이 이 도구를 허용
# 도구로 명시하면서 `gt_seg_idx 자동 파생`을 그 역할로 지정한다
from m6_evaluate import derive_gt_seg_idx                  # noqa: E402

KIT = ROOT / "label_kit"
CSV_PATH = KIT / "label_intake.csv"
TARGETS = KIT / "type_targets.json"
OUT_JSONL = KIT / "queries_new.jsonl"
TYPES = ["자막형", "장면형", "복합형"]

# 영상별 query_id 접두어와 목표 건수. 현행 test 39건(자막 12·복합 14·장면 13)에
# 34건을 더해 ~73건을 만든다 — hit@5가 유의로 전환되는 규모(평가확장_계획 §1).
VIDEOS = {
    "jissi_farm":             {"prefix": "jf", "n": 12},
    "softyeon_ceramics":      {"prefix": "sy", "n": 11},
    "baekmansonghee_jirisan": {"prefix": "bm", "n": 11},
}
TYPE_TARGET = {"자막형": 11, "복합형": 12, "장면형": 11}      # 합 34


def load_segs(cfg, vid):
    """**allowlist 로더를 거친다** — 캡션·자막을 읽지 않는다.

    같은 `segments.json`에 캡션이 들어 있고, 기확보 영상에는 그것이 이미
    존재한다. 관행이 아니라 도구가 차단해야 한다(`label_guard`).
    """
    p = Path(common.work_dir(cfg, vid)) / "segments.json"
    return label_guard.load_segments_for_labeling(p)["segments"]


def cmd_make(cfg):
    KIT.mkdir(parents=True, exist_ok=True)
    if CSV_PATH.exists():
        sys.exit(f"이미 있다: {CSV_PATH} — 덮어쓰지 않는다. 지우고 다시 실행하라")
    rows = []
    for vid, spec in VIDEOS.items():
        segs = load_segs(cfg, vid)
        dur = segs[-1]["end"]
        for i in range(1, spec["n"] + 1):
            rows.append({"query_id": f"{spec['prefix']}_q{i:02d}", "video_id": vid,
                         "text": "", "type": "", "gt_start": "", "gt_end": "",
                         "note": f"영상 길이 {dur}초"})
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    TARGETS.write_text(json.dumps(
        {"declared_before_labeling": True,
         "current_test": {"자막형": 12, "복합형": 14, "장면형": 13, "total": 39},
         "new_target": {**TYPE_TARGET, "total": sum(TYPE_TARGET.values())},
         "per_video": {v: s["n"] for v, s in VIDEOS.items()},
         "why": "hit@5를 유의로 전환하는 데 필요한 규모 ~73건(평가확장_계획 §1)",
         "rule": "라벨을 쓴 뒤 이 목표를 고치지 않는다 — 사후 조정 금지"},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"CSV  -> {CSV_PATH}  ({len(rows)}행)")
    print(f"목표 -> {TARGETS}")
    print("\n채울 칸: text / type / gt_start / gt_end")
    print(f"type 은 {' · '.join(TYPES)} 중 하나")
    print("\n규칙: 프레임 실물만 보고 판정한다. 검색을 돌려보고 고르지 마라.")


def cmd_build(cfg, strict):
    if not CSV_PATH.exists():
        sys.exit(f"없다: {CSV_PATH} — 먼저 make 를 실행하라")
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8-sig")))
    segcache = {v: load_segs(cfg, v) for v in VIDEOS}
    seg_len = cfg["seg_len_sec"]
    out, errs, seen = [], [], set()
    for r in rows:
        qid = (r.get("query_id") or "").strip()
        if not (r.get("text") or "").strip():
            continue                                   # 미작성 행은 건너뛴다
        vid = (r.get("video_id") or "").strip()
        where = f"{qid}"
        if qid in seen:
            errs.append(f"{where}: query_id 중복")
        seen.add(qid)
        if vid not in segcache:
            errs.append(f"{where}: 알 수 없는 video_id {vid}")
            continue
        t = (r.get("type") or "").strip()
        if t not in TYPES:
            errs.append(f"{where}: type 값이 {TYPES} 중 하나가 아니다 ({t!r})")
        try:
            s, e = float(r["gt_start"]), float(r["gt_end"])
        except (ValueError, KeyError, TypeError):
            errs.append(f"{where}: gt_start/gt_end 가 숫자가 아니다")
            continue
        segs = segcache[vid]
        dur = segs[-1]["end"]
        if not (0 <= s < e):
            errs.append(f"{where}: 시간 순서 오류 ({s} → {e})")
        if e > dur:
            errs.append(f"{where}: gt_end {e}초가 영상 길이 {dur}초를 넘는다")
        idx = derive_gt_seg_idx(s, e, len(segs), seg_len)
        if not idx:
            errs.append(f"{where}: 겹치는 세그먼트가 없다")
        out.append({"query_id": qid, "video_id": vid, "text": r["text"].strip(),
                    "type": t, "gt_start": s, "gt_end": e,
                    "gt_seg_idx": idx, "split": "test"})

    got = Counter(q["type"] for q in out)
    print(f"작성 {len(out)}건 · 유형 {dict(got)}")
    tgt = json.loads(TARGETS.read_text(encoding="utf-8"))["new_target"]
    for t in TYPES:
        d = got.get(t, 0) - tgt[t]
        if d:
            print(f"  [목표 대비] {t}: {got.get(t,0)} / 목표 {tgt[t]} ({d:+d})")

    if errs:
        print("\n검증 실패:")
        for m in errs:
            print("  -", m)
        if strict:
            sys.exit(1)
    else:
        print("\n검증 통과")

    OUT_JSONL.write_text(
        "\n".join(json.dumps(q, ensure_ascii=False) for q in out) + "\n",
        encoding="utf-8")
    print(f"-> {OUT_JSONL}")
    print("\n**본 queries.jsonl 에 자동 병합하지 않았다.** 병합은 승인 후 별도 단계다.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["make", "build"])
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--strict", action="store_true", help="검증 실패 시 종료코드 1")
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))
    (cmd_make if a.cmd == "make" else lambda c: cmd_build(c, a.strict))(cfg)


if __name__ == "__main__":
    main()

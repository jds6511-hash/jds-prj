"""STEP 7 — target vs wrong-top1 연결. 캡션 텍스트와 프레임을 연다.

STEP 6이 저장한 숫자에 캡션·프레임을 붙인다. **formal taxonomy·count를 만들지 않는다.**
해석은 STEP 8에서 사람이 읽는 문장으로 쓴다.

프레임은 미추적 폴더에만 복사한다 — pland_costco_hosting은 provenance legacy_exempt로
출처가 불명이라 공개·배포하지 않는다(계획 §1).

사용: python docs/probes/casestudy_step7_extract.py [step6_json]
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RD = ROOT / "runs/casestudy_caption_retrieval/cs_20260825"
V = "pland_costco_hosting"
ARMS = ("3b", "4b")
FRAME_DIR = RD / "frames_for_discussion"


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else (RD / "step6_retrieval_alpha0.json")
    step6 = json.loads(src.read_text(encoding="utf-8"))

    caps, segs_by_arm = {}, {}
    for arm in ARMS:
        wd = RD / ("%s_fresh" % arm) / "work" / V
        S = json.loads((wd / "segments.json").read_text(encoding="utf-8"))["segments"]
        segs_by_arm[arm] = S
        caps[arm] = {s["idx"]: (s.get("caption") or "") for s in S}

    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    frame_src = ROOT / "work" / V          # 원본 프레임(양 arm 입력이 동일함을 이미 확인)
    wanted, out_rows = set(), []

    for r in step6["results"]:
        tgt = r["target_segment"]
        wanted.add(tgt)
        row = {k: r[k] for k in ("query_id", "query_type", "query", "scene_id",
                                 "target_segment", "target_start", "target_end")}
        row["target_caption"] = {arm: caps[arm][tgt] for arm in ARMS}
        row["arms"] = {}
        for arm in ARMS:
            a = r["arms"][arm]
            t1 = a["top1_segment"]
            wanted.add(t1)
            row["arms"][arm] = {
                "target_rank": a["target_rank"], "target_score": a["target_score"],
                "top1_segment": t1, "top1_score": a["top1_score"],
                "top1_start": a["top1_start"],
                "top1_is_target": t1 == tgt,
                "top1_caption": caps[arm][t1],
                "top3": [dict(x, caption=caps[arm][x["idx"]]) for x in a["top3"]],
            }
        out_rows.append(row)

    copied = {}
    for i in sorted(wanted):
        s = segs_by_arm["3b"][i]
        dst = FRAME_DIR / ("seg%04d_%05.0fs.jpg" % (i, s["start"]))
        p = frame_src / s["rep_frame"]
        if p.is_file():
            shutil.copyfile(p, dst)
            copied[i] = dst.name

    lens = {arm: [len(c) for c in caps[arm].values()] for arm in ARMS}
    out = {
        "step": "STEP7_target_vs_top1",
        "source_step6": src.name,
        "video_id": V,
        "n_segments": step6["n_segments"],
        "view": step6["view"], "alpha": step6["alpha"],
        "illustrative_top1_hit_count": step6["illustrative_top1_hit_count"],
        "illustrative_top1_hit_count_caveat": step6["illustrative_top1_hit_count_caveat"],
        "caption_length_mean": {arm: round(sum(v) / len(v), 1) for arm, v in lens.items()},
        "frames_dir": str(FRAME_DIR.relative_to(ROOT)).replace("\\", "/"),
        "frames_note": ("출처 불명(provenance legacy_exempt) 영상의 프레임이다. "
                        "튜터 논의 한정, 공개·배포하지 않는다. git 미추적."),
        "frames": copied,
        "queries": out_rows,
    }
    dst = RD / "step7_target_vs_top1.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote %s" % dst)
    print("frames copied: %d -> %s" % (len(copied), FRAME_DIR))
    print("caption length mean: 3B %.1f · 4B %.1f"
          % (out["caption_length_mean"]["3b"], out["caption_length_mean"]["4b"]))
    miss = [r["query_id"] for r in out_rows
            if not (r["arms"]["3b"]["top1_is_target"] and r["arms"]["4b"]["top1_is_target"])]
    print("적어도 한 arm에서 target이 1위가 아닌 질의: %d/%d" % (len(miss), len(out_rows)))


if __name__ == "__main__":
    main()

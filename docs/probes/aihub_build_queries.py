"""[AI Hub 비디오 장면 설명문 데이터 -> 외부 평가 질의 파일 생성. 채택 아님, 외부 검증용]

우리 test 39건은 단일 라벨러 자체 라벨이다(IMPLEMENTATION_GUIDE 9-1(c) 미결).
AI Hub `003.비디오 장면 설명문 생성 데이터` Validation 분할은 제3자 라벨에 시간 구간이
붙어 있어 외부 평가셋이 된다.

**절대 지킬 것 둘.**
1. 이 데이터로 아무것도 튜닝하지 않는다. α는 dev 확정값(0.5)을 주입해 1회만 돌린다.
   여기서 α를 다시 고르면 외부 검증이 아니라 또 하나의 dev가 된다.
2. 절대값을 우리 test와 비교하지 않는다. 영상이 60초라 세그먼트가 12개뿐이고
   (우리 영상은 122~357개) Recall@5의 무작위 기저가 0.42다. **비교 가능한 것은
   baseline↔proposed 쌍체 차이뿐이다.**

`split`은 "external"로 둔다 — m6의 dev/test 경로와 섞이면 안 된다.
`type`에는 도메인을 넣어 m6의 by_type 분해가 도메인별 분해로 나오게 한다.

재현: python docs/probes/aihub_build_queries.py --out data_aihub
"""
import argparse, json, os, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from m6_evaluate import derive_gt_seg_idx                        # noqa: E402

SRC = ROOT / "Sample/003.비디오 장면 설명문 생성 데이터/01-1.정식개방데이터/Validation"
SEG_LEN = 5
DOMAIN_TAG = {"VL_D3_드라마": "드라마", "VL_D3_여행": "여행", "VL_D3_요리_음식": "요리음식"}


def parse_ts(t: str) -> float:
    """'00:05.00000' -> 5.0. 분:초.소수 형식."""
    m, rest = t.split(":")
    return int(m) * 60 + float(rest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data_aihub")
    ap.add_argument("--link", action="store_true",
                    help="영상을 복사하지 않고 경로만 기록(전송은 별도)")
    a = ap.parse_args()
    out = ROOT / a.out
    (out / "videos").mkdir(parents=True, exist_ok=True)
    (out / "queries").mkdir(parents=True, exist_ok=True)

    # 라벨 인덱스: video_name -> (json 경로, 도메인 폴더)
    lab = {}
    for p in (SRC / "02.라벨링데이터").rglob("*.json"):
        lab[p.stem] = (p, p.relative_to(SRC / "02.라벨링데이터").parts[0])

    rows, skipped, n_vid = [], [], 0
    for mp4 in sorted((SRC / "01.원천데이터").rglob("*.mp4")):
        vid = mp4.stem
        if vid not in lab:
            skipped.append((vid, "라벨 없음"))
            continue
        jp, dom = lab[vid]
        d = json.loads(jp.read_text(encoding="utf-8-sig"))
        n_seg = int(-(-d["duration"] // SEG_LEN))          # 올림
        n_vid += 1
        if not a.link:
            dst = out / "videos" / f"{vid}.mp4"
            if not dst.exists():
                shutil.copy2(mp4, dst)
        for i, s in enumerate(d["sentences"]):
            st, en = parse_ts(s["timestamps"][0]), parse_ts(s["timestamps"][1])
            # 구간이 영상 밖으로 나가거나 뒤집힌 라벨은 버리고 기록한다(수정하지 않는다).
            if not (0 <= st < en <= d["duration"] + 1e-6):
                skipped.append((f"{vid}#{i}", f"구간 이상 {st}~{en} (duration {d['duration']})"))
                continue
            gt = derive_gt_seg_idx(st, en, n_seg, SEG_LEN)
            if not gt:
                skipped.append((f"{vid}#{i}", "겹치는 세그먼트 없음"))
                continue
            rows.append({"query_id": f"ah_{vid}_{i:02d}", "video_id": vid,
                         "text": s["sentences_ko"].strip(),
                         "type": DOMAIN_TAG.get(dom, dom),
                         "gt_start": st, "gt_end": en, "gt_seg_idx": gt,
                         "split": "external"})

    qp = out / "queries" / "queries_aihub.jsonl"
    qp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                  encoding="utf-8")

    import collections
    byt = collections.Counter(r["type"] for r in rows)
    vids = {r["video_id"] for r in rows}
    print(f"영상 {n_vid}편 / 질의 {len(rows)}건 (영상 {len(vids)}편에 분포)")
    for t, n in sorted(byt.items()):
        print(f"  {t:8s} {n:5d}")
    lens = sorted(r["gt_end"] - r["gt_start"] for r in rows)
    segs = sorted(len(r["gt_seg_idx"]) for r in rows)
    print(f"  구간 길이 중앙 {lens[len(lens)//2]:.1f}s / gt 세그먼트 수 중앙 {segs[len(segs)//2]}")
    print(f"  제외 {len(skipped)}건")
    for s in skipped[:5]:
        print("   ", s)
    print("->", qp)


if __name__ == "__main__":
    main()

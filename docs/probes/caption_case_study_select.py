"""캡션 케이스 스터디 — 장면 5개 선정. **선정 규칙을 출력 보기 전에 고정한다.**

튜터 요청(2026-08-25 회의): 3B/4B 캡션을 장면 몇 개에서 나란히 놓고, 그 장면을 겨냥한
질의를 여러 개 만들어 검색했을 때 두 모델의 적중이 어디서 갈리는지, 1위가 다른 장면이면
그게 어떤 장면인지 본다.

**성격.** descriptive diagnostic이다. MRR·CI·유의성을 계산하지 않고, 배포 모델 변경이나
채택 판단의 근거로 쓰지 않는다. 표본 5장면은 판정 규모가 아니다.

**대상.** dev 3편(655구간). 두 arm 캡션이 같은 배치 `prec3_0818b`에서 동시 생성돼
하드웨어·코드 경로가 통제돼 있다. test·P2·P3는 건드리지 않는다.

**선정 규칙 (내용을 보지 않는다).**
  1. 후보 = 기존 dev 질의 96건의 GT 구간. 정답이 이미 검증된 구간만 쓴다.
  2. 유형 배분은 dev 구성비를 따른다 — 복합 34 / 자막 24 / 장면 38 (96건)
     → 5장면 = 복합 2 · 자막 1 · 장면 2. (결과를 보고 정한 비율이 아니다)
  3. 유형 안에서는 영상 라운드로빈으로 흩고, 같은 영상 안에서는 query_id 사전순.
  4. gt_seg_idx가 여러 구간이면 첫 구간을 대표로 쓴다.
  5. 캡션·자막·검색 결과를 보고 고르지 않는다. 이 스크립트는 캡션 파일을 읽지 않는다.

검색·평가 모듈(m5_search·m6_evaluate)을 import하지 않는다.
"""
import json
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUERIES = ROOT / "data/queries/queries.jsonl"
WORK = ROOT / "work"
OUT = ROOT / "docs/probes/_scratch/caption_case_study_scenes.json"
FRAME_DIR = ROOT / "docs/probes/_scratch/caption_case_study_frames"

QUOTA = {"복합형": 2, "자막형": 1, "장면형": 2}


def main() -> None:
    qs = [json.loads(l) for l in
          QUERIES.read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q.get("split") == "dev"]

    by_type = defaultdict(lambda: defaultdict(list))
    for q in sorted(dev, key=lambda r: r["query_id"]):
        by_type[q["type"]][q["video_id"]].append(q)

    picked, used_videos = [], []
    for t in sorted(QUOTA):
        vids = sorted(by_type[t])
        n = QUOTA[t]
        # 영상 라운드로빈 — 이미 뽑힌 영상은 뒤로 민다
        order = sorted(vids, key=lambda v: (used_videos.count(v), v))
        for i in range(n):
            v = order[i % len(order)]
            cand = [q for q in by_type[t][v]
                    if q["query_id"] not in {p["query_id"] for p in picked}]
            if not cand:
                continue
            q = cand[0]
            picked.append(q)
            used_videos.append(v)

    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    scenes = []
    for k, q in enumerate(picked, 1):
        v = q["video_id"]
        segs = json.loads((WORK / v / "segments.json").read_text(encoding="utf-8"))["segments"]
        idx = q["gt_seg_idx"][0]
        s = segs[idx]
        dst = FRAME_DIR / ("scene%d_%s_seg%04d.jpg" % (k, v[:24], idx))
        src = WORK / v / s["rep_frame"]
        if src.is_file():
            shutil.copyfile(src, dst)
        scenes.append({
            "scene_no": k,
            "video_id": v,
            "seg_idx": idx,
            "start": s["start"], "end": s["end"],
            "n_segments_in_video": len(segs),
            "query_type": q["type"],
            "existing_query_id": q["query_id"],
            "existing_query_text": q["text"],
            "gt_seg_idx_all": q["gt_seg_idx"],
            "rep_frame": str(dst.relative_to(ROOT)).replace("\\", "/"),
        })

    OUT.write_text(json.dumps({
        "purpose": "descriptive diagnostic — 3B vs 4B 캡션 케이스 스터디 장면 선정",
        "research_metrics_generated": False,
        "selection_rule": "docs/probes/caption_case_study_select.py 독스트링 참조",
        "quota": QUOTA,
        "corpus": "dev 3편 · 655구간 · prec3_0818b 동시 생성 캡션",
        "scenes": scenes,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote %s (%d scenes)" % (OUT, len(scenes)))
    print("frames -> %s" % FRAME_DIR)


if __name__ == "__main__":
    main()

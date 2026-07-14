"""[test 영상 sanity check — 배너 오작동 점검용, 공식 평가 아님]
abstention 배너 boolean(low_relevance = max(raw_sub_max, raw_cap_max) < τ)만 읽는다.
config·랭킹·공식 결과 미변경, MRR/hit 재계산·기록 없음(절대규칙: test 재평가 아님).
사용자 승인 후 실행(2026-07-13).

목적: τ=0.55(dev 3영상 캘리브)가 test 4영상(여행/AI홍보/요리/테크, 콘텐츠 상이)에서
  (A) 오배제 — 실제 유관 질의 39건에 배너가 잘못 뜨는가(유해 오류)
  (B) 감지 — 명백히 무관한 질의에 배너가 뜨는가
만 확인한다. '명백히 무관' 질의는 selection bias(미묘한 무관에 과대허용)를 여전히 가지므로,
이 점검은 미세 캘리브가 아니라 grosse 오작동 유무만 본다(한계 명시).

출력: scratchpad JSON only. 재현: python docs/probes/abstention_test_sanitycheck.py
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import common
from m5_search import VideoIndex, search_with_stats

# 여행 vlog / AI 홍보 / 통영 요리예능 / 테크 가젯 리뷰 — 어디에도 없는 주제
IRRELEVANT = [
    "북극곰이 빙하 위를 걷는 장면",
    "외과의사가 수술실에서 집도하는 장면",
    "우주비행사가 우주정거장에서 유영하는 장면",
    "축구 선수가 골을 넣고 세리머니하는 장면",
    "오케스트라가 무대에서 교향곡을 연주하는 장면",
    "화산이 용암을 분출하는 장면",
    "법정에서 판사가 판결봉을 두드리는 장면",
    "사막에서 낙타 대상이 모래언덕을 넘는 장면",
]


def low_rel(stats, tau):
    return max(stats["raw_sub_max"], stats["raw_cap_max"]) < tau


def main():
    cfg = common.load_config("config.yaml")
    tau = cfg["abstention_tau"]
    alpha = 0.5  # 확정 α (배너는 raw 통계 기반이라 α 무관하지만 계약대로 전달)
    qs = [json.loads(l) for l in
          Path("data/queries/queries.jsonl").read_text(encoding="utf-8").splitlines()
          if l.strip()]
    test = [q for q in qs if q["split"] == "test"]
    vids = sorted(set(q["video_id"] for q in test))
    idx = {v: VideoIndex.load(cfg, v) for v in vids}

    # (A) 오배제: 실제 유관 질의 39건 — 배너가 뜨면(True) 오배제(유해)
    false_abst = []
    for q in test:
        _, st = search_with_stats(q["text"], idx[q["video_id"]], alpha, cfg)
        ch = max(st["raw_sub_max"], st["raw_cap_max"])
        if low_rel(st, tau):
            false_abst.append({"query_id": q["query_id"], "type": q["type"],
                               "video": q["video_id"], "max_channel": round(ch, 4)})

    # (B) 감지: 무관 질의 × 4영상 — 배너가 떠야(True) 정상 감지
    detect = []
    for v in vids:
        for text in IRRELEVANT:
            _, st = search_with_stats(text, idx[v], alpha, cfg)
            ch = max(st["raw_sub_max"], st["raw_cap_max"])
            detect.append({"video": v, "query": text, "max_channel": round(ch, 4),
                           "banner_fired": low_rel(st, tau)})

    n_det = len(detect)
    n_fired = sum(d["banner_fired"] for d in detect)
    # 유관 39건 max_channel 분포(오배제 여유 확인용)
    chans = []
    for q in test:
        _, st = search_with_stats(q["text"], idx[q["video_id"]], alpha, cfg)
        chans.append(max(st["raw_sub_max"], st["raw_cap_max"]))
    chans.sort()

    out = {
        "tau": tau, "channel": "max(raw_sub_max, raw_cap_max)",
        "note": "test 재평가 아님 — 배너 boolean만. MRR/hit 미계산·미기록.",
        "A_false_abstention": {
            "n_test_queries": len(test),
            "n_banner_fired_on_relevant": len(false_abst),  # 0이 이상적
            "cases": false_abst,
            "relevant_max_channel_min5": [round(c, 4) for c in chans[:5]],
            "relevant_max_channel_median": round(chans[len(chans)//2], 4),
        },
        "B_detection": {
            "n_checks": n_det, "n_banner_fired": n_fired,
            "detection_rate": round(n_fired / n_det, 3),
            "by_video": {v: sum(d["banner_fired"] for d in detect if d["video"] == v)
                         for v in vids},
            "missed": [d for d in detect if not d["banner_fired"]],
        },
    }
    dest = Path(__file__).resolve().parent / "_scratch" / "abstention_test_sanity.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written:", dest)


if __name__ == "__main__":
    main()

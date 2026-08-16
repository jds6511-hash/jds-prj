"""[M8 구조화 map 예비 실행 — dev 전용, GPU 필요, test 미접촉]

**무엇을 확인하나.** 새 구조(사전등록 2차 §1)는 7B가 **JSON 배열**을 안정적으로
낸다는 전제 위에 서 있다. 그 전제부터 깨지면 나머지 판정은 의미가 없다.
사건 목록(정답)이 아직 없으므로 **Event Recall은 여기서 재지 않는다.**
여기서 보는 것은 셋뿐이다.

1. **파싱 성공률** — 청크 몇 개에서 JSON을 건졌나
2. **거른 사유 분포** — 코드 검증자가 무엇을 왜 버렸나
3. **파국 실패** — 다른 언어 이탈·유효 사건 0건 청크

현행 구조와 나란히 돌려 같은 GPU 실행 안에서 비교한다(생성 환경 효과 분리).

재현: python docs/probes/m8_structured_smoke.py --config config_server.yaml
"""
import argparse, collections, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common                                             # noqa: E402
import m8_report as m8                                    # noqa: E402
from llm import make_llm                                  # noqa: E402
from m8_report_quality import truncation, summariness     # noqa: E402

OUT = Path(__file__).resolve().parent / "_scratch"
REPDIR = OUT / "m8_structured_reports"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default="m8_structured_smoke.json")
    ap.add_argument("--videos", default=None,
                    help="쉼표 구분. 비우면 dev 전편. test 영상은 어느 경우에도 거부한다.")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True); REPDIR.mkdir(exist_ok=True)
    cfg = common.load_config(args.config)

    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    test_vids = {q["video_id"] for q in qs if q["split"] == "test"}
    vids = ([v.strip() for v in args.videos.split(",") if v.strip()] if args.videos
            else sorted({q["video_id"] for q in qs if q["split"] == "dev"}))
    # 구조 선택에 test 영상을 쓰면 test 산출물을 보고 구조를 고르는 것이 된다.
    assert not (set(vids) & test_vids), f"test 영상이 섞였다 — 중단: {set(vids) & test_vids}"
    print(len(vids), "편:", vids)

    llm = make_llm(cfg["report_model"],
                   max_new_tokens=cfg.get("report_max_new_tokens", 2048),
                   load_4bit=cfg.get("llm_4bit", False))
    res = {"note": __doc__.strip().splitlines()[0],
           "prereg": "docs/M8_구조변경_사전등록_2026-08-16.md",
           "model": cfg["report_model"], "dev_videos": vids, "arms": {}}

    for arm, fn in (("structured", m8.generate_report_structured),
                    ("current", m8.generate_report)):
        per = {}
        for v in vids:
            wdir = common.work_dir(cfg, v)
            doc = common.load_segments(wdir / "segments.json",
                                       require=["subtitle", "caption"],
                                       seg_len=cfg["seg_len_sec"])
            t0 = time.time()
            rep = fn(doc["segments"], llm, cfg["map_chunk_size"], cfg["map_chunk_overlap"])
            mins = round((time.time() - t0) / 60, 1)
            (REPDIR / f"{arm}__{v}.json").write_text(
                json.dumps({"video_id": v, "arm": arm, **rep}, ensure_ascii=False,
                           indent=2), encoding="utf-8")
            s = summariness(rep, doc["n_segments"])
            row = {"minutes": mins, "n_chunks": len(rep["map_raw_outputs"]),
                   "summariness": s, "truncation": truncation(rep)}
            if arm == "structured":
                rej = collections.Counter(r["reason"] for r in rep["rejected"])
                n_parsed = sum(1 for raw in rep["map_raw_outputs"]
                               if m8.parse_events(raw))
                row |= {"n_events": len(rep["events"]),
                        "parse_ok_chunks": n_parsed,
                        "parse_rate": round(n_parsed / len(rep["map_raw_outputs"]), 3),
                        "rejected_by_reason": dict(rej),
                        "chunk_retries": rep["chunk_retries"],
                        "zero_event_chunks": sum(1 for r in rep["chunk_retries"]
                                                 if not r["recovered"])}
            per[v] = row
            extra = (f"파싱 {row['parse_ok_chunks']}/{row['n_chunks']} 사건 {row['n_events']:>3} "
                     f"거름 {sum(row['rejected_by_reason'].values()):>3}"
                     if arm == "structured" else "")
            print(f"  {arm:<11}{v[:26]:<28} 문장 {s['n_sentences']:>4} "
                  f"커버 {s['coverage_of_video']:>6.1%} {extra} ({mins}분)")
        res["arms"][arm] = per
        (OUT / args.out).write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    print("저장:", OUT / args.out)


if __name__ == "__main__":
    main()

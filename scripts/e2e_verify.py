"""외부 E2E 산출물 검증 — PHASE 1~4 공용. **exit 0은 증거가 아니다.**

구조 검사(항상)와 API 검사(웹 UI가 떠 있을 때만)를 분리한다.
연구 지표를 만들지 않는다 — semantic은 MATCHED/OBSERVED/REVIEW만 낸다.

사용:
  python scripts/e2e_verify.py --video-id e2e_cooking_1
  python scripts/e2e_verify.py --video-id e2e_cooking_1 --base-url http://127.0.0.1:7872
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import numpy as np  # noqa: E402
import yaml  # noqa: E402
import common  # noqa: E402
import e2e_external as E  # noqa: E402

ECHO_MARKERS = ("알겠습니다", "다음은", "묘사한 것", "요청하신", "주문하신")


def structural(cfg: dict, v: dict, wdir: Path) -> dict:
    segs = json.loads((wdir / "segments.json").read_text(encoding="utf-8"))
    S = segs["segments"]
    caps = [(s.get("caption") or "") for s in S]
    subs = [(s.get("subtitle") or "") for s in S]
    meta = json.loads((wdir / "meta.json").read_text(encoding="utf-8"))
    dur = v["observed_duration_sec"]

    emb = {}
    for name in ("emb_sub", "emb_cap"):
        a = np.load(wdir / (name + ".npy"))
        emb[name] = {"shape": list(a.shape), "nan": int(np.isnan(a).sum()),
                     "check": E.check_embedding(a.shape[0], a.shape[1], len(S))}
    prov = segs.get("provenance") or meta.get("provenance") or {}
    return {
        "n_segments": len(S),
        "captions_filled": sum(1 for c in caps if c.strip()),
        "subtitles_filled": sum(1 for c in subs if c.strip()),
        "frames_on_disk": len(list((wdir / "frames").glob("*.jpg"))),
        "corrupted_captions": sum(1 for c in caps if common.is_corrupted_caption(c)),
        "subtitle_credit_hits": sum(1 for c in subs if common.is_subtitle_credit(c)),
        "prompt_echo_like": [i for i, c in enumerate(caps)
                             if any(k in c[:40] for k in ECHO_MARKERS)],
        "segment_bounds": E.check_segment_bounds(S, dur, cfg["seg_len_sec"]),
        "last_end": S[-1]["end"],
        "duration_sec": dur,
        "text_hash": meta.get("text_hash", "")[:16],
        "text_hash_match": meta.get("text_hash") == common.index_text_hash(segs),
        "embeddings": emb,
        "provenance": {k: prov.get(k) for k in
                       ("provenance_status", "source_id", "sha256_verified_at_m1")},
        "resume": E.stage_state(wdir, cfg),
    }


def api(base: str, video_id: str, dur: float, n_seg: int, queries: list) -> dict:
    def post(path, payload):
        req = urllib.request.Request(base + path,
                                     data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    out, stages = [], {}
    for q in queries:
        st, body = post("/api/search", {"video_id": video_id, "query": q["query"],
                                        "top_k": 5})
        rows = body["results"]
        # semantic_observation은 anchor를 (start, end) 쌍으로 받는다. LEVEL 2는 None.
        a_start = q.get("known_anchor_start")
        anchor = None if a_start is None else (a_start, q.get("known_anchor_end", a_start))
        out.append({"q": q, "http": st,
                    "check": E.check_results(rows, dur, n_seg),
                    "observation": E.semantic_observation(q["query"], anchor, rows),
                    "rows": rows})
    stages["search"] = all(o["check"]["ok"] for o in out)
    stages["seek"] = all(r["seek_to"] == r["start"] and 0 <= r["seek_to"] <= dur
                         for o in out for r in o["rows"])

    req = urllib.request.Request(base + "/api/video/" + video_id,
                                 headers={"Range": "bytes=0-1023"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            play = {"status": r.status, "content_range": r.headers.get("Content-Range"),
                    "len": len(r.read())}
    except urllib.error.HTTPError as e:
        play = {"status": e.code, "content_range": None, "len": 0}
    stages["playback"] = play["status"] == 206 and play["len"] == 1024

    try:
        with urllib.request.urlopen(base + "/api/video/__no_such_video__", timeout=30) as r:
            wrong = r.status
    except urllib.error.HTTPError as e:
        wrong = e.code
    stages["wrong_id_404"] = wrong == 404
    return {"search_results": out, "playback": play, "wrong_id_status": wrong,
            "stages": stages}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--base-url", default=None,
                    help="주면 검색·재생 API 검사까지 한다 (웹 UI가 떠 있어야 함)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    m = E.load_manifest()
    v = E.video_of(m, a.video_id)
    wdir = ROOT / "work" / a.video_id

    res = {"video_id": a.video_id, "research_metrics_generated": False,
           "e2e_only": True, "structural": structural(cfg, v, wdir)}
    res["run_identity"] = E.run_identity(
        v, cfg, E.local_file_status(v),
        segments_n=res["structural"]["n_segments"])

    if a.base_url:
        qs = json.loads((ROOT / "planning/e2e_smoke_queries.json").read_text(encoding="utf-8"))
        mine = [q for q in qs["queries"] if q["e2e_id"] == a.video_id]
        res["api"] = api(a.base_url, a.video_id, v["observed_duration_sec"],
                         res["structural"]["n_segments"], mine)

    dst = Path(a.out) if a.out else (
        ROOT / "runs/e2e_external/e2e_external_core_2026-08-25" / a.video_id
        / "verify.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str) + "\n",
                   encoding="utf-8")
    s = res["structural"]
    print("wrote %s" % dst)
    print("구간 %d · 캡션 %d · 자막 %d · 프레임 %d"
          % (s["n_segments"], s["captions_filled"], s["subtitles_filled"],
             s["frames_on_disk"]))
    print("bounds %s · text_hash %s · emb %s/%s · NaN %d"
          % (s["segment_bounds"]["ok"], s["text_hash_match"],
             s["embeddings"]["emb_sub"]["shape"], s["embeddings"]["emb_cap"]["shape"],
             s["embeddings"]["emb_sub"]["nan"] + s["embeddings"]["emb_cap"]["nan"]))
    print("오염 %d · 자막크레딧 %d · echo유사 %d · resume complete %s"
          % (s["corrupted_captions"], s["subtitle_credit_hits"],
             len(s["prompt_echo_like"]), s["resume"].get("complete")))
    if "api" in res:
        print("api stages:", json.dumps(res["api"]["stages"], ensure_ascii=False))
        for o in res["api"]["search_results"]:
            print("  %-24s ok=%s %s top1=seg%d@%.0fs"
                  % (o["q"]["query_id"], o["check"]["ok"],
                     o["observation"]["status"], o["rows"][0]["idx"],
                     o["rows"][0]["start"]))


if __name__ == "__main__":
    main()

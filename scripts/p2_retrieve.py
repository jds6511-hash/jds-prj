"""P2 검색 러너 — **arm 하나를 돌려 per-query RR만 남긴다.**

`p2_evaluate.py`가 두 arm을 비교한다. 이 모듈은 비교하지 않는다.

```
입력   split="p2" 최종 동결 GT JSONL (315행) + 그 파일의 sha256
채널   alpha=0.0 캡션 단독. 자막 임베딩을 읽지 않는다
후보   질의의 video_id에 속한 세그먼트 전체
       근거: 보충2 §2-1 "후보 풀 크기(영상별 세그먼트 수)" ·
             사전등록 §40 P1-b "AI Hub 검색을 영상 내 12개에서 …로 바꿔"
             (영상 내 검색이 baseline이고 전체 풀이 P1의 조작이었다)
       이 러너는 그 규칙을 새로 만들지 않는다
산출   per_query = query_id · video_id · rr · rank · n_candidates
       rank·n_candidates는 audit용이고 PRIMARY는 rr만 쓴다
```

왜 `m6_evaluate`를 쓰지 않는가. 두 군데서 막힌다 — `load_queries`가
`split in ("dev","test")`만 허용하고(그 게이트는 test를 지키는 장치다), per_query 키가
`mrr`라 `p2_evaluate`가 읽는 `rr`와 다르다. 게이트를 넓히는 대신 얇게 분리한다.

**랭킹 동일성**: M5는 코사인 → per-query z-score → 정적 치환 → α 가중합이다.
`alpha=0.0`이고 `static_threshold=0`이면 치환 마스크가 전부 False이므로 최종 점수는
캡션 코사인의 단조 변환이고 순위가 같다. 그래서 캡션 코사인만 계산한다.
`static_threshold != 0`이면 그 등식이 깨지므로 fail-closed로 거부한다.
"""
import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common                                                     # noqa: E402

ALPHA = 0.0
SPLIT = "p2"
N_QUERIES_REQUIRED = 315
SELECTION = ROOT / "docs" / "P2_선정표본_2026-08-20.json"
ARM_CAPTION_MODEL = {"3b": "Qwen/Qwen2.5-VL-3B-Instruct",
                     "4b": "Qwen/Qwen3-VL-4B-Instruct"}
REQUIRED_GT_FIELDS = ("query_id", "video_id", "text", "gt_start", "gt_end",
                      "gt_seg_idx")


class RetrieveError(Exception):
    pass


@dataclass
class CaptionIndex:
    video_id: str
    n_segments: int
    emb_cap: np.ndarray
    text_hash: str
    provenance: dict
    work_dir: str


# ------------------------------------------------------------- 동결 GT 게이트

def load_frozen_gt(path, sha256, require_count: int = N_QUERIES_REQUIRED) -> list:
    """최종 동결 GT만 받는다. 부분 GT·해시 없는 파일은 거부한다."""
    path = Path(path)
    if not path.is_file():
        raise RetrieveError(f"{path} 없음")
    if not sha256:
        raise RetrieveError("동결 해시 없이는 돌리지 않는다 — --gt-sha256 필수")
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != sha256:
        raise RetrieveError(f"GT sha256 불일치 — 기대 {sha256[:12]}… 실제 {got[:12]}…")
    rows = [json.loads(ln) for ln in
            path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(rows) != require_count:
        raise RetrieveError(f"{len(rows)}행이다 — {require_count}건 전부여야 한다. "
                            "부분 GT로는 돌리지 않는다")
    seen = set()
    for r in rows:
        qid = r.get("query_id")
        for f in REQUIRED_GT_FIELDS:
            if f not in r or r[f] is None or r[f] == "":
                raise RetrieveError(f"{qid}: {f} 없음")
        if not r["gt_seg_idx"]:
            raise RetrieveError(f"{qid}: gt_seg_idx 비어 있음")
        if r.get("split") != SPLIT:
            raise RetrieveError(f"{qid}: split={r.get('split')!r} — "
                                f"{SPLIT!r}만 받는다")
        if qid in seen:
            raise RetrieveError(f"query_id 중복: {qid}")
        seen.add(qid)
    return rows


def frozen_segment_counts(path=SELECTION) -> dict:
    """사전등록 선정표본의 영상별 세그먼트 수. 후보 수 대조의 단일 출처다."""
    sel = json.loads(Path(path).read_text(encoding="utf-8"))["selected"]
    return {r["source_id"]: r["n_segments"] for r in sel}


# ------------------------------------------------------------- 색인·랭킹

def load_caption_index(cfg: dict, video_id: str) -> CaptionIndex:
    wdir = common.work_dir(cfg, video_id)
    doc = common.load_segments(wdir / "segments.json", require=["caption"],
                               seg_len=cfg["seg_len_sec"])
    meta_p, emb_p = wdir / "meta.json", wdir / "emb_cap.npy"
    for p in (meta_p, emb_p):
        if not p.is_file():
            raise RetrieveError(f"{p} 없음 — m4_index를 먼저 돌려라")
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    if meta.get("embed_model") != cfg["embed_model"]:
        raise RetrieveError(f"{video_id}: embed_model 불일치 — "
                            f"색인 {meta.get('embed_model')!r} "
                            f"config {cfg['embed_model']!r}")
    want_hash = common.index_text_hash(doc)
    if meta.get("text_hash") != want_hash:
        raise RetrieveError(f"{video_id}: text_hash 불일치 — 재캡셔닝 후 m4 미실행")
    emb = np.load(emb_p)
    n = doc["n_segments"]
    if emb.shape[0] != n or meta.get("n_segments") != n:
        raise RetrieveError(f"{video_id}: 세그먼트 수 불일치 — "
                            f"segments {n} · meta {meta.get('n_segments')} · "
                            f"emb_cap {emb.shape[0]}")
    return CaptionIndex(video_id=video_id, n_segments=n, emb_cap=emb,
                        text_hash=want_hash,
                        provenance=doc.get("caption_provenance") or {},
                        work_dir=str(wdir))


def rank_caption_only(q_vec, emb_cap) -> list:
    """캡션 코사인 내림차순. 동점은 낮은 idx 우선(stable) — M5와 같은 tiebreak."""
    s = np.asarray(emb_cap, dtype=float) @ np.asarray(q_vec, dtype=float)
    return [int(i) for i in np.argsort(-s, kind="stable")]


def rr_of(ranked: list, gold) -> dict:
    """gold 중 가장 앞선 rank로 RR을 낸다. 후보에 gold가 없으면 오류다."""
    if not gold:
        raise RetrieveError("gt_seg_idx가 비어 있다 — RR을 만들지 않는다")
    goldset = {int(g) for g in gold}
    for pos, idx in enumerate(ranked, start=1):
        if int(idx) in goldset:
            return {"rank": pos, "rr": 1.0 / pos}
    raise RetrieveError(f"gold {sorted(goldset)}가 후보 {len(ranked)}건에 없다 — "
                        "RR=0으로 조용히 넘기지 않는다")


# ------------------------------------------------------------- arm 실행

def _default_embed(model_name: str):
    def fn(texts):
        from m4_index import embed_texts
        return embed_texts(list(texts), model_name)
    return fn


def _git_head():
    import subprocess
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                           capture_output=True, text=True)
        return r.stdout.strip() or None
    except Exception:
        return None


def run_arm(arm: str, queries: list, cfg: dict, frozen_n_segments: dict,
            gt_sha256: str, *, load_index=None, embed_fn=None) -> dict:
    """arm 하나의 per-query RR. 한 건이라도 실패하면 산출물을 만들지 않는다."""
    if arm not in ARM_CAPTION_MODEL:
        raise RetrieveError(f"arm={arm!r} 미허용 — {sorted(ARM_CAPTION_MODEL)}")
    want_model = ARM_CAPTION_MODEL[arm]
    if cfg.get("caption_model") != want_model:
        raise RetrieveError(f"arm={arm}인데 config caption_model="
                            f"{cfg.get('caption_model')!r}다 — arm과 config가 어긋났다")
    if cfg.get("static_threshold") != 0:
        raise RetrieveError(f"static_threshold={cfg.get('static_threshold')!r} — "
                            "0이 아니면 자막 점수가 캡션 채널로 치환돼 캡션 단독이 "
                            "아니다")
    if not gt_sha256:
        raise RetrieveError("동결 해시 없이는 돌리지 않는다")
    load_index = load_index or load_caption_index
    embed_fn = embed_fn or _default_embed(cfg["embed_model"])

    cache, by_video, rows = {}, {}, []
    for q in queries:
        vid = q["video_id"]
        if vid not in frozen_n_segments:
            raise RetrieveError(f"{vid}: 사전등록 선정표본에 없는 영상이다")
        if vid not in cache:
            index = load_index(cfg, vid)
            if index.n_segments != frozen_n_segments[vid]:
                raise RetrieveError(f"{vid}: 후보 {index.n_segments}건 != "
                                    f"사전등록 {frozen_n_segments[vid]}건")
            got_model = (index.provenance or {}).get("model_id")
            if got_model != want_model:
                raise RetrieveError(f"{vid}: 색인 model_id={got_model!r}인데 "
                                    f"arm {arm}은 {want_model!r}를 기대한다 — "
                                    "arm 경로가 뒤바뀌었다")
            cache[vid] = index
            by_video[vid] = {
                "n_segments": index.n_segments, "text_hash": index.text_hash,
                "work_dir": index.work_dir,
                "model_id": got_model,
                "model_revision": (index.provenance or {}).get("model_revision"),
                "prompt_sha256": (index.provenance or {}).get("prompt_sha256")}
        index = cache[vid]
        gold = [int(g) for g in q["gt_seg_idx"]]
        out_of = [g for g in gold if not 0 <= g < index.n_segments]
        if out_of:
            raise RetrieveError(f"{q['query_id']}: gt_seg_idx {out_of}가 후보 "
                                f"범위(0~{index.n_segments - 1}) 밖이다")
        qv = np.asarray(embed_fn([q["text"]]), dtype=float)[0]
        got = rr_of(rank_caption_only(qv, index.emb_cap), gold)
        rows.append({"query_id": q["query_id"], "video_id": vid,
                     "rr": got["rr"], "rank": got["rank"],
                     "n_candidates": index.n_segments})

    return {"run": {"arm": arm, "gt_sha256": gt_sha256, "query_count": len(rows),
                    "alpha": ALPHA, "caption_only": True,
                    "provenance": {
                        "caption_model": want_model,
                        "embed_model": cfg["embed_model"],
                        "static_threshold": cfg["static_threshold"],
                        "seg_len_sec": cfg["seg_len_sec"],
                        "work_root": str(cfg["paths"]["work"]),
                        "git_head": _git_head(),
                        "by_video": by_video}},
            "per_query": rows}


def run_and_write(out_path, *, arm, queries, cfg, frozen_n_segments, gt_sha256,
                  **kw) -> dict:
    """완주한 뒤에만 파일을 쓴다 — 부분 산출물을 남기지 않는다."""
    out = run_arm(arm, queries, cfg, frozen_n_segments, gt_sha256, **kw)
    common.atomic_write_json(out_path, out)
    return out


def assert_same_query_set(a: dict, b: dict) -> bool:
    """두 arm 산출물이 같은 동결 GT·같은 질의 집합인지만 본다. 수치는 보지 않는다."""
    if a["run"]["gt_sha256"] != b["run"]["gt_sha256"]:
        raise RetrieveError("두 arm의 gt_sha256이 다르다 — 같은 동결 GT가 아니다")
    ka = [r["query_id"] for r in a["per_query"]]
    kb = [r["query_id"] for r in b["per_query"]]
    if ka != kb:
        diff = set(ka) ^ set(kb)
        raise RetrieveError(f"두 arm의 질의 집합이 다르다 — {len(diff)}건 차이")
    return True


def main():
    ap = argparse.ArgumentParser(
        description="P2 캡션 단독 검색 — arm 하나만 돌린다. 비교는 p2_evaluate가 한다")
    ap.add_argument("--arm", required=True, choices=sorted(ARM_CAPTION_MODEL))
    ap.add_argument("--config", required=True, help="config_p2_<arm>.yaml")
    ap.add_argument("--gt", required=True, help="최종 동결 GT JSONL (315행)")
    ap.add_argument("--gt-sha256", required=True)
    ap.add_argument("--selection", default=str(SELECTION))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = common.load_config(a.config)
    queries = load_frozen_gt(a.gt, a.gt_sha256)
    out = run_and_write(a.out, arm=a.arm, queries=queries, cfg=cfg,
                        frozen_n_segments=frozen_segment_counts(a.selection),
                        gt_sha256=a.gt_sha256)
    print(f"{a.arm}: {out['run']['query_count']}건 기록 -> {a.out}")


if __name__ == "__main__":
    main()

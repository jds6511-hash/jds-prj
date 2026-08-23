"""P2 검색 러너 — **GT를 보기 전에 고정한다.**

합성 fixture만 쓴다. 3B/4B 실제 산출물은 GT 완성·동결 전에 열지 않는다.

고정하는 것.

```
입력       split="p2" 최종 동결 GT JSONL만. 315/315 + 동결 해시 없으면 거부
채널       alpha=0.0 캡션 단독. 자막 채널을 계산하지 않는다
후보       질의의 video_id에 속한 세그먼트만 (사전등록 보충2 §2-1 · 사전등록 §40)
RR         gold 중 가장 앞선 rank로 계산. 후보에 gold가 없으면 조용한 RR=0 금지
산출        per_query 키는 rr · rank · n_candidates. 두 arm 스키마 동일
안 하는 것  비교 · verdict · bootstrap · m6_evaluate import
```
"""
import ast
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import common                                                    # noqa: E402
import p2_retrieve as R                                          # noqa: E402

SRC = (ROOT / "scripts" / "p2_retrieve.py").read_text(encoding="utf-8")
DIM = 8
EMBED_MODEL = "nlpai-lab/KURE-v1"


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)


# --------------------------------------------------------------- fixture

def _video(work: Path, vid: str, n: int, arm: str = "3b",
           with_subtitle: bool = False) -> dict:
    """캡션 색인 하나. emb_cap = eye(DIM)[:n]이라 score[i] == q[i]가 된다."""
    wdir = work / vid
    wdir.mkdir(parents=True, exist_ok=True)
    segs = []
    for i in range(n):
        s = {"idx": i, "start": i * 5, "end": i * 5 + 5, "caption": f"{vid} 캡션 {i}"}
        if with_subtitle:
            s["subtitle"] = f"발화 {i}"
        segs.append(s)
    doc = {"video_id": vid, "n_segments": n, "segments": segs,
           "caption_provenance": {
               "model_id": R.ARM_CAPTION_MODEL[arm],
               "model_revision": f"rev_{arm}",
               "prompt_sha256": "b7c2598a" + "0" * 56}}
    common.atomic_write_json(wdir / "segments.json", doc)
    np.save(wdir / "emb_cap.npy", np.eye(DIM)[:n])
    common.atomic_write_json(wdir / "meta.json", {
        "embed_model": EMBED_MODEL, "n_segments": n,
        "text_hash": common.index_text_hash(doc)})
    return doc


def _cfg(work: Path, arm: str = "3b", static_threshold: float = 0) -> dict:
    return {"paths": {"work": str(work)}, "embed_model": EMBED_MODEL,
            "seg_len_sec": 5, "static_threshold": static_threshold,
            "caption_model": R.ARM_CAPTION_MODEL[arm]}


def _scores(table: dict):
    """embed_fn 대역 — 질의문을 그대로 점수 벡터로 바꾼다."""
    def fn(texts):
        return np.array([table[t] for t in texts], dtype=float)
    return fn


def _q(qid, vid, text, gold, start=0.0, end=5.0, qtype="복합형"):
    return {"query_id": qid, "video_id": vid, "query_type": qtype, "text": text,
            "gt_start": start, "gt_end": end, "gt_seg_idx": gold, "split": "p2"}


def _gt_file(tmp_path: Path, rows: list) -> tuple[Path, str]:
    import hashlib
    p = tmp_path / "gt.jsonl"
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    p.write_text(body, encoding="utf-8")
    return p, hashlib.sha256(p.read_bytes()).hexdigest()


def _vec(pairs: dict) -> list:
    v = [0.0] * DIM
    for i, s in pairs.items():
        v[i] = s
    return v


# --------------------------------------------------------------- RR 정확성

@pytest.mark.parametrize("gold,want_rank,want_rr", [
    ([3], 1, 1.0),            # 최고점 세그먼트가 gold
    ([2], 2, 0.5),
    ([0], 4, 0.25),           # 최저점 = 후보 끝
])
def test_rr_matches_the_rank_of_the_gold(gold, want_rank, want_rr):
    ranked = [3, 2, 1, 0]
    got = R.rr_of(ranked, gold)
    assert got == {"rank": want_rank, "rr": want_rr}


def test_multi_gold_uses_the_earliest_ranked_gold():
    ranked = [7, 5, 2, 9]
    assert R.rr_of(ranked, [9, 5, 2]) == {"rank": 2, "rr": 0.5}


def test_gold_missing_from_candidates_is_an_error_not_a_silent_zero():
    with pytest.raises(R.RetrieveError, match="gold"):
        R.rr_of([0, 1, 2], [7])


def test_empty_gold_is_an_error():
    with pytest.raises(R.RetrieveError, match="gt_seg_idx"):
        R.rr_of([0, 1, 2], [])


# --------------------------------------------------------------- 동결 GT 게이트

def test_frozen_gt_requires_the_full_count(tmp_path):
    rows = [_q(f"p2_v0_q{i:02d}", "v0", f"질의 {i}", [0]) for i in range(3)]
    p, h = _gt_file(tmp_path, rows)
    with pytest.raises(R.RetrieveError, match="315"):
        R.load_frozen_gt(p, h)


def test_frozen_gt_requires_the_hash(tmp_path):
    rows = [_q(f"p2_v0_q{i:02d}", "v0", f"질의 {i}", [0]) for i in range(3)]
    p, _ = _gt_file(tmp_path, rows)
    with pytest.raises(R.RetrieveError, match="동결"):
        R.load_frozen_gt(p, None, require_count=3)


def test_frozen_gt_refuses_a_changed_file(tmp_path):
    rows = [_q("p2_v0_q01", "v0", "질의", [0])]
    p, h = _gt_file(tmp_path, rows)
    p.write_text(p.read_text(encoding="utf-8").replace("질의", "다른 질의"),
                 encoding="utf-8")
    with pytest.raises(R.RetrieveError, match="sha256"):
        R.load_frozen_gt(p, h, require_count=1)


def test_only_the_p2_split_is_accepted(tmp_path):
    row = _q("p2_v0_q01", "v0", "질의", [0])
    row["split"] = "dev"
    p, h = _gt_file(tmp_path, [row])
    with pytest.raises(R.RetrieveError, match="split"):
        R.load_frozen_gt(p, h, require_count=1)


def test_duplicate_query_id_is_refused(tmp_path):
    rows = [_q("p2_v0_q01", "v0", "a", [0]), _q("p2_v0_q01", "v0", "b", [1])]
    p, h = _gt_file(tmp_path, rows)
    with pytest.raises(R.RetrieveError, match="중복"):
        R.load_frozen_gt(p, h, require_count=2)


@pytest.mark.parametrize("field", ["text", "gt_seg_idx", "video_id", "gt_start"])
def test_missing_required_field_is_refused(tmp_path, field):
    row = _q("p2_v0_q01", "v0", "질의", [0])
    del row[field]
    p, h = _gt_file(tmp_path, [row])
    with pytest.raises(R.RetrieveError, match=field):
        R.load_frozen_gt(p, h, require_count=1)


def test_frozen_gt_accepts_the_declared_count_and_hash(tmp_path):
    rows = [_q(f"p2_v0_q{i:02d}", "v0", f"질의 {i}", [0]) for i in range(4)]
    p, h = _gt_file(tmp_path, rows)
    got = R.load_frozen_gt(p, h, require_count=4)
    assert [r["query_id"] for r in got] == [r["query_id"] for r in rows]


# --------------------------------------------------------------- 후보군 격리

def test_candidates_are_only_the_segments_of_the_query_video(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4)
    _video(work, "v1", 6)
    qs = [_q("p2_v0_q01", "v0", "qa", [1]), _q("p2_v1_q01", "v1", "qb", [5])]
    out = R.run_arm("3b", qs, _cfg(work), {"v0": 4, "v1": 6}, "a" * 64,
                    embed_fn=_scores({"qa": _vec({1: 9.0}), "qb": _vec({5: 9.0})}))
    rows = {r["query_id"]: r for r in out["per_query"]}
    assert rows["p2_v0_q01"]["n_candidates"] == 4
    assert rows["p2_v1_q01"]["n_candidates"] == 6
    assert rows["p2_v0_q01"]["rr"] == 1.0 and rows["p2_v1_q01"]["rr"] == 1.0


def test_candidate_count_must_match_the_frozen_segment_count(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4)
    qs = [_q("p2_v0_q01", "v0", "qa", [1])]
    with pytest.raises(R.RetrieveError, match="사전등록"):
        R.run_arm("3b", qs, _cfg(work), {"v0": 5}, "a" * 64,
                  embed_fn=_scores({"qa": _vec({1: 9.0})}))


def test_gold_outside_the_candidate_range_is_refused(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4)
    qs = [_q("p2_v0_q01", "v0", "qa", [7])]
    with pytest.raises(R.RetrieveError, match="범위"):
        R.run_arm("3b", qs, _cfg(work), {"v0": 4}, "a" * 64,
                  embed_fn=_scores({"qa": _vec({1: 9.0})}))


def test_a_video_without_a_frozen_entry_is_refused(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4)
    qs = [_q("p2_v0_q01", "v0", "qa", [1])]
    with pytest.raises(R.RetrieveError, match="v0"):
        R.run_arm("3b", qs, _cfg(work), {}, "a" * 64,
                  embed_fn=_scores({"qa": _vec({1: 9.0})}))


# --------------------------------------------------------------- 캡션 단독

def test_alpha_is_frozen_at_caption_only():
    assert R.ALPHA == 0.0
    assert R.SPLIT == "p2" and R.N_QUERIES_REQUIRED == 315


def test_it_runs_without_any_subtitle_artifact(tmp_path):
    """fixture에 subtitle 필드도 emb_sub.npy도 없다 — 필요하지 않다는 증거다."""
    work = tmp_path / "work"
    _video(work, "v0", 4, with_subtitle=False)
    assert not (work / "v0" / "emb_sub.npy").exists()
    qs = [_q("p2_v0_q01", "v0", "qa", [2])]
    out = R.run_arm("3b", qs, _cfg(work), {"v0": 4}, "a" * 64,
                    embed_fn=_scores({"qa": _vec({2: 9.0})}))
    assert out["run"]["caption_only"] is True and out["run"]["alpha"] == 0.0
    assert out["per_query"][0]["rr"] == 1.0


def test_nonzero_static_threshold_is_refused(tmp_path):
    """치환이 켜지면 자막 점수가 캡션 채널로 들어와 캡션 단독이 깨진다 [m5 combine_scores]."""
    work = tmp_path / "work"
    _video(work, "v0", 4)
    qs = [_q("p2_v0_q01", "v0", "qa", [1])]
    with pytest.raises(R.RetrieveError, match="static_threshold"):
        R.run_arm("3b", qs, _cfg(work, static_threshold=0.5), {"v0": 4}, "a" * 64,
                  embed_fn=_scores({"qa": _vec({1: 9.0})}))


def test_ranking_ties_break_deterministically(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4)
    qs = [_q("p2_v0_q01", "v0", "qa", [3])]
    kw = dict(embed_fn=_scores({"qa": _vec({0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0})}))
    a = R.run_arm("3b", qs, _cfg(work), {"v0": 4}, "a" * 64, **kw)
    b = R.run_arm("3b", qs, _cfg(work), {"v0": 4}, "a" * 64, **kw)
    assert a["per_query"] == b["per_query"]
    assert a["per_query"][0]["rank"] == 4          # 동점이면 낮은 idx가 앞 (stable)


# --------------------------------------------------------------- arm 혼입 차단

def test_arm_and_config_caption_model_must_agree(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4, arm="3b")
    qs = [_q("p2_v0_q01", "v0", "qa", [1])]
    with pytest.raises(R.RetrieveError, match="caption_model"):
        R.run_arm("4b", qs, _cfg(work, arm="3b"), {"v0": 4}, "a" * 64,
                  embed_fn=_scores({"qa": _vec({1: 9.0})}))


def test_index_caption_provenance_must_match_the_declared_arm(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4, arm="4b")          # 색인은 4b인데 3b로 돌린다
    qs = [_q("p2_v0_q01", "v0", "qa", [1])]
    with pytest.raises(R.RetrieveError, match="model_id"):
        R.run_arm("3b", qs, _cfg(work, arm="3b"), {"v0": 4}, "a" * 64,
                  embed_fn=_scores({"qa": _vec({1: 9.0})}))


def test_stale_embeddings_are_refused(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4)
    meta = json.loads((work / "v0" / "meta.json").read_text(encoding="utf-8"))
    meta["text_hash"] = "f" * 64
    common.atomic_write_json(work / "v0" / "meta.json", meta)
    qs = [_q("p2_v0_q01", "v0", "qa", [1])]
    with pytest.raises(R.RetrieveError, match="text_hash"):
        R.run_arm("3b", qs, _cfg(work), {"v0": 4}, "a" * 64,
                  embed_fn=_scores({"qa": _vec({1: 9.0})}))


def test_embed_model_mismatch_is_refused(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4)
    cfg = _cfg(work)
    cfg["embed_model"] = "other/model"
    qs = [_q("p2_v0_q01", "v0", "qa", [1])]
    with pytest.raises(R.RetrieveError, match="embed_model"):
        R.run_arm("3b", qs, cfg, {"v0": 4}, "a" * 64,
                  embed_fn=_scores({"qa": _vec({1: 9.0})}))


# --------------------------------------------------------------- 산출 스키마

def test_per_query_schema_is_exactly_the_audit_set(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4)
    qs = [_q("p2_v0_q01", "v0", "qa", [1])]
    out = R.run_arm("3b", qs, _cfg(work), {"v0": 4}, "b" * 64,
                    embed_fn=_scores({"qa": _vec({1: 9.0})}))
    assert set(out["per_query"][0]) == {"query_id", "video_id", "rr", "rank",
                                        "n_candidates"}
    assert out["run"]["arm"] == "3b" and out["run"]["gt_sha256"] == "b" * 64
    assert out["run"]["query_count"] == 1


def test_both_arms_produce_the_same_schema(tmp_path):
    work3, work4 = tmp_path / "w3", tmp_path / "w4"
    _video(work3, "v0", 4, arm="3b")
    _video(work4, "v0", 4, arm="4b")
    qs = [_q("p2_v0_q01", "v0", "qa", [1])]
    emb = _scores({"qa": _vec({1: 9.0})})
    a = R.run_arm("3b", qs, _cfg(work3, arm="3b"), {"v0": 4}, "c" * 64, embed_fn=emb)
    b = R.run_arm("4b", qs, _cfg(work4, arm="4b"), {"v0": 4}, "c" * 64, embed_fn=emb)
    assert set(a) == set(b) and set(a["run"]) == set(b["run"])
    assert set(a["per_query"][0]) == set(b["per_query"][0])
    R.assert_same_query_set(a, b)


def test_arm_query_set_mismatch_is_refused(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4)
    emb = _scores({"qa": _vec({1: 9.0}), "qb": _vec({2: 9.0})})
    a = R.run_arm("3b", [_q("p2_v0_q01", "v0", "qa", [1])], _cfg(work),
                  {"v0": 4}, "c" * 64, embed_fn=emb)
    b = R.run_arm("3b", [_q("p2_v0_q02", "v0", "qb", [2])], _cfg(work),
                  {"v0": 4}, "c" * 64, embed_fn=emb)
    with pytest.raises(R.RetrieveError, match="질의 집합"):
        R.assert_same_query_set(a, b)


def test_arm_gt_hash_mismatch_is_refused(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4)
    emb = _scores({"qa": _vec({1: 9.0})})
    qs = [_q("p2_v0_q01", "v0", "qa", [1])]
    a = R.run_arm("3b", qs, _cfg(work), {"v0": 4}, "c" * 64, embed_fn=emb)
    b = R.run_arm("3b", qs, _cfg(work), {"v0": 4}, "d" * 64, embed_fn=emb)
    with pytest.raises(R.RetrieveError, match="gt_sha256"):
        R.assert_same_query_set(a, b)


def test_provenance_records_what_distinguishes_the_arms(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4, arm="3b")
    qs = [_q("p2_v0_q01", "v0", "qa", [1])]
    out = R.run_arm("3b", qs, _cfg(work), {"v0": 4}, "a" * 64,
                    embed_fn=_scores({"qa": _vec({1: 9.0})}))
    prov = out["run"]["provenance"]
    assert prov["caption_model"] == R.ARM_CAPTION_MODEL["3b"]
    assert prov["embed_model"] == EMBED_MODEL
    assert prov["static_threshold"] == 0
    v0 = prov["by_video"]["v0"]
    assert set(v0) == {"n_segments", "text_hash", "work_dir", "model_id",
                       "model_revision", "prompt_sha256"}
    assert v0["model_revision"] == "rev_3b"
    assert v0["work_dir"].endswith("v0")


# --------------------------------------------------------------- 부분 완주 거부

def test_one_failed_query_leaves_no_output_file(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4)
    qs = [_q("p2_v0_q01", "v0", "qa", [1]),
          _q("p2_v0_q02", "v0", "qb", [9])]            # 범위 밖 gold
    out_path = tmp_path / "arm_3b.json"
    with pytest.raises(R.RetrieveError):
        R.run_and_write(out_path, arm="3b", queries=qs, cfg=_cfg(work),
                        frozen_n_segments={"v0": 4}, gt_sha256="a" * 64,
                        embed_fn=_scores({"qa": _vec({1: 9.0}),
                                          "qb": _vec({2: 9.0})}))
    assert not out_path.exists()


def test_a_complete_run_writes_every_query(tmp_path):
    work = tmp_path / "work"
    _video(work, "v0", 4)
    qs = [_q("p2_v0_q01", "v0", "qa", [1]), _q("p2_v0_q02", "v0", "qb", [2])]
    out_path = tmp_path / "arm_3b.json"
    R.run_and_write(out_path, arm="3b", queries=qs, cfg=_cfg(work),
                    frozen_n_segments={"v0": 4}, gt_sha256="a" * 64,
                    embed_fn=_scores({"qa": _vec({1: 9.0}), "qb": _vec({2: 9.0})}))
    got = json.loads(out_path.read_text(encoding="utf-8"))
    assert got["run"]["query_count"] == 2 and len(got["per_query"]) == 2


# --------------------------------------------------------------- 경계 준수

def _imported_names(src: str) -> set:
    """import 노드만 본다 — 안내 문구에 모듈명이 적히는 것은 import가 아니다."""
    out = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


@pytest.mark.parametrize("mod", ["m6_evaluate", "p2_evaluate", "frame_human_kit",
                                 "m5_search"])
def test_it_does_not_import_the_evaluators(mod):
    assert mod not in _imported_names(SRC)


@pytest.mark.parametrize("token", ["bootstrap", "verdict", "판정", "delta",
                                   "alpha_search", "grid_search", "retune",
                                   "adoption", "work_p2", "eval_test"])
def test_it_computes_no_comparison_and_hardcodes_no_arm_path(token):
    assert token.lower() not in CODE.lower()


def test_it_never_reads_the_other_arm(tmp_path):
    """한 번 호출은 arm 하나만 연다 — 두 arm을 같은 호출에서 열 경로가 없다."""
    import inspect
    sig = inspect.signature(R.run_arm)
    assert "arm" in sig.parameters
    assert "base" not in sig.parameters and "candidate" not in sig.parameters


def test_test_split_is_not_reachable():
    assert '"test"' not in CODE and "'test'" not in CODE

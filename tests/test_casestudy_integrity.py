"""케이스 스터디 frame→query→caption→index→rank 연결의 integrity guard.

2026-08-26 CAPTION_TO_RETRIEVAL_INTEGRITY_AUDIT에서 확인한 정합성을 고정한다.
연구 지표를 재계산하지 않는다 — 동일성·개수·매핑만 본다.
CRITICAL로 보는 것은 잘못된 프레임 · stale 캡션/인덱스 · query mismatch ·
seg_idx 어긋남 · 두 arm의 검색 조건 차이다. 그 다섯을 여기서 막는다.

로컬 산출물(runs/)이 없는 환경에서는 skip한다 — clone 직후가 정상이다.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

RUN = ROOT / "runs/casestudy_caption_retrieval/cs_20260825"
PLAN = ROOT / "docs/finalization/caption_retrieval_casestudy_plan.json"
STEP6 = RUN / "step6_retrieval_alpha0.json"
VIDEO = "pland_costco_hosting"
ARMS = ("3b", "4b")
N_SEG = 395


def _need(*paths):
    for p in paths:
        if not p.exists():
            pytest.skip("케이스 스터디 로컬 산출물이 없는 환경이다 (clone 직후 정상)")


@pytest.fixture(scope="module")
def plan():
    _need(PLAN)
    return json.loads(PLAN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def step6():
    _need(STEP6)
    return json.loads(STEP6.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def work():
    dirs = {a: RUN / (a + "_fresh") / "work" / VIDEO for a in ARMS}
    _need(*[d / "segments.json" for d in dirs.values()])
    return dirs


@pytest.fixture(scope="module")
def docs(work):
    return {a: json.loads((work[a] / "segments.json").read_text(encoding="utf-8"))
            for a in ARMS}


# ---------------------------------------------------------------- query identity

def test_plan_has_exactly_5_scenes_and_15_queries(plan):
    assert len(plan["scenes"]) == 5
    qs = [q for sc in plan["scenes"] for q in sc["queries"]]
    assert len(qs) == 15
    assert len({q["query_id"] for q in qs}) == 15


def test_frozen_query_hash_reproduces(plan):
    """동결 해시 정의를 재현한다 — 질의 문구가 바뀌면 여기서 깨진다."""
    qs = [q for sc in plan["scenes"] for q in sc["queries"]]
    dump = json.dumps(qs, ensure_ascii=False, sort_keys=True)
    assert hashlib.sha256(dump.encode()).hexdigest() == plan["frozen_queries_sha256"]


def test_frozen_scene_hash_reproduces(plan):
    keys = ("scene_id", "segment_idx", "start", "end")
    obj = [{k: sc[k] for k in keys} for sc in plan["scenes"]]
    dump = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    assert hashlib.sha256(dump.encode()).hexdigest() == plan["frozen_scenes_sha256"]


def test_retrieval_artifact_query_text_matches_plan(step6, plan):
    qs = [q for sc in plan["scenes"] for q in sc["queries"]]
    assert [r["query"] for r in step6["results"]] == [q["text"] for q in qs]
    assert [r["query_id"] for r in step6["results"]] == [q["query_id"] for q in qs]


def test_retrieval_artifact_target_segment_matches_plan(step6, plan):
    want = [sc["segment_idx"] for sc in plan["scenes"] for _ in sc["queries"]]
    assert [r["target_segment"] for r in step6["results"]] == want


# ---------------------------------------------------------------- retrieval config

def test_retrieval_is_caption_only_without_sweep(step6):
    assert step6["alpha"] == 0.0
    assert step6["alpha_sweep"] is False
    assert step6["n_segments"] == N_SEG
    assert step6["video_id"] == VIDEO


def test_every_arm_ranked_the_full_pool(step6):
    seen = {r["arms"][a]["n_ranked"] for r in step6["results"] for a in ARMS}
    assert seen == {N_SEG}


def test_arm_configs_differ_only_in_model_and_paths():
    """검색 조건이 arm 간에 갈리면 비교가 성립하지 않는다 — CRITICAL 방어."""
    paths = [RUN / ("config_%s.yaml" % a) for a in ARMS]
    _need(*paths)
    cfg = {a: yaml.safe_load(p.read_text(encoding="utf-8"))
           for a, p in zip(ARMS, paths)}
    keys = set(cfg["3b"]) | set(cfg["4b"])
    diff = {k for k in keys if cfg["3b"].get(k) != cfg["4b"].get(k)}
    assert diff == {"caption_model", "paths"}, diff


# ---------------------------------------------------------------- caption / index

def test_each_arm_has_395_nonempty_captions_with_contiguous_idx(docs):
    for a in ARMS:
        segs = docs[a]["segments"]
        assert docs[a]["n_segments"] == len(segs) == N_SEG
        assert [s["idx"] for s in segs] == list(range(N_SEG))
        assert all(s["start"] == i * 5 for i, s in enumerate(segs))
        assert all(s["caption"].strip() for s in segs)


def test_index_is_not_stale_relative_to_captions(docs, work):
    """text_hash 불일치 = 캡션 갱신 후 재임베딩 누락. stale 인덱스 방어."""
    import common
    for a in ARMS:
        meta = json.loads((work[a] / "meta.json").read_text(encoding="utf-8"))
        assert meta["text_hash"] == common.index_text_hash(docs[a])
        assert meta["embed_model"] == "nlpai-lab/KURE-v1"
        assert meta["n_segments"] == N_SEG
        assert meta["dim"] == 1024


def test_embedding_matrices_have_expected_shape(work):
    for a in ARMS:
        for name in ("emb_cap.npy", "emb_sub.npy"):
            emb = np.load(work[a] / name)
            assert emb.shape == (N_SEG, 1024), (a, name, emb.shape)


def test_row_order_corresponds_to_segment_order(docs, work):
    """행 N ↔ seg_idx N 을 신규 임베딩 없이 검증한다.

    두 arm의 subtitle은 같고 caption은 전건 다르다. 따라서 같은 모델로 만든
    emb_sub는 행 단위로 비트동일해야 하고, emb_cap은 전건 달라야 한다.
    행 순서가 어긋나면 이 대응이 깨진다.
    """
    subs = {a: [s["subtitle"] for s in docs[a]["segments"]] for a in ARMS}
    assert subs["3b"] == subs["4b"]
    es = {a: np.load(work[a] / "emb_sub.npy") for a in ARMS}
    ec = {a: np.load(work[a] / "emb_cap.npy") for a in ARMS}
    caps = {a: [s["caption"] for s in docs[a]["segments"]] for a in ARMS}

    assert np.array_equal(es["3b"], es["4b"]), "같은 자막인데 emb_sub가 다르다"
    cap_same = np.array([caps["3b"][i] == caps["4b"][i] for i in range(N_SEG)])
    emb_same = np.all(ec["3b"] == ec["4b"], axis=1)
    assert np.array_equal(cap_same, emb_same), "캡션 동일성과 emb_cap 동일성이 어긋난다"


# ---------------------------------------------------------------- generation input

def test_both_arms_saw_byte_identical_frames(docs):
    """모델 외 입력이 같아야 비교가 성립한다 — 잘못된 프레임 방어."""
    fm = {a: (docs[a].get("caption_provenance") or {}).get("frame_manifest_sha256")
          for a in ARMS}
    assert fm["3b"] and fm["3b"] == fm["4b"], fm


def test_both_arms_used_the_same_prompt(docs):
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    want = hashlib.sha256(cfg["caption_prompt"].encode("utf-8")).hexdigest()
    for a in ARMS:
        pr = docs[a]["caption_provenance"]
        assert pr["prompt_sha256"] == want, a


def test_generation_decode_settings_identical_across_arms(docs):
    pr = {a: docs[a]["caption_provenance"] for a in ARMS}
    for k in ("config_vlm_4bit", "config_vlm_max_new_tokens", "config_vlm_max_pixels",
              "config_vlm_rep_penalty", "bnb_quant_type", "bnb_compute_dtype",
              "bnb_double_quant", "attn_implementation", "torch", "transformers",
              "gpu", "python"):
        assert pr["3b"].get(k) == pr["4b"].get(k), k


def test_discussion_frames_match_caption_input_frames(work):
    """논의·발표용 프레임 사본이 실제 캡션 입력 프레임과 같은 바이트여야 한다."""
    fd = RUN / "frames_for_discussion"
    if not fd.is_dir():
        pytest.skip("프레임 로컬 사본이 없는 환경이다 (clone 직후 정상)")
    h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    checked = 0
    for f in sorted(fd.glob("*.jpg")):
        m = re.match(r"seg(\d{4})_(\d+)s\.jpg", f.name)
        assert m, "프레임 파일명 규칙 위반: %s" % f.name
        idx = int(m.group(1))
        want = h(f)
        for a in ARMS:
            got = h(work[a] / "frames" / ("seg_%04d.jpg" % idx))
            assert got == want, (f.name, a)
        checked += 1
    assert checked == 27, "논의용 프레임 %d장 (27장이어야 한다)" % checked


# ---------------------------------------------------------------- deck ↔ artifact

def test_deck_ranks_match_frozen_retrieval_artifact(step6):
    """덱의 15질의 전체표 순위가 동결 검색 산출물과 일치해야 한다."""
    builder = ROOT / "docs/presentation/build_casestudy_deck.js"
    if not builder.is_file():
        pytest.skip("덱 생성기가 없는 환경이다")
    src = builder.read_text(encoding="utf-8")
    rows = re.findall(r'\["(?:\d\d|)",\s*"([^"]+)",\s*(\d+),\s*(\d+),\s*"\w*"\]', src)
    assert len(rows) == 15, "덱 전체표 행이 15개가 아니다: %d" % len(rows)
    want = {r["query"]: (r["arms"]["3b"]["target_rank"], r["arms"]["4b"]["target_rank"])
            for r in step6["results"]}
    for text, r3, r4 in rows:
        assert text in want, "덱 질의가 동결본에 없다: %s" % text
        assert want[text] == (int(r3), int(r4)), (text, want[text], (r3, r4))


def test_deck_top1_hit_count_matches_artifact(step6):
    """덱이 말하는 '1위 적중 2건씩'이 산출물과 맞아야 한다."""
    hit = {a: sum(1 for r in step6["results"]
                  if r["arms"][a]["top1_segment"] == r["target_segment"])
           for a in ARMS}
    assert hit == step6["illustrative_top1_hit_count"], hit
    assert hit == {"3b": 2, "4b": 2}, hit

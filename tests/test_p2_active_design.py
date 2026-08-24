"""P2 활성 설계 로더 — **표본 규모의 단일 출처를 매번 재검산한다.**

`315`를 여러 모듈에 박아 두면 amendment가 한 군데만 반영되고 나머지가 조용히
거짓말을 한다. 그래서 읽을 때마다 mask 해시·영상당 행 수·quota·유형 존재·
동결 배정표 부분집합을 전부 다시 확인한다.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_active_design as A                                       # noqa: E402
import p2_reduced_design as RD                                     # noqa: E402

KO = RD.TYPES


def _alloc(n_videos=35, per=3) -> list:
    rows = []
    for i in range(n_videos):
        vid = f"v{i:02d}"
        n = 0
        for t in KO:
            for _ in range(per):
                n += 1
                rows.append({"query_id": f"p2_{vid}_q{n:02d}", "video_id": vid,
                             "query_type": t})
    return rows


def _pair(tmp_path, allocation, total=175, **override):
    """mask + 활성 설계 파일 한 벌. mask는 실제 선택기로 만든다."""
    mask = RD.keep_mask(total, allocation=allocation)
    mp = tmp_path / "mask.json"
    mp.write_text(json.dumps(mask, ensure_ascii=False), encoding="utf-8")
    doc = {"design": mask["design"], "approved_at": "2026-08-24",
           "total_queries": mask["total"],
           "queries_per_video": mask["queries_per_video"],
           "n_videos": mask["n_videos"], "quota": mask["quota"],
           "frozen_allocation_total": len(allocation), "seed": mask["seed"],
           "keep_mask": str(mp), "keep_mask_sha256":
               hashlib.sha256(mp.read_bytes()).hexdigest(),
           "fixed_n": True, "no_outcome_based_top_up": True}
    doc.update(override)
    ap = tmp_path / "active.json"
    ap.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return ap, mp


# ------------------------------------------------------------- 정상 경로

def test_it_loads_and_returns_the_kept_ids(tmp_path):
    alloc = _alloc()
    ap, _ = _pair(tmp_path, alloc)
    got = A.load(ap, allocation=alloc)
    assert got["total_queries"] == 175
    assert len(got["kept_query_ids"]) == 175
    assert len(got["dropped_query_ids"]) == 140


def test_the_real_artifact_validates():
    got = A.load()
    assert got["design"] == "p2_175"
    assert got["total_queries"] == 175 and got["queries_per_video"] == 5
    assert got["quota"] == {"복합형": 62, "자막형": 44, "장면형": 69}
    assert len(got["kept_query_ids"]) == 175
    assert A.total_queries() == 175


def test_the_real_artifact_keeps_35_clusters_and_all_three_types():
    got = A.load()
    alloc = {r["query_id"]: r for r in RD.frozen_allocation()}
    per_video, types = {}, {}
    for q in got["kept_query_ids"]:
        v = alloc[q]["video_id"]
        per_video[v] = per_video.get(v, 0) + 1
        types.setdefault(v, set()).add(alloc[q]["query_type"])
    assert len(per_video) == 35 and set(per_video.values()) == {5}
    assert all(t == set(KO) for t in types.values())


# ------------------------------------------------------------- fail-closed

def test_a_tampered_mask_is_refused(tmp_path):
    alloc = _alloc()
    ap, mp = _pair(tmp_path, alloc)
    doc = json.loads(mp.read_text(encoding="utf-8"))
    doc["kept_query_ids"] = doc["kept_query_ids"][:-1]
    mp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(A.ActiveDesignError, match="sha256"):
        A.load(ap, allocation=alloc)


def test_a_missing_mask_is_refused(tmp_path):
    alloc = _alloc()
    ap, mp = _pair(tmp_path, alloc)
    mp.unlink()
    with pytest.raises(A.ActiveDesignError, match="mask"):
        A.load(ap, allocation=alloc)


def test_a_total_that_disagrees_with_the_mask_is_refused(tmp_path):
    alloc = _alloc()
    ap, _ = _pair(tmp_path, alloc, total_queries=200)
    with pytest.raises(A.ActiveDesignError, match="total_queries"):
        A.load(ap, allocation=alloc)


def test_a_quota_that_disagrees_with_the_mask_is_refused(tmp_path):
    alloc = _alloc()
    ap, _ = _pair(tmp_path, alloc, quota={"복합형": 60, "자막형": 46, "장면형": 69})
    with pytest.raises(A.ActiveDesignError, match="quota"):
        A.load(ap, allocation=alloc)


@pytest.mark.parametrize("flag", ["fixed_n", "no_outcome_based_top_up"])
def test_dropping_the_no_top_up_flag_is_refused(tmp_path, flag):
    alloc = _alloc()
    ap, _ = _pair(tmp_path, alloc, **{flag: False})
    with pytest.raises(A.ActiveDesignError, match=flag):
        A.load(ap, allocation=alloc)


def test_a_query_id_outside_the_frozen_allocation_is_refused(tmp_path):
    alloc = _alloc()
    ap, mp = _pair(tmp_path, alloc)
    doc = json.loads(mp.read_text(encoding="utf-8"))
    doc["kept_query_ids"][0] = "p2_zz_q99"
    mp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    ad = json.loads(ap.read_text(encoding="utf-8"))
    ad["keep_mask_sha256"] = hashlib.sha256(mp.read_bytes()).hexdigest()
    ap.write_text(json.dumps(ad, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(A.ActiveDesignError, match="새 질의"):
        A.load(ap, allocation=alloc)


def test_an_unbalanced_per_video_count_is_refused(tmp_path):
    alloc = _alloc()
    ap, mp = _pair(tmp_path, alloc)
    doc = json.loads(mp.read_text(encoding="utf-8"))
    kept = doc["kept_query_ids"]
    # v00의 유지분 하나를 v01의 미유지분으로 갈아 끼운다 — 총 수는 그대로다
    drop_of_v01 = next(q for q in doc["dropped_query_ids"] if "_v01_" in q)
    keep_of_v00 = next(q for q in kept if "_v00_" in q)
    doc["kept_query_ids"] = [drop_of_v01 if q == keep_of_v00 else q for q in kept]
    mp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    ad = json.loads(ap.read_text(encoding="utf-8"))
    ad["keep_mask_sha256"] = hashlib.sha256(mp.read_bytes()).hexdigest()
    ap.write_text(json.dumps(ad, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(A.ActiveDesignError, match="영상당|유형|quota"):
        A.load(ap, allocation=alloc)


def test_a_frozen_allocation_of_the_wrong_size_is_refused(tmp_path):
    alloc = _alloc()
    ap, _ = _pair(tmp_path, alloc)
    with pytest.raises(A.ActiveDesignError, match="동결 배정표"):
        A.load(ap, allocation=alloc[:-9])


def test_a_missing_active_file_is_refused(tmp_path):
    with pytest.raises(A.ActiveDesignError, match="활성 설계"):
        A.load(tmp_path / "nope.json")

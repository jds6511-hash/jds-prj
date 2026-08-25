"""external E2E — 새 한국어 영상이 배포 경로를 끝까지 통과하는지 확인한다.

**연구 평가가 아니다.** MRR·Recall·nDCG·bootstrap·유의성·모델 대조를 만들지 않는다.
E2E 영상은 연구 데이터로 승격되지 않으며, 그것을 manifest 검증이 강제한다.

```
HARD FUNCTIONAL   통과 못 하면 E2E FAIL — ingest·stt·caption·embedding·index·search·playback
SEMANTIC SMOKE    기능은 정상인데 검색 내용이 기대와 다른 경우. descriptive observation만
```

네트워크·다운로드는 이 모듈의 검증 대상이 아니다. 취득은 저장소가 이미 쓰는 경로
(`scripts/p2_staging_verify.py`의 `yt-dlp`)를 그대로 쓰고, **접근제한·인증 우회를
만들지 않는다.**
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

MANIFEST = ROOT / "planning" / "e2e_external_manifest.json"
RUNS_DIR = ROOT / "runs" / "e2e_external"          # 연구 run 디렉터리와 분리
SCHEMA_VERSIONS = (1,)
ID_PREFIX = "e2e_"

# 배포 identity. 이 값과 다른 조합으로 E2E를 돌리지 않는다.
DEPLOYMENT_IDENTITY = {
    "caption_model": "Qwen/Qwen2.5-VL-3B-Instruct",
    "vlm_4bit": True,
    "embed_model": "nlpai-lab/KURE-v1",
    "seg_len_sec": 5,
    "static_threshold": 0,
    "alpha": 0.5,
}
EMBED_DIM = 1024

# manifest video의 허용 키. 모르는 키는 통과시키지 않는다 — 연구용 필드가
# 슬쩍 들어오는 경로를 막는다.
VIDEO_KEYS = {
    "e2e_id", "phase", "class", "role", "role_correction", "source_url",
    "source_video_id", "title", "uploader", "upload_date", "duration_sec",
    "availability", "probed_at", "local_file", "local_file_sha256",
    "audio_present", "status", "note", "e2e_only",
    "eligible_for_research_evaluation", "eligible_for_p2", "eligible_for_p3",
    "eligible_for_test", "eligible_for_public_demo",
}
VIDEO_REQUIRED = {
    "e2e_id", "phase", "class", "role", "source_url", "source_video_id",
    "duration_sec", "availability", "status", "e2e_only",
    "eligible_for_research_evaluation", "eligible_for_p2", "eligible_for_p3",
    "eligible_for_test", "eligible_for_public_demo",
}
MUST_BE_FALSE = ("eligible_for_research_evaluation", "eligible_for_p2",
                 "eligible_for_p3", "eligible_for_test",
                 "eligible_for_public_demo")

# 연구 split 영상 이름. E2E가 이 이름을 쓰면 나중에 loader가 섞어 읽는다.
RESEARCH_VIDEO_IDS = frozenset({
    "gemini_promo", "itsub_viral_gadgets", "panibottle_vietnam1",
    "yunnamnopo_tongyeong",                                   # test
    "_10_000_Every_Day_You_Survive_In_The_Wilderness",
    "gwaktube_soviet_apartment", "kheritage_grave_excavation",  # dev
})

FUNCTIONAL_STAGES = ("ingest", "stt", "caption", "embedding", "index",
                     "search", "playback")
SEMANTIC_STATUSES = ("PASS", "OBSERVED", "REVIEW")


class E2EError(RuntimeError):
    pass


# ---- manifest ---------------------------------------------------------------

def load_manifest(path=MANIFEST) -> dict:
    p = Path(path)
    if not p.is_file():
        raise E2EError(f"manifest가 없다: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def validate(m: dict) -> dict:
    if m.get("schema_version") not in SCHEMA_VERSIONS:
        raise E2EError(f"지원하지 않는 schema_version={m.get('schema_version')} "
                       f"(지원 {SCHEMA_VERSIONS})")
    if m.get("research_metrics_generated") is not False:
        raise E2EError("research_metrics_generated는 false여야 한다 — E2E는 "
                       "연구 지표를 만들지 않는다")
    acq = m.get("acquisition") or {}
    if acq.get("bypass_used") is not False:
        raise E2EError("acquisition.bypass_used는 false여야 한다 — 접근제한 "
                       "우회를 쓰지 않는다")

    want = m.get("deployment_identity") or {}
    for k, v in DEPLOYMENT_IDENTITY.items():
        if want.get(k) != v:
            raise E2EError(f"deployment_identity의 {k}={want.get(k)!r}가 배포 "
                           f"구성 {v!r}과 다르다 — E2E는 배포 구성으로만 돈다")

    seen_id, seen_url = set(), set()
    for v in m.get("videos") or []:
        unknown = sorted(set(v) - VIDEO_KEYS)
        if unknown:
            raise E2EError(f"{v.get('e2e_id')}: 허용되지 않은 필드 {unknown} — "
                           f"allowlist 밖의 키를 통과시키지 않는다")
        missing = sorted(VIDEO_REQUIRED - set(v))
        if missing:
            raise E2EError(f"{v.get('e2e_id')}: 필수 필드 누락 {missing}")

        vid = v["e2e_id"]
        if not vid.startswith(ID_PREFIX):
            raise E2EError(f"{vid}: e2e_id는 {ID_PREFIX!r}로 시작해야 한다 — "
                           f"연구 영상 이름과 섞이지 않게 한다")
        if vid in RESEARCH_VIDEO_IDS:
            raise E2EError(f"{vid}: 연구 split(dev·test) 영상 이름이다 — "
                           f"E2E로 끌어오지 않는다")
        if v["e2e_only"] is not True:
            raise E2EError(f"{vid}: e2e_only는 true여야 한다")
        for f in MUST_BE_FALSE:
            if v[f] is not False:
                raise E2EError(f"{vid}: {f}는 false여야 한다 — E2E 데이터는 "
                               f"연구·발표에 승격되지 않는다")
        if not isinstance(v["duration_sec"], int) or v["duration_sec"] <= 0:
            raise E2EError(f"{vid}: duration_sec가 양의 정수가 아니다")
        if vid in seen_id:
            raise E2EError(f"{vid}: e2e_id 중복")
        if v["source_url"] in seen_url:
            raise E2EError(f"{vid}: source_url 중복 — {v['source_url']}")
        seen_id.add(vid)
        seen_url.add(v["source_url"])

    order = m.get("phase_order") or []
    unknown = [x for x in order if x not in seen_id]
    if unknown:
        raise E2EError(f"phase_order에 manifest에 없는 항목: {unknown}")

    return {"ok": True, "n_videos": len(m.get("videos") or []),
            "suite_id": m.get("e2e_suite_id"), "phase_order": order}


def video_of(m: dict, e2e_id: str) -> dict:
    for v in m.get("videos") or []:
        if v["e2e_id"] == e2e_id:
            return v
    raise E2EError(f"manifest에 없는 e2e_id: {e2e_id}")


# ---- 로컬 파일 --------------------------------------------------------------

def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def local_file_status(v: dict) -> dict:
    """로컬 영상 준비 상태. 없으면 예외가 아니라 상태로 보고한다."""
    lf = v.get("local_file")
    if not lf:
        return {"ok": False, "reason": "local_file이 manifest에 없다 — 영상을 "
                                       "먼저 준비해야 한다", "path": None}
    p = Path(lf)
    if not p.is_file():
        return {"ok": False, "reason": f"파일이 없다: {p}", "path": str(p)}
    digest = sha256_file(p)
    want = v.get("local_file_sha256")
    if want and want != digest:
        return {"ok": False, "path": str(p), "sha256": digest,
                "reason": f"sha256 불일치 — manifest {want[:16]}… vs 실제 "
                          f"{digest[:16]}…"}
    return {"ok": True, "reason": None, "path": str(p), "sha256": digest,
            "size_bytes": p.stat().st_size}


# ---- HARD FUNCTIONAL 검사 ----------------------------------------------------

def check_segment_bounds(segments: list, duration_sec: float,
                         seg_len: int) -> dict:
    if not segments:
        return {"ok": False, "reason": "구간이 0개다", "n_segments": 0}
    for s in segments:
        if s["start"] < 0 or s["end"] <= s["start"]:
            return {"ok": False, "reason": f"구간 {s['idx']} 시각이 뒤집혔다",
                    "n_segments": len(segments)}
        # M1은 마지막 구간을 duration에서 자른다 — 넘어가면 분할이 잘못된 것이다
        if s["end"] > duration_sec + 1e-6:
            return {"ok": False,
                    "reason": f"구간 {s['idx']} end={s['end']}가 duration="
                              f"{duration_sec}를 넘는다",
                    "n_segments": len(segments)}
    return {"ok": True, "reason": None, "n_segments": len(segments)}


def check_embedding(rows: int, dim: int, n_segments: int) -> dict:
    if dim != EMBED_DIM:
        return {"ok": False, "reason": f"임베딩 차원 {dim} != {EMBED_DIM}"}
    if rows != n_segments:
        return {"ok": False,
                "reason": f"임베딩 행 수 {rows} != 구간 수 {n_segments}"}
    return {"ok": True, "reason": None}


def check_results(results: list, duration_sec: float, n_segments: int) -> dict:
    for i, r in enumerate(results, 1):
        if r.get("rank") != i:
            return {"ok": False, "reason": f"rank가 연속이 아니다: {r.get('rank')} "
                                           f"(기대 {i})"}
        if not (0 <= r["idx"] < n_segments):
            return {"ok": False, "reason": f"구간 인덱스 범위 밖: {r['idx']}"}
        if not math.isfinite(r["score"]):
            return {"ok": False, "reason": f"점수가 유한하지 않다: {r['score']}"}
        if not (0 <= r["start"] < r["end"] <= duration_sec + 1e-6):
            return {"ok": False, "reason": f"구간 시각이 영상 범위 밖: "
                                           f"{r['start']}~{r['end']}"}
        if not (0 <= r["seek_to"] <= duration_sec):
            return {"ok": False, "reason": f"seek_to가 범위 밖: {r['seek_to']}"}
        if r["seek_to"] != r["start"]:
            return {"ok": False, "reason": f"seek_to({r['seek_to']})가 구간 "
                                           f"시작({r['start']})과 다르다"}
        if "subtitle" not in r or "caption" not in r:
            return {"ok": False, "reason": f"rank {i}에 근거 필드가 없다"}
    return {"ok": True, "reason": None, "n_results": len(results)}


def functional_verdict(stages: dict) -> dict:
    failed = [s for s in FUNCTIONAL_STAGES if stages.get(s) is not True]
    return {"verdict": "PASS" if not failed else "FAIL",
            "stages": {s: bool(stages.get(s)) for s in FUNCTIONAL_STAGES},
            "failed_stages": failed}


# ---- SEMANTIC SMOKE (descriptive) -------------------------------------------

def semantic_observation(query: str, anchor, results: list,
                         window_sec: int = 15) -> dict:
    """기능 판정과 분리된 관찰 기록. **연구 지표로 승격하지 않는다.**

    anchor가 있으면(LEVEL 1) top-k 안에 그 시각대가 들어왔는지 기술한다.
    없으면(LEVEL 2) 질의가 완료되고 결과·근거가 나왔는지만 본다.
    정답률·정확도를 계산하지 않는다.
    """
    if anchor is None:
        return {"query": query, "level": 2,
                "status": "OBSERVED" if results else "REVIEW",
                "anchor": None, "anchor_in_topk": None, "anchor_rank": None,
                "n_results": len(results),
                "is_research_metric": False,
                "note": ("정확한 timestamp GT가 없다 — 결과가 나왔는지와 사람이 "
                         "확인 가능한지까지만 본다")}
    lo, hi = float(anchor[0]) - window_sec, float(anchor[1]) + window_sec
    hit = next((r for r in results if r["start"] < hi and r["end"] > lo), None)
    return {"query": query, "level": 1,
            "status": "PASS" if hit else "REVIEW",
            "anchor": [anchor[0], anchor[1]], "window_sec": window_sec,
            "anchor_in_topk": hit is not None,
            "anchor_rank": hit["rank"] if hit else None,
            "n_results": len(results),
            "is_research_metric": False,
            "note": ("외부 공개 전사에서 얻은 시각 anchor다. 검색 결과를 보고 "
                     "고르지 않았다. 관찰이고 정확도가 아니다")}


# ---- CLI --------------------------------------------------------------------

def _print_manifest(m: dict, v: dict) -> None:
    st = local_file_status(v)
    print(f"  {v['e2e_id']:20s} phase {v['phase']} · {v['class']:14s} "
          f"{v['duration_sec']:5d}s · {v['availability']}")
    print(f"    role   {v['role']}")
    print(f"    local  {'준비됨 ' + st['sha256'][:16] + '…' if st['ok'] else st['reason']}")


def main():
    ap = argparse.ArgumentParser(
        description="external E2E — manifest 검증과 단계 점검 (연구 평가 아님)")
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument("--video-id")
    ap.add_argument("--suite", choices=["core"])
    ap.add_argument("--check-only", action="store_true",
                    help="manifest·로컬 파일 상태만 확인한다")
    a = ap.parse_args()

    try:
        m = load_manifest(a.manifest)
        info = validate(m)
    except E2EError as e:
        print(f"manifest 검증 실패 — {e}", file=sys.stderr)
        return 1

    print(f"manifest OK — suite {info['suite_id']} · 영상 {info['n_videos']}편")
    print(f"실행 순서: {' → '.join(info['phase_order'])}")
    targets = ([video_of(m, a.video_id)] if a.video_id else
               [video_of(m, x) for x in info["phase_order"]])
    for v in targets:
        _print_manifest(m, v)
    for e in m.get("excluded") or []:
        print(f"  {e['e2e_id']:20s} EXCLUDED — {e['reason']}")

    ready = [v for v in targets if local_file_status(v)["ok"]]
    print(f"\n로컬 파일 준비됨 {len(ready)}/{len(targets)}")
    if not ready:
        print("영상을 준비한 뒤 manifest의 local_file·local_file_sha256을 채워라. "
              "raw video는 git에 넣지 않는다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

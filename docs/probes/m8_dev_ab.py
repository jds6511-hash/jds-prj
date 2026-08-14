"""[M8 리포트 개선 A/B — dev 3편 전용, GPU 필요, test 미접촉]

**무엇을 가르는가.** 사전등록(docs/M8_개선_사전등록_2026-08-14.md) §2는 변경을 두
성격으로 나눠 적었다 — **결함 수정**(1·2번)과 **품질 개선**(3·4번). 한 번에 켜서
재보면 커버가 올라갔을 때 그게 결함이 고쳐진 덕인지 요약이 좋아진 덕인지 못 가린다.
그래서 arm을 셋으로 쪼갠다.

| arm | 잔여 CJK 제거 | 청크 커버 미달 재생성 | 요약 예산 | 뜻 |
|---|---|---|---|---|
| `prefix` | off | off | off | 사전등록 이전 동작 = 기준선 |
| `fix` | on | on | off | 결함 수정만 |
| `fix_budget` | on | on | on | 결함 수정 + 요약 예산 |

`prefix`는 src를 되돌리지 않고 **이 스크립트 안에서만** 끈다
(`common.strip_residual_cjk`를 항등함수로, `MIN_CHUNK_COVERAGE`를 0으로). 프로덕션
코드를 실험용으로 분기시키지 않기 위해서다.

**왜 dev에서만 하나.** 저장된 리포트 4편 중 3편이 test다(사전등록 §4 정정). 그걸
보며 프롬프트를 고르면 test 산출물에 맞춰 튜닝하는 것이 된다. 판정은 dev 3편에서만
한다. test 리포트 재생성은 8회차 재평가에 한 번만 포함한다.

**판정.** 관문 G1~G3와 주 지표는 사전등록 §3 그대로다. **여기서 임계를 고치지
않는다** — 못 넘으면 못 넘었다고 적는다.

**한계.** dev 3편은 표본이 아주 작다. arm 간 차이에 CI를 붙이지 않는다(영상 3개로는
의미 있는 구간이 안 나온다). 관문 통과/미통과와 실측치만 적는다.

재현: python docs/probes/m8_dev_ab.py --config config_server.yaml
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common                                             # noqa: E402
import m8_report as m8                                    # noqa: E402
from llm import make_llm                                  # noqa: E402
from m8_report_quality import truncation, summariness     # noqa: E402

OUT = Path(__file__).resolve().parent / "_scratch"
REPDIR = OUT / "m8_ab_reports"

# ── 사전 등록 임계 (M8_개선_사전등록_2026-08-14.md §3, 결과 보기 전 확정) ──────
GATES = {
    "G1_coverage_min": 0.90,
    "G2_no_truncation": True,          # truncated_tail 없음 AND truncation.stage != "reduce"
    "G3_cite_dump_max": 0,
    "G3_chars_per_cite_min": 15.0,
}
PRIMARY_MAX = 0.35                     # sentences_per_covered_segment

ARMS = {
    # (잔여 CJK 제거, 청크 커버 재생성, 요약 예산)
    "prefix":     (False, False, False),
    "fix":        (True,  True,  False),
    "fix_budget": (True,  True,  True),
}

_REAL_STRIP = common.strip_residual_cjk
_REAL_MIN_COV = m8.MIN_CHUNK_COVERAGE


def apply_arm(strip_cjk: bool, chunk_retry: bool) -> None:
    """arm 설정을 모듈 전역에 반영한다. 이 프로세스 안에서만 유효하다."""
    common.strip_residual_cjk = _REAL_STRIP if strip_cjk else (lambda s: s)
    m8.common.strip_residual_cjk = common.strip_residual_cjk
    m8.MIN_CHUNK_COVERAGE = _REAL_MIN_COV if chunk_retry else 0.0


def judge(t: dict, s: dict) -> dict:
    """관문·주 지표 판정. 임계는 GATES/PRIMARY_MAX 그대로 쓴다."""
    cov = s.get("coverage_of_video")
    g1 = cov is not None and cov >= GATES["G1_coverage_min"]
    g2 = (not t.get("truncated_tail")) and t.get("stage") != "reduce"
    g3 = (s.get("cite_dump_sentences") == GATES["G3_cite_dump_max"]
          and (s.get("chars_per_cite_mean") or 0) >= GATES["G3_chars_per_cite_min"])
    spc = s.get("sentences_per_covered_segment")
    primary = spc is not None and spc <= PRIMARY_MAX
    return {"G1_coverage": g1, "G2_truncation": g2, "G3_cite_dump": g3,
            "gates_all": g1 and g2 and g3,
            "primary_ok": primary, "primary_value": spc}


def load_queries() -> list[dict]:
    return [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--out", default="m8_dev_ab.json")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    REPDIR.mkdir(exist_ok=True)
    cfg = common.load_config(args.config)
    qs = load_queries()
    vids = sorted({q["video_id"] for q in qs if q["split"] == "dev"})
    assert vids, "dev 영상이 없다"
    print(f"dev {len(vids)}편: {vids}")

    # test 영상이 섞이면 즉시 멈춘다 — 이 프로브의 존재 이유가 무너진다
    test_vids = {q["video_id"] for q in qs if q["split"] == "test"}
    assert not (set(vids) & test_vids), "dev 목록에 test 영상이 섞였다 — 중단"

    llm = make_llm(cfg["report_model"],
                   max_new_tokens=cfg.get("report_max_new_tokens", 2048),
                   load_4bit=cfg.get("llm_4bit", False))

    # 코드 판을 결과에 박는다. arm 이름이 같아도 프롬프트가 바뀌면 다른 측정이다 —
    # 2026-08-14 1회차 뒤 규칙 7 문구와 재생성 프롬프트를 고쳤고, 그러면 `prefix`조차
    # 1회차와 다른 것을 재는 게 된다. 나중에 두 파일을 나란히 놓고 헷갈리지 않으려면
    # 여기 남겨야 한다.
    try:
        import subprocess
        rev = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        rev = None
    res = {"note": __doc__.strip().splitlines()[0],
           "code_rev": rev or "unknown",
           "prereg": "docs/M8_개선_사전등록_2026-08-14.md §3 (임계 고정)",
           "gates": GATES, "primary_max": PRIMARY_MAX,
           "model": cfg["report_model"], "llm_4bit": cfg.get("llm_4bit", False),
           "map_chunk_size": cfg["map_chunk_size"],
           "map_chunk_overlap": cfg["map_chunk_overlap"],
           "dev_videos": vids, "arms": {}}

    for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
        strip_cjk, chunk_retry, budget = ARMS[arm]
        apply_arm(strip_cjk, chunk_retry)
        print(f"\n=== arm {arm} (cjk_strip={strip_cjk} chunk_retry={chunk_retry} "
              f"budget={budget}) ===")
        per_video, t_arm = {}, time.time()
        for v in vids:
            wdir = common.work_dir(cfg, v)
            doc = common.load_segments(wdir / "segments.json",
                                       require=["subtitle", "caption"],
                                       seg_len=cfg["seg_len_sec"])
            t0 = time.time()
            rep = m8.generate_report(doc["segments"], llm,
                                     cfg["map_chunk_size"], cfg["map_chunk_overlap"],
                                     summary_budget=budget)
            mins = (time.time() - t0) / 60
            # 산출물 전량 저장 — 나중에 다른 각도로 보려고 GPU를 다시 쓰지 않는다
            (REPDIR / f"{arm}__{v}.json").write_text(
                json.dumps({"video_id": v, "arm": arm, "n_segments": doc["n_segments"],
                            **rep}, ensure_ascii=False, indent=2), encoding="utf-8")
            t = truncation(rep)
            s = summariness(rep, doc["n_segments"])
            per_video[v] = {"minutes": round(mins, 1), "truncation": t,
                            "summariness": s, "judgement": judge(t, s),
                            "n_map_retries": len(rep.get("map_retries") or []),
                            "reduce_retry": bool(rep.get("reduce_retry"))}
            j = per_video[v]["judgement"]
            print(f"  {v[:34]:<36} 커버 {s['coverage_of_video']:.1%} "
                  f"문장 {s['n_sentences']:>4} 자/인용 {s['chars_per_cite_mean']:>6.1f} "
                  f"몰아 {s['cite_dump_sentences']:>2} 주지표 {j['primary_value']} "
                  f"관문 {'통과' if j['gates_all'] else '실패'} ({mins:.1f}분)")
        gates_all = all(p["judgement"]["gates_all"] for p in per_video.values())
        primary_all = all(p["judgement"]["primary_ok"] for p in per_video.values())
        res["arms"][arm] = {
            "config": {"strip_residual_cjk": strip_cjk,
                       "chunk_coverage_retry": chunk_retry,
                       "summary_budget": budget},
            "minutes": round((time.time() - t_arm) / 60, 1),
            "per_video": per_video,
            "verdict": ("개선 채택 후보 — 관문 통과 + 주 지표 달성" if gates_all and primary_all
                        else "결함은 고쳤으나 요약성 미달 — 주 지표 미달" if gates_all
                        else "미채택 — 관문 실패"),
            "gates_all_videos": gates_all, "primary_all_videos": primary_all}
        print(f"  판정: {res['arms'][arm]['verdict']}")
        p = OUT / args.out                         # arm 하나 끝날 때마다 저장(중단 대비)
        p.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    apply_arm(True, True)                          # 원상 복구
    print(f"\n저장: {OUT / args.out}  (리포트 원본: {REPDIR})")


if __name__ == "__main__":
    main()

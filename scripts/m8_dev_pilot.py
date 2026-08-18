"""M8 dev 예비 실행 — 구조 안정성만 잰다. **판정이 아니다.**

사전등록: `docs/preregistration/M8_dev예비실행_사전등록_2026-08-18.md`.

**답하는 것은 하나 — 새 구조(`generate_report_structured`)가 7B에서 안정적으로 도는가.**
Event Recall·관문 C1~C3는 산출하지 않는다. 정답 사건 목록이 아직 없고, dev 3편은
판정 표본이 아니다(원 사전등록 §3).

**기존 `report.json`을 건드리지 않는다.** `report_pilot_{run_id}.json`으로 따로 쓴다 —
덮어쓰기 방지를 `--force` 유무에 맡기지 않는다.

**M9를 부르지 않는다.** `split=="test"` 하드코딩이라 실행 자체가 test 접촉이다.

실행은 `scripts/exp_launcher.py`로 한다(계획: `planning/exp_plans/m8_dev_pilot.json`).
"""
import argparse, io, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402
import m8_report                                           # noqa: E402
from llm import make_llm                                   # noqa: E402
from m8_metrics import structural_summary                  # noqa: E402

OUT = ROOT / "docs" / "probes" / "_scratch"


def dev_video_ids(queries_path: Path) -> list:
    """dev 질의가 붙은 영상. **test는 건드리지 않는다.**"""
    vids = []
    for line in queries_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        q = json.loads(line)
        if q.get("split") == "dev" and q["video_id"] not in vids:
            vids.append(q["video_id"])
    return vids


def pilot_report_path(wdir, run_id: str) -> Path:
    """영상별 예비 산출물 경로. **run_id·stage에 귀속돼야 한다** — 이름이 같으면
    FULL이 중간에 죽었을 때 CANARY 산출물(1편·2청크)이 full 결과 행세를 한다."""
    return Path(wdir) / f"report_pilot_{run_id}.json"


def catastrophic_flags(rep: dict) -> dict:
    """원 사전등록 C1과 같은 정의 — 다른 언어 이탈·조기 종료·반복 루프.
    **판정하지 않고 관측만 한다**(관문 집행은 판정 사이클의 일이다)."""
    ev = rep.get("events") or []
    reasons = [r.get("reason") for r in rep.get("rejected") or []]
    sents = rep.get("sentences") or []
    return {
        "foreign_language": "foreign_language" in reasons or any(
            common.is_corrupted_caption(e["event"] + e["description"]) for e in ev),
        "no_events": not ev,
        "repeat_loop": bool(sents) and (
            m8_report.distinct_ratio(sents) < m8_report.MIN_DISTINCT_RATIO),
    }


def run_stats(rep: dict) -> dict:
    """실행 자체의 안정성 — 사전등록 §2."""
    raws, retries = rep.get("map_raw_outputs") or [], rep.get("chunk_retries") or []
    return {"chunks": len(raws),
            "json_parse_failure_rate": round(
                sum(1 for r in raws if not m8_report.parse_events(r)) / max(len(raws), 1), 4),
            "chunk_retries": len(retries),
            "chunk_retry_recovery_rate": round(
                sum(1 for r in retries if r["recovered"]) / len(retries), 4)
            if retries else None}


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_server.yaml")
    ap.add_argument("--queries", default="data/queries/queries.jsonl")
    ap.add_argument("--out", default="m8_dev_pilot.json")
    ap.add_argument("--run-id", default="adhoc")
    ap.add_argument("--limit-videos", type=int, default=None, help="배관 점검 전용")
    ap.add_argument("--limit-chunks", type=int, default=None, help="배관 점검 전용")
    a = ap.parse_args()

    cfg = common.load_config(str(ROOT / a.config))
    vids = dev_video_ids(ROOT / a.queries)[:a.limit_videos]
    assert vids, "dev 영상이 없다"
    print(f"dev {len(vids)}편: {vids}", flush=True)

    llm = make_llm(cfg["report_model"],
                   max_new_tokens=cfg.get("report_max_new_tokens", 2048),
                   load_4bit=cfg.get("llm_4bit", False))
    per_video = {}
    for v in vids:
        wdir = Path(common.work_dir(cfg, v))
        doc = common.load_segments(wdir / "segments.json",
                                   require=["subtitle", "caption"],
                                   seg_len=cfg["seg_len_sec"])
        segs = doc["segments"]
        if a.limit_chunks:                 # canary — 앞쪽 청크만
            segs = segs[:cfg["map_chunk_size"] * a.limit_chunks]
        rep = m8_report.generate_report_structured(
            segs, llm, cfg["map_chunk_size"], cfg["map_chunk_overlap"])
        # 확정 산출물을 건드리지 않는다 — 별도 파일명
        pilot_report_path(wdir, a.run_id).write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        # 원시 산출물은 launcher REPORT 게이트 밖에 있다. 기술적으로 막지는
        # 않지만(과하다) 표식을 남긴다 — 정식 열람 경로는 REPORT뿐이다.
        (wdir / "DO_NOT_INSPECT_BEFORE_INVENTORY_FREEZE.txt").write_text(
            f"{v}의 정답 사건 목록이 동결되기 전에는 report_pilot_*.json을 열지 마라.\n"
            f"먼저 보면 사건 단위를 모델 출력에 맞추게 되어 분모가 오염된다.\n"
            f"동결: python scripts/event_inventory_kit.py freeze --video-id {v}\n",
            encoding="utf-8")
        per_video[v] = {"n_segments": len(segs),
                        **structural_summary(rep, len(segs)),
                        **run_stats(rep),
                        "catastrophic": catastrophic_flags(rep)}
        # **구조 수치를 stdout에 찍지 않는다.** 로그는 REPORT 게이트 밖이라,
        # 영상별 사건 수가 여기 찍히면 정답 목록을 쓰기 전에 사람 눈에 들어온다
        # (2026-08-18 실측 — 배관 진단 중 `_10_000`의 사건 수가 노출됐다).
        print(f"  {v}: 완료", flush=True)

    rep_all = {"probe": "m8_dev_pilot",
               "prereg": "docs/preregistration/M8_dev예비실행_사전등록_2026-08-18.md",
               "purpose": "구조 안정성 확인 — 판정 아님. Event Recall 미산출",
               "run_id": a.run_id, "config": a.config,
               "n_videos": len(vids),
               "catastrophic_videos": sum(
                   1 for s in per_video.values() if any(s["catastrophic"].values())),
               "per_video": per_video,
               "provenance": m8_report.report_provenance(llm, cfg)}
    # launcher가 `{run_dir}`를 절대경로로 넘긴다 — 그때는 그대로 쓴다. 상대경로면
    # 예전처럼 프로브 기본 위치. 이걸 안 하면 산출물이 run 디렉터리 밖에 떨어져
    # validator의 expected_files가 항상 FAIL이다(2026-08-18 실측).
    p = Path(a.out)
    if not p.is_absolute():
        p = OUT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rep_all, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {p}")
    print("**정답 사건 목록 동결 전에는 이 결과를 열람하지 마라** (사전등록 §4)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

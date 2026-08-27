"""M8 공식 생성 — 판정 표본 8편. **구조 경로로 canonical `report.json`을 만든다.**

왜 별도 스크립트가 필요한가. `m8_report.main()`은 **reduce 경로**(`generate_report`)를
쓴다. 그 경로의 문장에는 `span`·`event`가 없어서 `match_events`에 넘길 생성 사건이
0개가 되고, C2·C3가 **모델과 무관한 이유로** 0/FAIL이 된다. 관문은
`M8_구조변경_사전등록_2026-08-16`의 **사건 구조**에 정의돼 있으므로 공식 생성은
`generate_report_structured`여야 한다. `m8_dev_pilot.py`가 그 경로를 쓰지만
`report_pilot_*.json`에 쓰고 확정 산출물을 만들지 않는다.

이 스크립트가 코드로 막는 것.

```
pre-run   evaluator 동결 --verify 불일치 · git dirty · GT 해시 불일치 ·
          freeze_id 불일치 · 기존 canonical report 존재  → 실행 거부
canary    확정 경로에 쓰지 않는다. run 디렉터리의 report_canary_<vid>.json
full      기존 report.json을 **덮지 않는다**(실패 정책 B — 미완료분만 재시도)
내용      manifest에 서술 문자열을 담지 않는다. 수·상태만 — 실행 중 열람 금지
```

`save_report`는 파일을 먼저 쓰고 구조 검증을 한다. 검증이 실패해도 리포트는 남고,
그 사실을 manifest에 적는다 — **삼키지 않는다.** C1이 그것을 판정한다.

사용:
    python scripts/m8_official.py --canary --limit-videos 1 --limit-chunks 2
    python scripts/m8_official.py --run-id <id>
"""
import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                      # noqa: E402
import m8_c1                                                       # noqa: E402
import m8_metrics as M                                             # noqa: E402
import m8_report                                                   # noqa: E402
import m8_evaluator_freeze as EF                                   # noqa: E402
import m8_gates                                                    # noqa: E402
from event_inventory_kit import aggregate_gt_hash                  # noqa: E402


class OfficialRunError(RuntimeError):
    """실행 규율 위반. **경고가 아니라 중단이다.**"""


GENERATOR_SOURCES = ("src/m8_report.py", "src/llm.py", "src/common.py")


def source_sha256(root=ROOT, files=GENERATOR_SOURCES) -> dict:
    """생성기 소스 해시. 줄바꿈을 정규화한다(`m8_evaluator_freeze._sha_file`과 같은 이유)."""
    out = {}
    for rel in files:
        p = Path(root) / rel
        out[rel] = (EF._sha_text(p.read_text(encoding="utf-8").replace("\r\n", "\n"))
                    if p.is_file() else None)
    return out


def prerun_gate(videos, work_root, verify_diffs, gt_sha256,
                expect_gt_sha256, freeze_id, expect_freeze_id,
                git_dirty=None, source_sha256=None, expect_source_sha256=None,
                allow_existing: bool = False) -> dict:
    """실행 직전 대조. 하나라도 어긋나면 생성을 시작하지 않는다.

    **git 청결도를 조건으로 쓰지 않는다.** 서버에는 push 없이 scp로 코드가 가므로
    트리는 항상 dirty고, 그것을 조건으로 두면 정상 실행이 막힌다. 실제로 필요한
    보장은 "생성기 소스가 동결 시점과 같은가"이고 그건 **해시로** 확인한다.
    `git_dirty`는 기록만 한다.
    """
    if verify_diffs:
        raise OfficialRunError(
            "evaluator 동결 이후 판정 코드가 바뀌었다 — 이 상태로 생성하면 "
            f"관문을 결과 뒤에 고친 것과 구분되지 않는다: {verify_diffs}")
    if expect_source_sha256:
        bad = {k: (expect_source_sha256.get(k), (source_sha256 or {}).get(k))
               for k in expect_source_sha256
               if (source_sha256 or {}).get(k) != expect_source_sha256[k]}
        if bad:
            raise OfficialRunError(
                f"생성기 소스가 동결 시점과 다르다 — {list(bad)} "
                f"(기대/현재: {bad}). 같은 코드로 8편을 생성해야 한다")
    if gt_sha256 != expect_gt_sha256:
        raise OfficialRunError(f"GT aggregate 해시 불일치 — 동결={expect_gt_sha256} "
                               f"현재={gt_sha256}")
    if freeze_id != expect_freeze_id:
        raise OfficialRunError(f"evaluator freeze_id 불일치 — 기대={expect_freeze_id} "
                               f"받음={freeze_id}")
    existing = [v for v in videos
                if (Path(work_root) / v / "report.json").is_file()]
    if existing and not allow_existing:
        raise OfficialRunError(
            f"canonical report.json이 이미 있다: {existing} — 첫 공식 실행이 아니다. "
            f"미완료분만 재시도하려면 --allow-existing (실패 정책 B)")
    return {"passed": True, "n_videos": len(videos),
            "existing_reports": existing, "allow_existing": allow_existing,
            "gt_sha256": gt_sha256, "freeze_id": freeze_id,
            "git_dirty": git_dirty, "source_sha256": source_sha256}


def generate_one(segments: list, llm, chunk_size: int, overlap: int) -> dict:
    """**구조 경로.** 병합 전 원본(`map_raw_outputs`)이 함께 남는다 — C1이 그것을 본다."""
    return m8_report.generate_report_structured(segments, llm, chunk_size, overlap)


def write_report(video_id: str, wdir, run_dir, cfg: dict, rep: dict,
                 n_segments: int, provenance: dict, canary: bool) -> dict:
    """canary는 run 디렉터리, full은 확정 경로. **덮어쓰지 않는다.**"""
    if canary:
        out = Path(run_dir) / f"report_canary_{video_id}.json"
        Path(run_dir).mkdir(parents=True, exist_ok=True)
    else:
        out = Path(wdir) / "report.json"
        if out.is_file():
            raise OfficialRunError(f"{video_id}: report.json을 덮지 않는다 ({out})")
    err = None
    try:
        m8_report.save_report(out, video_id, cfg, rep, n_segments,
                              provenance=provenance)
    except AssertionError as e:
        # 파일은 이미 저장됐다. 삼키면 C1이 판정할 근거가 사라진다.
        err = str(e)[:300]
    return {"path": str(out), "structural_assert": err}


def video_manifest_row(video_id: str, rep: dict, n_segments: int,
                       written: dict) -> dict:
    """**수와 상태만.** 서술 문자열·C1 evidence를 담지 않는다 — 그게 들어가면
    8편 생성이 끝나기 전에 내용을 본 것이 된다."""
    finding = m8_c1.inspect_video(rep)
    st = M.structural_summary(rep, n_segments)
    return {"video_id": video_id, "n_segments": n_segments,
            "n_sentences": len(rep.get("sentences") or []),
            "n_events": len(rep.get("events") or []),
            "valid_events": st["valid_events"],
            "rejected_events": st["rejected_events"],
            "rejection_reasons": st["rejection_reasons"],
            "uncited_evaluable_sentences": st.get("uncited_evaluable_sentences"),
            "chunks": len(rep.get("map_raw_outputs") or []),
            "chunk_retries": len(rep.get("chunk_retries") or []),
            "c1_status": m8_c1.video_status(finding),
            "c1_kind_status": {k: finding[k]["status"] for k in m8_c1.C1_KINDS},
            "path": written["path"],
            "structural_assert": written["structural_assert"]}


def run(cfg, videos: list, llm, run_dir, run_id: str, canary: bool,
        limit_videos=None, limit_chunks=None, allow_existing=False,
        prerun: dict | None = None) -> dict:
    rows, failures = [], []
    for v in (videos[:limit_videos] if limit_videos else videos):
        wdir = Path(common.work_dir(cfg, v))
        if not canary and (wdir / "report.json").is_file():
            print(f"  {v}: 이미 있다 — 건너뛴다", flush=True)
            continue
        try:
            doc = common.load_segments(wdir / "segments.json",
                                       require=["subtitle", "caption"],
                                       seg_len=cfg["seg_len_sec"])
            s = doc["segments"]
            if limit_chunks:
                s = s[:cfg["map_chunk_size"] * limit_chunks]
            rep = generate_one(s, llm, cfg["map_chunk_size"],
                               cfg["map_chunk_overlap"])
            written = write_report(v, wdir, run_dir, cfg, rep, len(s),
                                   m8_report.report_provenance(llm, cfg), canary)
            rows.append(video_manifest_row(v, rep, len(s), written))
            print(f"  {v}: 완료", flush=True)     # 수치를 찍지 않는다
        except Exception as e:                     # noqa: BLE001 — 한 편 실패가 배치를 죽이지 않는다
            failures.append({"video_id": v, "error": f"{type(e).__name__}: {e}"[:300]})
            print(f"  {v}: 실패 ({type(e).__name__})", flush=True)
    return {"run_id": run_id, "stage": "CANARY" if canary else "FULL",
            "gate_spec": "docs/finalization/M8_GATE_SPEC_FREEZE_2026-08-27.md",
            "evaluator_freeze": "docs/finalization/m8_evaluator_freeze_2026-08-27.json",
            "prerun": prerun, "n_requested": len(videos),
            "n_written": len(rows), "failures": failures, "per_video": rows}


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_server.yaml")
    ap.add_argument("--run-id", default="m8_official")
    ap.add_argument("--out", default=None, help="run 디렉터리 (기본 results/<run_id>)")
    ap.add_argument("--canary", action="store_true")
    ap.add_argument("--limit-videos", type=int, default=None)
    ap.add_argument("--limit-chunks", type=int, default=None)
    ap.add_argument("--expect-source-sha", default=None,
                    help="생성기 소스 해시 JSON — 동결 시점과 대조한다")
    ap.add_argument("--print-source-sha", action="store_true",
                    help="이 머신의 생성기 소스 해시만 출력하고 끝낸다")
    ap.add_argument("--allow-existing", action="store_true",
                    help="실패 정책 B — 미완료분만 재시도")
    a = ap.parse_args()

    if a.print_source_sha:
        print(json.dumps(source_sha256(), ensure_ascii=False, indent=2))
        return 0
    cfg = common.load_config(str(ROOT / a.config))
    videos = m8_gates.panel_videos()
    run_dir = Path(a.out) if a.out else ROOT / "results" / a.run_id
    art_path = EF.DEFAULT_OUT
    if not art_path.is_file():
        raise OfficialRunError(f"evaluator 동결본이 없다: {art_path}")
    art = json.loads(art_path.read_text(encoding="utf-8"))
    expect_src = json.loads(Path(a.expect_source_sha).read_text(encoding="utf-8"))         if a.expect_source_sha else None
    prerun = prerun_gate(
        videos=videos, work_root=Path(cfg["paths"]["work"]),
        verify_diffs=EF.verify(art),
        git_dirty=EF.git_dirty(exclude=[EF._rel_out()]),
        source_sha256=source_sha256(), expect_source_sha256=expect_src,
        gt_sha256=aggregate_gt_hash(videos)["sha256"],
        expect_gt_sha256=art["aggregate_gt_sha256"],
        freeze_id=art["freeze_id"], expect_freeze_id="m8_evaluator_2026-08-27",
        allow_existing=a.allow_existing)
    prerun["git_head"] = EF._git("rev-parse", "HEAD")
    prerun["c2_metric"] = art["c2_metric"]
    print(f"pre-run PASS · HEAD {prerun['git_head'][:8]} · "
          f"GT {prerun['gt_sha256'][:12]} · 영상 {len(videos)}편", flush=True)

    from llm import make_llm
    llm = make_llm(cfg["report_model"],
                   max_new_tokens=cfg.get("report_max_new_tokens", 2048),
                   load_4bit=cfg.get("llm_4bit", False))
    man = run(cfg, videos, llm, run_dir, a.run_id, a.canary,
              a.limit_videos, a.limit_chunks, a.allow_existing, prerun)
    run_dir.mkdir(parents=True, exist_ok=True)
    mpath = run_dir / f"m8_official_{man['stage'].lower()}.json"
    common.atomic_write_json(mpath, man)
    print(f"{man['stage']} 완료 — 생성 {man['n_written']}편 · "
          f"실패 {len(man['failures'])}편")
    print(f"manifest: {mpath}")
    return 1 if man["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

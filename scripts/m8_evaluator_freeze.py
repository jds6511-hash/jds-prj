"""evaluator 동결 — **M8 공식 생성 직전** 시점의 대조 가능성.

`m8_freeze.py`와 다른 관문이다. 그쪽은 *M9 test를 열기 전*에 생성 조건을 고정하고,
이쪽은 *M8 공식 출력을 처음 보기 전*에 **판정 쪽**을 고정한다. 나중에 "결과를 보고
관문 코드를 고친 게 아니냐"에 답하는 근거다.

```
GT             동결본 8편의 aggregate hash
관문 규격 문서    M8_GATE_SPEC_FREEZE · 사전등록 2건 · GT 동결 기록
관문 구현        C1/C2/C3별로 그 관문을 계산하는 **함수 소스**의 해시
evaluator 소스   m8_c1 · m8_metrics · m8_gates · event_inventory_kit
동결 상수        임계·통계량·상태 enum·반복 연속 하한
미결             C2 판정 지표 — **채우지 않고 미결로 기록한다**
열람 여부        official_m8_output_viewed=false, 파일 수 실측으로 증거
```

사용:
    python scripts/m8_evaluator_freeze.py
    python scripts/m8_evaluator_freeze.py --verify
"""
import argparse
import hashlib
import inspect
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import common                                                      # noqa: E402
import m8_c1                                                       # noqa: E402
import m8_gates                                                    # noqa: E402
import m8_metrics as M                                             # noqa: E402
import event_inventory_kit as K                                    # noqa: E402

DEFAULT_OUT = ROOT / "docs/finalization/m8_evaluator_freeze_2026-08-27.json"

SPEC_DOCS = {
    "gate_spec": "docs/finalization/M8_GATE_SPEC_FREEZE_2026-08-27.md",
    "gate_rules": "docs/preregistration/M8_구조변경_사전등록_2026-08-16.md",
    "event_metric_spec": "docs/preregistration/M8_event지표_보충_2026-08-18.md",
    "event_inventory_protocol": "docs/preregistration/event_inventory_사전등록_2026-08-18.md",
    "gt_freeze": "docs/finalization/m8_c2_gt_freeze_2026-08-27.json",
}
EVALUATOR_SOURCES = {
    "m8_c1": "src/m8_c1.py",
    "m8_metrics": "src/m8_metrics.py",
    "m8_gates": "scripts/m8_gates.py",
    "event_inventory_kit": "scripts/event_inventory_kit.py",
}
# 관문별로 **그 관문을 계산하는 함수**만 묶는다. 파일 해시는 무관한 변경에도 움직여
# 대조가 둔해지고, 함수 해시는 무엇이 바뀌었는지 관문 단위로 가른다.
GATE_FUNCS = {
    "C1": [m8_c1.premerge_units, m8_c1.detect_repetition_loop,
           m8_c1.detect_early_stop, m8_c1.detect_language_drift,
           m8_c1.inspect_video, m8_c1.video_status,
           M._c1_statuses, M.c1_catastrophic_count, M.c1_verdict],
    "C2": [M.temporal_iou, M.match_events, M.matched_ious,
           M.event_temporal_alignment, M.temporal_event_recall,
           M.c2_statistic, M.c2_verdict, m8_gates.c2_candidates],
    "C3": [M.compression, M.c3_verdict, m8_gates.video_compression],
}
CONFIG_KEYS = ("seg_len_sec", "report_model", "report_max_new_tokens", "llm_4bit",
               "map_chunk_size", "map_chunk_overlap")


def _sha_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def _sha_file(rel: str):
    """**줄바꿈을 정규화한 뒤** 해시한다.

    Windows에서 `git checkout`이 LF를 CRLF로 바꾸므로 바이트 해시는 내용이 같아도
    달라진다(2026-08-27 실측 — 같은 커밋을 되돌린 직후 verify가 깨졌다). 줄바꿈
    때문에 깨지는 대조 도구는 대조를 안 하는 것과 같다.
    """
    p = ROOT / rel
    if not p.is_file():
        return None
    return _sha_text(p.read_text(encoding="utf-8").replace("\r\n", "\n"))


def _git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def gate_hash(gate: str, extra_sources=None) -> str:
    src = [inspect.getsource(f) for f in GATE_FUNCS[gate]]
    src += list(extra_sources or [])
    return _sha_text("\n".join(src))


def frozen_gate_constants() -> dict:
    """동결된 숫자·enum을 값으로 박는다 — 코드가 바뀌면 이 값도 함께 움직인다."""
    return {"C1_threshold_videos": 0,
            "C1_kinds": list(M.CATASTROPHIC_KINDS),
            "C1_statuses": list(m8_c1.STATUSES),
            "C1_repetition_min_run": m8_c1.REPETITION_MIN_RUN,
            "C2_statistic": "median", "C2_threshold": m8_gates.C2_THRESHOLD,
            "C3_statistic": m8_gates.C3_STATISTIC,
            "C3_threshold": m8_gates.C3_THRESHOLD}


def official_output_evidence(cfg, videos: list) -> dict:
    """**선언이 아니라 실측.** 패널 영상 작업 디렉터리에 리포트 파일이 있는지 센다."""
    found = []
    for v in videos:
        w = Path(common.work_dir(cfg, v))
        found += [str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
                  for pat in ("report.json", "report_pilot_*.json")
                  for p in w.glob(pat)]
    return {"videos_scanned": len(videos), "report_files_found": len(found),
            "files": sorted(found)}


def run_test_suite() -> dict:
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"],
                       cwd=ROOT, capture_output=True, encoding="utf-8",
                       errors="replace")
    m = re.search(r"(\d+) passed(?:, (\d+) skipped)?", r.stdout or "")
    return {"command": "python -m pytest tests/ -q",
            "exit_code": r.returncode,
            "passed": int(m.group(1)) if m else None,
            "skipped": int(m.group(2)) if (m and m.group(2)) else 0}


def build_artifact(run_tests: bool = True, config_path=None, gt_dir=None,
                   freeze_id: str = "m8_evaluator_2026-08-27") -> dict:
    cfg_path = Path(config_path or (ROOT / "config.yaml"))
    cfg = common.load_config(cfg_path)
    videos = m8_gates.panel_videos()
    gt = K.aggregate_gt_hash(videos, out_dir=gt_dir)      # 미동결이면 여기서 거부된다
    frozen_cfg = {k: cfg.get(k) for k in CONFIG_KEYS}
    cands = sorted(set(M.IOU_THETAS and
                       [f"temporal_event_recall@IoU>={t}" for t in M.IOU_THETAS])
                   | {"event_temporal_alignment"})
    return {
        "freeze_id": freeze_id,
        "purpose": "M8 공식 출력을 처음 보기 전에 판정 쪽을 고정한다",
        "official_m8_output_viewed": False,
        "official_output_evidence": official_output_evidence(cfg, videos),
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "n_videos": gt["n_videos"], "n_reference_events": gt["n_events"],
        "aggregate_gt_sha256": gt["sha256"],
        "spec_doc_sha256": {k: _sha_file(v) for k, v in sorted(SPEC_DOCS.items())},
        "evaluator_source_sha256": {k: _sha_file(v)
                                    for k, v in sorted(EVALUATOR_SOURCES.items())},
        "gate_implementation_sha256": {g: gate_hash(g) for g in sorted(GATE_FUNCS)},
        "frozen_gate_constants": frozen_gate_constants(),
        "config_frozen_keys": frozen_cfg,
        "config_sha256": _sha_text(json.dumps(frozen_cfg, ensure_ascii=False,
                                              sort_keys=True)),
        "c2_metric_decided": False,
        "c2_metric": None,
        "c2_metric_candidates": cands,
        "c2_metric_note": ("원 사전등록 §2-3은 'Event Recall 중앙값'이라 적었고 보충 "
                           "§3-3은 주지표를 event_temporal_alignment(연속값)로 두면서 "
                           "θ 기반 recall은 세 값을 모두 보고하고 하나를 고르지 "
                           "않는다고 했다. 판정 지표를 결과 열람 전에 별도로 정해야 "
                           "하며, m8_gates.panel_verdict는 명시 없이는 거부한다"),
        "unimplemented": ["Redundancy(사전등록 §2-2 부지표) — 진단으로만 보고"],
        "tests": run_test_suite() if run_tests else None,
        "note": ("이 파일 이후 evaluator 소스·관문 상수·GT가 바뀌면 판정과 분리 "
                 "불가능해진다. --verify로 대조한다."),
    }


def verify(artifact: dict) -> list:
    now = build_artifact(run_tests=False, freeze_id=artifact.get("freeze_id", ""))
    diffs = []
    for key in ("aggregate_gt_sha256", "config_sha256"):
        if now[key] != artifact.get(key):
            diffs.append(f"{key}: 동결={artifact.get(key)} 현재={now[key]}")
    for group in ("spec_doc_sha256", "evaluator_source_sha256",
                  "gate_implementation_sha256"):
        for name, want in (artifact.get(group) or {}).items():
            if now[group].get(name) != want:
                diffs.append(f"{group}.{name}: 동결={want} 현재={now[group].get(name)}")
    if now["frozen_gate_constants"] != artifact.get("frozen_gate_constants"):
        diffs.append("frozen_gate_constants가 바뀌었다")
    return diffs


def main() -> int:
    # 콘솔이 cp949라 한글·em dash가 그대로는 터진다(2026-08-27 실측)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--skip-tests", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)

    if a.verify:
        if not out.is_file():
            print(f"동결본이 없다: {out}")
            return 2
        diffs = verify(json.loads(out.read_text(encoding="utf-8")))
        if diffs:
            print("동결 이후 변경됨:")
            for d in diffs:
                print("  -", d)
            return 1
        print(f"동결 상태 그대로다 — {out.name}")
        return 0

    if out.exists():
        print(f"이미 있다: {out} — 동결본을 덮지 않는다. --verify로 대조하라")
        return 2
    art = build_artifact(run_tests=not a.skip_tests)
    common.atomic_write_json(out, art)
    print(f"기록: {out}")
    print(f"  GT {art['aggregate_gt_sha256'][:12]} · 사건 {art['n_reference_events']}건")
    print(f"  C1 {art['gate_implementation_sha256']['C1'][:12]} · "
          f"C2 {art['gate_implementation_sha256']['C2'][:12]} · "
          f"C3 {art['gate_implementation_sha256']['C3'][:12]}")
    print(f"  official_m8_output_viewed={art['official_m8_output_viewed']} "
          f"(리포트 파일 {art['official_output_evidence']['report_files_found']}건)")
    if art["tests"]:
        print(f"  tests {art['tests']['passed']} passed · "
              f"exit {art['tests']['exit_code']}")
    print("  C2 판정 지표는 미결로 기록됐다 — 정한 뒤 별도 문서로 남겨라")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

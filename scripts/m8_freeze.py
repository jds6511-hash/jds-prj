"""M8 동결 manifest 생성 — **M9 test를 열기 전에** 무엇이 고정됐는지 남긴다.

왜 필요한가. M9는 test 접촉이고 비가역이다. 나중에 "test 결과를 보고 프롬프트를 바꾼 게
아니냐"는 질문에 답할 수 있어야 한다. 답의 근거는 기억이 아니라 **test를 열기 전 시점의
해시**다.

무엇을 고정하는가 — M8 산출물을 바꿀 수 있는 것 전부다.

```
config          report_model · report_max_new_tokens · llm_4bit · map_chunk_size/overlap
프롬프트         _SYSTEM · map · reduce · event 규칙 (m8_report.prompt_sources)
스키마           m8_report.SCHEMA_VERSION + sentence/event 필드 계약
validator       aar_view(추적) · m8_metrics(지표) 파일 해시
평가 규칙        관문 C1~C3 · Event Recall 정의 문서
```

`test_opened`는 이 파일이 만들어지는 시점에 **항상 false**다. true로 바꾸는 것은
test-opening 승인 사건의 기록이며 이 스크립트가 하지 않는다.

동결은 **선언이 아니라 대조 가능성**이다. 그래서 `--verify`로 지금 상태가 manifest와
같은지 다시 물을 수 있게 한다 — 다르면 그 실행은 동결 이후 변경된 코드로 돈 것이다.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common                                                    # noqa: E402
import m8_report                                                 # noqa: E402

DEFAULT_OUT = ROOT / "docs/finalization/m8_freeze_manifest_2026-08-26.json"

# 해시를 뜨는 파일. M8 산출물·판정에 영향을 주는 것만 넣는다.
FROZEN_FILES = {
    "m8_report": "src/m8_report.py",
    "m8_metrics": "src/m8_metrics.py",
    "llm": "src/llm.py",
    "aar_view": "scripts/aar_view.py",
    "common": "src/common.py",
}
# 판정 규칙 문서. 관문 C1~C3와 Event Recall 정의가 여기에 있다.
RULE_DOCS = {
    "gate_rules": "docs/preregistration/M8_구조변경_사전등록_2026-08-16.md",
    "event_metric_spec": "docs/preregistration/M8_event지표_보충_2026-08-18.md",
    "event_inventory_protocol": "docs/preregistration/event_inventory_사전등록_2026-08-18.md",
}
CONFIG_KEYS = ("report_model", "report_max_new_tokens", "llm_4bit",
               "map_chunk_size", "map_chunk_overlap", "judge_model",
               "same_model_judge", "human_check_n")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(rel: str) -> str | None:
    p = ROOT / rel
    if not p.is_file():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git(*a) -> str:
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True,
                       encoding="utf-8", errors="replace")
    return r.stdout.strip()


def prompt_hashes() -> dict:
    """프롬프트 원문의 해시. `m8_report.prompt_sources()`가 원문을 들고 있다."""
    return {k: _sha256_text(v) for k, v in sorted(m8_report.prompt_sources().items())}


def build_manifest(config_path=None, freeze_id: str = "m8_final_2026-08-26") -> dict:
    cfg_path = Path(config_path or (ROOT / "config.yaml"))
    cfg = common.load_config(cfg_path)
    frozen_cfg = {k: cfg.get(k) for k in CONFIG_KEYS}
    return {
        "freeze_id": freeze_id,
        "test_opened": False,       # 이 스크립트는 이 값을 true로 만들지 않는다
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "config_path": cfg_path.name,
        "config_frozen_keys": frozen_cfg,
        "config_sha256": _sha256_text(
            json.dumps(frozen_cfg, ensure_ascii=False, sort_keys=True)),
        "report_schema_version": m8_report.SCHEMA_VERSION,
        "prompt_sha256": prompt_hashes(),
        "file_sha256": {k: _sha256_file(v) for k, v in sorted(FROZEN_FILES.items())},
        "rule_doc_sha256": {k: _sha256_file(v) for k, v in sorted(RULE_DOCS.items())},
        "input_contract": "work/<video_id>/segments.json (프레임·영상·임베딩 불필요)",
        "note": ("M8 동결 시점 기록. test_opened=false이고, 이 파일 이후의 프롬프트·스키마·"
                 "validator·판정 규칙 변경은 M9 결과와 분리 불가능해진다."),
    }


def verify(manifest: dict) -> list:
    """지금 상태가 manifest와 다른 항목 목록. 빈 리스트면 동결 상태 그대로다."""
    now = build_manifest(freeze_id=manifest.get("freeze_id", ""))
    diffs = []
    for key in ("config_sha256", "report_schema_version"):
        if now[key] != manifest.get(key):
            diffs.append(f"{key}: manifest={manifest.get(key)} now={now[key]}")
    for group in ("prompt_sha256", "file_sha256", "rule_doc_sha256"):
        for name, want in (manifest.get(group) or {}).items():
            got = now[group].get(name)
            if got != want:
                diffs.append(f"{group}.{name}: manifest={want} now={got}")
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--freeze-id", default="m8_final_2026-08-26")
    ap.add_argument("--verify", action="store_true",
                    help="기록 대신 대조만 한다 — 동결 이후 변경된 것이 있으면 비0으로 끝난다")
    a = ap.parse_args()
    out = Path(a.out)

    if a.verify:
        if not out.is_file():
            print(f"manifest가 없다: {out}")
            return 2
        diffs = verify(json.loads(out.read_text(encoding="utf-8")))
        if diffs:
            print("동결 이후 변경됨:")
            for d in diffs:
                print("  -", d)
            return 1
        print(f"동결 상태 그대로다 — {out.name}")
        return 0

    man = build_manifest(a.config, a.freeze_id)
    if out.exists():
        print(f"이미 있다: {out} — 동결본을 덮지 않는다. --verify로 대조하라")
        return 2
    common.atomic_write_json(out, man)
    print(f"기록: {out}")
    print(f"  git {man['git_commit'][:8]} · schema v{man['report_schema_version']} "
          f"· config {man['config_sha256'][:12]} · test_opened={man['test_opened']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

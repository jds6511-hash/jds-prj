"""케이스 스터디용 격리 config를 **config.yaml에서 재생성**한다. 수동 편집 금지.

arm별로 바꾸는 것은 두 가지뿐이다 — caption_model과 paths(work/results 분리).
prompt·max_new_tokens·rep_penalty·max_pixels·4bit·embed_model·seg_len·static_threshold는
그대로 둔다. 어느 arm에도 유리하게 튜닝하지 않는다(생성 전후를 assert로 대조).

두 arm 모두 오늘 같은 기계·같은 코드 경로에서 새로 생성한다(동시점 대조).
기존 2026-07 저장 3B 산출물은 덮어쓰지도 삭제하지도 않고, 이 대조에 쓰지 않는다.

사용: python scripts/casestudy_make_config.py <run_dir> <arm>     arm = 3b | 4b
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "config.yaml"

ARMS = {
    "3b": {"model": "Qwen/Qwen2.5-VL-3B-Instruct", "dir": "3b_fresh"},
    "4b": {"model": "Qwen/Qwen3-VL-4B-Instruct", "dir": "4b_fresh"},
}

KEEP_IDENTICAL = ("caption_prompt", "vlm_max_new_tokens", "vlm_rep_penalty",
                  "vlm_max_pixels", "vlm_4bit", "embed_model", "seg_len_sec",
                  "static_threshold")


def make(run_dir: Path, arm: str) -> Path:
    if arm not in ARMS:
        raise SystemExit("arm은 %s 중 하나다" % list(ARMS))
    cfg = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    before = {k: cfg.get(k) for k in KEEP_IDENTICAL}

    a = ARMS[arm]
    cfg["caption_model"] = a["model"]
    cfg["paths"] = dict(cfg.get("paths") or {})
    cfg["paths"]["work"] = (run_dir / a["dir"] / "work").as_posix()
    cfg["paths"]["results"] = (run_dir / a["dir"] / "results").as_posix()

    after = {k: cfg.get(k) for k in KEEP_IDENTICAL}
    assert before == after, "생성 조건이 바뀌었다 — 튜닝 금지 항목"

    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / ("config_%s.yaml" % arm)
    out.write_text(
        "# 자동 생성 — scripts/casestudy_make_config.py (수동 편집 금지)\n"
        "# 본 config.yaml에서 caption_model과 paths만 바꿨다. arm=%s\n" % arm
        + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    return out


if __name__ == "__main__":
    rd = Path(sys.argv[1])
    print("wrote %s" % make(rd, sys.argv[2]))

"""서버(RTX 4090 24GB)용 config를 **config.yaml에서 재생성**한다. 수동 편집 금지.

바꾸는 것은 두 가지뿐이다.
  llm_4bit  true → false   24GB에서는 7B를 bf16으로 올린다(로컬 6GB 대응값을 되돌린다)
  paths     서버 저장 경로  /home에 두면 시스템 디스크가 찬다 — /ssd 필수

프롬프트·모델 ID·chunk 설정·seg_len·embed_model 등은 그대로 둔다(assert로 대조).
본 config.yaml을 편집하지 않는다.

사용: python scripts/make_server_config.py [--base /ssd/daeseok/prj] [--out config_server.yaml]
"""
import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "config.yaml"

KEEP_IDENTICAL = ("report_model", "judge_model", "caption_model", "embed_model",
                  "caption_prompt", "map_chunk_size", "map_chunk_overlap",
                  "seg_len_sec", "static_threshold", "vlm_max_new_tokens",
                  "vlm_rep_penalty", "vlm_max_pixels", "stt_model", "stt_language")


def make(base_dir: str, out: Path) -> Path:
    cfg = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    before = {k: cfg.get(k) for k in KEEP_IDENTICAL}

    cfg["llm_4bit"] = False
    cfg["paths"] = dict(cfg.get("paths") or {})
    for k, sub in (("data", "data"), ("work", "work"), ("results", "results")):
        cfg["paths"][k] = "%s/%s" % (base_dir.rstrip("/"), sub)

    after = {k: cfg.get(k) for k in KEEP_IDENTICAL}
    assert before == after, "생성 조건이 바뀌었다 — 변경 금지 항목"

    out.write_text(
        "# 자동 생성 — scripts/make_server_config.py (수동 편집 금지)\n"
        "# config.yaml에서 llm_4bit와 paths만 바꿨다. 서버 RTX 4090 24GB 전용.\n"
        + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="/ssd/daeseok/prj",
                    help="서버 저장 루트 (/home 금지)")
    ap.add_argument("--out", default=str(ROOT / "config_server.yaml"))
    a = ap.parse_args()
    p = make(a.base, Path(a.out))
    print("wrote %s  (llm_4bit=false · paths -> %s)" % (p, a.base))

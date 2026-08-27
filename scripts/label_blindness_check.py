"""라벨링 산출물에 금지 정보가 새지 않았는지 검사한다 — **blindness 스모크.**

reference 사건 라벨은 프레임 실물만 보고 만들어야 한다(CLAUDE.md 절대규칙 3). 도구가
막고 있지만, "정말 blind였나"는 나중에 물어보게 되는 질문이므로 **증거를 남긴다.**

```
검사 대상   label_kit/ 아래 파일 전부 (이미지 · JSON · CSV · HTML · 파일명)
금지 정보   캡션 문자열 · 자막 문자열 · 검색 score · rank · M8 리포트 문장 · pilot 수치
방법       ① 파일명에 금지 토큰 ② 텍스트 파일 안에 금지 필드/문자열
           ③ **실제 캡션·자막 원문**을 segments.json에서 가져와 부분 문자열 대조
```

③이 핵심이다. 필드 이름만 검사하면 값이 다른 이름으로 실려 들어온 경우를 놓친다.

이미지 픽셀 안의 글자는 검사하지 않는다(OCR 없음). 대신 컨택트시트를 만드는 경로가
`label_guard`의 allowlist(`idx`·`start`·`end`·`rep_frame`)를 지나는지는 테스트가 잠근다.

재현: python scripts/label_blindness_check.py --out label_kit/blindness_check.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common                                                   # noqa: E402

LABEL_KIT = ROOT / "label_kit"
MANIFEST = ROOT / "docs" / "finalization" / "m8_c2_panel_manifest_2026-08-27.json"

TEXT_SUFFIXES = {".json", ".jsonl", ".csv", ".tsv", ".txt", ".md", ".html", ".htm", ".yaml"}
# 사람이 읽는 규칙 문서. "캡션을 보지 마라"를 적으려면 그 단어를 써야 하므로 토큰
# 검사에서 뺀다 — 대신 **값 대조**(§caption_or_subtitle_value_hits)는 여기도 적용된다.
GUIDE_SUFFIXES = {".md"}
# 데이터 파일 본문·파일명에서 금지하는 토큰. 값이 아니라 **정보 종류**를 막는다.
BANNED_TOKENS = ("caption", "subtitle", "캡션", "score", "rank", "mrr",
                 "recall", "groundedness", "coverage_rate", "report.json",
                 "eval_", "alpha_star", "pilot")
# `자막`은 질의 유형명 `자막형`과 겹친다 — 유형명이 아닐 때만 잡는다
BANNED_PATTERNS = ((r"자막(?!형)", "자막"),)
# 라벨 도구가 정당하게 쓰는 이름 — 위 토큰과 겹쳐도 통과시킨다
ALLOWED_NAME_TOKENS = ("blindness_check", "contact_sheet")
MIN_SNIPPET = 12          # 이보다 짧은 캡션 조각은 우연 일치가 나오므로 대조에서 뺀다

# 이 과제(M8 C2 reference 라벨링)에서 라벨러가 실제로 여는 산출물.
# `label_kit/` 전체에는 다른 과제의 도구가 섞여 있다 — 예를 들어 `i1_frames/`는
# **캡션 자체가 라벨 대상이던** I1 검출기 과제라 캡션이 들어 있는 것이 정상이다.
# 두 과제를 같은 기준으로 재면 이 검사가 늘 FAIL을 뱉어 쓸모가 없어진다.
STRICT_DIRS = ("contact_sheets", "event_inventory")


def panel_videos(manifest=MANIFEST) -> list:
    return list(json.loads(Path(manifest).read_text(encoding="utf-8"))["final_panel"])


def forbidden_strings(videos: list) -> dict:
    """영상별 캡션·자막 원문. **값 자체**를 대조 재료로 쓴다."""
    out = {}
    for v in videos:
        p = ROOT / "work" / v / "segments.json"
        if not p.exists():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        snips = []
        for s in doc["segments"]:
            for k in ("caption", "subtitle"):
                t = (s.get(k) or "").strip()
                if len(t) >= MIN_SNIPPET:
                    snips.append(t[:40])          # 앞 40자면 유출 판정에 충분하다
        out[v] = snips
    return out


def scan(root=LABEL_KIT, videos=None) -> dict:
    videos = videos or panel_videos()
    snippets = forbidden_strings(videos)
    files = [p for p in Path(root).rglob("*") if p.is_file()] if Path(root).exists() else []
    name_hits, body_hits, value_hits, other_scope = [], [], [], []

    def in_strict(p: Path) -> bool:
        return any(d in p.parts for d in STRICT_DIRS)

    for p in files:
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        low = p.name.lower()
        strict = in_strict(p)
        if strict and not any(a in low for a in ALLOWED_NAME_TOKENS):
            for t in BANNED_TOKENS:
                if t.lower() in low:
                    name_hits.append({"file": rel, "token": t})
        if p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # 토큰 검사 — strict 범위의 **데이터 파일**만. 규칙 문서는 그 단어를 써야 한다
        if strict and p.suffix.lower() not in GUIDE_SUFFIXES:
            for t in BANNED_TOKENS:
                if re.search(re.escape(t), text, re.IGNORECASE):
                    body_hits.append({"file": rel, "token": t})
            for pat, name in BANNED_PATTERNS:
                if re.search(pat, text):
                    body_hits.append({"file": rel, "token": name})

        # 값 대조 — **범위 전체**에 적용한다. 이게 실제 유출 검사다
        for v, snips in snippets.items():
            hit = next((sn for sn in snips if sn and sn in text), None)
            if hit:
                rec = {"file": rel, "video_id": v, "snippet": hit[:24]}
                (value_hits if strict else other_scope).append(rec)
                break

    ok = not (name_hits or body_hits or value_hits)
    return {
        "probe": "label_blindness_check",
        "root": str(Path(root).relative_to(ROOT)).replace("\\", "/"),
        "strict_dirs": list(STRICT_DIRS),
        "n_files": len(files),
        "n_files_strict": sum(1 for p in files if in_strict(p)),
        "n_videos_checked": len(snippets),
        "n_snippets": sum(len(v) for v in snippets.values()),
        "banned_tokens": list(BANNED_TOKENS) + [n for _, n in BANNED_PATTERNS],
        "filename_hits": name_hits,
        "body_token_hits": body_hits,
        "caption_or_subtitle_value_hits": value_hits,
        "out_of_scope_value_hits": other_scope,
        "note": ("판정은 strict 범위(이번 과제 산출물)로 한다. `label_kit/` 안의 다른 과제 "
                 "산출물은 out_of_scope로 따로 적는다 — 예를 들어 `i1_frames/`는 캡션 자체가 "
                 "라벨 대상이던 I1 검출기 과제다. 이미지 픽셀 속 글자는 검사하지 않는다"
                 "(OCR 없음) — 생성 경로가 label_guard allowlist를 지나는지는 테스트가 잠근다"),
        "verdict": "PASS" if ok else "FAIL",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(LABEL_KIT))
    ap.add_argument("--out", type=Path, default=LABEL_KIT / "blindness_check.json")
    args = ap.parse_args()
    res = scan(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    common.atomic_write_json(args.out, res)
    print(f"파일 {res['n_files']} · 영상 {res['n_videos_checked']} · "
          f"대조 문자열 {res['n_snippets']}")
    for k in ("filename_hits", "body_token_hits", "caption_or_subtitle_value_hits"):
        print(f"  {k:34} {len(res[k])}")
    print(f"판정: {res['verdict']}  → {args.out}")
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

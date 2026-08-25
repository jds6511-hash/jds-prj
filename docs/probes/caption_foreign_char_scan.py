"""캡션 외국어 문자 혼입 스캔 — **측정만 한다. 규칙도 인덱스도 바꾸지 않는다.**

배경. `common.is_corrupted_caption`은 한자·가나를 **절대 3자 이상 또는 비율 20% 초과**로
판정한다. 그런데 실제로 가장 흔한 혼입 형태가 `フラ`·`满了`·`っぱ`처럼 **2자 삽입**이라
임계값 아래로 빠져나간다. 이 스크립트는 그 미탐 규모를 센다.

현행 규칙과, "한글·ASCII 외 글자(letter)를 전부 오염으로 보는" 가상 규칙을 같은 캡션에
나란히 적용해 차이를 센다. **어떤 캡션도 수정하지 않고, 검출기를 바꾸지 않는다.**
(2026-08-25 사용자 결정: 기록만 — 확정 인덱스 재판정은 하지 않는다.)

기호·숫자·문장부호·이모지는 세지 않는다(`str.isalpha()`로 글자만 본다). 따라서
`℃`·`·`·`①` 같은 정상 문자는 오탐하지 않는다.

콘솔이 cp949라 한글이 깨지므로 결과는 UTF-8 JSON으로만 낸다.
사용: python docs/probes/caption_foreign_char_scan.py
"""
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common  # noqa: E402

OUT = ROOT / "docs/probes/_scratch/caption_foreign_char_scan.json"
HANGUL = (("가", "힣"), ("ᄀ", "ᇿ"), ("㄰", "㆏"))
SCRIPT_KEYS = ("CJK", "KATAKANA", "HIRAGANA", "CYRILLIC", "LATIN", "THAI",
               "ARABIC", "DEVANAGARI", "GREEK", "HEBREW")


def is_hangul(c: str) -> bool:
    return any(a <= c <= b for a, b in HANGUL)


def foreign_letters(text: str) -> list:
    """한글도 ASCII도 아닌 '글자'만. 기호·숫자·문장부호·이모지 제외."""
    return [c for c in text if c.isalpha() and not c.isascii() and not is_hangul(c)]


def script_of(c: str) -> str:
    try:
        n = unicodedata.name(c)
    except ValueError:
        return "UNKNOWN"
    for k in SCRIPT_KEYS:
        if n.startswith(k) or (" " + k) in n:
            return {"KATAKANA": "KANA", "HIRAGANA": "KANA"}.get(k, k)
    return n.split()[0]


def scan(work_dir: Path, label: str) -> dict:
    per_video, total, cur_n, new_items = {}, 0, 0, []
    for vd in sorted(work_dir.iterdir()):
        seg = vd / "segments.json"
        if not seg.is_file():
            continue
        caps = [(s.get("caption") or "")
                for s in json.loads(seg.read_text(encoding="utf-8"))["segments"]]
        cur = [c for c in caps if common.is_corrupted_caption(c)]
        new = [c for c in caps if foreign_letters(c) and not common.is_corrupted_caption(c)]
        per_video[vd.name] = {"captions": len(caps), "current_rule_hits": len(cur),
                              "newly_flagged": len(new)}
        total += len(caps)
        cur_n += len(cur)
        new_items.extend(new)

    ch, buckets = Counter(), Counter()
    for t in new_items:
        f = foreign_letters(t)
        for c in f:
            ch[c] += 1
        scripts = {script_of(c) for c in f}
        buckets["CJK/KANA만" if scripts <= {"CJK", "KANA"} else "+".join(sorted(scripts))] += 1

    return {
        "label": label,
        "work_dir": str(work_dir.relative_to(ROOT)).replace("\\", "/"),
        "n_videos": len(per_video),
        "n_captions": total,
        "current_rule_hits": cur_n,
        "newly_flagged": len(new_items),
        "newly_flagged_ratio": round(len(new_items) / max(total, 1), 4),
        "script_buckets": dict(buckets.most_common()),
        "top_chars": [{"char": c, "n": n,
                       "name": (unicodedata.name(c, "?"))} for c, n in ch.most_common(15)],
        "samples_truncated": [t[:120] for t in new_items[:3]],
        "per_video": per_video,
    }


def main() -> None:
    res = {
        "note": "측정 전용. is_corrupted_caption과 인덱스를 바꾸지 않는다.",
        "decision_2026_08_25": "A — 기록만. 검출기 확장·재캡셔닝·재색인 없음.",
        "current_rule": "한자·가나 절대 3자 이상 또는 비율 20% 초과 (common.is_corrupted_caption)",
        "hypothetical_rule": "한글·ASCII 외 글자(str.isalpha)가 1자 이상이면 오염",
        "scans": [],
    }
    for wd, label in ((ROOT / "work", "배포 인덱스"), (ROOT / "work_aihub", "AI Hub")):
        if wd.is_dir():
            res["scans"].append(scan(wd, label))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote %s" % OUT)
    for s in res["scans"]:
        print("  %-12s captions %5d · 현행 %3d · 가상 신규 %3d (%.2f%%)"
              % (s["label"], s["n_captions"], s["current_rule_hits"],
                 s["newly_flagged"], 100 * s["newly_flagged_ratio"]))


if __name__ == "__main__":
    main()

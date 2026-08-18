"""I1 B단계 시트 — 캡션을 처음 보여주고 drift 여부를 가른다.

사전등록: `I1검증셋_사전등록_2026-08-18.md` · `보충_B단계경계_2026-08-18.md` ·
`보충2_B단계_C0생략_2026-08-18.md`.

**B에서 새로 보이는 것은 캡션 문자열 하나다.** arm명·I1 판정·셀 이름·검색 순위·
A 라벨은 계속 숨긴다 — 캡션을 본 상태에서 그것들이 보이면 A가 막으려던 편향이
그대로 들어온다. 그리고 **"화면에 글자가 있었는가"를 다시 묻지 않는다.** A가 답했다.

대상(보충2):

    (가) A == cjk_text_present 이고 캡션에 CJK가 있는 인스턴스 전부
    (나) I1a 음성 · 셀 C2 표본 전부

C0은 human label을 생략한다 — 캡션 CJK가 0이면 도출 규칙상 CJK drift가 될 수 없다.
**분모에서 빼는 것이 아니다**: `true_cjk_drift=false`를 파생값으로 남기고 모집단·
가중치는 유지한다(`derived_negatives`).
"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "label_kit" / "i1_frames"
LABELS = ("matches_screen", "drift_despite_text", "drift_no_text", "unclear")
PREREG = ("docs/preregistration/I1검증셋_사전등록_2026-08-18.md + "
          "보충_B단계경계_2026-08-18.md + 보충2_B단계_C0생략_2026-08-18.md")


class SheetError(RuntimeError):
    pass


def load(kit=None) -> tuple:
    kit = Path(kit or KIT)
    man = json.loads((kit / "manifest.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader(
        (kit / "labels.csv").read_text(encoding="utf-8-sig").splitlines()))
    lab = {r["sample_id"]: (r.get("label") or "").strip() for r in rows}
    return man, lab


def targets(man: dict, lab: dict) -> list:
    """B human-label 대상. **순서는 sample_id 정렬로 고정**한다."""
    out = []
    for inst in man["instances"]:
        sid = inst["sample_id"]
        a = lab.get(sid, "")
        ga = a == "cjk_text_present" and inst["cjk_count"] > 0
        na = (not inst["i1a_hit"]) and inst["cell"] == "C2"
        if ga or na:
            out.append(inst)
    return sorted(out, key=lambda x: x["sample_id"])


def derived_negatives(man: dict) -> list:
    """C0 — 사람이 보지 않지만 **분모에는 남는다.** 파생값임을 명시한다."""
    return [{"sample_id": i["sample_id"], "cell": i["cell"],
             "caption_cjk_count": i["cjk_count"],
             "true_cjk_drift": False, "human_labeled": False,
             "basis": "caption_cjk_count == 0"}
            for i in sorted(man["instances"], key=lambda x: x["sample_id"])
            if i["cell"] == "C0" and i["cjk_count"] == 0]


def _mmss(sec: float) -> str:
    return f"{int(sec) // 60:02d}:{int(sec) % 60:02d}"


def build(kit=None, out_dir=None) -> Path:
    kit = Path(kit or KIT)
    man, lab = load(kit)
    blank = [i["sample_id"] for i in man["instances"]
             if not lab.get(i["sample_id"])]
    if blank:
        raise SheetError(
            f"A 라벨이 비어 있다({len(blank)}건, 예: {blank[:3]}) — A를 전부 끝내고 "
            f"확정한 뒤 B를 시작한다")
    tg = targets(man, lab)
    dn = derived_negatives(man)
    out = Path(out_dir or (kit.parent / "i1_stage_b"))
    out.mkdir(parents=True, exist_ok=True)

    lines = [
        "# I1 B단계 — 캡션의 외국어가 화면 글자에서 온 것인가",
        "",
        f"**{len(tg)}건.** 프레임은 `../i1_frames/full/<번호>.jpg`.",
        "",
        "각 항목에서 **프레임과 캡션을 같이 보고** 아래 넷 중 하나를 고른다.",
        "",
        "| 라벨 | 뜻 |",
        "|---|---|",
        "| `matches_screen` | 캡션의 외국어가 **화면에 보이는 글자와 대응**한다 |",
        "| `drift_despite_text` | 화면에 글자는 있으나 캡션 외국어는 **그것과 무관**하다 |",
        "| `drift_no_text` | 화면에 **해당 글자가 없다** |",
        "| `unclear` | 판단 불가 |",
        "",
        "> **캡션에 외국어(한자·가나 등)가 없으면 `drift_no_text`가 아니라 "
        "`unclear`가 아니다** — 그런 항목은 여기 없다. 전부 캡션에 외국어가 있거나 "
        "화면에 외국어가 있는 경우다.",
        "",
        "규칙 두 개.",
        "",
        "- **추측하지 마라.** 애매하면 `unclear`.",
        f"- **{len(tg)}건을 전부 끝내기 전에는 중간 분석을 돌리지 않는다.**",
        "",
        f"입력: `labels_b.csv`의 `label_b` 열. 사전등록: {PREREG}",
        "",
        "---",
        "",
    ]
    for i, inst in enumerate(tg, 1):
        lines += [f"## {i}. `{inst['sample_id']}`  ({_mmss(inst['start'])}"
                  f"~{_mmss(inst['end'])})",
                  "",
                  f"![{inst['sample_id']}](../i1_frames/full/{inst['sample_id']}.jpg)",
                  "",
                  "캡션:",
                  "",
                  f"> {inst['caption']}",
                  "", ""]
    (out / "sheet_b.md").write_text("\n".join(lines), encoding="utf-8")

    with open(out / "labels_b.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sample_id", "label_b"])
        for inst in tg:
            w.writerow([inst["sample_id"], ""])

    a_sha = hashlib.sha256(
        (kit / "labels.csv").read_bytes()).hexdigest()
    mpath = out / "manifest_b.json"
    mpath.write_text(json.dumps(
        {"stage": "B", "prereg": PREREG,
         "n_targets": len(tg), "targets": [i["sample_id"] for i in tg],
         "derived_negatives": len(dn), "derived_negative_rows": dn,
         "labels": list(LABELS),
         # A는 B 시작 시점에 동결한다 — 나중에 수정됐는지 이 해시로 대조한다
         "a_labels_sha256": a_sha,
         "hidden_from_sheet": ["arm", "i1a_hit", "cell", "search_rank", "a_label"],
         "note": ("C0은 human label 생략(보충2). 분모에서 제외하는 것이 아니라 "
                  "true_cjk_drift=false를 파생값으로 둔다")},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return mpath


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    m = build(a.kit, a.out)
    d = json.loads(m.read_text(encoding="utf-8"))
    print(f"대상 {d['n_targets']}건 · 파생 음성 {d['derived_negatives']}건")
    print(f"시트: {m.parent / 'sheet_b.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""I1 validation B단계 시트 — 캡션을 처음 보여주고 drift 여부를 가른다.

사전등록: 보충2 §2(라벨 절차) · 보충3 §6 · **보충4 §7**(블라인드 한계).

**대상은 A가 `cjk_text_present`인 것 단독이다.** development 도구
(`scripts/i1_stage_b_sheet.py`)는 `(나) i1a 음성 ∧ 셀 C2 전수`도 대상에 넣지만,
validation의 동결된 도출 규칙(`i1_validation_analysis.true_label`)은 A가
`no_text`·`korean_text_only`면 **B 없이** drift를 확정한다. 넓은 규칙을 그대로
쓰면 쓰이지 않는 B 라벨이 생기고, 나중에 "이 라벨도 있으니 쓰자"는 경로가 열린다.

**완전한 candidate-blind를 주장하지 않는다**(보충4 §7). B의 질문 자체가 캡션의
CJK와 화면 글자의 관계를 묻기 때문에 캡션 노출이 필수고, `fallback`이
`longest_cjk_run >= 2`이므로 캡션에서 후보 발동 여부가 상당 부분 도출된다.
목표는 **avoidable leakage 차단**이다 — arm·셀·현행 적중·후보 발동·**A 라벨**을
가리고, B 시작 시점에 A CSV를 sha256으로 동결한다.

`m5_search`·`m6_evaluate`를 import하지 않는다(CLAUDE.md 절대규칙 3). 읽기 전용 —
work/·results/·config 불변.
"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A_DIR = ROOT / "label_kit" / "i1_validation"
META = ROOT / "label_kit" / "i1_validation_meta"
B_DIR = ROOT / "label_kit" / "i1_validation_b"
LABELS = ("matches_screen", "drift_despite_text", "drift_no_text", "unclear")
PREREG = ("docs/preregistration/I1_detector_보충2_validation표집_2026-08-20.md + "
          "보충3_표집확정_2026-08-20.md + 보충4_판정근거_2026-08-20.md")
# 캡션을 보여주는 순간 후보 발동은 도출 가능하다 — 가릴 수 있는 것만 가린다
HIDDEN = ("arm", "cell", "i1a_hit", "candidate_firing", "a_label",
          "video_id", "cjk_count", "longest_cjk_run", "cjk_ratio")
BLINDNESS_LIMIT = ("B의 질문이 캡션의 외국어와 화면 글자의 관계이므로 캡션 노출이 "
                   "필수다. 동결된 후보가 longest_cjk_run 기반이라 캡션에서 발동 "
                   "여부가 도출된다. **완전한 candidate-blind가 아니다** — "
                   "avoidable leakage만 차단한다")


class SheetError(RuntimeError):
    pass


def load(a_dir=None, meta=None) -> tuple:
    a_dir, meta = Path(a_dir or A_DIR), Path(meta or META)
    man = json.loads((meta / "manifest_v.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader(
        (a_dir / "labels_v.csv").read_text(encoding="utf-8-sig").splitlines()))
    return man, {r["sample_id"]: (r.get("label") or "").strip() for r in rows}


def targets(man: dict, lab: dict) -> list:
    """A == `cjk_text_present` **단독**. 캡션 CJK가 0이면 도출 규칙상 제외된다."""
    out = [i for i in man["instances"]
           if lab.get(i["sample_id"], "") == "cjk_text_present"
           and i["cjk_count"] > 0]
    return sorted(out, key=lambda x: x["sample_id"])


def _mmss(sec: float) -> str:
    return f"{int(sec) // 60:02d}:{int(sec) % 60:02d}"


def _sheet_text(tg: list, a_dir_name: str) -> str:
    lines = [
        "# I1 validation B단계 — 캡션의 외국어가 화면 글자에서 온 것인가",
        "",
        f"**{len(tg)}건.** 프레임 원본은 `../{a_dir_name}/full/<번호>.jpg`.",
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
        "규칙 셋.",
        "",
        "- **화면에 글자가 있었는지를 다시 묻지 않는다.** A단계가 답했다.",
        "- **추측하지 마라.** 애매하면 `unclear`.",
        f"- **{len(tg)}건을 전부 끝내기 전에 분석을 돌리지 않는다. 분석은 1회다.**",
        "",
        f"입력: `../{a_dir_name}/labels_vb.csv`의 `label_b` 열.",
        "",
        f"사전등록: {PREREG}",
        "",
        "---",
        "",
    ]
    for i, inst in enumerate(tg, 1):
        sid = inst["sample_id"]
        lines += [f"## {i}. `{sid}`  ({_mmss(inst['start'])}~"
                  f"{_mmss(inst['end'])})",
                  "",
                  f"![{sid}](../{a_dir_name}/full/{sid}.jpg)",
                  "",
                  "캡션:",
                  "",
                  f"> {inst['caption']}",
                  "", ""]
    return "\n".join(lines)


def build(a_dir=None, meta=None, out_dir=None) -> Path:
    """B 시트를 만든다. **A 라벨 디렉터리 밖에 쓴다.**

    A용 누출 검사가 `label_kit/i1_validation/`의 텍스트 파일을 전수 훑기 때문에,
    캡션이 들어간 시트를 그 안에 두면 검사가 깨진다. 다만 **빈 라벨 CSV는**
    동결된 분석 코드가 읽는 경로(`i1_validation/labels_vb.csv`)에 둔다.
    """
    a_dir = Path(a_dir or A_DIR)
    man, lab = load(a_dir, meta)
    blank = [i["sample_id"] for i in man["instances"]
             if not lab.get(i["sample_id"])]
    if blank:
        raise SheetError(
            f"A 라벨이 비어 있다({len(blank)}건, 예: {blank[:3]}) — A를 전부 끝내고 "
            "동결한 뒤 B를 시작한다")
    tg = targets(man, lab)
    out = Path(out_dir or B_DIR)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sheet_b.md").write_text(_sheet_text(tg, a_dir.name),
                                    encoding="utf-8")

    lpath = a_dir / "labels_vb.csv"
    if not lpath.exists():                      # 이미 쓴 라벨을 덮어쓰지 않는다
        with open(lpath, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["sample_id", "label_b"])
            for inst in tg:
                w.writerow([inst["sample_id"], ""])

    mpath = out / "manifest_vb.json"
    mpath.write_text(json.dumps({
        "stage": "validation_B",
        "prereg": PREREG,
        "target_rule": "A == cjk_text_present AND caption_cjk_count > 0",
        "target_rule_note": ("development 도구의 (나) i1a 음성 ∧ C2 전수는 "
                             "쓰지 않는다 — validation 도출 규칙이 그 항목에 B를 "
                             "요구하지 않는다"),
        "n_targets": len(tg),
        "targets": [i["sample_id"] for i in tg],
        "labels": list(LABELS),
        # A는 B 시작 시점에 동결한다 — 캡션을 본 뒤 A를 고치는 경로를 막는다
        "a_labels_sha256": hashlib.sha256(
            (a_dir / "labels_v.csv").read_bytes()).hexdigest(),
        "hidden_from_sheet": list(HIDDEN),
        "candidate_blind": False,
        "blindness_limit": BLINDNESS_LIMIT,
        "label_file": str(lpath.relative_to(ROOT)) if ROOT in lpath.parents
                      else lpath.name,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return mpath


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a-dir", default=None)
    ap.add_argument("--meta", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    m = build(a.a_dir, a.meta, a.out)
    d = json.loads(m.read_text(encoding="utf-8"))
    print(f"B targets: {d['n_targets']}")
    print(f"sheet: {m.parent / 'sheet_b.md'}")
    print(f"labels: {d['label_file']}")
    print(f"a_labels_sha256: {d['a_labels_sha256'][:12]}")
    print("candidate_blind: False (caption exposure is required)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""제2 라벨러 유형 태그 일치도 — 맹검 키트 생성 + Cohen's kappa 채점.

IMPLEMENTATION_GUIDE 9-1(c)는 "2인 이상 라벨링 후 일치율 병기"를 약속했으나
미이행 상태였다(9-1-1). 선택지 B에 따라 **유형 태그(3분류)만** 제2 라벨러가
독립 부여하고 일치도를 낸다. GT 타임스탬프는 프레임 실물 검증이라 재라벨링
대상이 아니다.

**절대 규칙 3 준수** — 라벨러에게 나가는 것은 질의문과 GT 구간 클립뿐이다.
검색 결과·자막 텍스트·캡션·기존 유형 태그를 일절 보여주지 않는다. 그래서
맹검 CSV에는 query_id조차 없다(정답 파일과 육안 대조가 가능해지므로).

지표는 9-1-1에서 **Cohen's kappa 주지표 + percent agreement 병기**로 확정됐다.
단순 일치율은 우연 일치를 보정하지 않아 3분류에서 부풀려진다.

사용:
  python scripts/labeling_agreement.py kit   --split test --out label_kit/
  python scripts/labeling_agreement.py score --kit label_kit/ --filled 채운파일.csv
"""
import argparse
import csv
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402

CATS = ["자막형", "장면형", "복합형"]
GUIDE = """# 질의 유형 태깅 가이드 (제2 라벨러용)

## 할 일

`clips/` 안의 영상 클립을 보고, `labels_blind.csv`의 **유형** 칸에
`자막형` / `장면형` / `복합형` 중 하나를 적는다. 다른 칸은 건드리지 않는다.

각 클립은 그 질의의 정답 구간이다(앞뒤 2초 여유 포함). 파일명 `item_XX`가
CSV의 `item_id`와 대응한다.

## 판정 기준

**질문은 "이 질의를 찾으려면 무엇을 들어야/봐야 하는가"다.** 시스템이 어떻게
찾는지가 아니라, **사람이 이 구간을 알아보는 근거**가 무엇인지로 판단한다.

| 유형 | 기준 |
|---|---|
| **자막형** | 질의 내용이 **말소리(발화)**에 들어 있다. 화면을 안 보고 소리만 들어도 이 구간이라고 알 수 있다. |
| **장면형** | 질의 내용이 **화면**에 있다. 소리를 끄고 봐도 알 수 있고, 발화만으로는 알 수 없다. |
| **복합형** | 발화와 화면 **양쪽이 다 필요**하거나, 양쪽 모두로 알 수 있다. |

경계 사례 처리:
- 화면에 **박힌 글자**(영상 편집 자막·간판)는 **화면**으로 본다 → 장면형 쪽.
- 발화가 있지만 질의가 가리키는 건 화면 속 사물이면 → 장면형.
- 발화 내용과 화면 내용이 각각 질의의 다른 부분을 담당하면 → 복합형.
- 판단이 안 서면 **복합형으로 몰지 말고** 더 결정적인 쪽을 고른다. 그래도
  갈리면 복합형.

## 하지 말 것

- 검색 결과·시스템 출력을 보지 않는다(있어도 열지 않는다).
- 다른 사람의 라벨을 참고하지 않는다.
- 클립 밖의 영상 구간을 찾아보지 않는다.

## 주의 (연구 기록용)

이 가이드는 **원 라벨 작성 후에 문서화**됐다. 원 라벨러가 실제로 쓴 기준을
옮긴 것이지만, 사후 성문화라는 점은 한계로 보고한다.
"""


def cohens_kappa(a, b, cats):
    """Cohen's kappa. 기대 일치가 1이면 정의되지 않으므로 None을 돌려준다."""
    if len(a) != len(b):
        raise ValueError(f"길이 불일치: {len(a)} vs {len(b)}")
    if not a:
        raise ValueError("표본이 비었다")
    unknown = ({x for x in a} | {x for x in b}) - set(cats)
    if unknown:
        raise ValueError(f"정의되지 않은 범주: {sorted(unknown)}")

    n = len(a)
    p_o = percent_agreement(a, b)
    p_e = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    if p_e >= 1.0:
        return None                       # 둘 다 단일 범주 — 1.0을 주면 오보다
    return (p_o - p_e) / (1 - p_e)


def percent_agreement(a, b):
    return sum(x == y for x, y in zip(a, b)) / len(a)


def confusion(a, b, cats):
    """행 = 라벨러1(원 라벨), 열 = 라벨러2."""
    m = {r: {c: 0 for c in cats} for r in cats}
    for x, y in zip(a, b):
        m[x][y] += 1
    return m


def clip_cmd(video, start, end, out, pad=2.0):
    """GT 구간 ±pad를 잘라낸다. 음성 필수 — 자막형 판정의 유일한 근거다.

    `-c copy`를 쓰지 않는다. 스트림 복사는 가장 가까운 키프레임으로 컷이
    밀려서 구간이 수 초 어긋나는데, 라벨러가 판단해야 하는 것이 바로 그
    구간의 내용이라 어긋나면 라벨이 틀어진다.
    """
    ss = max(0.0, start - pad)
    dur = (end + pad) - ss
    return ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(ss),
            "-i", str(video), "-t", str(dur),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", str(out)]


def write_blind_kit(queries, out_dir, seed=42):
    """맹검 CSV + 키맵을 쓴다. 클립은 별도(ffmpeg 필요)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    order = list(queries)
    random.Random(seed).shuffle(order)

    keymap = {f"item_{i:02d}": q["query_id"] for i, q in enumerate(order, 1)}
    (out_dir / "_keymap.json").write_text(
        json.dumps(keymap, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "가이드.md").write_text(GUIDE, encoding="utf-8")

    # utf-8-sig — Excel이 BOM 없는 UTF-8 CSV를 cp949로 읽어 한글을 깨뜨린다.
    with (out_dir / "labels_blind.csv").open("w", encoding="utf-8-sig",
                                             newline="") as f:
        w = csv.DictWriter(f, ["item_id", "질의문", "유형"])
        w.writeheader()
        for iid, q in zip(keymap, order):
            w.writerow({"item_id": iid, "질의문": q["text"], "유형": ""})
    return keymap


def score(gold, keymap_path, filled_path, cats):
    gold_by_id = {q["query_id"]: q["type"] for q in gold}
    keymap = json.loads(Path(keymap_path).read_text(encoding="utf-8"))
    rows = list(csv.DictReader(Path(filled_path).open(encoding="utf-8-sig")))

    a, b, disagree = [], [], []
    for r in rows:
        iid = r["item_id"].strip()
        lab = (r.get("유형") or "").strip()
        if not lab:
            raise ValueError(f"미기입 항목: {iid}")
        qid = keymap[iid]
        a.append(gold_by_id[qid])
        b.append(lab)
        if a[-1] != b[-1]:
            disagree.append({"query_id": qid, "text": r.get("질의문", ""),
                             "labeler1": a[-1], "labeler2": b[-1]})

    missing = set(keymap) - {r["item_id"].strip() for r in rows}
    if missing:
        raise ValueError(f"미기입 항목: {sorted(missing)}")

    k = cohens_kappa(a, b, cats)
    return {"n": len(a),
            "cohens_kappa": None if k is None else round(k, 4),
            "percent_agreement": round(percent_agreement(a, b), 4),
            "confusion_labeler1_rows": confusion(a, b, cats),
            "dist_labeler1": {c: a.count(c) for c in cats},
            "dist_labeler2": {c: b.count(c) for c in cats},
            "disagreements": disagree,
            "note": ("9-1-1 확정: kappa 주지표, percent agreement 병기. "
                     "유형 태그만 재라벨링했고 GT 타임스탬프는 대상이 아니다.")}


def _load(split):
    qs = [json.loads(l) for l in
          (ROOT / "data/queries/queries.jsonl").read_text(encoding="utf-8")
          .splitlines() if l.strip()]
    return [q for q in qs if q["split"] == split]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    k = sub.add_parser("kit", help="맹검 라벨링 키트 생성")
    k.add_argument("--split", default="test")
    k.add_argument("--out", default="label_kit")
    k.add_argument("--pad", type=float, default=2.0)
    k.add_argument("--no-clips", action="store_true")

    s = sub.add_parser("score", help="채운 CSV 채점")
    s.add_argument("--kit", default="label_kit")
    s.add_argument("--filled", required=True)
    s.add_argument("--split", default="test")

    a = ap.parse_args()
    if a.cmd == "kit":
        cfg = common.load_config(str(ROOT / "config.yaml"))
        qs = _load(a.split)
        out = ROOT / a.out
        keymap = write_blind_kit(qs, out, seed=cfg["seed"])
        print(f"질의 {len(qs)}건 -> {out}")
        if not a.no_clips:
            (out / "clips").mkdir(exist_ok=True)
            by_id = {q["query_id"]: q for q in qs}
            for iid, qid in keymap.items():
                q = by_id[qid]
                vid = ROOT / "data/videos" / f"{q['video_id']}.mp4"
                dst = out / "clips" / f"{iid}.mp4"
                subprocess.run(clip_cmd(vid, q["gt_start"], q["gt_end"], dst,
                                        a.pad), check=True)
            print(f"클립 {len(keymap)}개 -> {out/'clips'}")
        print("라벨러에게 줄 것: 가이드.md, labels_blind.csv, clips/")
        print("절대 주지 말 것: _keymap.json")
    else:
        rep = score(_load(a.split), ROOT / a.kit / "_keymap.json",
                    Path(a.filled), CATS)
        p = ROOT / "results" / f"label_agreement_{a.split}.json"
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        print(f"n={rep['n']} kappa={rep['cohens_kappa']} "
              f"일치율={rep['percent_agreement']}")
        print("->", p)


if __name__ == "__main__":
    main()

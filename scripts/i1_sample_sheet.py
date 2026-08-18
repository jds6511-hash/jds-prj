"""I1 검증셋 — 층화 표본 추출 + 블라인드 프레임 컨택트시트 생성.

사전등록: `docs/preregistration/I1검증셋_사전등록_2026-08-18.md`(커밋 `3ab4a8f`,
표본 추출 전). 이 스크립트는 그 문서의 §2~§3만 구현한다.

**무엇을 재려는가.** 현행 `is_corrupted_caption`(I1a)이 실제 language drift를 얼마나
잡고 scene text를 얼마나 잘못 잡는지 — 그걸 재려면 **화면에 글자가 실제로 있는지**를
사람이 프레임으로 확인한 라벨이 있어야 한다. 이 스크립트는 그 라벨을 받기 위한
시트까지만 만든다. **detector 규칙은 만들지 않는다.**

**시트는 완전 블라인드다.** 프레임·시각·`sample_id`만 들어간다. arm명·캡션·I1 판정·
셀 이름·검색 순위·영상 제목은 넣지 않는다. 캡션을 같이 보여주면 **캡션에 적힌
글자를 화면에서 봤다고 믿는 편향**이 생긴다(사전등록 §1).

**프레임은 4 arm에서 동일하다.** 그래서 라벨 1건이 4 arm 전부에 쓰인다 — 중복
프레임은 한 번만 시트에 올린다.

`m5_search`·`m6_evaluate`를 import하지 않는다(CLAUDE.md 3조 — 순위로 항목을 고르면
선정 자체가 오염이다). work/·results/·config 불변. 읽기 전용.

재현: python scripts/i1_sample_sheet.py
"""
import argparse, io, json, random, re, sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402

CAP2X2 = ROOT / "docs/probes/_scratch/aihub_2x2_captions/full_2026-08-17"
ARMS = ["qwen25_3b__P0", "qwen25_3b__P1", "qwen3vl_4b__P0", "qwen3vl_4b__P1"]
OUT = ROOT / "label_kit" / "i1_frames"
CJK = re.compile(r"[一-鿿぀-ヿ]")          # 현행 detector와 동일 정규식

# 사전등록 §2 — 셀 정의와 할당. None = 전수.
#
# **이탈 1건: C4를 24 → 전수로 바꿨다.** 사전등록은 C4 할당을 24로 적었으나, 실제
# 모집단이 78건(9,312 중)이라 표집할 이유가 없다. I1a 적중 전체가 82건
# (C1 1 + C3 0 + C4 78 + C5 3)이고 이것이 **주 추정량(I1a precision)의 모집단
# 전부**다. 전수를 쓰면 표집오차가 0이 된다. 사람 라벨이 아직 하나도 없는 시점의
# 결정이므로 선택 자유도가 생기지 않는다. C2(모집단 800)는 사전등록대로 24 유지.
QUOTA = {"C0": 24, "C1": None, "C2": 24, "C3": None, "C4": None, "C5": None}
COLS, THUMB_W, PAD, LABEL_H, PER_SHEET = 5, 300, 10, 26, 40


def cell_of(text: str) -> str:
    """사전등록 §2 표. 서로 겹치지 않는다."""
    n = len(CJK.findall(text or ""))
    hit = common.is_corrupted_caption(text or "")
    if n == 0:
        return "C1" if hit else "C0"
    if n <= 2:
        return "C3" if hit else "C2"
    return "C4" if n <= 9 else "C5"


def longest_cjk_run(text: str) -> int:
    runs = re.findall(r"[一-鿿぀-ヿ]+", text or "")
    return max((len(r) for r in runs), default=0)


def collect(cfg) -> list[dict]:
    """4 arm × 전 영상 × 전 구간의 캡션 인스턴스. 라벨 대상이 아니라 모집단이다."""
    caps = {a: json.loads((CAP2X2 / f"{a}.json").read_text(encoding="utf-8"))
            for a in ARMS}
    rows = []
    for vid in sorted(caps[ARMS[0]]):
        doc = json.loads((Path(common.work_dir(cfg, vid)) / "segments.json")
                         .read_text(encoding="utf-8"))
        segs = doc["segments"]
        for arm in ARMS:
            arm_caps = caps[arm].get(vid)
            if not arm_caps or len(arm_caps) != len(segs):
                continue
            for i, (s, text) in enumerate(zip(segs, arm_caps)):
                n = len(CJK.findall(text or ""))
                rows.append({"arm": arm, "video_id": vid, "seg_idx": i,
                             "start": s["start"], "end": s["end"],
                             "rep_frame": s["rep_frame"], "caption": text,
                             "cjk_count": n, "cjk_len": len(text or ""),
                             "cjk_ratio": round(n / max(len(text or ""), 1), 4),
                             "longest_cjk_run": longest_cjk_run(text),
                             "i1a_hit": bool(common.is_corrupted_caption(text or "")),
                             "cell": cell_of(text)})
    return rows


def sample(rows: list[dict], seed: int) -> list[dict]:
    """셀별 할당을 arm에 균등 배분하고 셀 안에서는 seed 고정 무작위.
    C5는 최장 CJK 사례를 강제 포함한다(사전등록 §2)."""
    rng = random.Random(seed)
    picked, by_cell = [], {}
    for r in rows:
        by_cell.setdefault(r["cell"], []).append(r)

    for cell, quota in QUOTA.items():
        pool = by_cell.get(cell, [])
        if quota is None:                  # 전수 — arm 균등 배분이 필요 없다
            picked.extend({**r} for r in pool)
            continue
        forced = []
        if cell == "C5" and pool:
            forced = [max(pool, key=lambda r: r["cjk_count"])]
        per_arm = {a: [r for r in pool if r["arm"] == a and r not in forced]
                   for a in ARMS}
        for lst in per_arm.values():
            rng.shuffle(lst)
        take, need = list(forced), quota - len(forced)
        # arm 균등: 라운드로빈으로 하나씩 — 가용이 적은 arm은 자동으로 빠진다
        while need > 0 and any(per_arm.values()):
            for a in ARMS:
                if need <= 0:
                    break
                if per_arm[a]:
                    take.append(per_arm[a].pop())
                    need -= 1
        for r in take:
            picked.append({**r, "cell": cell})
    return picked


def build_sheets(frames: list[dict], cfg) -> list[Path]:
    """프레임 + 시각 + sample_id만. 캡션·arm·판정은 넣지 않는다."""
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for page, i0 in enumerate(range(0, len(frames), PER_SHEET), 1):
        chunk = frames[i0:i0 + PER_SHEET]
        rows = (len(chunk) + COLS - 1) // COLS
        first = Image.open(Path(common.work_dir(cfg, chunk[0]["video_id"]))
                           / chunk[0]["rep_frame"])
        th = int(THUMB_W * first.height / first.width)
        cell_h = th + LABEL_H
        sheet = Image.new("RGB", (COLS * (THUMB_W + PAD) + PAD,
                                  rows * (cell_h + PAD) + PAD), "white")
        draw = ImageDraw.Draw(sheet)
        for k, f in enumerate(chunk):
            x = PAD + (k % COLS) * (THUMB_W + PAD)
            y = PAD + (k // COLS) * (cell_h + PAD)
            im = Image.open(Path(common.work_dir(cfg, f["video_id"])) / f["rep_frame"])
            sheet.paste(im.convert("RGB").resize((THUMB_W, th)), (x, y))
            draw.text((x + 2, y + th + 5),
                      f"{f['sample_id']}   {int(f['start'])//60}:"
                      f"{int(f['start']) % 60:02d}", fill="black")
        p = OUT / f"sheet_{page:02d}.jpg"
        sheet.save(p, quality=90)
        made.append(p)
    return made


def main():
    # import 시점이 아니라 여기서 바꾼다 — 모듈 수준에서 하면 이 파일을 import하는
    # 쪽(pytest capture 등)의 stdout을 망가뜨린다
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_aihub.yaml")
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))
    seed = cfg["seed"]

    rows = collect(cfg)
    pop = Counter(r["cell"] for r in rows)
    picked = sample(rows, seed)

    # 프레임 단위로 중복 제거 — 같은 (영상, 구간)은 4 arm에서 같은 프레임이다
    frames, seen = [], {}
    rng = random.Random(seed)
    for r in picked:
        key = (r["video_id"], r["seg_idx"])
        if key not in seen:
            seen[key] = {"video_id": r["video_id"], "seg_idx": r["seg_idx"],
                         "start": r["start"], "rep_frame": r["rep_frame"]}
            frames.append(seen[key])
    rng.shuffle(frames)                    # 셀·arm 순서가 드러나지 않게
    for i, f in enumerate(frames, 1):
        f["sample_id"] = f"S{i:03d}"
    fid = {(f["video_id"], f["seg_idx"]): f["sample_id"] for f in frames}
    for r in picked:
        r["sample_id"] = fid[(r["video_id"], r["seg_idx"])]

    sheets = build_sheets(frames, cfg)
    # 원본 프레임도 sample_id 이름으로 낸다 — 시트 썸네일(300px)에서는 간판·자막
    # 같은 **작은 화면 글자가 안 읽힌다.** 판정 대상이 바로 그 글자다.
    full = OUT / "full"
    full.mkdir(parents=True, exist_ok=True)
    for f in frames:
        dst = full / f"{f['sample_id']}.jpg"
        if not dst.exists():
            dst.write_bytes((Path(common.work_dir(cfg, f["video_id"]))
                             / f["rep_frame"]).read_bytes())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manifest.json").write_text(json.dumps({
        "prereg": "docs/preregistration/I1검증셋_사전등록_2026-08-18.md",
        "seed": seed, "arms": ARMS, "quota": QUOTA,
        "deviation": "사전등록 §2의 C4 할당 24를 전수로 바꿨다 — 모집단이 78건이고 "
                     "I1a 적중 전체(82건)가 주 추정량의 모집단이라 표집오차를 "
                     "0으로 만드는 편이 낫다. 사람 라벨 생성 전 결정이므로 선택 "
                     "자유도 없음. C2(모집단 800)는 사전등록대로 24 유지.",
        "population_by_cell": dict(sorted(pop.items())),
        "population_total": len(rows),
        "sampled_instances": len(picked), "distinct_frames": len(frames),
        "by_cell_arm": {c: dict(Counter(r["arm"] for r in picked if r["cell"] == c))
                        for c in sorted(QUOTA)},
        "instances": picked}, ensure_ascii=False, indent=2), encoding="utf-8")
    lab = OUT / "labels.csv"
    if not lab.exists():        # 이미 라벨한 파일을 덮어쓰지 않는다
        lab.write_text("sample_id,label\n"
                       + "".join(f"{f['sample_id']},\n" for f in frames),
                       encoding="utf-8")

    print(f"모집단 {len(rows)} 인스턴스 · 셀별 {dict(sorted(pop.items()))}")
    print(f"추출 {len(picked)} 인스턴스 → **라벨할 프레임 {len(frames)}장**")
    for c in sorted(QUOTA):
        got = [r for r in picked if r["cell"] == c]
        print(f"  {c}: 모집단 {pop.get(c, 0):5d} → 추출 {len(got):3d} "
              f"{dict(Counter(r['arm'] for r in got))}")
    print(f"시트 {len(sheets)}장 + 원본 {len(frames)}장(full/): {OUT}")
    print("라벨: labels.csv의 label 칸에 "
          "cjk_text_present / korean_text_only / no_text / unclear 중 하나")
    print("작은 글자가 애매하면 full/<sample_id>.jpg 원본(1920×1080)을 열어 확인")
    print("**manifest.json은 라벨 중 열지 마라** — arm·캡션·I1 판정이 들어 있다")


if __name__ == "__main__":
    main()

"""[프레임 내용 확인 — 사람 맹검 키트 생성 (dev 전용, 채택 아님, 결과 전 커밋)]

**왜 필요한가.** `frame_content_judge.py`가 두 조건 모두 **판정 불가**로 끝났다.
관문을 통과한 판정자가 CLIP 하나뿐이었기 때문이다(생성형 판정자 2개는 하드
네거티브에서 "모르겠으면 2번"으로 쏠려 탈락 — capped 0.000/0.277, full 0.000/0.130).
사전 등록 규칙이 "통과 판정자 2개 미만이면 사람 확인으로 넘긴다"이므로 그 키트다.

판정자 스크립트의 `--human-kit`은 **모델이 갈린 항목**만 내보내도록 돼 있어,
판정 자체가 성립하지 않은 이번 경우에는 0건이 나온다. 그래서 이 스크립트가 필요하다.

**형식은 모델과 동일한 2지선다.** 같은 질의·같은 프레임 쌍을 사람에게도 주므로
사람 결과와 모델 결과가 같은 축에서 비교된다. 우연 수준이 정확히 0.5라 추정할
필요도 없다. 제시 순서는 항목마다 무작위로 뒤집는다.

**사람에게도 관문을 건다.** 사람이라고 무조건 믿지 않는다. 답을 아는 문항을 섞어
넣고, 그걸 못 맞히면 그 사람의 답 전체를 쓰지 않는다.

  A  실패 질의 × (정답 프레임 vs 같은 영상 무작위)   ← 관심 조건 52건
  C  성공 질의 × (정답 프레임 vs 같은 영상 무작위)   ← 양성 대조 12건
  N  다른 영상 질의 × (이 영상 프레임 2장)          ← 하드 네거티브 12건

**사전 등록한 판정 규칙 (결과 보기 전 확정, 2026-08-10).**
  - **사람 관문**: C 정답률 **≥ 0.75** 이고 N에서 특정 번호 쏠림이 **0.35~0.65**
    안이어야 그 사람의 답을 쓴다. 못 넘기면 그 사람 답은 **전량 제외**한다.
    (모델에 적용한 것과 같은 임계값 — 사람이라고 완화하지 않는다)
  - **집계**: 관문 통과자의 A 정답률을 `A/C`로 보정한 값이
    **≥ 0.6이면 (가) 캡션 모델·프롬프트 방향**, **≤ 0.4이면 (나) M2·해상도 방향**,
    그 사이면 **혼재**. `0`(둘 다 아님) 응답 비율도 반드시 병기한다.
  - 결과를 보고 임계값·조건을 바꾸지 않는다.

**해상도는 원본이다.** 사람에게 묻는 질문은 "이 프레임에 내용이 있는가"이고,
그건 M2 대표 프레임 선택의 문제다. 축소로 잃는 부분(max_pixels)은 두 조건 모두
관문을 통과한 CLIP이 따로 답할 수 있으므로 사람 키트에서 분리한다.

**라벨 규칙 준수.** 항목에는 검색 결과·캡션·자막이 들어가지 않는다(절대규칙 3).
정답 위치는 `_keymap.json`에만 있고 작업자는 열지 않는다.

키트는 gitignore 대상(`docs/probes/_scratch/`). work/·results/ 불변, test 미접촉.
재현: python docs/probes/frame_human_kit.py
"""
import csv
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common                                              # noqa: E402
from m5_search import VideoIndex                           # noqa: E402
from m6_evaluate import evaluate                           # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "_scratch"
KIT = OUT / "frame_human_kit_full"
SEED = 42
N_POS, N_NEG = 12, 12          # 양성 대조 / 하드 네거티브 문항 수


def main():
    cfg = common.load_config(str(ROOT / "config.yaml"))
    qs = [json.loads(l) for l in (ROOT / "data/queries/queries.jsonl")
          .read_text(encoding="utf-8").splitlines() if l.strip()]
    dev = [q for q in qs if q["split"] == "dev"]
    vids = sorted({q["video_id"] for q in dev})
    base = {v: VideoIndex.load(cfg, v) for v in vids}
    wdirs = {v: Path(common.work_dir(cfg, v)) for v in vids}

    # 실패/성공 정의는 진단 v1·판정 v2와 동일 — 캡션 단독(α=0.0)에서 1위를 잡았는가
    per_q = evaluate(dev, base, 0.0, cfg)["per_query"]
    rank1 = {r["query_id"]: (r["rank"] == 1) for r in per_q}
    failed = [q for q in dev if not rank1[q["query_id"]]]
    succ = [q for q in dev if rank1[q["query_id"]]]
    print(f"실패 {len(failed)} / 성공 {len(succ)} (dev {len(dev)})", flush=True)

    rng = np.random.default_rng(SEED)

    def pair(q, cross_video, flip):
        """(두 프레임 경로, 정답 위치 1|2|0). cross_video면 정답이 없으므로 0.

        flip은 호출자가 **조건별로 균형 배정**해 넘긴다. 항목마다 무작위로 뒤집으면
        소표본에서 위치가 치우쳐(실측 C가 9:3) "무조건 1번" 응답자가 양성 대조
        관문을 통과할 수 있다.
        """
        v = q["video_id"] if cross_video is None else cross_video
        segs = base[v].segments
        if cross_video is None:
            gt = set(q["gt_seg_idx"])
            gi = q["gt_seg_idx"][0]
            pool = [i for i in range(len(segs)) if i not in gt]
            oi = int(rng.choice(pool))
            paths = [wdirs[v] / segs[gi]["rep_frame"], wdirs[v] / segs[oi]["rep_frame"]]
            gt_pos = 1
        else:
            i, j = rng.choice(len(segs), size=2, replace=False)
            paths = [wdirs[v] / segs[int(i)]["rep_frame"],
                     wdirs[v] / segs[int(j)]["rep_frame"]]
            gt_pos = 0
        if flip:
            paths = paths[::-1]
            if gt_pos:
                gt_pos = 2
        return paths, gt_pos

    def balanced_flips(n):
        """절반은 뒤집고 절반은 그대로. 홀수면 남는 하나만 무작위."""
        f = np.array([True, False] * (n // 2) + ([bool(rng.integers(2))] if n % 2 else []))
        return rng.permutation(f)

    items = []
    for q in failed:
        items.append(("A", q, None))
    for q in rng.choice(succ, size=min(N_POS, len(succ)), replace=False):
        items.append(("C", q, None))
    for q in rng.choice(failed, size=N_NEG, replace=False):
        other = [v for v in vids if v != q["video_id"]]
        items.append(("N", q, str(rng.choice(other))))

    flips = {}                                      # 조건별로 정답 위치를 반반 배정
    for c in "ACN":
        idx = [i for i, (cond, _, _) in enumerate(items) if cond == c]
        flips.update(dict(zip(idx, balanced_flips(len(idx)))))

    order = rng.permutation(len(items))             # 조건이 순서로 드러나지 않게 섞는다
    (KIT / "frames").mkdir(parents=True, exist_ok=True)
    keymap, rows = {}, []
    for n, k in enumerate(order, 1):
        cond, q, cross = items[int(k)]
        paths, gt_pos = pair(q, cross, bool(flips[int(k)]))
        iid = f"item_{n:03d}"
        for j, p in enumerate(paths, 1):
            Image.open(p).convert("RGB").save(KIT / "frames" / f"{iid}_{j}.jpg", quality=95)
        keymap[iid] = {"condition": cond, "query_id": q["query_id"],
                       "gt_position": gt_pos, "cross_video": cross}
        rows.append({"item_id": iid, "질의문": q["text"], "정답": ""})

    (KIT / "_keymap.json").write_text(
        json.dumps(keymap, ensure_ascii=False, indent=2), encoding="utf-8")
    with (KIT / "answers_blind.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, ["item_id", "질의문", "정답"])
        w.writeheader()
        w.writerows(rows)
    (KIT / "가이드.md").write_text(
        "# 프레임 내용 확인 (맹검)\n\n"
        f"총 {len(rows)}문항. 한 문항에 20초 정도, 전체 30분 안팎.\n\n"
        "## 하는 일\n\n"
        "`frames/item_XXX_1.jpg`와 `item_XXX_2.jpg` 두 장을 보고, "
        "`answers_blind.csv`의 **정답** 칸에 질의문 내용이 보이는 사진 번호"
        "(`1` 또는 `2`)를 적는다. **둘 다 아니면 `0`**.\n\n"
        "## 규칙\n\n"
        "- **애매하면 `0`**을 적는다. 억지로 고르지 않는다. 이 문항 집합에는 "
        "정답이 아예 없는 문항이 섞여 있고, 그걸 `0`으로 걸러내는 것도 측정 대상이다.\n"
        "- 검색 결과·캡션·자막을 보지 않는다(절대규칙 3).\n"
        "- `_keymap.json`은 정답표다. **열지 않는다.**\n"
        "- 문항 순서에 규칙은 없다. 앞뒤 문항을 참고하지 않는다.\n"
        "- 중간에 멈춰도 되지만, 한 문항을 다시 돌아가 고치지 않는다.\n",
        encoding="utf-8")

    n_by = {c: sum(1 for v in keymap.values() if v["condition"] == c) for c in "ACN"}
    meta = {"note": "dev-only, 채택 아님. 판정 v2가 판정 불가로 끝나 사람에게 넘긴 키트.",
            "prereg": {"gate": "C 정답률 ≥0.75 이고 N 번호 쏠림 0.35~0.65",
                       "aggregate": "A/C 보정값 ≥0.6 캡션 방향 / ≤0.4 M2·해상도 / 사이 혼재",
                       "resolution": "원본(축소 없음)",
                       "declared_before_run": True},
            "seed": SEED, "n_items": len(rows), "n_by_condition": n_by,
            "path": str(KIT)}
    (OUT / "frame_human_kit_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"키트 {len(rows)}문항 (A {n_by['A']} / C {n_by['C']} / N {n_by['N']}) -> {KIT}")


if __name__ == "__main__":
    main()

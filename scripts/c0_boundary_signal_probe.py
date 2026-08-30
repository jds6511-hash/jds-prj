"""C0 — caption-text embedding 변화 신호 관찰. **관찰 전용이다.**

규격: `V2_1_ARCHITECTURE_SPEC_2026-08-30.md` §5·§25

질문 하나만 본다.

> KURE caption-text embedding distance의 peak가 사람이 보기에 의미 있는
> 화면·내용 변화와 어느 정도 대응하는가.

```
하지 않는다   threshold 결정 · optimal cutoff · minimum gap · smoothing tuning
             provider 채택 · 점수 계산 · GT 대조
```

신호는 **이미지 차이가 아니라 VLM이 무엇을 언어로 보존했는지의 변화**다.
그래서 캡션이 옷 색 수준으로 흔들리면 거리도 흔들린다 — 그것이 이번 관찰 항목이다.

LLM을 부르지 않고 GPU를 쓰지 않는다. 저장된 `emb_cap.npy`만 읽는다.

사용:
    python scripts/c0_boundary_signal_probe.py --out runs/c0/
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common                                                       # noqa: E402

# 관찰 구간 — 진단에서 이미 LLM 경계가 있는 곳 + caption-dominant 대조 1구간
WINDOWS = [("wonyi_geoje", "chunk3", 110, 169),
           ("wonyi_geoje", "chunk5", 220, 279),
           ("m8c2_3I7oGwk6EaQ", "seg000_059", 0, 59)]

DIAG = ROOT / "runs/model_diag/geoje_boundary_degeneracy.json"
BCS_3I7 = ROOT / "runs/bcs/bcs_v0_reparsed/m8c2_3I7oGwk6EaQ.json"

# 외형 어휘 — 캡션 요동이 peak를 만드는지 보기 위한 **관찰용 표지**다.
# 판정에 쓰지 않는다.
APPEARANCE = re.compile(
    r"분홍|핑크|파란|푸른|파랑|초록|녹색|검은|검정|흰|하얀|노란|빨간|보라|회색|"
    r"티셔츠|모자|드레스|반팔|상의|옷|머리카락|금발|스웨터|바지|치마")


def adjacent_distance(emb: np.ndarray) -> np.ndarray:
    """`d[i]` = seg i-1 → i 의 코사인 거리. L2 정규화 전제(meta에서 확인)."""
    d = np.zeros(len(emb), dtype=np.float64)
    d[1:] = 1.0 - np.sum(emb[1:] * emb[:-1], axis=1)
    return d


def percentile_rank(values: np.ndarray, idx) -> float:
    """영상 전체 분포에서의 백분위. **절대 임계를 쓰지 않기 위한 표현이다.**"""
    v = values[1:]                       # d[0]은 정의상 0 — 분포에서 뺀다
    return float((v < values[idx]).sum()) / max(len(v), 1)


def local_peaks(d: np.ndarray, lo: int, hi: int, radius: int = 2) -> list:
    """국소 최대. 임계가 아니라 **모양**으로만 뽑는다(cutoff 없음)."""
    out = []
    for i in range(max(lo, 1), hi + 1):
        a, b = max(1, i - radius), min(len(d) - 1, i + radius)
        if d[i] == d[a:b + 1].max() and d[i] > 0:
            out.append(i)
    return out


def llm_boundaries() -> dict:
    """이미 저장된 LLM 경계. 새로 생성하지 않는다."""
    out = {}
    diag = json.loads(DIAG.read_text(encoding="utf-8"))
    for arm, key in (("qwen_full", "current/full"),
                     ("qwen_caption_only", "current/caption_only"),
                     ("kanana_full", "comparison/full"),
                     ("kanana_caption_only", "comparison/caption_only")):
        for ch in ("chunk3", "chunk5"):
            out.setdefault(("wonyi_geoje", ch), {})[arm] = \
                diag["arms"][f"{key}/{ch}"]["boundaries"]
    bcs = json.loads(BCS_3I7.read_text(encoding="utf-8"))
    out[("m8c2_3I7oGwk6EaQ", "seg000_059")] = {
        "bcs_qwen_caption_only": [e["start_seg"] for e in bcs["episodes"]
                                  if 0 <= e["start_seg"] <= 59]}
    return out


def probe(vid: str, name: str, lo: int, hi: int, segs: list, emb: np.ndarray,
          bounds: dict) -> dict:
    d = adjacent_distance(emb)
    peaks = local_peaks(d, lo, hi)
    caps = [(s.get("caption") or "").strip() for s in segs]

    def app_only(i: int) -> bool:
        """앞뒤 캡션의 차이가 외형 어휘에만 있는가 — 관찰 표지."""
        if i <= 0:
            return False
        words = lambda t: set(re.findall(r"[가-힣]{2,}", t))       # noqa: E731
        diff = words(caps[i]) ^ words(caps[i - 1])
        return bool(diff) and all(APPEARANCE.search(x) for x in diff)

    win = d[lo:hi + 1]
    res = {"video_id": vid, "window": name, "lo": lo, "hi": hi,
           "distance": {"mean": round(float(win.mean()), 4),
                        "min": round(float(win.min()), 4),
                        "max": round(float(win.max()), 4),
                        "p50": round(float(np.percentile(win, 50)), 4),
                        "p90": round(float(np.percentile(win, 90)), 4)},
           "n_local_peaks": len(peaks),
           "peaks": [{"seg": int(i), "distance": round(float(d[i]), 4),
                      "pct_rank": round(percentile_rank(d, i), 3),
                      "appearance_only_diff": app_only(i),
                      "caption_prev": caps[i - 1][:70],
                      "caption_here": caps[i][:70]}
                     for i in sorted(peaks, key=lambda x: -d[x])[:10]],
           "llm_boundaries": {}}

    for arm, bs in bounds.items():
        inb = [b for b in bs if lo <= b <= hi and b > 0]
        ranks = [percentile_rank(d, b) for b in inb]
        onpeak = sum(1 for b in inb if b in set(peaks))
        res["llm_boundaries"][arm] = {
            "n": len(bs), "n_in_window": len(inb),
            "median_pct_rank": round(float(np.median(ranks)), 3) if ranks else None,
            "on_local_peak": onpeak,
            "on_local_peak_share": round(onpeak / len(inb), 3) if inb else None}
    return res


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default=str(ROOT / "runs/c0"))
    a = ap.parse_args()
    cfg = common.load_config(str(ROOT / a.config))
    bounds = llm_boundaries()

    out = {"purpose": "C0 관찰 — caption-text embedding 변화 신호",
           "spec": "docs/finalization/V2_1_ARCHITECTURE_SPEC_2026-08-30.md",
           "not_done": ["threshold", "optimal_cutoff", "minimum_gap",
                        "smoothing_tuning", "provider_adoption", "GT_대조"],
           "embedding_model": None, "windows": []}

    for vid, name, lo, hi in WINDOWS:
        wdir = Path(common.work_dir(cfg, vid))
        meta = json.loads((wdir / "meta.json").read_text(encoding="utf-8"))
        out["embedding_model"] = meta.get("embed_model")
        segs = common.load_segments(wdir / "segments.json",
                                    require=["subtitle", "caption"],
                                    seg_len=cfg["seg_len_sec"])["segments"]
        emb = np.load(wdir / "emb_cap.npy")
        if len(emb) != len(segs):
            raise SystemExit(f"{vid}: emb {len(emb)} vs segs {len(segs)}")
        out["windows"].append(
            probe(vid, name, lo, hi, segs, emb, bounds.get((vid, name), {})))

    p = Path(a.out) / "c0_boundary_signal.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    common.atomic_write_json(p, out)

    print(f"임베딩 {out['embedding_model']} · LLM 미호출 · GPU 미사용")
    for w in out["windows"]:
        print(f"\n=== {w['video_id']} {w['window']} seg#{w['lo']}~{w['hi']}")
        dd = w["distance"]
        print(f"인접거리  mean {dd['mean']} · p50 {dd['p50']} · p90 {dd['p90']} · "
              f"max {dd['max']} · 국소peak {w['n_local_peaks']}")
        for arm, m in w["llm_boundaries"].items():
            print(f"  {arm:<24} 창 안 {m['n_in_window']:>3}개 · "
                  f"거리 백분위 중앙 {m['median_pct_rank']} · "
                  f"peak 위 {m['on_local_peak']} ({m['on_local_peak_share']})")
        print("  상위 peak")
        for pk in w["peaks"][:5]:
            flag = " [외형어휘차이만]" if pk["appearance_only_diff"] else ""
            print(f"    seg#{pk['seg']} d={pk['distance']} "
                  f"pct={pk['pct_rank']}{flag}")
            print(f"       이전: {pk['caption_prev']}")
            print(f"       현재: {pk['caption_here']}")
    print(f"\n산출물: {p}")
    print("관찰 전용 — 임계·채택 판단 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

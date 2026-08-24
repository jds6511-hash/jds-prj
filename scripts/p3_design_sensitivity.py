"""P3 설계 민감도 — **정밀도 목표 ↔ 필요한 라벨 행 수**를 outcome-blind로 계산한다.

라벨 비용이 P2를 멈춰 세웠으므로, P3에서는 `k=몇 · m=몇`을 먼저 찍는 대신 **각 정밀도가
얼마의 라벨을 요구하는지**를 보고 결정한다. 이 모듈은 그 표만 만든다.

```
쓰는 자료   과거 진단 자료 하나뿐 — AI Hub 2×2 full(1,086질의 · 194 cluster)
채널        rr_fus(α=0.5) = P3 PRIMARY 채널 · rr_cap(α=0.0) = 필수 key secondary 채널
산식        half-width = Z·sqrt((σ²_b + σ²_w/m)/k)  →  k = ceil(Z²(σ²_b + σ²_w/m)/hw²)
안 하는 것   설계 자동 선택 · P2의 0.04 자동 승계 · P3 자료 생성·열람
```

**ICC=0이면 총 행 수가 m과 무관하다.** 관측 ICC가 두 채널 모두 0이면 "영상을 몇 편
모으는가"는 라벨 총량이 아니라 수집 비용·외부 타당성의 문제가 된다. ICC>0을 가정하면
m이 작은 설계가 총 행 수에서 유리해지고 대신 영상이 더 필요하다 — 그 교환을 표에 같이
낸다.

재현:
  python scripts/p3_design_sensitivity.py --out docs/P3_설계민감도_2026-08-24.json
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import p2_sample_size_sensitivity as S                             # noqa: E402

AIHUB = S.AIHUB
BASE_KEY, CAND_KEY = S.BASE_KEY, S.CAND_KEY
Z95 = S.Z95

# P3 PRIMARY는 배포 구성(융합 α=0.5), key secondary는 채널 격리(α=0.0)
CHANNELS = {"rr_fus_alpha_0_5": "rr_fus", "rr_cap_alpha_0_0": "rr_cap"}
PRIMARY_CHANNEL = "rr_fus_alpha_0_5"
SECONDARY_CHANNEL = "rr_cap_alpha_0_0"

TARGETS = (0.04, 0.05, 0.06)
M_GRID = (3, 4, 5, 6, 9)
ICC_GRID = (0.0, 0.03, 0.10, 0.25)
# cluster가 이보다 적으면 bootstrap을 추론으로 쓰지 않는다(보충2 §4-2 계열 규칙)
MIN_CLUSTERS_FOR_INFERENCE = 16
P2_HALF_WIDTH_TARGET = 0.04

LIMITATIONS = (
    "AI Hub 후보 풀은 영상당 12구간이고 P3는 장편(영상당 약 150~400구간)이다 — "
    "RR 분포의 스케일이 달라 절대 half-width·분산 성분을 P3로 그대로 옮길 수 없다",
    "AI Hub 2×2 arm은 bf16이고 P3는 양 arm 4bit(배포 경로 정밀도)다 — 생성 정밀도가 "
    "다르다",
    "AI Hub 1,086질의는 모델 확증에 이미 쓴 재사용 표본이다 — fresh evidence가 아니고 "
    "여기서는 분산 구조 진단에만 쓴다",
    "도메인이 다르다(AI Hub 드라마·여행·요리 vs 배포 다큐·리뷰 계열). 질의 유형 라벨도 "
    "AI Hub에는 없다",
    "정규근사이고 balanced 설계를 가정한다 — paired cluster bootstrap의 percentile CI와 "
    "정확히 같지 않다",
    "ICC 훑기는 가정값이고 추정이 아니다. 관측 ICC가 0이어도 장편에서 0이라는 뜻은 아니다",
    "이 표는 P3의 실제 half-width를 예측하지 않는다. 정밀도 목표별 라벨 부담의 크기를 "
    "가늠하는 계획 보조 자료다",
    "질의 유형별 이질 분산·영상×유형 상호작용·후보 풀 크기 의존성은 이 일원 모형에 들어 "
    "있지 않다",
)


class DesignError(Exception):
    pass


def paired_deltas(channel_field: str, source=AIHUB) -> list:
    """질의별 짝지은 Δ. **채널을 인자로 받는다** — 융합·캡션 둘 다 재기 위해서다."""
    doc = json.loads(Path(source).read_text(encoding="utf-8"))
    pq = doc.get("per_query") or {}
    for key in (BASE_KEY, CAND_KEY):
        if key not in pq:
            raise DesignError(f"{key} arm이 자료에 없다")
    a, b = pq[BASE_KEY], pq[CAND_KEY]
    if len(a) != len(b):
        raise DesignError(f"두 arm 길이가 다르다 {len(a)} vs {len(b)}")
    out = []
    for ra, rb in zip(a, b):
        if ra["query_id"] != rb["query_id"]:
            raise DesignError(f"질의 순서가 다르다: {ra['query_id']} vs "
                              f"{rb['query_id']}")
        if channel_field not in ra or channel_field not in rb:
            raise DesignError(f"채널 {channel_field}가 자료에 없다")
        out.append({"query_id": ra["query_id"], "video_id": ra["video_id"],
                    "delta": float(rb[channel_field]) -
                             float(ra[channel_field])})
    return out


def required_k(half_width: float, m: int, sigma2_between: float,
               sigma2_within: float) -> int:
    """목표 half-width를 만족하는 최소 cluster 수."""
    if not half_width > 0:
        raise DesignError(f"half-width 목표가 양수가 아니다: {half_width}")
    if not isinstance(m, int) or m < 1:
        raise DesignError(f"queries/video가 1 이상 정수가 아니다: {m}")
    var = sigma2_between + sigma2_within / m
    return int(math.ceil(Z95 ** 2 * var / half_width ** 2))


def design_table(sigma2_between: float, sigma2_within: float,
                 targets=TARGETS, grid=M_GRID) -> list:
    """(목표 half-width × queries/video) → 필요한 영상 수와 총 라벨 행 수."""
    rows = []
    for hw in targets:
        for m in sorted(grid):
            k = required_k(hw, m, sigma2_between, sigma2_within)
            rows.append({
                "half_width_target": hw,
                "queries_per_video": m,
                "video_clusters": k,
                "total_gt_rows": k * m,
                "achieved_half_width": round(
                    S.projected_half_width(sigma2_between, sigma2_within, k, m),
                    4),
                "cluster_warning": (
                    f"cluster {k} < {MIN_CLUSTERS_FOR_INFERENCE} — 이 규모는 "
                    f"기술 통계로만 보고한다"
                    if k < MIN_CLUSTERS_FOR_INFERENCE else None),
            })
    return rows


def icc_table(total_variance: float, targets=TARGETS, grid=M_GRID,
              scenarios=ICC_GRID) -> list:
    """ICC를 가정값으로 훑는다 — m 선택의 이득이 ICC에 얼마나 의존하는지 보인다."""
    out = []
    for icc in scenarios:
        s2b = total_variance * icc
        s2w = total_variance * (1.0 - icc)
        out.append({"assumed_icc": icc,
                    "total_gt_rows": {
                        str(hw): {m: required_k(hw, m, s2b, s2w) * m
                                  for m in sorted(grid)} for hw in targets},
                    "video_clusters": {
                        str(hw): {m: required_k(hw, m, s2b, s2w)
                                  for m in sorted(grid)} for hw in targets}})
    return out


def channel_report(name: str, field: str, source=AIHUB) -> dict:
    deltas = paired_deltas(field, source)
    dec = S.decompose(deltas)
    total = dec["sigma2_between"] + dec["sigma2_within"]
    return {
        "channel": name, "field": field,
        "variance_decomposition": {
            "n": dec["n"], "k": dec["k"],
            "sigma2_between": round(dec["sigma2_between"], 6),
            "sigma2_within": round(dec["sigma2_within"], 6),
            "icc": round(dec["icc"], 4),
            "queries_per_cluster_observed": dec["queries_per_cluster_observed"],
        },
        "design_table": design_table(dec["sigma2_between"],
                                     dec["sigma2_within"]),
        "icc_scenarios": icc_table(total),
        "icc_scenarios_note": ("가정값 훑기이고 추정이 아니다. ICC가 크면 m이 작은 "
                               "설계가 총 행 수에서 유리해지고 대신 영상이 더 "
                               "필요하다 — 라벨 비용과 수집 비용의 교환이다"),
        "total_rows_invariant_in_m": dec["icc"] == 0.0,
    }


def report(source=AIHUB) -> dict:
    chans = {name: channel_report(name, field, source)
             for name, field in CHANNELS.items()}
    return {
        "probe": "p3_design_sensitivity",
        "question": ("정밀도 목표별로 필요한 video cluster 수 · queries/video · "
                     "총 GT 행 수"),
        "primary_channel": PRIMARY_CHANNEL,
        "key_secondary_channel": SECONDARY_CHANNEL,
        "channels": chans,
        "targets": list(TARGETS),
        "m_grid": list(M_GRID),
        "p2_half_width_target": P2_HALF_WIDTH_TARGET,
        "p2_target_auto_inherited": False,
        "p2_target_note": ("0.04는 P2의 규칙이다. P3에 자동 승계하지 않고 비교 후보로만 "
                           "넣는다. 비용을 보고 목표를 낮추는 것이 아니라, 각 목표가 "
                           "어떤 결론을 허용하는지와 라벨 부담을 함께 보고 사전 "
                           "결정한다"),
        "min_clusters_for_inference": MIN_CLUSTERS_FOR_INFERENCE,
        "reused_conventions": {
            "bootstrap_B": {"value": 2000,
                            "source": ("docs/preregistration/부호역전_확증_보충2_"
                                       "P2설계_2026-08-20.md §2 · AI Hub 2×2 "
                                       "산출물 bootstrap_B")},
            "cluster_unit": {"value": "video",
                             "source": "보충2 §2 (paired video-cluster)"},
            "estimator": {"value": "paired video-cluster bootstrap",
                          "source": "보충2 §2"},
        },
        "bootstrap_seed": "prereg_freeze_시_결정",
        "bootstrap_seed_note": ("결과와 무관하게 사전등록 동결 시점에 결정론적으로 "
                                "고정하고 기록한다. 지금 임의의 숫자를 발명하지 않는다"),
        "noninferiority_margin_delta": "P3-C 미선택 — defer",
        "historical_source": str(Path(source).relative_to(ROOT)).replace(
            "\\", "/") if Path(source).is_relative_to(ROOT) else str(source),
        "sample_reuse_note": ("이 표본은 모델 확증에 이미 썼다. 여기서는 분산 구조 "
                             "진단으로만 쓰고, P3의 증거로 세지 않는다"),
        "outcome_access": {"p3_data_generated": False, "p3_outcome_opened": False,
                           "p2_outcome_opened": False},
        "auto_selection": False,
        "decision": "사용자_승인_사항",
        "limitations": list(LIMITATIONS),
    }


def _fmt(r: dict) -> str:
    lines = []
    for name in (PRIMARY_CHANNEL, SECONDARY_CHANNEL):
        ch = r["channels"][name]
        v = ch["variance_decomposition"]
        lines.append(f"[{name}] sigma2_b={v['sigma2_between']} "
                     f"sigma2_w={v['sigma2_within']} ICC={v['icc']} "
                     f"(n={v['n']} k={v['k']})")
        lines.append("  hw     m   clusters  rows   achieved")
        for row in ch["design_table"]:
            warn = " *" if row["cluster_warning"] else ""
            lines.append(f"  {row['half_width_target']:.2f}  "
                         f"{row['queries_per_video']:>2}   "
                         f"{row['video_clusters']:>6}  "
                         f"{row['total_gt_rows']:>5}   "
                         f"{row['achieved_half_width']:.4f}{warn}")
    lines.append("* cluster < 16 — 기술 통계로만 보고")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description="P3 설계 민감도 (outcome-blind). 설계를 고르지 않는다")
    ap.add_argument("--out")
    a = ap.parse_args()
    r = report()
    print(_fmt(r))
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

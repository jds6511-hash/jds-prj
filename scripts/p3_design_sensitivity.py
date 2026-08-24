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

# 0.02는 사용자가 동결한 배포 정책 임계다(2026-08-24). 나머지는 비교 후보로 남긴다.
TARGETS = (0.02, 0.04, 0.05, 0.06)
M_GRID = (3, 4, 5, 6, 9)

# 사용자 결정 · 결과 열람 전 동결(2026-08-24). 숫자를 여기 한 곳에만 둔다.
FROZEN = {"gain": 0.02, "clusters": 300, "m": 5, "driver": "PRIMARY",
          "route": "external_human_annotator"}
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


# 과거 효과 크기 — **endpoint별로 분리해서 적는다.** 캡션 단독 값과 융합 값을 섞으면
# "이 정밀도로 저 효과를 잡는다"는 계산이 틀린다.
HISTORICAL_EFFECTS = {
    "rr_fus_alpha_0_5": (
        {"sample": "aihub", "n_queries": 1086, "delta": 0.0191,
         "ci": "cluster에서 0 배제 · query CI는 0 포함",
         "source": "docs/재분석_2x2_2026-08-18.md §3 (융합 α=0.5, 4B/P0)"},
        {"sample": "dev", "n_queries": 96, "delta": -0.0764,
         "ci": "산술 차이 · CI 미사전등록",
         "source": "docs/작업현황_2026-08-18.md §5-10 (고정 α=0.5 Δ_deploy)"},
    ),
    "rr_cap_alpha_0_0": (
        {"sample": "aihub", "n_queries": 1086, "delta": 0.0310,
         "ci": "[+0.0080, +0.0536] — 0 배제",
         "source": "docs/재분석_2x2_2026-08-18.md §3 (캡션 단독, 4B/P0)"},
        {"sample": "dev", "n_queries": 96, "delta": -0.0903,
         "ci": "[−0.2112, −0.0276] — cluster 3, 진단용만",
         "source": "docs/재분석_부호역전_2026-08-18.md §1"},
    ),
}


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


def min_confirmable_effect(half_width: float) -> float:
    """CI로 0을 배제하려면 |Δ|가 half-width를 넘어야 한다.

    `Δ ± hw`가 0을 건너지 않는 조건이 `|Δ| > hw`다. 그래서 목표 half-width는 곧
    **확증할 수 있는 최소 효과 크기**다 — "hw 0.04면 +0.031도 판정된다"는 틀렸다.
    """
    if not half_width > 0:
        raise DesignError(f"half-width가 양수가 아니다: {half_width}")
    return half_width


def confirmable(delta: float, half_width: float) -> bool:
    return abs(delta) > min_confirmable_effect(half_width)


def rows_for_effect(effect: float, sigma2_between: float,
                    sigma2_within: float, m: int) -> dict:
    """이 크기의 효과를 CI로 확증하려면 몇 행이 필요한가."""
    if not effect:
        raise DesignError("효과 크기가 0이면 필요한 규모가 정의되지 않는다")
    hw = abs(float(effect))
    k = required_k(hw, m, sigma2_between, sigma2_within)
    return {"effect": effect, "required_half_width_below": hw,
            "queries_per_video": m, "video_clusters": k,
            "total_gt_rows": k * m}


def confirmability(channels: dict, targets=TARGETS, m: int = 5) -> list:
    """목표 half-width별로 **과거 효과 크기를 확증할 수 있는지**와, 확증에 필요한 규모."""
    out = []
    for name, ch in channels.items():
        v = ch["variance_decomposition"]
        for eff in HISTORICAL_EFFECTS[name]:
            need = rows_for_effect(eff["delta"], v["sigma2_between"],
                                   v["sigma2_within"], m)
            for hw in targets:
                out.append({
                    "channel": name, "sample": eff["sample"],
                    "delta": eff["delta"], "half_width_target": hw,
                    "confirmable": confirmable(eff["delta"], hw),
                    "min_confirmable_effect_at_target": hw,
                    "queries_per_video": m,
                    "total_gt_rows_to_confirm": need["total_gt_rows"],
                    "video_clusters_to_confirm": need["video_clusters"],
                    "source": eff["source"]})
    return out


def sample_size_options(primary: dict, secondary: dict, targets=TARGETS,
                        grid=M_GRID) -> dict:
    """표본 규모를 무엇이 정하는가 — **두 안을 나란히 낸다.**

    ```
    A  PRIMARY(α=0.5) 정밀도로 N을 정하고, secondary의 달성 half-width를 함께 보고
    B  PRIMARY와 secondary가 **같은** 임계를 만족하도록 N을 키운다
    ```

    α=0.0은 mandatory key secondary이고 **co-primary가 아니다.** 따라서 B를 기본으로
    쓰는 규칙은 현재 승인되지 않았다 — 선택은 사용자 결정이다.
    """
    pv, sv = primary["variance_decomposition"], secondary["variance_decomposition"]
    a, b = [], []
    for hw in targets:
        for m in sorted(grid):
            kp = required_k(hw, m, pv["sigma2_between"], pv["sigma2_within"])
            ks = required_k(hw, m, sv["sigma2_between"], sv["sigma2_within"])
            a.append({
                "half_width_target": hw, "queries_per_video": m,
                "video_clusters": kp, "total_gt_rows": kp * m,
                "primary_achieved_half_width": round(S.projected_half_width(
                    pv["sigma2_between"], pv["sigma2_within"], kp, m), 4),
                "secondary_achieved_half_width": round(S.projected_half_width(
                    sv["sigma2_between"], sv["sigma2_within"], kp, m), 4)})
            kb = max(kp, ks)
            b.append({
                "half_width_target": hw, "queries_per_video": m,
                "video_clusters": kb, "total_gt_rows": kb * m,
                "primary_achieved_half_width": round(S.projected_half_width(
                    pv["sigma2_between"], pv["sigma2_within"], kb, m), 4),
                "secondary_achieved_half_width": round(S.projected_half_width(
                    sv["sigma2_between"], sv["sigma2_within"], kb, m), 4),
                "extra_rows_vs_A": (kb - kp) * m})
    return {"A_primary_driven": a, "B_primary_and_secondary": b}


def icc_robustness(sigma2_between: float, sigma2_within: float,
                   targets=TARGETS, grid=M_GRID, scenarios=ICC_GRID) -> list:
    """ICC=0을 진실로 가정하지 않는다 — 가정이 틀렸을 때 설계가 얼마나 무너지는가.

    두 가지를 같이 낸다.

    ```
    1  가정 ICC에서 목표를 맞추려면 필요한 k · 총 행 수
    2  **ICC=0으로 잡은 설계**를 그 세계에 놓았을 때 실제 half-width
    ```

    2번이 요점이다. m이 크고 영상 수가 적은 설계(예: m=9)는 cluster 의존성이 조금만
    생겨도 크게 나빠진다 — 총 행 수가 같아도 그렇다. **예측이 아니라 설계 강건성
    진단이다.**
    """
    total = sigma2_between + sigma2_within
    out = []
    for icc in scenarios:
        s2b, s2w = total * icc, total * (1.0 - icc)
        for hw in targets:
            for m in sorted(grid):
                k0 = required_k(hw, m, sigma2_between, sigma2_within)
                k1 = required_k(hw, m, s2b, s2w)
                out.append({
                    "assumed_icc": icc, "half_width_target": hw,
                    "queries_per_video": m,
                    "video_clusters_icc0": k0, "total_gt_rows_icc0": k0 * m,
                    "video_clusters_under_assumed_icc": k1,
                    "total_gt_rows_under_assumed_icc": k1 * m,
                    "achieved_half_width_if_icc_true": round(
                        S.projected_half_width(s2b, s2w, k0, m), 4)})
    return out


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
        "icc_robustness": icc_robustness(dec["sigma2_between"],
                                         dec["sigma2_within"]),
        "total_rows_invariant_in_m_at_observed_icc": dec["icc"] == 0.0,
        "total_rows_invariant_note": ("관측 ICC에서만 성립한다. ICC가 0이 아니면 "
                                      "m이 작은 설계가 총 행 수에서 유리하다 — "
                                      "icc_robustness를 함께 보라"),
    }


def frozen_decision(primary: dict, secondary: dict) -> dict:
    """사용자가 결과 열람 전에 동결한 결정 — 최소 가치 효과·정밀도·driver·규모·라벨 경로.

    `+0.02`는 **데이터가 알려준 상수가 아니라 배포 정책 임계**다. 4B가 실제 6GB/4bit
    배포 환경에서 OOM 없이 들어가고 caption wall-clock이 더 짧았으므로 `+0.04~0.06`을
    최소 가치 효과로 요구할 근거가 약해졌다는 운영 판단에서 나왔다. 라벨 부담을 보고
    임계를 올리는 것은 금지된 역방향 결정이다.
    """
    pv = primary["variance_decomposition"]
    sv = secondary["variance_decomposition"]
    hw, k, m = FROZEN["gain"], FROZEN["clusters"], FROZEN["m"]
    k_min = required_k(hw, m, pv["sigma2_between"], pv["sigma2_within"])
    return {
        "decided_at": "2026-08-24",
        "decided_by": "user",
        "decided_before_outcome_access": True,

        "minimum_deployment_relevant_gain": hw,
        "gain_kind": "deployment_policy_threshold",
        "gain_is_measured_constant": False,
        "gain_rationale": ("실제 6GB/4bit 배포 환경에서 4B가 OOM 없이 들어가고 caption "
                           "wall-clock이 더 짧았다. 추가 비용은 VRAM reserved "
                           "+0.431GB · 저장 +1.28GB와 일회성 재생성·검증 절차 수준이다. "
                           "이 조건에서 MRR +0.02급 개선은 교체를 검토할 만한 크기라고 "
                           "본다. 라벨링이 힘들다는 이유로 임계를 +0.05·+0.06으로 "
                           "올리면 금지된 역방향 결정이 된다"),

        "primary_half_width_target": hw,
        "video_clusters": k,
        "queries_per_video": m,
        "total_gt_rows": k * m,
        "sample_size_driver": FROZEN["driver"],

        "math_minimum_video_clusters": k_min,
        "math_minimum_total_gt_rows": k_min * m,
        "primary_projected_half_width": round(S.projected_half_width(
            pv["sigma2_between"], pv["sigma2_within"], k, m), 4),
        "secondary_projected_half_width": round(S.projected_half_width(
            sv["sigma2_between"], sv["sigma2_within"], k, m), 4),
        "precision_claim_rule": ("'1,500행이면 +0.02를 반드시 검출한다'가 아니다. "
                                 "historical variance + ICC=0 근사에 기반하면 300×5 "
                                 "설계가 약 0.019급 half-width를 **목표로 한다**는 "
                                 "뜻이고, 실제 P3 cluster 구조에서는 더 넓어질 수 "
                                 "있다. 검출 보장이 아니다"),
        "topup_after_results_allowed": False,
        "topup_rule": ("결과를 본 뒤 표본을 늘리지 않는다. 달성 half-width가 목표보다 "
                       "넓게 나오면 그 사실을 그대로 보고한다"),

        "secondary_forced_to_same_half_width": False,
        "secondary_reported_always": True,
        "secondary_role_rule": ("α=0.0은 mandatory key secondary다 — 300×5에서 반드시 "
                                "계산·보고하지만 PRIMARY와 같은 half-width를 맞추려고 "
                                "N을 키우지 않는다(B안 미채택). PRIMARY가 실패했는데 "
                                "caption-only가 좋다고 adoption을 rescue하지 못한다"),

        "m_rationale": ("m=9로 가면 영상 수·GPU 비용은 줄지만 ICC가 조금만 생겨도 "
                        "취약해진다. m=3은 cluster robustness가 좋아지지만 영상이 약 "
                        "500편으로 뛰어 수집·인덱싱 부담이 과도하다. m=5가 절충점이다"),

        "labeling_route": FROZEN["route"],
        "labeling_rules": [
            "annotator에게 frozen query/GT protocol과 원본 video/audio만 준다",
            "3B/4B identity · 모델 캡션 · 파이프라인 STT · retrieval 결과 · 기존 arm "
            "결과를 숨긴다",
            "label_origin은 기록하되 PRIMARY의 selection·weighting에 쓰지 않는다",
            "사람 최종 확정 없이 GT로 세지 않는다",
            "유형 쿼터는 표집 전 동결한다",
        ],
        "scene_only_ai_route_used_for_p3a": False,
        "ai_assist_rule": ("AI 초안을 쓰려면 **전 유형을 동일 원칙으로 처리하는 "
                           "audio-capable draft route**를 별도 amendment로 만들어야 "
                           "한다. 장면형만 AI화하는 현재 방식은 P3-A에 쓰지 않는다"),

        "p3a_execution": "HOLD",
        "blocking_item": "annotation_logistics",
        "blocking_note": ("통계 설계가 덜 끝나서가 아니다. 1,500행을 실제로 처리할 "
                          "외부 annotator 경로(계약·QC·blind input bundle·작업 방식·"
                          "처리 가능성)가 확보되기 전에는 표본 수집도 시작하지 않는다"),
        "go_scope_now": "외부 annotator 경로 구체화까지",
        "next_go_bundle": ("경로 확보 후 acquisition + annotation + 2-arm indexing + "
                           "retrieval/evaluation을 한 번에 승인"),
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
        "secondary_is_co_primary": False,
        "secondary_precision_rule_approved": False,
        "secondary_role_note": ("α=0.0은 mandatory key secondary다 — 반드시 계산·"
                                "보고하지만 co-primary가 아니고, PRIMARY 실패를 "
                                "구제하지도 않는다. 그래서 secondary가 자동으로 "
                                "표본 규모를 지배하지 않는다"),
        "channels": chans,
        "targets": list(TARGETS),
        "m_grid": list(M_GRID),
        "historical_effect_illustrations": {
            k: [dict(e) for e in v] for k, v in HISTORICAL_EFFECTS.items()},
        "historical_effect_note": ("endpoint별로 분리했다. 융합 α=0.5 값과 캡션 단독 "
                                   "α=0.0 값을 섞어서 '이 정밀도로 저 효과를 잡는다'고 "
                                   "계산하면 틀린다"),
        "confirmability": confirmability(chans),
        "confirmability_note": ("CI로 0을 배제하려면 |Δ| > half-width여야 한다. "
                                "목표 half-width는 곧 확증 가능한 최소 효과 크기다 — "
                                "hw 0.04로 +0.019·+0.031을 확증할 수 없다"),
        "sample_size_options": sample_size_options(chans[PRIMARY_CHANNEL],
                                                   chans[SECONDARY_CHANNEL]),
        "frozen_decision": frozen_decision(chans[PRIMARY_CHANNEL],
                                           chans[SECONDARY_CHANNEL]),
        "sample_size_driver": FROZEN["driver"],
        "sample_size_driver_note": ("A안(PRIMARY 주도) 동결 — PRIMARY 정밀도로 N을 "
                                    "정하고 secondary의 달성 half-width를 함께 보고한다. "
                                    "B안(양쪽 동일 임계)은 채택하지 않았다 — α=0.0은 "
                                    "co-primary가 아니므로 N을 키우지 않는다"),
        "icc_zero_assumed_as_truth": False,
        "icc_robustness_note": ("관측 ICC=0을 P3의 진실로 가정하지 않는다. 비영 ICC "
                                "시나리오는 **설계 강건성 진단이고 P3 예측이 아니다.** "
                                "m이 크고 영상 수가 적은 설계는 cluster 의존성이 조금만 "
                                "생겨도 정밀도가 크게 나빠진다"),
        "minimum_deployment_relevant_gain": FROZEN["gain"],
        "adoption_utility_note": ("half-width를 고르기 전에 답해야 하는 질문이 있다 — "
                                  "'어느 정도의 deployment gain이면 4B의 추가 운영 "
                                  "비용을 감수하고 교체할 가치가 있는가'. 예를 들어 "
                                  "+0.019급을 CI로 확증하려면 confirmability 표의 규모가 "
                                  "필요한데, 그 라벨 비용이 교체 가치와 맞는지는 통계가 "
                                  "아니라 운영 판단이다. **결과를 본 뒤 정하면 안 되고 "
                                  "추론 전에 정한다.** δ 형식일 필요는 없으나 채택 결정 "
                                  "문서에는 있어야 한다"),
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

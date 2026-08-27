"""M8 event 지표 — 구조 진단 + (정답 목록이 생긴 뒤의) 시간적 사건 정합.

사전등록: `docs/preregistration/M8_event지표_보충_2026-08-18.md`.
**정답 사건 목록도 M8 재실행 산출물도 없는 시점에 규칙을 고정한다** — 나중에 정하면
목록과 지표를 서로 맞춰 튜닝할 수 있다.

**여기 있는 것은 event coverage가 아니다.** 정답 사건 목록(사람이 프레임을 보고 쓴
event inventory)이 아직 없으므로 coverage는 정의되지 않는다. `timeline_span_coverage`는
**진단**이다 — 긴 span 하나로 올릴 수 있어 품질 지표가 아니다. 이름에 그 사실을 박았다.

span은 `[start_idx, end_idx]`이고 **양 끝 포함**이다(`[0,4]` = 5구간).
"""
from collections import Counter

import numpy as np
from scipy.optimize import linear_sum_assignment

import common

IOU_THETAS = (0.3, 0.5, 0.7)          # 사전등록 §3-3 — 하나를 고르지 않고 전부 보고


def _len(span) -> int:
    return span[1] - span[0] + 1


def temporal_iou(a, b) -> float:
    """구간 IoU. 양 끝 포함이라 길이가 `end - start + 1`이다 — off-by-one이면
    지표가 조용히 어긋난다."""
    inter = min(a[1], b[1]) - max(a[0], b[0]) + 1
    if inter <= 0:
        return 0.0
    union = _len(a) + _len(b) - inter
    return inter / union


def match_events(refs: list, gens: list) -> dict:
    """정답 사건 → 생성 사건의 **1:1** 최적 매칭. 대응 없으면 None.

    **단순 "겹치면 covered"를 쓰지 않는 이유:** 거대한 span 하나가 여러 정답 사건을
    덮어 recall을 부풀린다. `segment coverage`를 주지표에서 내린 것과 같은 결함이다.

    탐욕적 매칭도 쓰지 않는다 — 먼저 온 정답이 더 나은 짝을 가져가면 전체 합이
    나빠진다. IoU 합 최대화(Hungarian)로 푼다. **겹침이 0인 쌍은 맺지 않는다**
    (억지 짝은 alignment를 오염시킨다)."""
    out = {i: None for i in range(len(refs))}
    if not refs or not gens:
        return out
    cost = np.array([[-temporal_iou(r["span"], g["span"]) for g in gens]
                     for r in refs])
    for i, j in zip(*linear_sum_assignment(cost)):
        if -cost[i, j] > 0:
            out[int(i)] = int(j)
    return out


def matched_ious(refs: list, gens: list) -> list:
    m = match_events(refs, gens)
    return [0.0 if m[i] is None else temporal_iou(refs[i]["span"], gens[m[i]]["span"])
            for i in range(len(refs))]


def event_temporal_alignment(refs: list, gens: list):
    """**주지표** — 정답 사건별 매칭 IoU의 macro 평균. 매칭 실패는 0으로 센다.

    macro인 이유: 사건 하나가 한 표다. 길이 가중이면 긴 사건이 결과를 지배한다.
    연속값인 이유: 임계 θ를 하나 고르면 그 선택이 결과를 만든다(원 사전등록이
    0.70에 외부 근거가 없다고 자백한 것과 같은 문제).

    정답이 0개면 `0.0`이 아니라 **None** — "정합 0"과 "측정 불가"는 다른 상태다
    (M9 `coverage_rate`와 같은 원칙)."""
    if not refs:
        return None
    return round(float(np.mean(matched_ious(refs, gens))), 4)


def temporal_event_recall(refs: list, gens: list, thetas=IOU_THETAS) -> dict:
    """부지표 — `IoU ≥ θ`인 정답 사건 비율. **세 θ를 전부 보고한다.**

    이름에 `temporal`을 박는다. 이 값이 검증하는 것은 **같은 시간대의 사건을
    분리해서 잡았는가**이지, 그 사건을 의미적으로 옳게 서술했는가가 아니다.
    `event recall`이라고 줄여 부르면 의미 커버리지를 잰 것처럼 읽힌다 —
    현행 M9 coverage judge는 positive accuracy 0.550으로 그 자리를 못 메운다."""
    if not refs:
        return {f"temporal_event_recall@IoU>={t}": None for t in thetas}
    ious = matched_ious(refs, gens)
    return {f"temporal_event_recall@IoU>={t}":
            round(sum(1 for v in ious if v >= t) / len(ious), 4) for t in thetas}


class GateSpecError(RuntimeError):
    """사전등록이 정하지 않은 것을 판정 시점에 정하려 할 때. **묻지 않고 고르지 않는다.**"""


def compression(n_sentences: int, n_reference_events: int):
    """C3 지표 — `리포트 문장 수 / 정답 사건 수`. 사전등록 §2-2 그대로다.

    정답 사건이 0개면 `0.0`도 `inf`도 아니라 **None**(측정 불가)이다.
    """
    if not n_reference_events:
        return None
    return round(n_sentences / n_reference_events, 4)


# C1의 파국 유형. 사전등록 §2-2가 이 셋을 열거했다 — 늘리지 않는다.
CATASTROPHIC_KINDS = ("language_drift", "early_stop", "repetition_loop")


def c1_catastrophic_count(per_video_flags: list) -> int:
    """파국이 난 **영상 수**. 사전등록이 "발생 영상 수"로 정의했으므로 문장 수가 아니다."""
    return sum(1 for f in per_video_flags if f)


def c1_verdict(per_video_flags: list) -> dict:
    """C1 — 파국 0편이어야 한다."""
    n = c1_catastrophic_count(per_video_flags)
    return {"kinds": list(CATASTROPHIC_KINDS), "n_catastrophic_videos": n,
            "n_videos": len(per_video_flags), "threshold": 0,
            "passed": n == 0}


def c3_verdict(per_video_compressions: list, statistic: str | None = None,
               threshold: float = 2.0) -> dict:
    """C3 — Compression ≤ 2.0.

    **집계 통계량을 기본값으로 고르지 않는다.** 사전등록 §2-3은 임계 2.0만 정했고
    영상 여러 편을 어떻게 합칠지는 적지 않았다. C2가 중앙값이니 C3도 중앙값일 것
    같지만, 그렇게 짐작해 넣는 순간 사전등록에 없는 규칙이 코드에 생긴다.
    호출자가 명시해야 하고, 그 선택은 **결과를 보기 전에** 문서로 남겨야 한다.
    """
    if statistic not in ("median", "mean", "max"):
        raise GateSpecError(
            "C3 집계 통계량이 사전등록에 없다 — 'median' / 'mean' / 'max' 중 하나를 "
            "명시하고 그 선택을 결과 열람 전에 문서로 남겨라 "
            "(docs/preregistration/M8_구조변경_사전등록_2026-08-16.md §2-3)")
    vals = [v for v in per_video_compressions if v is not None]
    if not vals:
        return {"statistic": statistic, "value": None, "threshold": threshold,
                "n_videos": 0, "passed": None}
    agg = {"median": np.median, "mean": np.mean, "max": np.max}[statistic]
    val = round(float(agg(vals)), 4)
    return {"statistic": statistic, "value": val, "threshold": threshold,
            "n_videos": len(vals), "passed": bool(val <= threshold)}


def c2_statistic(per_video_recalls: list):
    """C2 판정값 — 영상별 Event Recall의 **중앙값**. 평균이 아니다.

    사전등록 `M8_구조변경_사전등록_2026-08-16.md` §2-3이 "평균이 아니라 중앙값"을
    명시했고(영상 간 편차 ±48%p 실측), 판정 표본은 8~12편이다. **N이 짝수면
    중앙값은 정렬된 가운데 두 값의 평균**이므로 N=8에서는 4번째와 5번째의 평균이다.

    판정 시점에 즉석으로 `mean`이나 다른 quantile 규칙을 쓰면 사전등록과 어긋난다 —
    그래서 함수로 고정한다. 이 함수는 새 방법론이 아니라 **구현 정합성 장치**다.
    영상이 0편이면 `0.0`이 아니라 None(측정 불가)이다.
    """
    vals = [v for v in per_video_recalls if v is not None]
    if not vals:
        return None
    return round(float(np.median(vals)), 4)


def c2_verdict(per_video_recalls: list, threshold: float = 0.70) -> dict:
    """C2 통과 여부. **결과를 보고 threshold를 바꾸지 않는다** — 인자 기본값이 동결값이다."""
    stat = c2_statistic(per_video_recalls)
    return {"statistic": "median", "value": stat, "threshold": threshold,
            "n_videos": len([v for v in per_video_recalls if v is not None]),
            "passed": None if stat is None else bool(stat >= threshold)}


def _union_len(events: list) -> int:
    """겹치는 span을 합집합으로. 단순 합이면 1을 넘는다."""
    total, cur = 0, None
    for s in sorted([e["span"] for e in events], key=lambda x: x[0]):
        if cur and s[0] <= cur[1] + 1:
            cur = [cur[0], max(cur[1], s[1])]
        else:
            if cur:
                total += _len(cur)
            cur = list(s)
    return total + (_len(cur) if cur else 0)


def timeline_span_coverage(events: list, n_segments: int):
    """**진단 지표.** 사건 span 합집합 ÷ 전체 구간 수.

    `event coverage`라고 부르지 않는다 — 긴 span 하나로 올릴 수 있다."""
    if not n_segments:
        return None
    return round(_union_len(events) / n_segments, 4)


# Layer 1 — 사건 정렬 실패 유형. `docs/재분석_M8pilot_2026-08-18.md` §3에서 동결됐다.
# C1·C2·C3와 사건 구조 평가에 쓴다. **늘리거나 줄이지 않는다** — 새 유형이 필요하면
# outcome-blind amendment 사건이다. 문장 근거성 실패 유형(Layer 2)은 층이 달라
# `m9_report_eval.CLAIM_GROUNDING_REASONS`에 따로 있다 [D5].
EVENT_ALIGNMENT_TYPES = ("overmerge", "boundary_too_wide", "boundary_shift",
                         "missed_event", "spurious_event", "reasonable_match")


def structural_summary(report: dict, n_segments: int) -> dict:
    """`validate_events`가 코드로 판정한 값에서만 뽑는다. 품질 판단이 아니다."""
    ev = report.get("events") or []
    spans = [e["span"] for e in ev]
    overlaps = sum(1 for i in range(len(spans)) for j in range(i + 1, len(spans))
                   if min(spans[i][1], spans[j][1]) >= max(spans[i][0], spans[j][0]))
    return {
        "valid_events": len(ev),
        "rejected_events": len(report.get("rejected") or []),
        "rejection_reasons": dict(Counter(r["reason"]
                                          for r in report.get("rejected") or [])),
        "span_len_dist": [_len(s) for s in spans],
        "evidence_per_event_dist": [len(e["evidence_segments"]) for e in ev],
        "chars_per_evidence": [round(len(e["description"]) / len(e["evidence_segments"]), 4)
                               for e in ev if e["evidence_segments"]],
        "event_span_overlap_pairs": overlaps,
        "timeline_span_coverage": timeline_span_coverage(ev, n_segments),
        "chunk_retries": len(report.get("chunk_retries") or []),
        # 인용 없는 evaluable 문장은 M8 출력 계약 위반이다 — 여기서 세고, 판정은
        # aar_view / m9_report_eval.structural_precheck가 거부로 한다 [D4].
        # 생성 단계에서 저장을 막지는 않는다(raw_output 보존 원칙) — 대신 드러낸다.
        "uncited_evaluable_sentences": common.uncited_evaluable_sentences(
            report.get("sentences") or []),
    }

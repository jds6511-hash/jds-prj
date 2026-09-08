"""WVR_SAMPLING_SEMANTIC_DENSITY_V1 계약 (2026-09-08 · freeze).

사전등록: `docs/preregistration/WVR_SAMPLING_SEMANTIC_DENSITY_V1_2026-09-08.md`

```
Stage 1  VISUAL_TEMPORAL_COVERAGE     모델 없이 결정적 계산
Stage 2  PAIRED_OUTPUT_SENSITIVITY    같은 3분 구간에서 0.5fps vs 0.25fps
```

**이름을 지킨다.** Stage 1은 화면 변화 측정이고 `SEMANTIC_SUFFICIENCY`가 아니다.
0.5fps는 영상의 truth가 아니라 **현재보다 높은 표집 밀도 reference**다 —
2초 사이에 나타났다 사라지는 것은 0.5fps도 못 본다.
"""
import wvr_contract as contract

STAGE1 = "VISUAL_TEMPORAL_COVERAGE"
STAGE2 = "PAIRED_OUTPUT_SENSITIVITY"

# 기준 집합 = C01의 0.5fps 300프레임. 0.25fps는 그 부분집합이어야 한다.
REFERENCE_FPS = 0.5
KEEP_STRIDE = 2                      # 짝수 index만 남긴다 → 0,4,8,…,596
DENSITY_FPS = 0.25

# Stage 2 진단 창. **chunk 길이 조정이 아니다** — 0.5fps가 600초에서 OOM이라
# paired 비교가 가능한 짧은 구간을 쓰는 것이고, 생산 chunk는 600초 그대로다.
WINDOW_SEC = 180.0
WINDOW_STRIDE_SEC = 30.0

# 창 선택은 Stage 1 점수로만 한다. 사람이 내용을 보고 고르지 않는다.
SELECTION_LABELS = ("D1_highest_change", "D2_median_change", "D3_lowest_change")

# 매칭 허용오차는 하나로 고르지 않는다 — 두 값을 나란히 보고한다(사전등록된 값).
MATCH_TOLERANCE_SEC = (4.0, 8.0)

HISTOGRAM_BINS = 64


class DensityError(ValueError):
    """계약 위반. 조용히 넘기지 않는다."""


def reference_timestamps() -> tuple:
    """0.5fps 기준 시각. C01·A0가 쓴 것과 같은 규칙이다."""
    return contract.frame_timestamps(0.0, contract.CHUNK_LENGTH_SEC,
                                     REFERENCE_FPS, contract.CHUNK_MAX_FRAMES)


def keep_drop(reference=None) -> tuple:
    """KEEP은 0.25fps 집합, DROP은 빠지는 프레임. 둘은 기준 집합의 분할이다."""
    stamps = tuple(reference if reference is not None else reference_timestamps())
    keep = tuple(stamps[index] for index in range(0, len(stamps), KEEP_STRIDE))
    drop = tuple(stamp for stamp in stamps if stamp not in set(keep))
    if len(keep) + len(drop) != len(stamps):
        raise DensityError("KEEP·DROP이 기준 집합의 분할이 아니다")
    return keep, drop


def assert_subset(keep, arm_timestamps) -> None:
    """0.25fps arm이 기준 집합의 부분집합인지 — 새로 표집하면 confound다."""
    missing = [stamp for stamp in arm_timestamps if stamp not in set(keep)]
    if missing:
        raise DensityError("KEEP 집합에 없는 시각이 있다: %r" % missing[:5])
    if len(arm_timestamps) != len(keep):
        raise DensityError("KEEP %d개인데 arm은 %d개다"
                           % (len(keep), len(arm_timestamps)))


def neighbours(stamp: float, keep) -> tuple:
    """DROP 프레임의 직전·직후 KEEP 프레임."""
    before = [value for value in keep if value < stamp]
    after = [value for value in keep if value > stamp]
    return (before[-1] if before else None, after[0] if after else None)


def luma_diff(left, right) -> float:
    """평균 절대 휘도 차 (0~255). 임계값 없이 분포를 본다."""
    if len(left) != len(right):
        raise DensityError("프레임 크기가 다르다")
    total = sum(abs(int(a) - int(b)) for a, b in zip(left, right))
    return round(total / len(left), 4)


def histogram(values) -> tuple:
    """64구간 휘도 히스토그램 (합이 1)."""
    counts = [0] * HISTOGRAM_BINS
    width = 256 / HISTOGRAM_BINS
    for value in values:
        counts[min(HISTOGRAM_BINS - 1, int(value / width))] += 1
    total = float(len(values)) or 1.0
    return tuple(count / total for count in counts)


def histogram_distance(left, right) -> float:
    """1 − 교집합. 0이면 같은 분포다."""
    return round(1.0 - sum(min(a, b) for a, b in zip(left, right)), 6)


def novelty(diff_prev, diff_next) -> float:
    """양쪽 이웃과 모두 다를 때만 정보가 사라진다 — 그래서 min이다."""
    values = [value for value in (diff_prev, diff_next) if value is not None]
    if not values:
        raise DensityError("이웃이 없다")
    return round(min(values), 4)


def distribution(values) -> dict:
    """분포만 보고한다. 임계값을 만들지 않는다."""
    if not values:
        raise DensityError("값이 없다")
    ordered = sorted(values)

    def percentile(fraction):
        index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
        return round(ordered[index], 4)

    return {"count": len(ordered), "min": round(ordered[0], 4),
            "median": percentile(0.5), "p75": percentile(0.75),
            "p90": percentile(0.90), "p95": percentile(0.95),
            "max": round(ordered[-1], 4),
            "mean": round(sum(ordered) / len(ordered), 4)}


def windows(duration_sec=None) -> tuple:
    """결정적 3분 창 목록."""
    span = contract.CHUNK_LENGTH_SEC if duration_sec is None else duration_sec
    starts, start = [], 0.0
    while start + WINDOW_SEC <= span + 1e-9:
        starts.append(round(start, 3))
        start += WINDOW_STRIDE_SEC
    if not starts:
        raise DensityError("창을 만들 수 없다: %r" % span)
    return tuple({"window_id": "W%02d" % (index + 1), "start_sec": value,
                  "end_sec": round(value + WINDOW_SEC, 3)}
                 for index, value in enumerate(starts))


def window_score(window, drop_scores) -> float:
    """창 안 DROP 프레임 novelty 합. 창 선택의 유일한 근거다."""
    return round(sum(score for stamp, score in drop_scores
                     if window["start_sec"] <= stamp < window["end_sec"]), 4)


def select_windows(scored) -> dict:
    """D1 최대 · D3 최소 · D2 중앙 순위. 동률은 이른 창."""
    if not scored:
        raise DensityError("점수가 없다")
        # 동률에서 이른 창을 고르기 위해 start_sec를 2차 키로 쓴다
    ranked = sorted(scored, key=lambda row: (row["score"], row["start_sec"]))
    median_index = (len(ranked) - 1) // 2
    return {"D1_highest_change": ranked[-1], "D2_median_change":
            ranked[median_index], "D3_lowest_change": ranked[0]}


def window_frames(window, keep, drop) -> dict:
    """창 안의 기준·KEEP·DROP 프레임 시각."""
    inside = lambda stamp: window["start_sec"] <= stamp < window["end_sec"]
    return {"reference": tuple(sorted(stamp for stamp in tuple(keep) + tuple(drop)
                                      if inside(stamp))),
            "keep": tuple(stamp for stamp in keep if inside(stamp)),
            "drop": tuple(stamp for stamp in drop if inside(stamp))}

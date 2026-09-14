"""WVR_SAMPLING_SEMANTIC_DENSITY_SHORT_WINDOW_V1 계측기 (2026-09-09 · freeze).

사전등록: `docs/preregistration/WVR_SHORT_WINDOW_V1_2026-09-09.md`

```
유일한 변경   context 길이 180초 → 48초
동결          모델·revision·dtype·attn·양자화·프롬프트(V2 해시)·max_new_tokens 4096 ·
              English-only · greedy · repetition_penalty · collapse 규칙 · 해상도 512×288
창            Evidence Resolution에서 NEITHER_RESOLVED인 리뷰어 지목 충돌만 입력으로
              쓰고, gap ≤ 8초 clustering → 중심 기준 48초 창 → 4초 grid floor snap.
              사람이 창을 재선택하지 않는다
판정          자동 matcher는 audit diagnostic. primary는 blinded side-by-side 사람 판정
```
"""
import hashlib
import math

import wvr_contract as contract
import wvr_density as density
import wvr_density_prompt_v2 as diag
import wvr_density_v1b as events

EVENT = "WVR_SAMPLING_SEMANTIC_DENSITY_SHORT_WINDOW_V1"
ARTIFACT_TAG = "short_window"

# 입력 — 이전 사건의 미해결 충돌만
SOURCE_ARTIFACT = "evidence_resolution_v1.json"
SOURCE_SOURCE_TAG = "REVIEWER_NAMED"
SOURCE_RESOLUTION = "NEITHER_RESOLVED"

CONFLICT_GAP_SEC = 8.0        # cluster 병합 기준 (V2 허용오차 상한과 같은 값)
WINDOW_SEC = 48.0             # 가장 긴 cluster(D2 104–152)의 길이
GRID_SEC = 4.0                # 0.25fps 표집 격자
HALF_OPEN = True

ARM_S0 = "S0"                 # 0.5fps · higher-density reference (truth 아님)
ARM_S1 = "S1"                 # 0.25fps · S0의 KEEP 부분집합
ARMS = (ARM_S0, ARM_S1)
S0_FRAME_COUNT = 24
S1_FRAME_COUNT = 12
TOTAL_INFERENCES = 6

# 결과를 보기 전에 적어 둔 파생값 (파생 함수가 이것과 달라지면 테스트가 RED)
EXPECTED_CLUSTERS = (
    ("C1", "D1", 380.0, 390.0),
    ("C2", "D1", 420.0, 460.0),
    ("C3", "D2", 104.0, 152.0),
)
EXPECTED_WINDOWS = (
    ("P1", "C1", 360.0, 408.0),
    ("P2", "C2", 416.0, 464.0),
    ("P3", "C3", 104.0, 152.0),
)

# V2에서 그대로 가져와 동결하는 값 (하나라도 달라지면 단일 변경이 아니다)
FROZEN_FROM_V2 = {
    "model_id": contract.MODEL_ID,
    "model_revision": contract.MODEL_REVISION,
    "dtype": contract.DTYPE,
    "quantization": contract.QUANTIZATION,
    "attn_implementation": contract.ATTN_IMPLEMENTATION,
    "device_map": contract.DEVICE_MAP,
    "frame_width": contract.FRAME_WIDTH,
    "frame_height": contract.FRAME_HEIGHT,
    "do_sample": contract.DO_SAMPLE,
    "num_beams": contract.NUM_BEAMS,
    "repetition_penalty": contract.REPETITION_PENALTY,
    "do_sample_frames": contract.DO_SAMPLE_FRAMES,
    "do_resize": contract.DO_RESIZE,
    "max_new_tokens": events.tokens_for(events.EVENT_V2),
    "prompt_contract": diag.DIAG_CONTRACT_NAME,
    "prompt_hash": diag.prompt_hash(),
    "output_language": diag.OUTPUT_LANGUAGE,
    "reference_fps": density.REFERENCE_FPS,
    "density_fps": density.DENSITY_FPS,
    "keep_stride": density.KEEP_STRIDE,
    "match_tolerances": list(density.MATCH_TOLERANCE_SEC),
}

# 사람 판정 어휘 (네 값만 쓴다)
STABLE = "STABLE"
GRANULARITY_SHIFT = "GRANULARITY_SHIFT"
MATERIAL_DIVERGENCE = "MATERIAL_DIVERGENCE"
UNRESOLVED = "UNRESOLVED"
VERDICTS = (STABLE, GRANULARITY_SHIFT, MATERIAL_DIVERGENCE, UNRESOLVED)
PASSING_VERDICTS = (STABLE, GRANULARITY_SHIFT)

PROBE_PASS = "C01_SHORT_WINDOW_PAIRED_STABILITY_PASS"
PROBE_HOLD = "SHORT_WINDOW_PAIRED_STABILITY_HOLD"
PROBE_INCONCLUSIVE = "INCONCLUSIVE"

AUTOMATIC_MATCHER_ROLE = "AUDIT_DIAGNOSTIC_ONLY"
SEMANTIC_SUFFICIENCY_CLAIM_ALLOWED = False
EVENT_EXTRACTION_APPROVED = False
FRAME_ADJUDICATION_APPROVED = False

ALLOWED_PASS_CONCLUSION = (
    "C01에서 180초 probe가 보여준 report-material divergence는 48초 "
    "conflict-focused window에서는 재현되지 않았고, 0.25fps 출력은 0.5fps "
    "higher-density reference에 대해 report-materially stable했다.")
FORBIDDEN_CONCLUSION = "0.25fps is universally semantically sufficient"


class ShortWindowError(RuntimeError):
    """short-window 계약 위반."""


def snap_floor(value: float, grid: float = GRID_SEC) -> float:
    return math.floor(round(value / grid, 6)) * grid


def unresolved_conflicts(resolution: dict) -> dict:
    """리뷰어 지목 + NEITHER_RESOLVED인 충돌 구간만 pair별로 모은다."""
    rows = {}
    for pair, block in resolution["pairs"].items():
        spans = set()
        for row in block["conflicts"]:
            if SOURCE_SOURCE_TAG not in row["source"]:
                continue
            if row["resolution"] != SOURCE_RESOLUTION:
                continue
            spans.add((float(row["evidence_window"][0]),
                       float(row["evidence_window"][1])))
        if spans:
            rows[pair] = sorted(spans)
    return rows


def cluster(spans, gap: float = CONFLICT_GAP_SEC) -> list:
    """gap 이하로 떨어진 구간을 같은 cluster로 합친다 (정렬 순서대로 결정적)."""
    merged = []
    for start, end in sorted(spans):
        if merged and start - merged[-1][1] <= gap:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(row[0], row[1]) for row in merged]


def derive_clusters(resolution: dict) -> list:
    rows, index = [], 0
    per_pair = unresolved_conflicts(resolution)
    for pair in sorted(per_pair):
        for start, end in cluster(per_pair[pair]):
            index += 1
            rows.append({"cluster_id": "C%d" % index, "pair": pair,
                         "start_sec": start, "end_sec": end,
                         "length_sec": round(end - start, 3)})
    return rows


def window_for_cluster(row: dict) -> dict:
    """cluster 중심에서 48초 창을 잡고 4초 grid로 floor snap한다."""
    length = float(row["end_sec"]) - float(row["start_sec"])
    if length > WINDOW_SEC:
        raise ShortWindowError("cluster가 창보다 길다: %s %.1f초"
                               % (row["cluster_id"], length))
    centre = (float(row["start_sec"]) + float(row["end_sec"])) / 2.0
    start = snap_floor(centre - WINDOW_SEC / 2.0)
    end = start + WINDOW_SEC
    if start > row["start_sec"] or end < row["end_sec"]:
        raise ShortWindowError("창이 cluster를 못 덮는다: %s" % row["cluster_id"])
    return {"start_sec": start, "end_sec": end}


def derive_windows(resolution: dict) -> list:
    rows = []
    for index, row in enumerate(derive_clusters(resolution), start=1):
        span = window_for_cluster(row)
        rows.append({
            "window_id": "P%d" % index, "cluster_id": row["cluster_id"],
            "source_pair": row["pair"],
            "cluster": [row["start_sec"], row["end_sec"]],
            "start_sec": span["start_sec"], "end_sec": span["end_sec"],
            "length_sec": WINDOW_SEC,
        })
    return rows


def assert_expected(windows) -> None:
    """파생 결과가 사전등록에 적힌 창과 같은지 확인한다."""
    observed = tuple((row["window_id"], row["cluster_id"], row["start_sec"],
                      row["end_sec"]) for row in windows)
    if observed != EXPECTED_WINDOWS:
        raise ShortWindowError("파생된 창이 사전등록과 다르다: %r" % (observed,))


def arm_timestamps(window: dict, arm: str) -> tuple:
    """S0 = 2초 간격 24프레임, S1 = 그중 4초 간격 12프레임."""
    start = float(window["start_sec"])
    step = 1.0 / density.REFERENCE_FPS
    reference = tuple(round(start + step * i, 3)
                      for i in range(S0_FRAME_COUNT))
    if reference[-1] >= float(window["end_sec"]):
        raise ShortWindowError("기준 프레임이 창을 벗어난다")
    if arm == ARM_S0:
        return reference
    if arm == ARM_S1:
        keep = reference[::density.KEEP_STRIDE]
        if len(keep) != S1_FRAME_COUNT:
            raise ShortWindowError("KEEP 프레임 수가 %d가 아니다: %d"
                                   % (S1_FRAME_COUNT, len(keep)))
        density.assert_contained(reference, keep)
        return keep
    raise ShortWindowError("모르는 arm: %r" % arm)


def single_change(requested: dict) -> dict:
    """V2에서 바뀐 것이 context 길이 하나뿐인지 확인한다."""
    differences = {}
    for key, value in FROZEN_FROM_V2.items():
        if key not in requested:
            continue
        if requested[key] != value:
            differences[key] = {"expected": value, "observed": requested[key]}
    return {"single_change": not differences, "differences": differences,
            "changed_axis": "context_length_sec",
            "from_sec": density.WINDOW_SEC, "to_sec": WINDOW_SEC}


def window_pass(verdict: str) -> bool:
    if verdict not in VERDICTS:
        raise ShortWindowError("모르는 판정값: %r" % verdict)
    return verdict in PASSING_VERDICTS


def probe_verdict(verdicts, technical_failures=()) -> str:
    """기술적 무효 → INCONCLUSIVE → material → HOLD → 나머지 unresolved."""
    values = list(verdicts)
    if len(values) != len(EXPECTED_WINDOWS):
        raise ShortWindowError("창 %d개의 판정이 필요하다: %r"
                               % (len(EXPECTED_WINDOWS), values))
    for value in values:
        if value not in VERDICTS:
            raise ShortWindowError("모르는 판정값: %r" % value)
    if list(technical_failures):
        return PROBE_INCONCLUSIVE
    if MATERIAL_DIVERGENCE in values:
        return PROBE_HOLD
    if UNRESOLVED in values:
        return PROBE_INCONCLUSIVE
    return PROBE_PASS


def blind_label(window_id: str, arm: str, salt: str) -> str:
    """A/B 배정 — salt를 모르면 재현할 수 없다."""
    digest = hashlib.sha256(("%s|%s" % (salt, window_id)).encode("utf-8"))
    flip = digest.digest()[0] & 1
    if arm == ARM_S0:
        return "B" if flip else "A"
    if arm == ARM_S1:
        return "A" if flip else "B"
    raise ShortWindowError("모르는 arm: %r" % arm)


def salt_hash(salt: str) -> str:
    return hashlib.sha256(salt.encode("utf-8")).hexdigest()

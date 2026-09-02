"""E-02 DET 증거 — 결정성 계약을 **실제 실행**으로 잰다.

`fixed_window`이므로 deterministic할 것이다 — 이 추론을 PASS로 쓰지 않는다. 계약마다
입력을 실제로 흔들고, 무엇을 비교했는지 남긴다.

```
DET-002  rerun N≥3          경계 목록 + episode 구조 동일     (byte equality 아님 · OPEN-4)
DET-003  different LLM      canonical partition 동일
DET-004  different VLM cap   fixed-window boundary 동일
DET-005  changed OCR         fixed-window boundary 동일
DET-007  parallel execution  race로 결과 변동 없음
```

비교 projection은 **시간 구조뿐**이다.

```
넣는다     boundary_positions · spans · episode_id · start_seg · end_seg
          start_sec · end_sec · 순서 · 개수
넣지 않는다  content · raw bytes · hash · run_id · 판정
```

세 perturbation 계약(003 · 004 · 005)을 하나로 뭉치지 않는다. 그리고 **perturbation이
실제로 perturbation인지 먼저 확인한다** — A와 B가 같으면 그 테스트는 아무것도 재지 않는다.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from v2_1_aar import build_aar_canonical, structural_signature
from v2_1_boundary import ProviderRegistry
from v2_1_episode import build_episodes
from v2_1_fixed_window import FixedWindowV1, window_spans
from v2_1_fixtures import INSTRUCTION_ECHO, scenario
from v2_1_gate_b import run_pipeline
from v2_1_parse import model_failure
from v2_1_run import create_run, hash_config
from v2_1_sanitation import classify_channel
from v2_1_timeline import build_timeline

#: 20초 창. 60초 격자에서 창이 3개 나온다 — 창이 하나뿐이면 "경계 목록 동일"이
#: 자동으로 성립해 비교가 무의미해진다.
WINDOW_SEC = 20.0

REPEATS = 5          # matrix는 N≥3을 요구한다. 여유를 둔다.
WORKERS = 8


def _registry():
    registry = ProviderRegistry()
    registry.register(FixedWindowV1())
    return registry


def _time_projection(segments, channels, window_sec=WINDOW_SEC):
    """격자와 채널에서 시간 구조만 파생한다.

    경계를 **입력으로 받지 않는다** — `window_spans`로 직접 파생해야 "같은 영상·같은
    config에서 partition이 같은가"를 재는 것이 된다.
    """
    judged = {source_type: classify_channel(channel, source_type)
              for source_type, channel in channels.items() if channel}
    timeline = build_timeline(segments, judged)
    spans = window_spans(segments, window_sec)
    episodes = build_episodes(spans, segments, timeline=timeline)
    boundary = _registry().run(
        None, segments, config={"window_sec": window_sec}).boundary_positions
    return {
        "boundary_positions": tuple(boundary),
        "spans": tuple(spans),
        "episodes": tuple((e.episode_id, e.start_seg, e.end_seg,
                           e.start_sec, e.end_sec) for e in episodes),
        "count": len(episodes),
    }


def _channels(name):
    s = scenario(name)
    return {"asr": dict(s.asr), "vlm": dict(s.caption), "ocr": dict(s.ocr)}


# ── DET-007 parallel execution ───────────────────────────────────────────
#: worker마다 **다른 입력**을 준다. 전부 같은 입력으로 돌리면 thread 사이로 상태가
#: 새어도 결과가 우연히 맞아 통과한다 — 그러면 race를 재지 못한다.
WORK = (("S1", 20.0), ("S2", 60.0), ("S1", 60.0), ("S3", 20.0),
        ("S2", 20.0), ("S4", 60.0), ("S5", 20.0), ("S1", 15.0))


def _one_run(root: Path, index: int, name: str, window_sec: float):
    """한 worker의 전 구간. run layout까지 실제로 만든다."""
    layout = create_run(root, video_id=name, run_id="run-%03d" % index,
                        analysis_mode="report",
                        config_hash=hash_config({"window_sec": window_sec}),
                        code_git_head="deadbeef")
    s = scenario(name)
    projection = _time_projection(s.segments, _channels(name), window_sec)
    payloads = _PAYLOADS_A * len(projection["spans"])
    pipeline = run_pipeline(layout.dir("raw"), payloads, name=name,
                            spans=list(projection["spans"]),
                            run_id=layout.manifest.run_id)
    return projection, structural_signature(pipeline.document)


def test_det_007_parallel_runs_do_not_interfere(tmp_path):
    """실제 동시 실행. frozen dataclass·pure 함수처럼 보인다는 것은 증거가 아니다."""
    serial = [_one_run(tmp_path / "serial", index, name, window_sec)
              for index, (name, window_sec) in enumerate(WORK)]
    # 입력이 실제로 갈린다 — 같은 답만 나오면 비교가 무의미하다.
    assert len({tuple(r[0]["spans"]) for r in serial}) > 1

    root = tmp_path / "parallel"
    with ThreadPoolExecutor(max_workers=len(WORK)) as pool:
        results = list(pool.map(
            lambda item: _one_run(root, item[0], *item[1]),
            list(enumerate(WORK))))

    assert len(results) == len(WORK)
    for index, (got, want) in enumerate(zip(results, serial)):
        assert got == want, "worker %d (%s)" % (index, WORK[index][0])

    # run layout이 실제로 분리됐다.
    made = sorted("%s/%s" % (video.name, run.name)
                  for video in root.iterdir() for run in video.iterdir())
    assert len(made) == len(WORK)


def test_det_007_a_shared_registry_is_safe_under_concurrent_reads(tmp_path):
    """provider registry를 공유해도 결과가 흔들리지 않는다."""
    shared = _registry()
    s = scenario("S1")
    config = {"window_sec": WINDOW_SEC}

    def run(_):
        return tuple(shared.run(None, s.segments,
                                config=config).boundary_positions)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        seen = set(pool.map(run, range(WORKERS * 4)))
    assert len(seen) == 1
    assert seen.pop() == tuple(window_spans(s.segments, WINDOW_SEC)[i][0]
                               for i in range(3))


# ── DET-002 rerun N≥3 ────────────────────────────────────────────────────
def test_det_002_at_least_three_reruns_give_the_same_structure():
    """N≥3. 2회 실행이나 serialization equality로 닫지 않는다."""
    s = scenario("S1")
    channels = _channels("S1")
    runs = [_time_projection(s.segments, channels) for _ in range(REPEATS)]

    assert REPEATS >= 3
    assert all(run == runs[0] for run in runs[1:])

    # 비교가 무의미해지지 않도록 창이 여러 개인지 확인한다.
    assert len(runs[0]["boundary_positions"]) == 3
    assert runs[0]["count"] == 3
    assert runs[0]["episodes"][0][0] == "EP01"
    assert [e[0] for e in runs[0]["episodes"]] == ["EP01", "EP02", "EP03"]


def test_det_002_reruns_of_the_full_pipeline_keep_the_same_structure(tmp_path):
    """정본 문서까지 태운 뒤에도 N≥3에서 같다. run_id는 매번 다르다."""
    spans = window_spans(scenario("S1").segments, WINDOW_SEC)
    signatures = []
    for index in range(REPEATS):
        pipeline = run_pipeline(tmp_path / ("run%d" % index), _PAYLOADS_A,
                                name="S1", spans=spans,
                                run_id="run-%03d" % index)
        signatures.append(structural_signature(pipeline.document))
    assert len(signatures) >= 3
    assert all(sig == signatures[0] for sig in signatures[1:])
    assert len(signatures[0]) == 3


# ── DET-003 different LLM ────────────────────────────────────────────────
#: 서로 다른 모델 출력. 문장·발화·인용·실패까지 전부 다르다.
_PAYLOADS_A = ({"summary": "해변에 앉아 이야기한다."},
               {"summary": "짐을 챙겨 자리를 옮긴다.",
                "dialogue_note": "다음 장소를 정한다.", "stt_cites": [9]},
               {"summary": "지도를 펼쳐 본다."})
_PAYLOADS_B = ({"summary": "두 사람이 모래를 밟는다.", "stt_cites": [1]},
               model_failure(RuntimeError("CUDA out of memory")),
               {"summary": "간식을 꺼내 나눈다.", "dialogue_note": "하산 시각을 말한다.",
                "stt_cites": [10]})


def test_det_003_a_different_llm_output_does_not_move_the_partition(tmp_path):
    """모델 출력이 달라도 canonical partition은 같다."""
    spans = window_spans(scenario("S1").segments, WINDOW_SEC)
    first = run_pipeline(tmp_path / "a", _PAYLOADS_A, name="S1", spans=spans,
                         run_id="run-a")
    second = run_pipeline(tmp_path / "b", _PAYLOADS_B, name="S1", spans=spans,
                          run_id="run-b")

    # perturbation 검증 — 두 산출물이 실제로 다르다.
    summaries_a = [e["summary"] for e in first.document["episodes"]]
    summaries_b = [e["summary"] for e in second.document["episodes"]]
    assert summaries_a != summaries_b
    assert [e["content_status"] for e in first.document["episodes"]] != \
        [e["content_status"] for e in second.document["episodes"]]

    # 비교 projection — 시간 구조만.
    assert structural_signature(first.document) == \
        structural_signature(second.document)
    assert [(e["start_seg"], e["end_seg"]) for e in first.document["episodes"]] \
        == [(s, e) for s, e in spans]
    assert [e["episode_id"] for e in first.document["episodes"]] == \
        [e["episode_id"] for e in second.document["episodes"]]


# ── DET-004 different VLM caption ────────────────────────────────────────
#: 같은 격자에 얹는 완전히 다른 캡션. 전 구간이 다르다.
CAPTION_A = {i: "두 여성이 해변에 앉아 있습니다." for i in range(12)}
CAPTION_B = {i: "남자가 공사장에서 벽돌을 옮기고 있습니다." for i in range(12)}
CAPTION_ECHO = {**CAPTION_A, 3: INSTRUCTION_ECHO}


@pytest.mark.parametrize("other", ["B", "ECHO", "EMPTY"])
def test_det_004_a_different_vlm_caption_does_not_move_the_boundary(other):
    """캡션이 달라도 창 경계와 episode 구조는 같다."""
    segments = scenario("S1").segments
    variants = {"B": CAPTION_B, "ECHO": CAPTION_ECHO,
                "EMPTY": {i: "" for i in range(12)}}
    caption_b = variants[other]

    # perturbation 검증 — 두 캡션이 실제로 다르다. 같으면 아무것도 재지 않는다.
    assert CAPTION_A != caption_b
    differing = [i for i in CAPTION_A if CAPTION_A[i] != caption_b.get(i)]
    assert differing, other

    base = _time_projection(segments, {"vlm": CAPTION_A})
    moved = _time_projection(segments, {"vlm": caption_b})
    assert base == moved
    assert len(base["boundary_positions"]) == 3


def test_det_004_the_caption_change_is_visible_somewhere_else():
    """경계가 안 움직이는 것이 '캡션이 무시된다'는 뜻은 아니다 — 판정은 달라진다."""
    judged_a = classify_channel(CAPTION_A, "vlm")
    judged_echo = classify_channel(CAPTION_ECHO, "vlm")
    assert judged_a[3].status != judged_echo[3].status


# ── DET-005 changed OCR ──────────────────────────────────────────────────
OCR_A = {**{i: "" for i in range(12)}, 4: "출발 09:30 김해공항"}
OCR_B = {**{i: "" for i in range(12)}, 9: "도착 18:40 인천"}


@pytest.mark.parametrize("other", ["B", "NONE", "ALL"])
def test_det_005_changed_ocr_does_not_move_the_boundary(other):
    """OCR이 달라도 창 경계와 episode 구조는 같다. 소스 스캔만으로 닫지 않는다."""
    segments = scenario("S1").segments
    variants = {"B": OCR_B, "NONE": {}, "ALL": {i: "표지판 %d" % i for i in range(12)}}
    ocr_b = variants[other]

    assert OCR_A != ocr_b, other

    base = _time_projection(segments, {"vlm": CAPTION_A, "ocr": OCR_A})
    moved = _time_projection(segments, {"vlm": CAPTION_A, "ocr": ocr_b})
    assert base == moved
    assert len(base["boundary_positions"]) == 3


def test_det_005_the_ocr_change_is_visible_in_the_timeline():
    """OCR 변경이 실제로 어딘가에는 반영된다 — 그래야 위 불변성이 의미를 갖는다."""
    segments = scenario("S1").segments
    a = build_timeline(segments, {"ocr": classify_channel(OCR_A, "ocr")})
    b = build_timeline(segments, {"ocr": classify_channel(OCR_B, "ocr")})
    assert [(e.segment_id, len(e.ocr_refs)) for e in a] != \
        [(e.segment_id, len(e.ocr_refs)) for e in b]


# ── DET-006 보강 — 독립 재생성 후 직렬화 ─────────────────────────────────
def test_det_006_ids_and_ordering_survive_an_independent_rebuild(tmp_path):
    """왕복만이 아니라 **독립 재생성 → 직렬화**에서도 id·순서가 같다."""
    spans = window_spans(scenario("S1").segments, WINDOW_SEC)
    texts = []
    for index in range(3):
        pipeline = run_pipeline(tmp_path / ("r%d" % index), _PAYLOADS_A,
                                name="S1", spans=spans, run_id="run-fixed")
        document = build_aar_canonical(
            video_id="S1", run_id="run-fixed",
            segments=pipeline.scenario.segments, grounded=pipeline.grounded,
            timeline=pipeline.timeline)
        payload = json.loads(json.dumps(document, ensure_ascii=False,
                                        sort_keys=True))
        texts.append([(e["episode_id"], e["start_seg"], e["end_seg"])
                      for e in payload["episodes"]])
    assert all(t == texts[0] for t in texts[1:])
    assert [t[0] for t in texts[0]] == ["EP01", "EP02", "EP03"]

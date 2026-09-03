"""Gate B 공용 파이프라인 조립 (B-08).

Gate B 테스트마다 같은 조립을 반복해 왔다 — segments → raw store → sanitation →
timeline → episodes → content → binding → grounding → aar. 결함 주입 테스트는 그
사슬 **전체**를 통과시켜야 의미가 있으므로 여기서 한 번만 세운다.

LLM을 부르지 않는다. 모델 출력 자리에는 payload 사전을 그대로 넣는다 — 그래야
"모델이 이런 것을 냈을 때 어디서 잡히는가"를 결정적으로 잴 수 있다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from v2_1_aar import build_aar_canonical
from v2_1_binding import bind_cites
from v2_1_content import merge_content
from v2_1_episode import build_episodes
from v2_1_fixtures import scenario
from v2_1_grounding import apply_grounding, validate_grounding
from v2_1_parse import SegmentRegistry, parse_json_payload
from v2_1_raw_store import RawStore
from v2_1_sanitation import classify_channel
from v2_1_sparse_summary import apply_sparse_summary
from v2_1_timeline import build_timeline

DEFAULT_SPANS = ((0, 5), (6, 11))


@dataclass
class Pipeline:
    """한 영상에 대한 Gate B 전 구간 산출물."""

    scenario: object
    store: RawStore
    timeline: list
    episodes: list
    registry: SegmentRegistry
    results: list
    bindings: list
    grounding: list
    grounded: list
    document: dict


def run_pipeline(tmp_path, payloads, *, name="S1", spans=DEFAULT_SPANS,
                 asr_overrides=None, run_id="run-001") -> Pipeline:
    """모델 출력 자리에 `payloads`를 넣고 정본 문서까지 만든다.

    `payloads` 원소는 사전(정상 출력) · 문자열(raw 그대로) · ParseResult(실패 주입)
    셋 중 하나다.
    """
    s = scenario(name)
    store = RawStore(tmp_path / "raw", run_id=run_id, video_id=name)
    asr = dict(s.asr)
    asr.update(asr_overrides or {})

    judged = {}
    for source_type, channel in (("asr", asr), ("vlm", s.caption), ("ocr", s.ocr)):
        if not channel:
            continue
        for segment_id, text in channel.items():
            store.store(segment_id=segment_id, source_type=source_type,
                        producer="p", producer_version="v", payload=text)
        judged[source_type] = classify_channel(channel, source_type)

    timeline = build_timeline(s.segments, judged)
    episodes = build_episodes(list(spans), s.segments, timeline=timeline)
    registry = SegmentRegistry(s.segments)

    results, bindings, grounding, grounded = [], [], [], []
    for index, (episode, payload) in enumerate(zip(episodes, payloads)):
        outcome = _outcome(store, registry, index, payload)
        result = merge_content(episode, outcome)
        binding = bind_cites(result, timeline, registry)
        verdict = validate_grounding(binding, store)
        results.append(result)
        bindings.append(binding)
        grounding.append(verdict)
        # sparse safe mode는 판정 **뒤**에 온다. grounding이 이 결정을 하지
        # 않는다 — 여기서 바뀌는 것은 문장의 출처뿐이다(TRI-005 · C3).
        grounded.append(apply_sparse_summary(
            apply_grounding(binding, verdict), episode, timeline, store))

    document = build_aar_canonical(video_id=name, run_id=run_id,
                                   segments=s.segments, grounded=grounded,
                                   timeline=timeline)
    return Pipeline(s, store, timeline, episodes, registry,
                    results, bindings, grounding, grounded, document)


def _outcome(store, registry, index, payload):
    """모델 출력을 raw store에 남긴 뒤 parse한다 — raw-before-parse를 지킨다."""
    if not isinstance(payload, (dict, str)):
        return payload                      # 이미 만들어진 실패(model_failure 등)
    raw = payload if isinstance(payload, str) else json.dumps(payload,
                                                              ensure_ascii=False)
    return store.store_then_parse(
        lambda text: parse_json_payload(text, registry),
        segment_id=index,
        source_type="llm",
        producer="fixture",
        producer_version="0",
        payload=raw,
    ).parsed

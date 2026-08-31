"""OPEN-10 재실행 확인 + 새로 드러난 필드 혼동 (2026-08-31).

저장된 run 3 raw만 쓴다 — 모델도 GPU도 부르지 않는다. 실행 결과를 주장이 아니라
산출물로 고정하는 것이 목적이다.

```
run 2 (episode_content_v1)  dialogue_note = "선택"                자리표시자 복사
run 3 (episode_content_v2)  dialogue_note = "[0, 1, 2, …]"        필드 혼동
```

`"선택"`은 사라졌다. 그런데 같은 부류(producer-side contamination)가 다른 모양으로
나타났다. **차이가 중요하다** — `"선택"`은 앵커가 없어 grounding을 통과했겠지만,
run 3의 오염은 세 경로 모두 grounding에서 걸려 canonical에 남지 않는다.
"""
import json
import tempfile
from pathlib import Path

import pytest

from v2_1_binding import bind_cites
from v2_1_content import merge_content
from v2_1_episode import build_episodes
from v2_1_fixtures import scenario
from v2_1_grounding import (
    FAIL_NO_SUPPORT,
    FAIL_UNSUPPORTED,
    NOT_APPLICABLE,
    apply_grounding,
    validate_grounding,
)
from v2_1_parse import VALID_PARSE, SegmentRegistry, parse_json_payload
from v2_1_raw_store import RawStore
from v2_1_sanitation import classify_channel
from v2_1_timeline import build_timeline

ROOT = Path(__file__).resolve().parents[1]
RUN3 = ROOT / "runs/v2_1/b02b_integration_run3.json"
RAW = ROOT / "runs/v2_1/b02b_raw"

CASES = {"S3": (0, 11), "S4": (0, 11), "S1": (6, 11)}


@pytest.fixture(scope="module")
def report():
    return json.loads(RUN3.read_text(encoding="utf-8"))


def _downstream(name):
    """저장된 raw를 그대로 파이프라인 뒤쪽에 태운다."""
    s = scenario(name)
    store = RawStore(Path(tempfile.mkdtemp()), run_id="r3", video_id=name)
    judged = {}
    for source_type, channel in (("asr", s.asr), ("vlm", s.caption), ("ocr", s.ocr)):
        if not channel:
            continue
        for segment_id, text in channel.items():
            store.store(segment_id=segment_id, source_type=source_type,
                        producer="p", producer_version="v", payload=text)
        judged[source_type] = classify_channel(channel, source_type)
    timeline = build_timeline(s.segments, judged)
    episode = build_episodes([CASES[name]], s.segments, timeline=timeline)[0]
    registry = SegmentRegistry(s.segments)
    raw = (RAW / ("run3_%s.raw" % name)).read_text(encoding="utf-8")
    binding = bind_cites(
        merge_content(episode, parse_json_payload(raw, registry)), timeline, registry
    )
    verdict = validate_grounding(binding, store)
    return verdict, apply_grounding(binding, verdict)


# ── OPEN-10 acceptance ───────────────────────────────────────────────────
def test_the_placeholder_is_gone(report):
    for case in report["cases"]:
        assert case["dialogue_note"] != "선택"
    assert "선택" not in json.dumps(report, ensure_ascii=False)


def test_the_placeholder_is_gone_from_the_raw_output():
    for name in CASES:
        assert "선택" not in (RAW / ("run3_%s.raw" % name)).read_text(encoding="utf-8")


def test_it_was_actually_present_before():
    """수정 전 산출물이 남아 있어야 '고쳤다'가 검증 가능하다."""
    before = (RAW / "run2_S1.raw").read_text(encoding="utf-8")
    assert "선택" in before


def test_the_run_used_prompt_v2(report):
    for case in report["cases"]:
        assert case["prompt_version"] == "episode_content_v2"


def test_conditions_were_unchanged(report):
    assert report["model_id"] == "Qwen/Qwen2.5-7B-Instruct"
    assert report["generation"]["do_sample"] is False
    assert report["generation"]["max_new_tokens"] == 512
    assert "none" in report["quantization"]


def test_contract_still_holds(report):
    for case in report["cases"]:
        assert case["content_status"] == VALID_PARSE
        assert case["episode_structure_intact"] is True
        assert case["raw_ref"]
        assert case["ignored_fields"] == []


# ── 새로 드러난 것 — 필드 혼동 ───────────────────────────────────────────
def test_the_model_now_confuses_the_two_optional_fields(report):
    """dialogue_note에 인용 목록이 문자열로 들어왔다. 발화가 아니다."""
    notes = {c["scenario"]: c["dialogue_note"] for c in report["cases"]}
    assert notes["S4"].startswith("[")
    assert notes["S1"].startswith("[")


def test_caption_only_video_still_produced_speech_cites(report):
    """S3는 ASR이 아예 없는데 stt_cites가 채워졌다 — 지어낸 인용이다."""
    s3 = next(c for c in report["cases"] if c["scenario"] == "S3")
    assert s3["stt_cites"]
    assert not scenario("S3").asr


# ── 그 오염이 canonical에 남는가 ─────────────────────────────────────────
def test_the_contamination_never_reaches_canonical_content():
    """세 경로 모두 dialogue가 제거되고 summary만 남는다."""
    for name in CASES:
        verdict, grounded = _downstream(name)
        assert grounded.dialogue_note is None, name
        assert grounded.summary, name


def test_each_case_fails_for_its_own_reason():
    assert _downstream("S3")[0].status == NOT_APPLICABLE
    assert _downstream("S4")[0].status == FAIL_NO_SUPPORT
    assert _downstream("S1")[0].status == FAIL_UNSUPPORTED


def test_invented_cites_do_not_become_support():
    """S3의 지어낸 인용은 claim이 없으므로 근거로 승격되지 않는다."""
    verdict, grounded = _downstream("S3")
    assert grounded.dialogue_note is None
    assert verdict.status == NOT_APPLICABLE


def test_the_earlier_placeholder_would_have_survived_grounding():
    """`"선택"`은 앵커가 없어 통과했을 것이다 — OPEN-10이 중요했던 이유."""
    from v2_1_grounding import anchors_in

    assert anchors_in("선택") == set()
    assert anchors_in("[0, 1, 2]") != set()

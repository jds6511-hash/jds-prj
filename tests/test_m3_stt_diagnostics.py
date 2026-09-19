"""m3_generate.transcribe의 진단 수집 확장 — 기본 동작은 그대로다.

clean validation(§7)이 STT 시점의 avg_logprob·no_speech_prob·compression_ratio를 요구한다.
공식 경로를 벗어나 따로 전사하면 두 번 돌려야 하므로, 같은 호출에서 함께 담는다.
"""
import json

import m3_generate


class Seg:
    def __init__(self, start, end, text, avg_logprob=-0.3, no_speech_prob=0.05,
                 compression_ratio=1.2, words=None):
        self.start, self.end, self.text = start, end, text
        self.avg_logprob, self.no_speech_prob = avg_logprob, no_speech_prob
        self.compression_ratio = compression_ratio
        self.words = words


class Word:
    def __init__(self, word, probability, start, end):
        self.word, self.probability, self.start, self.end = word, probability, start, end


def test_segment_diagnostic_collects_available_fields():
    segment = Seg(1.0, 4.0, " 예산 집행 현황입니다. ", avg_logprob=-0.42,
                  no_speech_prob=0.11, compression_ratio=1.31,
                  words=[Word("예산", 0.91, 1.0, 1.4), Word("집행", 0.72, 1.4, 1.9)])
    diagnostic = m3_generate.segment_diagnostic(segment)
    assert diagnostic["t0"] == 1.0 and diagnostic["t1"] == 4.0
    assert diagnostic["text"] == "예산 집행 현황입니다."
    assert diagnostic["avg_logprob"] == -0.42
    assert diagnostic["no_speech_prob"] == 0.11
    assert diagnostic["compression_ratio"] == 1.31
    assert diagnostic["min_word_probability"] == 0.72
    assert round(diagnostic["mean_word_probability"], 4) == 0.815


def test_segment_diagnostic_without_words():
    diagnostic = m3_generate.segment_diagnostic(Seg(0.0, 2.0, "네."))
    assert diagnostic["min_word_probability"] is None
    assert diagnostic["mean_word_probability"] is None


def test_cache_payload_keeps_utterances_first_class(tmp_path):
    """캐시 형식이 바뀌어도 기존 독자는 utterances만 읽으면 된다."""
    cache = tmp_path / "stt_cache.json"
    payload = {"meta": {"model": "large-v3"},
               "utterances": [{"text": "가", "t0": 0.0, "t1": 1.0}],
               "diagnostics": [{"t0": 0.0, "t1": 1.0, "avg_logprob": -0.2}]}
    cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    stored = json.loads(cache.read_text(encoding="utf-8"))
    assert [u["text"] for u in stored["utterances"]] == ["가"]
    assert stored["diagnostics"][0]["avg_logprob"] == -0.2


def test_transcribe_signature_has_optional_diagnostics():
    import inspect

    signature = inspect.signature(m3_generate.transcribe)
    assert "with_diagnostics" in signature.parameters
    assert signature.parameters["with_diagnostics"].default is False

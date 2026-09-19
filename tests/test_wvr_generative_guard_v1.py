"""WVR_GENERATIVE_GUARD_AND_REPORT_SELECTION_V1.

생성 → 하드 게이트 → claim 단위 검증 → 실패 시 fallback → report 선택.
검증 모델 호출은 주입한다(테스트는 GPU 없이 돈다).
"""
import pytest

import wvr_generative_guard_v1 as G
import wvr_report_selection_v1 as S


# ── 언어 하드 게이트 ────────────────────────────────────────────────────

def test_language_gate_passes_korean():
    assert G.language_gate("치즈를 냉동과 냉장으로 나누어 보관하는 방법을 설명한다.")["status"] == G.PASS


def test_language_gate_allows_latin_terms_inside_korean():
    result = G.language_gate("AI 서비스와 GPU 지원 예산을 논의한다.")
    assert result["status"] == G.PASS


def test_language_gate_blocks_chinese_output():
    result = G.language_gate("参与人员提到了剁碎的蒜和盐，并分享了粉丝最喜欢的一道菜。")
    assert result["status"] == G.FAIL
    assert result["reason_code"] == G.LANGUAGE_GATE_FAIL


def test_language_gate_blocks_mixed_title_with_han():
    result = G.language_gate("음식谈论")
    assert result["status"] == G.FAIL


def test_language_gate_blocks_japanese_kana():
    assert G.language_gate("食事の準備をします")["status"] == G.FAIL


def test_language_gate_blocks_mostly_latin():
    assert G.language_gate("The participants discussed the budget plan.")["status"] == G.FAIL


# ── atomic claim 분해 ──────────────────────────────────────────────────

def test_split_claims_separates_clauses():
    claims = G.split_claims("서비스 제공자가 고객에게 지게 사용 과정을 보여주며, 고객들이 서비스를 받고 있습니다.")
    assert len(claims) >= 2
    assert any("지게" in c for c in claims)


def test_split_claims_keeps_single_sentence_intact():
    claims = G.split_claims("계란후라이를 하나씩 만들어 가고 있습니다.")
    assert claims == ["계란후라이를 하나씩 만들어 가고 있습니다."]


def test_split_claims_drops_empty_fragments():
    assert all(c.strip() for c in G.split_claims("A이며, , B이다."))


# ── claim 검증 (모델 주입) ─────────────────────────────────────────────

def fake_verifier(mapping, default=G.UNCERTAIN):
    def verify(claim, evidence_texts):
        for key, verdict in mapping.items():
            if key in claim:
                return {"verdict": verdict, "reason": "stub:%s" % key}
        return {"verdict": default, "reason": "stub:default"}
    return verify


def test_verify_summary_marks_unsupported_when_any_core_claim_fails():
    result = G.verify_summary(
        "서비스 제공자가 고객에게 지게 사용 과정을 보여준다.",
        ["밑에 계신 분들은 올라오셔서 지게 매실게요"],
        fake_verifier({"서비스": G.UNSUPPORTED, "지게": G.SUPPORTED}))
    assert result["status"] == G.UNSUPPORTED
    assert any(c["verdict"] == G.UNSUPPORTED for c in result["claims"])


def test_verify_summary_supported_when_all_claims_supported():
    result = G.verify_summary("계란후라이를 만든다.", ["계란후라이를 만들었어요"],
                              fake_verifier({"계란": G.SUPPORTED}))
    assert result["status"] == G.SUPPORTED


def test_verify_summary_uncertain_when_mixed_without_unsupported():
    result = G.verify_summary("치즈를 보관한다.", ["치즈를 반은 얼려먹고"],
                              fake_verifier({}, default=G.UNCERTAIN))
    assert result["status"] == G.UNCERTAIN


# ── STT anomaly ───────────────────────────────────────────────────────

def test_stt_anomaly_detects_repeated_token():
    item = {"id": "U1", "start": 0.0, "end": 12.0,
            "text": "참기름, 참기름, 참기름, 참기름, 참기름, 참기름, 참기름."}
    assert G.utterance_flag(item) == G.STT_ANOMALY


def test_stt_anomaly_detects_broken_characters():
    item = {"id": "U2", "start": 0.0, "end": 5.0, "text": "검은 오리지널ą 조금씩 올려줘요"}
    assert G.utterance_flag(item) == G.STT_ANOMALY


def test_low_confidence_flag_from_transcript_field():
    item = {"id": "U3", "start": 0.0, "end": 5.0, "text": "웅얼거림", "low_confidence": True}
    assert G.utterance_flag(item) == G.LOW_CONFIDENCE


def test_normal_utterance_has_normal_flag():
    item = {"id": "U4", "start": 0.0, "end": 5.0, "text": "예산 집행 현황을 보고드립니다."}
    assert G.utterance_flag(item) == G.NORMAL


def test_event_anomaly_ratio_and_dependency():
    utterances = [{"id": "U1", "start": 0, "end": 5, "text": "참기름 참기름 참기름 참기름 참기름"},
                  {"id": "U2", "start": 6, "end": 20, "text": "예산 집행 현황을 보고드립니다."}]
    summary = G.event_anomaly_summary(utterances)
    assert summary["anomaly_utterance_ids"] == ["U1"]
    assert summary["anomaly_ratio"] == 0.5
    assert summary["depends_on_anomaly"] is False


def test_event_anomaly_dependency_when_most_evidence_is_broken():
    utterances = [{"id": "U1", "start": 0, "end": 5, "text": "참기름 참기름 참기름 참기름 참기름"},
                  {"id": "U2", "start": 6, "end": 9, "text": "오리지널ą ą ą"}]
    summary = G.event_anomaly_summary(utterances)
    assert summary["depends_on_anomaly"] is True


# ── 최종 판정과 fallback ───────────────────────────────────────────────

def test_decision_uses_generative_when_all_gates_pass():
    decision = G.decide_summary(generated="계란후라이를 만든다.", extractive="계란후라이 어쩌고",
                                language={"status": G.PASS},
                                verification={"status": G.SUPPORTED},
                                anomaly={"depends_on_anomaly": False},
                                numbers=[])
    assert decision["summary"] == "계란후라이를 만든다."
    assert decision["summary_source"] == G.GENERATIVE


def test_decision_falls_back_on_language_failure():
    decision = G.decide_summary(generated="音食谈论", extractive="추출 요약",
                                language={"status": G.FAIL, "reason_code": G.LANGUAGE_GATE_FAIL},
                                verification={"status": G.SUPPORTED},
                                anomaly={"depends_on_anomaly": False}, numbers=[])
    assert decision["summary"] == "추출 요약"
    assert decision["summary_source"] == G.EXTRACTIVE_FALLBACK
    assert G.LANGUAGE_GATE_FAIL in decision["reasons"]


def test_decision_falls_back_on_unsupported_claim():
    decision = G.decide_summary(generated="서비스 제공자가 고객에게…", extractive="추출 요약",
                                language={"status": G.PASS},
                                verification={"status": G.UNSUPPORTED},
                                anomaly={"depends_on_anomaly": False}, numbers=[])
    assert decision["summary_source"] == G.EXTRACTIVE_FALLBACK
    assert "UNSUPPORTED_CLAIM" in decision["reasons"]


def test_decision_falls_back_when_evidence_is_broken():
    decision = G.decide_summary(generated="프리팬이 작업을 시작합니다.", extractive="프리팬이 완성되었습니다.",
                                language={"status": G.PASS},
                                verification={"status": G.UNCERTAIN},
                                anomaly={"depends_on_anomaly": True}, numbers=[])
    assert decision["summary_source"] == G.EXTRACTIVE_FALLBACK
    assert "STT_ANOMALY_DEPENDENCY" in decision["reasons"]


def test_decision_falls_back_on_unsupported_number():
    decision = G.decide_summary(generated="3개월 보관한다.", extractive="보관한다",
                                language={"status": G.PASS},
                                verification={"status": G.SUPPORTED},
                                anomaly={"depends_on_anomaly": False}, numbers=["3개월"])
    assert decision["summary_source"] == G.EXTRACTIVE_FALLBACK


def test_decision_keeps_generative_when_uncertain_but_evidence_clean():
    decision = G.decide_summary(generated="예산 편성 방향을 설명한다.", extractive="원문 발췌",
                                language={"status": G.PASS},
                                verification={"status": G.UNCERTAIN},
                                anomaly={"depends_on_anomaly": False}, numbers=[])
    assert decision["summary_source"] == G.GENERATIVE
    assert "UNCERTAIN_CLAIM" in decision["reasons"]


def test_regenerated_source_label():
    decision = G.decide_summary(generated="예산 편성 방향을 설명한다.", extractive="원문",
                                language={"status": G.PASS},
                                verification={"status": G.SUPPORTED},
                                anomaly={"depends_on_anomaly": False}, numbers=[],
                                regenerated=True)
    assert decision["summary_source"] == G.REGENERATED


# ── report selection ──────────────────────────────────────────────────

def _row(row_id, start, end, summary, evidence="음성", chapter="CH001"):
    return {"row_id": row_id, "start": start, "end": end, "summary": summary,
            "category": "구분", "evidence": evidence, "evidence_type": "AUDIO",
            "chapter_id": chapter, "visual_event_ids": [], "speech_event_ids": [row_id],
            "visual_claim_ids": [], "utterance_ids": []}


def fake_encoder_for(rows_map):
    import numpy as np

    def encode(texts):
        out = []
        for index, text in enumerate(texts):
            vec = rows_map.get(text)
            if vec is None:
                vec = [0.0] * 4
                vec[index % 4] = 1.0
            array = np.asarray(vec, dtype=np.float32)
            out.append(array / (np.linalg.norm(array) or 1.0))
        return np.stack(out)
    return encode


def test_selection_suppresses_near_duplicate_in_same_chapter():
    rows = [_row("R1", 0, 10, "재료를 손질한다."), _row("R2", 20, 30, "재료를 손질한다.")]
    encode = fake_encoder_for({"재료를 손질한다.": [1.0, 0, 0, 0]})
    kept, suppressed = S.select_rows_for_report(rows, encode)
    assert [r["row_id"] for r in kept] == ["R1"]
    assert suppressed[0]["row_id"] == "R2"
    assert suppressed[0]["reason"] == S.DUPLICATE_IN_CHAPTER


def test_selection_keeps_duplicates_across_different_chapters():
    rows = [_row("R1", 0, 10, "재료를 손질한다.", chapter="CH001"),
            _row("R2", 600, 610, "재료를 손질한다.", chapter="CH009")]
    encode = fake_encoder_for({"재료를 손질한다.": [1.0, 0, 0, 0]})
    kept, suppressed = S.select_rows_for_report(rows, encode)
    assert len(kept) == 2 and suppressed == []


def test_selection_keeps_distinct_rows():
    rows = [_row("R1", 0, 10, "재료를 손질한다."), _row("R2", 20, 30, "열차를 타고 이동한다.")]
    encode = fake_encoder_for({"재료를 손질한다.": [1.0, 0, 0, 0],
                               "열차를 타고 이동한다.": [0, 1.0, 0, 0]})
    kept, suppressed = S.select_rows_for_report(rows, encode)
    assert len(kept) == 2 and suppressed == []


def test_selection_never_removes_evidence_ids():
    rows = [_row("R1", 0, 10, "재료를 손질한다."), _row("R2", 20, 30, "재료를 손질한다.")]
    rows[1]["utterance_ids"] = ["U9"]
    encode = fake_encoder_for({"재료를 손질한다.": [1.0, 0, 0, 0]})
    _kept, suppressed = S.select_rows_for_report(rows, encode)
    assert suppressed[0]["utterance_ids"] == ["U9"]


def test_selection_reports_granularity_limitation_for_long_row():
    rows = [_row("R1", 0, 700, "식재료를 구매한다.")]
    encode = fake_encoder_for({"식재료를 구매한다.": [1.0, 0, 0, 0]})
    kept, _suppressed = S.select_rows_for_report(rows, encode, long_row_sec=600.0)
    assert kept[0]["granularity_flag"] == S.REPORT_GRANULARITY_LIMITATION


def test_selection_is_stable_and_time_ordered():
    rows = [_row("R2", 50, 60, "B"), _row("R1", 0, 10, "A")]
    encode = fake_encoder_for({"A": [1.0, 0, 0, 0], "B": [0, 1.0, 0, 0]})
    kept, _ = S.select_rows_for_report(rows, encode)
    assert [r["row_id"] for r in kept] == ["R1", "R2"]


def test_selection_rejects_unknown_structure_change():
    rows = [_row("R1", 0, 10, "A")]
    encode = fake_encoder_for({"A": [1.0, 0, 0, 0]})
    kept, suppressed = S.select_rows_for_report(rows, encode)
    assert len(kept) + len(suppressed) == len(rows)      # 행을 새로 만들지 않는다

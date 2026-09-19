"""WVR_MULTIMODAL_REPORT_COMPOSER_V2 — 표시 계층 구성 규칙."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "jds_video" / "_internal"))

import wvr_report_composer_v2 as composer  # noqa: E402


def utt(uid, start, end, text):
    return {"id": uid, "start": start, "end": end, "text": text}


def episode(eid, start, end, summary, evidence=composer.VISUAL, category="관찰",
            broad_activity=(), display="VISUAL_EVIDENCE"):
    return {"episode_id": eid, "start": start, "end": end, "summary": summary,
            "evidence": evidence, "category": category,
            "broad_activity": list(broad_activity), "display": display}


# ── 보고 가치 ──────────────────────────────────────────────────────────

def test_unknown_label_becomes_unclear_and_stays_reportable():
    assert composer.normalize_reportability("뭔가이상") == composer.UNCLEAR
    assert composer.is_reportable("뭔가이상")


def test_meta_and_filler_are_not_reportable():
    assert not composer.is_reportable(composer.META_CONTENT)
    assert not composer.is_reportable(composer.FILLER)
    assert composer.is_reportable(composer.CONTENT)


def test_label_normalization_is_case_insensitive():
    assert composer.normalize_reportability("meta-content") == composer.META_CONTENT


# ── 주제 분할 ──────────────────────────────────────────────────────────

def test_unrelated_topics_split_at_real_utterance_boundaries():
    summary = "예산안 편성 방향을 보고했다. 해양 수색 절차를 설명했다."
    utterances = [utt("U1", 0, 10, "예산안 편성 방향입니다"),
                  utt("U2", 10, 20, "예산안 관련 보고입니다"),
                  utt("U3", 20, 30, "해양 수색 절차를 말씀드립니다")]
    out = composer.split_summary_by_topic(summary, utterances)
    assert len(out) == 2
    assert out[0]["utterance_ids"] == ["U1", "U2"] and out[0]["end"] == 20
    assert out[1]["utterance_ids"] == ["U3"] and out[1]["start"] == 20


def test_related_sentences_are_not_split():
    summary = "예산안을 편성했다. 예산안은 청년 지원을 담았다."
    utterances = [utt("U1", 0, 10, "예산안 편성"), utt("U2", 10, 20, "예산안 청년 지원")]
    assert len(composer.split_summary_by_topic(summary, utterances)) == 1


def test_single_sentence_never_splits():
    assert len(composer.split_summary_by_topic("한 문장이다.", [utt("U1", 0, 5, "한 문장")])) == 1


def test_split_is_skipped_when_a_topic_has_no_supporting_utterance():
    summary = "예산안을 보고했다. 해양 수색을 설명했다."
    utterances = [utt("U1", 0, 10, "예산안 보고")]
    assert len(composer.split_summary_by_topic(summary, utterances)) == 1


def test_split_is_skipped_when_spans_interleave():
    summary = "예산안을 보고했다. 수색을 설명했다."
    utterances = [utt("U1", 0, 10, "예산안"), utt("U2", 10, 20, "수색"),
                  utt("U3", 20, 30, "예산안 다시")]
    assert len(composer.split_summary_by_topic(summary, utterances)) == 1


def test_split_never_invents_text():
    summary = "예산안 편성 방향을 보고했다. 해양 수색 절차를 설명했다."
    utterances = [utt("U1", 0, 10, "예산안 편성"), utt("U2", 10, 20, "해양 수색 절차")]
    out = composer.split_summary_by_topic(summary, utterances)
    joined = " ".join(o["summary"] for o in out)
    assert set(composer.words(joined)) == set(composer.words(summary))


# ── 융합 사건 ──────────────────────────────────────────────────────────

def test_narrower_visual_gets_a_partial_scene_clause():
    clause = composer.modality_clause("지게로 물건을 옮기는", 400, 408, 300, 700)
    assert clause.startswith("일부 장면에서 확인된 내용:")


def test_coextensive_visual_gets_a_plain_clause():
    clause = composer.modality_clause("음식을 조리하는", 300, 700, 300, 700)
    assert clause.startswith("화면에서 확인된 내용:")


def test_fused_summary_keeps_both_evidence_texts():
    fused = composer.compose_fused_summary("봉사활동을 했다",
                                           composer.modality_clause("옮기는", 0, 5, 0, 10))
    assert "봉사활동을 했다" in fused and "옮기는" in fused


def test_fused_summary_without_visual_is_unchanged():
    assert composer.compose_fused_summary("봉사활동을 했다", None) == "봉사활동을 했다"


# ── 종속 화면 관찰 ─────────────────────────────────────────────────────

def test_visual_detail_with_same_activity_inside_a_visual_event_is_subordinate():
    detail = episode("RE2", 100, 108, "식재료를 담는 활동", broad_activity=["FOOD_PREPARATION"])
    container = episode("RE1", 0, 300, "식재료를 준비하고 조리하는 활동",
                        broad_activity=["FOOD_PREPARATION"])
    assert composer.is_subordinate_visual(detail, [container])[0] == \
        composer.SUBORDINATE_VISUAL_DETAIL


def test_visual_detail_with_a_different_activity_is_kept():
    detail = episode("RE2", 100, 108, "상품을 고르는 행동", broad_activity=["SHOPPING_OR_BROWSING"])
    container = episode("RE1", 0, 300, "음식을 먹는다", broad_activity=["EATING"])
    assert composer.is_subordinate_visual(detail, [container]) is None


def test_temporal_containment_alone_does_not_merge():
    detail = episode("RE2", 100, 108, "검은색 원통형 물체를 다루고 있습니다",
                     broad_activity=["WORK_OR_STUDY"])
    container = episode("RE1", 0, 300, "봉사활동을 하고 있다", evidence=composer.AUDIO,
                        category="봉사활동", broad_activity=[])
    assert composer.is_subordinate_visual(detail, [container]) is None


def test_generic_visual_inside_an_audio_event_is_folded():
    detail = episode("RE2", 100, 108, "남성이 마이크 앞에서 말하고 있습니다")
    container = episode("RE1", 0, 300, "예산안 편성 방향을 보고한다", evidence=composer.AUDIO)
    assert composer.is_subordinate_visual(detail, [container])[0] == composer.GENERIC_VISUAL_COVERED


def test_audio_episode_is_never_subordinate():
    detail = episode("RE2", 100, 108, "무언가 말한다", evidence=composer.AUDIO)
    container = episode("RE1", 0, 300, "무언가 말한다", evidence=composer.AUDIO)
    assert composer.is_subordinate_visual(detail, [container]) is None


# ── 전사 덩어리 ────────────────────────────────────────────────────────

def test_discourse_opener_marks_transcript_row():
    assert composer.looks_like_transcript("그렇지만 행안부 차원에서 어쨌든 그쪽은 어렵다")


def test_short_report_sentence_is_not_transcript():
    assert not composer.looks_like_transcript("예산안 편성 방향을 보고했다.")


def test_compression_drops_leading_discourse_sentence():
    text = "그렇지만 어쨌든 그쪽은 어렵다. 목포 서부 지역 지원 방안을 상의하기로 했다."
    out = composer.compress_transcript_text(text)
    assert out["compressed"] and out["text"].startswith("목포")


def test_compression_never_adds_words():
    text = "그러니까 그 안타까움이 있다. 중앙정부 차원에서 지원을 검토한다."
    out = composer.compress_transcript_text(text)
    assert set(composer.words(out["text"])) <= set(composer.words(text))


def test_compression_keeps_something_even_when_all_sentences_open_with_markers():
    out = composer.compress_transcript_text("그러니까 어렵다.")
    assert out["text"]


# ── 불확실 고유명사 ────────────────────────────────────────────────────

def test_term_only_in_low_confidence_utterances_is_flagged():
    utterances = [utt("U1", 0, 5, "수고반전관리는 성수품을 공급한다"),
                  utt("U2", 5, 10, "성수품 공급을 확대한다")]
    states = {"U1": "ASR_LOW_CONFIDENCE", "U2": "ASR_NORMAL"}
    found = composer.uncertain_terms("수고반전관리는 성수품 공급을 확대한다", utterances, states,
                                     ("ASR_LOW_CONFIDENCE",))
    # 조사가 붙은 형태 그대로 잡는다 — 형태소 분석을 쓰지 않는다(한계는 결과 문서에 적는다).
    assert found == ["수고반전관리는"]


def test_term_present_in_reliable_utterances_is_not_flagged():
    utterances = [utt("U1", 0, 5, "성수품 공급"), utt("U2", 5, 10, "성수품 공급")]
    states = {"U1": "ASR_LOW_CONFIDENCE", "U2": "ASR_NORMAL"}
    assert composer.uncertain_terms("성수품 공급", utterances, states,
                                    ("ASR_LOW_CONFIDENCE",)) == []


# ── 제목·개요 근거 ─────────────────────────────────────────────────────

def test_title_claim_without_support_is_rejected():
    episodes = [episode("RE1", 0, 10, "봉사활동을 했다", category="봉사활동")]
    audit = composer.audit_title("주부의 겨울철 봉사활동", episodes)
    assert audit["usable"] is False
    assert any("주부의" in c["unsupported_words"] for c in audit["title_claims"])


def test_supported_title_passes():
    episodes = [episode("RE1", 0, 10, "봉사활동을 했다", category="봉사활동"),
                episode("RE2", 10, 20, "조리를 했다", category="조리")]
    audit = composer.audit_title("봉사활동 · 조리", episodes)
    assert audit["usable"] and audit["title_claims"][0]["supported_by"] == ["RE1"]


def test_prominence_word_needs_repeated_evidence():
    episodes = [episode("RE1", 0, 10, "예산안을 보고했다", category="예산")]
    assert composer.prominence_violations("대통령이 국정을 주도한다", episodes)


def test_prominence_word_is_allowed_when_evidence_repeats():
    episodes = [episode("RE1", 0, 10, "회의를 주도했다"), episode("RE2", 10, 20, "논의를 주도했다")]
    assert composer.prominence_violations("회의를 주도한다", episodes) == []


def test_overview_sentence_without_support_is_unusable():
    episodes = [episode("RE1", 0, 10, "예산안을 보고했다", category="예산")]
    records = composer.audit_overview("예산안을 보고한다. 우주 탐사선을 발사한다.", episodes)
    assert records[0]["usable"] and not records[1]["usable"]
    assert records[0]["sentence_id"] == "S01"


# ── 구분 ───────────────────────────────────────────────────────────────

def test_approved_category_is_used_when_supported():
    out = composer.choose_episode_category("봉사활동", "봉사활동을 하고 있다", [], composer.AUDIO)
    assert out["category"] == "봉사활동"


def test_uncertain_term_is_blocked_from_category():
    out = composer.choose_episode_category("수고반전관리", "수고반전관리가 공급한다",
                                           ["FOOD_PREPARATION"], composer.AUDIO,
                                           blocked_terms=("수고반전관리",))
    assert out["category"] != "수고반전관리"


def test_visual_category_falls_back_to_activity_label():
    out = composer.choose_episode_category("관찰 장면", "식재료를 조리하는 활동",
                                           ["FOOD_PREPARATION"], composer.VISUAL)
    assert out["category"] == "조리"


def test_importance_marks_fused_event_major():
    episodes = [{"start": 0, "end": 10, "evidence": composer.VISUAL_AUDIO, "display": "GENERATIVE"},
                {"start": 0, "end": 4, "evidence": composer.VISUAL, "display": "VISUAL_EVIDENCE"},
                {"start": 0, "end": 300, "evidence": composer.AUDIO, "display": "GENERATIVE"}]
    levels = composer.assign_importance(episodes)
    assert levels[0] == composer.MAJOR and levels[2] == composer.MAJOR
    assert levels[1] == composer.MINOR


def test_approved_category_does_not_need_lexical_support():
    out = composer.choose_episode_category("경제 정책", "물가 상승과 민생 어려움을 논의했다",
                                           [], composer.AUDIO, approved=True)
    assert out["category"] == "경제 정책"


def test_blocked_category_falls_back_even_when_approved():
    out = composer.choose_episode_category("수고반전관리", "수고반전관리가 공급한다", [],
                                           composer.AUDIO, blocked_terms=("수고반전관리",),
                                           approved=True)
    assert out["category"] == composer.NEUTRAL_SPEECH


def test_continuation_sentence_does_not_start_a_new_topic():
    summary = "연탄 봉사활동을 하러 갔다. 또한, 만두집에서 만두를 먹었다."
    utterances = [utt("U1", 0, 10, "연탄 봉사활동"), utt("U2", 10, 20, "만두집 만두")]
    assert len(composer.split_summary_by_topic(summary, utterances)) == 1


def test_identical_overlapping_visual_rows_keep_the_longer_one():
    short = episode("RE1", 24, 32, "사람이 빵과 토마토를 준비하고 있습니다")
    long_row = episode("RE2", 27, 76, "사람이 빵과 토마토를 준비하고 있습니다")
    assert composer.is_subordinate_visual(short, [long_row])[0] == composer.DUPLICATE_OVERLAP
    assert composer.is_subordinate_visual(long_row, [short]) is None


# ── 융합 무결성 ────────────────────────────────────────────────────────

def test_frozen_link_is_read_not_decided():
    event = {"relations": [{"speech_event_id": "SP005", "relation": "COMPLEMENTARY"},
                           {"speech_event_id": "SP009", "relation": "INDEPENDENT"}]}
    assert composer.has_frozen_link(event, "SP005")
    assert not composer.has_frozen_link(event, "SP009")
    assert not composer.has_frozen_link({"relations": []}, "SP005")


def test_visual_outside_episode_span_is_temporal_error():
    ep = {"episode_id": "RE1", "start": 27.7, "end": 76.2, "evidence": composer.VISUAL,
          "visual_event_ids": ["V1"], "speech_event_ids": [], "frozen_link": False}
    out = composer.audit_episode(ep, {"V1": (24.0, 32.0)})
    assert out["status"] == composer.EPISODE_TEMPORAL_ERROR


def test_visual_attached_without_relation_is_provenance_error():
    ep = {"episode_id": "RE1", "start": 0.0, "end": 100.0, "evidence": composer.VISUAL,
          "visual_event_ids": ["V1"], "speech_event_ids": ["SP1"], "frozen_link": False}
    out = composer.audit_episode(ep, {"V1": (10.0, 20.0)})
    assert out["status"] == composer.EPISODE_PROVENANCE_ERROR


def test_fused_episode_with_relation_is_grounded():
    ep = {"episode_id": "RE1", "start": 0.0, "end": 100.0, "evidence": composer.VISUAL_AUDIO,
          "visual_event_ids": ["V1"], "speech_event_ids": ["SP1"], "frozen_link": True}
    assert composer.audit_episode(ep, {"V1": (10.0, 20.0)})["status"] == composer.EPISODE_GROUNDED


def test_visual_audio_label_without_relation_fails():
    ep = {"episode_id": "RE1", "start": 0.0, "end": 100.0, "evidence": composer.VISUAL_AUDIO,
          "visual_event_ids": ["V1"], "speech_event_ids": ["SP1"], "frozen_link": False}
    assert composer.audit_episode(ep, {"V1": (10.0, 20.0)})["status"] == \
        composer.EPISODE_PROVENANCE_ERROR


def test_pure_audio_episode_is_grounded():
    ep = {"episode_id": "RE1", "start": 0.0, "end": 100.0, "evidence": composer.AUDIO,
          "visual_event_ids": [], "speech_event_ids": ["SP1"], "frozen_link": False}
    assert composer.audit_episode(ep, {})["status"] == composer.EPISODE_GROUNDED


def test_clause_provenance_marks_the_visual_sentence():
    clause = "일부 장면에서 확인된 내용: 음식을 접시에 담는다."
    summary = "봉사활동을 하고 있다. " + clause
    out = composer.clause_provenance(summary, clause, composer.VISUAL_AUDIO)
    assert out[0]["evidence"] == composer.CLAUSE_VISUAL_AUDIO
    assert out[1]["evidence"] == composer.CLAUSE_VISUAL


def test_uncertain_clause_is_dropped_not_rewritten():
    out = composer.drop_uncertain_clauses(
        "홍제역 근처의 바이소에서 강판을 샀다. 만두집에서 만두를 먹었다.", ["바이소에서"])
    assert "바이소" not in out["text"] and "만두" in out["text"]
    assert len(out["removed"]) == 1


def test_uncertain_clause_drop_keeps_something():
    out = composer.drop_uncertain_clauses("바이소에서 샀다.", ["바이소에서"])
    assert out["text"] and out["removed"] == []


def test_narrative_overview_reads_as_a_flow():
    episodes = [episode("RE1", 0, 60, "a", category="조리"),
                episode("RE2", 60, 120, "b", category="이동"),
                episode("RE3", 120, 180, "c", category="봉사활동")]
    text, evidence = composer.narrative_overview(episodes)
    assert text == "조리에서 시작해 이동을 거쳐 봉사활동으로 이어진다."
    assert evidence[0]["report_episode_ids"] == ["RE1", "RE2", "RE3"]


def test_narrative_overview_skips_generic_categories():
    episodes = [episode("RE1", 0, 60, "a", category=composer.NEUTRAL_VISUAL),
                episode("RE2", 60, 120, "b", category="이동"),
                episode("RE3", 120, 180, "c", category="봉사활동")]
    text, _ = composer.narrative_overview(episodes)
    assert composer.NEUTRAL_VISUAL not in text


def test_rounding_difference_is_not_a_temporal_error():
    ep = {"episode_id": "RE1", "start": 48.01, "end": 56.02, "evidence": composer.VISUAL,
          "visual_event_ids": ["V1"], "speech_event_ids": [], "frozen_link": False}
    assert composer.audit_episode(ep, {"V1": (48.0146, 56.0226)})["status"] == \
        composer.EPISODE_GROUNDED


def test_overview_particle_matches_final_consonant():
    episodes = [episode("RE1", 0, 60, "a", category="조리"),
                episode("RE2", 60, 120, "b", category="이동"),
                episode("RE3", 120, 180, "c", category="저녁 메뉴")]
    text, _ = composer.narrative_overview(episodes)
    assert text.endswith("저녁 메뉴로 이어진다.") and "메뉴으로" not in text


def test_flow_sampling_keeps_both_ends():
    """길이가 모두 같아 순위를 못 가릴 때 쓰는 보조 경로 — 앞뒤를 모두 남긴다."""
    names = ["C%d" % i for i in range(10)]
    picked = composer._sample_flow(names, 4)
    assert picked[0] == "C0" and picked[-1] == "C9" and len(picked) == 4


def test_overview_keeps_the_longest_activities_in_time_order():
    episodes = [episode("RE1", 0, 10, "a", category="짧은 것"),
                episode("RE2", 10, 400, "b", category="긴 것"),
                episode("RE3", 400, 800, "c", category="더 긴 것")]
    text, _ = composer.narrative_overview(episodes, limit=2)
    assert "짧은 것" not in text and text.startswith("긴 것에서 시작해")

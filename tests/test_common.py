import json, pytest
from pathlib import Path
import common

def _doc(n=3, dur=14.0, extra=None):
    segs = []
    for i in range(n):
        s = {"idx": i, "start": i * 5, "end": min(i * 5 + 5, dur)}
        if extra:
            s.update(extra)
        segs.append(s)
    return {"video_id": "v1", "duration_sec": dur, "fps": 30.0,
            "n_segments": n, "segments": segs}

def test_load_segments_ok(tmp_path):
    p = tmp_path / "segments.json"
    common.atomic_write_json(p, _doc())
    doc = common.load_segments(p)
    assert doc["n_segments"] == 3

def test_load_segments_rejects_broken_idx(tmp_path):
    d = _doc(); d["segments"][2]["idx"] = 5          # 연속성 위반
    p = tmp_path / "segments.json"; common.atomic_write_json(p, d)
    with pytest.raises(ValueError, match="idx"):
        common.load_segments(p)

def test_load_segments_rejects_start_invariant(tmp_path):
    d = _doc(); d["segments"][1]["start"] = 7        # start = idx*5 위반
    p = tmp_path / "segments.json"; common.atomic_write_json(p, d)
    with pytest.raises(ValueError, match="start"):
        common.load_segments(p)

def test_load_segments_seg_len_parameterized(tmp_path):
    # seg_len_sec이 5가 아닌 실험(예: ablation 3초)도 하드코딩 없이 검증 가능해야 함
    d = _doc(n=3, dur=9.0)
    for i, s in enumerate(d["segments"]):
        s["start"] = i * 3; s["end"] = min(i * 3 + 3, 9.0)
    p = tmp_path / "segments.json"; common.atomic_write_json(p, d)
    doc = common.load_segments(p, seg_len=3)
    assert doc["n_segments"] == 3
    with pytest.raises(ValueError, match="start"):   # seg_len 안 맞으면 여전히 잡아야 함
        common.load_segments(p, seg_len=5)

def test_load_segments_missing_field_names_module(tmp_path):
    p = tmp_path / "segments.json"; common.atomic_write_json(p, _doc())
    with pytest.raises(ValueError, match="m2_keyframe"):
        common.load_segments(p, require=["rep_frame"])
    with pytest.raises(ValueError, match="m3_generate"):
        common.load_segments(p, require=["caption"])

def test_is_corrupted_caption_flags_non_korean_script():
    assert common.is_corrupted_caption(
        "一架米色的直升機停在一片草地和樹林之間，背景是清澈的藍天。")
    assert not common.is_corrupted_caption("한 남성이 숲속 길을 걸어가는 장면이다.")

def test_is_corrupted_caption_flags_word_repetition():
    assert common.is_corrupted_caption("계단 위에는 계단 위에는 계단 위에는 계단 위에는 계단 위에는")
    assert not common.is_corrupted_caption("")

def test_is_corrupted_caption_flags_partial_mixing():
    # 부분 혼입(비율 < 0.2)도 절대 개수(>=3)로 감지 — 실데이터 Wilderness idx=31
    # "카모フラ주제 재킷…나무가满了 숲속" 유형 [리뷰 2026-07-11 Major]
    assert common.is_corrupted_caption(
        "3일차, 남성은 흰색 모자와 카모フラ주제 재킷을 입고 나무가满了 숲속에서 웃으며 채팅합니다.")
    # 2자 이하 혼입은 통과(고유명사·간판 표기 여지)
    assert not common.is_corrupted_caption(
        "남성이 中자가 적힌 간판 아래에서 이야기하는 장면이다.")

def test_is_corrupted_caption_flags_phrase_repetition():
    # 3어절 이상 구(句) 연속 반복은 단일 토큰 빈도로 못 잡는다 [리뷰 2026-07-11 Major]
    assert common.is_corrupted_caption("한 남자가 걷고 있다 " * 4)
    assert common.is_corrupted_caption("계단위에는" * 7)          # 공백 없는 반복
    assert not common.is_corrupted_caption(
        "한 남자가 파란 재킷을 입고 눈 덮인 산길을 천천히 걸어 내려오는 장면이다.")

def test_atomic_write_and_config(tmp_path):
    p = tmp_path / "x.json"
    common.atomic_write_json(p, {"a": 1})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}
    cfg = common.load_config(Path(__file__).parents[1] / "config.yaml")
    assert cfg["seg_len_sec"] == 5 and cfg["alpha_tiebreak"] == "larger"


def test_truncate_to_sentence():
    # 8-3(b) 미완결 문장 절단: 마지막 완결 문장 경계까지만
    assert common.truncate_to_sentence(
        "남성이 걷는다. 배경에 나무가 보이고 그는 갑자기") == "남성이 걷는다."
    assert common.truncate_to_sentence(
        "요리를 한다! 접시에 담는다") == "요리를 한다!"
    # 이미 완결이면 그대로
    assert common.truncate_to_sentence("완결된 문장이다.") == "완결된 문장이다."
    # 경계 문자가 없으면(전체가 미완결) 원문 유지 — 신호 소실 방지
    assert common.truncate_to_sentence("경계 없는 조각") == "경계 없는 조각"
    assert common.truncate_to_sentence("") == ""


def test_strip_residual_cjk():
    # 8-3(c) 잔여 한자·가나 제거(음차 아님) + 공백 정규화
    assert common.strip_residual_cjk("책架 앞의 남성") == "책 앞의 남성"
    assert common.strip_residual_cjk("카모フラ주 재킷") == "카모주 재킷"
    assert common.strip_residual_cjk("정상 한국어 캡션") == "정상 한국어 캡션"


def test_postprocess_caption_off_by_default():
    # 플래그 없으면 원문 그대로, caption_raw 미생성 (현행 동작 불변)
    clean, raw = common.postprocess_caption("남성이 걷는다. 배경에 나무가", {})
    assert clean == "남성이 걷는다. 배경에 나무가"
    assert raw is None


def test_postprocess_caption_applies_when_enabled():
    cfg = {"caption_truncate_incomplete": True, "caption_normalize_cjk": True}
    clean, raw = common.postprocess_caption("책架에서 걷는다. 그리고 갑자기", cfg)
    assert clean == "책에서 걷는다."          # CJK 제거 + 미완결 절단
    assert raw == "책架에서 걷는다. 그리고 갑자기"   # 원문 보존
    # 변화 없으면 caption_raw 불필요
    clean2, raw2 = common.postprocess_caption("정상 문장이다.", cfg)
    assert clean2 == "정상 문장이다." and raw2 is None

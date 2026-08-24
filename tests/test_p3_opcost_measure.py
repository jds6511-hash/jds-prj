"""p3_opcost_v1 실측 도구 — 계약 테스트 (GPU 없이 도는 부분만).

이 도구는 **캡션 문자열을 저장하지 않는다.** 내용을 남기면 GT·프롬프트 조정 통로가
열린다. 길이와 토큰 수만 남긴다. 검색·평가 경로는 import조차 하지 않는다.
"""
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import p3_opcost_measure as M     # noqa: E402


# ---- 프레임 동결 -----------------------------------------------------------

def test_frame_selection_is_deterministic(tmp_path):
    a = M.select_frames(n=12, seed=M.SEED)
    b = M.select_frames(n=12, seed=M.SEED)
    assert a == b and len(a) == 12


def test_frame_selection_changes_with_seed():
    assert M.select_frames(n=12, seed=1) != M.select_frames(n=12, seed=2)


def test_frame_selection_spreads_across_videos():
    frames = M.select_frames(n=20, seed=M.SEED)
    vids = {Path(f).parent.parent.name for f in frames}
    assert len(vids) >= 3


def test_frame_selection_uses_no_content_signal():
    """정렬 키에 캡션·자막·검색 결과가 들어가지 않는다."""
    src = (ROOT / "scripts" / "p3_opcost_measure.py").read_text(encoding="utf-8")
    fn = [n for n in ast.walk(ast.parse(src))
          if isinstance(n, ast.FunctionDef) and n.name == "select_frames"][0]
    body = ast.dump(fn)
    for bad in ("caption", "subtitle", "segments.json", "rr_", "rank", "score"):
        assert bad not in body, bad


def test_freeze_refuses_overwrite(tmp_path):
    p = tmp_path / "frames.json"
    M.freeze_frames(n=4, out=p)
    with pytest.raises(M.MeasureError):
        M.freeze_frames(n=4, out=p)


def test_freeze_records_config_and_commit(tmp_path):
    p = tmp_path / "frames.json"
    doc = M.freeze_frames(n=4, out=p)
    for k in ("frames", "n", "seed", "commit", "protocol", "vlm_max_pixels",
              "vlm_max_new_tokens", "vlm_rep_penalty", "quantized",
              "frozen_at"):
        assert k in doc, k
    assert doc["protocol"] == "p3_opcost_v1"
    assert doc["quantized"] is True          # 양 arm 배포 정밀도(4bit)


# ---- arm 설정 --------------------------------------------------------------

def test_arm_config_swaps_only_caption_model():
    base = M.arm_config("3b")
    cand = M.arm_config("4b")
    assert base["caption_model"] == M.ARM_MODEL["3b"]
    assert cand["caption_model"] == M.ARM_MODEL["4b"]
    diff = {k for k in set(base) | set(cand) if base.get(k) != cand.get(k)}
    assert diff == {"caption_model"}


def test_both_arms_are_4bit():
    for arm in ("3b", "4b"):
        assert M.arm_config(arm)["vlm_4bit"] is True


def test_unknown_arm_refused():
    with pytest.raises(M.MeasureError):
        M.arm_config("7b")


# ---- 교대 배치 -------------------------------------------------------------

def test_block_order_alternates():
    assert M.block_order(blocks=2) == ["3b", "4b", "3b", "4b"]
    assert M.block_order(blocks=1) == ["3b", "4b"]


def test_block_order_rejects_zero():
    with pytest.raises(M.MeasureError):
        M.block_order(blocks=0)


# ---- 캡션 내용 비저장 ------------------------------------------------------

def test_summarize_keeps_only_length_and_tokens():
    r = M.summarize_output("어떤 문장이 들어와도", n_tokens=7)
    assert set(r) == {"chars", "n_tokens"}
    assert r["chars"] == len("어떤 문장이 들어와도")


def test_module_never_stores_caption_text():
    src = (ROOT / "scripts" / "p3_opcost_measure.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # 결과 dict에 텍스트를 담는 키가 없어야 한다
    keys = {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for bad in ("caption", "text", "sample", "samples", "output_text"):
        assert bad not in keys, bad


def test_module_does_not_import_search_or_eval():
    src = (ROOT / "scripts" / "p3_opcost_measure.py").read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not ({"m4_index", "m5_search", "m6_evaluate", "p2_retrieve",
                 "p2_evaluate", "p2_label_intake"} & mods)


def test_module_does_not_write_into_work_index():
    src = (ROOT / "scripts" / "p3_opcost_measure.py").read_text(encoding="utf-8")
    assert "segments.json" not in src
    assert "meta.json" not in src


# ---- 결과 스키마 -----------------------------------------------------------

def test_result_schema_declares_required_provenance():
    for k in ("model_id", "model_revision", "dtype_effective",
              "quantized_effective", "attn_implementation", "vlm_max_pixels",
              "vlm_max_new_tokens", "vlm_rep_penalty", "torch", "transformers",
              "gpu", "vram_total_gb", "commit"):
        assert k in M.PROVENANCE_FIELDS, k


def test_result_schema_declares_cost_fields():
    for k in ("load_sec_median", "vram_after_load_gb", "vram_peak_gb",
              "sec_per_frame_median", "sec_per_frame_mean", "n_frames",
              "n_failures", "oom", "model_storage_bytes"):
        assert k in M.COST_FIELDS, k


def test_stage_names_are_limited():
    assert M.STAGES == ("canary", "full")
    with pytest.raises(M.MeasureError):
        M.out_path("bogus")


def test_canary_and_full_write_different_files():
    assert M.out_path("canary") != M.out_path("full")


def test_measure_refuses_without_frozen_frames(tmp_path):
    with pytest.raises(M.MeasureError):
        M.load_frozen(tmp_path / "nope.json")


def test_frozen_frames_must_exist_on_disk(tmp_path):
    p = tmp_path / "frames.json"
    p.write_text(json.dumps({"protocol": "p3_opcost_v1", "n": 1, "seed": 1,
                             "frames": ["work/nope/frames/seg_9999.jpg"]}),
                 encoding="utf-8")
    with pytest.raises(M.MeasureError):
        M.load_frozen(p)


# ---- 보고표 ----------------------------------------------------------------

def _block(arm, block, spf, peak, reserved, free, loads, chars, tokens):
    return {"arm": arm, "block": block,
            "provenance": {"model_id": f"m-{arm}", "model_revision": "rev",
                           "dtype_effective": "torch.bfloat16",
                           "quantized_effective": True,
                           "quantization_mismatch": False,
                           "vram_total_gb": 6.0,
                           "vram_free_at_start_gb": 5.0},
            "cost": {"sec_per_frame_median": spf, "vram_peak_gb": peak,
                     "vram_peak_reserved_gb": reserved,
                     "vram_min_free_gb": free, "load_sec_all": loads,
                     "n_frames": 39, "n_frames_attempted": 40,
                     "n_failures": 0, "oom": False,
                     "out_chars_mean": chars, "out_tokens_mean": tokens}}


def _doc():
    blocks = [_block("3b", 0, 7.4, 2.4, 3.1, 2.6, [11.0, 10.5, 10.8], 107.0, 85.0),
              _block("4b", 1, 5.7, 3.0, 3.8, 1.9, [12.5, 12.0, 12.2], 78.0, 58.0),
              _block("3b", 2, 7.6, 2.4, 3.1, 2.6, [10.9, 10.7, 10.6], 107.0, 85.0),
              _block("4b", 3, 5.8, 3.0, 3.8, 1.9, [12.1, 12.3, 12.0], 78.0, 58.0)]
    per = {}
    for arm in ("3b", "4b"):
        rows = [b for b in blocks if b["arm"] == arm]
        import statistics as st
        per[arm] = {
            "blocks": len(rows),
            "sec_per_frame_median_of_blocks": st.median(
                [r["cost"]["sec_per_frame_median"] for r in rows]),
            "n_failures": 0, "oom": False,
            "out_chars_mean": rows[0]["cost"]["out_chars_mean"],
            "out_tokens_mean": rows[0]["cost"]["out_tokens_mean"],
            "model_storage_bytes": 7 * 1024 ** 3}
    return {"stage": "full", "block_order": ["3b", "4b", "3b", "4b"],
            "blocks": blocks, "per_arm": per, "caption_text_stored": False}


def test_summary_reports_per_block_values():
    s = M.summary(_doc())
    a = s["arms"]["3b"]
    assert a["sec_per_frame_median_per_block"] == [7.4, 7.6]
    assert a["vram_peak_reserved_gb_per_block"] == [3.1, 3.1]
    assert a["minimum_generation_free_vram_gb_per_block"] == [2.6, 2.6]
    assert a["load_sec_per_block"] == [[11.0, 10.5, 10.8], [10.9, 10.7, 10.6]]


def test_summary_reports_completion_counts():
    a = M.summary(_doc())["arms"]["4b"]
    assert a["n_frames_attempted"] == [40, 40]
    assert a["n_frames_timed"] == [39, 39]


def test_summary_reports_block_drift():
    assert M.summary(_doc())["arms"]["3b"]["block_drift_sec_per_frame"] == 0.2


def test_summary_ratio_is_candidate_over_base():
    r = M.summary(_doc())["ratio"]
    assert r["sec_per_frame_candidate_over_base"] == round(5.75 / 7.5, 4)
    assert r["vram_peak_reserved_delta_gb"] == 0.7


def test_summary_separates_token_rate_from_frame_time():
    """frame당 빠른 것이 연산 효율인지 짧은 출력인지 가른다."""
    s = M.summary(_doc())
    b, c = s["arms"]["3b"], s["arms"]["4b"]
    assert b["end_to_end_output_tokens_per_sec"] == round(85.0 / 7.5, 3)
    assert c["end_to_end_output_tokens_per_sec"] == round(58.0 / 5.75, 3)
    assert s["ratio"][
        "end_to_end_output_tokens_per_sec_candidate_over_base"] is not None


def test_token_rate_field_names_its_scope():
    """분모가 전체 wall-clock임을 이름과 주석에 박는다 — decoder 속도가 아니다."""
    s = M.summary(_doc())
    assert "tokens_per_sec" not in s["arms"]["3b"]
    note = s["token_rate_scope_note"]
    assert "wall-clock" in note and "decoder" in note


def test_summary_declares_free_vram_scope():
    s = M.summary(_doc())
    assert s["free_vram_sampling_scope"] == "generation_loop_only"
    assert "load" in s["free_vram_scope_note"]
    assert s["order_effect_rule"]


def test_summary_carries_wording_and_grade_rules():
    s = M.summary(_doc())
    assert s["measurement_grade"] and s["wording_rule"] and s["headroom_note"]
    assert "통계적 모집단 추정이 아니다" in s["measurement_grade"]


def test_summary_keeps_quantization_evidence():
    a = M.summary(_doc())["arms"]["4b"]
    assert a["quantized_effective"] is True
    assert a["quantization_mismatch"] is False


def test_frozen_protocol_name_is_checked(tmp_path):
    p = tmp_path / "frames.json"
    p.write_text(json.dumps({"protocol": "other", "n": 0, "seed": 1,
                             "frames": []}), encoding="utf-8")
    with pytest.raises(M.MeasureError):
        M.load_frozen(p)

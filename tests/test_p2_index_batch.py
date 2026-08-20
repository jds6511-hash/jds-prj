"""P2 두 arm 색인 배치 — config 생성 · 단계 순서 · 검증 훅.

이 배치가 지켜야 하는 것은 성능이 아니라 **비교 가능성**이다. 사전등록
`부호역전_확증_보충2` §2가 고정한 것은 두 arm이 프롬프트·프레임·자막·평가자까지
같고 **모델만 다르다**는 조건이다. 그래서 아래를 코드로 막는다.

1. 변형 config는 `config.yaml`에서 재생성한다 (손으로 고치지 않는다)
2. 두 arm의 `paths.work`·`results`가 **본 인덱스와 서로** 갈린다
3. 프롬프트는 두 arm 동일 — arm이 바꾸는 것은 `caption_model`뿐이다
4. 정밀도는 양쪽 4bit (배포 경로) — PRIMARY 정의가 그렇다
5. 프레임과 자막은 한 번만 만들어 **복제**한다 (생성 흔들림이 arm 차이로 오독되지 않게)
6. m3 → m4 순서를 건너뛰지 않는다
7. 검증 훅이 구간 수를 사전등록값과 대조한다 (재현 게이트)
"""
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "hooks"))
import p2_index_batch as B                                        # noqa: E402
import p2_index_hook as H                                         # noqa: E402


# ---- 1~4. config 생성 -------------------------------------------------

def test_arms_are_frozen_to_the_preregistration():
    assert set(B.ARMS) == {"3b", "4b"}
    assert B.ARMS["3b"]["caption_model"] == "Qwen/Qwen2.5-VL-3B-Instruct"
    assert B.ARMS["4b"]["caption_model"] == "Qwen/Qwen3-VL-4B-Instruct"
    # PRIMARY는 **배포 경로 정밀도(4bit)로 양쪽을** 잰다
    assert all(a["vlm_4bit"] is True for a in B.ARMS.values())
    assert B.PRIMARY.startswith("Δ_deploy")


def test_configs_are_regenerated_from_the_main_config(tmp_path):
    base = {"caption_model": "X", "vlm_4bit": False, "caption_prompt": "P0-텍스트",
            "seg_len_sec": 5, "paths": {"data": "data", "work": "work",
                                        "results": "results"}}
    src = tmp_path / "config.yaml"
    src.write_text(yaml.safe_dump(base, allow_unicode=True), encoding="utf-8")
    out = B.make_configs(src, tmp_path, stage="full")
    assert set(out) == {"3b", "4b"}
    cfgs = {k: yaml.safe_load(Path(v).read_text(encoding="utf-8"))
            for k, v in out.items()}
    for arm, c in cfgs.items():
        assert c["caption_model"] == B.ARMS[arm]["caption_model"]
        assert c["vlm_4bit"] is True
        assert c["seg_len_sec"] == 5                  # 본 config에서 상속된다
        assert c["caption_prompt"] == "P0-텍스트"      # 프롬프트는 손대지 않는다
    # 프롬프트가 두 arm에서 같다 — arm이 바꾸는 것은 모델뿐이다
    assert cfgs["3b"]["caption_prompt"] == cfgs["4b"]["caption_prompt"]


def test_paths_are_isolated_from_the_deployed_index(tmp_path):
    base = {"caption_model": "X", "vlm_4bit": True, "caption_prompt": "p",
            "paths": {"data": "data", "work": "work", "results": "results"}}
    src = tmp_path / "config.yaml"
    src.write_text(yaml.safe_dump(base, allow_unicode=True), encoding="utf-8")
    out = B.make_configs(src, tmp_path, stage="full")
    works, results = set(), set()
    for arm, p in out.items():
        c = yaml.safe_load(Path(p).read_text(encoding="utf-8"))
        assert c["paths"]["work"] not in ("work",)
        assert c["paths"]["results"] not in ("results",)
        assert c["paths"]["data"] == "data"           # 입력 영상은 공용이다
        works.add(c["paths"]["work"]); results.add(c["paths"]["results"])
    assert len(works) == 2 and len(results) == 2      # arm끼리도 갈린다


def test_canary_paths_do_not_collide_with_full(tmp_path):
    base = {"caption_model": "X", "vlm_4bit": True, "caption_prompt": "p",
            "paths": {"data": "data", "work": "work", "results": "results"}}
    src = tmp_path / "config.yaml"
    src.write_text(yaml.safe_dump(base, allow_unicode=True), encoding="utf-8")
    full = B.make_configs(src, tmp_path, stage="full")
    can = B.make_configs(src, tmp_path, stage="canary")
    fw = yaml.safe_load(Path(full["3b"]).read_text(encoding="utf-8"))["paths"]["work"]
    cw = yaml.safe_load(Path(can["3b"]).read_text(encoding="utf-8"))["paths"]["work"]
    assert fw != cw, "CANARY 산출물이 FULL 자리에 들어가면 안 된다"


# ---- 5~6. 단계 순서와 복제 -------------------------------------------

def test_stage_order_puts_m4_after_m3():
    order = [s["name"] for s in B.STAGES]
    # 기준 arm이 STT·캡션을 먼저 만들고(m3_base), 그 자막을 복제한 뒤 후보 arm이
    # 캡션만 만든다 — `--subtitles-only`는 캡션 없는 인덱스에서 거부된다(8-5(7))
    assert order.index("mirror_frames") > order.index("m3_base")
    assert order.index("m3_captions") > order.index("mirror_frames")
    assert order.index("m4_index") > order.index("m3_captions")


def test_stt_runs_once_and_only_the_candidate_arm_recaptions():
    by = {s["name"]: s for s in B.STAGES}
    assert by["m3_base"]["arms"] == (B.BASE_ARM,), "STT는 기준 arm에서 1회만 돈다"
    assert B.BASE_ARM not in by["m3_captions"]["arms"], \
        "기준 arm 캡션을 두 번 만들면 같은 arm에서 생성이 두 판본 생긴다"
    assert by["m3_captions"]["extra"] == ["--captions-only"]
    assert set(by["m4_index"]["arms"]) == set(B.ARMS)


def test_frames_and_subtitles_are_mirrored_not_regenerated(tmp_path):
    a = tmp_path / "wa" / "v"; a.mkdir(parents=True)
    (a / "segments.json").write_text(
        json.dumps({"video_id": "v", "n_segments": 1,
                    "segments": [{"idx": 0, "start": 0, "end": 5,
                                  "rep_frame": "frames/seg_0000.jpg",
                                  "subtitle": "말", "caption": "3B가 쓴 캡션"}]}),
        encoding="utf-8")
    (a / "frames").mkdir(); (a / "frames" / "seg_0000.jpg").write_bytes(b"jpg")
    (a / "audio.wav").write_bytes(b"wav")
    (a / "stt_cache.json").write_text("{}", encoding="utf-8")
    b = tmp_path / "wb"
    B.mirror(a, b / "v")
    doc = json.loads((b / "v" / "segments.json").read_text(encoding="utf-8"))
    assert (b / "v" / "frames" / "seg_0000.jpg").read_bytes() == b"jpg"
    assert (b / "v" / "stt_cache.json").exists()
    assert doc["segments"][0]["subtitle"] == "말"     # 자막은 그대로 옮긴다
    # **캡션은 옮기지 않는다** — arm마다 새로 만든다
    assert not doc["segments"][0].get("caption")


def test_mirror_refuses_to_clobber_existing_captions(tmp_path):
    a = tmp_path / "wa" / "v"; a.mkdir(parents=True)
    (a / "segments.json").write_text(
        json.dumps({"video_id": "v", "n_segments": 1,
                    "segments": [{"idx": 0, "start": 0, "end": 5,
                                  "rep_frame": "f.jpg", "subtitle": "s"}]}),
        encoding="utf-8")
    b = tmp_path / "wb" / "v"; b.mkdir(parents=True)
    (b / "segments.json").write_text(
        json.dumps({"video_id": "v", "n_segments": 1,
                    "segments": [{"idx": 0, "start": 0, "end": 5,
                                  "caption": "이미 생성된 4B 캡션"}]}),
        encoding="utf-8")
    with pytest.raises(B.BatchError, match="캡션"):
        B.mirror(a, b)


def test_canary_uses_one_video_and_full_uses_the_whole_sample():
    sel = json.loads((ROOT / "docs" / "P2_선정표본_2026-08-20.json")
                     .read_text(encoding="utf-8"))["selected"]
    assert len(B.video_ids(sel, stage="full")) == 35
    can = B.video_ids(sel, stage="canary")
    assert len(can) == 1
    # 가장 짧은 영상을 쓴다 — 전 경로를 돌리면서 GPU를 가장 적게 쓴다
    smallest = min(sel, key=lambda r: r["n_segments"])["source_id"]
    assert can == [smallest]


# ---- 7. 검증 훅 -------------------------------------------------------

def _run(tmp_path, segs=3, cap=True, arms=("3b", "4b"), same_prompt=True,
         sub_same=True):
    rows = {}
    for i, arm in enumerate(arms):
        rows[arm] = {
            "videos": {"v1": {
                "n_segments": segs,
                "expected_n_segments": 3,
                "captions_nonempty": segs if cap else 0,
                "subtitle_sha256": "s1" if (sub_same or i == 0) else "s2",
                "text_hash_matches_meta": True,
                "emb_shapes": {"emb_sub": [segs, 1024], "emb_cap": [segs, 1024]},
                "provenance_present": True,
            }},
            "caption_provenance": {
                "model_id": B.ARMS[arm]["caption_model"],
                "quantized": True,
                "prompt_sha256": "p1" if (same_prompt or i == 0) else "p2",
                "attn_implementation": "sdpa",
            }}
    return {"stage": "FULL", "arms": rows}


def test_hook_passes_a_clean_run(tmp_path):
    (tmp_path / "p2_index_batch_run_full.json").write_text(
        json.dumps(_run(tmp_path), ensure_ascii=False), encoding="utf-8")
    ok, checks = H.check(tmp_path)
    assert ok is True, checks
    assert checks["segments_match_preregistered"] is True
    assert checks["prompt_identical_across_arms"] is True
    assert checks["subtitles_identical_across_arms"] is True


def test_hook_fails_when_segment_count_drifts(tmp_path):
    r = _run(tmp_path, segs=4)          # 사전등록값 3과 다르다
    (tmp_path / "p2_index_batch_run_full.json").write_text(
        json.dumps(r, ensure_ascii=False), encoding="utf-8")
    ok, checks = H.check(tmp_path)
    assert ok is False and checks["segments_match_preregistered"] is False


def test_hook_fails_when_prompt_differs_between_arms(tmp_path):
    (tmp_path / "p2_index_batch_run_full.json").write_text(
        json.dumps(_run(tmp_path, same_prompt=False), ensure_ascii=False),
        encoding="utf-8")
    ok, checks = H.check(tmp_path)
    assert ok is False and checks["prompt_identical_across_arms"] is False


def test_hook_fails_when_subtitles_differ_between_arms(tmp_path):
    (tmp_path / "p2_index_batch_run_full.json").write_text(
        json.dumps(_run(tmp_path, sub_same=False), ensure_ascii=False),
        encoding="utf-8")
    ok, checks = H.check(tmp_path)
    assert ok is False and checks["subtitles_identical_across_arms"] is False


def test_hook_fails_on_empty_captions(tmp_path):
    (tmp_path / "p2_index_batch_run_full.json").write_text(
        json.dumps(_run(tmp_path, cap=False), ensure_ascii=False),
        encoding="utf-8")
    ok, checks = H.check(tmp_path)
    assert ok is False and checks["captions_complete"] is False


def test_hook_fails_when_an_arm_is_missing(tmp_path):
    (tmp_path / "p2_index_batch_run_full.json").write_text(
        json.dumps(_run(tmp_path, arms=("3b",)), ensure_ascii=False),
        encoding="utf-8")
    ok, checks = H.check(tmp_path)
    assert ok is False and checks["both_arms_present"] is False


def test_hook_fails_when_an_arm_ran_unquantized(tmp_path):
    r = _run(tmp_path)
    r["arms"]["4b"]["caption_provenance"]["quantized"] = False
    (tmp_path / "p2_index_batch_run_full.json").write_text(
        json.dumps(r, ensure_ascii=False), encoding="utf-8")
    ok, checks = H.check(tmp_path)
    assert ok is False and checks["both_arms_quantized"] is False


def test_hook_fails_when_a_model_id_is_not_the_declared_one(tmp_path):
    r = _run(tmp_path)
    r["arms"]["4b"]["caption_provenance"]["model_id"] = "Qwen/Qwen3-VL-8B-Instruct"
    (tmp_path / "p2_index_batch_run_full.json").write_text(
        json.dumps(r, ensure_ascii=False), encoding="utf-8")
    ok, checks = H.check(tmp_path)
    assert ok is False and checks["model_ids_as_declared"] is False


def test_hook_reports_no_verdict_words():
    """훅은 조건을 검사한다 — 채택·성능 판정을 하지 않는다."""
    src = (ROOT / "scripts" / "hooks" / "p2_index_hook.py").read_text(
        encoding="utf-8").split('"""', 2)[2]
    for bad in ("adopt", "채택", "우세", "significant"):
        assert bad not in src, bad


# ---- stage별 산출물 이름 ------------------------------------------------

def test_output_name_is_stage_scoped():
    """CANARY와 FULL이 같은 run_id를 공유한다 — 이름이 갈리지 않으면 서로를 막거나
    1편짜리 CANARY 결과가 FULL 결과 행세를 한다."""
    src = (ROOT / "scripts" / "p2_index_batch.py").read_text(encoding="utf-8")
    assert 'p2_index_batch_run_{a.stage}.json' in src
    plan = json.loads((ROOT / "docs" / "planning" / "p2_index_plan.json")
                      .read_text(encoding="utf-8"))
    assert plan["canary_expected_files"] == ["p2_index_batch_run_canary.json"]
    assert plan["full_expected_files"] == ["p2_index_batch_run_full.json"]
    assert plan["expected_files"] == plan["full_expected_files"]


def test_hook_prefers_the_full_report_when_both_exist(tmp_path):
    can = _run(tmp_path, segs=4)          # CANARY: 사전등록값과 다른 구간 수
    full = _run(tmp_path, segs=3)         # FULL: 정상
    (tmp_path / "p2_index_batch_run_canary.json").write_text(
        json.dumps(can, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "p2_index_batch_run_full.json").write_text(
        json.dumps(full, ensure_ascii=False), encoding="utf-8")
    ok, checks = H.check(tmp_path)
    assert ok is True, checks           # canary 파일을 집었다면 FAIL이 났을 것이다

"""P2 질의 intake — **동결된 배정표를 입력 양식으로 펼치는 것뿐이다.**

여기서 고정하는 것은 라벨 품질이 아니라 **오염 경로와 배정 불변성**이다.

```
배정 source of truth  docs/P2_질의쿼터_2026-08-20.json 하나
사람이 채우는 것       text · gt_start · gt_end (+선택 note)
자동 파생             gt_seg_idx = common.derive_gt_seg_idx만
자동으로 안 하는 것    본 질의 파일 병합 · 검색 · 평가 · 캡션·자막 참조
```

`m5_search`·`m6_evaluate`·`frame_human_kit`을 **import조차 하지 않는다**(절대규칙 3).
제시 항목을 순위로 고르면 선정 자체가 오염이므로, 관행이 아니라 테스트가 막는다.
"""
import ast
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import common                                                    # noqa: E402
import p2_label_intake as I                                      # noqa: E402

SRC = (ROOT / "scripts" / "p2_label_intake.py").read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    """docstring을 떼고 **실행되는 코드만** 남긴다.

    금지 항목을 문서에 설명하는 것과 실제로 건드리는 것은 다르다 — 이 모듈의
    docstring은 "`segments.json`을 열지 않는다"고 적고 있어서 문자열 검색만 하면
    자기 설명에 걸린다.
    """
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)


# ---------------------------------------------------------------- 오염 경로

@pytest.mark.parametrize("mod", ["m5_search", "m6_evaluate", "frame_human_kit"])
def test_forbidden_modules_are_not_imported(mod):
    assert f"import {mod}" not in SRC and mod not in CODE


@pytest.mark.parametrize("token", ["caption", "score", "rank", "results",
                                   "segments.json", "work_dir"])
def test_model_output_is_never_touched(token):
    """`segments.json`을 열지도 않는다 — allowlist 필터보다 강한 조건이다."""
    assert token not in CODE


def test_does_not_write_the_official_query_file():
    assert "data/queries" not in CODE and "queries.jsonl" not in CODE


# ---------------------------------------------------------------- 배정 불변성

def test_allocation_is_exactly_35_videos_times_9():
    rows = I.load_allocation()
    assert len(rows) == 315
    per_video = {}
    for r in rows:
        per_video[r["video_id"]] = per_video.get(r["video_id"], 0) + 1
    assert len(per_video) == 35
    assert set(per_video.values()) == {9}


def test_type_totals_match_the_frozen_quota():
    rows = I.load_allocation()
    got = {}
    for r in rows:
        got[r["query_type"]] = got.get(r["query_type"], 0) + 1
    assert got == {"복합형": 111, "자막형": 79, "장면형": 125}


def test_per_video_type_counts_match_the_quota_file():
    quota = json.loads(I.QUOTA.read_text(encoding="utf-8"))["per_video_quota"]
    rows = I.load_allocation()
    for vid, want in quota.items():
        got = {}
        for r in rows:
            if r["video_id"] == vid:
                got[r["query_type"]] = got.get(r["query_type"], 0) + 1
        assert got == {I.TYPE_KO[k]: v for k, v in want.items() if v}, vid


def test_query_ids_are_unique_and_deterministic():
    a = I.load_allocation()
    b = I.load_allocation()
    ids = [r["query_id"] for r in a]
    assert len(set(ids)) == 315
    assert [r["query_id"] for r in b] == ids
    assert [r["query_type"] for r in b] == [r["query_type"] for r in a]


def test_make_emits_blank_human_columns(tmp_path):
    p = tmp_path / "intake.csv"
    I.make(p)
    rows = list(csv.DictReader(p.read_text(encoding="utf-8-sig").splitlines()))
    assert len(rows) == 315
    assert list(rows[0].keys()) == list(I.COLUMNS)
    assert all(not r["text"] and not r["gt_start"] and not r["gt_end"]
               for r in rows)


# ---------------------------------------------------------------- build 검증

def _filled(tmp_path, mutate=None):
    """배정 전량을 최소 유효값으로 채운 CSV. `mutate(rows)`로 한 행만 망친다."""
    rows = [{**r, "text": f"{r['query_id']} 질의", "gt_start": "10",
             "gt_end": "20", "note": ""} for r in I.load_allocation()]
    if mutate:
        mutate(rows)
    p = tmp_path / "filled.csv"
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(I.COLUMNS))
        w.writeheader()
        w.writerows(rows)
    return p


def test_build_derives_gt_seg_idx_with_the_shared_rule(tmp_path):
    out = I.build(_filled(tmp_path))
    assert len(out) == 315
    seg_len = common.load_config(ROOT / "config.yaml")["seg_len_sec"]
    n = I.n_segments_of()
    for r in out:
        assert r["gt_seg_idx"] == common.derive_gt_seg_idx(
            r["gt_start"], r["gt_end"], n[r["video_id"]], seg_len)
        assert r["split"] == "p2" and r["split"] != "test"


def test_build_refuses_a_changed_query_type(tmp_path):
    def swap(rows):
        rows[0]["query_type"] = "장면형" if rows[0]["query_type"] != "장면형" \
            else "자막형"
    with pytest.raises(I.IntakeError, match="query_type"):
        I.build(_filled(tmp_path, swap))


@pytest.mark.parametrize("col", ["text", "gt_start", "gt_end"])
def test_build_refuses_an_empty_cell(tmp_path, col):
    with pytest.raises(I.IntakeError, match="비어"):
        I.build(_filled(tmp_path, lambda rows: rows[3].update({col: ""})))


def test_build_refuses_reversed_or_zero_length_span(tmp_path):
    with pytest.raises(I.IntakeError, match="gt_start < gt_end"):
        I.build(_filled(tmp_path,
                        lambda rows: rows[5].update({"gt_start": "30",
                                                     "gt_end": "30"})))


def test_build_refuses_a_span_past_the_video(tmp_path):
    """영상 길이는 사전등록된 선정표본에서 읽는다 — 서버 산출물을 보지 않는다."""
    with pytest.raises(I.IntakeError, match="영상 길이"):
        I.build(_filled(tmp_path,
                        lambda rows: rows[7].update({"gt_end": "999999"})))


# ------------------------------------------------- 기확보 4편의 실제 영상 길이

FREE4 = ("baekmansonghee_jirisan", "jissi_farm", "pland_costco_hosting",
         "softyeon_ceramics")


def test_recorded_duration_is_used_when_present():
    """31편은 선정표본에 duration_sec이 있다 — 파일을 다시 재지 않는다."""
    b = I.time_bound_of(5)
    sample = I._sample()
    for vid, rec in sample.items():
        if rec.get("duration_sec") is not None:
            assert b[vid] == rec["duration_sec"]


def test_free4_bound_is_measured_not_the_loose_grid(monkeypatch):
    """`n_segments × 5`는 실제 길이의 상한이라 한 구간만큼 느슨하다.

    사람이 영상 끝보다 뒤의 gt_end를 적어도 통과할 수 있었다 — 그 구멍을 닫는다.
    """
    nseg = I.n_segments_of()
    fake = {vid: (nseg[vid] - 1) * 5 + 2.0 for vid in FREE4}   # 마지막 구간 2초
    monkeypatch.setattr(I, "_measure_duration",
                        lambda p: fake[Path(p).stem])
    b = I.time_bound_of(5)
    for vid in FREE4:
        assert b[vid] == fake[vid] < nseg[vid] * 5


def test_free4_measurement_must_match_the_preregistered_grid(monkeypatch):
    """재본 길이가 사전등록 n_segments와 다른 격자를 만들면 멈춘다."""
    monkeypatch.setattr(I, "_measure_duration", lambda p: 10.0)
    with pytest.raises(I.IntakeError, match="n_segments"):
        I.time_bound_of(5)


def test_missing_free4_file_fails_closed(monkeypatch, tmp_path):
    """파일이 없으면 느슨한 상한으로 조용히 내려가지 않는다."""
    monkeypatch.setattr(I, "VIDEOS", tmp_path)
    with pytest.raises(I.IntakeError, match="영상 파일이 없다"):
        I.time_bound_of(5)


def test_measurement_uses_the_same_path_as_m1():
    """cv2 frame_count/fps다 — ffprobe duration이 아니다(격자가 어긋난다)."""
    src = (ROOT / "scripts" / "p2_label_intake.py").read_text(encoding="utf-8")
    assert "CAP_PROP_FRAME_COUNT" in src and "CAP_PROP_FPS" in src


def test_build_refuses_a_moved_video(tmp_path):
    """질의를 다른 영상으로 옮기면 배정이 조용히 바뀐다 — 거부한다."""
    with pytest.raises(I.IntakeError, match="video_id가 배정과 다르다"):
        I.build(_filled(tmp_path,
                        lambda rows: rows[9].update({"video_id": "nope"})))


def test_build_refuses_an_unknown_query_id(tmp_path):
    with pytest.raises(I.IntakeError, match="배정에 없다"):
        I.build(_filled(tmp_path,
                        lambda rows: rows[9].update({"query_id": "p2_x_q01"})))


@pytest.mark.parametrize("mutate", [lambda rows: rows.pop(),
                                    lambda rows: rows.append(dict(rows[0]))])
def test_build_refuses_partial_or_oversized_submission(tmp_path, mutate):
    with pytest.raises(I.IntakeError, match="315"):
        I.build(_filled(tmp_path, mutate))


def test_build_refuses_a_duplicated_query_id_at_full_count(tmp_path):
    """행 수는 맞는데 하나가 중복이면 다른 하나가 빠진 것이다."""
    with pytest.raises(I.IntakeError, match="중복"):
        I.build(_filled(tmp_path,
                        lambda rows: rows.__setitem__(4, dict(rows[3]))))


def test_build_refuses_an_unknown_type_label(tmp_path):
    with pytest.raises(I.IntakeError, match="유형"):
        I.build(_filled(tmp_path,
                        lambda rows: rows[11].update({"query_type": "행동형"})))


def test_write_staging_does_not_touch_the_official_file(tmp_path):
    official = ROOT / "data" / "queries" / "queries.jsonl"
    before = official.read_bytes()
    out = I.build(_filled(tmp_path))
    p = tmp_path / "staging.jsonl"
    I.write_jsonl(out, p)
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 315
    assert json.loads(lines[0])["split"] == "p2"
    assert official.read_bytes() == before

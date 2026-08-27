"""M8 REDESIGN ROUND 1 — R1·R2·R5·R6.

가장 중요한 것은 **baseline이 그대로 재현되는가**다. 기본 인자로 부르면
공식 실행과 같은 프롬프트·같은 경로여야 한다 — 아니면 비교의 baseline이 사라진다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import m8_report as R                                              # noqa: E402


def segs(n, start=0):
    return [{"idx": start + i, "start": (start + i) * 5.0,
             "end": (start + i) * 5.0 + 5, "subtitle": f"발화{i}",
             "caption": f"화면{i}", "rep_frame": "f.jpg"} for i in range(n)]


def llm_events(per_chunk=2, empty_for=()):
    """청크 범위를 읽어 사건을 낸다. `empty_for` 범위 크기에는 빈 배열을 낸다."""
    calls = []

    def gen(prompt, **kw):
        import re
        m = re.search(r"seg#(\d+)부터 seg#(\d+)", prompt)
        lo, hi = (int(m.group(1)), int(m.group(2))) if m else (0, 5)
        calls.append((lo, hi))
        if (hi - lo + 1) in empty_for:
            return "[]"
        step = max((hi - lo + 1) // per_chunk, 1)
        out = []
        for k in range(per_chunk):
            a = lo + k * step
            b = min(a + step - 1, hi)
            if a > b:
                break
            out.append({"event": f"사건{a}", "span": [a, b],
                        "evidence_segments": [a],
                        "description": f"seg {a}에서 사람이 무언가를 오래 한다"})
        return json.dumps(out, ensure_ascii=False)
    gen.calls = calls
    return gen


# ---------------------------------------------------------------- baseline 불변

def test_default_prompt_is_the_frozen_one():
    """기본 인자는 공식 실행과 같은 규칙이어야 한다."""
    p = R.build_event_prompt(segs(3))
    assert R._EVENT_RULES in p
    assert R.EVENT_RULES_V2 not in p


def test_v2_rules_only_when_asked():
    p = R.build_event_prompt(segs(3), rules=R.EVENT_RULES_V2)
    assert R.EVENT_RULES_V2 in p and R._EVENT_RULES not in p


def test_default_structured_run_has_no_split_provenance():
    rep = R.generate_report_structured(segs(60), llm_events(), 60, 5)
    assert rep.get("chunk_splits") in (None, [])


# ---------------------------------------------------------------- R1·R2 계약

def test_v2_rules_state_both_directions():
    """짧은 건 살리고 긴 건 찢지 않는다 — **한 프롬프트에 양방향**이 있어야 한다."""
    t = R.EVENT_RULES_V2
    assert "짧" in t and "보존" in t
    assert "과분할" in t or "쪼개" in t
    assert "주요 행동" in t or "주 행동" in t


def test_v2_rules_do_not_leak_panel_gt_wording():
    """소비된 N=8의 GT 문구를 프롬프트 예시로 복사하지 않는다."""
    t = R.EVENT_RULES_V2
    for gt in ("호박순", "타코야끼", "비닐하우스", "왕릉", "거제", "지리산",
               "아그네스", "한복", "발굴현장"):
        assert gt not in t


def test_v2_requires_korean_event_title():
    """R6 — 사건명도 한국어."""
    assert "한국어" in R.EVENT_RULES_V2


def test_v2_does_not_add_similarity_threshold():
    """R2를 fuzzy merge로 풀지 않는다 — 임베딩·유사도 임계 금지."""
    src = (ROOT / "src" / "m8_report.py").read_text(encoding="utf-8")
    for banned in ("cosine", "similarity", "embed_merge", "merge_judge"):
        assert banned not in src


def test_merge_semantics_unchanged():
    """기존 deterministic merge를 건드리지 않았다."""
    e = {"event": "가", "span": [0, 5], "evidence_segments": [0],
         "description": "가나다"}
    f = {"event": "가", "span": [6, 9], "evidence_segments": [6],
         "description": "라마바"}
    g = {"event": "나", "span": [0, 5], "evidence_segments": [0],
         "description": "사아자"}
    assert len(R.merge_events([dict(e), dict(f)])) == 1     # 이름 같고 인접 → 병합
    assert len(R.merge_events([dict(e), dict(g)])) == 2     # 이름 다르면 유지


# ---------------------------------------------------------------- R5 분할 재시도

def test_split_retry_halves_the_chunk_once():
    """60구간이 두 번 비면 30+30으로 한 번만 쪼갠다."""
    llm = llm_events(empty_for=(60,))
    rep = R.generate_report_structured(segs(60), llm, 60, 5, split_retry=True)
    widths = [hi - lo + 1 for lo, hi in llm.calls]
    assert widths[:2] == [60, 60]              # 최초 + 재생성
    assert 30 in widths                        # 절반으로 재시도
    assert rep["chunk_splits"] and rep["chunk_splits"][0]["chunk"] == 0
    assert rep["events"], "분할로 사건을 건졌어야 한다"


def test_split_retry_is_one_level_only():
    """30도 비면 15로 더 쪼개지 않는다 — 무한 분할 금지."""
    llm = llm_events(empty_for=(60, 30))
    rep = R.generate_report_structured(segs(60), llm, 60, 5, split_retry=True)
    widths = [hi - lo + 1 for lo, hi in llm.calls]
    assert 15 not in widths
    assert rep["chunk_splits"][0]["recovered"] is False
    assert rep["chunk_splits"][0]["halves"] == 2


def test_split_retry_off_by_default():
    llm = llm_events(empty_for=(60,))
    R.generate_report_structured(segs(60), llm, 60, 5)
    assert all(hi - lo + 1 == 60 for lo, hi in llm.calls)


def test_split_records_provenance_even_when_recovered():
    llm = llm_events(empty_for=(60,))
    rep = R.generate_report_structured(segs(60), llm, 60, 5, split_retry=True)
    s = rep["chunk_splits"][0]
    assert set(s) >= {"chunk", "halves", "recovered", "events_from_split"}
    assert s["recovered"] is True and s["events_from_split"] > 0


def test_split_does_not_run_when_retry_succeeds():
    llm = llm_events()          # 첫 시도부터 성공
    rep = R.generate_report_structured(segs(60), llm, 60, 5, split_retry=True)
    assert rep["chunk_splits"] == []


# ---------------------------------------------------------------- dev 러너 경계

def test_dev_runner_never_writes_canonical_report():
    src = (ROOT / "scripts" / "m8_redesign_dev.py").read_text(encoding="utf-8")
    assert '"report.json"' not in src and "/ 'report.json'" not in src
    assert "m8_redesign_dev" in src


def test_dev_runner_declares_run_kind():
    import m8_redesign_dev as D
    assert D.RUN_KIND == "m8_redesign_dev"


# ---------------------------------------------------------------- 비교 도구

def test_compare_labels_scores_as_development_not_confirmation():
    import m8_redesign_compare as C
    rows = {"v": {"alignment": 0.8, "compression": 1.0, "c1_status": "ABSENT"}}
    s = C.panel_dev_scores(rows)
    assert s["is_confirmation"] is False
    assert set(s) >= {"dev_c1_present_videos", "dev_c2_median_alignment",
                      "dev_c3_max_compression"}
    for k in s:
        assert not k.startswith("C1") and not k.startswith("C2")


def test_compare_never_writes_official_paths():
    src = (ROOT / "scripts" / "m8_redesign_compare.py").read_text(encoding="utf-8")
    assert "m8_official_result" not in src
    assert 'work' in src and 'report.json' in src          # baseline은 읽는다
    assert "atomic_write_json" not in src                  # 자기 산출물만 write_text


def test_compare_metrics_cover_the_four_failure_axes():
    import m8_redesign_compare as C
    rep = {"sentences": [{"sent_id": 0, "text": "가", "cites": [0]}],
           "events": [{"event": "가", "span": [0, 4], "evidence_segments": [0],
                       "description": "가나다"}],
           "rejected": [], "map_raw_outputs": ["[]"], "chunk_retries": [],
           "chunk_splits": []}
    m = C.metrics(rep, [{"event": "GT", "span": [0, 4]}], 10)
    for k in ("unmatched_gt", "unmatched_gt_short", "unmatched_generated",
              "alignment", "compression", "rejections", "zero_event_chunks",
              "chunk_splits", "non_korean_event_titles", "span_coverage"):
        assert k in m


def test_compare_refuses_when_baseline_is_not_official(tmp_path):
    """baseline lineage가 안 맞으면 비교를 시작하지 않는다."""
    import m8_redesign_compare as C
    (tmp_path / "v1").mkdir()
    (tmp_path / "v1" / "report.json").write_text("{}", encoding="utf-8")
    lin = tmp_path / "lineage.json"
    lin.write_text(json.dumps({"report_sha256": {"v1": "0" * 64}}), encoding="utf-8")
    cfg = {"paths": {"work": str(tmp_path)}}
    with pytest.raises(C.LineageError):
        C.check_baseline_lineage(cfg, ["v1"], lineage_path=lin)


def test_compare_lineage_passes_on_real_official_reports():
    import m8_redesign_compare as C
    import common as CM
    from m8_gates import panel_videos as PV
    cfg = CM.load_config(str(ROOT / "config.yaml"))
    out = C.check_baseline_lineage(cfg, PV())
    assert out["all_match"] is True and out["checked"] == 8

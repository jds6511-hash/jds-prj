"""P2 AI 초안 — **프롬프트를 결과 전에 고정하고, 생성 경로를 두지 않는다.**

```
고정        PROMPT_TEMPLATE 해시 하나. 행마다 채워도 해시가 흔들리지 않는다
동결 정합    query_id·video_id·query_type을 바꾸는 초안은 거부
금지 필드    caption · retrieval · rank · score · arm · 3b · 4b · embedding · index
음성 없으면  자막형·복합형은 초안을 만들지 않고 requires_human_audio로 보낸다
생성        이 모듈에 없다 — 별도 승인 사건이다
```
"""
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_ai_draft as D                                            # noqa: E402

SRC = (ROOT / "scripts" / "p2_ai_draft.py").read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and ast.get_docstring(node):
            node.body = node.body[1:]
    return ast.unparse(tree)


CODE = _code_only(SRC)
ALLOC = [{"query_id": "p2_v0_q01", "video_id": "v0", "query_type": "장면형"},
         {"query_id": "p2_v0_q02", "video_id": "v0", "query_type": "자막형"},
         {"query_id": "p2_v0_q03", "video_id": "v0", "query_type": "복합형"},
         {"query_id": "p2_v1_q01", "video_id": "v1", "query_type": "장면형"}]
DUR = {"v0": 100.0, "v1": 60.0}


def _draft(qid="p2_v0_q01", vid="v0", t="장면형", **kw):
    row = {"query_id": qid, "video_id": vid, "query_type": t,
           "draft_text": "철판에 반죽 붓는 장면", "draft_gt_start": 12.0,
           "draft_gt_end": 18.5, "ai_model": "some-vlm",
           "prompt_sha256": D.prompt_sha256(),
           "generated_at": "2026-08-24T12:00:00"}
    row.update(kw)
    return row


# ------------------------------------------------------------- 프롬프트 고정

def test_prompt_hash_is_one_value_independent_of_the_row():
    h = D.prompt_sha256()
    assert len(h) == 64
    a = D.prompt_for("장면형", "p2_v0_q01", "v0", 20, 100.0)
    b = D.prompt_for("자막형", "p2_v0_q02", "v0", 20, 100.0)
    assert a != b
    assert D.prompt_sha256() == h          # 채워 넣어도 템플릿 해시는 그대로


def test_the_prompt_forbids_inference_from_system_outputs():
    p = D.prompt_for("장면형", "p2_v0_q01", "v0", 20, 100.0)
    for word in ("검색 시스템", "캡션 모델", "임베딩", "색인", "검색 결과", "순위",
                 "점수"):
        assert word in p
    assert "초안" in p and "사람이 원본 영상을 직접 보고 확정" in p


def test_the_prompt_carries_the_frozen_type_definition():
    for t, frag in (("자막형", "말소리에 답이 있다"),
                    ("장면형", "화면에 답이 있다"),
                    ("복합형", "발화와 화면 양쪽")):
        assert frag in D.prompt_for(t, "q", "v", 10, 50.0)


def test_the_prompt_contains_no_human_label_example():
    """기존 human-only 라벨을 few-shot으로 넣지 않는다."""
    p = D.PROMPT_TEMPLATE
    assert "few-shot" not in p.lower()
    assert "예시" not in p and "이렇게 썼" not in p


def test_an_unknown_type_is_refused():
    with pytest.raises(D.DraftError, match="유형"):
        D.prompt_for("행동형", "q", "v", 10, 50.0)


# ------------------------------------------------------------- 대상 선정

def test_pending_rows_exclude_what_the_human_already_finished():
    got = D.pending_rows(["p2_v0_q01"], allocation=ALLOC)
    assert [r["query_id"] for r in got] == ["p2_v0_q02", "p2_v0_q03",
                                            "p2_v1_q01"]


def test_pending_rows_read_no_label_content():
    """완료 판정은 query_id 목록으로만 들어온다 — 내용이 인자에 없다."""
    import inspect
    src = inspect.getsource(D.pending_rows)
    for token in ("text", "gt_start", "gt_end", "note"):
        assert token not in src


def test_without_audio_speech_types_go_to_the_human():
    el = D.eligibility(ALLOC, audio_supported=False)
    assert el["draftable"] == ["p2_v0_q01", "p2_v1_q01"]
    assert el["requires_human_audio"] == ["p2_v0_q02", "p2_v0_q03"]
    assert el["n_draftable"] == 2 and el["n_requires_human"] == 2


def test_with_audio_every_type_is_draftable():
    el = D.eligibility(ALLOC, audio_supported=True)
    assert el["requires_human_audio"] == [] and el["n_draftable"] == 4


def test_without_video_nothing_is_draftable():
    el = D.eligibility(ALLOC, audio_supported=True, video_supported=False)
    assert el["n_draftable"] == 0 and el["n_requires_human"] == 4


def test_audio_required_types_are_the_speech_ones():
    assert set(D.AUDIO_REQUIRED_TYPES) == {"자막형", "복합형"}


# ------------------------------------------------------------- 초안 검증

def test_a_valid_draft_passes():
    by_id = {r["query_id"]: r for r in ALLOC}
    assert D.validate_draft(_draft(), by_id, DUR)["query_id"] == "p2_v0_q01"


@pytest.mark.parametrize("field", ["query_id", "draft_text", "draft_gt_start",
                                   "ai_model", "prompt_sha256"])
def test_a_missing_field_is_refused(field):
    by_id = {r["query_id"]: r for r in ALLOC}
    row = _draft()
    del row[field]
    with pytest.raises(D.DraftError, match="누락|없다"):
        D.validate_draft(row, by_id, DUR)


@pytest.mark.parametrize("key", ["caption", "rank", "score", "arm", "3b", "4b",
                                 "retrieval", "embedding", "index", "mrr"])
def test_a_forbidden_field_is_refused(key):
    by_id = {r["query_id"]: r for r in ALLOC}
    with pytest.raises(D.DraftError, match="미허용 필드|금지 필드"):
        D.validate_draft(_draft(**{key: "x"}), by_id, DUR)


@pytest.mark.parametrize("key,val", [("video_id", "v1"),
                                     ("query_type", "자막형")])
def test_frozen_identity_cannot_be_changed(key, val):
    by_id = {r["query_id"]: r for r in ALLOC}
    with pytest.raises(D.DraftError, match=key):
        D.validate_draft(_draft(**{key: val}), by_id, DUR)


def test_an_unknown_query_id_is_refused():
    by_id = {r["query_id"]: r for r in ALLOC}
    with pytest.raises(D.DraftError, match="동결 배정"):
        D.validate_draft(_draft(qid="p2_zz_q99"), by_id, DUR)


def test_a_reversed_span_is_refused():
    by_id = {r["query_id"]: r for r in ALLOC}
    with pytest.raises(D.DraftError, match="draft_gt_start"):
        D.validate_draft(_draft(draft_gt_start=20, draft_gt_end=20), by_id, DUR)


def test_a_span_past_the_video_is_refused():
    by_id = {r["query_id"]: r for r in ALLOC}
    with pytest.raises(D.DraftError, match="영상 길이"):
        D.validate_draft(_draft(draft_gt_end=200), by_id, DUR)


def test_an_empty_draft_text_is_refused():
    by_id = {r["query_id"]: r for r in ALLOC}
    with pytest.raises(D.DraftError, match="draft_text"):
        D.validate_draft(_draft(draft_text="  "), by_id, DUR)


def test_a_drifted_prompt_hash_is_refused():
    by_id = {r["query_id"]: r for r in ALLOC}
    with pytest.raises(D.DraftError, match="prompt_sha256"):
        D.validate_draft(_draft(prompt_sha256="f" * 64), by_id, DUR)


def test_optional_audit_fields_are_allowed():
    by_id = {r["query_id"]: r for r in ALLOC}
    row = _draft(rationale="12초에 철판 등장", evidence_seg_idx=2,
                 ai_provider="x", ai_model_version="1", settings={"t": 0})
    assert D.validate_draft(row, by_id, DUR)


def test_duplicate_drafts_are_refused():
    with pytest.raises(D.DraftError, match="중복"):
        D.validate_all([_draft(), _draft()], allocation=ALLOC, durations=DUR)


# ------------------------------------------------------------- 산출물

def test_write_drafts_freezes_and_reports_its_hash(tmp_path):
    p = tmp_path / "drafts.jsonl"
    meta = D.write_drafts([_draft(), _draft(qid="p2_v1_q01", vid="v1")], p,
                          allocation=ALLOC, durations=DUR)
    assert meta["n_drafts"] == 2 and len(meta["sha256"]) == 64
    assert meta["prompt_sha256"] == D.prompt_sha256()
    assert len(D.load_drafts(p)) == 2


def test_write_drafts_refuses_to_overwrite(tmp_path):
    p = tmp_path / "drafts.jsonl"
    D.write_drafts([_draft()], p, allocation=ALLOC, durations=DUR)
    with pytest.raises(D.DraftError, match="이미 있다"):
        D.write_drafts([_draft()], p, allocation=ALLOC, durations=DUR)


def test_an_invalid_batch_writes_nothing(tmp_path):
    p = tmp_path / "drafts.jsonl"
    with pytest.raises(D.DraftError):
        D.write_drafts([_draft(), _draft(qid="p2_zz_q99")], p,
                       allocation=ALLOC, durations=DUR)
    assert not p.exists()


def test_load_drafts_on_a_missing_file_is_empty(tmp_path):
    assert D.load_drafts(tmp_path / "nope.jsonl") == []


def test_the_draft_artifact_is_separate_from_the_final_gt():
    assert "p2_ai_assist" in str(D.DRAFTS)
    assert "p2_label_intake" not in str(D.DRAFTS)


# ------------------------------------------------------------- 경계

def test_there_is_no_generation_entry_point():
    """생성은 이 모듈에 없다 — 별도 승인 사건이다."""
    for token in ("requests", "urllib.request", "openai", "anthropic",
                  "httpx", "generate(", "call_model"):
        assert token not in CODE


def _imported(src: str) -> set:
    out = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


@pytest.mark.parametrize("mod", ["p2_retrieve", "p2_evaluate", "m5_search",
                                 "m6_evaluate", "frame_human_kit", "m4_index"])
def test_it_imports_no_retrieval_or_evaluation_module(mod):
    assert mod not in _imported(SRC)


def test_the_evidence_lists_are_declared():
    assert "source_video" in D.EVIDENCE_ALLOWED
    assert "contact_sheet" in D.EVIDENCE_ALLOWED
    assert "burned_in_on_screen_text" in D.EVIDENCE_ALLOWED
    for f in ("caption_3b", "caption_4b", "pipeline_subtitle_stt", "rank",
              "score", "arm_identity", "existing_human_labels"):
        assert f in D.EVIDENCE_FORBIDDEN


def test_it_does_not_read_segments_json_or_the_work_tree():
    for token in ("segments.json", "work_p2", "emb_cap", "meta.json"):
        assert token not in CODE

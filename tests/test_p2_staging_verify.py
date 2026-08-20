"""P2 표집틀 검증 — staging에서 입력을 **검증하고 고르는** 단계.

사전등록 보충4 §1. 막는 것 여섯.
1. production이 아닌 함수로 세그먼트 수를 재는 것 (production은 cv2 기반이다)
2. 재현 게이트를 통과하지 않고 신규 파일 판정으로 넘어가는 것
3. 다운로드 실패를 `segment_ineligible`로 적는 것
4. 배포 경로(`data/videos/`·`work/`)에 쓰는 것 — 승격은 승인 ②다
5. `achieved_k`가 상한 `c`를 넘거나 `target_k`를 넘는 것
6. 캡션·검색·모델 산출물이 이 모듈에 들어오는 것
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import p2_staging_verify as S                                    # noqa: E402


# ---- production 규칙 -----------------------------------------------------

def test_bounds_and_cap_are_frozen():
    assert S.SEG_LEN == 5
    assert S.TARGET_SEGMENTS == (150, 400)
    assert S.TARGET_K == 35
    assert S.C_CAP == 0.80


def test_probe_opens_the_file_once_and_derives_both(monkeypatch):
    """duration과 n_segments가 같은 호출에서 나와야 한다 — 두 번 열면 갈릴 수 있다."""
    calls = []
    monkeypatch.setattr(S.M, "get_video_info",
                        lambda p: (calls.append(str(p)), (912.4, 30.0))[1])
    assert S.probe("x.mp4") == (912.4, 183)
    assert len(calls) == 1


def test_segment_count_uses_the_production_functions(monkeypatch):
    """production은 cv2 프레임수/fps다 — 별도 파서로 재구현하지 않는다."""
    calls = []

    def fake(path):
        calls.append(str(path))
        return 912.4, 30.0

    monkeypatch.setattr(S.M, "get_video_info", fake)
    assert S.production_n_segments("x.mp4") == 183
    assert calls == ["x.mp4"]


def test_segment_count_matches_m1_assert(monkeypatch):
    """m1_preprocess.py:54의 assert와 같은 값이어야 한다."""
    import math
    for d in (750.0, 912.4, 1055.2, 1974.9, 2000.0):
        monkeypatch.setattr(S.M, "get_video_info", lambda p, d=d: (d, 30.0))
        assert S.production_n_segments("x") == math.ceil(d / 5)


def test_eligibility_is_inclusive_at_both_bounds():
    assert S.classify_segments(150) == "verified_eligible"
    assert S.classify_segments(400) == "verified_eligible"
    assert S.classify_segments(149) == "segment_ineligible"
    assert S.classify_segments(401) == "segment_ineligible"


# ---- 재현 게이트 ---------------------------------------------------------

def test_reproduction_gate_reference_is_the_frozen_four():
    assert S.GATE_REF == {"baekmansonghee_jirisan": 183, "jissi_farm": 211,
                          "softyeon_ceramics": 192,
                          "pland_costco_hosting": 395}


def test_reproduction_gate_requires_exact_match(monkeypatch, tmp_path):
    monkeypatch.setattr(S, "production_n_segments", lambda p: 183)
    r = S.reproduction_gate(tmp_path, tmp_path, ref={"a": 183})
    assert r["all_match"] is True
    r = S.reproduction_gate(tmp_path, tmp_path, ref={"a": 184})
    assert r["all_match"] is False
    assert r["by_video"]["a"] == {"expected": 184, "got": 183, "match": False}


def test_verify_refuses_to_run_without_gate_pass(monkeypatch, tmp_path):
    """게이트 실패 시 신규 파일 판정으로 넘어가지 않는다."""
    monkeypatch.setattr(S, "production_n_segments", lambda p: 1)
    with pytest.raises(S.VerifyError, match="재현"):
        S.run(rows=[], staging=tmp_path, video_dir=tmp_path,
              work_dir=tmp_path, ref={"a": 183})


# ---- 상태 3분리 ---------------------------------------------------------

def test_download_failure_is_not_segment_ineligible(monkeypatch, tmp_path):
    monkeypatch.setattr(S, "download", lambda v, d: (None, "Private video"))
    row = {"video_id": "z", "family": "ebs_docuprime", "domain": "x"}
    m = S.verify_one(row, tmp_path)
    assert m["download_status"] == "failed"
    assert m["verification_status"] == "verification_unavailable"
    assert m["n_segments"] is None
    assert m["verification_status"] != "segment_ineligible"


def test_verified_row_records_provenance(monkeypatch, tmp_path):
    f = tmp_path / "z.mp4"
    f.write_bytes(b"fake-bytes")
    monkeypatch.setattr(S, "download", lambda v, d: (f, None))
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    m = S.verify_one({"video_id": "z", "family": "kbs_docu", "domain": "d"},
                     tmp_path)
    import hashlib
    assert m["file_sha256"] == hashlib.sha256(b"fake-bytes").hexdigest()
    assert m["source_url"].endswith("z")
    assert m["source_id"] == "z"
    assert m["publisher"] == "kbs" and m["program"] == "kbs_docu"
    assert m["verification_status"] == "verified_eligible"
    for k in ("source_url", "source_id", "download_status", "local_filename",
              "file_sha256", "duration_sec", "n_segments",
              "verification_status", "publisher", "program"):
        assert k in m, k


# ---- achieved_k ---------------------------------------------------------

@pytest.mark.parametrize("n,e,k", [(7, 30, 35), (7, 26, 33), (6, 29, 30),
                                   (5, 20, 25), (4, 16, 20), (0, 30, 0)])
def test_achieved_k_table(n, e, k):
    assert S.achieved_k(n, e) == k


def test_achieved_k_never_exceeds_target_or_cap():
    for n in range(0, 12):
        for e in range(0, 40):
            k = S.achieved_k(n, e)
            assert k <= S.TARGET_K
            ebs = k - n if k > n else 0
            if k:
                assert ebs / k <= S.C_CAP + 1e-9, (n, e, k)


def test_non_ebs_sources_are_declared():
    assert S.publisher_of("kbs_docu") == "kbs"
    assert S.publisher_of("ebs_hangukgihaeng") == "ebs"
    assert set(S.NON_EBS) >= {"kbs", "other", "free"}


# ---- 경계: 배포 경로에 쓰지 않는다 ----------------------------------------

def test_staging_is_not_the_production_video_dir():
    assert "data/videos" not in str(S.STAGING).replace("\\", "/")
    assert S.STAGING.name != "videos"


def test_module_never_writes_to_work_or_data_videos():
    body = (ROOT / "scripts" / "p2_staging_verify.py").read_text(
        encoding="utf-8").split('"""', 2)[2]
    for bad in ("work_dir /", 'data" / "videos', "extract_audio",
                "save_segments"):
        assert bad not in body, bad


def test_no_model_or_search_imports():
    body = (ROOT / "scripts" / "p2_staging_verify.py").read_text(
        encoding="utf-8").split('"""', 2)[2]
    for bad in ("m3_generate", "m4_index", "m5_search", "m6_evaluate",
                "caption", "qwen", "alpha", "mrr"):
        assert bad not in body.lower(), bad


def test_in_scope_excludes_lecture_dialog():
    rows = [{"family": "lecture_dialog", "eligible": "True"},
            {"family": "ebs_docuprime", "eligible": "True"},
            {"family": "kbs_docu", "eligible": "False"}]
    assert [r["family"] for r in S.in_scope(rows)] == ["ebs_docuprime"]


# ---- 산출물 ------------------------------------------------------------

def test_manifest_reports_counts_and_achieved_k(monkeypatch, tmp_path):
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    monkeypatch.setattr(S, "download", lambda v, d: (f, None))
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    monkeypatch.setattr(S, "reproduction_gate",
                        lambda *a, **k: {"all_match": True, "by_video": {}})
    rows = [{"video_id": "a", "family": "ebs_docuprime", "domain": "d",
             "eligible": "True"}]
    m = S.run(rows=rows, staging=tmp_path, video_dir=tmp_path,
              work_dir=tmp_path)
    assert m["counts"]["verified_eligible"] == 1
    assert "achieved_k" in m and "target_k" in m
    assert m["approval_stage"] == "approval_1_sampling_frame_verification"
    assert "promotion" in m["boundary_note"] or "승격" in m["boundary_note"]
    saved = json.loads((tmp_path / "manifest.json").read_text(
        encoding="utf-8"))
    assert saved["target_k"] == 35


def test_cli_output_is_ascii_safe():
    src = (ROOT / "scripts" / "p2_staging_verify.py").read_text(
        encoding="utf-8")
    for line in src.split("if __name__")[0].splitlines():
        if line.strip().startswith("print("):
            assert line.isascii(), line

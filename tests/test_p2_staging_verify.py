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
    monkeypatch.setattr(S, "download",
                        lambda v, d: (None, "Private video", "download_failed"))
    row = {"video_id": "z", "family": "ebs_docuprime", "domain": "x"}
    m = S.verify_one(row, tmp_path)
    assert m["download_status"] == "failed"
    assert m["verification_status"] == "verification_unavailable"
    assert m["n_segments"] is None
    assert m["verification_status"] != "segment_ineligible"


def test_verified_row_records_provenance(monkeypatch, tmp_path):
    f = tmp_path / "z.mp4"
    f.write_bytes(b"fake-bytes")
    monkeypatch.setattr(S, "download", lambda v, d: (f, None, "downloaded"))
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    monkeypatch.setattr(S, "has_audio", lambda p: True)
    monkeypatch.setattr(S, "container_audio_lang", lambda p: None)
    monkeypatch.setattr(S, "platform_audio_probe",
                        lambda v: {"selected_audio_language": "ko"})
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


def test_format_prefers_avc1_for_the_cv2_path():
    """production duration을 cv2가 읽는다 — avc1이 그 경로에서 안전하다."""
    assert "avc1" in S.FORMAT
    assert "height<=1080" in S.FORMAT


def test_media_info_is_provenance_only(monkeypatch, tmp_path):
    """해상도는 기록만 한다 — eligibility는 n_segments만 본다."""
    f = tmp_path / "z.mp4"
    f.write_bytes(b"x")
    monkeypatch.setattr(S, "download", lambda v, d: (f, None, "downloaded"))
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    monkeypatch.setattr(S, "has_audio", lambda p: True)
    monkeypatch.setattr(S, "container_audio_lang", lambda p: None)
    monkeypatch.setattr(S, "platform_audio_probe",
                        lambda v: {"selected_audio_language": "ko"})
    monkeypatch.setattr(S, "media_info", lambda p: {"width": 640,
                                                    "height": 360, "fps": 30.0})
    lo = S.verify_one({"video_id": "z", "family": "kbs_docu"}, tmp_path)
    monkeypatch.setattr(S, "media_info", lambda p: {"width": 1920,
                                                    "height": 1080, "fps": 30.0})
    hi = S.verify_one({"video_id": "z", "family": "kbs_docu"}, tmp_path)
    assert lo["verification_status"] == hi["verification_status"]
    assert lo["media"]["height"] != hi["media"]["height"]


def test_acquisition_condition_is_recorded_per_video(monkeypatch, tmp_path):
    """pre_existing 파일에는 이번 실행 조건을 적용했다고 쓰지 않는다."""
    f = tmp_path / "z.mp4"
    f.write_bytes(b"x")
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    monkeypatch.setattr(S, "media_info", lambda p: {"width": 1920})
    monkeypatch.setattr(S, "container_audio_lang", lambda p: None)
    monkeypatch.setattr(S, "platform_audio_probe",
                        lambda v: {"selected_audio_language": "ko"})
    monkeypatch.setattr(S, "has_audio", lambda p: True)
    monkeypatch.setattr(S, "download", lambda v, d: (f, None, "downloaded"))
    a = S.verify_one({"video_id": "z", "family": "kbs_docu"}, tmp_path)
    monkeypatch.setattr(S, "download", lambda v, d: (f, None, "pre_existing"))
    b = S.verify_one({"video_id": "z", "family": "kbs_docu"}, tmp_path)
    c = S.verify_one({"video_id": "z", "family": "kbs_docu"}, tmp_path,
                     origin=ORIGIN)
    assert a["acquisition"]["yt_dlp_version"] and a["acquisition"]["format_selector"]
    # origin이 없으면 unknown으로 남는다 — downloaded로 복원하지 않는다
    assert b["acquisition"]["source"] == "pre_existing_unknown_acquisition"
    assert b["acquisition"]["yt_dlp_version"] is None
    assert b["acquisition"]["note"]
    # origin이 있으면 아는 조건을 잃지 않는다
    assert c["acquisition"]["acquired_by"] == "canary_run"


def test_manifest_records_ffmpeg_version(monkeypatch, tmp_path):
    """merge가 ffmpeg를 거친다 — 컨테이너를 만든 손을 기록한다."""
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    monkeypatch.setattr(S, "download", lambda v, d: (f, None, "downloaded"))
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    monkeypatch.setattr(S, "media_info", lambda p: {"width": 1920})
    monkeypatch.setattr(S, "reproduction_gate",
                        lambda *a, **k: {"all_match": True, "by_video": {}})
    m = S.run(rows=[{"video_id": "a", "family": "kbs_docu", "eligible": "True"}],
              staging=tmp_path, video_dir=tmp_path, work_dir=tmp_path)
    assert m["ffmpeg_version"]
    assert m["yt_dlp_version"]


# ---- 발화 축: 이름을 증거 강도에 맞춘다 -----------------------------------

def test_speech_status_names_never_claim_verification():
    """STT를 안 돌렸다 — 어떤 값도 `verified`라고 부르지 않는다."""
    for probe in ({"selected_audio_language": "ko"},
                  {"selected_audio_language": "en"},
                  {"platform_language": "ko"},
                  {"platform_language": "en"}, {}):
        assert "verified" not in S.speech_status(probe)


def test_evidence_tiers_prefer_the_selected_audio_track():
    """페이지 수준 언어를 트랙 언어로 상속하지 않는다."""
    assert S.speech_status({"selected_audio_language": "ko-KR"}) \
        == "audio_track_ko"
    # 트랙이 다른 언어면 페이지가 ko라도 반증이다
    assert S.speech_status({"selected_audio_language": "en",
                            "platform_language": "ko"}) == "audio_track_other"
    # 트랙 정보가 없을 때만 페이지 수준으로 내려간다
    assert S.speech_status({"platform_language": "ko"}) \
        == "platform_language_ko"
    assert S.speech_status({}) == "speech_unresolved"


def test_criterion_claim_is_not_refuted_not_verified():
    assert S.speech_criterion("audio_track_ko") == "korean_speech_not_refuted"
    assert S.speech_criterion("speech_unresolved") \
        == "korean_speech_not_refuted"
    assert S.speech_criterion("audio_track_other") == "refuted_non_korean"
    assert S.speech_criterion("platform_language_other") == "refuted_non_korean"


def test_only_refuted_speech_is_excluded(monkeypatch, tmp_path):
    """정보가 없는 것을 비한국어로 취급하지 않는다 — 반증만 배제한다."""
    f = tmp_path / "z.mp4"
    f.write_bytes(b"x")
    monkeypatch.setattr(S, "download", lambda v, d: (f, None, "downloaded"))
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    monkeypatch.setattr(S, "media_info", lambda p: {"width": 1920})
    monkeypatch.setattr(S, "has_audio", lambda p: True)
    monkeypatch.setattr(S, "container_audio_lang", lambda p: "eng")
    row = {"video_id": "z", "family": "kbs_docu"}
    cases = [({"selected_audio_language": "ko"}, True),
             ({"platform_language": "ko"}, True),
             ({}, True),
             ({"selected_audio_language": "en"}, False)]
    for pr, usable in cases:
        monkeypatch.setattr(S, "platform_audio_probe", lambda v, p=pr: dict(p))
        m = S.verify_one(row, tmp_path)
        assert m["sampling_frame_usable"] is usable, pr


def test_selected_audio_track_provenance_is_recorded(monkeypatch, tmp_path):
    f = tmp_path / "z.mp4"
    f.write_bytes(b"x")
    monkeypatch.setattr(S, "download", lambda v, d: (f, None, "downloaded"))
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    monkeypatch.setattr(S, "media_info", lambda p: {"width": 1920})
    monkeypatch.setattr(S, "has_audio", lambda p: True)
    monkeypatch.setattr(S, "container_audio_lang", lambda p: "eng")
    monkeypatch.setattr(S, "platform_audio_probe", lambda v: {
        "platform_language": "ko", "selected_format_id": "137+140",
        "selected_audio_format_id": "140", "selected_audio_language": "ko"})
    m = S.verify_one({"video_id": "z", "family": "kbs_docu"}, tmp_path)
    assert m["selected_audio_format_id"] == "140"
    assert m["selected_audio_language"] == "ko"
    assert m["selected_format_id"] == "137+140"
    assert m["speech_status"] == "audio_track_ko"


def test_container_audio_tag_is_provenance_only(monkeypatch, tmp_path):
    """실측에서 ko 영상이 eng로 태깅됐다 — 판정에 쓰면 전 편이 오판된다."""
    f = tmp_path / "z.mp4"
    f.write_bytes(b"x")
    monkeypatch.setattr(S, "download", lambda v, d: (f, None, "downloaded"))
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    monkeypatch.setattr(S, "media_info", lambda p: {"width": 1920})
    monkeypatch.setattr(S, "has_audio", lambda p: True)
    monkeypatch.setattr(S, "container_audio_lang", lambda p: "eng")
    monkeypatch.setattr(S, "platform_audio_probe",
                        lambda v: {"selected_audio_language": "ko"})
    m = S.verify_one({"video_id": "z", "family": "kbs_docu"}, tmp_path)
    assert m["media"]["container_audio_lang"] == "eng"
    assert m["sampling_frame_usable"] is True


def test_probe_reads_metadata_only():
    import inspect
    src = inspect.getsource(S.platform_audio_probe)
    assert "--skip-download" in src
    for bad in ("whisper", "m3_", "faster_whisper"):
        assert bad not in src.lower()


def test_manifest_records_speech_evidence_limits(monkeypatch, tmp_path):
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    monkeypatch.setattr(S, "download", lambda v, d: (f, None, "downloaded"))
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    monkeypatch.setattr(S, "media_info", lambda p: {"width": 1920})
    monkeypatch.setattr(S, "has_audio", lambda p: True)
    monkeypatch.setattr(S, "container_audio_lang", lambda p: "eng")
    monkeypatch.setattr(S, "platform_audio_probe",
                        lambda v: {"selected_audio_language": "ko"})
    monkeypatch.setattr(S, "reproduction_gate",
                        lambda *a, **k: {"all_match": True, "by_video": {}})
    m = S.run(rows=[{"video_id": "a", "family": "kbs_docu", "eligible": "True"}],
              staging=tmp_path, video_dir=tmp_path, work_dir=tmp_path)
    e = m["speech_evidence"]
    assert e["claim_level"] == "korean_speech_not_refuted"
    assert "검증됐다고 주장하지" in e["statement"]
    assert e["evidence_tiers"] and e["inheritance_forbidden"]
    assert e["other_available_evidence"] and e["container_tag_unusable"]
    assert "PRIMARY를 바꾸지" in e["post_approval_2_rule"]
    assert m["counts"]["speech_audio_track_ko"] == 1
    assert m["counts"]["speech_refuted"] == 0


# ---- 취득 귀속: "이번에 받았나"와 "어떻게 받았나"를 구별한다 ----------------

ORIGIN = {"acquired_by_map": {"z": {"acquired_by": "canary_run",
                                   "yt_dlp_version": "2026.08.19",
                                   "format_selector": "avc1-pref"}},
          "prior_sha256": {"z": "deadbeef"}}


def test_downloaded_in_this_run_records_current_condition():
    a = S.attribute("z", "downloaded", ORIGIN)
    assert a["acquired_by"] == "this_run"
    assert a["yt_dlp_version"] and a["format_selector"] == S.FORMAT


def test_pre_existing_keeps_known_condition_from_frozen_origin():
    """재검증 실행에서 모든 파일이 pre_existing으로 보이지만, 조건은 이미 안다.

    **아는 것을 잃지 않는다** — 커밋 메시지만으로는 manifest provenance가 아니다.
    """
    a = S.attribute("z", "pre_existing", ORIGIN)
    assert a["acquired_by"] == "canary_run"
    assert a["yt_dlp_version"] == "2026.08.19"
    assert a["format_selector"] == "avc1-pref"


def test_pre_existing_without_origin_is_unknown_not_downloaded():
    """**모르는 것을 복원하지 않는다.**"""
    a = S.attribute("q", "pre_existing", ORIGIN)
    assert a["source"] == "pre_existing_unknown_acquisition"
    assert a["acquired_by"] is None and a["yt_dlp_version"] is None
    assert S.attribute("q", "pre_existing", None)["yt_dlp_version"] is None


def test_hash_check_never_claims_agreement_without_a_prior():
    assert S.hash_check("q", "abc", ORIGIN)["match"] is None
    assert "최초" in S.hash_check("q", "abc", ORIGIN)["note"]
    assert S.hash_check("z", "deadbeef", ORIGIN)["match"] is True
    assert S.hash_check("z", "other", ORIGIN)["match"] is False


def test_manifest_reports_mismatches_and_unknowns(monkeypatch, tmp_path):
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    monkeypatch.setattr(S, "download", lambda v, d: (f, None, "pre_existing"))
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    monkeypatch.setattr(S, "media_info", lambda p: {"width": 1920})
    monkeypatch.setattr(S, "has_audio", lambda p: False)
    monkeypatch.setattr(S, "container_audio_lang", lambda p: None)
    monkeypatch.setattr(S, "platform_audio_probe",
                        lambda v: {"selected_audio_language": "ko"})
    monkeypatch.setattr(S, "reproduction_gate",
                        lambda *a, **k: {"all_match": True, "by_video": {}})
    m = S.run(rows=[{"video_id": "a", "family": "kbs_docu", "eligible": "True"}],
              staging=tmp_path, video_dir=tmp_path, work_dir=tmp_path,
              origin={"acquired_by_map": {}, "prior_sha256": {"a": "nope"}})
    assert m["counts"]["verified_eligible"] == 0        # usable 아님
    assert m["sha256_mismatches"] == ["a"]
    assert m["unknown_acquisition"] == ["a"]
    assert m["no_audio"] == ["a"]
    assert m["acquisition_origin_supplied"] is True


# ---- 완성 파일만 인정한다 -------------------------------------------------

def test_partial_and_intermediate_files_are_not_accepted(tmp_path):
    """`.part`·병합 전 `.f137.mp4`를 완성 파일로 쓰면 음성 없는/잘린 입력이
    조용히 verified_eligible이 된다 — cv2는 그런 파일도 열고 duration을 준다."""
    (tmp_path / "vid.f137.mp4").write_bytes(b"x")
    (tmp_path / "vid.mp4.part").write_bytes(b"x")
    assert S.final_file(tmp_path, "vid") is None
    (tmp_path / "vid.mp4").write_bytes(b"x")
    assert S.final_file(tmp_path, "vid").name == "vid.mp4"


def test_zero_byte_file_is_not_accepted(tmp_path):
    (tmp_path / "vid.mp4").write_bytes(b"")
    assert S.final_file(tmp_path, "vid") is None


def test_download_reports_incomplete_artifacts(monkeypatch, tmp_path):
    """exit 0이어도 완성 파일이 없으면 실패다."""
    class R:
        returncode = 0
        stdout = ""
        stderr = ""
    monkeypatch.setattr(S.subprocess, "run", lambda *a, **k: R())
    (tmp_path / "vid.f137.mp4").write_bytes(b"x")
    path, err, how = S.download("vid", tmp_path)
    assert path is None and how == "download_failed"
    assert "incomplete" in err


def test_audio_is_a_second_axis_not_a_segment_criterion(monkeypatch, tmp_path):
    """표집틀 hard 조건이 한국어 발화 포함이다(규격 §1) — 음성 없음은 취득 실패다.

    길이 판정과 취득 integrity를 **다른 축**으로 남긴다. 길이만 통과한 파일을
    pool에 넣었다가 선정 뒤 승인 ②에서 빼면 그것이 사후 제외다.
    """
    f = tmp_path / "z.mp4"
    f.write_bytes(b"x")
    monkeypatch.setattr(S, "download", lambda v, d: (f, None, "downloaded"))
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    monkeypatch.setattr(S, "media_info", lambda p: {"width": 1920})
    monkeypatch.setattr(S, "container_audio_lang", lambda p: None)
    monkeypatch.setattr(S, "platform_audio_probe",
                        lambda v: {"selected_audio_language": "ko"})
    monkeypatch.setattr(S, "has_audio", lambda p: False)
    m = S.verify_one({"video_id": "z", "family": "kbs_docu"}, tmp_path)
    assert m["verification_status"] == "verified_eligible"   # 길이 축은 통과
    assert m["acquisition_status"] == "no_audio"             # 취득 축은 실패
    assert m["sampling_frame_usable"] is False


def test_audio_unknown_is_not_no_audio_and_not_usable(monkeypatch, tmp_path):
    """확인하지 못한 것을 "음성 없음"으로도, usable로도 세지 않는다."""
    f = tmp_path / "z.mp4"
    f.write_bytes(b"x")
    monkeypatch.setattr(S, "download", lambda v, d: (f, None, "downloaded"))
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    monkeypatch.setattr(S, "media_info", lambda p: {"width": 1920})
    monkeypatch.setattr(S, "container_audio_lang", lambda p: None)
    monkeypatch.setattr(S, "platform_audio_probe",
                        lambda v: {"selected_audio_language": "ko"})
    monkeypatch.setattr(S, "has_audio", lambda p: None)
    m = S.verify_one({"video_id": "z", "family": "kbs_docu"}, tmp_path)
    assert m["acquisition_status"] == "audio_unknown"
    assert m["sampling_frame_usable"] is False


def test_ffprobe_failure_is_unknown_not_false(monkeypatch, tmp_path):
    class R:
        returncode = 1
        stdout = ""
        stderr = "boom"
    monkeypatch.setattr(S.subprocess, "run", lambda *a, **k: R())
    assert S.has_audio(tmp_path / "x.mp4") is None
    assert S.acquisition_status(None) == "audio_unknown"
    assert S.acquisition_status(False) == "no_audio"
    assert S.acquisition_status(True) == "ok"


def test_achieved_k_counts_only_usable(monkeypatch, tmp_path):
    """길이만 통과한 영상은 E/N에 들어가지 않는다."""
    rows = [{"source_id": "a", "publisher": "ebs", "sampling_frame_usable": True,
             "verification_status": "verified_eligible",
             "acquisition_status": "ok"},
            {"source_id": "b", "publisher": "ebs", "sampling_frame_usable": False,
             "verification_status": "verified_eligible",
             "acquisition_status": "no_audio"}]
    c = S.counts(rows, free_verified=0)
    assert c["verified_eligible"] == 1
    assert c["segment_eligible_any_audio"] == 2
    assert c["acquisition_no_audio"] == 1
    assert c["ebs_verified"] == 1


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
    monkeypatch.setattr(S, "download", lambda v, d: (f, None, "downloaded"))
    monkeypatch.setattr(S, "probe", lambda p: (1000.0, 200))
    monkeypatch.setattr(S, "media_info", lambda p: {"width": 1920})
    monkeypatch.setattr(S, "has_audio", lambda p: True)
    monkeypatch.setattr(S, "container_audio_lang", lambda p: None)
    monkeypatch.setattr(S, "platform_audio_probe",
                        lambda v: {"selected_audio_language": "ko"})
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

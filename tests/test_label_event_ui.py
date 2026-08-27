"""사건 목록 작성 UI — blind 강제와 양식 정합성.

이 도구가 입력량을 줄이는 것은 좋지만, **줄여서는 안 되는 것**이 둘 있다.

```
① blind          어떤 경로도 caption·subtitle을 내보내지 않는다
② 동결 양식       최종 산출은 사전등록 CSV(start_sec,end_sec,event,unclear)다.
                 validate·freeze 경로를 새로 만들지 않는다
```
"""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import label_event_ui as UI                                     # noqa: E402

VID = "panel_a"
OTHER = "panel_b"


@pytest.fixture
def env(tmp_path):
    """합성 영상 2편. 실제 패널 영상을 쓰면 테스트가 blind를 깬다."""
    cfg = {"paths": {"data": str(tmp_path / "data"), "work": str(tmp_path / "work"),
                     "results": str(tmp_path / "results")}, "seg_len_sec": 5}
    for v in (VID, OTHER):
        w = tmp_path / "work" / v
        (w / "frames").mkdir(parents=True)
        segs = []
        for i in range(6):
            (w / "frames" / f"seg_{i:04d}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
            segs.append({"idx": i, "start": i * 5, "end": i * 5 + 5,
                         "rep_frame": f"frames/seg_{i:04d}.jpg",
                         # 아래 둘은 allowlist가 걸러야 하는 것들이다
                         "caption": f"합성 캡션 {i} 비밀", "subtitle": f"합성 자막 {i} 비밀"})
        (w / "segments.json").write_text(json.dumps(
            {"video_id": v, "n_segments": 6, "duration_sec": 30, "fps": 30,
             "segments": segs}, ensure_ascii=False), encoding="utf-8")
    inv = tmp_path / "inv"
    inv.mkdir()
    app = UI.create_app(cfg, videos=[VID], root=inv)
    return {"cfg": cfg, "inv": inv, "client": TestClient(app), "tmp": tmp_path}


# ------------------------------------------------------------------ blind

def test_no_route_returns_caption_or_subtitle(env):
    """경로를 하나씩 고르는 게 아니라 **전부** 훑는다."""
    c = env["client"]
    routes = [r.path for r in c.app.routes if "{video_id}" in getattr(r, "path", "")]
    assert routes, "video_id를 받는 경로가 없다 — 열거가 비었다"
    for path in routes:
        url = path.replace("{video_id}", VID).replace("{idx}", "0")
        r = c.get(url)
        if r.status_code != 200:
            continue
        body = r.text if "json" in r.headers.get("content-type", "") or \
            r.headers.get("content-type", "").startswith("text") else ""
        assert "비밀" not in body, f"{path}에서 캡션·자막이 새어 나왔다"
        for k in ("caption", "subtitle"):
            assert k not in body, f"{path}에 {k} 필드가 있다"


def test_segments_route_returns_only_idx_and_time(env):
    r = env["client"].get(f"/api/segments/{VID}")
    assert r.status_code == 200
    assert {k for s in r.json()["segments"] for k in s} == {"idx", "start", "end"}


def test_videos_outside_the_frozen_panel_are_refused(env):
    for url in (f"/api/segments/{OTHER}", f"/api/draft/{OTHER}",
                f"/api/frame/{OTHER}/0", f"/api/video/{OTHER}"):
        assert env["client"].get(url).status_code == 403, url


def test_panel_list_comes_from_the_frozen_manifest():
    man = ROOT / "docs/finalization/m8_c2_panel_manifest_2026-08-27.json"
    if not man.exists():
        pytest.skip("패널 manifest 미동결")
        return
    assert UI.panel_videos() == json.loads(man.read_text(encoding="utf-8"))["final_panel"]


def test_ui_html_does_not_mention_forbidden_channels():
    html = UI.HTML.read_text(encoding="utf-8")
    for token in ("caption", "subtitle", "/api/search", "score", "rank"):
        assert token not in html, token
    assert "muted" in html          # 미리보기는 무음이다


# ------------------------------------------------- 시각·id는 코드가 채운다

def test_timestamps_are_derived_not_typed(env):
    c = env["client"]
    r = c.put(f"/api/draft/{VID}", json={"events": [
        {"start_seg": 1, "end_seg": 3, "description": "사람이 걸어감"}]})
    assert r.status_code == 200
    e = r.json()["events"][0]
    assert (e["start_sec"], e["end_sec"]) == (5.0, 20.0)      # seg 1 시작 ~ seg 3 끝
    assert e["event_id"] == "E001"


def test_reversed_selection_is_normalized(env):
    r = env["client"].put(f"/api/draft/{VID}", json={"events": [
        {"start_seg": 4, "end_seg": 2, "description": "역순 선택"}]})
    e = r.json()["events"][0]
    assert (e["start_seg"], e["end_seg"]) == (2, 4)


def test_out_of_range_segment_is_rejected(env):
    r = env["client"].put(f"/api/draft/{VID}", json={"events": [
        {"start_seg": 0, "end_seg": 99, "description": "범위 밖"}]})
    assert r.status_code == 400


def test_events_are_sorted_and_ids_unique(env):
    r = env["client"].put(f"/api/draft/{VID}", json={"events": [
        {"start_seg": 4, "end_seg": 5, "description": "나중"},
        {"start_seg": 0, "end_seg": 1, "description": "처음"}]})
    ev = r.json()["events"]
    assert [e["start_seg"] for e in ev] == [0, 4]
    assert len({e["event_id"] for e in ev}) == 2


def test_draft_survives_reload(env):
    c = env["client"]
    c.put(f"/api/draft/{VID}", json={"events": [
        {"start_seg": 0, "end_seg": 2, "description": "자동 저장 확인"}]})
    again = c.get(f"/api/draft/{VID}").json()
    assert again["events"][0]["description"] == "자동 저장 확인"
    assert again["status"] == "DRAFT"


# --------------------------------------------------------- 동결 양식 정합성

def test_export_writes_the_preregistered_csv_header(env):
    c = env["client"]
    c.put(f"/api/draft/{VID}", json={"events": [
        {"start_seg": 0, "end_seg": 2, "description": "재료를 담음"},
        {"start_seg": 3, "end_seg": 5, "description": "알 수 없는 장면", "unclear": 1}]})
    r = c.post(f"/api/export/{VID}")
    assert r.status_code == 200
    csv = (env["inv"] / f"{VID}.csv").read_text(encoding="utf-8").splitlines()
    assert csv[0] == "start_sec,end_sec,event,unclear"
    assert csv[1] == "0,15,재료를 담음,"
    assert csv[2].endswith(",1")


def test_export_refuses_when_a_description_is_empty(env):
    """V3(이름 비어 있지 않음)에서 거부될 것을 내보내기 전에 막는다."""
    c = env["client"]
    c.put(f"/api/draft/{VID}", json={"events": [{"start_seg": 0, "end_seg": 1,
                                                 "description": ""}]})
    r = c.post(f"/api/export/{VID}")
    assert r.status_code == 400 and "설명" in r.json()["detail"]


def test_export_refuses_when_there_are_no_events(env):
    assert env["client"].post(f"/api/export/{VID}").status_code == 400


def test_export_quotes_a_description_containing_a_comma(env):
    c = env["client"]
    c.put(f"/api/draft/{VID}", json={"events": [
        {"start_seg": 0, "end_seg": 1, "description": "차에서 내림, 건물로 이동"}]})
    c.post(f"/api/export/{VID}")
    line = (env["inv"] / f"{VID}.csv").read_text(encoding="utf-8").splitlines()[1]
    assert '"차에서 내림, 건물로 이동"' in line


def test_draft_and_csv_are_separate_files(env):
    """초안이 사전등록 CSV를 조용히 덮지 않는다 — 내보내기는 명시 행위다."""
    c = env["client"]
    c.put(f"/api/draft/{VID}", json={"events": [{"start_seg": 0, "end_seg": 1,
                                                 "description": "무언가"}]})
    assert (env["inv"] / f"{VID}.draft.json").exists()
    assert not (env["inv"] / f"{VID}.csv").exists()
    c.post(f"/api/export/{VID}")
    assert (env["inv"] / f"{VID}.csv").exists()


def test_ui_never_touches_freeze(env):
    """동결은 기존 도구만 한다 — UI에 freeze 경로가 없어야 한다."""
    src = (ROOT / "scripts/label_event_ui.py").read_text(encoding="utf-8")
    assert "def freeze" not in src
    assert "FROZEN_" not in src
    paths = [getattr(r, "path", "") for r in env["client"].app.routes]
    assert not [p for p in paths if "freeze" in p]


def test_ids_stay_unique_after_deleting_a_middle_event(env):
    """중간 사건을 지우고 새로 추가해도 id가 겹치면 안 된다.

    실측 사고: 목록에 `E007`이 둘, `E006`이 없는 상태가 나왔다 — 새 id를 목록 길이로
    매겨서 삭제 뒤 번호가 재사용됐다. id는 사건을 가리키는 유일한 손잡이라
    겹치면 UI에서 다른 사건이 선택되고 삭제도 엉킨다.
    """
    c = env["client"]
    r = c.put(f"/api/draft/{VID}", json={"events": [
        {"start_seg": 0, "end_seg": 0, "description": "하나"},
        {"start_seg": 1, "end_seg": 1, "description": "둘"},
        {"start_seg": 2, "end_seg": 2, "description": "셋"}]})
    ev = r.json()["events"]
    assert [e["event_id"] for e in ev] == ["E001", "E002", "E003"]

    kept = [e for e in ev if e["event_id"] != "E002"]          # 가운데 삭제
    kept.append({"event_id": None, "start_seg": 4, "end_seg": 4, "description": "넷"})
    ev2 = c.put(f"/api/draft/{VID}", json={"events": kept}).json()["events"]
    ids = [e["event_id"] for e in ev2]
    assert len(ids) == len(set(ids)), ids
    assert "E003" in ids                                        # 기존 id는 그대로 둔다


def test_duplicate_ids_in_input_are_repaired(env):
    """이미 저장된 초안에 중복 id가 있으면 저장할 때 고쳐 준다(먼저 온 것을 유지)."""
    c = env["client"]
    ev = c.put(f"/api/draft/{VID}", json={"events": [
        {"event_id": "E007", "start_seg": 0, "end_seg": 1, "description": "먼저"},
        {"event_id": "E007", "start_seg": 2, "end_seg": 3, "description": "나중"}]}).json()["events"]
    ids = [e["event_id"] for e in ev]
    assert len(set(ids)) == 2, ids
    assert ev[0]["event_id"] == "E007" and ev[0]["description"] == "먼저"


def test_end_sec_is_clamped_to_video_duration(env):
    """마지막 구간의 `end`가 `duration_sec`를 넘는 인덱스가 있다 — m1 반올림 산물이다.

    실측: `m8c2_cIxG7OHYMPU`는 마지막 구간 end 1638.0 · duration 1637.999로
    V2(영상 길이 안)에서 거부됐다. 사람 입력 문제가 아니므로 내보낼 때 잘라 준다.
    """
    w = env["tmp"] / "work" / VID / "segments.json"
    doc = json.loads(w.read_text(encoding="utf-8"))
    doc["duration_sec"] = 29.999                  # 마지막 구간 end(30)보다 짧다
    w.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    r = env["client"].put(f"/api/draft/{VID}", json={"events": [
        {"start_seg": 4, "end_seg": 5, "description": "마지막 구간"}]})
    assert r.json()["events"][0]["end_sec"] == 29.999


def test_export_does_not_lose_subsecond_precision(env):
    """`%g`는 유효숫자 6자리라 1637.999를 1638로 반올림한다 — V2가 그 0.001로 거부한다."""
    w = env["tmp"] / "work" / VID / "segments.json"
    doc = json.loads(w.read_text(encoding="utf-8"))
    doc["duration_sec"] = 29.999
    w.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    c = env["client"]
    c.put(f"/api/draft/{VID}", json={"events": [
        {"start_seg": 4, "end_seg": 5, "description": "마지막 구간"}]})
    c.post(f"/api/export/{VID}")
    line = (env["inv"] / f"{VID}.csv").read_text(encoding="utf-8").splitlines()[1]
    assert line.startswith("20,29.999,"), line

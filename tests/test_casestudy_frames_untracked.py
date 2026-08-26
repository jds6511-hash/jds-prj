"""케이스 스터디 논의용 프레임이 git에 추적되지 않아야 한다.

실제 사고(2026-08-26): `caption_retrieval_casestudy_results.json`이 프레임 디렉터리를
**"미추적 · 튜터 논의 한정 · 공개 금지"**로 선언했는데 실제로는 27장이 추적되고 있었다.
선언만 있고 강제가 없으면 선언이 아무 일도 하지 않는다 — 2026-08-26 F4에서 고친
데모 진입점 결함과 같은 유형이다.

미푸시 히스토리에서 blob까지 제거했고(`docs/finalization/HISTORY_REWRITE_2026-08-26.md`),
이 테스트가 재발을 막는다. 원본 영상 프레임이고 저장소는 공개다.
"""
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GLOB = "runs/casestudy_caption_retrieval/*/frames_for_discussion"
RESULTS = ROOT / "docs/finalization/caption_retrieval_casestudy_results.json"


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8")


def test_no_frame_is_tracked():
    """추적 중인 프레임이 0건이어야 한다."""
    r = _git("ls-files", "--", GLOB)
    tracked = [x for x in r.stdout.splitlines() if x.strip()]
    assert not tracked, "프레임이 git에 추적되고 있다: %s" % tracked[:5]


def test_no_frame_is_tracked_anywhere_in_current_lineage():
    """현재 lineage의 어떤 커밋에도 프레임이 없어야 한다."""
    r = _git("log", "--oneline", "--all", "--", GLOB)
    commits = [x for x in r.stdout.splitlines() if x.strip()]
    # 백업 ref(backup/pre-frame-rewrite)는 재작성 전 상태를 일부러 보존한 것이다.
    kept = []
    for c in commits:
        sha = c.split()[0]
        anc = _git("merge-base", "--is-ancestor", sha, "HEAD")
        if anc.returncode == 0:
            kept.append(c)
    assert not kept, "HEAD 조상 커밋에 프레임이 남아 있다: %s" % kept[:3]


def test_gitignore_blocks_new_frames():
    """규칙이 실제로 차단하는지 git에게 직접 물어본다."""
    sample = ("runs/casestudy_caption_retrieval/cs_20260825/"
              "frames_for_discussion/seg0079_00395s.jpg")
    r = _git("check-ignore", "-q", "--no-index", "--", sample)
    assert r.returncode == 0, "%s 가 .gitignore로 차단되지 않는다" % sample


def test_results_artifact_still_declares_frames_unpublished():
    """선언 문구가 사라지면 이 테스트의 근거도 사라진다 — 함께 지킨다."""
    if not RESULTS.is_file():
        pytest.skip("결과 artifact가 없는 환경이다")
    d = json.loads(RESULTS.read_text(encoding="utf-8"))
    frames = d["artifacts"]["frames_dir"]
    assert "frames_for_discussion" in frames
    assert "미추적" in frames and "공개 금지" in frames, frames


def test_local_frames_are_preserved_for_deck_rebuild():
    """추적은 끊었지만 로컬 사본은 남아 있어야 한다 — PPT 재생성에 쓴다.

    clone 직후에는 없는 것이 정상이므로 없으면 skip한다.
    """
    d = ROOT / "runs/casestudy_caption_retrieval/cs_20260825/frames_for_discussion"
    if not d.is_dir():
        pytest.skip("프레임 로컬 사본이 없는 환경이다 (clone 직후 정상)")
    jpgs = sorted(d.glob("*.jpg"))
    assert len(jpgs) == 27, "프레임 %d장 (27장이어야 한다)" % len(jpgs)
    builder = ROOT / "docs/presentation/build_casestudy_deck.js"
    if builder.is_file():
        src = builder.read_text(encoding="utf-8")
        assert "frames_for_discussion" in src
        for name in ("seg0079_00395s.jpg", "seg0000_00000s.jpg",
                     "seg0188_00940s.jpg", "seg0316_01580s.jpg"):
            assert name in src, name
            assert (d / name).is_file(), "덱이 참조하는 %s 가 없다" % name

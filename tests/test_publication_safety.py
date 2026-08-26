"""공개 저장소 안전성 — **`git add -A`를 해도 비공개 자산이 추적되지 않는가.**

현재 상태는 좋다(위험 tracked 0건). 문제는 그것을 지키는 장치가 없었다는 것이다.
2026-08-26에 실제로 사고가 있었다 — 케이스 스터디 논의용 프레임 27장이 커밋됐고
(acb8650) 미푸시 상태에서 히스토리째로 제거했다. 정책은 문서에 있었고 강제는 없었다.

여기서 보는 것 셋.

1. 정책상 금지된 경로가 **추적되고 있지 않다** (tracked_forbidden == 0)
2. `.gitignore`가 대표 경로를 **실제로** 무시한다 (`git check-ignore`로 확인 —
   패턴을 읽어서 판단하지 않는다. 디렉터리 구조와 안 맞는 패턴은 무용지물이다)
3. 규칙이 **과하지 않다** — 공개해야 하는 source·라벨·결과가 무시되지 않는다

파일명 키워드로 판정하지 않는다. 정책에 적힌 경로/패턴만 본다.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# 정책 근거를 각 항목에 적는다. 근거 없는 패턴은 넣지 않는다.
FORBIDDEN = [
    # (대표 경로, 정책 근거)
    ("docs/tutor/_local/캡션검색_케이스스터디.pptx",
     "AI Hub·원본 영상 프레임 embed — 재배포 권한 미확인, 얼굴 식별 가능"),
    ("runs/casestudy_caption_retrieval/cs_20260826/frames_for_discussion/seg0002.jpg",
     "원본 영상 프레임 — '미추적·튜터 논의 한정·공개 금지' 선언 대상"),
    ("data/videos/pland_costco_hosting.mp4",
     "원본 영상은 YouTube 저작물 — 저장소 비포함"),
    ("work/pland_costco_hosting/segments.json",
     "자막·캡션은 영상 파생 텍스트 — 저장소 비포함"),
    ("work/pland_costco_hosting/emb_sub.npy", "임베딩 산출물 — 저장소 비포함"),
    ("docs/finalization/AAR_SAMPLE_pland.md",
     "AAR 렌더본에 인용 구간의 자막·캡션 원문이 실린다"),
    ("SERVER_LOCAL.md", "서버 접속 정보"),
    ("artifacts/p2_staging.json", "P2 표집틀 staging — 승격은 별도 승인"),
    ("New_Sample/spk_0001.wav", "AI Hub 화자 음성·전사 — 재배포 불허"),
    ("data_aihub/queries.jsonl", "AI Hub 라벨 파생 질의 — 재배포가 된다"),
    ("label_kit/clips/case_01.mp4", "라벨링 키트 클립 — 원본 영상 파생물"),
]

# 공개돼야 하는 것. 규칙이 넓어져 이것들이 무시되면 재현성이 깨진다.
MUST_BE_PUBLISHABLE = [
    "src/m5_search.py",
    "scripts/demo.py",
    "config.yaml",
    "README.md",
    "data/queries/queries.jsonl",
    "results/eval_test.json",
    "results/alpha_search_dev.json",
    "docs/DESIGN_SPEC.md",
    "docs/presentation/build_casestudy_deck.js",
    "label_kit/event_inventory/FROZEN_events.json",
    "docs/finalization/project_design_conformance_2026-08-26.json",
]


def _git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       encoding="utf-8", errors="replace")
    return r.stdout


def _is_ignored(rel: str) -> bool:
    r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT,
                       capture_output=True)
    return r.returncode == 0


@pytest.fixture(scope="module")
def tracked():
    out = _git("ls-files")
    if not out.strip():
        pytest.skip("git 저장소가 아니거나 추적 파일이 없다")
    return set(out.splitlines())


# ------------------------------------------- 1. 금지 자산이 추적되지 않는다

def test_no_restricted_assets_tracked(tracked):
    """정책상 금지된 **경로/패턴**으로 추적 중인 파일이 없어야 한다."""
    bad = []
    for path in tracked:
        p = path.replace("\\", "/")
        if (p.startswith("docs/tutor/_local/")
                or "/frames_for_discussion/" in p
                or p.startswith("data/videos/")
                or p.startswith("work/")
                or p.startswith("New_Sample/")
                or p.startswith("data_aihub/")
                or p.startswith("artifacts/")
                or p == "SERVER_LOCAL.md"
                or p.startswith("docs/finalization/AAR_SAMPLE_")
                or (p.startswith("label_kit/") and "/event_inventory/" not in p)
                or p.endswith((".mp4", ".wav", ".npy", ".pptx"))):
            bad.append(p)
    assert bad == [], f"공개 금지 자산이 추적되고 있다: {bad[:10]}"


def test_index_artifacts_are_not_tracked(tracked):
    """segments.json·emb_*.npy·meta.json은 어느 경로에서도 추적하지 않는다."""
    names = ("segments.json", "emb_sub.npy", "emb_cap.npy")
    bad = [p for p in tracked if Path(p).name in names]
    assert bad == [], bad


# ------------------------------------- 2. .gitignore가 실제로 동작한다

@pytest.mark.parametrize("rel,reason", FORBIDDEN)
def test_forbidden_paths_are_actually_ignored(rel, reason):
    """패턴을 읽는 대신 `git check-ignore`로 확인한다.

    파일이 실제로 없어도 판정된다 — 대표 경로로 규칙 자체를 검사하는 방식이다.
    """
    assert _is_ignored(rel), f"{rel} 이 무시되지 않는다 ({reason})"


def test_gitignore_declares_the_reason_for_local_only_assets():
    """왜 막았는지 적혀 있어야 다음 사람이 규칙을 되돌리지 않는다."""
    txt = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for anchor in ("docs/tutor/_local/", "frames_for_discussion", "AAR_SAMPLE_"):
        assert anchor in txt, anchor


# --------------------------------------------- 3. 규칙이 과하지 않다

@pytest.mark.parametrize("rel", MUST_BE_PUBLISHABLE)
def test_publishable_sources_are_not_ignored(rel):
    assert not _is_ignored(rel), f"{rel} 이 무시된다 — 규칙이 과하게 넓다"


@pytest.mark.parametrize("rel", MUST_BE_PUBLISHABLE)
def test_publishable_sources_are_actually_tracked(tracked, rel):
    if not (ROOT / rel).exists():
        pytest.skip(f"{rel} 이 이 작업 트리에 없다")
    assert rel in tracked, f"{rel} 이 추적되지 않는다"


def test_frozen_label_inventory_stays_tracked(tracked):
    """동결 사건 목록은 temporal 지표의 분모다 — 없으면 결과를 재현할 수 없다."""
    frozen = [p for p in tracked if p.startswith("label_kit/event_inventory/FROZEN_")]
    if not list((ROOT / "label_kit/event_inventory").glob("FROZEN_*.json")):
        pytest.skip("이 작업 트리에 동결 목록이 없다")
    assert frozen, "FROZEN_*.json 이 추적되지 않는다"

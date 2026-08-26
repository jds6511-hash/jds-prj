"""데모 대상 영상 자격 정책 — **선언이 아니라 강제 지점**.

두 번 같은 유형의 사고가 났다.

1. `eligible_for_public_demo: false`를 manifest에 적어 뒀는데 진입점이 막지 않았다
   (2026-08-26 F4에서 `scripts/demo.py`에 preflight 추가).
2. 그 preflight가 **시작 시 `--video-id` 하나만** 검사했고, 웹 API는 요청 본문의
   `video_id`를 그대로 받았다. 서버가 뜬 뒤에는 test split 영상도 조회·재생됐다
   (2026-08-26 설계 정합성 감사에서 발견).

그래서 정책을 `scripts/demo.py`에서 **중립 모듈로 옮겨** 진입점과 요청 경로가 같은
함수를 쓰게 한다. `src/`는 `scripts/`를 import하지 않으므로 여기에 둔다.

**fail-closed다.** 판정을 못 하면 통과시키지 않는 쪽으로 기운다. 예외는 manifest
부재 하나뿐이고 그 이유를 아래에 적었다.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# test 39질의가 붙은 영상. 데모로 돌리지 않는다 — 공표된 결과 인용만 허용한다.
# data/queries/queries.jsonl의 split=="test" 집합과 일치해야 한다
# (tests/test_eligibility.py가 대조한다 — 새 test 영상이 추가되면 여기서 깨진다).
TEST_SPLIT_VIDEOS = ("gemini_promo", "itsub_viral_gadgets",
                     "panibottle_vietnam1", "yunnamnopo_tongyeong")

E2E_MANIFEST = ROOT / "planning/e2e_external_manifest.json"

# P2/P3 산출물은 별도 paths를 쓰고 work/에 들어오지 않는다. 그래도 이름 접두어로
# 한 겹 더 막는다 — generic glob이 섞여 들어오는 경로를 차단하는 값싼 방어다.
RESTRICTED_PREFIXES = ("p2_", "p3_")


def e2e_only_videos() -> frozenset:
    """manifest가 `e2e_only` 또는 `eligible_for_public_demo: false`로 선언한 영상.

    manifest가 없으면 빈 집합이다 — 배포본에 `planning/`이 없을 수 있어 실행을
    깨뜨리지 않는다. **다만 그때는 E2E 차단이 동작하지 않는다**(아래 함수가 그
    사실을 그대로 노출한다).
    """
    if not E2E_MANIFEST.is_file():
        return frozenset()
    import json
    try:
        m = json.loads(E2E_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    out = set()
    for v in m.get("videos", []):
        vid = v.get("e2e_id")
        if vid and (v.get("e2e_only") or v.get("eligible_for_public_demo") is False):
            out.add(vid)
    return frozenset(out)


def demo_block_reason(video_id: str) -> str | None:
    """데모로 돌리면 안 되는 이유. 자격이 있으면 None.

    반환 문자열은 사용자에게 그대로 보여도 되는 문장이다.
    """
    if not video_id:
        return "video_id가 비어 있다"
    if video_id in TEST_SPLIT_VIDEOS:
        return (f"{video_id}는 test split 영상이다 — 데모로 실행하지 않는다. "
                f"공표된 test 결과는 results/eval_test.json 인용으로만 쓴다")
    if video_id in e2e_only_videos():
        return (f"{video_id}는 external E2E 전용 영상이다"
                f"(eligible_for_public_demo=false) — 기능 검증용으로 편입한 "
                f"외부 영상이라 데모로 실행하지 않는다")
    if video_id.startswith(RESTRICTED_PREFIXES):
        return f"{video_id}는 P2/P3 전용 이름 규칙이다 — 데모 경로에서 다루지 않는다"
    return None


def demo_eligible(video_id: str) -> bool:
    return demo_block_reason(video_id) is None


def manifest_available() -> bool:
    """E2E 차단이 실제로 동작하는 상태인지. preflight가 경고에 쓴다."""
    return E2E_MANIFEST.is_file()

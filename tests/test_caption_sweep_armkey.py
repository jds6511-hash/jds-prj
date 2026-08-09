"""캡션 스윕의 arm 식별자 — 토큰 상한 덮어쓰기가 캡션 캐시와 섞이면 안 된다.

절단율이 높은 arm(P2 44.4% 실측)을 상한을 올려 재측정할 때, 키가 안 갈리면
128토큰으로 만든 캡션을 그대로 재사용해서 "상한을 올려도 안 변한다"는 완전히
틀린 결론이 나온다. 그 회귀만 막는다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docs/probes"))
from caption_model_sweep import arm_key                    # noqa: E402

DEFAULT = 128


def test_no_override_keeps_plain_key():
    assert arm_key("P0", None, DEFAULT) == "P0"


def test_override_equal_to_default_keeps_plain_key():
    """같은 값을 명시했을 뿐인데 키가 갈리면 기존 캡션을 헛되이 재생성한다."""
    assert arm_key("P0", DEFAULT, DEFAULT) == "P0"


def test_override_splits_the_key():
    assert arm_key("P0", 512, DEFAULT) == "P0@512"


def test_distinct_overrides_do_not_collide():
    keys = {arm_key("P2", n, DEFAULT) for n in (None, 256, 512)}
    assert len(keys) == 3

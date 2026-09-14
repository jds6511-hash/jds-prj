"""v2.1 최종 판정 규칙 — supersession을 좁게 연다.

frozen matrix는 모든 P0 충족을 요구하고, `REG-010`은 `push = NO`다. 실제로는
후속 승인 아래 push가 수행됐으므로 그 상태를 **조용히 PASS로 바꾸지 않는다.**

```
PASS                            문자 그대로 충족
PASS_BY_AUTHORIZED_SUPERSESSION 후속 명시적 결정이 그 운영 규칙을 바꿨다
WAIVED                          원 규칙은 그대로이고 실패를 예외적으로 수용한다
FAIL                            그 외
```

`supersession`은 **`REG-010` 하나에만** 열려 있다. 목록을 늘리면 다른 P0 실패를
supersession이라 부르는 우회로가 생긴다 — 늘리는 것은 별도 승인 사건이다.

addendum이 없거나 근거 pointer가 없으면 supersession을 인정하지 않는다.
"""
from __future__ import annotations

import re
from pathlib import Path

PASS = "PASS"
PASS_BY_AUTHORIZED_SUPERSESSION = "PASS_BY_AUTHORIZED_SUPERSESSION"
WAIVED = "WAIVED"
FAIL = "FAIL"

P0_STATUSES = (PASS, PASS_BY_AUTHORIZED_SUPERSESSION, WAIVED, FAIL)

#: supersession을 쓸 수 있는 항목. 하나뿐이다.
AUTHORIZED_SUPERSESSION_IDS = ("REG-010",)

ADDENDUM_PATH = "docs/finalization/V2_1_REG_010_AUTHORIZATION_ADDENDUM_2026-09-02.md"
MATRIX_PATH = "docs/finalization/V2_1_ACCEPTANCE_MATRIX_2026-08-30.md"

#: addendum이 갖춰야 하는 것. 하나라도 없으면 근거가 아니다.
REQUIRED_SECTIONS = (
    "Original frozen criterion",
    "Subsequent decision",
    "Effective interpretation",
    "PASS_BY_AUTHORIZED_SUPERSESSION",
    "not WAIVED",
    "authorized_supersession_ids",
)

#: 승인 범위를 가리키는 commit pointer(짧은 SHA)가 실제로 적혀 있어야 한다.
_EVIDENCE = re.compile(r"\b[0-9a-f]{7,40}\b")


def authorization_recorded(root: Path) -> bool:
    """addendum이 존재하고, 필요한 절과 근거 pointer를 갖췄는가."""
    path = root / ADDENDUM_PATH
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if any(section not in text for section in REQUIRED_SECTIONS):
        return False
    return len(set(_EVIDENCE.findall(text))) >= 2


def frozen_criterion_intact(root: Path) -> bool:
    """원 기준이 matrix에 그대로 남아 있는가. 덮어쓰면 supersession이 아니다."""
    matrix = (root / MATRIX_PATH).read_text(encoding="utf-8")
    return bool(re.search(r"\|\s*REG-010\s*\|\s*P0\s*\|\s*push\s*\|\s*NO",
                          matrix))


def p0_satisfied(acceptance_id: str, status: str, root: Path) -> bool:
    """P0 하나가 최종 acceptance를 통과하는가.

    supersession은 **허용 목록에 있고 · addendum이 갖춰져 있고 · 원 기준이 그대로
    남아 있을 때만** 인정된다.
    """
    if status not in P0_STATUSES:
        raise ValueError("unknown status: %r" % (status,))
    if status == PASS:
        return True
    if status != PASS_BY_AUTHORIZED_SUPERSESSION:
        return False
    return (
        acceptance_id in AUTHORIZED_SUPERSESSION_IDS
        and authorization_recorded(root)
        and frozen_criterion_intact(root)
    )

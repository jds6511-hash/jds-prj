"""v2.1 research boundary guards — 금지된 변화를 기계가 잡는다 (A-11).

```
REG-005  BCS core diff                없음
REG-006  official test access         없음
REG-007  M9 execution artifact        없음
REG-008  new human GT artifact        없음
REG-009  provider adoption marker     없음
REF-003  wonyi_gyeongju 자동 대조      없음
```

"지금 트리가 깨끗하다"만 보면 부족하다. **금지된 변화가 실제로 들어왔을 때
깨져야** 가드다. 그래서 모든 검사는 `root`를 받아 합성 트리에도 돌릴 수 있다.

기준선은 `docs/finalization/v2_1_research_boundary_baseline_2026-08-30.json`이다.
존재 자체를 금지할 수 없는 항목이 있기 때문이다 — 예를 들어
`results/m8_redesign_r1/report_dev_wonyi_gyeongju.json`은 gyeongju가 dev 세트에
있어서 생긴 **정상 M8 산출물**이지 사람이 쓴 보고서와의 대조가 아니다. 그래서
"있으면 실패"가 아니라 "기준선에 없던 것이 생기면 실패"로 잰다.

줄바꿈은 비교 전에 정규화한다. Windows 체크아웃에서 CRLF로 바뀌는 것을 변경으로
읽으면 가드가 매일 거짓 실패한다(2026-08-14 md5 대조에서 겪었다).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

BASELINE_PATH = "docs/finalization/v2_1_research_boundary_baseline_2026-08-30.json"

#: 동결된 BCS. 이 파일들은 v2.1 작업 중 바뀌면 안 된다.
BCS_PROTECTED = (
    "src/bcs.py",
    "src/bcs_present.py",
    "scripts/bcs_prototype.py",
    "scripts/bcs_reparse.py",
    "scripts/bcs_hwpx.py",
)

#: 공식 test 접촉 흔적이 남는 자리.
OFFICIAL_TEST_PATHS = (
    "results/eval_test.json",
    "results/eval_test_kure.json",
    "data/queries/queries.jsonl",
)

#: 사람이 만든 GT 인벤토리.
HUMAN_GT_GLOB = "label_kit/event_inventory/*.json"

#: 산출물이 쌓이는 자리. 소스·문서는 여기 없다.
ARTIFACT_DIRS = ("runs", "results", "artifacts")

_M9 = re.compile(r"m9", re.IGNORECASE)
_GYEONGJU = re.compile(r"gyeongju", re.IGNORECASE)
_ADOPTION = re.compile(r"caption_text_change_point", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Failure:
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class GuardReport:
    ok: bool
    failures: list[Failure]


def digest(path: Path) -> str:
    """줄바꿈을 정규화한 내용 해시. CRLF 변환을 변경으로 읽지 않는다."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _artifact_files(root: Path):
    for name in ARTIFACT_DIRS:
        directory = root / name
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file():
                yield path


def _inventory(root: Path, paths) -> dict[str, str]:
    return {p: digest(root / p) for p in paths if (root / p).is_file()}


def check_bcs_unchanged(root: Path, baseline: dict) -> list[Failure]:
    """REG-005 — 동결본은 한 글자도 바뀌면 안 된다."""
    failures = []
    recorded = baseline["bcs_protected"]
    for path, expected in recorded.items():
        target = root / path
        if not target.is_file():
            failures.append(Failure("BCS_CORE_MISSING", path))
        elif digest(target) != expected:
            failures.append(Failure("BCS_CORE_DIFF", path))
    return failures


def check_official_test_untouched(root: Path, baseline: dict) -> list[Failure]:
    """REG-006 — test 39는 비가역 자원이다. 재평가는 물론 재작성도 없다."""
    failures = []
    for path, expected in baseline["official_test"].items():
        target = root / path
        if not target.is_file():
            failures.append(Failure("OFFICIAL_TEST_MISSING", path))
        elif digest(target) != expected:
            failures.append(Failure("OFFICIAL_TEST_MODIFIED", path))
    return failures


def check_no_m9_artifacts(root: Path) -> list[Failure]:
    """REG-007 — M9는 실행 자체가 test 접촉이다. 산출물이 있으면 돌린 것이다."""
    found = sorted(
        str(p.relative_to(root)) for p in _artifact_files(root) if _M9.search(p.name)
    )
    return [Failure("M9_ARTIFACT", path) for path in found]


def check_no_new_human_gt(root: Path, baseline: dict) -> list[Failure]:
    """REG-008 — 새 라벨은 별도 승인 사건이다. v2.1 구현 중에 생길 수 없다."""
    failures = []
    recorded = baseline["human_gt"]
    current = {
        str(p.relative_to(root)).replace("\\", "/"): digest(p)
        for p in sorted(root.glob(HUMAN_GT_GLOB))
    }
    for path in sorted(set(current) - set(recorded)):
        failures.append(Failure("NEW_HUMAN_GT", path))
    for path in sorted(set(recorded) & set(current)):
        if current[path] != recorded[path]:
            failures.append(Failure("HUMAN_GT_MODIFIED", path))
    return failures


def check_no_provider_adoption(root: Path) -> list[Failure]:
    """REG-009 — C0는 MIXED_SIGNAL이었다. change-point를 default로 올리지 않는다."""
    failures = []
    boundary = root / "src/v2_1_boundary.py"
    if boundary.is_file():
        text = boundary.read_text(encoding="utf-8")
        if 'DEFAULT_PROVIDER_NAME = "fixed_window_v1"' not in text:
            failures.append(Failure("DEFAULT_PROVIDER_CHANGED", "src/v2_1_boundary.py"))
    for config in sorted(root.glob("config*.yaml")):
        if _ADOPTION.search(config.read_text(encoding="utf-8")):
            failures.append(
                Failure("PROVIDER_ADOPTION_MARKER", str(config.relative_to(root)))
            )
    for path in _artifact_files(root):
        if path.suffix in (".json", ".yaml") and _ADOPTION.search(
            path.read_text(encoding="utf-8", errors="ignore")
        ):
            failures.append(
                Failure("PROVIDER_ADOPTION_MARKER", str(path.relative_to(root)))
            )
    return failures


def check_no_gyeongju_comparison(root: Path, baseline: dict) -> list[Failure]:
    """REF-003 — 사람이 쓴 보고서는 형식 참조다. 성능 대조 대상이 아니다.

    gyeongju는 dev 세트에 있어 정상 M8 산출물이 이미 존재한다. 그래서 존재가
    아니라 **기준선에 없던 산출물이 생겼는가**로 잰다.
    """
    recorded = set(baseline["gyeongju_artifacts"])
    current = {
        str(p.relative_to(root)).replace("\\", "/")
        for p in _artifact_files(root)
        if _GYEONGJU.search(p.name)
    }
    return [Failure("NEW_GYEONGJU_ARTIFACT", path)
            for path in sorted(current - recorded)]


def load_baseline(root: Path) -> dict:
    return json.loads((root / BASELINE_PATH).read_text(encoding="utf-8"))


def run_all(root: Path, baseline: dict | None = None) -> GuardReport:
    """가드 전부를 돌린다. 첫 실패에서 멈추지 않는다."""
    baseline = baseline if baseline is not None else load_baseline(root)
    failures = [
        *check_bcs_unchanged(root, baseline),
        *check_official_test_untouched(root, baseline),
        *check_no_m9_artifacts(root),
        *check_no_new_human_gt(root, baseline),
        *check_no_provider_adoption(root),
        *check_no_gyeongju_comparison(root, baseline),
    ]
    return GuardReport(not failures, failures)


def build_baseline(root: Path) -> dict:
    """현재 트리에서 기준선을 만든다. 승인된 시점에만 다시 만든다."""
    return {
        "generated": "2026-08-30",
        "note": "v2.1 구현 착수 시점의 연구 경계 기준선. 갱신은 별도 승인 사건이다.",
        "bcs_protected": _inventory(root, BCS_PROTECTED),
        "official_test": _inventory(root, OFFICIAL_TEST_PATHS),
        "human_gt": {
            str(p.relative_to(root)).replace("\\", "/"): digest(p)
            for p in sorted(root.glob(HUMAN_GT_GLOB))
        },
        "gyeongju_artifacts": sorted(
            str(p.relative_to(root)).replace("\\", "/")
            for p in _artifact_files(root)
            if _GYEONGJU.search(p.name)
        ),
    }

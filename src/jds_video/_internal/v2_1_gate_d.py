"""v2.1 Gate D — 연구 경계 최종 검증 (D-01).

새 실험도, 성능 확인도 아니다. **지켜온 경계가 저장소 상태에서도 그대로인지**를
기계가 다시 확인한다.

```
M9 미실행 · official test 미개방 · BCS core 무변경 · 새 human GT 없음
추가 모델 비교 없음 · change-point 미채택 · C0 tuning 없음
```

다섯은 A-11 가드가 이미 검사한다 — **다시 구현하지 않고 그대로 부른다.** 나머지
둘(모델 비교 · C0 tuning)만 여기서 더한다.

두 검사는 "있으면 실패"가 아니라 **"기록에 없던 것이 생기면 실패"**다. 과거 진단
산출물은 보존 대상이지 위반이 아니기 때문이다(A-11이 gyeongju에서 쓴 것과 같은
방식). 기록된 것이 조용히 바뀌어도 실패로 잡는다 — 역사를 다시 쓰는 것도 위반이다.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from v2_1_guards import (
    Failure,
    _artifact_files,
    check_bcs_unchanged,
    check_no_m9_artifacts,
    check_no_new_human_gt,
    check_no_provider_adoption,
    check_official_test_untouched,
    digest,
)
from v2_1_guards import load_baseline as load_boundary_baseline

INVENTORY_PATH = "docs/finalization/v2_1_gate_d_inventory_2026-09-02.json"

#: 산출물 **경로**의 M9 흔적. A-11 REG-007은 파일 이름만 보므로
#: `runs/m9_official/result.json`처럼 디렉터리에만 표시가 남는 경우를 놓친다.
#: A-11을 고치는 대신 Gate D에서 경로 수준으로 한 겹 더 본다(2026-09-02 발견).
_M9_PATH = re.compile(r"(^|/)m9[_\-/]", re.IGNORECASE)

#: 모델 대조 산출물로 읽히는 이름. 존재가 아니라 **추가**를 잡는다.
_MODEL_COMPARISON = re.compile(
    r"(compare|comparison|_vs_|threeway|benchmark|ranking|kanana|exaone|qwen3)",
    re.IGNORECASE,
)

#: 경계 탐색 튜닝으로 읽히는 이름.
_C0_TUNING = re.compile(
    r"(threshold|sweep|smoothing|min_?gap|tuning|grid_?search|optuna|change_?point)",
    re.IGNORECASE,
)

CONDITIONS = (
    "m9_not_executed",
    "official_test_unopened",
    "bcs_core_unchanged",
    "no_new_human_gt",
    "no_additional_model_comparison",
    "change_point_not_adopted",
    "no_c0_tuning",
)


@dataclass(frozen=True, slots=True)
class Condition:
    name: str
    ok: bool
    failures: tuple[Failure, ...]


@dataclass(frozen=True, slots=True)
class GateDReport:
    ok: bool
    conditions: tuple[Condition, ...]

    def failures(self) -> list[Failure]:
        return [f for condition in self.conditions for f in condition.failures]


def load_inventory(root: Path) -> dict:
    return json.loads((root / INVENTORY_PATH).read_text(encoding="utf-8"))


def _recorded_scan(root: Path, pattern: re.Pattern, recorded: dict, code: str):
    """기록에 없던 산출물과, 기록된 것의 변경을 함께 본다."""
    failures = []
    seen = set()
    for path in _artifact_files(root):
        if not pattern.search(path.name):
            continue
        relative = str(path.relative_to(root)).replace("\\", "/")
        seen.add(relative)
        if relative not in recorded:
            failures.append(Failure(code, relative))
        elif digest(path) != recorded[relative]:
            failures.append(Failure(code + "_MODIFIED", relative))
    for relative in sorted(set(recorded) - seen):
        if (root / relative).exists():
            continue
        failures.append(Failure(code + "_MISSING", relative))
    return failures


def check_no_m9_execution(root: Path) -> list[Failure]:
    """M9 실행 흔적을 **경로 전체**에서 본다. 이름만 보면 디렉터리를 놓친다."""
    found = sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in _artifact_files(root)
        if _M9_PATH.search(str(path.relative_to(root)).replace("\\", "/"))
    )
    return [Failure("M9_RUN_PATH", path) for path in found]


def check_no_new_model_comparison(root: Path, inventory: dict) -> list[Failure]:
    """Gate B 이후 새 모델 대조 실험이 추가되지 않았는가.

    과거 진단(Qwen ↔ Kanana · EXAONE 종결)은 **보존 대상**이다. 문자열이 있다는
    이유로 실패시키지 않는다.
    """
    return _recorded_scan(root, _MODEL_COMPARISON,
                          inventory["model_comparison_artifacts"],
                          "NEW_MODEL_COMPARISON")


def check_no_c0_tuning(root: Path, inventory: dict) -> list[Failure]:
    """C0를 채택하지 않은 것과 별개로, 이후에 튜닝을 돌린 흔적이 없는가.

    threshold · smoothing · min-gap · peak 파라미터 탐색이 대상이다.
    """
    return _recorded_scan(root, _C0_TUNING,
                          inventory["c0_tuning_artifacts"],
                          "C0_TUNING_ARTIFACT")


def verify_research_boundary(root: Path, baseline: dict | None = None,
                             inventory: dict | None = None) -> GateDReport:
    """일곱 조건을 전부 돌린다. 첫 실패에서 멈추지 않는다."""
    baseline = baseline if baseline is not None else load_boundary_baseline(root)
    inventory = inventory if inventory is not None else load_inventory(root)

    results = (
        ("m9_not_executed",
         check_no_m9_artifacts(root) + check_no_m9_execution(root)),
        ("official_test_unopened", check_official_test_untouched(root, baseline)),
        ("bcs_core_unchanged", check_bcs_unchanged(root, baseline)),
        ("no_new_human_gt", check_no_new_human_gt(root, baseline)),
        ("no_additional_model_comparison",
         check_no_new_model_comparison(root, inventory)),
        ("change_point_not_adopted", check_no_provider_adoption(root)),
        ("no_c0_tuning", check_no_c0_tuning(root, inventory)),
    )
    conditions = tuple(
        Condition(name, not failures, tuple(failures)) for name, failures in results
    )
    return GateDReport(all(c.ok for c in conditions), conditions)


def build_inventory(root: Path) -> dict:
    """현재 트리에서 기록을 만든다. **승인된 시점에만** 다시 만든다."""
    def scan(pattern):
        return {
            str(p.relative_to(root)).replace("\\", "/"): digest(p)
            for p in _artifact_files(root) if pattern.search(p.name)
        }

    return {
        "generated": "2026-09-02",
        "note": "Gate D 기준 기록. 과거 산출물은 보존 대상이고, 여기 없던 것이 "
                "생기면 위반이다.",
        "model_comparison_artifacts": scan(_MODEL_COMPARISON),
        "c0_tuning_artifacts": scan(_C0_TUNING),
    }

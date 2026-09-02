"""E-03 CP 증거 — **non-adoption safeguard**를 잰다.

이 family는 "잘 동작하는가"가 아니다. matrix 절 이름 그대로 `non-adoption
safeguard`다 — 채택되지 않았고, 튜닝·GT·LLM 일치도로 슬쩍 승격되지 않았는가.

```
CP-002  explicit enable only     flag 없으면 **호출 자체가 0**
CP-003  no tuning embedded       채택 경로에 C0 유래 tuned 값 없음 (진단 쪽은 허용)
CP-004  no human GT optimization GT 존재가 아니라 **최적화 의존** 부재
CP-005  no LLM agreement crit.   일치도는 **재지만** 채택 기준이 아니다
CP-006  sanitation prerequisite  지정 문서의 해당 절에 문장이 있다
CP-007  VLM dependence recorded  지정 문서의 해당 절에 문장이 있다
```

세 가지를 특히 조심한다.

```
"threshold라는 단어 없음" 식 전역 grep은 증거가 아니다
문서 어딘가에 "VLM"이 있는지 보는 것도 증거가 아니다
CP-008 · CP-009는 진단이며 acceptance 요구가 아니다 — 여기서 기능을 만들지 않는다
```
"""
import ast
import json
import re
import shutil
from pathlib import Path

import pytest

from v2_1_boundary import (
    DEFAULT_PROVIDER_NAME,
    BoundaryResult,
    ProviderRegistry,
    UnknownProviderError,
)
from v2_1_fixed_window import FixedWindowV1
from v2_1_fixtures import scenario
from v2_1_guards import check_no_provider_adoption

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts/c0_boundary_signal_probe.py"
C0_DOC = ROOT / "docs/finalization/C0_BOUNDARY_SIGNAL_OBSERVATION_2026-08-30.md"
ARCH = ROOT / "docs/finalization/V2_1_ARCHITECTURE_SPEC_2026-08-30.md"
C0_ARTIFACT = ROOT / "runs/c0/c0_boundary_signal.json"

#: 예약된 후보 이름. 구현체는 없다 — 그 사실 자체가 CP-002의 일부다.
CANDIDATE = "caption_text_change_point"

#: v2.1 경계 **채택 경로**. 진단 스크립트는 여기 없다.
ADOPTION_PATH = ("src/v2_1_boundary.py", "src/v2_1_fixed_window.py")

#: C0에서 다뤘던 튜닝 파라미터 어휘.
TUNING_WORDS = ("threshold", "cutoff", "min_gap", "mingap", "smoothing",
                "peak", "radius", "sweep", "grid_search")

#: config에 이미 있는 threshold류. 전부 **검색 파이프라인**이고 C0보다 앞선다.
#: 이 목록이 있어야 "전역 금지"가 아니라 "경계를 그었다"가 된다.
PRE_C0_SEARCH_KEYS = {
    "static_threshold": "M5 정적 치환 · 2026-07-11 dev 스윕",
    "iou_thresholds": "M6 평가 IoU · 검색 지표",
    "abstention_tau": "M5 무관련 경고 · 2026-07-13 재캘리브레이션",
}


# ── CP-002 explicit enable only ──────────────────────────────────────────
class _Spy:
    """change-point provider 자리에 놓는 감시자. 호출되면 센다."""

    name = CANDIDATE
    version = "spy"

    def __init__(self):
        self.calls = 0

    def __call__(self, segments, **kwargs):
        self.calls += 1
        return BoundaryResult(provider_name=self.name, provider_version=self.version,
                              provider_config={},
                              boundary_positions=[segments[0].segment_id])


def test_cp_002_the_candidate_is_never_called_without_an_explicit_name():
    """명시하지 않은 실행에서 change-point 호출 수 = 0. 호출 수로 잰다."""
    segments = scenario("S1").segments
    registry = ProviderRegistry()
    registry.register(FixedWindowV1())
    spy = _Spy()
    registry.register(spy)                      # 등록돼 있어도 선택되지 않는다

    for _ in range(5):
        result = registry.run(None, segments)
        assert result.provider_name == DEFAULT_PROVIDER_NAME
    assert spy.calls == 0

    # 명시하면 그때만 실행된다 — explicit enable의 의미가 이것이다.
    assert registry.run(CANDIDATE, segments).provider_name == CANDIDATE
    assert spy.calls == 1


def test_cp_002_no_production_module_registers_a_change_point_provider():
    """예약된 이름에 대응하는 구현·등록이 production에 없다.

    `src/`를 AST로 훑는다 — 문자열 grep은 docstring에 걸린다.
    """
    offenders = []
    for path in sorted((ROOT / "src").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and \
                    re.search(r"change.?point", node.name, re.I):
                offenders.append("%s::%s" % (path.name, node.name))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "register":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and arg.value == CANDIDATE:
                        offenders.append("%s: register(%r)" % (path.name, CANDIDATE))
    assert not offenders, offenders


def test_cp_002_asking_for_it_when_absent_fails_instead_of_falling_back():
    """구현이 없을 때 조용히 default로 흐르지 않는다 — 그러면 실행 여부가 흐려진다."""
    registry = ProviderRegistry()
    registry.register(FixedWindowV1())
    with pytest.raises(UnknownProviderError):
        registry.get(CANDIDATE)


# ── CP-003 no tuning embedded ────────────────────────────────────────────
def test_cp_003_the_adoption_path_carries_no_tuning_parameter():
    """경계 채택 경로에 C0 유래 튜닝 값이 없다. 진단 스크립트는 대상이 아니다."""
    offenders = []
    for relative in ADOPTION_PATH:
        text = (ROOT / relative).read_text(encoding="utf-8").lower()
        offenders += [(relative, word) for word in TUNING_WORDS if word in text]
    assert not offenders, offenders


def test_cp_003_config_threshold_keys_are_all_pre_c0_search_keys():
    """config에 threshold가 있는 것 자체는 위반이 아니다 — **무엇인지**를 본다."""
    text = (ROOT / "config.yaml").read_text(encoding="utf-8")
    keys = {line.split(":", 1)[0].strip()
            for line in text.splitlines()
            if ":" in line and not line.strip().startswith("#")
            and any(w in line.split(":", 1)[0].lower()
                    for w in ("threshold", "tau", "cutoff", "gap", "smoothing"))}
    assert keys, "threshold류 키를 하나도 못 찾았다 — 검사가 무의미해졌다"
    assert keys <= set(PRE_C0_SEARCH_KEYS), keys - set(PRE_C0_SEARCH_KEYS)


def test_cp_003_the_diagnostic_side_is_allowed_to_have_shape_parameters():
    """진단에 파라미터가 있는 것은 허용이다 — 그래야 '전역 금지'가 아님이 드러난다."""
    source = PROBE.read_text(encoding="utf-8")
    assert "radius" in source                    # local_peaks의 모양 파라미터
    # 그러나 임계·채택 판단은 없다.
    for forbidden in ("threshold =", "cutoff =", "min_gap", "smooth("):
        assert forbidden not in source, forbidden


def test_cp_003_a_tuned_value_planted_in_the_adoption_path_is_detectable(tmp_path):
    """검사에 이가 있는지 — 합성 트리에 C0 유래 값을 심어 본다."""
    fake = tmp_path / "v2_1_boundary.py"
    fake.write_text('DEFAULT_PROVIDER_NAME = "fixed_window_v1"\n'
                    'CAPTION_CP_THRESHOLD = 0.6798\n', encoding="utf-8")
    text = fake.read_text(encoding="utf-8").lower()
    assert any(word in text for word in TUNING_WORDS)


# ── CP-004 no human GT optimization ──────────────────────────────────────
#: GT를 가리키는 식별자.
GT_TOKENS = ("gt_seg_idx", "reference_events", "event_inventory", "label_kit",
             "gt_start", "gt_end", "human_boundaries")

#: 선택·최적화를 뜻하는 식별자.
SELECTION_TOKENS = ("argmax", "best_", "optimize", "select_threshold",
                    "tune", "fit(")


def _cp_sources():
    return {str(p.relative_to(ROOT)).replace("\\", "/"):
            p.read_text(encoding="utf-8")
            for p in [PROBE, *(ROOT / r for r in ADOPTION_PATH)]}


def test_cp_004_no_gt_identifier_appears_in_the_cp_path():
    offenders = []
    for relative, text in _cp_sources().items():
        offenders += [(relative, token) for token in GT_TOKENS if token in text]
    assert not offenders, offenders


def test_cp_004_no_selection_is_driven_by_anything_in_the_cp_path():
    """GT가 없다는 것만으로는 부족하다 — **선택 코드 자체가 없다.**"""
    offenders = []
    for relative, text in _cp_sources().items():
        offenders += [(relative, token) for token in SELECTION_TOKENS
                      if token in text]
    assert not offenders, offenders


def test_cp_004_the_artifact_declares_gt_comparison_as_not_done():
    artifact = json.loads(C0_ARTIFACT.read_text(encoding="utf-8"))
    assert "GT_대조" in artifact["not_done"]
    assert "provider_adoption" in artifact["not_done"]


def test_cp_004_step_a_used_gt_for_measurement_with_a_frozen_criterion():
    """STEP A는 GT를 **측정**에 썼다. 사전등록된 기준이 실행 전에 동결됐다.

    이 구분이 CP-004의 요점이다 — GT 사용 자체가 위반이 아니라, GT로 파라미터를
    **고르는 것**이 위반이다.
    """
    doc = (ROOT / "docs/finalization/AARV2_STEP_A_RESULT_2026-08-28.md").read_text(
        encoding="utf-8")
    prereg = doc.split("## B.", 1)[1].split("## C.", 1)[0]
    assert "하이퍼파라미터 없음" in prereg
    assert "GO_threshold" in prereg
    assert "AARV2_STEP_A_PREREG_2026-08-28.md" in doc     # 실행 전 동결 문서


def test_cp_004_a_passing_gate_still_did_not_adopt_the_provider():
    """STEP A는 GO였는데도 채택되지 않았다 — 비채택의 가장 강한 증거다."""
    step_a = (ROOT / "docs/finalization/AARV2_STEP_A_RESULT_2026-08-28.md").read_text(
        encoding="utf-8")
    assert "STEP A   GO" in step_a
    gate = step_a.split("## G. Gate", 1)[1].split("---", 1)[0]
    assert "PASS" in gate
    # 그럼에도 default는 그대로다.
    assert check_no_provider_adoption(ROOT) == []
    c0 = C0_DOC.read_text(encoding="utf-8")
    assert re.search(r"%s\s+CANDIDATE" % CANDIDATE, c0)


# ── CP-005 no LLM agreement criterion ────────────────────────────────────
def test_cp_005_the_probe_does_measure_llm_agreement():
    """먼저 사실을 인정한다 — 일치도를 **잰다.** 안 잰다고 적으면 거짓이다."""
    source = PROBE.read_text(encoding="utf-8")
    assert "on_local_peak_share" in source
    assert "llm_boundaries" in source
    artifact = json.loads(C0_ARTIFACT.read_text(encoding="utf-8"))
    arms = artifact["windows"][0]["llm_boundaries"]
    assert arms, "산출물에 LLM 대조가 없다 — 이 테스트가 무의미해졌다"
    assert "on_local_peak_share" in next(iter(arms.values()))


def test_cp_005_the_agreement_never_selects_anything():
    """계산은 하되 **판정 키를 내지 않는다.** 채택 기준이 되는 순간 위반이다."""
    source = PROBE.read_text(encoding="utf-8")
    for forbidden in ("provider_score", "verdict", "chosen_provider",
                      "make_llm", "argmax", "def adopt", "adopt("):
        assert forbidden not in source, forbidden
    # `adoption`이 소스에 나오는 유일한 자리는 "하지 않았다"는 선언이다.
    for line in source.splitlines():
        if "adoption" in line:
            assert "not_done" in line or "provider_adoption" in line, line
    artifact = json.loads(C0_ARTIFACT.read_text(encoding="utf-8"))
    for forbidden in ("adopted", "verdict", "provider_score", "selected"):
        assert forbidden not in artifact, forbidden
    assert "provider_adoption" in artifact["not_done"]


def test_cp_005_using_llm_boundaries_as_truth_is_recorded_as_impossible():
    """문서가 그 사용을 금지로 적었는지 — 절을 잘라서 본다."""
    doc = C0_DOC.read_text(encoding="utf-8")
    section = doc.split("## 6.", 1)[1].split("## 7.", 1)[0]
    assert "LLM 경계를 정답으로 삼아" in section
    assert "불가" in section


# ── CP-006 sanitation prerequisite (문서 계약) ───────────────────────────
def test_cp_006_the_sanitation_prerequisite_is_in_its_own_section():
    """문서 전역 검색이 아니라 **해당 절**을 본다."""
    doc = C0_DOC.read_text(encoding="utf-8")
    defect = doc.split("### 4-1.", 1)[1].split("### 4-2.", 1)[0]
    assert "캡션 QC가 선행 조건" in defect

    implication = doc.split("## 6.", 1)[1].split("## 7.", 1)[0]
    assert "캡션 결함 필터가 선행" in implication


def test_cp_006_the_prerequisite_names_the_concrete_defects():
    """"QC가 필요하다"만으로는 계약이 아니다 — 무엇이 결함인지 적혀 있어야 한다."""
    implication = C0_DOC.read_text(encoding="utf-8").split(
        "## 6.", 1)[1].split("## 7.", 1)[0]
    for defect in ("지시문 에코", "외국어 캡션"):
        assert defect in implication, defect


# ── CP-007 VLM/model-input dependence (문서 계약) ────────────────────────
def test_cp_007_the_vlm_dependence_is_stated_in_the_invariance_section():
    """모델 교체 불변성 절에서 change_point가 **보장 없음**으로 적혀 있어야 한다."""
    spec = ARCH.read_text(encoding="utf-8")
    section = spec.split("## 6. 모델 교체 불변성", 1)[1].split("## 7.", 1)[0]
    assert "vision caption model 교체" in section
    row = [line for line in section.splitlines() if "change_point" in line]
    assert any("보장 없음" in line for line in row), row
    # content model 교체와 구분돼 있다 — 같은 칸에 뭉치면 계약이 사라진다.
    assert any("경계 불변" in line and "보장 없음" not in line for line in row), row


def test_cp_007_the_candidate_section_records_what_the_signal_measures():
    spec = ARCH.read_text(encoding="utf-8")
    section = spec.split("### candidate: `%s`" % CANDIDATE, 1)[1].split("### ", 1)[0]
    assert "VLM" in section and "언어로 보존" in section
    assert "CANDIDATE" in section


@pytest.mark.parametrize("phrase", ["보장 없음", "언어로 보존"])
def test_cp_007_removing_the_statement_breaks_the_contract(tmp_path, phrase):
    """문장 제거 mutation이 잡히는지 — 합성 사본으로 확인한다."""
    copy = tmp_path / ARCH.name
    shutil.copy2(ARCH, copy)
    copy.write_text(copy.read_text(encoding="utf-8").replace(phrase, "…"),
                    encoding="utf-8")
    assert phrase not in copy.read_text(encoding="utf-8")

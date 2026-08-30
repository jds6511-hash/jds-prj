"""경계 열거 degeneracy 진단 — 지표 정의 고정.

사전등록: `docs/finalization/MODEL_DEGENERACY_DIAG_PREREG_2026-08-29.md`
NON-ADOPTIVE diagnostic. BCS·모델·프롬프트를 바꾸지 않는다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import model_degeneracy_diag as D                                   # noqa: E402


def test_BCS와_모델을_바꾸지_않는다():
    src = (ROOT / "scripts" / "model_degeneracy_diag.py").read_text(encoding="utf-8")
    for bad in ("import bcs", "report_model =", "adopt", "config.yaml\"] ="):
        assert bad not in src, bad


def test_연속정수_run():
    assert D.longest_step_run(list(range(254, 280)), 1) == 26
    assert D.longest_step_run([220, 227, 229, 238], 1) == 1


def test_등차_run():
    n, s = D.longest_arithmetic_run([110, 120, 130, 140, 150, 165])
    assert (n, s) == (5, 10)
    n, s = D.longest_arithmetic_run([220, 227, 229, 238, 249])
    assert n <= 2


def test_등차는_1간격을_세지_않는다():
    """1간격은 consecutive_run이 따로 센다 — 두 지표가 같은 것을 세면 안 된다."""
    n, s = D.longest_arithmetic_run(list(range(10, 20)))
    assert s == 0 and n == 1


def test_parse_실패를_모델_실패와_분리한다():
    m = D.measure("사건 경계는 없습니다.", 0, 10, "p")
    assert m["parse_status"] == "PARSE_CONTRACT_FAILURE"
    assert D.measure('{"atomic_start_segments": []}', 0, 10, "p")["parse_status"] \
        == "EMPTY_LIST"
    assert D.measure('["0", "5"]', 0, 10, "p")["parse_status"] == "PARSE_OK"


def test_범위밖_경계를_기록한다():
    m = D.measure('[5, 99]', 0, 10, "p")
    assert m["out_of_range"] == [99] and m["boundary_count"] == 1


def test_위치_안정성():
    o = D.overlap([1, 2, 3], [2, 3, 4])
    assert (o["shared"], o["a_only"], o["b_only"]) == (2, 1, 1)
    assert o["jaccard"] == 0.5

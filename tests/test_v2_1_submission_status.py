"""제출 profile 확정 — arm·SUBMISSION_READY·provenance가 흔들리지 않게 잠근다.

```
제출 arm        R1 / episode_content_v3_summary_only
기본 계약        v2 (교체하지 않았다)
SUBMISSION_READY YES — 다만 뜻이 좁다(의미적 사실성 독립 검증이 아니다)
41 = 39 + 2     parse 실패 2건을 숨기지 않는다
```

HWPX는 `.gitignore`가 막는 바이너리라 저장소에 없다. manifest가 sha256으로 가리키고,
파일이 로컬에 있으면 그 값이 맞는지 확인한다.
"""
import hashlib
import json
from pathlib import Path

from v2_1_prompt import CONTRACT, CONTRACT_V3, PROMPT_VERSION, contract_hash

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/finalization/V2_1_SUBMISSION_STATUS_2026-09-03.md"
MANIFEST = ROOT / "runs/v3_paired/submission_manifest.json"
RUN = ROOT / "runs/v3_paired/r1_v3"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


# ── 상태 선언 ────────────────────────────────────────────────────────────
def test_the_submission_arm_is_declared():
    text = _doc()
    assert "SUBMISSION ARM               = R1 / episode_content_v3_summary_only" in text
    assert "SUBMISSION_READY             = YES" in text


def test_submission_ready_is_narrowed_in_both_languages():
    """넓게 읽히면 GRD-004 waiver와 모순된다."""
    text = _doc()
    assert ("It does not mean that all generated summaries have been independently"
            in text)
    assert "의미적 사실성이 독립 검증되었다는 뜻은 아니다" in text


def test_the_default_contract_was_not_promoted():
    text = _doc()
    assert "default promotion                NOT ADOPTED" in text
    assert "repository default contract   episode_content_v2" in text
    # 문서 주장과 코드가 어긋나지 않는지 같이 본다.
    assert PROMPT_VERSION == "episode_content_v2"
    assert CONTRACT["output"]["optional"] == ["dialogue_note", "stt_cites"]


def test_the_two_failures_are_reported_not_hidden():
    text = _doc()
    assert "41  canonical episodes" in text
    assert "39  presentation-eligible" in text
    assert " 2  parse-contract failure" in text
    assert "EP35" in text and "EP39" in text


def test_the_doc_does_not_overclaim():
    text = _doc()
    for forbidden in ("entailment가 해결", "품질이 좋아졌", "GRD-004 해제"):
        assert forbidden not in text, forbidden
    # 문구를 금지하는 것이 아니라 **부정문으로만** 등장해야 한다.
    assert "`v3 worsens parsing`은 **주장하지 않는다.**" in text


def test_the_forbidden_follow_ups_are_written_down():
    text = _doc()
    for line in ("v3를 repository default로 변경",
                 "실패한 두 구간만 재생성해 cherry-pick",
                 "official test 접근 · M9 실행"):
        assert line in text, line


# ── manifest ─────────────────────────────────────────────────────────────
def test_the_manifest_pins_the_submission_contract():
    manifest = _manifest()
    assert manifest["submission_arm"] == "R1"
    assert manifest["submission_contract"] == CONTRACT_V3["version"]
    assert manifest["prompt_hash"] == contract_hash(CONTRACT_V3)
    assert manifest["default_contract_unchanged"] is True


def test_the_manifest_counts_match_the_run():
    manifest = _manifest()
    document = json.loads(
        (RUN / "S5/aar_canonical.json").read_text(encoding="utf-8"))
    run = json.loads((RUN / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["episodes"] == len(document["episodes"]) == 41
    assert manifest["presentation_eligible"] == run["distributions"][
        "presentation"]["eligible"] == 39
    assert manifest["parse_contract_failure"] == 2
    assert manifest["episodes"] == (manifest["presentation_eligible"]
                                    + manifest["parse_contract_failure"])
    assert manifest["fingerprint"]["prompt_version"] == CONTRACT_V3["version"]
    assert manifest["input"]["segments_sha256"] == (
        "aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92")


def test_the_manifest_records_a_measured_hangul_check():
    """"PASS"를 인자로 받지 않고 실제로 열어 본 결과다."""
    hangul = _manifest()["hangul"]
    assert hangul["hancom_open"] is True
    assert hangul["pdf_export"] is True
    assert hangul["pdf_bytes"] > 0
    assert _manifest()["structural_validator"] == "PASS"


def test_the_manifest_identifies_the_artifact_by_hash():
    artifact = _manifest()["artifact"]
    assert len(artifact["hwpx_sha256"]) == 64
    local = RUN / "report.hwpx"
    if local.is_file():                     # .gitignore가 막으므로 없을 수 있다
        assert hashlib.sha256(local.read_bytes()).hexdigest() == \
            artifact["hwpx_sha256"]


def test_the_manifest_states_what_it_does_not_claim():
    claims = _manifest()["not_claimed"]
    joined = " ".join(claims).lower()
    assert "entailment" in joined
    assert "grd-004" in joined
    assert "default" in joined

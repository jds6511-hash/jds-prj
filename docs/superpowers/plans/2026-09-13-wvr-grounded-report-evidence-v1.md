# WVR Grounded Report Evidence V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit all 116 frozen Qwen3-VL raw window outputs once, decide the preregistered sufficiency branch, and only when Branch A qualifies produce lineage-complete grounded details and diverse highlights.

**Architecture:** A pure standard-library core parses raw envelopes, classifies only explicit visible facts, validates lineage, evaluates the four frozen Branch A thresholds, and contains the Branch A selector. A one-shot runner snapshots all protected hashes, audits the complete universe, writes the applicable branch artifacts, rechecks protection, and refuses overwrite. Existing V2/V3, timeline, STT, beta/v3, report, and HWPX paths remain read-only.

**Tech Stack:** Python 3.12+ standard library, pytest, existing JSON artifacts and SHA256 conventions.

**Spec:** `docs/preregistration/WVR_GROUNDED_REPORT_EVIDENCE_V1_2026-09-13.md`

## Global Constraints

- Raw universe is exactly C01 24 + C02 24 + C03 24 + C04 24 + C05 20 = 116 files with manifest SHA256 `8c40bbe26b2e5e4e56800dbb5c87799e8d91c9df970bfac4a1e212c544cba485`.
- `visual inference = 0`, `STT inference = 0`, `beta/v3 regeneration = 0`, `text generation inference = 0`, and retry is zero.
- `BROAD_ACTIVITY`, canonical `OBSERVED_CHANGE`, `CONTEXT_INFERENCE`, and `UNCERTAINTY` never become high-confidence detail.
- Branch A requires usable-detail windows >= 5, distinct activities with detail >= 3, non-dominant activity detail >= 1, and lineage-complete grounded candidates >= 5.
- Any failed threshold closes as `CLOSED / GROUNDING_DETAIL_SOURCE_INSUFFICIENT`; Branch A downstream files must not exist.
- No result-driven regex, threshold, exception, selection, or text-template change is allowed.
- Existing V2/V3 report artifacts, timeline/lineage, canonical flow, beta/v3, M3 STT, official test, and M9 remain unchanged.

---

### Task 1: Raw Universe, Envelope Audit, and Visual-Fact Classifier

**Files:**
- Create: `src/wvr_grounded_report_evidence_v1.py`
- Create: `tests/test_wvr_grounded_report_evidence_v1.py`

**Interfaces:**
- Consumes: repository root, frozen segment plans, raw UTF-8 bytes, canonical activity set.
- Produces: `raw_universe(root: Path) -> list[dict]`, `extract_envelope(raw: str) -> dict`, `audit_one(source: dict, raw_bytes: bytes, allowed: set[str]) -> dict`, `manifest_sha256(sources: list[dict]) -> str`.

- [ ] **Step 1: Write failing universe and lineage tests**

```python
def test_raw_universe_has_frozen_counts_and_manifest(repo_root):
    rows = ge.raw_universe(repo_root)
    assert Counter(r["chunk"] for r in rows) == {
        "C01": 24, "C02": 24, "C03": 24, "C04": 24, "C05": 20}
    assert len(rows) == 116
    assert ge.manifest_sha256(rows) == \
        "8c40bbe26b2e5e4e56800dbb5c87799e8d91c9df970bfac4a1e212c544cba485"

def test_unknown_source_window_fails_closed(tmp_path):
    source = fixture_source(tmp_path, window="S99", plan_windows={"S01"})
    with pytest.raises(ge.GroundingError, match="unknown source window"):
        ge.audit_one(source, valid_raw(), ALLOWED)

def test_detail_outside_source_interval_fails_closed():
    observation = fixture_observation(start=0, end=48)
    observation["visual_facts"] = [{"text": "음식을 먹는다",
                                     "source_span": [48, 72]}]
    with pytest.raises(ge.GroundingError, match="outside source interval"):
        ge.validate_observation(observation)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
$env:UV_CACHE_DIR=(Resolve-Path '.uv-cache').Path
uv run --offline --no-project --with pytest python -m pytest tests/test_wvr_grounded_report_evidence_v1.py -q -p no:cacheprovider --basetemp .pytest-tmp-grounded-red1
```

Expected: collection fails with `ModuleNotFoundError: wvr_grounded_report_evidence_v1`.

- [ ] **Step 3: Implement the frozen universe and envelope parser**

```python
RAW_ROOTS = {
    "C01": "runs/wvr_video_overview_preview_v2",
    "C02": "runs/wvr_chunk_overview_v2/C02",
    "C03": "runs/wvr_chunk_overview_v2/C03",
    "C04": "runs/wvr_chunk_overview_v2/C04",
    "C05": "runs/wvr_chunk_overview_v2/C05",
}

def extract_envelope(raw):
    text = raw.strip()
    low, high = text.find("{"), text.rfind("}")
    if low < 0 or high <= low:
        raise GroundingError("raw JSON object not found")
    value = json.loads(text[low:high + 1])
    if not isinstance(value, dict):
        raise GroundingError("raw JSON object required")
    return {"json": value, "prefix": text[:low].strip("` \r\n"),
            "suffix": text[high + 1:].strip("` \r\n")}
```

Pair each raw with its frozen `video_overview_v2_segments.json` row. Reject
duplicate/missing segment IDs and raw-count drift before opening raw content.

- [ ] **Step 4: Write failing fact-disposition tests**

```python
@pytest.mark.parametrize("field,text,reason", [
    ("BROAD_ACTIVITY", "음식 준비 및 조리", "broad_label_only"),
    ("OBSERVED_CHANGE", "식사 → 이동", "canonical_transition_only"),
    ("CONTEXT_INFERENCE", "병원에서 퇴원한 것으로 보임", "context_inference"),
    ("UNCERTAINTY", "재료를 다루는 듯함", "uncertainty_only"),
])
def test_four_contract_fields_never_become_visual_fact(field, text, reason):
    assert ge.classify_text(field, text)["rejection_reason"] == reason

@pytest.mark.parametrize("text", [
    "여행을 계획하며 물건을 포장한다",
    "기분이 좋아 음식을 먹는다",
    "직장 업무를 위해 옷을 손질한다",
])
def test_unsupported_context_phrase_is_rejected(text):
    assert ge.classify_text("RAW_EXTRA", text)["eligible"] is False

def test_explicit_visible_fact_is_retained_with_verbatim_source():
    got = ge.classify_text("RAW_EXTRA", "재료를 손으로 다루고 그릇에 담는다")
    assert got == {"eligible": True,
                   "text": "재료를 손으로 다루고 그릇에 담는다",
                   "source_text": "재료를 손으로 다루고 그릇에 담는다",
                   "confidence": "high", "rejection_reason": None}
```

- [ ] **Step 5: Implement deterministic classification and observation validation**

Use the exact action roots, generic nouns, and forbidden markers in prereg §5.
`RAW_EXTRA` is eligible only when it contains an allowed action and, except for
walking/movement, an allowed visible noun. Store every rejected string and its
reason in the audit. Require `source.chunk`, `source.window`, `source.raw_path`,
64-hex `source.raw_sha256`, and a fact source span contained in the source window.

- [ ] **Step 6: Verify GREEN and commit**

Run the Task 1 test command. Expected: all Task 1 tests pass.

```bash
git add src/wvr_grounded_report_evidence_v1.py tests/test_wvr_grounded_report_evidence_v1.py
git commit -m "feat: add frozen raw detail auditor"
```

---

### Task 2: Sufficiency Gate and Branch-Safe Runner

**Files:**
- Modify: `src/wvr_grounded_report_evidence_v1.py`
- Modify: `tests/test_wvr_grounded_report_evidence_v1.py`
- Create: `scripts/wvr_grounded_report_evidence_v1_run.py`

**Interfaces:**
- Consumes: all 116 audit rows, frozen timeline/canonical flow, protected paths.
- Produces: `evaluate_sufficiency(audits: list[dict], timeline: dict) -> dict`, `snapshot_sources(root: Path) -> dict`, and one-shot runner outputs.

- [ ] **Step 1: Write failing gate and protection tests**

```python
def test_exact_branch_a_thresholds_are_conjunctive():
    audits = qualifying_audits(windows=5, activities=3,
                               non_dominant=1, candidates=5)
    assert ge.evaluate_sufficiency(audits, TIMELINE)["branch"] == "A"
    for key in ("usable_detail_windows", "distinct_activities_with_detail",
                "non_dominant_activities_with_detail",
                "lineage_complete_candidates"):
        changed = copy.deepcopy(audits)
        lower_metric_by_one(changed, key)
        assert ge.evaluate_sufficiency(changed, TIMELINE)["branch"] == \
            "SOURCE_INSUFFICIENT"

def test_source_insufficient_writes_only_audit_record_and_result(tmp_path):
    run = load_runner()
    result = run.execute(tmp_path, audit_fixture="broad-only")
    assert result["status"] == "CLOSED / GROUNDING_DETAIL_SOURCE_INSUFFICIENT"
    assert result["new_visual_inference_required"] == "UNKNOWN"
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "execution_record.json", "raw_detail_audit.json", "result.json"]
    assert result["inference"] == {"visual": 0, "stt": 0,
                                    "beta_v3_regeneration": 0,
                                    "text_generation": 0}

def test_source_hash_drift_fails_closed(tmp_path):
    before = ge.snapshot_sources(tmp_path)
    protected_file(tmp_path).write_text("changed", encoding="utf-8")
    with pytest.raises(ge.GroundingError, match="source hash drift"):
        ge.assert_unchanged(before, ge.snapshot_sources(tmp_path))
```

- [ ] **Step 2: Run focused tests and verify RED**

Expected failures: `evaluate_sufficiency`, `snapshot_sources`, and runner
`execute` do not yet exist.

- [ ] **Step 3: Implement the conjunction gate and one-shot runner**

```python
def evaluate_sufficiency(audits, timeline):
    metrics = compute_gate_metrics(audits, timeline)
    passed = (metrics["usable_detail_windows"] >= 5 and
              metrics["distinct_activities_with_detail"] >= 3 and
              metrics["non_dominant_activities_with_detail"] >= 1 and
              metrics["lineage_complete_candidates"] >= 5)
    return {"branch": "A" if passed else "SOURCE_INSUFFICIENT",
            "metrics": metrics, "all_thresholds_pass": passed}
```

The runner must refuse when `runs/wvr_grounded_report_v1` already exists. It
writes an initial execution record before opening semantic raw content, updates
`raw_files_inspected` after each unique file, requires exactly 116, writes the
audit, decides the branch, checks source hashes, and stops immediately on Branch
B. It contains no model/runtime imports.

- [ ] **Step 4: Verify GREEN and commit**

Run all tests in `tests/test_wvr_grounded_report_evidence_v1.py`.

```bash
git add src/wvr_grounded_report_evidence_v1.py scripts/wvr_grounded_report_evidence_v1_run.py tests/test_wvr_grounded_report_evidence_v1.py
git commit -m "feat: add grounded evidence branch gate"
```

---

### Task 3: Branch A Grounded Stores and Diversity-Aware Highlights

**Files:**
- Modify: `src/wvr_grounded_report_evidence_v1.py`
- Modify: `scripts/wvr_grounded_report_evidence_v1_run.py`
- Modify: `tests/test_wvr_grounded_report_evidence_v1.py`

**Interfaces:**
- Consumes: qualifying audit rows and frozen timeline/lineage.
- Produces: `build_grounded_store`, `build_candidates`, `select_highlights`, `render_highlight`, `compare_v3`, and Branch A JSON artifacts.

- [ ] **Step 1: Write failing schema and selection tests**

```python
def test_detail_without_lineage_is_rejected():
    detail = valid_detail(); del detail["source"]
    with pytest.raises(ge.GroundingError, match="source lineage"):
        ge.validate_detail(detail)

def test_activity_outside_allowed_or_source_set_is_rejected():
    candidate = valid_candidate(activity=["미등록 활동"])
    with pytest.raises(ge.GroundingError, match="unknown activity"):
        ge.validate_candidate(candidate, ALLOWED)

def test_duplicate_id_and_nonmonotonic_time_are_rejected():
    rows = [valid_highlight("H01", 20, 30), valid_highlight("H01", 0, 10)]
    with pytest.raises(ge.GroundingError):
        ge.validate_highlights(rows, ALLOWED)

def test_selector_caps_identical_signature_at_two_and_keeps_zones_and_final():
    got = ge.select_highlights(selection_fixture(), FINAL_SPAN,
                               dominant={"음식 준비 및 조리", "구매 또는 둘러보기"})
    assert 5 <= len(got) <= 8
    assert max(Counter(tuple(x["activities"]) for x in got).values()) <= 2
    assert {x["temporal_zone"] for x in got} == {"early", "middle", "late"}
    assert [got[-1]["start_sec"], got[-1]["end_sec"]] == FINAL_SPAN
    assert sum(bool(set(x["activities"]) - DOMINANT) for x in got) >= 2
```

- [ ] **Step 2: Write failing text-contract tests**

```python
def test_same_label_and_nonadjacent_highlights_never_claim_transition():
    same = ge.render_highlight(valid_highlight("H01", 0, 24,
                                               activity=["식사"]))
    assert "전환" not in same
    pair = ge.render_pair(valid_highlight("H01", 0, 24),
                          valid_highlight("H02", 48, 72))
    assert "전환" not in pair

def test_compound_label_uses_separator_not_broken_particle():
    text = ge.render_highlight(valid_highlight(
        "H01", 0, 24, activity=["구매 또는 둘러보기", "음식 준비 및 조리"]))
    assert "구매 또는 둘러보기 · 음식 준비 및 조리" in text
    assert "둘러보기과" not in text

def test_adjacent_different_pair_may_claim_transition():
    pair = ge.render_pair(valid_highlight("H01", 0, 24, activity=["식사"]),
                          valid_highlight("H02", 24, 48, activity=["이동"]))
    assert "전환" in pair
```

- [ ] **Step 3: Implement store, candidates, selector, and comparison**

Implement the exact prereg §8–§10 lexicographic rank and constraints. The runner
calls these functions only when the gate branch is `A`, writes the seven Branch
A data artifacts, validates them, compares against the frozen V3 metrics, and
never renders Overview/report/HWPX.

- [ ] **Step 4: Verify GREEN and mutation coverage**

Run the complete new test file. Confirm tests fail if the activity-signature cap
is changed to three, if a context value is promoted, if a source hash is
removed, or if `<=` replaces exact adjacency.

- [ ] **Step 5: Run report-path regression tests and commit**

```powershell
uv run --offline --no-project --with pytest python -m pytest tests/test_wvr_whole_video_report_v1.py tests/test_wvr_whole_video_report_v2.py tests/test_wvr_whole_video_report_v3.py tests/test_wvr_grounded_report_evidence_v1.py -q -p no:cacheprovider --basetemp .pytest-tmp-grounded-regression
```

```bash
git add src/wvr_grounded_report_evidence_v1.py scripts/wvr_grounded_report_evidence_v1_run.py tests/test_wvr_grounded_report_evidence_v1.py
git commit -m "feat: add grounded diversity highlight path"
```

---

### Task 4: One-Shot Raw Audit, Branch Decision, and Reviewer Record

**Files:**
- Generate: `runs/wvr_grounded_report_v1/raw_detail_audit.json`
- Generate: `runs/wvr_grounded_report_v1/execution_record.json`
- Generate: `runs/wvr_grounded_report_v1/result.json`
- Generate only on Branch A: the seven downstream files listed in prereg §11
- Create: `docs/probes/WVR_GROUNDED_REPORT_EVIDENCE_V1_RESULT_2026-09-13.md`

**Interfaces:**
- Consumes: committed runner at a clean tracked HEAD and frozen protected sources.
- Produces: exactly one complete audit, one branch decision, and a copy-ready reviewer report.

- [ ] **Step 1: Preflight without semantic raw inspection**

Run source count, manifest hash, output-absence, and protected-hash checks. Abort
before audit if any differs from prereg. Record code HEAD and prereg commit.

- [ ] **Step 2: Execute the audit exactly once**

```powershell
$env:UV_CACHE_DIR=(Resolve-Path '.uv-cache').Path
$env:PYTHONIOENCODING='utf-8'
uv run --offline --no-project python scripts/wvr_grounded_report_evidence_v1_run.py
```

Expected: `raw_files_inspected == 116`, retry zero, and either Branch B closure
or Branch A `EXECUTED / REVIEW_PENDING`. Do not run this command twice.

- [ ] **Step 3: Enforce the branch stop**

For `SOURCE_INSUFFICIENT`, confirm only the three always-produced files exist,
the status is `CLOSED / GROUNDING_DETAIL_SOURCE_INSUFFICIENT`, and stop all
downstream functions. For Branch A, validate all seven downstream artifacts,
5–8 highlights, 100% lineage, activity cap, temporal coverage, final phase, text
contracts, and comparison metrics.

- [ ] **Step 4: Recheck source protection and tests**

Compare raw manifest and all prereg §2 hashes before/after. Run the focused
regression command from Task 3. Run the repository full suite in the configured
server environment and report pre-existing failures separately without fixing
them.

- [ ] **Step 5: Write and commit the result record**

The result document includes raw audit counts, usable/broad-only counts, the
four gate metrics, the exact branch decision, grounded-store/highlight metrics
only when Branch A ran, inference counters, protected hashes, test output, and
the applicable status. It does not declare architecture PASS, baseline
replacement, or new-inference necessity.

```bash
git add docs/probes/WVR_GROUNDED_REPORT_EVIDENCE_V1_RESULT_2026-09-13.md
git commit -m "result: record grounded report evidence V1"
```

Then provide the result in one reviewer-copyable block and STOP.

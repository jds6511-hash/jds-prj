# WVR Semantic Boundary Candidate Shadow V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute the preregistered blinded semantic chapter-boundary candidate proposer without generating chapters or revealing candidate timestamps.

**Architecture:** A pure Python core deterministically derives 144 opaque candidate packets from the frozen Conservative Event Map. Separate command-line tools build sealed inputs, execute exactly 18 one-shot text-LLM batches, persist raw output before parsing, validate all artifacts, and record reviewer verdicts without revealing mappings prematurely.

**Tech Stack:** Python 3, pytest, pinned Hugging Face Transformers runtime, JSON/Markdown artifacts, Git provenance.

**Spec:** `docs/preregistration/WVR_SEMANTIC_BOUNDARY_CANDIDATE_SHADOW_V1_2026-09-10.md`

## Global Constraints

- Frozen map SHA256: `0ebecf34e84550805392bfcc8b4681f5028679250736a03f230dafb32d692e8c`.
- Frozen submission SHA256: `5732075871fd7902d52239cebced28f9489a0f558dac67c61f5d2ca994e9cd7b`.
- Proposer runtime: `Qwen/Qwen2.5-7B-Instruct`, revision `a09a35458c702b33eeacc393d103063234e8bc28`, bf16, SDPA, no 4-bit loading, greedy, 2048 tokens, one attempt per batch.
- Candidate universe is the 144 unique internal source-event start times; opaque IDs use the preregistered SHA256 permutation.
- Prompts and reviewer materials contain no timestamps, event/window/region/grid identifiers, prior chapter content, preferred source, or conflict winner.
- Mapping remains sealed until every packet candidate has a reviewer verdict; executor never supplies semantic or final verdicts.
- No new VLM inference, Track A input, chapter/Overview/Analysis/Conclusion/HWPX generation, official test, M9, or submission mutation.
- `tests/test_wvr_boundary_candidate_v1.py` was inherited at SHA256 `6aa39751fb74baa9e2526af466800855e2f167b15c0e522bd872097d9c294b2f`; reviewer-approved errata 2 §30 and errata 3 §31 correct only WVR-B14 and structural leakage tests B11/B12/B15, producing SHA256 `355432494ddd129a51cf582ce580722c296dbae8b169cd97b2319ec0cdded6b4`.

---

### Task 1: Core deterministic candidate and sealed packet contract

**Files:**
- Create: `src/wvr_boundary_candidate_v1.py`
- Create: `scripts/wvr_bcand_build.py`
- Create: `scripts/wvr_bcand_verdicts.py`
- Test: `tests/test_wvr_boundary_candidate_v1.py`

**Interfaces:**
- Consumes: frozen `conservative_event_map_v1.json` and existing `wvr_conservative_map_v1` helpers.
- Produces: `source_events`, `candidate_times`, `blind_ids`, `build_candidates`, `render_block`, `leakage_audit`, `batches`, `render_prompt`, parsing/reduction/seal helpers, deterministic builder artifacts, and reviewer-only verdict recording/reveal gate.

- [x] **Step 1: Verify inherited RED**

Run: `python -m pytest tests/test_wvr_boundary_candidate_v1.py -q`

Expected: collection fails because `wvr_boundary_candidate_v1` and current-event scripts do not exist.

- [x] **Step 2: Implement the minimal core contract**

Implement the public functions and constants exercised by WVR-B01 through WVR-B25 and WVR-B27 through WVR-B30. Use exact preregistered ID hashing, 30-second overlap contexts, opaque observation-set ordering, strict schemas, and sealed mappings.

```python
def blind_ids(times: list[float]) -> list[dict]: ...
def build_candidates(events: list[dict], document: dict) -> list[dict]: ...
def leakage_audit(texts: list[str], events: list[dict], candidates: list[dict]) -> dict: ...
def parse_batch(payload: dict, expected_ids: list[str]) -> dict[str, dict]: ...
```

- [x] **Step 3: Implement deterministic build and verdict boundaries**

`wvr_bcand_build.py` writes only candidates, sealed map, deterministic batch membership, and 18 LF-only rendered prompts. `wvr_bcand_verdicts.py` records only reviewer verdicts and refuses reveal until the entire packet ID set is adjudicated.

```python
def main(argv=None) -> int: ...
def record(runs: Path, payload: dict) -> dict: ...
def reveal(runs: Path) -> dict[str, float]: ...
```

- [x] **Step 4: Verify inherited GREEN**

Run: `python -m pytest tests/test_wvr_boundary_candidate_v1.py -q`

Expected: `30 passed` with only the reviewer-approved WVR-B14 correction recorded in the integrity audit.

---

### Task 2: One-shot runner, raw parser, self-check, and final validator

**Files:**
- Create: `tests/test_wvr_boundary_candidate_runtime_v1.py`
- Create: `scripts/wvr_bcand_selfcheck.py`
- Create: `scripts/wvr_bcand_run.py`
- Create: `scripts/wvr_bcand_parse.py`
- Create: `scripts/wvr_bcand_validate.py`

**Interfaces:**
- Consumes: Task 1 build artifacts and the existing `llm.make_llm`/`llm.llm_provenance` boundary.
- Produces: pre-inference gate report, one raw file per unfinished batch, record with executor handoff provenance, parsed proposals, leakage audit, reviewer packet, weak appendix, summary, and a machine-readable validator result.

- [x] **Step 1: Write runtime boundary tests**

Tests use temporary run directories and a deterministic fake generator injected below the pinned Transformers loader. They verify refusal on bad hashes/leakage/runtime provenance, raw-before-parse ordering, no overwrite/retry, remaining-batch resume only, strict parsing, full ID coverage, artifact reduction, and validator rejection of mapping/downstream leakage.

```python
def test_runner_persists_each_raw_before_any_parse(tmp_path, monkeypatch): ...
def test_runner_refuses_existing_raw_and_never_retries(tmp_path, monkeypatch): ...
def test_parser_requires_all_eighteen_raw_batches(tmp_path): ...
def test_validator_rejects_premature_mapping_or_downstream_artifact(tmp_path): ...
```

- [x] **Step 2: Verify runtime RED**

Run: `python -m pytest tests/test_wvr_boundary_candidate_runtime_v1.py -q`

Expected: collection fails because runtime scripts do not exist.

- [x] **Step 3: Implement pre-inference self-check**

The self-check recomputes frozen hashes, candidates, batch coverage, prompt-template/rendered hashes, leakage audits, mapping seal, alternative-observation coverage, submission integrity, and absence of forbidden current-event artifacts.

- [x] **Step 4: Implement one-shot batch runner**

The runner loads model revision/runtime exactly once, skips only already complete raw batches during a documented resume, refuses inconsistent partial state, writes every prompt and raw output with LF endings, hashes raw bytes, and never parses.

- [x] **Step 5: Implement strict parser and reviewer material builder**

The parser reads persisted raw only, checks each expected batch ID set, writes all proposals, leakage audit, STRONG+AMBIGUOUS packet, WEAK appendix, packet IDs, density diagnostic, and executor state without mappings or verdicts.

- [x] **Step 6: Implement final validator**

The validator independently rebuilds deterministic inputs, checks all 18 raw hashes and 144 IDs, confirms schema/vocabulary/reduction/seal/downstream boundaries, and reports technical PASS/FAIL only.

- [x] **Step 7: Verify runtime and inherited GREEN**

Run: `python -m pytest tests/test_wvr_boundary_candidate_runtime_v1.py tests/test_wvr_boundary_candidate_v1.py -q`

Expected: all current-event tests pass.

---

### Task 3: Implementation verification and immutable implementation commit

**Files:**
- Modify: only files created in Tasks 1-2 plus this plan.

**Interfaces:**
- Consumes: complete current-event implementation.
- Produces: clean implementation commit containing no inference artifacts.

- [x] **Step 1: Run current-event self-check in a temporary copy**

Run builder and self-check against a temporary run directory containing only the frozen map; confirm 144 candidates, 18 batches, zero leakage, and no model call.

- [x] **Step 2: Run mutation tests and full suite**

Run: `python -m pytest tests/test_wvr_boundary_candidate_v1.py tests/test_wvr_boundary_candidate_runtime_v1.py -q`

Run: `python -m pytest tests/ -q`

Evidence before the implementation commit: current-event `41 passed`; full suite
`5004 passed, 3 skipped, 2 repository-state gate failures`. The two failures require
the implementation to be committed and pushed and are rerun after that transition.

- [x] **Step 3: Confirm frozen boundaries**

Recompute map/submission hashes and confirm no `bcand_v1_raw_*`, proposal, packet, chapter, Overview, Analysis, Conclusion, or HWPX artifact exists before the implementation commit.

- [ ] **Step 4: Commit implementation**

Stage the plan, inherited test, core module, all current-event scripts, and runtime tests; commit with a message identifying implementation as pre-generation with zero artifacts.

---

### Task 4: Pre-inference gate and first proposer execution

**Files:**
- Create under `runs/wvr_light_v1/`: preregistered `bcand_v1_*` build, raw, parsed, audit, packet, appendix, and summary artifacts only.

**Interfaces:**
- Consumes: clean implementation commit checked out on the approved lab GPU environment.
- Produces: exactly 18 batch raw outputs from the frozen proposer runtime and derived reviewer artifacts.

- [ ] **Step 1: Push immutable provenance when available**

Push the non-rewritten implementation history to the configured origin if network and repository permissions permit.

- [ ] **Step 2: Recheck hashes and run pre-inference gate**

Run builder and `wvr_bcand_selfcheck.py`; require exact frozen map/submission hashes, 144 candidates, 18 unique batches, sealed mappings, neutral prompt hashes, and zero leakage.

- [ ] **Step 3: Execute FIRST inference once**

On the approved lab 4090 environment, run `wvr_bcand_run.py` using the frozen model revision/runtime. Do not retry a completed batch; resume only missing batches after a process interruption and record `resumed_batches`.

- [ ] **Step 4: Parse and validate**

Run `wvr_bcand_parse.py`, current-event tests, full suite, and `wvr_bcand_validate.py`. Do not reveal `bcand_v1_blind_map.json` or include it in reviewer-facing reporting.

- [ ] **Step 5: Document and commit results**

Write the probe report with executor provenance, distributions, timestamp-free reviewer packet content, technical validation, mutation/full-suite evidence, and only `EXECUTED / REVIEW_PENDING`; commit and push without semantic adjudication.

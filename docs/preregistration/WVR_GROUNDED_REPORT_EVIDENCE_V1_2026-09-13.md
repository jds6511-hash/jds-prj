# WVR_GROUNDED_REPORT_EVIDENCE_V1 — design/preregistration

Date: 2026-09-13  
Event: `WVR_GROUNDED_REPORT_EVIDENCE_V1`

## 1. Scope and protected baselines

This incident tests whether already-persisted Qwen3-VL window raw outputs retain
usable observable visual detail after the broad-activity pipeline. It does not
replace or reopen either baseline:

```text
WVR_WHOLE_VIDEO_REPORT_V2
CLOSED / WHOLE_VIDEO_REPORT_PASS

WVR_WHOLE_VIDEO_REPORT_V3_USABILITY
CLOSED / WHOLE_VIDEO_REPORT_USABILITY_HOLD
```

No visual, STT, beta/v3, Overview, Analysis, Conclusion, report, or HWPX
generation is authorized. Existing raw files are read-only. Official test and
M9 remain unopened/not invoked.

## 2. Frozen source manifest

The audit universe is exactly 116 persisted segment raw files:

```text
C01  runs/wvr_video_overview_preview_v2/              24
C02  runs/wvr_chunk_overview_v2/C02/                  24
C03  runs/wvr_chunk_overview_v2/C03/                  24
C04  runs/wvr_chunk_overview_v2/C04/                  24
C05  runs/wvr_chunk_overview_v2/C05/                  20
```

Only files matching `video_overview_v2_segment_S*_raw.txt` belong to the raw
universe. The cross-platform manifest digest is computed by sorting the key
`<chunk>/<filename>` by Unicode code point and hashing, for each file, UTF-8 key
+ NUL + binary SHA256 bytes + LF.

```text
raw file count          116
raw manifest SHA256     8c40bbe26b2e5e4e56800dbb5c87799e8d91c9df970bfac4a1e212c544cba485
```

Other protected hashes before audit:

```text
whole_video_activity_timeline.json
ba43a395c26342b6e028b32e33db629c82bf08c3d74785e211c7b04fb5537937

timeline_lineage.json
23d9734363c5f98c507bce4b4c76ae913f9359d091d22204ebfa5261fb758e8e

canonical_flow.json
f1bb720e48b602030143eebd43a200098cc24a125176116e1ff7587295c2858f

overview_result.json
f5d9cc5efcbf1af70e453c7536468b861e2e5eb977604d0657f839dc101b4ba6

M3 segments.json
aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92

WVR V2 artifact tree
c30c209951b8a487bca7dbc4b6428762844b48407e85f1706ac2349d4438d2f9

WVR V3 artifact tree
174ce25ba807e1f90b283547889911373f105eb13f1c584bbaba65a3bac5077a

beta/v3 b2run tree
63f7e620654376344cf7853023755512d0eeaa6384e22f4303eb36fc9fb5bf3a
```

Tree digests use the same sorted relative-path + file-SHA algorithm. Every
protected digest must match after execution.

## 3. Architectural alternatives and decision

Three approaches were considered:

1. **Raw-first recovery adapter — selected.** Audit all 116 raw files and
   recover only explicit observable detail already present. This preserves the
   experiment boundary and can prove either recoverability or insufficiency.
2. Parse only normalized summaries. Rejected because those artifacts have
   already enforced the exact four-field contract and could hide text outside
   the parsed JSON object.
3. Run a new visual prompt or manually annotate frames. Rejected in this
   incident because it changes the observation source and requires separate
   reviewer authorization.

## 4. Raw audit contract

Each raw file is decoded as UTF-8 and audited byte-for-byte without rewriting.
The existing parser behavior is reproduced to identify one JSON object,
optionally surrounded by a Markdown fence or prefix/suffix text. The audit
records:

```text
chunk
window/segment id
absolute source window start/end
raw path
raw SHA256
JSON parse status
JSON keys
non-JSON prefix/suffix after fence removal
BROAD_ACTIVITY
OBSERVED_CHANGE
CONTEXT_INFERENCE
UNCERTAINTY
detail candidates and disposition
```

The absolute window is taken from the frozen segment plan paired to that raw,
not inferred from its filename. Unknown/missing source windows fail closed.

## 5. Grounded visual fact definition

A high-confidence `visual_fact` must satisfy every rule:

1. The text occurs verbatim in the frozen raw bytes outside
   `CONTEXT_INFERENCE` and is more specific than a canonical broad label or a
   canonical `A → B` transition.
2. It is a directly visible action/state involving a visible actor, generic
   object, or movement. Allowed semantic families are handling/cutting/mixing/
   placing food or materials; eating/drinking; walking/moving; wrapping/folding;
   handling or repairing clothing/fabric; and visible cleanup.
3. It contains no uncertainty marker and no context, intent, cause, plan,
   emotion, occupation, medical, or inferred-place claim.
4. Its source window and raw SHA256 are known and its interval contains the
   detail.

The following deterministic dispositions apply:

```text
BROAD_ACTIVITY value                    broad label only; never a detail
OBSERVED_CHANGE canonical A → B         change only; never a detail
CONTEXT_INFERENCE value                 forbidden as factual detail
UNCERTAINTY value                       uncertainty store only; never high confidence
fence/language boilerplate              ignored
extra explicit visible-action text      eligible after all filters
extra JSON field with visible fact      eligible after all filters, while recording schema drift
```

Allowed direct-action roots:

```text
다루, 자르, 썰, 섞, 젓, 담, 넣, 꺼내, 놓, 집, 먹, 마시,
걷, 이동, 포장, 감싸, 접, 손질, 수선, 꿰매, 바느질, 정리,
씻, 조리, 착용, 벗
```

Allowed generic visible nouns:

```text
손, 사람, 재료, 음식, 그릇, 용기, 도구, 의류, 옷, 천,
물건, 포장재, 종이
```

Walking/movement facts may qualify without an object noun. Other facts require
at least one allowed visible noun and one direct-action root. Exact object names
may be retained only when they occur verbatim in raw and no uncertainty marker
is attached; otherwise they are generalized to the closest allowed generic
noun while storing both verbatim source text and normalized fact.

Forbidden markers include:

```text
불명확, 불확실, 애매, 추정, 가능성, 듯, 아마,
의도, 목적, 계획, 예정, 기분, 감정, 일상, 습관,
퇴원, 병원, 직장, 업무, 휴가, 여행, 방문 예정, 선물용
```

STT and beta/v3 prose are not read by the extractor. A fact failing any rule is
recorded with a rejection reason, not repaired or paraphrased into eligibility.

## 6. Grounding schema and lineage

Eligible and uncertain observations use:

```json
{
  "observation_id": "GO0001",
  "start_sec": 0.0,
  "end_sec": 48.0,
  "broad_activity": ["음식 준비 및 조리"],
  "visual_facts": [
    {
      "text": "normalized conservative fact",
      "source_text": "verbatim raw substring",
      "confidence": "high"
    }
  ],
  "observed_change": [],
  "uncertainty": [],
  "source": {
    "chunk": "C01",
    "window": "S01",
    "raw_path": "...",
    "raw_sha256": "..."
  }
}
```

IDs are assigned in absolute-time, chunk, window order. Each normalized detail
has exactly one verbatim source substring and one raw file. A detail without
known raw, source window, enclosing interval, or SHA256 is rejected. Timeline
entries may refer to one or more observation IDs; they never copy detail without
that reference.

## 7. Pre-registered Branch A sufficiency gate

Branch A executes only if all conditions hold after the complete 116-file audit:

```text
usable-detail windows                         >= 5
distinct broad activities linked to details  >= 3
non-dominant activity with detail             >= 1
lineage-complete detail-bearing candidates    >= 5
every eligible fact passes all safety rules   true
```

The frozen rationale is:

```text
usable-detail windows >= 5
  proves the detail layer has enough repeated support to be reusable

distinct broad activities linked to details >= 3
  prevents recovered detail from being confined to one dominant activity

non-dominant activity with detail >= 1
  establishes at least the possibility of improving V3's dominant-activity bias

lineage-complete detail-bearing candidates >= 5
  establishes that the minimum five representative highlights can be built
```

`dominant` means the two activities with greatest total coverage seconds in the
frozen 96-entry timeline, ties resolved by Korean Unicode lexical order.

If any condition fails, the fixed outcome is:

```text
decision: GROUNDING_DETAIL_SOURCE_INSUFFICIENT
new_visual_inference_required: UNKNOWN
downstream_grounded_store_executed: false
highlight_selection_executed: false
status: CLOSED / GROUNDING_DETAIL_SOURCE_INSUFFICIENT
```

The incident then stops. It may recommend a separately approved observation
event but may not declare that new inference is necessary or execute it.

## 8. Temporal normalization and candidate construction

Branch A maps each window observation to the frozen normalized timeline through
chunk/window lineage. Details are attached only to the intersection of their
source window and owned timeline entry; no interval is expanded. Adjacent
timeline entries merge into an activity block only when their complete ordered
activity tuple is identical. The block retains all observation IDs and sources.

Every candidate records:

```text
candidate id
start/end/duration
activity set
temporal zone (early/middle/late thirds)
visual fact count
unique normalized visual fact count
activity coverage seconds and rarity rank
repeat count of the activity signature
timeline entry ids
grounded observation ids
source lineage
```

Candidates without a high-confidence fact are excluded except for the exact
canonical final phase, which may be retained as a broad-only ending candidate.

## 9. Diversity-aware selection

The target is `min(7, eligible candidate count)` and must remain within 5–8.
Selection is deterministic in this order:

1. Select the exact canonical final-phase candidate.
2. For each early/middle/late third, select the highest-ranked unselected
   detail-bearing candidate in that zone.
3. If available, select candidates until at least two selected highlights have
   an activity outside the two dominant activities.
4. Fill remaining slots by global rank.

Rank is lexicographic:

```text
has high-confidence detail                   descending
unique visual fact count                     descending
rarest linked activity's coverage seconds    ascending
duration                                     descending
start time                                   ascending
candidate id                                 ascending
```

Constraints checked after every tentative selection:

```text
same complete activity signature <= 2 highlights
repeated signature requires a different normalized fact set
highlight time intervals do not overlap
lineage completeness == 100%
```

If a mandatory early/middle/late/final condition or the 5-highlight minimum
cannot be met without violating a constraint, Branch A fails closed with
`DIVERSITY_SELECTION_CONTRACT_UNSATISFIED`; rules are not relaxed.

## 10. Highlight text contract

The default user-facing text is local to the selected candidate:

```text
<time>에는 <single activity>가 나타난다.
<one or two high-confidence grounded facts>.
```

For multiple activities:

```text
<time>에는 A · B 활동이 함께 나타난다.
<one or two high-confidence grounded facts>.
```

No Korean particle is concatenated to an arbitrary label. The separator form
prevents `둘러보기과`-type errors.

`전환된다` is allowed only when candidate A ends exactly where candidate B
starts and their complete activity sets differ. It is not used for nonadjacent
representative highlights, identical labels, or gaps. The default renderer does
not need transition wording.

## 11. Artifacts

Always produced in an isolated new directory:

```text
runs/wvr_grounded_report_v1/
  raw_detail_audit.json
  execution_record.json
  result.json
```

Produced only for Branch A:

```text
  grounded_observations.json
  grounded_detail_store.json
  grounded_detail_lineage.json
  activity_blocks.json
  highlight_candidates.json
  highlights.json
  highlight_lineage.json
  comparison_v3.json
```

Branch B writes no apparently successful empty detail/highlight artifact. Raw
files are never copied, rewritten, or deleted.

## 12. Old-vs-new measurements

The V3 baseline is frozen as 7 highlights. Its highlighted activities are
dominated by `음식 준비 및 조리` and `구매 또는 둘러보기`; `이동`, `외출 준비`,
`포장 작업`, and `의류 작업 및 수선` are absent.

If Branch A runs, comparison records:

```text
highlight count
distinct activity count
dominant activity share
rare/non-dominant represented count
highlights with grounded detail
average grounded facts per highlight
lineage completeness
unknown/unverified detail count
context inference count
internal identifier exposure
same-label fake-transition count
nonadjacent-transition wording count
Korean grammar-template violations
```

Metrics are descriptive. No PASS threshold or baseline-replacement decision is
derived from them.

## 13. Required tests

Tests must fail closed for:

```text
detail without source lineage
unknown source window
detail outside source interval
unsupported context phrase
activity outside the allowed/source set
duplicate highlight id
non-monotonic timestamp
same-label fake transition
non-adjacent transition wording
compound-label particle concatenation
dominant/signature cap violation
source hash drift
```

Tests also verify complete raw-universe audit, Branch B early stop, exact Branch
A sufficiency thresholds, deterministic selection, V3 comparison metrics, and
zero inference counters.

## 14. Ordering and stop conditions

```text
1. commit this preregistration
2. write failing tests and implement the frozen audit/branch logic
3. snapshot protected sources and audit all 116 raw files exactly once
4. compute the Branch A / GROUNDING_DETAIL_SOURCE_INSUFFICIENT decision
5. only for Branch A, build grounded stores and diversity-aware highlights once
6. verify artifacts and protected hashes, report the applicable status, and STOP
```

No result-driven rule change, parser relaxation, manual fact promotion, retry,
new prompt campaign, report/HWPX regeneration, or baseline modification is
authorized.

Final status is limited to one of:

```text
WVR_GROUNDED_REPORT_EVIDENCE_V1
EXECUTED / REVIEW_PENDING

WVR_GROUNDED_REPORT_EVIDENCE_V1
CLOSED / GROUNDING_DETAIL_SOURCE_INSUFFICIENT
```

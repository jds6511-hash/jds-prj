# V3 usability highlight selection rule — fixed before candidate computation

This variant does not change the reviewer-PASS V2 baseline or run any inference.

1. Read the frozen whole-video activity timeline in absolute video time. Require
   ordered, gap-free, non-overlapping entries from 0 to the observed end. Reject
   any activity absent from the frozen canonical activity vocabulary.
2. Merge adjacent entries only when their **entire ordered activity tuple** is
   identical. A block is exactly the union of its source entries; do not extend
   it into a neighbouring block. Retain every entry's timeline index, chunk,
   window, and frozen artifact hashes as lineage.
3. Divide the observed [0, end) interval into six equal clock strata. For each
   stratum choose the block with greatest *overlap duration* with that stratum;
   break ties by longer whole-block duration, then earlier block start. Select
   each block at most once; if already selected in an earlier stratum, choose
   the next-ranked unselected block.
4. Ensure the exact canonical final-phase block is selected. If not, append it.
   This makes seven highlights on the expected source; abort if the result is
   outside 5–8 rather than changing the rule after inspecting it.
5. Sort selected blocks by absolute start. Display their exact start/end in
   `MM:SS` (or `HH:MM:SS` beyond 1 hour). Each description states only the
   frozen broad activity and whether that activity persists or transitions to
   the next selected phase. Do not infer a place, object, plan, intent, recipe,
   or unobserved local action. A missing frozen visual summary never licenses a
   guessed detail.
6. One-line summary uses only the canonical activity vocabulary and V2
   Overview's activity order. V2 SHORT/DETAILED Overview, Analysis and
   Conclusion are copied verbatim into the new variant. Technical metadata
   is moved to a separate appendix. Existing HWPX renderer is reused.

No manual reselection, model calls, prompt retry, beta episode prose, official
test, M9, or changes to frozen source files are allowed.

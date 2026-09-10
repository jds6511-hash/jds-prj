# WVR Boundary Candidate inherited test integrity audit (2026-09-10)

사건: `WVR_SEMANTIC_BOUNDARY_CANDIDATE_SHADOW_V1`

## Provenance

```
original prereg commit   4ace1f224f141c51338ccca7eafa39745e9d9ec4
errata 1 commit          8c7df4c9538fb1de2c25f540f3627329f6b804dc
errata 2 commit          a1e958a1ddf6612d30b382b95b8049fbaf4392a9
original test SHA256     6aa39751fb74baa9e2526af466800855e2f167b15c0e522bd872097d9c294b2f
errata 2 test SHA256     929944c0fd42f866e2bc02b7ac8a23def5d9b2147d8a462562d6b2418329f5db
errata 3 commit          38a91fc1e9ed5fa478693c847c9b0dba5952145e
corrected test SHA256    355432494ddd129a51cf582ce580722c296dbae8b169cd97b2319ec0cdded6b4
inference                0회
raw/result artifact      0건
```

## Correction reason and authority

Prereg §6의 frozen observation 원문 보존과 기존 §10/WVR-B14의 rendered prompt 전체
activity-term 금지는 frozen input에서 동시에 만족할 수 없었다. 리뷰어가
`PREREG_TEST_CONTRACT_MISMATCH / CONFIRMED` 및
`MINIMAL PRE-INFERENCE ERRATA / APPROVED`로 판정했고, prereg errata 2 §30.1~§30.4가
fixed guidance neutrality와 source observation fidelity의 범위를 분리했다.

## Exact WVR-B14 diff

```diff
 def test_wvr_b14_the_prompt_is_frozen_and_neutral():
     assert bc.sha256_text(bc.PROPOSER_PROMPT_V1) == bc.PROMPT_TEMPLATE_SHA256
-    lowered = bc.PROPOSER_PROMPT_V1.lower()
-    for phrase in bc.FORBIDDEN_PROMPT_STRINGS:
-        assert phrase not in lowered, phrase
+    guidance_banned = ("food preparation", "eating", "sewing",
+                       "gift wrapping", "clothing", "400 sec",
+                       "v1 chapter sequence")
+    assert tuple(bc.FORBIDDEN_PROMPT_STRINGS) == guidance_banned
+    guidance = bc.PROPOSER_PROMPT_V1.lower()
+    for phrase in guidance_banned:
+        assert phrase not in guidance, phrase
     batch = bc.batches(CANDIDATES)[0]
     prompt = bc.render_prompt([BY_ID[value]
                                for value in batch["candidate_ids"]])
     for value in batch["candidate_ids"]:
         assert value in prompt
-    for phrase in bc.FORBIDDEN_PROMPT_STRINGS:
-        assert phrase not in prompt.lower(), phrase
     for label in bc.PROPOSALS:
         assert label in prompt
+    # Errata 2 §30: activity terms in frozen source observations are allowed,
+    # but every actor/action/object_or_state line must remain verbatim.
+    expected_lines = []
+    for value in batch["candidate_ids"]:
+        boundary = BY_ID[value]["boundary_sec"]
+        for low, high in ((max(bc.VIDEO_START_SEC,
+                               boundary - bc.CONTEXT_WINDOW_SEC), boundary),
+                          (boundary, min(bc.VIDEO_END_SEC,
+                                         boundary + bc.CONTEXT_WINDOW_SEC))):
+            for event in EVENTS:
+                overlap = max(0.0, min(high, event["end_sec"])
+                              - max(low, event["start_sec"]))
+                if overlap > 0:
+                    expected_lines.append("%s | %s | %s" % (
+                        event["actor"], event["action"],
+                        event["object_or_state"]))
+    for line in set(expected_lines):
+        assert prompt.count(line) >= expected_lines.count(line), line
+    assert any(phrase in prompt.lower() for phrase in
+               ("food", "eat", "sew", "gift", "wrap", "cook", "cloth"))
+    assert bc.leakage_audit([prompt], EVENTS, CANDIDATES)["violations"] == []
```

## Re-audit A–G

```
A new semantic acceptance threshold added                 NO
B preregistered prohibitions substantively omitted        NO
C result-dependent threshold present                      NO
D blind mapping seal weakened                             NO
E timestamp/window/region/grid/prior-chapter leakage      NO
F chapter/title/summary generation enabled                NO
G conflict winner selection enabled                       NO
```

WVR-B14 now separately enforces neutral fixed guidance, verbatim source payload preservation,
natural activity-term presence in source payload, and global geometry/prior-chapter leakage
absence. Candidate universe, context, batching, vocabulary, mapping seal, reduction, reviewer
authority, density diagnostic, raw-before-parse, and downstream prohibitions are unchanged.

```
PREREG_TEST_CONTRACT_CONSISTENT
```

## Second correction: structural leakage (errata 3 §31)

Frozen source payload의 자연어 `train window`와 `blender`/`blending`을 geometry/time
metadata substring으로 오인하는 모순을 리뷰어가 승인했다. 아래 diff만 추가됐다.

```diff
 def test_wvr_b11_a_rendered_block_carries_no_geometry_or_event_id():
     text = "\n".join(bc.render_block(row) for row in CANDIDATES)
     for event in EVENTS:
         assert event["event_id"] not in text
         assert event["source_window"] not in text
-    for word in ("REGION", "region", "window", "grid", "CH0", "R0",
-                 "stitch", "STITCH"):
-        assert word not in text
+    assert not re.search(r"\bW\d{2}\b|\bR\d{2}\b|\bCH\d{2}\b", text)
+    for metadata in ("source_window", "source_window_id", "window_id",
+                     "region_id", "region_class", "region_boundary",
+                     "chapter_id", "prior_chapter", "grid_24s", "grid_48s",
+                     "earlier_window", "later_window", "24-second grid",
+                     "48-second grid"):
+        assert metadata not in text
+    assert "train window showing cityscape" in text
+    assert "walking through train window" in text
     for row in EVENTS[:40]:
         assert row["action"] in text

 def test_wvr_b12_the_leakage_audit_catches_injected_geometry():
     clean = bc.leakage_audit([bc.render_block(row) for row in CANDIDATES],
                              EVENTS, CANDIDATES)
     assert clean["violations"] == []
     assert clean["candidate_id_order_differs_from_time_order"] is True
     for poison in ("the boundary is at 400.0 sec", "source window W07",
-                   "region R05", EVENTS[0]["event_id"]):
+                   "window_id: W07", "region R05", "region_id: R05",
+                   "prior chapter CH03", EVENTS[0]["event_id"]):
         dirty = bc.leakage_audit([poison], EVENTS, CANDIDATES)
         assert dirty["violations"], poison
+    natural = bc.leakage_audit(["train window showing cityscape",
+                                "blending ingredients in a blender"],
+                               EVENTS, CANDIDATES)
+    assert natural["violations"] == []

 def test_wvr_b15_the_prompt_never_asks_for_chapters_or_times():
     prompt = bc.render_prompt([BY_ID["C001"]])
-    for field in bc.TIME_FIELDS:
+    structured_time_fields = ("start_sec", "end_sec", "boundary_sec",
+                              "timestamp", "time_sec")
+    assert tuple(bc.TIME_FIELDS) == structured_time_fields
+    for field in structured_time_fields:
         assert field not in prompt
     for word in ("title", "summary", "dominant_activities", "overview"):
         assert word not in prompt.lower()
+    assert "blender" in prompt.lower()
+    for poison in ('{"start_sec": 48}', '{"end_sec": 72}',
+                   '{"boundary_sec": 48}', '{"timestamp": 48.0}',
+                   '{"time": 48}', "move the boundary start time"):
+        assert bc.leakage_audit([poison], EVENTS, CANDIDATES)["violations"], poison
     assert bc.CHAPTER_GENERATION_ALLOWED is False
```

Local pytest가 기본 `%TEMP%/pytest-of-UserK` 접근 권한 때문에 `tmp_path` setup에서
실패하므로 contract expectation을 바꾸지 않고 workspace 밖의 전용 임시 경로를 쓴다.

```
--basetemp C:\Users\UserK\AppData\Local\Temp\prj-codex-basetemp
```

Second re-audit에서도 A–G 결과는 모두 `NO`다. Structural identifier/metadata poison은
RED로 남고 frozen natural-language payload는 원문 그대로 허용된다.

```
PREREG_TEST_CONTRACT_CONSISTENT
```

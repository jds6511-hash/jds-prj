# WVR Semantic Boundary Candidate Shadow V1 — Result Closure (2026-09-11)

## Reviewer decision and final status

```text
OPTION A SELECTED

PACKET_OR_GENERATION_FAILURE
CONFIRMED
```

```text
WVR_SEMANTIC_BOUNDARY_CANDIDATE_SHADOW_V1
CLOSED / BOUNDARY_CANDIDATE_SHADOW_INCONCLUSIVE
```

이 문서는 technical failure와 frozen artifact provenance만 기록한다. proposal label 분포,
candidate rationale, semantic quality, candidate-to-timestamp mapping은 분석하거나 보고하지
않는다.

## A. Provenance

```text
original prereg commit       4ace1f224f141c51338ccca7eafa39745e9d9ec4
errata 1 commit              8c7df4c9538fb1de2c25f540f3627329f6b804dc
errata 2 commit              a1e958a1ddf6612d30b382b95b8049fbaf4392a9
errata 3 commit              38a91fc1e9ed5fa478693c847c9b0dba5952145e
implementation commit        5ee61147c68e2d383c5763d06a578bae408e4cec
previous executor agent      Claude in VS Code
current executor agent       Codex in VS Code
```

Execution record:

```text
runs/wvr_light_v1/bcand_v1_record.json
SHA256 077a970d80d4c2b2c26badc17e9e17e500106fab4628ba776fdc570e3bf5232f
```

## B. Frozen inputs

```text
Conservative Event Map SHA256
0ebecf34e84550805392bfcc8b4681f5028679250736a03f230dafb32d692e8c

submission SHA256
5732075871fd7902d52239cebced28f9489a0f558dac67c61f5d2ca994e9cd7b
```

두 hash 모두 execution 전과 closure 시점에 일치했다. submission은 변경하지 않았다.

## C. Pre-inference gate

```text
status                              PASS
candidate count                    144
batch count                        18
inference count                    0
source map hash                    PASS
submission hash                    PASS
prompt template hash               PASS
deterministic candidate rebuild    PASS
deterministic batch rebuild        PASS
rendered prompt rebuild            PASS
candidate IDs unique               PASS
mapping sealed                     PASS
blind leakage                      0
alternative observations preserved PASS
downstream artifacts               0
prohibition flags closed           PASS
```

Clean/pushed implementation verification before inference:

```text
5006 passed, 3 skipped, 0 failed
```

## D. FIRST inference execution

```text
model                       Qwen/Qwen2.5-7B-Instruct
revision                    a09a35458c702b33eeacc393d103063234e8bc28
effective dtype             torch.bfloat16
attention implementation    sdpa
quantized                   false
load_4bit                   false
do_sample                   false
max_new_tokens              2048
GPU                         NVIDIA GeForce RTX 4090
batch construction          18 batches × 8 candidates
generated batches           18 / 18
preexisting raw batches     0
retry                       0
elapsed_sec                 365.598
max VRAM allocated bytes    15673411584
max VRAM reserved bytes     16013852672
new VLM inference           0
Track A input               false
```

The runner persisted every raw batch and its SHA256 before parsing. `parsed_here` in the
execution record remains `false`.

## E. Frozen schema failure

Parsing stopped on the first frozen-schema violation:

```text
batch                 B03
candidate             C021
field                 before_activity
actual type           string
actual value state    empty
required state        non-empty string
error                  SCHEMA_VIOLATION: empty or non-string field
```

Failure characterization, without timestamp reveal:

```text
C021 frozen source BEFORE
empty                         true
event_count                   0
observation_set_count         0

C021 frozen source AFTER
empty                         false
event_count                   12
```

The empty generated field is consistent with a structurally empty frozen source side. That
fact does not relax the V1 schema and does not authorize reparse or retry.

Non-semantic technical diagnosis recorded only the following aggregate facts:

```text
raw files                         18
raw hash mismatch                 0
JSON extraction failure           0
raw leakage violation             0
top-level field-set violation     0
candidate-set mismatch            0
candidate field-set violation     0
proposal vocabulary violation     0
empty/non-string field violation  1
```

No proposal distribution or rationale was inspected for semantic judgment.

The mapping-bearing `bcand_v1_blind_map.json` and `bcand_v1_candidates.json` remain preserved
in the local and isolated server worktrees, but are explicitly excluded from the result commit
and remote push. This prevents the commit itself from becoming a premature mapping reveal.

## F. Raw artifact manifest

Raw bytes were not edited or reserialized.

```text
bcand_v1_raw_B01.txt c2a1a6e5410986b27ccbf34bfe17eb00dba67be55c2e086f9f9cfe2c1295798e
bcand_v1_raw_B02.txt fa86eefe375cbffd28b15ff2ce96bb0563b2d36d983006f307b18024e0d7695c
bcand_v1_raw_B03.txt 03de36ff42cf700ff2802a6edcdaf44778809f01b78734a507849c43cb7deb75
bcand_v1_raw_B04.txt 50e4d55e063aebdd3e952c0269bf522bbf52ccc5344aa9b88bd6e5fdb741c7bf
bcand_v1_raw_B05.txt 683f3cae3b3d011b5baa97c08588162d8d5d64ecd3e905d8bde69a601db2e489
bcand_v1_raw_B06.txt 29ec1ce5983380a545651a862e9ee555785391ba82afcd2d0749bfb98b4db56d
bcand_v1_raw_B07.txt 9f5e9365d5573943af08ba33177496212bb75048d50bacc98057c09bc09a45ab
bcand_v1_raw_B08.txt 27257ab614c9306155858635668f9838325df35810cc20d03e2c5cfa7ab07414
bcand_v1_raw_B09.txt c30987983e255a7c5a8968c533388dbac4fe2025130460d74718cc80e624be73
bcand_v1_raw_B10.txt 5a8f9ea53e2a071fd07bbd390715f831b1c21f33d3a3c82f535896fe44a58767
bcand_v1_raw_B11.txt eccd6453f9be29c468269795a111126c00c367618b93d8adddb076b06895b870
bcand_v1_raw_B12.txt f9b3442b098ffc521ea2b79e9b7a71d386c7c21e3043c0d6282efddf9b467671
bcand_v1_raw_B13.txt 82e37e04087c345e30ab74b0a42f07665c474b86160c37a5ffe2aae9ee8e5698
bcand_v1_raw_B14.txt 8fdcc287d9b9fb20b227e2e838c581705ed0afe3ea0130bd15d6a4ee380d2913
bcand_v1_raw_B15.txt 2cc1147ebfaa382a473305fc15387e489bc9c2efe12d3309ed7b6a3c21829f47
bcand_v1_raw_B16.txt fae2c3c3baedf67f803cfd7a311fb29b3bc1e3a3b90a6a443f0f20acba0907cb
bcand_v1_raw_B17.txt 826e51f915fdc62b983db719cc12211aed0e742051ef39606a3f6238a89dab34
bcand_v1_raw_B18.txt 4e542e030ec55aae0b2f9a3af1b2cf32c738356e7614b0e0dec8de9fdcc161f1
```

The same hashes are frozen in `bcand_v1_record.json`.

## G. Prohibited post-result actions

The following were not performed:

```text
schema relaxation
parser relaxation
raw modification or reserialization
reparse under a changed contract
inference retry
prompt/model/runtime/threshold change
semantic result recovery
candidate-to-timestamp mapping reveal
chapter/title/summary/Overview/Analysis/Conclusion/HWPX generation
official-test opening
```

## H. Technical and semantic disposition

```text
FIRST inference                         COMPLETE
raw preservation                       COMPLETE (18 / 18)
technical completion gate              FAIL / SCHEMA_VIOLATION
parsed proposal artifact               NOT GENERATED
reviewer packet                        NOT GENERATED
weak appendix                          NOT GENERATED
technical validator                    NOT RUN (parser blocker)
semantic adjudication                  NOT PERFORMED
mapping                                SEALED
semantic quality                       INCONCLUSIVE
```

No claim is made that the semantic proposer, candidate sufficiency, boundary method, or Qwen
semantic quality failed. The only result is failure to satisfy the frozen V1 output schema.

## I. Final incident status

```text
WVR_SEMANTIC_BOUNDARY_CANDIDATE_SHADOW_V1
CLOSED / BOUNDARY_CANDIDATE_SHADOW_INCONCLUSIVE
```

STOP. A later source-empty-side contract, if authorized, must be a separately preregistered
incident and must not reuse these V1 raw outputs as its semantic result.

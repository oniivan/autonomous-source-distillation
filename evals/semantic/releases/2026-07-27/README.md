# Semantic Release Receipt

## Result

Five isolated fresh-agent cases passed: boundary overlap, source-composition order in
both directions, incremental correction, and cold reconstruction. Every generated
serious bundle passed schema-v3 structure and readiness, and the source-order variants
produced equivalent decision fields.

## Bound Evidence

- operational runtime SHA-256:
  `f96947351524f2389f9213d9a1cdac7dc605fabd6175ddc05a3ed9cbe0526bed`
- scorer file SHA-256:
  `9c0fdf9d6bd59763fd29bfc089e0b9ca4a5641f7217df618faad069ec183ea47`
- evaluator execution-surface SHA-256:
  `0d57eaa9247af16e4b624ef0071ae8ff9d1fd394430076142cd38e87c4a0b0a2`
- oracle SHA-256:
  `fc93592f0b3e834bb6a6fee146a44054c017fa4196aad3b809a5b45a2dac5186`
- evaluator, oracle, runtime, and staged case-input bindings: pass
- oracle copied into the agent-visible runtime: no
- authoritative receipt: `semantic-evaluation-receipt.json`
- generation identities: `agent-runs.json`
- scoring-envelope migration: `generation-provenance.json`
- generation metadata: `generation-run-metadata.json`
- generation output hashes: `generation-output-manifest.json`

## Provenance Note

The agents generated their outputs in an isolated run using the exact runtime and case
input hashes recorded here. Evaluator/oracle prebinding was added before adjudication,
so those unchanged outputs were copied byte-for-byte into a newly prepared scoring run
with identical runtime and input trees. This release does not claim the agents ran a
second time in the scoring directory.

## Proof Boundary

This is behavioral evidence for the named C/D/G/I fixtures and one model family. The
runtime was artifact-isolated by allowlist, not attested by the host filesystem. It is
not a universal factuality guarantee.

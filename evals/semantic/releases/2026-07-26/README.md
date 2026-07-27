# Semantic Release Receipt

## Result

The clean sealed run passed cases C, D in both source orders, G, and I. Every generated
serious bundle passed schema-v3 structure and readiness. The D semantic fields were
identical after source-order reversal.

## Bound Runtime

- installed skill:
  `$CODEX_HOME/skills/autonomous-source-distillation`
- installed tree SHA-256:
  `09f92a062aa0ee117b274d0280707ee4200a5e7355e1a5ea7ebfed663f41fe07`
- oracle copied into staged run: no
- authoritative receipt: `semantic-evaluation-receipt.json`
- raw staged cases and outputs: `cases/`
- dispatch identities: `agent-runs.json`

## Contaminated First Run

`contaminated-run-a-receipt.json` preserves the failed first attempt. Although the agents
received a source-checkout skill attachment, they resolved the stale installed runtime,
whose auditor did not support `--require-ready`. That run is excluded from semantic
release evidence. The installed runtime was synchronized and hashed before the clean run.

## Proof Boundary

This is evidence for the named C/D/G/I fixtures and runtime only. It is not a universal
factuality guarantee and does not claim cases A, B, E, F, or H were executed.

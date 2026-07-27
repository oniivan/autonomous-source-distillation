# Distillation Handoff

- Objective and fidelity profile: determine whether the supplied evidence supports a
  global October rollout; serious route, low acceptable loss, source-only verification.
- Source revisions consumed: S1-R1, S2-R1, S3-R1, and S4-R1.
- Representation limits: each source is a one-line statement; underlying pilot,
  feasibility, and audit materials were not supplied.
- Region, facet, and risk coverage: all four planned chunks were distilled; every
  required facet and risk check is covered or passed in `coverage.json`.
- Durable artifacts: `sources.jsonl`, `chunks.jsonl`, `chunk-notes.jsonl`,
  `evidence.jsonl`, `claims.jsonl`, `coverage.json`, `synthesis.md`, and
  `semantic-result.json`.
- Key claim IDs: C1-C7 preserve source-level facts; C8 is the global-rollout conclusion.
- Contradiction and minority evidence: S4 is the only direct global-decision source and
  blocks rollout pending the EU audit; S1 and S3 support only regional readiness.
- Source composition: S2 is derived from S1 and shares family F1, so it is excluded from
  independent corroboration. Independent families are represented by S1/F1, S3/F3,
  and S4/F4.
- External verification: none; all claims remain source-only.
- Source-only or uncertain points: EU audit status, pilot methods, feasibility methods,
  and all reported judgments.
- Delta or supersession state: none; one revision per source and all claims are active.
- Context safe to drop: copied raw inputs and `chunks.jsonl` after ledger validation.
- Exact next context to load: `semantic-result.json`, then C8 in `claims.jsonl`, then
  E3, E6, E9, and E10 in `evidence.jsonl`; load source lines only if exact wording is
  needed.
- Stale-after trigger: any new source revision, EU audit update, Europe readiness
  evidence, or change to the declared S2-to-S1 derivation.

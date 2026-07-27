# Distillation Handoff

- Objective and fidelity: Recover five specified briefing facts with exact transcript
  line locators and low acceptable loss.
- Source revision consumed: `S1-R1`, bound to `inputs/source.txt` by SHA-256.
- Representation limits: No audio was supplied to check transcript accuracy or speaker
  attribution.
- Coverage: Seven contiguous chunks account for lines 1-900; none were skipped. All five
  required facets and the boundary, representation, and sparse-middle risks were checked.
- Key claims: `C1`, `C2`, `C3`, `C4`, and `C5`.
- Minority evidence: `C4` preserves the reliability lead's conditional opposition.
- Contradictions: None stated in the source.
- Verification: All material claims remain `source-only`; no external verification was
  performed.
- Context safe to drop: `inputs/source.txt` and `chunks.jsonl` after the bundle has been
  loaded.
- Exact reload set: `run-manifest.json`, `sources.jsonl`, `chunk-notes.jsonl`,
  `evidence.jsonl`, `claims.jsonl`, `coverage.json`, `synthesis.md`, and `handoff.md`.
- Stale-after trigger: A changed source digest or transcript revision requires a new
  source revision and delta review.

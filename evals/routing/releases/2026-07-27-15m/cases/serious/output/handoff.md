# Distillation Handoff

- Objective and fidelity profile: Recover five briefing fields with exact locators;
  acceptable loss is low and unsupported material claims are excluded.
- Source revision consumed: `S1-R1`, registered in `sources.jsonl`.
- Representation limit: Only transcript text was supplied; no audio was available for
  transcript or speaker-attribution verification.
- Region coverage: All 225 lines were distilled across six contiguous chunks; none
  were skipped.
- Facet coverage: Budget cap, launch date, release blocker, requested dissent, and
  scope limitation are covered by `E1` through `E5`.
- Risk coverage: Boundary, representation, and sparse-middle checks passed.
- Durable artifacts: `sources.jsonl`, `chunk-notes.jsonl`, `evidence.jsonl`,
  `claims.jsonl`, `coverage.json`, `synthesis.md`, and `result.json`.
- Key claims: `C1`, `C2`, `C3`, `C4`, and `C5`.
- Dissent evidence: `E4` preserves the reliability lead's attributed conditional
  opposition; no broader consensus is inferred.
- External verification: None performed; all material claims remain source-only.
- Context safe to drop after loading the ledgers: `inputs/source.txt` and
  `chunks.jsonl`.
- Exact next context to load: `run-manifest.json`, `sources.jsonl`,
  `chunk-notes.jsonl`, `evidence.jsonl`, `claims.jsonl`, `coverage.json`,
  `synthesis.md`, and this handoff.
- Stale-after trigger: Any change to the copied source bytes or source revision ID
  requires re-distillation and re-audit.

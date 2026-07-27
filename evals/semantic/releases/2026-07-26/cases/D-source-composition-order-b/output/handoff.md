# Distillation Handoff

- Objective and fidelity profile: Decide whether the supplied evidence supports a
  global October rollout, with low acceptable loss for scope, blockers, contradictions,
  and derivation.
- Source revisions consumed: `S4-R1`, `S3-R1`, `S2-R1`, `S1-R1`, in registry order.
- Representation limits: Each source is a one-line supplied text. No underlying audit,
  pilot data, partner analysis, or external verification was available.
- Region, facet, and risk coverage: All four planned line chunks were distilled with no
  skips. Global readiness, regional scope, blocker, composition, and contradiction
  facets are covered. Representation, composition, and order checks pass.
- Key claim: `C8`, the supplied evidence does not support a global October rollout.
- Contradiction and minority evidence: `S2` says the October rollout is ready (`E7`),
  opposing `C8`; `S4` supplies the direct global blocker (`E1`).
- Source composition: `S2` is derived entirely from `S1` and shares family `F1`, so it
  is preserved as opposing text but excluded from independent corroboration.
- External verification: None. All factual premises are source-only, and `C8` is marked
  disputed because the contrary wording is retained.
- Unresolved gaps: The EU audit closure status is unknown, and the underlying regional
  analyses are unavailable.
- Context safe to drop: Copied raw inputs and `chunks.jsonl` after the ledgers are
  loaded; the files remain durable in the bundle.
- Exact next context to load: Start with `semantic-result.json` and `claims.jsonl`;
  reload `evidence.jsonl` and `sources.jsonl` for stance and lineage, then
  `coverage.json` for completion checks.
- Stale-after trigger: Rebuild the affected evidence, claims, synthesis, and semantic
  result if any source revision, EU audit status, regional scope, or lineage changes.

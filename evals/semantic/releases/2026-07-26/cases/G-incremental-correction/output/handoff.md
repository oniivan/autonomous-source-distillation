# Long Material Handoff

- Objective and fidelity profile: Identify the current and previous filing deadlines
  with low-loss preservation of the correction history.
- Source revisions consumed: `S1-R1` and `S1-R2`, both registered as logical source
  `S1` in stable family `S1-FAMILY`.
- Representation limits: None for the one-line plain-text fixtures; external authority
  and publication context were not supplied.
- Region, facet, and risk coverage: Both one-line revisions were fully distilled. The
  current deadline, previous deadline, and supersession facets are covered. Revision,
  representation, and boundary checks passed.
- Key claims: `C-DEADLINE-SEP30` is superseded; `C-DEADLINE-OCT15` is active.
- Delta receipt: `S1-R2` changes the filing date from September 30, 2026 to October 15,
  2026 and explicitly replaces the old date. `C-DEADLINE-OCT15` supersedes
  `C-DEADLINE-SEP30`, and the old claim reciprocally names the new claim as its
  replacement.
- Contradictions and minority evidence: No unresolved contradiction remains after
  applying the explicit correction. Both statements remain preserved as revision
  history and do not count as independent corroboration.
- External verification: None.
- Source-only or uncertain points: Both deadline claims are source-only; "current"
  means current within the supplied revisions.
- Unresolved gaps: None for the requested probe.
- Context safe to drop: Raw fixture text after the registered evidence and claims are
  loaded.
- Exact next context to load: `sources.jsonl`, `evidence.jsonl`, `claims.jsonl`, and
  `synthesis.md`.
- Stale-after trigger: Receipt of a later revision of logical source `S1`.

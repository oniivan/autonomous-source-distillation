# Run Manifest

- Route: serious
- Objective: determine the current filing deadline and preserve the correction history.
- Sources: logical source `S1`, revisions `S1-R1` and `S1-R2`, stable family `F1`.
- Required facets: deadline; correction history.
- Required risks: revision drift; representation.
- Acceptable loss: low.
- Completion oracle: both dates resolve to exact revision-specific evidence, and claim supersession is reciprocal.
- Key claims: `C1` (superseded) and `C2` (active).
- Verification: source-only; no external verification was performed.

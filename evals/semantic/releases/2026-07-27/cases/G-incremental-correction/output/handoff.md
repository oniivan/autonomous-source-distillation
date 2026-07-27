# Long Material Handoff

- Objective and fidelity profile: identify the current filing deadline and retain the prior corrected deadline; serious route, low acceptable loss.
- Source revisions consumed: `S1-R1` and `S1-R2`, both logical source `S1` and source family `F1`.
- Representation limits: plain-text policy statements only; no publication metadata or external authority was supplied.
- Region/facet/risk coverage: both one-line revisions were fully distilled; deadline, correction history, revision drift, and representation were checked.
- Durable artifacts: `sources.jsonl`, `chunks.jsonl`, `chunk-notes.jsonl`, `evidence.jsonl`, `claims.jsonl`, `coverage.json`, and `synthesis.md`.
- Key claim IDs: `C1` is the superseded September 30, 2026 claim; `C2` is the active October 15, 2026 claim.
- Contradictions and minority evidence: the later correction replaces the earlier date; no independent-source disagreement is represented.
- External verification: none.
- Source-only or uncertain points: both deadline statements remain source-only.
- Delta or supersession state: `C1.superseded_by_claim_ids = ["C2"]`; `C2.supersedes_claim_ids = ["C1"]`.
- Context safe to drop: copied raw inputs and chunk text after the ledgers are loaded.
- Exact next context to load: `claims.jsonl`, then `evidence.jsonl`; load `inputs/policy-r2.txt` line 1 to recheck the current deadline.
- Stale-after trigger: any later revision of logical source `S1` or another authoritative correction.

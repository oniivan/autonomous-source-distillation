# Distillation Handoff

- Objective and fidelity: recover the exact launch gate with low acceptable loss and no duplicate support from overlap.
- Source revision consumed: `S1-R1`, registered from `inputs/source.txt` with line locators and an immutable SHA-256 digest.
- Representation limits: the fixture has no speaker identities, timestamps, or original recording; the line-preserving text is sufficient for the wording probe.
- Coverage: unique lines 1-2 belong to `S1-R1-C001`; `S1-R1-C002` loads line 2 as overlap and uniquely covers lines 3-4. Both chunks were distilled with no skips.
- Key result: `C1`, supported once by canonical evidence `E1` at lines 2-3.
- Overlap accounting: line 2 is context-loaded in the second chunk, but no second support record was created. `E2` at line 4 is context only.
- Contradictions and minority evidence: none present in the registered source.
- External verification: none; `C1` remains source-only.
- Context safe to drop: raw source and chunk ledgers after the listed reload artifacts are retained.
- Reload: open `claims.jsonl`, `evidence.jsonl`, `coverage.json`, and `semantic-result.json`; retrieve `inputs/source.txt` only if the exact source wording must be rechecked.
- Stale-after trigger: a byte change to `inputs/source.txt` requires a new source revision, new chunk hashes, and re-distillation.

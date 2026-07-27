# Distillation Handoff

- **Objective and fidelity:** Recover five specified briefing facts with exact line
  locators, low acceptable loss, and no unsupported material claims.
- **Source revision consumed:** `S1-R1`, copied to `inputs/source.txt`.
- **Representation limits:** Text transcript only; no audio comparison was available.
- **Coverage:** All six planned chunks and all unique lines 1-225 were distilled with no
  skipped regions. All five required facets and all declared risks passed.
- **Key claims:** `C1` budget cap, `C2` launch date, `C3` release blocker, `C4` minority
  dissent, and `C5` scope limitation.
- **Contradictions and minority evidence:** No contradiction is recorded. The
  reliability lead's conditional opposition is preserved separately as `C4` / `E4`.
- **External verification:** None; all claims remain source-only.
- **Context safe to drop:** Raw `inputs/source.txt` and `chunks.jsonl` after the ledgers
  are loaded.
- **Exact reload order:** Load `run-manifest.json`, `claims.jsonl`, `evidence.jsonl`,
  `coverage.json`, and `sources.jsonl`; consult `chunk-notes.jsonl` or the copied source
  only when a fuller span is needed.
- **Stale-after trigger:** Rebuild the affected chunks, evidence, claims, and synthesis
  if the source bytes or revision change.

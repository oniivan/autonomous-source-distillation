# Evidence Ledger

| Evidence ID | Source IDs | Evidence | Design implication |
|---|---|---|---|
| E1 | P1, P2, P3, P4 | Nominal context fit does not guarantee robust retrieval, aggregation, or summarization across positions and paraphrases. | Do not use “it fits” as a reason to skip staged extraction. |
| E2 | P5, P7 | Hierarchical summarization scales, but recursive summaries can amplify unsupported content unless merges return to source context. | Every merge must preserve source spans and run a claim audit. |
| E3 | P6, P15, P16 | The downstream question materially changes which information can be compressed safely. | Record an objective profile and build query-conditioned projections. |
| E4 | L2, P15 | A query-conditioned projection is lossy and may become stale when the objective changes. | Keep reusable source-faithful notes canonical and projections disposable. |
| E5 | P17, P18, P19, P20, P21 | Segmentation quality matters, but the best method depends on task, corpus, retrieval setting, and chunk size. | Use native structure first, mechanical fallback second, advanced methods only after eval. |
| E6 | P4, P8, P11 | Coverage is not the same as factuality; sparse roles or insights may be omitted despite a fluent, accurate-looking summary. | Track region and facet coverage separately from claim support. |
| E7 | P9, P10, P12 | One automatic factuality score is not dependable for long, information-dense summaries. | Decompose output into atomic claims and verify against selected spans. |
| E8 | P14, P23 | Proposition-level and variable-length evidence spans can be more faithful than fixed sentence/document citations. | Store the minimal sufficient native locator while retaining chunk ancestry. |
| E9 | P13 | Multi-source summaries can change with source order and ignore changes in source composition. | Preserve per-source stance, independent-source counts, and reorder tests. |
| E10 | P22 | Transcript errors propagate unevenly; WER does not capture task impact and entity repair can matter disproportionately. | Keep raw and normalized forms linked; flag entities, numbers, negation, and attribution as high-risk. |
| E11 | P25, P26 | Text-only extraction can lose table information; table summarization has schema-specific error modes. | Audit modalities and use row/column/cell or figure locators for structured claims. |
| E12 | P24 | Updating a previous summary can cause incomplete or incorrect entity associations. | Process deltas against versioned source state and explicitly supersede affected claims. |
| E13 | O1 | External material may contain adversarial instructions. | Treat all source content as untrusted data and forbid source-driven tool or policy changes. |
| E14 | O2, O3 | Isolated small chunks lose parent context; loading everything also degrades precision and context economy. | Store compact parent/section context and load bounded dependency-complete views. |


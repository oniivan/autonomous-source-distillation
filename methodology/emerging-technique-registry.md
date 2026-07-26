# Emerging Technique Registry

`AS_OF`: 2026-07-18

| Technique | Status | Evidence | Appropriate use | Recheck trigger |
|---|---|---|---|---|
| Native structure and discourse-aware boundaries | adopted | P17, P19 | Default segmentation when headings, timestamps, turns, records, or phases exist | A local eval shows fixed mechanical chunks are consistently better |
| Query-conditioned extraction/compression | adopted as derived view | P6, P15, P16 | Tailor synthesis to a declared objective after source-faithful extraction | Objective changes or omitted-fact eval fails |
| Source-backed hierarchical merging | adopted | P5, P7 | Very long sources or bundles requiring multiple synthesis levels | Claim attribution or hallucination audit regresses |
| Atomic claim and exact-span audit | adopted | P9-P12, P14, P23 | Serious, high-stakes, or reusable distillation | Long-form metric research invalidates the current audit |
| LLM-guided semantic chunking | conditional | P18, P19 | Narrative in-document retrieval after comparison with structural baseline | Corpus, task, model, or cost changes |
| Contextual/late chunk embeddings | conditional retrieval adapter | P20, O2 | Retrieval where cross-chunk references are a measured failure | Embedding model or retrieval workload changes |
| Perplexity-based dynamic chunking | pilot | P21 | Experimental logical-boundary detection | Peer-reviewed replication or local benchmark |
| One scalar LLM factuality judge | rejected as sole gate | P9, P10, P12 | May be one signal only | Robust long-document calibration evidence appears |
| Fixed universal chunk size or overlap | rejected | P15, P19 | None | A narrowly defined corpus-specific eval may set a local value |
| Text-only flattening of mixed-layout documents | rejected | P25, P26 | None when tables/figures carry meaning | Representation audit proves non-text content irrelevant |
| In-place overwrite of evolving summaries | rejected | P24, L2 | None for auditable work | A versioned owner system supplies equivalent supersession proof |


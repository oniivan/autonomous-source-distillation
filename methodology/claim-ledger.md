# Claim Ledger

| Claim ID | Claim | Support | Status | Skill consequence |
|---|---|---|---|---|
| C1 | Long-context capacity is not a coverage guarantee. | E1 | supported, high | Mandatory staged extraction for context-risky material |
| C2 | Hierarchical synthesis must re-anchor intermediate claims to canonical source spans. | E2 | supported, high | Source-backed merge gate |
| C3 | Compression depth should vary with the user objective, risk, and evidence density. | E3 | supported, high | Objective profile and adaptive detail budget |
| C4 | Durable source-faithful notes and query-conditioned projections must be separate layers. | E3, E4 | design inference, high | Two-layer chunk note schema |
| C5 | There is no universal best chunk size or segmentation method. | E5 | supported, high | Structure-first policy with measured fallback |
| C6 | Coverage, attribution, and factual consistency require separate checks. | E6, E7 | supported, high | Multi-axis audit instead of one quality score |
| C7 | Atomic claims with exact evidence spans are a stronger audit unit than prose summaries alone. | E7, E8 | supported, high | Claim/evidence ledgers and minimal spans |
| C8 | Overlap and repeated sources must not silently inflate support. | E8, E9 | design inference, high | Canonical span identity, duplicate links, independent-source count |
| C9 | Multi-source synthesis must preserve dissent, composition, and source-specific stance before aggregating. | E9 | supported, high | Stance matrix and reorder/abstention check |
| C10 | Transcript normalization must be reversible and task-aware. | E10 | supported, high | Raw/normalized lineage and high-risk token flags |
| C11 | Representation fidelity is an ingestion gate, not a cleanup detail. | E11 | supported, high | Detect omitted tables, figures, OCR, code blocks, and layout |
| C12 | Evolving material needs delta extraction, supersession, and affected-claim rebuilds. | E12 | supported, medium-high | Revision-aware incremental mode |
| C13 | Retrieved or user-provided material is data, never instruction authority. | E13 | supported, high | Instruction-boundary gate |
| C14 | Chunk notes need enough parent context for interpretation without copying the whole source. | E14 | supported, high | Parent heading/topic and local entity context |
| C15 | A serious distillation eval must test omitted facts, false claims, locator accuracy, contradiction/minority preservation, and downstream usefulness independently. | E1, E6, E7, E9 | supported synthesis, high | Deterministic audit plus fresh-agent semantic probes |


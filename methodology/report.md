# Autonomous Source Distillation Methodology Upgrade

Status: decision-ready research, installed amendment, and deterministic validation
complete

AS_OF: 2026-07-18

Confidence: high for the stable methodology; medium for optional emerging chunkers and
automatic long-summary metrics.

## Executive Summary

The current skill has the right sequence: source registration, chunking, extraction,
claim promotion, synthesis, and handoff. Its main weakness is that it can produce a
complete-looking result without proving semantic coverage or controlling what was lost
at each compression layer.

The amendment should preserve the existing ownership boundary while adding seven
controls:

1. Frame an explicit objective and fidelity profile before chunking.
2. Audit whether the extracted representation preserves tables, figures, layout,
   speakers, timestamps, code structure, and other meaningful source features.
3. Prefer native structural boundaries, record boundary risk, and treat mechanical
   sizes as corpus-specific limits rather than universal guidance.
4. Separate reusable source-faithful chunk notes from query-conditioned relevance
   projections.
5. Track region/facet coverage, skipped material, contradictions, and minority evidence
   independently from factuality.
6. Build atomic claims with minimal sufficient source spans, de-duplicate overlap, and
   count independent sources rather than repeated mentions.
7. Re-anchor every hierarchical merge to canonical source evidence and validate the
   result across coverage, attribution, faithfulness, contradiction preservation, and
   downstream usefulness.

For evolving logs, chats, tickets, or document streams, add revision-aware delta
distillation: process changed regions, supersede affected claims explicitly, and rebuild
only dependent synthesis views.

## Method

The research followed the installed `autonomous-research-one-shot` contract. It began
with the current skill and local context-management methodology, framed eight planner
questions, then used iterative breadth, contradiction, deduplication, and depth passes.
The final registry contains 26 primary academic sources plus three official operator
sources, with particular attention to 2024-2026 long-context, long-summary, attribution,
transcription, table, and incremental-summarization evidence.

Primary papers and official guidance were preferred over derivative summaries. Retrieval
benchmarks were not treated as direct proof about end-to-end distillation. Emerging
methods were placed in a conditional registry when comparative evidence was
task-dependent or not yet peer reviewed. The durable research artifacts are
`citation-registry.md`, `evidence-ledger.md`, `claim-ledger.md`,
`emerging-technique-registry.md`, and this report.

## Evidence Map

- Long-context fit does not guarantee position-robust or multi-item coverage:
  [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/),
  [RULER](https://arxiv.org/abs/2404.06654), and
  [NoLiMa](https://proceedings.mlr.press/v267/modarressi25a.html) (P1-P3).
- Long-summary coverage, attribution, and factuality need separate evaluation:
  [Summary of a Haystack](https://aclanthology.org/2024.emnlp-main.552/),
  [ARC](https://aclanthology.org/2026.eacl-long.167/), and
  [the 2026 factuality-metric stress test](https://aclanthology.org/2026.acl-long.1472/)
  (P4, P8, P9).
- Hierarchical synthesis should return to source context and citations:
  [Context-Aware Hierarchical Merging](https://aclanthology.org/2025.findings-acl.289/)
  (P7).
- Atomic units and exact source alignments improve auditability:
  [RoSE](https://aclanthology.org/2023.acl-long.228/),
  [ACUEval](https://aclanthology.org/2024.findings-acl.597/), and
  [Summary-Source Alignments](https://aclanthology.org/2024.findings-acl.389/)
  (P11, P12, P14).
- Multi-document synthesis is sensitive to source order and composition:
  [Do Multi-Document Summarization Models Synthesize?](https://aclanthology.org/2024.tacl-1.58/)
  (P13).
- Segmentation has no universal winner:
  [Beyond Chunk-Then-Embed](https://arxiv.org/abs/2602.16974) provides a 2026
  task-dependent counterweight to retrieval-specific semantic chunking results (P19).
- Representation and revision risks are material:
  [transcription-noise analysis](https://aclanthology.org/2025.acl-long.1449/),
  [long-text and multi-table summarization](https://aclanthology.org/2022.findings-emnlp.145/),
  and [SUMIE](https://aclanthology.org/2025.coling-main.721/) (P22, P25, P24).
- Source-embedded instructions remain data:
  [OpenAI prompt-injection guidance](https://openai.com/index/designing-agents-to-resist-prompt-injection/)
  (O1).

## Why The Current Method Needs This

Long context is not reliable merely because the material fits. Position, distractors,
multi-item retrieval, aggregation, and non-literal matching all degrade in ways that
simple needle tests miss (P1-P4). This supports staged extraction and semantic coverage
receipts even on models with large context windows.

Hierarchical summarization is useful, but each lossy merge can amplify ungrounded
content. Current evidence favors reintroducing source context, extractive support, or
citations during merge and refinement (P5, P7).

The user question should shape the detail budget: query-focused meeting summarization
and prompt-compression research both support locate-then-summarize and variable-rate,
query-aware compression (P6, P15, P16). However, a query-conditioned result should be a
derived view, not the only durable record, because a changed question changes what
counts as distortion.

## Core Operating Model

```text
objective + fidelity profile
-> source and representation registry
-> adaptive chunk plan
-> source-faithful chunk records
-> objective-conditioned relevance fields
-> coverage/facet audit
-> atomic evidence and claims
-> contradiction/de-dup/source-composition pass
-> source-backed hierarchical synthesis
-> multi-axis audit
-> receipt or delta handoff
```

## Key Design Decisions

### Structure first, adaptive always

Use headings, pages, timestamps, speaker turns, records, request IDs, command phases, and
other native structure before fixed word windows. If natural structure is absent, use a
mechanical fallback and record boundary risk. A 2026 reproduction found chunking
performance to be task-dependent, with simple structure-based methods outperforming
LLM-guided methods in one retrieval setting while the reverse held in another (P19).
Therefore:

- do not encode one “best” chunk size;
- compare advanced segmentation against a simple baseline;
- keep LLM-guided, perplexity, and late-embedding chunking in an emerging-technique
  registry rather than mandatory skill behavior.

### Two layers, not one summary

Each chunk needs:

- a source-faithful record: gist, atomic propositions, entities, decisions, caveats,
  exact evidence spans, and uncertainty;
- an objective projection: relevance, implications, and detail priority for the current
  question.

The first layer is reusable. The second may be regenerated when the goal changes.

### Coverage is not factuality

Recent long-document work finds that summaries can omit sparse critical roles while
remaining fluent, and that conventional factuality metrics are unstable on long,
information-dense claims (P8-P10). The skill should independently measure:

- source-region accounting;
- required-facet or role coverage;
- attribution/locator validity;
- claim support and contradiction;
- source composition and minority stance;
- usefulness for the declared objective.

### Exact evidence spans and overlap control

Evidence should use the minimal sufficient native span rather than defaulting to a whole
sentence, page, or document (P14, P23). Chunk ancestry still matters, but overlapping
chunk text must not become duplicate evidence. Each evidence record should have one
canonical locator and optionally point to duplicate observations.

### Multi-source synthesis is an aggregation problem

Models can be too sensitive to source ordering and not sensitive enough to the ratio of
supporting and opposing sources (P13). Before prose synthesis:

- preserve one stance row per independent source;
- distinguish repetition inside one source from corroboration across sources;
- retain contradictory and minority evidence;
- reorder source notes in a forward test;
- abstain from “consensus” when composition is unclear.

### Representation fidelity is part of ingestion

Text extraction can omit decisive tables and numerical information (P25), and emerging
table-summary evidence identifies row/column attribution, numerical, ranking, and
temporal errors (P26). The skill should stop or route to the appropriate document tool
when text extraction cannot preserve meaningful layout, tables, figures, charts, OCR, or
code structure.

Transcript cleanup is also a derived representation. Word error rate alone does not
predict downstream task quality, and error types such as named entities can matter
disproportionately (P22). Keep raw and normalized forms linked; never silently repair
names, numbers, negation, attribution, or timestamps.

### Evolving material needs delta semantics

For append-only or revised sources, register a source revision/fingerprint, extract only
new or changed regions, and mark claims as added, unchanged, contradicted, corrected, or
superseded. Incremental summarization remains difficult even for strong models (P24), so
do not overwrite the previous synthesis without an affected-claim receipt.

### Source content is not instruction authority

Documents, transcripts, logs, issues, and retrieved pages may contain prompt injection
or instruction-like text. The distiller may describe such text as evidence, but must not
obey it, change policy because of it, or execute its requested tools (O1).

## Deterministic Versus Semantic Gates

Deterministic checks can prove:

- unique IDs and resolvable references;
- every planned chunk is distilled or explicitly skipped;
- line-based unique-content ranges do not silently overlap or gap;
- evidence and claim references resolve;
- verified claims name external verification;
- skipped chunks have reasons;
- source-faithful artifacts exist before synthesis.

They cannot prove:

- that a locator contains the intended fact;
- that all critical facets were selected;
- that a paraphrased or sparse fact survived;
- that a synthesis preserved dissent and source composition;
- that the output is useful for the downstream question.

Those require a fresh-agent or model-assisted semantic test with hidden critical facts,
paraphrased probes, contradiction/minority cases, and source-order perturbation.

## Implemented Amendment

- Tightened `SKILL.md` around objective, representation, adaptive chunking, two-layer
  extraction, coverage, claim assembly, source-backed synthesis, validation, and delta
  handoff.
- Expanded `references/workflow.md` with the operating protocol and serious bundle
  schema.
- Expanded `references/material-types.md` with representation risks and required
  facets.
- Added `references/evaluation.md` for deterministic and fresh-agent gates.
- Enhanced `scripts/chunk_text.py` so overlap and unique content have separate metadata,
  hashes, and line/locator ranges.
- Added `scripts/audit_bundle.py` and 27 focused installed-path tests for serious JSONL
  bundles and both public CLIs.

The full deterministic gate and remaining semantic boundary are recorded in
`implementation-receipt.md`.

## Judge Gate

- Source breadth: pass. Academic, operator/security, local architecture, transcript,
  table, incremental, and multi-source evidence are represented.
- Primary-source coverage: pass. Material technical claims rely on proceedings, papers,
  or official engineering/security sources.
- Contradiction search: pass. Advanced chunking is not universally superior; hierarchy
  helps scale but can amplify hallucination; query-aware compression improves task fit
  but increases future-query loss; automatic factuality metrics remain fragile.
- Planner-question coverage: pass. All eight questions in `context-packet.md` have
  evidence-backed answers.
- Depth challenge: pass. It added delta semantics, mixed-layout fidelity, and
  variable-length source spans.
- Synthesis approval: pass.

## Contradictions And Limits

- Most chunking papers optimize retrieval, not end-to-end distillation. Advanced
  chunkers remain conditional pending a local cross-material benchmark.
- No automatic metric is a sufficient semantic oracle for long summaries. Fresh-agent
  tests and targeted human review remain necessary for high-stakes work.
- Logs, code dumps, and support corpora have less direct summarization literature than
  narrative and meeting data. Their adaptations are grounded primarily in stable
  locator, coverage, and provenance principles.

## Research Audit

The first plausible answer would have added semantic chunking and a better summary
prompt. The deeper pass changed that recommendation: it rejected any universal advanced
chunker, separated source-faithful and query-conditioned layers, split omission coverage
from factuality, introduced source-composition checks, and added representation and
revision gates. Further search is unlikely to change the stable invariants; it would
mainly alter which optional chunking or evaluation technique is preferred for a specific
corpus.

Detailed sources and claim links are in `citation-registry.md`, `evidence-ledger.md`, and
`claim-ledger.md`.

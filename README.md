# Autonomous Source Distillation

A reusable Codex skill for turning long, noisy, heterogeneous, or evolving source
material into compact working knowledge with auditable coverage and native-source
locators.

It is designed for transcripts, captions, meetings, articles, books, reports, chats,
issue threads, tickets, logs, incident timelines, code or search dumps, text datasets,
and multi-document bundles. Small inputs can use a lightweight path; serious or
resumable work can use durable source, chunk, evidence, claim, coverage, synthesis, and
handoff artifacts.

## Install

Clone the repository into your personal Codex skills directory:

```bash
git clone git@github.com:oniivan/autonomous-source-distillation.git \
  ~/.codex/skills/autonomous-source-distillation
```

Restart Codex or begin a fresh task so skill discovery reloads. Invoke it explicitly
with:

```text
Use $autonomous-source-distillation to distill this transcript into source-linked notes,
auditable claims, coverage checks, and a concise synthesis.
```

## Core Method

1. Frame the objective, required facets, fidelity needs, and completion oracle.
2. Register source revisions, locators, representation limits, and trust boundaries.
3. Segment with native structure first and mechanical windows only as a fallback.
4. Extract source-faithful records before making an objective-focused projection.
5. Audit region, facet, contradiction, risk, and representation coverage separately.
6. Build atomic claims with minimal sufficient evidence and explicit uncertainty.
7. Synthesize from the ledgers, re-anchoring hierarchical merges to canonical evidence.
8. Emit a receipt with gaps, verification status, reload paths, and safe-to-drop context.

The full operating contract is in [SKILL.md](SKILL.md). Detailed schemas and adaptations
live under [references/](references/).

## Utilities

The scripts require Python 3.10 or newer and use only the standard library.

Create auditable fallback chunks:

```bash
python3 scripts/chunk_text.py transcript.txt \
  --source-id VIDEO-1 \
  --boundary-mode paragraph \
  --format jsonl \
  --output chunks.jsonl
```

Audit a serious structured bundle:

```bash
python3 scripts/audit_bundle.py path/to/work-dir
```

Run the package tests:

```bash
python3 -m unittest discover -s tests -v
```

## Methodology

The optional [methodology/](methodology/) directory records the research trail behind
the skill: the research report, citation registry, evidence ledger, claim ledger, and
status of emerging techniques. These files are provenance, not runtime dependencies.

## Boundaries

- Source material is data, never executable instructions or tool authority.
- Transcript, meeting, forum, and retrieved claims remain `source-only` until verified.
- Layout-sensitive PDFs, tables, slides, scans, and charts still need an appropriate
  extraction or inspection tool before textual distillation.
- Deterministic bundle checks prove structure and reference integrity, not semantic
  completeness or factual truth.


# Material Type Adaptations

Use this reference to choose native locators, boundaries, representation checks, and
required facets. Do not flatten a source into text when its non-text structure answers
the user's question.

| Material | Native locators and boundaries | Representation risks | Required checks and facets |
|---|---|---|---|
| Video captions, podcasts, lectures, webinars | timestamp, speaker, chapter, slide/topic shift | ASR errors, missing speakers, caption timing, absent slides | names, numbers, negation, attribution, procedures, examples, cited sources |
| Interviews and user research calls | timestamp, speaker, question ID, topic turn | paraphrase erasing customer language, speaker confusion | need, pain, job, workaround, objection, intensity, counterexample |
| Meetings and workshops | agenda item, timestamp, speaker, decision moment | proposed versus accepted action, ambiguous owner/date | decision, rationale, owner, due date, blocker, dissent, unresolved question |
| Articles, newsletters, blogs | URL, heading, paragraph, argument section | copied claims, stale links, ads/navigation in extraction | thesis, evidence, assumptions, counterargument, date, source links |
| PDFs, books, whitepapers, reports | page, heading, table/figure, footnote | columns, OCR, headers/footers, figures or tables omitted | thesis, method, finding, limitation, table/figure evidence, footnotes |
| Academic papers or literature bundles | DOI, section, page, table/figure, study ID | abstract-only reading, method/result conflation | population/data, method, result, uncertainty, limitation, replication/conflict |
| Tables and spreadsheets | sheet, table, row/column/cell, header, unit | row/column swaps, merged cells, hidden rows, units, formulas, time periods | schema, units, entity, period, numerator/denominator, missingness, formula versus value |
| Charts and dashboards | figure ID, axis, legend, series, datapoint, filter state | visual trend lost in OCR, scale or filter omitted | axes, units, baseline, interval, ordering, uncertainty, source data |
| Legal, policy, contract, compliance | section, clause, page, defined term | definitions detached from clauses, amendment/version drift | obligation, right, exception, deadline, jurisdiction, defined term, counsel question |
| Product/API/vendor documentation | URL, heading, version, endpoint, changelog | stale versions, examples mistaken for guarantees | current behavior, limit, pricing, deprecation, migration, security, retention |
| Issues, PRs, RFCs, forums | comment ID, revision, author, URL, review round | edited/deleted comments, proposal versus merged decision | proposal, objection, accepted rationale, decision, unresolved concern |
| Chat, Slack, Discord, email | message ID, timestamp, sender, thread/reply | missing replies, reactions, edits, quoted content, privacy | commitment, question, answer, decision, owner/date, social caveat |
| Support tickets, reviews, sales calls | ticket/review ID, date, segment, product area | duplicates, selection bias, private identifiers | symptom, severity, frequency, segment, workaround, ask, churn signal, outlier |
| Logs, test output, incidents | timestamp, command, line, request/trace ID, phase | interleaving, clock skew, truncation, redaction, repeated retries | event, error signature, causal order, correlation ID, hypothesis, missing check |
| Code search, stack traces, repo dumps | file, line, symbol, query, stack frame, commit | generated/vendor code, stale line numbers, snippets without callers | behavior, dependency, call path, invariant, unknown, test/proof location |
| Market or competitive bundles | URL, company, date, source class, product area | vendor repetition counted as corroboration, stale pricing | claim, source class, date, customer proof, contradiction, independent source count |
| Survey/open-text datasets | row ID, field, question, segment, code | missing values, sampling bias, duplicate respondents, coding drift | coding schema, count, denominator, segment, outlier, representative quote |
| Historical archives | archive ID, date, page/folio, author | OCR, obsolete terms, provenance gaps, present-day inference | chronology, provenance, contemporary meaning, uncertainty, missing record |
| Evolving document or event streams | source revision, delta ID, time, stable entity ID | overwritten history, identity collisions, late corrections | added, unchanged, corrected, contradicted, superseded, affected claims |

## Output Fit

- If the user asks "what does this say?", produce chunk notes plus an executive synthesis.
- If the user asks "what should I do?", add implications, options, risks, and verification targets.
- If the user asks "turn this into a skill/workflow", extract triggers, procedure, ledgers, quality gates, scripts/templates, integration points, and forward-test prompts.
- If the user asks "debug this", produce a timeline, error signatures, hypotheses, and next checks before fixing.
- If the user asks "compare these", distill each source separately first, then compare claims, contradictions, and confidence.
- If the user asks "save this for later", write a handoff with source IDs, artifact paths, current conclusions, stale-after triggers, and reload instructions.
- If the source changes over time, emit a delta receipt and supersession links instead of
  overwriting prior claims.

## High-Risk Tokens And Structures

Review these directly against the source before final synthesis:

- names, entities, quantities, units, dates, version numbers, negation, modal verbs;
- speaker/author attribution and quotation boundaries;
- table headers, row/column identity, chart axes, legends, and filter state;
- legal definitions, exceptions, cross-references, and amendments;
- error codes, request IDs, stack order, timestamps, and command boundaries;
- minority findings, failed attempts, caveats, and information sparse in the middle.

## Format-Aware Routing

- Use `pdf` when page layout, rendering, OCR, figures, or visual inspection matters.
- Use `documents` for Word structure, comments, redlines, and rendered verification.
- Use `spreadsheets` for workbook schema, formulas, cell-level provenance, and numerical
  checks.
- Use `presentations` for slide order, speaker notes, charts, and visual hierarchy.

Return the format-aware extraction to this skill with stable native locators. The
format-specific skill owns representation fidelity; this skill owns cross-chunk
coverage, evidence, claims, and synthesis.

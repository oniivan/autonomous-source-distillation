# Citation Registry

## Local Canonical Sources

| ID | Source | Use | Limits |
|---|---|---|---|
| L1 | [`../SKILL.md`](../SKILL.md) | Current contract and ownership | Implementation, not external evidence |
| L2 | `research/context-engineering-skill-design/report.md` | Context-as-derived-view, reversibility, ownership | Broader lifecycle scope |
| L3 | `knowledge/improvement-log.md` | Origin decisions and prior verification | Historical project record |

## Primary Research And Technical Sources

| ID | Source | Material finding | Adoption note |
|---|---|---|---|
| P1 | [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/) | Relevant information is used less reliably depending on position in long input | Adopt position-robust coverage checks |
| P2 | [RULER](https://arxiv.org/abs/2404.06654) | Simple needle retrieval overstates usable context; multi-item retrieval, distractors, aggregation, and QA degrade with length | Adopt multi-fact and distractor-aware evals |
| P3 | [NoLiMa](https://proceedings.mlr.press/v267/modarressi25a.html) | Non-literal matching is harder than lexical needle retrieval | Adopt paraphrased/latent critical-fact probes |
| P4 | [Summary of a Haystack](https://aclanthology.org/2024.emnlp-main.552/) | Long-context summarization needs separate coverage and citation scoring | Adopt separate coverage and attribution gates |
| P5 | [SummN](https://aclanthology.org/2022.acl-long.112/) | Multi-stage split-then-summarize can scale to long dialogue and documents | Adopt hierarchy conditionally |
| P6 | [QMSum](https://aclanthology.org/2021.naacl-main.472/) | Query-focused meeting summarization benefits from locate-then-summarize | Adopt objective-conditioned extraction as a derived layer |
| P7 | [Context-Aware Hierarchical Merging](https://aclanthology.org/2025.findings-acl.289/) | Recursive merging can amplify hallucination; source context, extractive support, and citations improve it | Require source-backed merge audits |
| P8 | [ARC](https://aclanthology.org/2026.eacl-long.167/) | Long summaries omit sparse critical arguments; omission coverage and factual error are distinct | Adopt facet/role coverage matrix |
| P9 | [Stress Testing Factual Consistency Metrics for Long Documents](https://aclanthology.org/2026.acl-long.1472/) | Short-form factuality metrics are unstable on long, information-dense claims | Do not trust one scalar judge |
| P10 | [LongDocFACTScore](https://aclanthology.org/2024.lrec-main.941/) | Long-document factuality needs length-aware, fine-grained evaluation | Validate claims against selected source spans |
| P11 | [RoSE and Atomic Content Units](https://aclanthology.org/2023.acl-long.228/) | Fine-grained semantic units improve targeted summary evaluation | Use atomic claims/propositions in evals |
| P12 | [ACUEval](https://aclanthology.org/2024.findings-acl.597/) | Decomposing summaries into atomic units makes faithfulness checks more interpretable | Adopt atomic claim audit, not the metric wholesale |
| P13 | [Do Multi-Document Summarization Models Synthesize?](https://aclanthology.org/2024.tacl-1.58/) | Models are order-sensitive and under-sensitive to source composition | Preserve per-source stance and test reorder robustness |
| P14 | [The Power of Summary-Source Alignments](https://aclanthology.org/2024.findings-acl.389/) | Proposition-level source alignment supports salience, redundancy, and attribution tasks | Prefer minimal exact evidence spans |
| P15 | [Fundamental Limits of Prompt Compression](https://proceedings.neurips.cc/paper_files/paper/2024/hash/ac8fbba029dadca99d6b8c3f913d3ed6-Abstract-Conference.html) | Compression has a rate-distortion tradeoff and should be query-aware and variable-rate | Reject a universal compression ratio |
| P16 | [RECOMP](https://proceedings.iclr.cc/paper_files/paper/2024/hash/bda88ed2892f5e61c9a9bf215c566913-Abstract-Conference.html) | Selective query-aware compression can reduce irrelevant context | Conditional projection technique |
| P17 | [Toward Unifying Text Segmentation and Long Document Summarization](https://aclanthology.org/2022.emnlp-main.8/) | Section/topic segmentation and diversity improve written and spoken long-document summarization | Adopt structure-first segmentation and facet diversity |
| P18 | [LumberChunker](https://aclanthology.org/2024.findings-emnlp.377/) | Dynamic semantic boundaries improve one narrative retrieval benchmark | Conditional, retrieval-specific |
| P19 | [Beyond Chunk-Then-Embed](https://arxiv.org/abs/2602.16974) | A 2026 reproduction finds chunking strategy is task-dependent and simple structure-based methods can beat LLM-guided methods | Emerging; reinforces baseline-first policy |
| P20 | [Late Chunking](https://arxiv.org/abs/2409.04701) | Contextualized chunk embeddings can preserve cross-chunk references, with task/size-dependent limits | Optional retrieval adapter only |
| P21 | [Meta-Chunking](https://arxiv.org/abs/2410.12788) | Perplexity and dynamic merging may identify logical boundaries efficiently | Pilot only |
| P22 | [Measuring the Effect of Transcription Noise](https://aclanthology.org/2025.acl-long.1449/) | Noise type matters; WER alone does not predict downstream quality; entities can deserve targeted repair | Adopt raw/normalized lineage and risk flags |
| P23 | [Unstructured Evidence Attribution](https://aclanthology.org/2025.emnlp-main.95/) | Fixed evidence granularity can be inferior to exact variable-length evidence spans | Adopt minimal sufficient native spans |
| P24 | [SUMIE](https://aclanthology.org/2025.coling-main.721/) | Incrementally updated summaries suffer incomplete and incorrect entity associations | Add revision-aware delta mode |
| P25 | [Long Text and Multi-Table Summarization](https://aclanthology.org/2022.findings-emnlp.145/) | Text-only extraction can omit decisive tabular and numerical information | Add representation-fidelity gate |
| P26 | [TabFaith](https://aclanthology.org/2026.surgellm-1.21/) | Table summaries can misattribute rows/columns, numbers, rankings, and time | Emerging; require cell/schema locators for table claims |
| O1 | [OpenAI: Designing Agents to Resist Prompt Injection](https://openai.com/index/designing-agents-to-resist-prompt-injection/) | External content can contain instructions intended to redirect an agent | Adopt a hard data-not-instructions boundary |
| O2 | [Anthropic: Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval) | Isolated chunks can lose document context important for retrieval | Preserve parent/section context in chunk metadata |
| O3 | [Anthropic: Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Long-context performance is a gradient; context should be curated | Supports bounded active-context policy |

## Source-Class Audit

- Peer-reviewed or proceedings sources: covered.
- 2025-2026 emerging findings: covered.
- Technical operator/security guidance: covered.
- Contradictory evidence: covered through task-dependent chunking and metric-instability
  findings.
- Community sources: intentionally excluded because primary sources were sufficient.

# Authoritative Final Review

## Decision

Verdict: **promotable for release within the stated proof boundaries**.

The original adversarial review, the blind second review, the first adjudication, the
corrective implementation, and the independent promotion retest now support one
conclusion: all eight original findings have either been closed by code and evidence or
bounded explicitly where deterministic proof cannot own the claim. The final promotion
review found three additional release blockers in the evaluation system. Those were
corrected and independently reproduced as closed.

This verdict does not claim universal semantic accuracy. It means the package now
enforces its schema-v3 structural and readiness contracts, provides bounded fresh-agent
semantic and routing evidence, and preserves enough binding and replay evidence to detect
the evaluated classes of drift.

## Review Method

The review did not concatenate the earlier reports or give the later review automatic
priority. It:

1. grouped findings by root cause rather than reviewer wording;
2. reproduced malformed-input, false-green, portability, resource, routing, and release
   evidence claims;
3. separated deterministic structure, declared readiness, and semantic quality by proof
   owner;
4. reassessed severity after implementation;
5. retained failed attempts and correction provenance;
6. submitted the proposed release to an independent read-only promotion reviewer; and
7. required that reviewer to retest the exact three blockers it found after correction.

The evidence surface is the current code plus the dated receipts under `evals/`. The
original first review, blind review, and adjudication remain historical evidence in the
skill-factory research package; this file is the release decision.

## Consolidated Findings

### 1. Malformed-input totality and type safety

Original conclusion: both reviews found that public malformed input could crash or
false-pass. Severity was High because the CLI promised a machine-readable audit result.

Evidence: malformed status lists, unhashable JSON values, invalid UTF-8, Boolean line
numbers, duplicate keys, and non-finite numbers reproduced the defect.

Resolution: **closed**.

- `scripts/audit_bundle.py` now uses strict JSON loading, rejects duplicate keys and
  non-finite values, normalizes public fields through typed helpers, rejects Boolean
  numerics, and contains UTF-8 and I/O failures.
- The package suite and the 25-case preserved mutation suite include malformed and
  previously false-green inputs. No mutation escapes as a traceback.

Independent severity after correction: none. Future schema additions must pass through
the same total public-field boundary.

### 2. Revision, lifecycle, and source-binding invariants

Original conclusion: labels such as revision, skipped, contradicted, and superseded were
not bound strongly enough to source state. Both reviews rated the root issue High.

Evidence: schema/hash/count skew, skipped evidence supporting a claim, and superseded
claims without lineage previously passed.

Resolution: **closed for schema v3**.

- Sources have immutable revision IDs, byte hashes, line counts, locator schemes, and
  derivation metadata.
- Chunks bind source revision, exact source ranges, content bytes, and hashes.
- Evidence binds source, revision, chunk, polarity, and in-range native locators.
- Skipped notes cannot own evidence; supersession is reciprocal; coverage modes and
  readiness requirements are explicit.
- Schema v2 remains available only as a documented structural-compatibility path. Schema
  v3 owns readiness.

Independent severity after correction: none. The compatibility boundary is intentional,
not evidence that legacy bundles satisfy the stronger contract.

### 3. Corroboration, polarity, duplication, and inference

Original conclusion: the first review rated this Medium and the blind review High. The
blind severity was better supported because opposing-only evidence, aliases, and repeated
observations could alter confidence while still passing.

Resolution: **closed**.

- Canonical duplicate roots are memoized and counted once while duplicate rows remain
  available for provenance.
- Supporting, opposing, and qualifying evidence are distinct.
- Source-family derivation prevents mirrors or derived sources from being counted as
  independent support.
- Claim kind and lifecycle status constrain valid polarity combinations.
- Inferences require explicit premises.

Remaining uncertainty: source-family declarations are still supplied by the producer and
validated for internal consistency; they are not an external bibliographic identity
service.

### 4. Structural validity, readiness, and semantic proof

Original conclusion: both reviews found a High release-assurance issue, but their proposed
exit behavior differed.

The first review could be read as requiring any unresolved or failed work to make
structural validation fail. The blind review more clearly distinguished a legitimately
well-formed incomplete bundle from a ready deliverable. The latter is better supported.

Resolution: **closed through separate proof owners**.

- `scripts/audit_bundle.py` reports `structure_status` and `readiness_status` separately.
- Structure validates declared schema, references, hashes, lineage, and coverage records.
- Readiness validates completion requirements and required artifacts.
- Deterministic audit does not claim factual truth.
- Fresh-agent semantic evaluation owns its separate fixture-bounded receipt.
- The packaged starter bundle passes both structure and readiness.

The semantic suite covers C, D in both source orders, G, and I. It does not silently stand
in for unexecuted A, B, E, F, or H cases.

### 5. First-run and release usability

Original conclusion: the blind review added this Medium finding; the first review noted
command/schema divergence but underweighted arbitrary-checkout failure.

Resolution: **closed**.

- Identity tests derive the canonical identity from package metadata rather than the
  checkout basename.
- Public commands consistently use `python3`.
- A complete schema-v3 starter bundle and executable audit path are packaged.
- The stock Skill Creator validator passes in a disposable environment.

### 6. Resource behavior

Original conclusion: both reviews identified operational risk. Reproduction showed roughly
553-666 MB peak RSS on 20-26 MB line-heavy inputs. Medium remained the appropriate
severity because the issue was a capacity failure, not silent semantic corruption.

Resolution: **closed against declared local ceilings**.

- Chunk generation streams output and preserves exact boundary, whitespace, locator, and
  hash behavior through parity tests.
- Duplicate-root traversal is memoized.
- The release benchmark records about 26 MB peak RSS for 15- and 60-minute transcript
  proxies.
- A 24 MB corpus peaks at 193.766 MB and completes in 2.741 seconds.

Remaining uncertainty: these are local synthetic measurements, not universal host
guarantees.

### 7. Proportional routing

Original conclusion: both reviews agreed that proportionality was prose rather than an
operational choice. Medium was appropriate because the failure could waste tokens or omit
needed recovery controls, but length alone did not imply incorrect output.

Resolution: **closed for the evaluated route boundary**.

- The skill defines direct, light, and serious routes keyed first to risk, revision,
  source composition, reuse, audit, and resume needs.
- Word count is an assessment cue, not an automatic escalation trigger.
- Fresh agents on 2,251-word and 9,001-word low-risk fixtures recovered 5/5 facts with
  exact locators on every route.
- Direct was recommended with output-token proxies of 246 and 236. Light used 1,504 and
  1,409; serious used 7,848 and 17,654.

The evidence therefore supports direct handling for a stable low-risk 10-15 or 30-60
minute transcript when no audit, revision, multi-source, or recovery need exists. It does
not support a universal length-only router.

### 8. Methodology provenance

Original conclusion: the blind review added this as Low; some lens reports overstated it.
The weakness affected publication traceability, not runtime correctness.

Resolution: **closed to the release claim**.

- Local canonical sources are packaged.
- Material external sources now have native section, experiment, benchmark, or method
  locators in `methodology/citation-registry.md`.
- Evidence, claim, and emerging-technique ledgers distinguish adopted, conditional,
  pilot, and rejected methods.
- Optional methodology remains explanatory evidence and is excluded from the behavior
  runtime.

## Promotion Review Findings

The independent promotion reviewer found three additional release blockers after the
original eight had been remediated.

### A. Evaluator dependency closure was incompletely bound

The first corrective evaluators bound their top-level files but not all package-local
helpers. A helper change could therefore alter scoring without tripping the evaluator
binding.

Resolution: **closed and independently reproduced**.

- `scripts/evaluation_contract.py` hashes a declared evaluator file surface with stable
  path framing.
- Semantic and route preparation record the full current four-file surface; scoring
  recomputes and compares it before loading the oracle.
- The independent retest changed only a package-local locator helper. Both evaluators
  stopped with zero scored cases/routes and an isolated `evaluator_binding: fail`.
- Current semantic evaluator-surface digest:
  `0d57eaa9247af16e4b624ef0071ae8ff9d1fd394430076142cd38e87c4a0b0a2`.
- Current routing evaluator-surface digest:
  `3696e16924794db26400e113a124751af278d47c86ad8d64266ee2690050bc44`.

### B. Correction provenance was content-free

The first replay implementation accepted records that stated a correction occurred
without cross-binding the original generation, migrated outputs, corrected scorer, and
agent completion sets.

Resolution: **closed and independently reproduced**.

- Semantic replay verifies schema, mode, rerun status, runtime, case inputs, output
  manifest, retained output hashes, and completed-agent case set.
- Routing replay compares the retained failed pre-correction receipt with current
  evaluator, runtime, inputs, dispatch markers, output hashes, route set, and completed
  agent runs.
- Content-free provenance, a mismatched semantic runtime hash, and a mismatched
  pre-correction route-output hash all fail replay.

### C. Release replay omitted valid behavioral outputs

The first replay covered serious bundles but omitted semantic I and the direct/light
routing outputs. A release could therefore lose five behavioral outputs and still pass.

Resolution: **closed and independently reproduced**.

- Replay enumerates semantic cases and routing routes directly from source receipts.
- It verifies all 11 behavioral outputs, then adds the starter bundle for 12 total replay
  cases.
- Tests remove each behavioral output individually and require failure.
- The independent retest removed the original five omitted outputs together; replay
  named all five missing hashes and failed.

The reviewer reran the focused release workflow suite at 23/23 and found no new
release-blocking regression introduced by these corrections.

## Correction Provenance

One route-scoring failure was a scorer false negative, not an agent failure. Fresh agents
used the exact native form `inputs/source.txt:N`; the initial parser accepted only a
narrower wording. The failed receipts were retained. The corrected source-specific parser
rescored byte-identical outputs and preserved original dispatch markers without claiming
that agents reran.

Semantic outputs were likewise migrated byte-identically from their original generation
run into a stronger prebound scoring envelope. Generation metadata, output manifests,
agent IDs, runtime/input hashes, and scoring receipts are cross-checked during release
replay.

## Verification Evidence

- Package suite: **92/92 pass**.
- Focused independent corrective retest: **23/23 pass**.
- Mutation suite: **25/25 expected outcomes pass**, with no traceback.
- Starter bundle: schema-v3 structure and readiness pass.
- Semantic suite: C, D-A, D-B, G, and I pass; D is source-order invariant.
- Route suites: direct, light, and serious each recover 5/5 facts and exact locators for
  both 15- and 60-minute proxies.
- Resource suite: all declared time and peak-RSS ceilings pass.
- Strict replay: **11 behavioral outputs plus starter**, with runtime, inputs, evaluator
  surface, oracle, dispatch, output, and correction-provenance bindings passing.
- Stock Skill Creator validator: pass using PyYAML only in a disposable validation
  environment; the runtime remains standard-library-only.

The behavior-runtime digest evaluated by fresh agents is
`f96947351524f2389f9213d9a1cdac7dc605fabd6175ddc05a3ed9cbe0526bed`.
Its 21-file allowlist excludes evaluators, oracles, tests, retained outputs, and
methodology.

## Disagreements And Architecture Decisions

1. **Should unresolved work fail structure?** No. A valid incomplete bundle may pass
   structure and fail readiness. This preserves diagnostics without calling it ready.
2. **Should deterministic audit own semantic truth?** No. The audit owns declared
   structural and readiness invariants; withheld-oracle fresh-agent evaluation owns
   fixture-bounded semantic evidence.
3. **Should 30-60 minute transcripts automatically use serious mode?** No. Comparative
   evidence supports direct mode for stable low-risk one-pass transcripts. Risk, reuse,
   revisions, multiple sources, audit, or resume needs justify escalation.
4. **Should remediation introduce a validation framework, event-sourcing system, model
   router, or separate orchestration skill?** No. Typed standard-library helpers,
   immutable revisions with reciprocal supersession, and a short route table restore the
   advertised contract without architectural churn.
5. **Should the route false negative be erased or rerun?** Neither. Retaining the failed
   scorer receipt and proving byte-identical correction is stronger evidence than hiding
   the attempt or pretending a new generation occurred.

## Residual Limits

- Semantic evidence covers C, D, G, and I, not every documented semantic case.
- Route comparisons use one model family and synthetic low-risk transcript fixtures.
- Artifact allowlisting proves the supplied runtime surface, not host-level filesystem or
  process isolation.
- Token values are serialized-output proxies, not billing telemetry.
- Resource measurements are local and synthetic.
- A readiness pass is not a factuality guarantee. High-stakes conclusions still require
  source-appropriate human or specialist review.

These are declared proof boundaries rather than hidden release blockers. Materially
broader assurance claims should trigger new fixtures and receipts instead of being
inferred from this release.

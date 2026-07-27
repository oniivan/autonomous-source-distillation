# Semantic Evaluation

This suite executes the smallest high-risk subset of the skill's documented forward
tests:

- C: boundary-spanning evidence and overlap de-duplication;
- D: source composition, derivation, dissent, and order invariance;
- G: immutable revisions and reciprocal supersession;
- I: cold reconstruction from durable artifacts.

The fixture task and source files are public. The expected answers remain under
`oracles/` and are not copied into a staged run. Preparation binds the evaluator and
oracle hashes, then copies an explicit behavior-runtime allowlist with no evaluator,
oracle, retained output, tests, or methodology. Scoring rechecks those hashes plus every
runtime and case-input tree before loading the oracle. Give each fresh agent only its
case and that staged runtime, and keep agents mutually isolated. This is artifact-level
quarantine, not host filesystem attestation.

Prepare an external run:

```bash
python3 "$ASD_PACKAGE_ROOT/scripts/semantic_eval.py" prepare \
  --skill-root "$ASD_PACKAGE_ROOT" \
  --run-dir /tmp/asd-semantic-run
```

After all five fresh-agent outputs exist, score them:

```bash
python3 "$ASD_PACKAGE_ROOT/scripts/semantic_eval.py" score \
  --run-dir /tmp/asd-semantic-run \
  --receipt /tmp/asd-semantic-run/semantic-evaluation-receipt.json
```

Four generated serious-bundle cases must pass the real schema-v3 structure and readiness
audit in addition to the hidden semantic oracle. The D case runs twice with reversed
source order. The receipt is semantic release evidence for these cases only; it is not
consumed as a factuality judgment by `audit_bundle.py`.

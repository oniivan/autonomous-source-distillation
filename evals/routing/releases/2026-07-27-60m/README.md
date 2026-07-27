# Route Comparison Receipt: 60-Minute Proxy

All three isolated routes recovered all five sparse facts with exact locators and no
unsupported material claim.

| Route | Fact recall | Locator accuracy | Output-token proxy | Elapsed | Recovery |
|---|---:|---:|---:|---:|---|
| direct | 5/5 | 5/5 | 236 | 60.750 s | source reference |
| light | 5/5 | 5/5 | 1,409 | 122.649 s | notes, coverage, reload paths |
| serious | 5/5 | 5/5 | 17,654 | 229.362 s | audited v3 bundle and handoff |

For this stable, low-risk, one-source 9,001-word transcript, `direct` is the least
intensive passing route. This supports risk- and recovery-based escalation rather than a
length-only rule. The token measure is an artifact-size proxy, not model billing
telemetry.

The initial scorer recognized only prose such as `line 47` and rejected the equally
exact `inputs/source.txt:47` form used by direct and light agents. The failed receipt is
retained as `precorrection-locator-receipt.json`; the corrected scorer accepts only the
task's exact source path plus the expected line and preserves the original outputs and
dispatch markers.

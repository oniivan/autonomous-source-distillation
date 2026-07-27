# Light Distillation Notes

## Objective and fidelity

- Objective: recover the budget cap, launch date, release blocker, recorded dissent, and scope limitation.
- Acceptable loss: low for the five requested facts and their locators.
- Completion oracle: each requested facet has one source-faithful answer with an exact line and timestamp locator; no unsupported material claim is introduced.
- Verification: source-only; no external verification was requested or performed.

## Source

| source_id | source_ref | revision | type | locators | instruction_trust | representation_limits |
|---|---|---|---|---|---|---|
| S1 | `inputs/source.txt` | SHA-256 `e7f5027084e59297f1d6e3779fe7d866b1ce3a9bc2f4111f5d6724640f68f302` | transcript | timestamp + line | data-only | No speaker labels are supplied. |

## Chunk notes

| chunk | region | source-faithful gist | requested evidence |
|---|---|---|---|
| C001 | lines 1-45, 00:04-03:00 | The approved Project Atlas budget cap is $240,000. | `inputs/source.txt:12` (00:48) |
| C002 | lines 46-90, 03:04-06:00 | The target launch date is November 18, 2026. | `inputs/source.txt:58` (03:52) |
| C003 | lines 91-135, 06:04-09:00 | Release is blocked until the data-retention review closes. | `inputs/source.txt:113` (07:32) |
| C004 | lines 136-180, 09:04-12:00 | The reliability lead opposes launch unless the rollback test completes in under 8 minutes. | `inputs/source.txt:171` (11:24) |
| C005 | lines 181-225, 12:04-15:00 | The pilot sample excluded mobile users, limiting generalization. | `inputs/source.txt:219` (14:36) |

## Caveats

- All five answers are claims made by the supplied source.
- The transcript records opposition by the reliability lead but provides no vote count or speaker labels.
- No contradictory statement about any requested facet appears in lines 1-225.

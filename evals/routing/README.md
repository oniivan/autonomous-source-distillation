# Routing Comparison

This evaluation forces one stable transcript proxy through direct, light, and serious
routes. Profiles cover 15 minutes (about 2,250 words) and 60 minutes (about 9,000
words). A withheld oracle scores five sparse facts and their locators. The
comparison reports artifact bytes, an explicit four-characters-per-token output proxy,
elapsed wall time from dispatch marker to final artifact, and recovery features.

It is a proportionality check, not an actual model-billing receipt. It supports only
the least intensive route that preserves quality on each named synthetic profile.
Preparation binds the selected oracle, evaluator, stripped operational runtime, and
case inputs. Scoring rechecks them plus create-once dispatch markers before loading the
oracle.

```bash
python3 "$ASD_PACKAGE_ROOT/scripts/route_comparison.py" prepare \
  --run-dir /tmp/asd-route-comparison \
  --skill-root "$ASD_PACKAGE_ROOT" \
  --duration-minutes 15
```

Repeat with a separate run directory and `--duration-minutes 60` for the long profile.

Before dispatching each fresh agent:

```bash
python3 "$ASD_PACKAGE_ROOT/scripts/route_comparison.py" mark-start \
  --run-dir /tmp/asd-route-comparison \
  --case-id direct
```

After all outputs exist:

```bash
python3 "$ASD_PACKAGE_ROOT/scripts/route_comparison.py" score \
  --run-dir /tmp/asd-route-comparison \
  --receipt /tmp/asd-route-comparison/route-comparison-receipt.json
```

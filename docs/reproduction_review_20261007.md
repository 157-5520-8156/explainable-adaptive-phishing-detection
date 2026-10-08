# Reproduction and independent evaluation review — 7 October 2026

## Scope

This closes user-requested steps 2 and 3 against review base `c53564b`: raw-only one-command reproduction and a frozen independent archived-page experiment. The existing Word thesis is unchanged; the extension is experimental evidence for its next revision.

## Standards axis

Three P2 findings were corrected in `22ac6ef`:

1. Independent acquisition unnecessarily depended on unrelated source downloads. It now requests only its required Hannousse CSV and the two archived-page catalogs.
2. Reproduction entry points did not enforce the stated runtime. Both now check Python 3.12 and every pinned dependency before fitting, and record the observed versions.
3. Early acquisition/preparation failures and interruptions could lack a structured receipt. Both commands now preserve manifest status and failure details; the missing-raw CLI regression passes.

The final Standards reviewer found no remaining regression in those fixes and independently reran the comparison function for amended runs `_06` and `_07` without writing artifacts: PASS at zero tolerance. Public-host availability is separate from successful computation with verified inputs. Earlier interrupted or failed attempts remain explicitly labelled and do not count as completed experiments.

## Spec axis

The P2 exclusion-reporting gap is resolved: per-row ledgers and class/domain breakdowns now quantify 811 legitimate and 2,807 phishing target exclusions, plus 55 source exclusions. Retained target records are 7,343 legitimate and 4,397 phishing. The reviewer independently recomputed these totals.

Claims are restricted to eligible unique-content records. Mixed labels on identical content do not demonstrate wrong labels. The selected mixed-source model uses labelled target fitting/calibration folds, while source-only transfer does not. Source snapshot coverage, parser/capture differences and class-dependent retention are reported. Deterministic fitting seeds and clean reruns are not independent population replications.

## Numerical reproduction correction

Parallel forest probability accumulation can reorder floating-point sums. A historical threshold at a tied boundary consequently changed a small number of secondary forest decisions on one clean rerun, despite score differences near machine precision. Fitting still uses four workers; probability inference now uses one worker for a fixed summation order. This is an execution amendment, not model selection using test scores. Historical outputs are preserved rather than silently replaced.

Both amended raw-only executions completed all six stages:

- `experiments/reproduction_20261007_06/manifest.json`
- `experiments/reproduction_20261007_07/manifest.json`

Their post-execution comparison checks identical raw hashes, execution sources and runtime; byte-identical partition/training manifests; calibration-selected models and cutoffs; all 45 URL validation/test score archives; all 96 complete page prediction ledgers; 84 URL metric rows, 54 calibration metric rows and 48 policy/final-test rows. Substantive equality is exact, with zero tolerance. Timing/timestamp metadata is not required to match. This establishes current pinned-environment reproducibility and does not claim retrospective equality for historical parallel-forest boundary decisions.

Receipt: `experiments/reproduction_20261007_07/determinism_comparison.json`.

## Independent experiment verification

The separate verifier passes for 120 prediction files and 60 model specifications. It checks creator hashes and raw labels, exclusion against the complete retained source CSV, domain/content isolation, checkpoint scores and calibration-only model selection, and independently recomputes confusion/ranking metrics.

The raw-archive clean rerun `experiments/independent_reproduction_20261007_02` reproduces all 120 decision vectors and byte-identical training/partition manifests. Maximum score difference is 3.3306690738754696e-16; maximum ranking-metric difference is 5.960194038312494e-08. It is a reproduction, not a second corpus.

Receipts:

- `experiments/independent_20261007_02/verification.json`
- `experiments/independent_reproduction_20261007_02/reference_comparison.json`

On the 7,047 untouched eligible target records, source-only shared-page performance is FPR 3.22%, recall 66.44%; labelled mixed-source development gives FPR 1.82%, recall 79.85%. The latter meets the prespecified empirical 5%/75% targets on this population. This does not certify future-time or live deployment, nor automatic adaptation without target labels.

## Implementation checks

The full unit suite passes: 20/20 tests. Tests cover boundary calibration, fitting/calibration isolation, raw-hash rejection, passive extraction agreement, unsafe pickle rejection, download-range validation and failed-run receipts. They are synthetic implementation checks, not performance evidence.

Scientific figures are generated from saved measurements and were visually inspected. TreeSHAP additivity is verified on 200 records, with maximum log-odds residual 6.217248937900877e-15. This verifies decomposition, not causality or human trust.

The Mendeley-managed Word draft retains SHA-256 `b9aaa23286902011bfaad5ab2c64ea799d307e81a413d02a561a2b3937244bc5`; the user-edited first draft is preserved and excluded from the implementation commit.

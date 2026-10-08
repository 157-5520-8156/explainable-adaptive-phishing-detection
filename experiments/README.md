# Experiment evidence index

The accepted October 6 execution is **revision_20261006_02**. Its `manifest.json` records actual start/finish times, the executed command, raw-data hashes, the source/configuration snapshot and the hashes of generated artifacts. Its `verification.json` independently checks 9 source metric rows, 6 external metric rows and 48 replay metric rows, plus 660 sampled predictions reconstructed from saved model checkpoints.

## What was executed

| Archive | Status | Meaning |
| --- | --- | --- |
| `legacy_20261001` | Imported historical snapshot | Original files formerly under `results/`; archived on October 6. Original per-run timestamp metadata were absent. This is not a newly executed run. |
| `revision_20261006_01` | Numerical artifacts completed, process finalisation failed | The logger referred to a closed file at process exit. Retained for audit; not the accepted run. |
| `revision_20261006_02` | Completed and verified | Corrected delayed-feedback provenance, frozen external test, split sensitivity, two replay scenarios, four policies, model checkpoints. |

## Inspect the accepted run

- `source/`: immutable copies of experiment code, tests, configurations and requirements used in the run.
- `console.log`: actual execution output.
- `artifacts/static_metrics.csv`, `static_predictions.csv`: source results and original predictions.
- `artifacts/external_data_audit.json`, `external_partition_manifest.csv`: quality exclusions, overlap removal and external group roles.
- `artifacts/frozen_external_models.json`, `external_metrics.csv`, `external_predictions.csv`: frozen source-trained models and external scores. No external threshold tuning.
- `artifacts/replay_metrics.csv`, `replay_predictions.csv`, `replay_windows.csv`: all 48 real-record replay conditions, including unsuccessful comparators.
- `artifacts/label_arrival_ledger.csv`: original prediction version, label arrival and eligibility for ADWIN.
- `artifacts/replay_models/`: initial and refitted forest checkpoints.
- `artifacts/*_warmup_manifest.csv`, `*_stream_manifest.csv`: exact selected raw-record identities and order.
- `analysis/figures/`: plots and the exported numerical points for Figure 4-1. Plotting metadata link back to the prediction CSV hashes.
- `analysis/idna_overlap_audit.json`: an additional check that IDNA-normalised group identities also do not cross the protected partitions.

Raw CSVs reside once in `../data/raw/`, with acquisition records. Their checksums are repeated in each run manifest. Large derived models, predictions and manifests remain available locally but are omitted from Git; the retained scripts regenerate them. They are not placeholders or invented measurements.

## Reproduce

From the project root, after installing `requirements.txt`:

```sh
.venv/bin/python scripts/download_data.py
.venv/bin/python scripts/download_external.py
.venv/bin/python scripts/run_revision.py --run-id your_new_run_id
.venv/bin/python scripts/verify_revision.py --run-id your_new_run_id
.venv/bin/python scripts/plot_revision.py --run-id your_new_run_id
```

Choose a fresh run ID. The runner refuses to overwrite an existing archive. Timings are machine-dependent. When reloading probability CSVs for AP, use `float_precision="round_trip"` to preserve tied-score groups.

## Interpretation

The URL strings and labels are published dataset records. The source-switch order, balanced sampling and label delay are controlled experimental choices, not observed calendar-time events. Individual URL labels are adopted from the publishers, not independently reverified. The full source-trained forest fails on the frozen external population: its mean F1 is about 0.4359 and false-positive rate about 0.9973. Those results are retained and discussed, not replaced with the favourable source F1 around 0.9963.

## October 7 redesign and accepted correction

The current page-study result source is `page_20261007_02`, alongside the frozen URL redesign `redesign_20261007_03`. The previous page archive `page_20261007_01` is retained; its threshold-only calibration comparator is withdrawn because it admitted some original fitting domains. The corrected archive explicitly reuses 36 unaffected frozen executions and reruns 12 threshold-only executions. Those correction tests are post-inspection diagnostics, with no new test-driven model selection. Initial page models, partitions and the fixed/periodic primary predictions do not change.

The page contract is 44 recomputed URL statistics plus 24 creator-supplied content measurements from Hannousse V3. It is evaluated on new registered domains within that corpus, not on an unseen content source. It does not fetch current destinations. Independent verification checks 96 prediction files, actual retained-estimator calibration boundaries and label-arrival provenance. Accepted path-dependent SHAP explanations reconstruct actual log odds; a failed interventional configuration remains rejected evidence.

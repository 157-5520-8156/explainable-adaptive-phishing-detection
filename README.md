# Explainable and Adaptive Machine Learning for Phishing Detection

Research implementation and experiment evidence by Geoff. This public repository accompanies the undergraduate project proposal. Repository visibility was changed to public on 8 October 2026. Uploaded on 8 October 2026; experiments retain their actual run dates and status.

## Contents

- `src/`, `scripts/`, `configs/`: research implementation, acquisition, fitting, prediction, explanation, replay, analysis and verification procedures.
- `tests/`: regression and protocol checks.
- `experiments/`: tracked configuration, source snapshots, summary metrics, verification records and failure records. Large models, raw inputs and row-level prediction files are not bundled.
- `data/raw/*json`: source versions, provenance, official URLs and integrity information.
- `docs/`: methods, findings, correction history and reproduction scope.

School-owned templates, Word drafts, Office automation, local environments, private credentials, creator raw datasets and trained checkpoints are excluded. Dataset terms still apply when acquiring inputs. No blanket licence for third-party data is granted. This is not a live phishing-browsing service.

## Reproduction

Use Python 3.12 and the pinned dependencies:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Original URL and page study, using verified creator inputs under `data/raw`:

```sh
.venv/bin/python scripts/reproduce.py --output-dir experiments/a_fresh_raw_reproduction
```

Add `--download` to request official inputs. Network acquisition can fail independently of the experiment; failed or interrupted runs are not successful reproductions.

Independent passive archived-page study, with creator archives under `data/raw/archives` and source label CSV under `data/raw`:

```sh
.venv/bin/python scripts/reproduce_independent.py --output-dir experiments/a_fresh_independent_reproduction
```

Optional acquisition:

```sh
.venv/bin/python scripts/download_verified_inputs.py --folder data/raw --filenames hannousse_dataset_B_05_2020.csv
.venv/bin/python scripts/recover_official_archive_ranges.py --catalog data/raw/hannousse_dom_catalog.json
.venv/bin/python scripts/recover_official_archive_ranges.py --catalog data/raw/compphish_dom_catalog.json
```

Fresh output directories are required. These runners reconstruct features, eligible populations and grouped roles from raw inputs, check hashes and package versions, and retain fitting, predictions, feedback, selection and verification records. See `docs/reproduction_review_20261007.md` and `docs/independent_results_20261007.md` for completed runs and limitations. Some analysis scripts need locally regenerated checkpoints; summary files cannot substitute for those artifacts.

## Evidence boundaries

The 68-input model uses 44 URL features and 24 supplied historical webpage measurements. Its unseen-domain test within Hannousse V3 reported FPR 6.24%, phishing recall 82.22% and F1 0.8725 on 6,849 rows. This is not independent-source or future-time performance.

A separate 72-input model uses the URL features and 28 shared passive DOM aggregations. On 7,047 eligible CompPhish test rows, source-only development gave FPR 3.22% and recall 66.44%. With separate labelled target-development roles, FPR was 1.82%, recall 79.85% and F1 0.8732. The latter is not zero-target-label transfer. Published labels, archive availability, content exclusions and campaign sharing limit interpretation.

Forty-eight adaptive-policy executions use constructed record orders and label delays. They do not establish natural chronological deployment performance or unconditional adaptation benefits. Failed URL-only results and a withdrawn threshold comparator remain documented. Inspected tests are not relabelled as fresh blind tests.

SHAP contributions describe model associations, not causal evidence about malicious intent. Reconstruction checks establish numerical consistency with a model output.

## Version management

`SOURCE_SNAPSHOT.json` records the source workspace commit and every included file hash. Historical manifests may contain local paths and earlier commits; they are provenance records, not required paths on another computer. The full local working repository and data archives remain separate.

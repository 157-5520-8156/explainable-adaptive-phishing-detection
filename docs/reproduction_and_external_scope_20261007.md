# Raw reproduction and independent source evaluation

User instruction: complete the proposed steps 2 and 3 autonomously. Deliver a raw-CSV one-command pipeline, eliminate legacy cache/archive dependencies, execute it in an isolated fresh workspace, independently verify predictions and compare to retained results. New outputs must not overwrite existing evidence or the user-edited draft.

For independent evaluation, use authoritative creator datasets with real URL/label and archived webpage observations. Audit feature semantics rather than rename unrelated measurements. Freeze protocol/model/cutoff selection before viewing new test predictions; fit or tune only development roles. Preserve all outcomes and errors; no fabricated measurements or relabelled examples.

The observed CompPhish release has a different feature contract. The new passive_html_v1 branch is therefore separate from the old68-input model:44 recomputedURLstatistics+28sharedDOMaggregations. All feature extraction remains passive. Source serialized DOM is interpreted as inert data with a strict opcode/global whitelist; downloaded pickle/code is never executed. Source snapshot coverage, duplicate removals, parser and collection differences must be quantified.

Protocol authority: configs/independent_protocol.json. The old model has68 inputs; the new shared branch has72 inputs. Source-only transfer and target-development adaptation must remain clearly distinguished, and neither scores nor hyperparameters may be chosen from the sealed target test. A low false-positive fraction alone is insufficient without phishing recall. Store per-record identities/probabilities/cutoffs, group partition manifests, model/source hashes, source timestamps and independent checks.

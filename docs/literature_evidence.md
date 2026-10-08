# Literature evidence for the October 7 draft

Checked: 2026-10-01 (Asia/Shanghai). Scope: a targeted primary-source review, not a systematic or exhaustive literature review. Reference numbers below correspond to `references.json`. This note contains literature facts and proposed protocol decisions; it contains no results from our experiments.

## Decisions that the evidence supports

1. Use raw URL strings to compute documented lexical features. PhiUSIIL also includes webpage features, so using all supplied numeric columns would not constitute URL-only detection. Exclude externally derived similarity/probability fields from the primary configuration unless their construction and prediction-time availability are verified.
2. Use registered-domain-disjoint partitions for the primary static test and audit hostname/domain overlaps. A random split may be retained as a secondary comparison, with its weaker generalization claim stated explicitly.
3. Compare fixed, periodic, and drift-triggered retraining with the same base model and information budget. Describe this as adaptive batch retraining; do not call a scikit-learn Random Forest an incremental learner.
4. Run constructed streams only as controlled distribution-shift experiments. The published schema does not supply per-record observation timestamps. Donation/publication dates are not observation times; row order is not verified chronology.
5. Store predictions at first arrival. Use labels to calculate errors, update ADWIN, and train only when the labels become available. Zero delay is a favorable assumption; an instance-count delay is a simulated delay, not a measured operational labeling latency.
6. Use SHAP for prediction attribution and model diagnosis. Additivity checks and explanation repeatability do not establish causality, analyst trust, or operational utility.
7. Position the contribution as a reproducible empirical assessment of detection, interpretation, and adaptation under explicitly controlled conditions. Existing work already covers incremental phishing learning, online URL learning, domain-disjoint splitting, and SHAP stability. Do not claim these individual elements are firsts.

These are project protocol choices informed by the sources below. Their implementation and empirical benefits must be checked against the actual experiment artifacts.

## Verified evidence and boundaries

### [1] PhiUSIIL dataset: creator-owned repository record

The UCI record reports 235,795 samples: 134,850 legitimate and 100,945 phishing URLs, with features from both URL text and webpage source. It describes 54 features, no missing values, and says `FILENAME` may be ignored. Labels are 1 for legitimate and 0 for phishing. The license is CC BY 4.0. Its variable list does not list a per-record observation timestamp. The downloaded CSV schema must still be audited before quoting implementation-specific column counts.

Boundary: mixed features and statements that URLs are recent do not establish a chronological stream. UCI links the original article DOI as its dataset DOI; do not invent a separate UCI dataset DOI. Creator-published Mendeley V2 has its own DOI, 10.17632/shwpxscxy2.2.

Sources: [UCI dataset record](https://archive.ics.uci.edu/dataset/967/phiusil-phishing-url-dataset), [creator's Mendeley V2](https://data.mendeley.com/datasets/shwpxscxy2/2).

### [2] Original PhiUSIIL paper: verified metadata, limited content access

The original article is by Arvind Prasad and Shalini Chandra, in *Computers & Security*, volume 136, article 103545, January 2024. Its title explicitly includes similarity index and incremental learning. The publisher API returned title, DOI, journal, date and identifiers, but no abstract or full text. Crossref confirmed authors, volume and article number.

Boundary: cite the paper as existing incremental-learning work, but do not describe its specific update algorithm, feature equations, evaluation protocol or performance without the original text. The 2023 DOI suffix and Mendeley upload date do not change the article's 2024 issue year.

Sources: [article DOI](https://doi.org/10.1016/j.cose.2023.103545), [publisher metadata API](https://api.elsevier.com/content/article/PII:S0167404823004558?httpAccept=text/xml), [DOI registration metadata](https://api.crossref.org/works/10.1016/j.cose.2023.103545).

### [3] Online malicious URL learning predates this project

Ma, Saul, Savage and Voelker investigated online learning with lexical and host-based URL features and live labeled data. Their paper excludes webpage content and motivates online learning through scale and changing features. It supplies direct historical evidence that adaptation in URL detection is established research.

Boundary: this is malicious-site detection covering scams, spam and phishing, not the identical binary PhiUSIIL task. Host-based features include information beyond the URL string. Its reported accuracy cannot be compared directly with ours because the data, feature availability and evaluation setting differ.

Source: [author-hosted ICML 2009 paper](https://cseweb.ucsd.edu/~savage/papers/ICML09.pdf).

### [4] Random Forest is an established ensemble baseline

Breiman describes Random Forests as combinations of tree predictors using randomized components and studies their generalization properties. This supports its use as a classical nonlinear ensemble comparator.

Boundary: the general paper provides no PhiUSIIL performance evidence and does not make a batch implementation drift-aware. Periodically fitting a new forest is our adaptation policy, not a property implied by the estimator's name.

Source: [original publisher article](https://doi.org/10.1023/A:1010933404324).

### [5] SHAP explains particular predictions

Lundberg and Lee introduce additive feature attribution with desirable properties and assign importance to each feature for an individual prediction. SHAP provides a principled basis for local explanation and aggregate feature-attribution summaries.

Boundary: values explain the fitted predictive function under the explainer's feature-dependence/background assumptions. They do not independently establish phishing causation, feature correctness, robustness, or human benefit. Avoid turning a SHAP bar chart into a claim of improved trust.

Sources: [NeurIPS proceedings record](https://proceedings.neurips.cc/paper/2017/hash/8a20a8621978632d76c43dfd28b67767-Abstract.html), [official SHAP caution about causal interpretation](https://shap.readthedocs.io/en/latest/example_notebooks/overviews/Be%20careful%20when%20interpreting%20predictive%20models%20in%20search%20of%20causal%20insights.html).

### [6] Tree explanations connect local and global inspection

Lundberg and colleagues present efficient tree-model explanations, local interaction attribution, and aggregation of local explanations to inspect global model behavior. Their validation is primarily in medical tasks rather than phishing detection.

Boundary: the method does not guarantee stable attribution under arbitrary background data or correlated features. Document the selected output scale, class, feature-perturbation mode and reference data. Check reconstructed model outputs numerically. Use a common explanation background when comparing successive models, and report attribution changes separately from prediction changes.

Sources: [publisher article](https://www.nature.com/articles/s42256-019-0138-9), [official TreeExplainer API](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html).

### [7] ADWIN detects changes in a monitored stream

Bifet and Gavaldà introduce adaptively sized windows and show how error monitoring can signal model revision. The original work studies synthetic and real streams and discusses statistical guarantees under its assumptions. River documents a compressed ADWIN2 implementation, compares subwindow means, and exposes parameters including `delta`, `clock`, minimum window length and a grace period.

Boundary: an alarm identifies evidence of change in the chosen scalar stream. Monitoring classification errors requires revealed ground truth. A change in error does not by itself identify the cause, prove adversarial behavior, or distinguish prior/covariate/concept changes. Retraining benefit must be measured.

Sources: [original SIAM article](https://epubs.siam.org/doi/10.1137/1.9781611972771.42), [author-hosted original manuscript](https://www.cs.upc.edu/~gavalda/papers/adwin06.pdf), [official River API](https://riverml.xyz/latest/api/drift/ADWIN/).

### [8] Verification latency matters in stream evaluation

Grzenda, Gomes and Bifet explain that immediate-label test-then-train assumptions are inadequate when verification has latency. Their paper proposes continuous re-evaluation and demonstrates the relevance of delayed labels.

Boundary: delayed evaluation of the first-arrival prediction is not the same procedure as their continuous re-evaluation. Cite this paper for the importance of label latency. State explicitly if our study scores only the first prediction. Bibliographic year is 2020 for volume 34, pages 1237–1266; online publication was November 2019.

Source: [original open-access publisher article](https://link.springer.com/article/10.1007/s10618-019-00654-y).

### [9] Recent phishing research already tests domain isolation and SHAP stability

Ahamed and colleagues published an integrated URL-phishing evaluation in August 2026. The study combines domain-disjoint partitioning, URL mutation stress testing, multiple model families and explanation-stability analysis. The original article reports substantial robustness losses for some perturbation families despite high clean-set accuracy.

Boundary: these are the authors' reported results, not independently replicated measurements or results from our experiments. Our work should acknowledge this overlap and focus on the empirically assessed interaction of adaptive retraining, delayed labels, detection and computation cost. Do not claim domain-disjoint SHAP evaluation is new.

Source: [original Frontiers article](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2026.1834407/full).

### [10] River implements delayed progressive validation

The official `progressive_val_score` documentation exposes arrival moments and delays. Without delay it predicts, scores, then updates; with delay, targets are revealed later. The documentation warns that reusing an already trained model alters the evaluation.

Boundary: a toolkit does not validate our data order. An instance index is adequate for a declared constructed stream but cannot be reported as actual calendar time. The code must retain the original prediction until its label arrives rather than silently substitute a later model's prediction.

Source: [official River documentation](https://riverml.xyz/latest/api/evaluate/progressive-val-score/).

### [11] Group partitions separate group identities

`GroupShuffleSplit` partitions using supplied grouping information. Its size parameters describe fractions/counts of groups rather than rows, and independently generated test splits can overlap across repetitions.

Boundary: grouping by a URL hostname alone does not separate sibling subdomains. Our registered-domain extraction policy and Public Suffix List snapshot must be documented. Group splitting is not automatically stratified; audit actual class proportions, row counts and overlap for each split. Domain isolation does not eliminate collection bias or all campaign similarity.

Source: [official scikit-learn API](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html).

### [12] Preprocessing must respect evaluation partitions

Official scikit-learn guidance defines leakage as using information unavailable at prediction time, warns against fitting preprocessing on test data, and recommends splitting before fitted transformations. Pipelines help preserve these boundaries in tuning and evaluation.

Boundary: preventing scaler/selector leakage does not verify precomputed external features. We therefore propose recomputing primary features from raw URLs, and investigating supplied similarity/probability features separately. A correlation with the label is a risk signal for audit; it is not sufficient proof of leakage.

Source: [official scikit-learn common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html).

## Proposed research questions and honest contribution statement

- RQ1: How do linear and tree-based baselines perform on unseen registered domains using reproducible URL lexical features?
- RQ2: Which features influence the selected tree model, and how repeatable, additive and computationally expensive are the resulting explanations under documented settings?
- RQ3: Under a constructed distribution shift, how do fixed, periodic and ADWIN-triggered retraining compare in phishing recall, false-positive rate, F1/average precision, update count and update cost, including a simulated label delay?

Draft wording: “This project implements and evaluates a reproducible URL-phishing classification pipeline that integrates tree-model attribution with controlled adaptive retraining. It compares detection performance, interpretation diagnostics and computational costs under domain-isolated evaluation and explicitly constructed distribution shifts.”

This is an integration and empirical evaluation claim. It is not a claim of a new classifier, new SHAP algorithm, new drift detector, comprehensive literature coverage, or production qualification. If adaptive retraining fails to outperform the static or periodic comparator, report that result and examine why.

## Experiment-reporting checks

- Preserve raw data hash, downloaded filename, version, license, label mapping and the exact feature list.
- Record deduplication and invalid-URL policy; audit conflicts before dropping rows.
- Preserve group identities, split manifests and class counts; ensure zero selected-group overlap.
- Fit transformation parameters and select settings using development data only. Fix the threshold and experiment configurations before scoring the final static holdout.
- State stream construction, subgroup selection, phase boundaries, seed and the intended kind of shift. Merely changing feature frequencies establishes distribution shift, not necessarily changed conditional label relationships.
- Store initial predictions, revealed-label events, retraining events and model identifiers. Distinguish observation index from measured time.
- Report all strategy outcomes, including zero alarms or unsuccessful retraining. Do not tune the detector against evaluation labels and then call the same replay an independent test.
- Report the local machine and measured runtime. Fewer retrains do not alone prove lower total latency or memory use.
- State that URLs are archived benchmark strings and no live-site validation has been performed unless separate evidence exists.

## Bibliography handling

`references.json` contains 12 selected entries with numeric keys, verified bibliographic metadata, evidence-access status and URLs. Documentation entries have no invented publication year; use “n.d.” with the access date. The original PhiUSIIL paper is included with an explicit limited-content-access flag. Optional API pages in the evidence sections document implementation semantics; cite them separately in the thesis if those details are discussed extensively.

Supplemental baseline API: [official LogisticRegression documentation](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html). It describes a regularized logistic classifier; this provides implementation semantics, not an original phishing-specific result.

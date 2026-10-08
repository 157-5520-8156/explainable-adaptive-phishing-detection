# Review and correction record

Review base: 16e057b. First reviewed implementation: 798cda7. The implement and code-review skills required separate Standards and Spec reviews. Both independently found threshold-only calibration reuse of domains previously fitted by its retained estimator. This was a material methodology defect, not a test-domain leak.

Original evidence stays in page_20261007_01. It is no longer the accepted threshold comparator. Corrected evidence is page_20261007_02: 36 valid executions and their tests are explicitly reused; 12 threshold-policy executions are rerun using only original calibration plus revealed recent replay domains. Corrected threshold test measurements are post-inspection correction diagnostics, not new blind confirmation. No model-family, hyperparameter or operating-point selection used test results. The fixed and periodic primary measurements do not change.

The verifier now checks calibration against the actual retained estimator's original fit domains for threshold policy and matches replay manifests back to the real feedback pool. A regression check excludes original fitted domains from the threshold calibration interface. The prediction CLI now rejects unsupported non-HGB checkpoints explicitly instead of treating forest class-probability attributions as scalar log odds.

Standards axis: two runtime/methodology defects found and addressed; duplicated metric code noted as a maintenance heuristic, with no demonstrated metric discrepancy.
Spec axis: one material calibration-boundary defect found and addressed; remaining source/test/feedback/explanation boundaries verified. No deployment qualification is claimed.

The follow-up reviews independently verified all 168 corrected threshold-update events and byte equality for the 36 reused runs. A preliminary concern about a missing snapshot helper was withdrawn after checking the executed archive: its runner uses the inline calibration correction and imports only FeedbackMonitor; the later helper is working-tree regression hardening. The executed snapshot is preserved. The inherited primary test timestamp is explicitly labelled, and correction output-write ranges are reconstructed separately from filesystem timestamps without inventing a logger.

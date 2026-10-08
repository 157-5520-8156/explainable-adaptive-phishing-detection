"""Compare completed raw-only runs after their execution, without cache reuse."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def compare(left: Path, right: Path) -> dict:
    manifests = [json.loads((p / 'manifest.json').read_text()) for p in (left, right)]
    for manifest in manifests:
        assert manifest['status'] == 'complete'
        assert manifest['raw_only_start']
        assert not manifest['old_experiment_or_processed_cache_copied']
    assert manifests[0]['input_files'] == manifests[1]['input_files']
    assert manifests[0]['source_sha256'] == manifests[1]['source_sha256']
    assert manifests[0]['runtime'] == manifests[1]['runtime']
    checks = []
    for name in ['development_partition_manifest.csv', 'new_source_partition_manifest.csv', 'training_manifest.csv']:
        relative = Path('workspace/experiments/url_run/artifacts') / name
        assert (left / relative).read_bytes() == (right / relative).read_bytes(), name
        checks.append({'file': str(relative), 'byte_identical': True})
    for name in ['url_test_metrics.csv', 'page_replay_metrics.csv', 'page_final_test_metrics.csv',
                 'workspace/experiments/url_run/artifacts/validation_metrics.csv']:
        a = pd.read_csv(left / name, float_precision='round_trip')
        b = pd.read_csv(right / name, float_precision='round_trip')
        # Elapsed time depends on OS scheduling; it is recorded, not a model result.
        ignored = [c for c in ['seconds'] if c in a.columns]
        a = a.drop(columns=ignored)
        b = b.drop(columns=ignored)
        pd.testing.assert_frame_equal(a, b, check_exact=True)
        checks.append({'file': name, 'rows': len(a), 'all_substantive_values_identical': True,
                       'ignored_timing_columns': ignored})
    for name in ['url_run/artifacts/validation_calibrations.json', 'page_run/artifacts/selection.json']:
        relative = Path('workspace/experiments') / name
        a, b = [json.loads((p / relative).read_text()) for p in (left, right)]
        if isinstance(a, dict):
            a.pop('frozen_at', None)
            b.pop('frozen_at', None)
        assert a == b, name
        checks.append({'file': str(relative), 'calibration_identical': True})
    relative = Path('workspace/experiments/url_run/artifacts/validation_selection.json')
    a, b = [json.loads((p / relative).read_text()) for p in (left, right)]
    for key in ['selected_family', 'validation_ranking', 'selection_data', 'test_scores_inspected']:
        assert a[key] == b[key], key
    score_files = sorted((left / 'workspace/experiments/url_run/artifacts').glob('*scores_*.npz'))
    assert len(score_files) == 45, len(score_files)
    for file in score_files:
        relative = file.relative_to(left)
        with np.load(file) as a, np.load(right / relative) as b:
            assert set(a.files) == set(b.files)
            for key in a.files:
                assert np.array_equal(a[key], b[key]), (str(relative), key)
    vectors = 0
    for directory in sorted((left / 'workspace/experiments/page_run/artifacts/replays').iterdir()):
        for name in ['predictions.csv', 'test_predictions.csv']:
            relative = directory.relative_to(left) / name
            a = pd.read_csv(left / relative, float_precision='round_trip')
            b = pd.read_csv(right / relative, float_precision='round_trip')
            pd.testing.assert_frame_equal(a, b, check_exact=True)
            vectors += 1
    assert vectors == 96, vectors
    return {'status': 'PASS', 'left': str(left), 'right': str(right),
            'same_verified_raw_inputs_and_source_and_runtime': True,
            'comparison_started_after_both_runs_completed': True,
            'checks': checks, 'identical_url_score_archives': len(score_files),
            'identical_page_prediction_ledgers': vectors,
            'comparison_tolerance': 0,
            'interpretation': 'Exact substantive reproduction in this pinned environment after serial forest inference amendment; not independent population replication or historical forest boundary equality.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.left, args.right)
    (args.right / 'determinism_comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))

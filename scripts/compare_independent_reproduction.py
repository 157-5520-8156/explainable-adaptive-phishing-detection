"""Confirm that a raw-only rerun preserves frozen domain roles and decisions."""
from pathlib import Path
import argparse,json
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--reproduction-dir',type=Path,required=True);args=parser.parse_args();r=args.reproduction_dir
original=ROOT/'experiments/independent_20261007_02/artifacts';fresh=r/'workspace/experiments/independent_run/artifacts'
for name in ['partition_manifest.csv','source_only_training_manifest.csv','mixed_source_development_training_manifest.csv','source_only_calibration_manifest.csv','mixed_source_development_calibration_manifest.csv']:
 if (original/name).read_bytes()!=(fresh/name).read_bytes():raise AssertionError('Changed role/training assignment: '+name)
keys=['regime','branch','family','seed','budget'];a=pd.read_csv(original/'all_test_metrics.csv',float_precision='round_trip').sort_values(keys).reset_index(drop=True);b=pd.read_csv(fresh/'all_test_metrics.csv',float_precision='round_trip').sort_values(keys).reset_index(drop=True)
assert a[keys].equals(b[keys]) and np.array_equal(a[['tn','fp','fn','tp']].to_numpy(),b[['tn','fp','fn','tp']].to_numpy())
metrics=['fpr','recall','f1','average_precision','roc_auc'];delta=float(np.max(np.abs(a[metrics].to_numpy()-b[metrics].to_numpy())));assert delta<1e-5
vectors=0;score_delta=0.
for p in original.glob('*test_predictions.csv'):
 x=pd.read_csv(p,float_precision='round_trip');y=pd.read_csv(fresh/p.name,float_precision='round_trip')
 assert np.array_equal(x.URL,y.URL) and np.array_equal(x.y,y.y) and np.array_equal(x.prediction,y.prediction)
 difference=float(np.max(np.abs(x.score.to_numpy()-y.score.to_numpy())));assert difference<1e-12;score_delta=max(score_delta,difference);vectors+=1
out={'status':'PASS','compared_prediction_vectors':vectors,'all_confusion_counts_identical':True,'all_partition_and_training_manifests_byte_identical':True,'maximum_score_difference':score_delta,'maximum_ranking_metric_difference':delta,'no_prior_features_or_models_used_by_clean_run':True,'scope':'Reproduction on the pinned environment, not another independent population.'}
(r/'reference_comparison.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))

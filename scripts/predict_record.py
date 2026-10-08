"""Predict and explain an archived page record without visiting its URL."""
import argparse,json,sys
from pathlib import Path
import joblib,pandas as pd,numpy as np,shap
from scipy.special import expit
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',required=True,type=Path)
    parser.add_argument('--record',required=True,type=Path,help='JSON with URL and all 24 archived content measurements')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    # Only project-generated checkpoints should be loaded, as joblib is pickle based.
    state=joblib.load(args.checkpoint);bundle=state['bundle']
    if bundle.family != 'hist_gradient_boosting':
        parser.error('This interface supports selected histogram-gradient-boosting page checkpoints only')
    record=json.loads(args.record.read_text());frame=pd.DataFrame([record]);X=bundle.matrix(frame)
    score=float(bundle.estimator.predict_proba(X)[0,1]);threshold=float(state['threshold'])
    explained=shap.TreeExplainer(bundle.estimator,feature_perturbation='tree_path_dependent',model_output='raw')(X,check_additivity=True)
    values=np.asarray(explained.values)[0];base=float(np.asarray(explained.base_values)[0]);raw=base+float(values.sum())
    if abs(float(expit(raw))-score)>1e-8: raise RuntimeError('Explanation does not reconstruct the model score')
    result={'phishing_score':score,'decision_threshold':threshold,'prediction':'phishing' if score>=threshold else 'legitimate',
            'decision_version':int(state['decision_version']),'model_family':bundle.family,
            'input_contract':'archived URL plus creator-supplied webpage measurements',
            'explanation_space':'log odds','base_log_odds':base,'reconstructed_log_odds':raw,
            'feature_contributions':[{ 'feature':bundle.feature_names[i], 'value':float(X.iloc[0,i]), 'contribution_log_odds':float(values[i])}
                                     for i in np.argsort(-np.abs(values))]}
    text=json.dumps(result,indent=2,allow_nan=False)+'\n'
    if args.output: args.output.write_text(text)
    else: print(text,end='')

if __name__=='__main__': main()

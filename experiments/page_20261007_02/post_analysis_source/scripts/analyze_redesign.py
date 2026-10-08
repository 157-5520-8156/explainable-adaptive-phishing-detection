"""Post-freeze explanations, invariance, paired uncertainty and visual evidence."""
from pathlib import Path
import json,sys
import joblib,numpy as np,pandas as pd,shap
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.special import expit
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from page_model import CONTENT_FEATURES
from url_model_v2 import normalize_url
from evaluation import metrics
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--run-id',default='page_20261007_02');args=parser.parse_args()
RUN=ROOT/'experiments'/args.run_id;A=RUN/'artifacts';O=RUN/'analysis';O.mkdir(exist_ok=True);F=O/'figures';F.mkdir(exist_ok=True)
def dump(path,obj): Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
selection=json.loads((A/'selection.json').read_text());family=selection['family']
bundle=joblib.load(A/f'{family}_42.joblib');train=pd.read_pickle(A/'initial_train.pkl');test=pd.read_pickle(A/'sealed_test.pkl')
cut=next(c['threshold'] for c in selection['calibrations'] if c['family']==family and c['seed']==42 and c['budget']==.05)
joblib.dump({'bundle':bundle,'threshold':cut,'decision_version':0},A/'initial_selected_42.joblib',compress=3)
# Interventional TreeSHAP with explicit background failed numerical additivity.
# Retain the failure; use the separately verified training-path formulation.
dump(O/'rejected_interventional_explanation.json', {'status':'REJECTED', 'background_n':100, 'example_reconstruction':4.920196, 'example_model_log_odds':5.463303, 'reason':'Numerical additivity failed; these attributions are not reported as valid.'})
explain=test.sample(n=200,random_state=20261007).copy();X=explain[bundle.feature_names]
explainer=shap.TreeExplainer(bundle.estimator,feature_perturbation='tree_path_dependent',model_output='raw')
sv=explainer(X,check_additivity=True);values=np.asarray(sv.values);base=np.asarray(sv.base_values)
raw=bundle.estimator.decision_function(X);err=np.max(np.abs(base+values.sum(axis=1)-raw))
assert err<1e-5
assert np.max(np.abs(expit(raw)-bundle.estimator.predict_proba(X)[:,1]))<1e-12
rank=pd.DataFrame({'feature':bundle.feature_names,'mean_absolute_shap_log_odds':np.abs(values).mean(axis=0)}).sort_values('mean_absolute_shap_log_odds',ascending=False)
rank.to_csv(O/'shap_global.csv',index=False)
np.savez_compressed(O/'shap_values.npz',values=values,base=base,raw_score=raw)
explain[['URL','group','y']].to_csv(O/'explanation_manifest.csv',index=False)
fullscores=bundle.estimator.predict_proba(test[bundle.feature_names])[:,1]
local=[]
for label,true,pred in [('true_phishing',1,1),('false_negative',1,0),('false_positive',0,1),('true_normal',0,0)]:
    indices=np.flatnonzero((test.y.to_numpy()==true)&((fullscores>=cut).astype(int)==pred))
    idx=int(indices[0]);row=test.iloc[[idx]];sx=explainer(row[bundle.feature_names]);v=np.asarray(sx.values)[0];b=float(np.asarray(sx.base_values)[0])
    top=np.argsort(-np.abs(v))[:6]
    local.append({'case':label,'url':str(row.URL.iloc[0]),'published_y':true,'prediction':pred,'score':float(fullscores[idx]),'threshold':cut,
                  'base_log_odds':b,'reconstructed_log_odds':b+float(v.sum()),
                  'top_contributions':[{'feature':bundle.feature_names[k],'value':float(row[bundle.feature_names].iloc[0,k]),'shap_log_odds':float(v[k])} for k in top]})
dump(O/'local_explanations.json',local)
dump(O/'explanation_audit.json',{'model':'initial selected seed 42','output_space':'raw log odds; expit gives phishing score',
    'feature_perturbation':'tree_path_dependent', 'background':'training tree path counts; no explicit background sample','explained_n':200,'max_additivity_error':float(err),'human_evaluation_performed':False,'causal_interpretation_supported':False})
# Post hoc feature-group ablations use identical fitting/calibration/test domains.
# They are diagnostics after test inspection and do not replace the selected model.
from sklearn.ensemble import HistGradientBoostingClassifier
from url_model_v2 import training_weights,calibrate_threshold
cal=pd.read_pickle(A/'calibration.pkl');P=json.loads((RUN/'source/configs/page_protocol.json').read_text());abl=[]
for group,names in [('url_only',[n for n in bundle.feature_names if n not in CONTENT_FEATURES]),('content_only',CONTENT_FEATURES)]:
    m=HistGradientBoostingClassifier(**P['hist_gradient_boosting'],random_state=42)
    m.fit(train[names],train.y,sample_weight=training_weights(train));cp=m.predict_proba(cal[names])[:,1]
    t=calibrate_threshold(cal.y,cp,cal.source,.05)['threshold'];tp=m.predict_proba(test[names])[:,1]
    joblib.dump(m,O/f'ablation_{group}.joblib',compress=3)
    abl.append({'features':group,'diagnostic_status':'post hoc after primary test inspection','threshold':t,**metrics(test.y,tp,t,test.group)})
abl.append({'features':'combined','diagnostic_status':'frozen primary','threshold':cut,**metrics(test.y,fullscores,cut,test.group)})
pd.DataFrame(abl).to_csv(O/'feature_group_ablations.csv',index=False)
# URL-only root normalization invariant under the selected URL bundle.
url=ROOT/'experiments/redesign_20261007_03/artifacts';ub=joblib.load(url/'static_models/hist_gradient_boosting_42.joblib')
roots=pd.read_pickle(ROOT/'data/processed/url_features.pkl');roots=roots[roots.y.eq(0)].head(200).URL.tolist()
from urllib.parse import urlsplit
roots=[urlsplit(u)._replace(path='',query='',fragment='').geturl() for u in roots]
p0=ub.predict_proba(roots)[:,1];p1=ub.predict_proba([u+'/' for u in roots])[:,1]
assert np.array_equal(p0,p1)
dump(O/'root_invariance.json',{'actual_legitimate_rows':200,'max_score_difference':float(np.max(np.abs(p0-p1))),
                               'old_baseline_root_slash_flips':200,'new_score_flips':int((p0!=p1).sum()),
                               'interpretation':'Representation invariance only, not proof of label accuracy.'})
# Paired resampling of test domains for a fixed seed and prespecified policy contrast.
base=pd.read_csv(A/'replays/path_profile_fixed_delay2_seed42/test_predictions.csv')
alt=pd.read_csv(A/'replays/path_profile_periodic_delay2_seed42/test_predictions.csv')
assert np.array_equal(base.group,alt.group) and np.array_equal(base.y,alt.y)
f=pd.DataFrame({'group':base.group,'normal':(base.y==0).astype(int),'positive':(base.y==1).astype(int),
                'd_fp':((alt.prediction-base.prediction)*(base.y==0)).astype(int),
                'd_tp':((alt.prediction-base.prediction)*(base.y==1)).astype(int)})
sums=f.groupby('group')[['normal','positive','d_fp','d_tp']].sum().to_numpy();rng=np.random.default_rng(20261007);diff=[]
for _ in range(1000):
    n,p,fp,tp=sums[rng.integers(0,len(sums),len(sums))].sum(axis=0);diff.append([fp/n,tp/p])
dump(O/'paired_policy_intervals.json',{'comparison':'periodic minus fixed; path_profile delay2 seed42',
                                     'domain_bootstrap_replicates':1000,'delta_fpr_95':list(map(float,np.quantile(np.array(diff)[:,0],[.025,.975]))),
                                     'delta_recall_95':list(map(float,np.quantile(np.array(diff)[:,1],[.025,.975]))),
                                     'conditional_on_fitted_models':True})
plt.rcParams.update({'font.family':'Arial','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':160})
def save(name): plt.tight_layout();plt.savefig(F/name,bbox_inches='tight');plt.close()
# Explicitly separated branch metrics; no misleading common-denominator bars.
from sklearn.metrics import precision_recall_curve
plt.figure(figsize=(7.0,3.5));pr,rc,_=precision_recall_curve(test.y,fullscores);plt.step(rc,pr,where='post',color='#164f7a');plt.axhline(float(test.y.mean()),color='#777777',linestyle='--',linewidth=.8,label='Test prevalence');plt.scatter([metrics(test.y,fullscores,cut)['recall']],[metrics(test.y,fullscores,cut)['precision']],c='black',label='Frozen 5% calibration cutoff');plt.xlabel('Phishing recall');plt.ylabel('Precision');plt.legend();plt.ylim(0,1.02);plt.xlim(0,1);save('figure_4_1_page_pr.png')
plt.figure(figsize=(7,3.8));top=rank.head(10).iloc[::-1];plt.barh(top.feature,top.mean_absolute_shap_log_odds,color='#164f7a');plt.xlabel('Mean absolute TreeSHAP contribution (log odds)');save('figure_4_2_shap.png')
from sklearn.metrics import ConfusionMatrixDisplay
plt.figure(figsize=(5,3.6));ConfusionMatrixDisplay.from_predictions(test.y,fullscores>=cut,display_labels=['Legitimate','Phishing'],ax=plt.gca(),cmap='Blues',colorbar=False);save('figure_4_3_confusion.png')
replays=pd.read_csv(A/'replay_metrics.csv');final=pd.read_csv(A/'final_test_metrics.csv')
plt.figure(figsize=(7,3.8));
for policy,color in [('fixed','#666666'),('threshold','#bd6a15'),('periodic','#164f7a'),('drift','#39834b')]:
    pred=pd.read_csv(A/f'replays/path_profile_{policy}_delay2_seed42/predictions.csv');batch=pred.groupby('batch').apply(lambda g:(g.prediction!=g.y).mean(),include_groups=False);plt.plot(batch.index,batch.values,label=policy,color=color,marker='.',linewidth=1)
plt.xlabel('Replay batch (160 records; final batch is partial)');plt.ylabel('Original prediction error rate');plt.legend(ncol=4);save('figure_4_4_replay.png')
plt.figure(figsize=(7,3.4));agg=final.groupby(['order','delay','policy'])[['fpr','recall']].mean();
for policy,marker in [('fixed','o'),('threshold','s'),('periodic','^'),('drift','D')]:
    pts=agg.xs(policy,level='policy');plt.scatter(100*pts.fpr,100*pts.recall,label=policy,marker=marker,s=130 if policy=='fixed' else 45,facecolors='none' if policy=='fixed' else None,edgecolors='black' if policy=='fixed' else None,zorder=5 if policy=='fixed' else 3)
plt.axvline(5,color='#777777',linestyle='--',linewidth=.8);plt.xlabel('Final unseen-domain false-positive rate (%)');plt.ylabel('Phishing recall (%)');plt.legend(ncol=4);save('figure_4_5_tradeoff.png')
dump(O/'summary.json',{'selected_family':family,'static_test':metrics(test.y,fullscores,cut,test.group),
                      'initial_cutoff':cut,'paired_policy_intervals':json.loads((O/'paired_policy_intervals.json').read_text()),
                      'content_feature_count':24,'url_feature_count':44,'test_evaluation_is_new_domains_same_corpus':True})
print(json.dumps(json.loads((O/'summary.json').read_text()),indent=2))

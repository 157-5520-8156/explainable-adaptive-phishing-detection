"""Conditional cluster uncertainty, numerical explanations and final scientific figures."""
from pathlib import Path
import argparse,json,sys,shutil
import joblib,numpy as np,pandas as pd,shap
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.special import expit
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from raw_protocol import file_sha256

def dump(p,o):Path(p).write_text(json.dumps(o,indent=2,allow_nan=False)+'\n')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args();run=ROOT/'experiments'/args.run_id;A=run/'artifacts';O=run/'analysis';O.mkdir();F=O/'figures';F.mkdir()
 selected=json.loads((A/'selection.json').read_text());test=pd.read_pickle(A/'target_features.pkl');test=test[test.partition.eq('sealed_test')].reset_index(drop=True)
 # One domain resampling draw is shared by every selected-pipeline contrast.
 frames={};summaries={}
 for choice in selected['selected']:
  key=choice['regime']+'__'+choice['branch'];spec=next(s for s in selected['models'] if all(s[k]==choice[k] for k in ['regime','branch','family']) and s['seed']==42)
  frame=pd.read_csv(A/(Path(spec['model_path']).stem+'_budget0.05_test_predictions.csv'),float_precision='round_trip');frames[key]=frame
  df=frame.assign(normal=(frame.y==0).astype(int),positive=(frame.y==1).astype(int),fp=((frame.y==0)&(frame.prediction==1)).astype(int),tp=((frame.y==1)&(frame.prediction==1)).astype(int))
  summaries[key]=df.groupby('group')[['normal','positive','fp','tp']].sum()
 keys=list(summaries);domains=summaries[keys[0]].index
 assert all(x.index.equals(domains) for x in summaries.values())
 rng=np.random.default_rng(20261007);replicates={k:[] for k in keys}
 for _ in range(1000):
  draw=rng.integers(0,len(domains),len(domains))
  for key in keys:
   n,p,fp,tp=summaries[key].to_numpy()[draw].sum(axis=0);replicates[key].append([fp/n,tp/p,2*tp/(p+tp+fp)])
 intervals={key:{metric:list(map(float,np.quantile(np.asarray(values)[:,j],[.025,.975]))) for j,metric in enumerate(['fpr','recall','f1'])} for key,values in replicates.items()}
 contrasts={}
 for name,new,old in [('mixed_page_minus_source_page','mixed_source_development__shared_page_72','source_only__shared_page_72'),('mixed_page_minus_mixed_url','mixed_source_development__shared_page_72','mixed_source_development__url_only_44')]:
  delta=np.asarray(replicates[new])-np.asarray(replicates[old]);contrasts[name]={metric:list(map(float,np.quantile(delta[:,j],[.025,.975]))) for j,metric in enumerate(['fpr','recall','f1'])}
 dump(O/'domain_bootstrap.json',{'replicates':1000,'seed':20261007,'fitting_seed':42,'intervals_95':intervals,'paired_contrasts_95':contrasts,'conditional_on_models_and_corpus':True,'causal_feature_effect_established':False})
 choice=next(c for c in selected['selected'] if c['regime']=='mixed_source_development' and c['branch']=='shared_page_72')
 spec=next(s for s in selected['models'] if all(s[k]==choice[k] for k in ['regime','branch','family']) and s['seed']==42)
 model=joblib.load(run/spec['model_path']);sample=test.sample(n=min(200,len(test)),random_state=20261007);X=sample[spec['features']]
 if spec['family']=='numeric_logistic':
  scaler,estimator=model.steps[0][1],model.steps[1][1];train=pd.concat([pd.read_pickle(A/'source_features.pkl').query('partition=="source_train"'),pd.read_pickle(A/'target_features.pkl').query('partition=="target_train"')]);background=scaler.transform(train[spec['features']].sample(n=100,random_state=20261007));sx=scaler.transform(X)
  ex=shap.LinearExplainer(estimator,background)(sx);values=np.asarray(ex.values);base=np.asarray(ex.base_values);actual=model.decision_function(X);space='log odds'
 else:
  ex=shap.TreeExplainer(model,feature_perturbation='tree_path_dependent',model_output='raw')(X,check_additivity=True)
  if spec['family']=='random_forest':values=np.asarray(ex.values)[:,:,1];base=np.asarray(ex.base_values)[:,1];actual=model.predict_proba(X)[:,1];space='phishing class probability'
  else:values=np.asarray(ex.values);base=np.asarray(ex.base_values);actual=model.decision_function(X);space='log odds'
 error=float(np.max(np.abs(base+values.sum(axis=1)-actual)));assert error<1e-5
 if space=='log odds':assert np.max(np.abs(expit(actual)-model.predict_proba(X)[:,1]))<1e-12
 rank=pd.DataFrame({'feature':spec['features'],'mean_abs_contribution':np.abs(values).mean(axis=0)}).sort_values('mean_abs_contribution',ascending=False);rank.to_csv(O/'shap_global.csv',index=False)
 dump(O/'explanation_verification.json',{'family':spec['family'],'scope':'selected mixed-source shared-page model, seed42','output_space':space,'sample_n':len(sample),'maximum_additivity_error':error,'human_or_causal_validation':False})
 sample[['URL','group','y']].to_csv(O/'explanation_manifest.csv',index=False)
 np.savez_compressed(O/'shap_values.npz',values=values,base=base,output=actual)
 dump(O/'selected_model_spec.json',spec);joblib.dump({'model':model,'threshold':spec['cutoffs']['0.05'],'features':spec['features'],'family':spec['family'],'feature_contract':'passive_html_v1+normalized_url_v3','source_model_sha256':spec['sha256']},O/'selected_page_seed42.joblib',compress=3)
 plt.rcParams.update({'font.family':'Arial','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':160})
 def save(name):plt.tight_layout();plt.savefig(F/name,bbox_inches='tight');plt.close()
 # Percent axes start at zero; paired uncertainty remains in the adjacent report.
 labels=['Source URL','Source page','Mixed URL','Mixed page'];ordered=['source_only__url_only_44','source_only__shared_page_72','mixed_source_development__url_only_44','mixed_source_development__shared_page_72']
 from sklearn.metrics import recall_score
 fprs=[float(f.prediction[f.y==0].mean())*100 for k in ordered for f in [frames[k]]];recalls=[float(f.prediction[f.y==1].mean())*100 for k in ordered for f in [frames[k]]]
 fig,axs=plt.subplots(1,2,figsize=(8,3.7));axs[0].bar(labels,fprs,color='#164f7a');axs[0].axhline(5,color='#666',linestyle='--',linewidth=.8);axs[0].set_ylabel('Legitimate false-positive rate (%)');axs[1].bar(labels,recalls,color='#164f7a');axs[1].axhline(75,color='#666',linestyle='--',linewidth=.8);axs[1].set_ylabel('Phishing recall (%)');axs[1].set_ylim(0,100)
 for ax in axs:ax.tick_params(axis='x',rotation=25)
 save('independent_primary_comparison.png')
 plt.figure(figsize=(7,3.8));top=rank.head(10).iloc[::-1];plt.barh(top.feature,top.mean_abs_contribution,color='#164f7a');plt.xlabel('Mean absolute SHAP contribution ('+space+')');save('independent_shap.png')
 from sklearn.metrics import precision_recall_curve,ConfusionMatrixDisplay
 plt.figure(figsize=(6.5,3.5))
 for k,label in [('source_only__shared_page_72','Source-only page'),('mixed_source_development__shared_page_72','Mixed-source page')]:
  f=frames[k];p,r,_=precision_recall_curve(f.y,f.score);plt.step(r,p,where='post',label=label)
 plt.axhline(float(test.y.mean()),color='#777',linestyle='--',label='Test prevalence');plt.xlabel('Phishing recall');plt.ylabel('Precision');plt.xlim(0,1);plt.ylim(0,1);plt.legend();save('independent_precision_recall.png')
 f=frames['mixed_source_development__shared_page_72'];fig,ax=plt.subplots(figsize=(4.5,3.5));ConfusionMatrixDisplay.from_predictions(f.y,f.prediction,display_labels=['Legitimate','Phishing'],ax=ax,cmap='Blues',colorbar=False);save('independent_confusion.png')
 # Visible-text sparsity is a capture/parser caveat, not fabricated missing zeros.
 s=pd.read_pickle(A/'source_features.pkl');t=pd.read_pickle(A/'target_features.pkl');profile=[]
 for label,data in [('source_creator_DOM',s),('target_lxml_HTML',t)]:
  for y,g in data.groupby('y'):profile.append({'source_representation':label,'y':int(y),'n':len(g),'empty_title_fraction':float(g.html_empty_title.mean()),'zero_visible_text_fraction':float(g.html_visible_text_length.eq(0).mean()),'median_element_count':float(g.html_element_count.median())})
 dump(O/'capture_profile.json',profile)
 print('Explainability verified:',spec['family'],error,flush=True)

if __name__=='__main__':main()

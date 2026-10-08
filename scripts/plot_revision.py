"""Plot audited observations with full scales, detail views and explicit baselines."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import precision_recall_curve

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args()
RUN=ROOT/'experiments'/args.run_id;R=RUN/'artifacts';F=RUN/'analysis/figures';F.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':260,'figure.facecolor':'white'})
colors={'Logistic Regression':'#4b4b4b','Decision Tree':'#c06b20','Random Forest':'#17548d',
        'fixed':'#444444','periodic':'#17548d','drift':'#b26016','threshold':'#5c3b86'}
styles={'fixed':':','periodic':'-','drift':'--','threshold':'-.'}
labels={'fixed':'Fixed','periodic':'Periodic retrain','drift':'ADWIN retrain','threshold':'Threshold only'}
def save(fig,name):fig.tight_layout();fig.savefig(F/name,bbox_inches='tight');plt.close(fig)

pred=pd.read_csv(R/'static_predictions.csv',float_precision='round_trip');metrics=pd.read_csv(R/'static_metrics.csv',float_precision='round_trip')
fig,axes=plt.subplots(1,2,figsize=(6.6,3.5));curve_records=[]
for name,style in [('Logistic Regression','--'),('Decision Tree',':'),('Random Forest','-')]:
 d=pred[(pred.model==name)&(pred.seed==17)];p,r,t=precision_recall_curve(d.y,d.probability)
 row=metrics[(metrics.model==name)&(metrics.seed==17)].iloc[0]
 for ax in axes:
  ax.step(r,p,where='post',label=name,color=colors[name],ls=style,lw=1.5)
  ax.scatter([row.recall],[row.precision],s=17,color=colors[name],zorder=5)
 for i in range(len(p)):curve_records.append({'model':name,'precision':float(p[i]),'recall':float(r[i]),'threshold':float(t[i]) if i<len(t) else None})
prevalence=float(d.y.mean());axes[0].axhline(prevalence,color='#888',ls='-.',lw=1,label=f'Class prevalence {prevalence:.4f}')
axes[0].set(xlim=(0,1.005),ylim=(0,1.015),title='(a) Full range',xlabel='Phishing recall',ylabel='Phishing precision')
axes[1].set(xlim=(.97,1.001),ylim=(.94,1.002),title='(b) Detail view',xlabel='Phishing recall',ylabel='Phishing precision')
axes[1].set_xticks([.97,.98,.99,1.0])
axes[0].legend(loc='lower left',fontsize=8.5)
for ax in axes:ax.grid(alpha=.18)
save(fig,'figure_4_1_source_pr.png');pd.DataFrame(curve_records).to_csv(F/'figure_4_1_curve_points.csv',index=False)

external=pd.read_csv(R/'external_predictions.csv',float_precision='round_trip');em=pd.read_csv(R/'external_metrics.csv')
fig,ax=plt.subplots(figsize=(6.4,3.8))
for variant,color,style,label in [('full_30_features','#17548d','-','Full features'),('host_only_7_features','#b26016','--','Host-only diagnostic')]:
 d=external[(external.variant==variant)&(external.seed==17)];p,r,_=precision_recall_curve(d.y,d.probability);row=em[(em.variant==variant)&(em.seed==17)].iloc[0]
 ax.step(r,p,where='post',color=color,ls=style,label=f'{label}: AP {row.average_precision:.4f}')
 ax.scatter(row.recall,row.precision,color=color,s=25,zorder=5)
ax.axhline(d.y.mean(),ls=':',color='#777',label=f'Class prevalence {d.y.mean():.4f}')
ax.set(xlabel='Phishing recall',ylabel='Phishing precision',xlim=(0,1.01),ylim=(0,1.02));ax.legend(loc='lower left',fontsize=9);ax.grid(alpha=.18)
save(fig,'figure_4_2_external_pr.png')

imp=pd.read_csv(R/'shap_importance.csv').head(10).iloc[::-1];fig,ax=plt.subplots(figsize=(6.4,3.8))
ax.barh(imp.feature.str.replace('_',' '),imp.mean_abs_shap,color='#17548d');ax.set_xlabel('Mean absolute SHAP contribution to phishing score')
save(fig,'figure_4_3_shap.png')

windows=pd.read_csv(R/'replay_windows.csv');metas=json.loads((R/'replay_scenarios.json').read_text())
boundaries={m['seed']:m['boundary_index'] for m in metas if m['scenario']=='source_switch'}
w=windows[windows.scenario=='source_switch'].copy();w['relative_index']=w.end_index-w.seed.map(boundaries)
fig,axes=plt.subplots(2,1,figsize=(6.4,5.6),sharex=True)
for delay,ax in zip([0,2],axes):
 for policy in ['fixed','periodic','drift','threshold']:
  g=w[(w.delay_batches==delay)&(w.policy==policy)].groupby('relative_index').f1.agg(['mean','std','count']);g=g[g['count']==3]
  ax.plot(g.index,g['mean'],color=colors[policy],ls=styles[policy],label=labels[policy],lw=1.5)
  ax.fill_between(g.index,g['mean']-g['std'].fillna(0),g['mean']+g['std'].fillna(0),color=colors[policy],alpha=.07)
 ax.axvline(0,color='#777',ls=':',lw=1);ax.set(ylabel='Batch phishing F1',ylim=(.55,1.02),title=f'Label delay = {delay} batches');ax.grid(alpha=.18)
axes[0].legend(fontsize=8,loc='lower left',ncol=2);axes[1].set_xlabel('Observation count relative to the designed source switch')
save(fig,'figure_4_4_source_replay.png')

rm=pd.read_csv(R/'replay_metrics.csv');ag=rm[rm.scenario=='source_switch'].groupby(['delay_batches','policy']).mean(numeric_only=True)
fig,axes=plt.subplots(1,2,figsize=(8,3.5));xs=np.arange(4);policies=['fixed','periodic','drift','threshold']
for delay,offset,alpha in [(0,-.16,1),(2,.16,.45)]:
 for ax,col in zip(axes,['updates','total_fit_seconds']):
  ax.bar(xs+offset,[ag.loc[(delay,p),col] for p in policies],width=.3,color=[colors[p] for p in policies],alpha=alpha,label=f'Delay {delay}')
for ax in axes:ax.set_xticks(xs,['Fixed','Periodic','ADWIN','Threshold'],rotation=18);ax.grid(axis='y',alpha=.15)
axes[0].set_ylabel('Forest refits');axes[1].set_ylabel('Total forest fitting time (s)');axes[1].legend(fontsize=8)
save(fig,'figure_4_5_update_cost.png')

ab=pd.read_csv(R/'exploratory_ablation.csv');fig,ax=plt.subplots(figsize=(6.4,3.5));variants=['Full','No HTTPS','Host only','HTTPS only']
vals=[metrics[metrics.model=='Random Forest'].f1.mean()]+[ab[ab.variant==v].f1.mean() for v in ['without_https','host_only','https_only']]
ax.bar(variants,vals,color=['#17548d','#777','#777','#777']);ax.set(ylabel='Source holdout phishing F1',ylim=(0,1.06));ax.grid(axis='y',alpha=.15)
for i,v in enumerate(vals):ax.text(i,v+.012,f'{v:.4f}',ha='center')
save(fig,'figure_4_6_ablation.png')

# Retain validated simple structure diagram; replace the architecture text to match the revised experiment.
import shutil
shutil.copy2(ROOT/'results/figures/report_structure.png',F/'figure_1_1_structure.png')
fig,ax=plt.subplots(figsize=(8,3.7));ax.axis('off')
nodes=[(.17,.88,'PhiUSIIL source\ntraining and validation'),(.72,.88,'Wangchuk corpus\nquality and overlap audit'),(.17,.55,'Fit classifiers and\nfreeze thresholds'),(.72,.55,'Separate held-out domains\nfrom adaptation pool'),(.17,.2,'Source holdout, SHAP\nand frozen external test'),(.72,.2,'Two-source and stationary\nreplays with delayed labels')]
for x,y,text in nodes:ax.text(x,y,text,ha='center',va='center',fontsize=10,bbox={'boxstyle':'square,pad=.55','fc':'white','ec':'#333'})
for x in [.17,.72]:
 for y in [.74,.4]:ax.annotate('',xy=(x,y-.065),xytext=(x,y+.065),arrowprops={'arrowstyle':'->'})
ax.annotate('',xy=(.35,.23),xytext=(.6,.48),arrowprops={'arrowstyle':'->','ls':'--'});ax.set_xlim(-.03,.98);ax.set_ylim(.02,1)
save(fig,'figure_3_1_architecture.png')
manifest={'run_id':args.run_id,'source_csv_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [R/'static_predictions.csv',R/'external_predictions.csv',R/'replay_windows.csv',R/'replay_metrics.csv']},'figures':[p.name for p in sorted(F.glob('*.png'))],'figure_4_1':'Full-range empirical step PR and labelled zoom; threshold markers from source validation; prevalence baseline; full points exported.'}
(F/'manifest.json').write_text(json.dumps(manifest,indent=2));print('Figures:',F)

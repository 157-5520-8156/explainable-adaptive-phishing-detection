"""Research figures generated from experiment CSV/JSON evidence."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import precision_recall_curve

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';F=R/'figures';F.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':220,'figure.facecolor':'white'})
COLORS={'fixed':'#444444','periodic':'#2563a5','drift':'#b55b16'}

def save(fig,name):
 fig.tight_layout();fig.savefig(F/name,bbox_inches='tight');plt.close(fig)

# This is a scientific flow diagram, not an illustrative image.
fig,ax=plt.subplots(figsize=(8,2.5));ax.axis('off')
labels=['Chapter 1\nProblem and scope','Chapter 2\nPrior research','Chapter 3\nProtocol','Chapter 4\nImplementation\nand evidence','Chapter 5\nConclusions']
for i,l in enumerate(labels):
 x=.08+i*.21
 ax.text(x,.6,l,ha='center',va='center',fontsize=10,bbox={'boxstyle':'square,pad=.5','fc':'white','ec':'#444'})
 if i<4:ax.annotate('',xy=(x+.155,.6),xytext=(x+.075,.6),arrowprops={'arrowstyle':'->','color':'#444'})
ax.set_xlim(-.03,1);ax.text(.48,.05,'Research questions connect the protocol to the measured findings',ha='center',fontsize=10)
save(fig,'report_structure.png')

fig,ax=plt.subplots(figsize=(8,3.2));ax.axis('off')
for x,y,t in [(.12,.8,'Archived URL strings'),(.4,.8,'Deduplicate and\ngroup domains'),(.72,.8,'30 lexical features'),(.35,.38,'Static train / validate / test\nLR, tree and forest'),(.77,.38,'Constructed stream\nFixed / periodic / ADWIN'),(.35,.03,'TreeSHAP attribution\nand source-bias diagnostics'),(.77,.03,'Original predictions,\nlabel arrivals, model updates')]:
 ax.text(x,y,t,ha='center',va='center',fontsize=10,bbox={'boxstyle':'square,pad=.45','fc':'white','ec':'#444'})
for xy,xytext in [((.29,.8),(.24,.8)),((.61,.8),(.53,.8)),((.35,.55),(.65,.7)),((.77,.55),(.77,.7)),((.35,.15),(.35,.27)),((.77,.15),(.77,.27))]:ax.annotate('',xy=xy,xytext=xytext,arrowprops={'arrowstyle':'->','color':'#444'})
save(fig,'architecture.png')

static=pd.read_csv(R/'static_predictions.csv',float_precision='round_trip');metrics=pd.read_csv(R/'static_metrics.csv')
fig,ax=plt.subplots(figsize=(6.5,3.7))
for name,color in [('Logistic Regression','#555'),('Decision Tree','#b55b16'),('Random Forest','#2563a5')]:
 d=static[(static.model==name)&(static.seed==17)];p,re,t=precision_recall_curve(d.y,d.probability)
 ap=float(metrics[(metrics.model==name)&(metrics.seed==17)].average_precision.iloc[0])
 ax.plot(re,p,label=f'{name}  AP={ap:.4f}',color=color,lw=1.5)
ax.set(xlabel='Phishing recall',ylabel='Phishing precision',xlim=(0,1.01),ylim=(0,1.02));ax.legend(loc='lower left',fontsize=9);ax.grid(alpha=.2)
save(fig,'static_pr.png')

fig,ax=plt.subplots(figsize=(6.5,3.8));imp=pd.read_csv(R/'shap_importance.csv').head(10).iloc[::-1]
ax.barh(imp.feature.str.replace('_',' '),imp.mean_abs_shap,color='#2563a5');ax.set_xlabel('Mean absolute SHAP value in probability units')
save(fig,'shap_importance.png')

windows=pd.read_csv(R/'stream_windows.csv');fig,axes=plt.subplots(2,1,figsize=(6.5,5.5),sharex=True)
for delay,ax in zip([0,2],axes):
 for policy in ['fixed','periodic','drift']:
  d=windows[(windows.policy==policy)&(windows.delay_batches==delay)].groupby('end_index').f1.agg(['mean','std'])
  ax.plot(d.index,d['mean'],label=policy.title(),color=COLORS[policy],lw=1.6)
  ax.fill_between(d.index,d['mean']-d['std'].fillna(0),d['mean']+d['std'].fillna(0),color=COLORS[policy],alpha=.12)
 ax.axvline(6000,color='#888',ls='--',lw=1);ax.set(ylabel='Batch phishing F1',ylim=(.58,1.025),title=f'Simulated label delay: {delay} batches');ax.grid(alpha=.2)
axes[0].legend(loc='lower left',ncol=3,fontsize=9);axes[1].set_xlabel('Observation index after warmup');save(fig,'stream_f1.png')

stream=pd.read_csv(R/'stream_metrics.csv');agg=stream.groupby(['delay_batches','policy']).mean(numeric_only=True)
fig,axes=plt.subplots(1,2,figsize=(7,3.5));xs=np.arange(3)
for delay,offset,alpha in [(0,-.16,1),(2,.16,.55)]:
 for ax,col in zip(axes,['updates','total_fit_seconds']):
  vals=[agg.loc[(delay,p),col] for p in ['fixed','periodic','drift']]
  ax.bar(xs+offset,vals,width=.3,color=[COLORS[p] for p in ['fixed','periodic','drift']],alpha=alpha,label=f'Delay {delay}')
for ax in axes:ax.set_xticks(xs,['Fixed','Periodic','ADWIN']);ax.grid(axis='y',alpha=.2)
axes[0].set_ylabel('Retraining count');axes[1].set_ylabel('Total fitting time (seconds)');axes[1].legend(fontsize=9);save(fig,'stream_cost.png')

ab=pd.read_csv(R/'exploratory_ablation.csv');fig,ax=plt.subplots(figsize=(6.5,3.7));names=['Full features','No HTTPS flag','Host only','HTTPS only']
vals=[metrics[metrics.model=='Random Forest'].f1.mean()]+[ab[ab.variant==v].f1.mean() for v in ['without_https','host_only','https_only']]
ax.bar(names,vals,color=['#2563a5','#777','#777','#777']);ax.set(ylim=(0,1.05),ylabel='Test phishing F1');ax.grid(axis='y',alpha=.2)
for i,v in enumerate(vals):ax.text(i,v+.015,f'{v:.4f}',ha='center',fontsize=10)
save(fig,'exploratory_ablation.png')

row=metrics[(metrics.model=='Random Forest')&(metrics.seed==17)].iloc[0];matrix=np.array([[row.tn,row.fp],[row.fn,row.tp]],dtype=int)
fig,ax=plt.subplots(figsize=(4.7,3.8));ax.imshow(matrix,cmap='Greys',vmin=0,vmax=matrix.max());ax.set_xticks([0,1],['Legitimate','Phishing']);ax.set_yticks([0,1],['Legitimate','Phishing']);ax.set(xlabel='Predicted label',ylabel='True label')
for i in range(2):
 for j in range(2):ax.text(j,i,f'{matrix[i,j]:,}',ha='center',va='center',color='white' if matrix[i,j]>matrix.max()/2 else 'black',fontsize=13)
save(fig,'confusion_matrix.png')
print('Saved',len(list(F.glob('*.png'))),'figures')

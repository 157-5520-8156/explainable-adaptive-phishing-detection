"""First-draft experiments with explicit group isolation and label-arrival order."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import platform
import time
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, confusion_matrix, f1_score,
                            precision_recall_curve, precision_score, recall_score,
                            roc_auc_score, accuracy_score)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from river.drift import ADWIN

from features import canonical_url, domain_group, features

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs/experiment.json").read_text())
OUT = Path(os.environ.get("PHISHING_RESULTS_DIR", str(ROOT / "results"))).resolve()

def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False), encoding="utf-8")

def progress(message):
    print(message, flush=True)

def prepare():
    cache = ROOT / "data/processed/url_features.pkl"
    signature={"raw_sha256":hashlib.sha256((ROOT/"data/raw/PhiUSIIL_Phishing_URL_Dataset.csv").read_bytes()).hexdigest(),
               "feature_code_sha256":hashlib.sha256((ROOT/"src/features.py").read_bytes()).hexdigest(),
               "tldextract_version":importlib.metadata.version("tldextract")}
    cache_meta=cache.with_suffix('.manifest.json')
    if cache.exists() and cache_meta.exists():
        cached=json.loads(cache_meta.read_text())
        if cached.get('signature')==signature:
            write_json(OUT/'data_audit.json',cached['audit'])
            return pd.read_pickle(cache)
    raw = pd.read_csv(ROOT / "data/raw/PhiUSIIL_Phishing_URL_Dataset.csv", usecols=["URL", "label"])
    if not set(raw.label.unique()) <= {0, 1}:
        raise ValueError("Unexpected UCI label encoding")
    audit = {"raw_rows": len(raw), "raw_class_counts": {str(k): int(v) for k, v in raw.label.value_counts().items()},
             "raw_label_mapping": "UCI 0=phishing, 1=legitimate; experiment y=1-label",
             "feature_source": "recomputed from raw URL; no released engineered features used",
             "per_row_timestamp_available": False}
    raw["canonical"] = raw.URL.map(canonical_url)
    raw["group"] = raw.URL.map(domain_group)
    valid = raw[raw.canonical.ne("") & raw.group.ne("")].copy()
    audit["invalid_removed"] = len(raw) - len(valid)
    conflicting = valid.groupby("canonical").label.nunique()
    conflicts = set(conflicting[conflicting > 1].index)
    audit["conflicting_url_keys"] = len(conflicts)
    audit["conflicting_rows_removed"] = int(valid.canonical.isin(conflicts).sum())
    valid = valid[~valid.canonical.isin(conflicts)]
    before = len(valid)
    valid = valid.drop_duplicates("canonical").reset_index(drop=True)
    audit["duplicate_rows_removed"] = before - len(valid)
    progress(f"Extracting URL features for {len(valid):,} deduplicated rows")
    matrix = pd.DataFrame([features(u) for u in valid.URL])
    assert np.isfinite(matrix.to_numpy(dtype=float)).all()
    frame = pd.concat([valid[["URL", "canonical", "group"]], matrix], axis=1)
    frame["y"] = 1 - valid.label.to_numpy()
    audit.update({"retained_rows": len(frame), "domain_groups": int(frame.group.nunique()),
                  "retained_phishing": int(frame.y.sum()), "retained_legitimate": int((frame.y==0).sum()),
                  "feature_names": list(matrix.columns), "feature_count": len(matrix.columns),
                  "public_suffix_handling": "tldextract bundled PSL snapshot, private suffixes enabled, network fetch disabled"})
    frame.to_pickle(cache)
    write_json(OUT / "data_audit.json", audit)
    write_json(cache_meta,{'signature':signature,'audit':audit})
    return frame

def metric_row(y, prob, threshold=0.5):
    pred = np.asarray(prob) >= threshold
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {"n": int(len(y)), "phishing": int(np.sum(y)),
            "accuracy": float(accuracy_score(y, pred)),
            "precision": float(precision_score(y, pred, zero_division=0)),
            "recall": float(recall_score(y, pred, zero_division=0)),
            "f1": float(f1_score(y, pred, zero_division=0)),
            "average_precision": float(average_precision_score(y, prob)),
            "roc_auc": float(roc_auc_score(y, prob)) if len(np.unique(y))==2 else None,
            "false_positive_rate": float(fp / (fp+tn)) if fp+tn else 0.0,
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}

def val_threshold(y, prob):
    precision, recall, thresholds = precision_recall_curve(y, prob)
    score = 2*precision[:-1]*recall[:-1] / np.maximum(precision[:-1]+recall[:-1], 1e-12)
    return float(thresholds[np.argmax(score)])

def group_split(frame):
    feature_cols = json.loads((OUT / "data_audit.json").read_text())["feature_names"]
    splitter = StratifiedGroupKFold(n_splits=CONFIG["group_folds"], shuffle=True, random_state=CONFIG["split_seed"])
    assignment = np.full(len(frame), -1)
    for fold, (_, idx) in enumerate(splitter.split(frame[feature_cols], frame.y, frame.group)):
        assignment[idx] = fold
    frame = frame.copy()
    frame["partition"] = np.where(assignment==0, "test", np.where(assignment==1, "validation", "train"))
    groups = {s: set(frame.loc[frame.partition==s, "group"]) for s in ["train", "validation", "test"]}
    overlaps = {f"{a}_{b}": len(groups[a]&groups[b]) for a,b in [("train","test"),("train","validation"),("validation","test")]}
    assert all(v==0 for v in overlaps.values())
    summary = {"seed": CONFIG["split_seed"], "method": "StratifiedGroupKFold 5 folds; test fold 0, validation fold 1, train folds 2-4",
               "group_overlaps": overlaps, "partitions": {}}
    for s in groups:
        f=frame[frame.partition==s]
        summary["partitions"][s] = {"n": len(f), "groups": len(groups[s]), "phishing": int(f.y.sum()), "phishing_fraction": float(f.y.mean())}
    frame[["canonical", "group", "y", "partition"]].to_csv(OUT / "split_manifest.csv", index=False)
    write_json(OUT / "split_summary.json", summary)
    return frame, feature_cols

def static_experiment(frame, cols):
    parts = {s:frame[frame.partition==s] for s in ["train","validation","test"]}
    rows=[]; predictions=[]
    for seed in CONFIG["model_seeds"]:
        learners={
            "Logistic Regression": make_pipeline(StandardScaler(), LogisticRegression(**CONFIG["logistic_regression"], random_state=seed)),
            "Decision Tree": DecisionTreeClassifier(**CONFIG["decision_tree"], random_state=seed),
            "Random Forest": RandomForestClassifier(**CONFIG["random_forest"], random_state=seed),
        }
        for name, model in learners.items():
            start=time.perf_counter(); model.fit(parts["train"][cols],parts["train"].y); fit=time.perf_counter()-start
            vp=model.predict_proba(parts["validation"][cols])[:,1]
            threshold=val_threshold(parts["validation"].y,vp)
            start=time.perf_counter(); prob=model.predict_proba(parts["test"][cols])[:,1]; inference=time.perf_counter()-start
            row={"model":name,"seed":seed,"threshold":threshold,"fit_seconds":fit,"predict_seconds":inference,
                 **metric_row(parts["test"].y.to_numpy(),prob,threshold)}
            rows.append(row)
            prediction=parts["test"][["canonical","group","y"]].copy()
            prediction["model"]=name;prediction["seed"]=seed;prediction["probability"]=prob;prediction["threshold"]=threshold
            predictions.append(prediction)
            progress(f"Static {name} seed={seed}: F1={row['f1']:.4f} AP={row['average_precision']:.4f}, fit={fit:.1f}s")
            if name=="Random Forest":
                joblib.dump(model,OUT/f"rf_seed_{seed}.joblib")
            else:
                joblib.dump(model,OUT/f"{name.lower().replace(' ','_')}_seed_{seed}.joblib")
    pd.DataFrame(rows).to_csv(OUT/"static_metrics.csv",index=False)
    pd.concat(predictions,ignore_index=True).to_csv(OUT/"static_predictions.csv",index=False)
    # Group-bootstrap uncertainty conditional on this fixed split and primary seed.
    primary=predictions[2]
    group_indices=list(primary.groupby("group",sort=False).indices.values())
    rng=np.random.default_rng(CONFIG["split_seed"])
    boot=[]
    y=primary.y.to_numpy();p=primary.probability.to_numpy();t=float(primary.threshold.iloc[0])
    for _ in range(CONFIG["bootstrap_replicates"]):
        idx=np.concatenate([group_indices[i] for i in rng.integers(0,len(group_indices),len(group_indices))])
        m=metric_row(y[idx],p[idx],t)
        boot.append([m["f1"],m["average_precision"],m["recall"],m["false_positive_rate"]])
    arr=np.array(boot)
    write_json(OUT/"static_uncertainty.json",{
        "method":"200 domain-group bootstrap replicates; conditional on fixed split, primary RF seed; not temporal validation",
        "intervals":{k:{"lower":float(np.quantile(arr[:,i],.025)),"upper":float(np.quantile(arr[:,i],.975))} for i,k in enumerate(["f1","average_precision","recall","false_positive_rate"])}
    })

def make_stream(frame, seed):
    cfg=CONFIG["stream"];rng=np.random.default_rng(seed)
    dev=frame[frame.partition=="train"].sample(frac=1,random_state=seed).drop_duplicates("group")
    # One URL per registrable domain; disjoint domains throughout warmup and stream.
    # Class-conditional URL-length strata define an artificial distribution shift.
    q={};phases={"A":[],"B":[]}
    for label in [0,1]:
        sub=dev[dev.y==label]
        lo,hi=sub.url_length.quantile([.4,.6])
        q[str(label)]={"q40":float(lo),"q60":float(hi)}
        short=sub[sub.url_length<=lo];long=sub[sub.url_length>=hi]
        # Ties cannot create overlap even when q40==q60.
        long=long[~long.group.isin(set(short.group))]
        na=(cfg["warmup_size"]+cfg["phase_size"])//2;nb=cfg["phase_size"]//2
        if len(short)<na or len(long)<nb:
            raise RuntimeError(f"Insufficient disjoint domain representatives for class={label}: {len(short)}, {len(long)}")
        phases["A"].append(short.sample(n=na,random_state=seed+label))
        phases["B"].append(long.sample(n=nb,random_state=seed+label))
    a=pd.concat(phases["A"]).sample(frac=1,random_state=seed).reset_index(drop=True)
    b=pd.concat(phases["B"]).sample(frac=1,random_state=seed+1).reset_index(drop=True)
    warm=a.iloc[:cfg["warmup_size"]].copy()
    # Warmup exactly balanced; draw its samples separately to avoid random class-count differences.
    warm=pd.concat([a[a.y==c].iloc[:cfg["warmup_size"]//2] for c in [0,1]]).sample(frac=1,random_state=seed)
    a=a[~a.group.isin(set(warm.group))].sample(frac=1,random_state=seed+2).reset_index(drop=True)
    stream=pd.concat([a.assign(phase="A"),b.assign(phase="B")],ignore_index=True)
    assert stream.group.is_unique and not set(warm.group)&set(stream.group)
    assert not set(stream.group)&set(frame.loc[frame.partition=="test","group"])
    assert len(stream)==2*cfg["phase_size"]
    meta={"seed":seed,"warmup":len(warm),"phase_A":len(a),"phase_B":len(b),"shift_index":len(a),"class_conditional_length_quantiles":q,
          "warmup_phishing":int(warm.y.sum()),"phase_A_phishing":int(a.y.sum()),"phase_B_phishing":int(b.y.sum()),
          "domain_overlap_warmup_stream":0,"stream_repeated_domains":0,
          "interpretation":"Constructed class-balanced short-to-long URL distribution shift; not timestamped concept drift. A fixed conditional label relation is not established."}
    return warm.reset_index(drop=True),stream,meta

def simulate(warm, stream, cols, seed, policy, delay, audit_log=None, model_dir=None):
    cfg=CONFIG["stream"];batchsize=cfg["batch_size"]
    model=RandomForestClassifier(**CONFIG["random_forest"],random_state=seed)
    start=time.perf_counter();model.fit(warm[cols],warm.y);fit_time=time.perf_counter()-start
    if model_dir is not None:
        model_dir=Path(model_dir);model_dir.mkdir(parents=True,exist_ok=True)
        joblib.dump(model,model_dir/'version_0.joblib',compress=3)
    initial_fit=fit_time;predict_time=0.;updates=0;detections=0;last_update=-1000
    threshold=.5;threshold_updates=0;threshold_seconds=0.;detector_seconds=0.;stale_errors_ignored=0
    total_start=time.perf_counter()
    detector=ADWIN(delta=cfg["adwin_delta"])
    observed=warm.copy();pending=[];predictions=[];windows=[];events=[];arrivals=0
    for bno,startidx in enumerate(range(0,len(stream),batchsize)):
        batch=stream.iloc[startidx:startidx+batchsize]
        version=updates
        start=time.perf_counter();prob=model.predict_proba(batch[cols])[:,1];predict_time+=time.perf_counter()-start
        pred=batch[["canonical","group","y","phase"]].copy();pred["probability"]=prob;pred["batch"]=bno;pred["model_version"]=version
        pred['threshold']=threshold
        predictions.append(pred)
        windows.append({"batch":bno,"end_index":startidx+len(batch),"phase":str(batch.phase.iloc[0]),"model_version":version,'threshold':threshold,**metric_row(batch.y.to_numpy(),prob,threshold)})
        pending.append((bno,batch.copy(),prob,version,threshold))
        # Labels for t arrive after prediction at t+delay. Only matured labels are trainable.
        while pending and pending[0][0]+delay<=bno:
            source_batch,known,oldprob,prediction_version,old_threshold=pending.pop(0);arrivals+=1
            observed=pd.concat([observed,known],ignore_index=True).iloc[-cfg["recent_window"]:].copy()
            detected=False
            eligible=policy=='drift' and prediction_version==updates
            if audit_log is not None:audit_log.append({'seed':seed,'policy':policy,'delay_batches':delay,'arrival_batch':bno,'source_batch':source_batch,'prediction_version':prediction_version,'current_version':updates,'n_labels':len(known),'used_by_detector':eligible})
            if policy=='drift' and not eligible:stale_errors_ignored+=len(known)
            if eligible:
                detector_start=time.perf_counter()
                for error in ((oldprob>=old_threshold).astype(int)!=known.y.to_numpy()).astype(int):
                    detector.update(int(error))
                    if detector.drift_detected:
                        detections+=1;detected=True
                detector_seconds+=time.perf_counter()-detector_start
            if policy=='threshold' and arrivals%cfg['periodic_every']==0 and bno+1<len(range(0,len(stream),batchsize)):
                threshold_start=time.perf_counter()
                threshold=val_threshold(observed.y,model.predict_proba(observed[cols])[:,1]);threshold_updates+=1
                threshold_seconds+=time.perf_counter()-threshold_start
            trigger=(policy=="periodic" and arrivals%cfg["periodic_every"]==0) or (policy=="drift" and detected and bno-last_update>=cfg["cooldown_batches"])
            if trigger:
                # Exclude a useless update after the final prediction.
                if bno+1<len(range(0,len(stream),batchsize)):
                    start=time.perf_counter();model=clone(model);model.fit(observed[cols],observed.y);duration=time.perf_counter()-start
                    fit_time+=duration;updates+=1;last_update=bno
                    if model_dir is not None:joblib.dump(model,model_dir/f'version_{updates}.joblib',compress=3)
                    events.append({"after_prediction_batch":bno,"revealed_source_batch":source_batch,"next_model_version":updates,"train_rows":len(observed),"fit_seconds":duration,"trigger":policy})
                    if policy=="drift":detector=ADWIN(delta=cfg["adwin_delta"])
    allpred=pd.concat(predictions,ignore_index=True)
    row={"seed":seed,"policy":policy,"delay_batches":delay,"initial_fit_seconds":initial_fit,"total_fit_seconds":fit_time,
         'threshold_updates':threshold_updates,'threshold_seconds':threshold_seconds,'detector_seconds':detector_seconds,'stale_errors_ignored':stale_errors_ignored,'simulation_seconds_including_initial_fit':time.perf_counter()-total_start+initial_fit,
         "predict_seconds":predict_time,"updates":updates,"detections":detections,"labels_revealed":int(len(warm)+min(arrivals*batchsize,len(stream))),
         **metric_row(allpred.y.to_numpy(),allpred.probability.to_numpy(),allpred.threshold.to_numpy())}
    for phase in ["A","B"]:
        sub=allpred[allpred.phase==phase];m=metric_row(sub.y.to_numpy(),sub.probability.to_numpy(),sub.threshold.to_numpy())
        for key in ["f1","recall","false_positive_rate","average_precision"]:row[f"phase_{phase}_{key}"]=m[key]
    allpred["seed"]=seed;allpred["policy"]=policy;allpred["delay_batches"]=delay
    for item in windows:item.update({"seed":seed,"policy":policy,"delay_batches":delay})
    for item in events:item.update({"seed":seed,"policy":policy,"delay_batches":delay})
    return row,allpred,windows,events

def stream_experiment(frame,cols):
    rows=[];preds=[];wins=[];events=[];metas=[]
    for seed in CONFIG["model_seeds"]:
        warm,stream,meta=make_stream(frame,CONFIG["stream"]["seed"]+seed);meta["model_seed"]=seed;metas.append(meta)
        for delay in CONFIG["stream"]["label_delay_batches"]:
            for policy in ["fixed","periodic","drift"]:
                row,p,w,e=simulate(warm,stream,cols,seed,policy,delay)
                rows.append(row);preds.append(p);wins.extend(w);events.extend(e)
                progress(f"Stream seed={seed} delay={delay} {policy}: F1={row['f1']:.4f} B={row['phase_B_f1']:.4f} updates={row['updates']}")
    pd.DataFrame(rows).to_csv(OUT/"stream_metrics.csv",index=False)
    pd.concat(preds,ignore_index=True).to_csv(OUT/"stream_predictions.csv",index=False)
    pd.DataFrame(wins).to_csv(OUT/"stream_windows.csv",index=False)
    pd.DataFrame(events).to_csv(OUT/"stream_update_events.csv",index=False)
    write_json(OUT/"stream_scenarios.json",metas)

def explain(frame,cols):
    import shap
    from scipy.stats import spearmanr
    cfg=CONFIG["explanation"];seed=CONFIG["model_seeds"][0]
    train=frame[frame.partition=="train"];test=frame[frame.partition=="test"]
    background=train[cols].sample(n=cfg["background_size"],random_state=seed)
    sample=test.sample(n=cfg["evaluation_size"],random_state=seed)
    model=joblib.load(OUT/f"rf_seed_{seed}.joblib")
    explainer=shap.TreeExplainer(model,data=background,feature_perturbation="interventional",model_output="probability")
    start=time.perf_counter();ev=explainer(sample[cols],check_additivity=True);duration=time.perf_counter()-start
    values=ev.values[:,:,1];base=ev.base_values[:,1]
    prob=model.predict_proba(sample[cols])[:,1]
    residual=np.max(np.abs(base+values.sum(axis=1)-prob))
    assert residual<1e-5
    np.savez_compressed(OUT/"shap_values.npz",values=values,base=base,probability=prob,features=np.array(cols),X=sample[cols].to_numpy(),y=sample.y.to_numpy())
    importance=pd.DataFrame({"feature":cols,"mean_abs_shap":np.mean(np.abs(values),axis=0)}).sort_values("mean_abs_shap",ascending=False)
    importance.to_csv(OUT/"shap_importance.csv",index=False)
    stable=sample.iloc[:cfg["stability_size"]]
    base_imp=np.mean(np.abs(values[:len(stable)]),axis=0);top=set(np.argsort(base_imp)[-5:])
    stability=[]
    for otherseed in CONFIG["model_seeds"][1:]:
        other=joblib.load(OUT/f"rf_seed_{otherseed}.joblib")
        e=shap.TreeExplainer(other,data=background,feature_perturbation="interventional",model_output="probability")
        v=e(stable[cols],check_additivity=True).values[:,:,1]
        imp=np.mean(np.abs(v),axis=0)
        stability.append({"reference_seed":seed,"comparison_seed":otherseed,"spearman_global":float(spearmanr(base_imp,imp).statistic),
                          "top5_overlap":len(top&set(np.argsort(imp)[-5:]))/5})
    write_json(OUT/"explanation_audit.json",{"sample_size":len(sample),"background_size":len(background),"seconds":duration,
                "seconds_per_explanation":duration/len(sample),"max_additivity_error":float(residual),"model_output":"phishing probability",
                "stability_sample_size":len(stable),"stability":stability,
                "limitations":"fixed small sampled test set; interventional feature dependence assumption; not causal or a user-trust study; seed comparison on same split"})
    metrics=pd.read_csv(OUT/"static_metrics.csv")
    threshold=float(metrics[(metrics.model=="Random Forest")&(metrics.seed==seed)].threshold.iloc[0])
    alltest=pd.read_csv(OUT/"static_predictions.csv",float_precision='round_trip')
    alltest=alltest[(alltest.model=="Random Forest")&(alltest.seed==seed)]
    alltest["pred"]=(alltest.probability>=threshold).astype(int)
    cases=[]
    for name,condition in [("true_positive",(alltest.y==1)&(alltest.pred==1)),("false_positive",(alltest.y==0)&(alltest.pred==1)),("false_negative",(alltest.y==1)&(alltest.pred==0))]:
        subset=alltest[condition].copy()
        if subset.empty:continue
        subset["distance"]=abs(subset.probability-threshold)
        selected=subset.sort_values("distance",ascending=False).iloc[0]
        case=frame[frame.canonical==selected.canonical].iloc[[0]]
        val=explainer(case[cols],check_additivity=True).values[0,:,1]
        topidx=np.argsort(abs(val))[-5:][::-1]
        # Hash is suitable for the dissertation; no clickable malicious URL is needed.
        cases.append({"type":name,"url_sha256":hashlib.sha256(selected.canonical.encode()).hexdigest(),"truth":int(selected.y),"probability":float(selected.probability),
                      "threshold":threshold,"top_features":[{"feature":cols[i],"value":float(case[cols[i]].iloc[0]),"contribution":float(val[i])} for i in topidx]})
    write_json(OUT/"case_studies.json",cases)
    progress(f"SHAP: {duration:.1f}s, max additivity error={residual:.2e}")

def ablation(frame,cols):
    """Post-hoc exploratory source-bias diagnostic; does not select the main model."""
    parts={s:frame[frame.partition==s] for s in ["train","validation","test"]}
    rows=[]
    diagnostic=[]
    for seed in CONFIG["model_seeds"]:
        for name,selected in [("without_https",[c for c in cols if c!="has_https"]),
                              ("host_only",["host_length","host_digit_ratio","host_hyphens","subdomain_count","suffix_length","host_is_ip","has_punycode"]),
                              ("https_only",["has_https"])]:
            model=RandomForestClassifier(**CONFIG["random_forest"],random_state=seed)
            model.fit(parts["train"][selected],parts["train"].y)
            joblib.dump(model,OUT/f"{name}_seed_{seed}.joblib")
            threshold=val_threshold(parts["validation"].y,model.predict_proba(parts["validation"][selected])[:,1])
            prob=model.predict_proba(parts["test"][selected])[:,1]
            rows.append({"variant":name,"seed":seed,"threshold":threshold,**metric_row(parts["test"].y.to_numpy(),prob,threshold)})
        main=joblib.load(OUT/f"rf_seed_{seed}.joblib")
        m=pd.read_csv(OUT/"static_metrics.csv");t=float(m[(m.model=="Random Forest")&(m.seed==seed)].threshold.iloc[0])
        for https in [0,1]:
            sub=parts["test"][parts["test"].has_https==https]
            diagnostic.append({"seed":seed,"has_https":https,**metric_row(sub.y.to_numpy(),main.predict_proba(sub[cols])[:,1],t)})
    pd.DataFrame(rows).to_csv(OUT/"exploratory_ablation.csv",index=False)
    pd.DataFrame(diagnostic).to_csv(OUT/"https_stratum_metrics.csv",index=False)
    counts=pd.crosstab(frame.y,frame.has_https).to_dict()
    write_json(OUT/"source_bias_audit.json",{
        "https_by_class_counts":{str(k):{str(i):int(v) for i,v in c.items()} for k,c in counts.items()},
        "rows_with_nonempty_path_by_class":{str(c):int(((frame.y==c)&(frame.path_length>0)).sum()) for c in [0,1]},
        "host_only_features":["host_length","host_digit_ratio","host_hyphens","subdomain_count","suffix_length","host_is_ip","has_punycode"],
        "ablation_status":"Exploratory after seeing SHAP and initial holdout results. Not a preregistered confirmatory test; does not change main model.",
        "interpretation":"Strong scheme/label association may reflect collection bias; it is not a universal safety rule."})
    progress("Exploratory HTTPS bias ablation completed")

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--stage",choices=["all","prepare","static","stream","explain","ablation"],default="all");args=parser.parse_args()
    start=time.perf_counter();OUT.mkdir(exist_ok=True)
    write_json(OUT/"environment.json",{"python":platform.python_version(),"platform":platform.platform(),"machine":platform.machine(),
        "packages":{p:importlib.metadata.version(p) for p in ["numpy","pandas","scikit-learn","scipy","shap","river","tldextract","matplotlib"]},
        "config_sha256":hashlib.sha256((ROOT/"configs/experiment.json").read_bytes()).hexdigest()})
    frame=prepare();frame,cols=group_split(frame)
    if args.stage in ["all","static"]:static_experiment(frame,cols)
    if args.stage in ["all","stream"]:stream_experiment(frame,cols)
    if args.stage in ["all","explain"]:explain(frame,cols)
    if args.stage in ["all","ablation"]:ablation(frame,cols)
    write_json(OUT/f"run_{args.stage}.json",{"stage":args.stage,"completed":True,"elapsed_seconds":time.perf_counter()-start})
    progress(f"Completed {args.stage} in {time.perf_counter()-start:.1f}s")

if __name__=="__main__":main()

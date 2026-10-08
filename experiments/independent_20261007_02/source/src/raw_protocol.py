"""Reconstruct archived eligibility roles from published CSVs, never legacy caches."""
from pathlib import Path
import hashlib
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from features import canonical_url, domain_group

RAW_CATALOG = {
    'PhiUSIIL_Phishing_URL_Dataset.csv': {'sha256':'a236549cd369cd80bd478ff8e1779cbf44c58d5c3f79f7a51a1adbed7d06d1c6','dataset_record':'https://archive.ics.uci.edu/dataset/967/phiusil-phishing-url-dataset'},
    'wangchuk_dataset2.csv': {'sha256':'fccce1a99282b3cd8a1fe08fa83350fe44f7afc4c8889a6d0a94ef9c4d7897e3','doi':'10.17632/3jddhy2f6s.1'},
    'hannousse_dataset_B_05_2020.csv': {'sha256':'21093e2902e5441c86a6daf95e86e7c332046e477fdf109a579d7bd81e586d6c','doi':'10.17632/c2gw7fy2j4.3'},
}

def file_sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()

def verify_raw_directory(directory):
    result={}
    for name,spec in RAW_CATALOG.items():
        path=Path(directory)/name
        if not path.is_file():raise FileNotFoundError(f'Required creator CSV missing: {path}')
        actual=file_sha256(path)
        if actual!=spec['sha256']:raise ValueError(f'Raw checksum mismatch: {name}; expected {spec["sha256"]}, got {actual}')
        result[name]={**spec,'bytes':path.stat().st_size}
    return result

def phi_eligible(raw):
    if not set(raw.label.unique()) <= {0,1}:raise ValueError('Unexpected PhiUSIIL labels')
    f=raw[['URL','label']].copy();f['canonical']=f.URL.map(canonical_url);f['group']=f.URL.map(domain_group)
    before=len(f);f=f[f.canonical.ne('') & f.group.ne('')].copy()
    audit={'raw_rows':before,'invalid_removed':before-len(f),'label_mapping':'raw 1 legitimate -> y0; raw0 phishing -> y1'}
    conflicts=f.groupby('canonical').label.nunique();keys=set(conflicts[conflicts>1].index)
    audit['conflicting_rows_removed']=int(f.canonical.isin(keys).sum());f=f[~f.canonical.isin(keys)]
    before=len(f);f=f.drop_duplicates('canonical').reset_index(drop=True);audit['duplicate_rows_removed']=before-len(f)
    f['y']=1-f.label.astype(int);audit['retained_rows']=len(f)
    return f[['URL','canonical','group','y']],audit

def wangchuk_roles(raw,phi,seed=61006,holdout_fraction=.5):
    if list(raw.columns)!=['URL','Label'] or set(raw.Label.unique())!={0,1}:raise ValueError('Unexpected Wangchuk schema/labels')
    f=raw.copy();f['canonical']=f.URL.map(canonical_url);f['group']=f.URL.map(domain_group)
    bad=f.URL.isna()|f.canonical.eq('')|f.group.eq('')|f.URL.str.contains(r'[\s<>\"]',regex=True,na=True)
    audit={'raw_rows':len(f),'quality_excluded':int(bad.sum())};f=f[~bad].copy()
    conflicts=f.groupby('canonical').Label.nunique();keys=set(conflicts[conflicts>1].index)
    audit['conflicting_rows_removed']=int(f.canonical.isin(keys).sum());f=f[~f.canonical.isin(keys)]
    before=len(f);f=f.drop_duplicates('canonical');audit['duplicate_rows_removed']=before-len(f)
    overlap=f.group.isin(set(phi.group));audit['source_domain_overlap_excluded']=int(overlap.sum())
    f=f[~overlap].reset_index(drop=True);f['y']=f.Label.astype(int)
    adaptation,holdout=next(GroupShuffleSplit(n_splits=1,test_size=holdout_fraction,random_state=seed).split(f,groups=f.group))
    f['partition']='adaptation';f.loc[holdout,'partition']='external_holdout'
    if set(f.loc[adaptation,'group']) & set(f.loc[holdout,'group']):raise RuntimeError('External role overlap')
    audit['partitions']={role:{'rows':len(g),'normal':int(g.y.eq(0).sum()),'phishing':int(g.y.sum()),'domains':int(g.group.nunique())} for role,g in f.groupby('partition')}
    return f[['URL','canonical','group','y','partition']],audit

def raw_development_inputs(directory):
    verified=verify_raw_directory(directory)
    phi,phi_audit=phi_eligible(pd.read_csv(Path(directory)/'PhiUSIIL_Phishing_URL_Dataset.csv',usecols=['URL','label']))
    wang,wang_audit=wangchuk_roles(pd.read_csv(Path(directory)/'wangchuk_dataset2.csv'),phi)
    return phi,wang,{'verified_inputs':verified,'phi_eligibility':phi_audit,'wangchuk_legacy_roles':wang_audit,
                     'cached_features_read':False,'legacy_experiment_directory_read':False}

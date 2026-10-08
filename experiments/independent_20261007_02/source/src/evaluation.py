"""Threshold and domain-aware evaluation shared by the redesign experiments."""
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score

def metrics(y, scores, threshold, groups=None):
    y, scores = np.asarray(y), np.asarray(scores)
    pred = scores >= threshold
    tn, fp, fn, tp = map(int, confusion_matrix(y, pred, labels=[0, 1]).ravel())
    out = {'n': len(y), 'normal_n': tn + fp, 'phishing_n': tp + fn,
           'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp,
           'fpr': fp / (fp + tn) if fp + tn else None,
           'recall': tp / (tp + fn) if tp + fn else None,
           'precision': tp / (tp + fp) if tp + fp else 0,
           'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
           'average_precision': float(average_precision_score(y, scores)),
           'roc_auc': float(roc_auc_score(y, scores)) if len(np.unique(y)) == 2 else None}
    if groups is not None:
        f = pd.DataFrame({'group': np.asarray(groups), 'y': y, 'positive': pred})
        out['domain_macro_fpr'] = float(f[f.y == 0].groupby('group').positive.mean().mean())
        out['domain_macro_recall'] = float(f[f.y == 1].groupby('group').positive.mean().mean())
    return out

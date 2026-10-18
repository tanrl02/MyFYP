"""Plot saved tuning aggregates and validation learning curves; no image loading."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
runtime=ROOT/'tmp/baseline-plot-runtime'
if runtime.is_dir():sys.path.insert(0,str(runtime))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'tmp/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    output=ROOT/'docs/ai/efficientnet_tuning'
    summary=json.loads((output/'comparison.json').read_text(encoding='utf-8'))
    rows=summary['trials'];x=np.arange(3)
    fig,(a,b)=plt.subplots(2,1,figsize=(10,8.5),layout='constrained')
    for offset,key,label,colour in ((-.23,'accuracy','Accuracy','#087f8c'),
            (0,'macro_precision','Macro precision','#8551a3'),(.23,'macro_f1','Macro-F1','#bc6a23')):
        values=[r[key] for r in rows]
        bars=a.bar(x+offset,values,.23,label=label,color=colour)
        a.bar_label(bars,labels=[f'{v:.3f}' for v in values],padding=3,fontsize=9)
    a.axhline(.85,color='#ad2634',linestyle='--',label='Accuracy target 0.85')
    a.set(xticks=x,xticklabels=[r['label'] for r in rows],ylim=(0,1.05),ylabel='Score (0–1)',
          title='EfficientNet-B0 tuning — 193 validation images, seed 3403')
    a.legend(loc='upper center',ncol=2,fontsize=9)
    for row in rows:
        parent=ROOT/'docs/ai'/('model_comparison' if row['label']=='Control' else 'efficientnet_tuning')
        history=json.loads((parent/row['run_id']/'epochs.json').read_text())
        b.plot([r['epoch'] for r in history],[r['validation']['accuracy'] for r in history],
               marker='.',label=row['label'])
        b.scatter(row['best_epoch'],row['accuracy'],marker='*',s=90,zorder=3)
    b.axhline(.85,color='#ad2634',linestyle='--')
    b.axvline(3.5,color='grey',linestyle=':')
    b.set(xlabel='Epoch',ylabel='Validation accuracy',ylim=(0,1),xticks=(1,3,6,9,12,15,18),
          title='Learning curves — stars mark selected checkpoints')
    b.legend(ncol=3,fontsize=9,loc='upper center')
    fig.savefig(output/'tuning.png',dpi=180);plt.close(fig)
    print('Saved tuning chart; no test evaluation.')


if __name__=='__main__':main()

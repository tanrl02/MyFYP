"""Plot saved clean metrics, synthetic lighting probes and class recalls."""
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
    output=ROOT/'docs/ai/enhancement'
    summary=json.loads((output/'comparison.json').read_text(encoding='utf-8'))
    rows=summary['initial_runs'];names=['Baseline','Training jitter','Contrast blend'];x=np.arange(3)
    fig,(a,b)=plt.subplots(2,1,figsize=(9,7.5),layout='constrained')
    for offset,key,label,colour in ((-.18,'accuracy','Clean accuracy','#087f8c'),(.18,'macro_f1','Clean macro-F1','#8551a3')):
        values=[r['validation'][key] for r in rows]
        bars=a.bar(x+offset,values,.36,color=colour,label=label)
        a.bar_label(bars,labels=[f'{v:.3f}' for v in values],padding=3)
    a.axhline(.85,color='#ad2634',linestyle='--',label='Accuracy target 0.85')
    a.set(xticks=x,xticklabels=names,ylim=(0,1.05),ylabel='Score (0–1)',title='Enhancement comparison — 193 validation images, seed 3403')
    a.legend(ncol=3,fontsize=9,loc='upper center')
    for offset,factor,label,colour in ((-.18,'0.8','Brightness ×0.8','#bc6a23'),(.18,'1.2','Brightness ×1.2','#457b9d')):
        values=[r['lighting_probes'][factor]['accuracy'] for r in rows]
        bars=b.bar(x+offset,values,.36,color=colour,label=label)
        b.bar_label(bars,labels=[f'{v:.3f}' for v in values],padding=3)
    b.set(xticks=x,xticklabels=names,ylim=(0,1.05),ylabel='Accuracy (0–1)',
          title='Synthetic lighting probes — same cases reused, not a phone benchmark')
    b.legend(ncol=2,loc='upper center')
    fig.savefig(output/'comparison.png',dpi=180);plt.close(fig)
    first=json.loads((output/rows[0]['run_id']/'summary.json').read_text())
    mapping=first['run']['class_to_index']
    labels=[name.replace('_',' ').capitalize()+f" (n={rows[0]['validation']['per_class'][index]['support']})"
            for name,index in sorted(mapping.items(),key=lambda item:item[1])]
    data=np.array([[r['validation']['per_class'][i]['recall'] for r in rows] for i in range(8)])
    fig,ax=plt.subplots(figsize=(8.6,6),layout='constrained')
    im=ax.imshow(data,vmin=0,vmax=1,cmap='viridis',aspect='auto')
    ax.set(xticks=range(3),xticklabels=names,yticks=range(8),yticklabels=labels,
           title='Clean per-condition recall — single development seed')
    for i in range(8):
        for j in range(3):ax.text(j,i,f'{data[i,j]:.3f}',ha='center',va='center',color='white' if data[i,j]<.55 else 'black')
    fig.colorbar(im,ax=ax,label='Recall')
    fig.savefig(output/'class_recall.png',dpi=180);plt.close(fig)
    print('Saved metric/probe and class-recall figures.')


if __name__=='__main__':main()

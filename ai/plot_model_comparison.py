"""Plot aggregate validation-only comparison; no image/model loading."""
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
    output=ROOT/'docs/ai/model_comparison'
    summary=json.loads((output/'comparison.json').read_text())
    rows=summary['matched_runs']
    labels={'efficientnet_b0':'EfficientNet-B0','densenet121':'DenseNet-121','resnet50':'ResNet-50'}
    names=[labels[row['architecture']] for row in rows]
    x=np.arange(len(rows)); width=.23
    fig,ax=plt.subplots(figsize=(9,5.3),layout='constrained')
    for offset,key,label,colour in ((-1,'accuracy','Accuracy','#087f8c'),(0,'macro_precision','Macro precision','#8551a3'),(1,'macro_f1','Macro-F1','#bc6a23')):
        values=[row[key] for row in rows]
        bars=ax.bar(x+offset*width,values,width,label=label,color=colour)
        ax.bar_label(bars,labels=[f'{value:.3f}' for value in values],padding=3,fontsize=9)
    ax.axhline(.85,color='#ad2634',linestyle='--',label='Accuracy target 0.85')
    ax.set(xticks=x,xticklabels=names,ylim=(0,1.02),ylabel='Score (0–1)',title='Matched model comparison — 193 validation images')
    ax.legend(loc='upper center',ncol=2,fontsize=9)
    fig.savefig(output/'metrics.png',dpi=180);plt.close(fig)
    class_names=[name.replace('_',' ').capitalize() for name,index in sorted(summary['class_to_index'].items(),key=lambda item:item[1])]
    data=np.array([[row['per_class'][index]['f1'] for row in rows] for index in range(8)])
    fig,ax=plt.subplots(figsize=(8.4,6),layout='constrained')
    im=ax.imshow(data,vmin=0,vmax=1,cmap='viridis',aspect='auto')
    ax.set(xticks=range(len(names)),xticklabels=names,yticks=range(8),yticklabels=class_names,
           title='Per-condition F1 — validation only, single seed')
    for i in range(8):
        for j in range(len(rows)):ax.text(j,i,f'{data[i,j]:.3f}',ha='center',va='center',color='white' if data[i,j]<.55 else 'black')
    fig.colorbar(im,ax=ax,label='F1 (0–1)')
    fig.savefig(output/'per_class_f1.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5.3),layout='constrained')
    for row,name in zip(rows,names):
        history=json.loads((output/row['run_id']/'epochs.json').read_text())
        ax.plot([r['epoch'] for r in history],[r['validation']['accuracy'] for r in history],
                marker='.',label=name)
        ax.scatter(row['best_epoch'],row['accuracy'],s=80,marker='*',zorder=3)
    ax.axhline(summary['protocol']['accuracy_target'],color='#ad2634',linestyle='--',label='Accuracy target 0.85')
    ax.axvline(summary['protocol']['warmup_epochs']+.5,color='grey',linestyle=':',label='Full fine-tuning begins')
    ax.set(xlabel='Epoch',ylabel='Validation accuracy',ylim=(0,1),xticks=(1,3,6,9,12,15,18),
           title='Learning curves — stars mark selected checkpoints')
    ax.legend(fontsize=9,ncol=2)
    fig.savefig(output/'learning_curves.png',dpi=180);plt.close(fig)
    print('Saved aggregate metrics, per-class F1 and learning curves; test set not evaluated.')


if __name__=='__main__':main()

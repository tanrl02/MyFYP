"""Plot measured prediction preservation and storage trade-offs; no photos."""
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
from matplotlib.ticker import MaxNLocator
import numpy as np


def main():
    folder=ROOT/'docs/ai/upload_recipes'
    data=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    names=data['protocol']['recipes'];x=np.arange(len(names))
    labels=['Current JPEG85','JPEG95 default','JPEG95 4:4:4','Lossless PNG']
    fig,(a,b)=plt.subplots(2,1,figsize=(9,7.2),layout='constrained')
    for i,(run,label,colour) in enumerate(zip(data['runs'],['Full-feature B0','Partial-freezing B0'],['#087f8c','#8551a3'])):
        values=[run['recipes'][name]['predictions_changed'] for name in names]
        bars=a.bar(x+(i-.5)*.32,values,.32,color=colour,label=label)
        a.bar_label(bars,padding=3)
    a.set(xticks=x,xticklabels=labels,ylabel='Changed predictions / 193',ylim=(0,max(
        r['recipes'][n]['predictions_changed'] for r in data['runs'] for n in names)+3),
        title='Upload recipe comparison — fixed checkpoints, validation only')
    a.yaxis.set_major_locator(MaxNLocator(integer=True));a.legend(loc='upper right')
    sizes=[data['storage'][name]['mean_bytes']/1024 for name in names]
    bars=b.bar(x,sizes,color='#bc6a23')
    b.bar_label(bars,labels=[f'{v:.1f}' for v in sizes],padding=3)
    b.set(xticks=x,xticklabels=labels,ylabel='Mean encoded image size (KiB)',ylim=(0,max(sizes)*1.18),
          title='Storage cost — prediction preservation does not establish clinical reliability')
    fig.savefig(folder/'comparison.png',dpi=180);plt.close(fig)
    print('Saved prediction/storage chart.')


if __name__=='__main__':main()

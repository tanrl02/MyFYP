"""Render validation figures from saved aggregates; does not load any images/models."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
local_plot_runtime = ROOT / 'tmp/baseline-plot-runtime'
if local_plot_runtime.is_dir(): sys.path.insert(0, str(local_plot_runtime))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'tmp/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    output = ROOT / 'docs/ai/baseline_results'
    summary = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
    epochs = json.loads((output / 'epochs.json').read_text(encoding='utf-8'))
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    x = [row['epoch'] for row in epochs]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    axes[0].plot(x, [row['validation_macro_f1'] for row in epochs], marker='o', color='#087f8c', label='Macro-F1')
    axes[0].plot(x, [row['validation_accuracy'] for row in epochs], marker='s', color='#7756a6', label='Accuracy')
    best = summary['best_epoch']
    axes[0].scatter([best], [summary['validation']['macro_f1']], color='#e68613', s=110, zorder=4, label=f'Selected epoch {best}')
    axes[0].set(ylabel='Validation score', xlabel='Epoch', ylim=(0, 1), xticks=x)
    axes[0].legend(frameon=False, loc='lower right'); axes[0].grid(alpha=.2)
    axes[1].plot(x, [row['validation_loss'] for row in epochs], marker='o', color='#087f8c')
    axes[1].set(ylabel='Unweighted cross-entropy', xlabel='Epoch', xticks=x)
    axes[1].grid(alpha=.2)
    fig.suptitle('EfficientNet-B0 frozen-head baseline | Validation only (193 images)', fontweight='bold')
    fig.savefig(output / 'learning_curve.png', dpi=160); plt.close(fig)
    mapping = summary['class_to_index']
    names = [label.replace('_', ' ').title().replace('Seborrheic Dermatitis', 'Seborrhoeic dermatitis') for label, _ in sorted(mapping.items(), key=lambda item: item[1])]
    matrix = np.array(summary['validation']['confusion_matrix'])
    fig, axis = plt.subplots(figsize=(9, 8), layout='constrained')
    image = axis.imshow(matrix, cmap='Blues', vmin=0)
    axis.set(xticks=np.arange(len(names)), yticks=np.arange(len(names)), xticklabels=names, yticklabels=names,
             xlabel='Predicted label', ylabel='Source label')
    plt.setp(axis.get_xticklabels(), rotation=40, ha='right', rotation_mode='anchor')
    for i in range(len(names)):
        for j in range(len(names)):
            axis.text(j, i, str(matrix[i, j]), ha='center', va='center', color='white' if matrix[i, j] > matrix.max() * .5 else '#17212b')
    axis.set_title(f"Validation confusion matrix | Selected epoch {best}\nCounts from 193 images; test set not evaluated", pad=14)
    fig.colorbar(image, ax=axis, shrink=.8, label='Image count')
    fig.savefig(output / 'validation_confusion.png', dpi=160); plt.close(fig)
    print('Saved learning_curve.png and validation_confusion.png')


if __name__ == '__main__':
    main()

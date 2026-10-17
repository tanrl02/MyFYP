"""Verify a completed baseline checkpoint and export validation-only evidence."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import torch
from torch.utils.data import DataLoader

try:
    from ai.baseline_data import ROOT, load_baseline_data
    from ai.train_baseline import FrozenImages, build_model, evaluate, features_digest, seed_everything
except ModuleNotFoundError:
    from baseline_data import ROOT, load_baseline_data
    from train_baseline import FrozenImages, build_model, evaluate, features_digest, seed_everything
from torchvision.models import EfficientNet_B0_Weights


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', default='efficientnet-b0-baseline-v1')
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    args = parser.parse_args()
    if not args.run_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in args.run_id):
        raise ValueError('Invalid run ID')
    folder = ROOT / 'ai/runs' / args.run_id
    complete = json.loads((folder / 'complete.json').read_text(encoding='utf-8'))
    history = json.loads((folder / 'history.json').read_text(encoding='utf-8'))
    run = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
    config = run['config']
    if run['mode'] != 'train' or len(history) != config['epochs'] or complete['epochs'] != len(history):
        raise ValueError('Run is not a completed full baseline')
    if [row['epoch'] for row in history] != list(range(1, len(history) + 1)):
        raise ValueError('Epoch sequence is incomplete')
    if complete['test_evaluated'] is not False or run['test_images_evaluated'] != 0:
        raise ValueError('This analysis requires an untouched test evaluation stage')
    best = max(history, key=lambda row: (row['validation']['macro_f1'], -row['validation']['loss']))
    checkpoint_path = folder / 'best.pt'
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
    if checkpoint['epoch'] != best['epoch'] or checkpoint['validation'] != best['validation'] or checkpoint['metadata'] != run:
        raise ValueError('Saved checkpoint does not match the logged selection rule')
    mapping, rows, dataset = load_baseline_data(config)
    seed_everything(config['seed'], config['cpu_threads'])
    torch.hub.set_dir(str(ROOT / 'ai/weights'))
    weights = EfficientNet_B0_Weights.IMAGENET1K_V1
    original_path = Path(torch.hub.get_dir()) / 'checkpoints' / Path(weights.url).name
    if not original_path.exists() or hashlib.sha256(original_path.read_bytes()).hexdigest() != run['weight_sha256']:
        raise ValueError('Original pretrained checkpoint missing or changed; no download in verification')
    model = build_model(len(mapping))
    original_features = features_digest(model)
    original_head = model.classifier[-1].weight.detach().clone()
    model.load_state_dict(checkpoint['model_state_dict'], strict=True)
    if original_features != features_digest(model): raise ValueError('Frozen feature state changed during baseline')
    if torch.equal(original_head, model.classifier[-1].weight): raise ValueError('Classifier did not learn any update')
    device = torch.device(args.device)
    model.to(device)
    loader = DataLoader(FrozenImages(rows['val'], weights.transforms()), batch_size=config['batch_size'], shuffle=False, num_workers=0)
    reproduced = evaluate(model, loader, device, len(mapping))
    for key in ('accuracy', 'macro_f1', 'confusion_matrix', 'per_class'):
        if reproduced[key] != best['validation'][key]: raise ValueError(f'Validation replay differs: {key}')
    if not math.isclose(reproduced['loss'], best['validation']['loss'], rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError('Validation replay loss differs')
    names = {index: name for name, index in mapping.items()}
    class_metrics = [{'class_name': names[row['class_index']], **row} for row in reproduced['per_class']]
    summary = {'verified_on': '2026-10-18', 'run_id': args.run_id, 'dataset_version': config['dataset_version'],
               'architecture': config['architecture'], 'stage': config['training_stage'],
               'completed_epochs': len(history), 'best_epoch': best['epoch'],
               'training_images': len(rows['train']), 'validation_images': len(rows['val']), 'test_images_evaluated': 0,
               'validation': {**reproduced, 'per_class': class_metrics},
               'first_epoch_validation': history[0]['validation'], 'last_epoch_validation': history[-1]['validation'],
               'recorded_epoch_seconds': sum(row['seconds'] for row in history),
               'class_to_index': mapping, 'config': config, 'device': run['device'], 'gpu': run['gpu'],
               'runtime': {key: run[key] for key in ('python', 'torch', 'torchvision', 'numpy', 'pillow', 'cuda_runtime')},
               'checkpoint': checkpoint_path.relative_to(ROOT).as_posix(),
               'checkpoint_sha256': hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
               'pretrained_weight_sha256': run['weight_sha256'], 'feature_state_sha256': original_features,
               'checkpoint_selection_verified': True, 'validation_replay_verified': True,
               'frozen_features_including_batchnorm_unchanged': True, 'classifier_updated': True,
               'clinical_validity_established': False, 'fine_tuning_completed': False}
    output = ROOT / 'docs/ai/baseline_results'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    with (output / 'per_class.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(class_metrics[0])); writer.writeheader(); writer.writerows(class_metrics)
    epochs = [{'epoch': row['epoch'], 'validation_macro_f1': row['validation']['macro_f1'],
               'validation_accuracy': row['validation']['accuracy'], 'validation_loss': row['validation']['loss'],
               'training_weighted_mean_batch_loss': row['training_weighted_mean_batch_loss'], 'seconds': row['seconds']} for row in history]
    (output / 'epochs.json').write_text(json.dumps(epochs, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'best_epoch': summary['best_epoch'], 'validation_macro_f1': reproduced['macro_f1'],
                      'validation_accuracy': reproduced['accuracy'], 'validation_replay_verified': True,
                      'test_images_evaluated': 0, 'output': str(output)}, indent=2))


if __name__ == '__main__':
    main()

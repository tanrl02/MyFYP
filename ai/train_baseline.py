"""Explicit smoke/train modes for a frozen-head ImageNet transfer baseline.

Never evaluates test images. Smoke mode discards its one-step model.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import random
import sys
import time

os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import numpy as np
from PIL import Image, ImageOps
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
import torchvision
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0

try:
    from ai.baseline_data import ROOT, classification_metrics, load_baseline_data, training_class_weights
except ModuleNotFoundError:
    from baseline_data import ROOT, classification_metrics, load_baseline_data, training_class_weights


class FrozenImages(Dataset):
    def __init__(self, rows, transform): self.rows, self.transform = rows, transform
    def __len__(self): return len(self.rows)
    def __getitem__(self, index):
        row = self.rows[index]
        content = (ROOT / row['local_path']).read_bytes()
        if hashlib.sha256(content).hexdigest() != row['sha256']:
            raise ValueError('Image changed since frozen manifest')
        with Image.open(io.BytesIO(content)) as image:
            tensor = self.transform(ImageOps.exif_transpose(image).convert('RGB'))
        return tensor, int(row['class_index'])


def seed_everything(seed, cpu_threads):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(cpu_threads)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)


def build_model(class_count, pretrained=True):
    weights = EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
    model = efficientnet_b0(weights=weights)
    model.features.requires_grad_(False)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, class_count)
    return model


def train_mode(model):
    model.train()
    model.features.eval()  # Freeze BatchNorm buffers and stochastic depth as well as gradients.


def features_digest(model):
    digest = hashlib.sha256()
    for name, tensor in model.features.state_dict().items():
        digest.update(name.encode()); digest.update(tensor.detach().cpu().numpy().tobytes())
    return digest.hexdigest()


def evaluate(model, loader, device, class_count):
    model.eval(); targets, predictions, loss_sum = [], [], 0.0
    with torch.inference_mode():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            logits = model(images)
            if not torch.isfinite(logits).all(): raise ValueError('Nonfinite validation logits')
            loss_sum += nn.functional.cross_entropy(logits, labels, reduction='sum').item()
            targets.extend(labels.cpu().tolist()); predictions.extend(logits.argmax(1).cpu().tolist())
    return {**classification_metrics(targets, predictions, class_count), 'loss': loss_sum / len(targets)}


def one_per_class(rows):
    chosen = {}
    for row in rows: chosen.setdefault(int(row['class_index']), row)
    return [chosen[index] for index in sorted(chosen)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('smoke', 'train'), required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    parser.add_argument('--download-weights', action='store_true')
    args = parser.parse_args()
    if not args.run_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in args.run_id):
        raise ValueError('Use a lowercase run identifier with digits, hyphens or underscores')
    config = json.loads((ROOT / 'ai/baseline_config.json').read_text(encoding='utf-8'))
    if (config['architecture'], config['weights'], config['training_stage']) != (
        'efficientnet_b0', 'EfficientNet_B0_Weights.IMAGENET1K_V1', 'frozen_feature_extractor_train_classifier_only'):
        raise ValueError('This runner supports only the configured frozen-head EfficientNet-B0 baseline')
    mapping, rows, dataset_lock = load_baseline_data(config)
    output = ROOT / 'ai/runs' / args.run_id
    if output.exists(): raise ValueError('Run exists; choose a new run ID')
    device = torch.device('cuda' if args.device == 'auto' and torch.cuda.is_available() else 'cpu' if args.device == 'auto' else args.device)
    if device.type == 'cuda' and not torch.cuda.is_available(): raise ValueError('CUDA unavailable')
    torch.hub.set_dir(str(ROOT / 'ai/weights'))
    weights = EfficientNet_B0_Weights.IMAGENET1K_V1
    weight_path = Path(torch.hub.get_dir()) / 'checkpoints' / Path(weights.url).name
    if not weight_path.exists() and not args.download_weights:
        raise ValueError('Pretrained weights missing; rerun with --download-weights')
    if weight_path.exists() and not hashlib.sha256(weight_path.read_bytes()).hexdigest().startswith('7f5810bc'):
        raise ValueError('Cached pretrained checkpoint failed the official hash-prefix check')
    seed_everything(config['seed'], config['cpu_threads'])
    model = build_model(len(mapping)).to(device)
    weight_sha = hashlib.sha256(weight_path.read_bytes()).hexdigest()
    if not weight_sha.startswith('7f5810bc'): raise ValueError('Pretrained checkpoint hash differs from official URL prefix')
    transform = weights.transforms()
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(parameters, lr=config['learning_rate'], weight_decay=config['weight_decay'])
    criterion = nn.CrossEntropyLoss(weight=torch.tensor(training_class_weights(rows['train'], len(mapping)), device=device))
    output.mkdir(parents=True)
    metadata = {'mode': args.mode, 'config': config, 'class_to_index': mapping, 'dataset_lock': dataset_lock,
                'device': str(device), 'gpu': torch.cuda.get_device_name(0) if device.type == 'cuda' else None,
                'torch': str(torch.__version__), 'torchvision': str(torchvision.__version__), 'numpy': np.__version__,
                'pillow': Image.__version__, 'weight_url': weights.url, 'weight_sha256': weight_sha,
                'python': sys.version, 'cuda_runtime': torch.version.cuda,
                'preprocessing': repr(transform), 'parameters': sum(p.numel() for p in model.parameters()),
                'trainable_parameters': sum(p.numel() for p in parameters), 'test_images_evaluated': 0}
    (output / 'run.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: metadata[key] for key in ('mode', 'device', 'gpu', 'parameters', 'trainable_parameters')}, indent=2), flush=True)
    if args.mode == 'smoke':
        features_before = features_digest(model)
        head_before = model.classifier[-1].weight.detach().clone()
        images, labels = next(iter(DataLoader(FrozenImages(one_per_class(rows['train']), transform), batch_size=len(mapping))))
        train_mode(model); optimizer.zero_grad(set_to_none=True)
        logits = model(images.to(device)); loss = criterion(logits, labels.to(device))
        if not torch.isfinite(loss): raise ValueError('Nonfinite smoke loss')
        loss.backward(); optimizer.step()
        model.eval()
        val_images, _ = next(iter(DataLoader(FrozenImages(one_per_class(rows['val']), transform), batch_size=len(mapping))))
        with torch.inference_mode(): validation_shape = list(model(val_images.to(device)).shape)
        checks = {'purpose': 'Pipeline smoke check, not measured model performance', 'training_images': len(mapping),
                  'validation_images': len(mapping), 'test_images': 0, 'logits_shape': list(logits.shape),
                  'validation_logits_shape': validation_shape, 'finite_loss': True,
                  'features_unchanged': features_before == features_digest(model),
                  'head_updated': not torch.equal(head_before, model.classifier[-1].weight.detach()),
                  'checkpoint_saved': False}
        if not checks['features_unchanged'] or not checks['head_updated'] or validation_shape != [len(mapping), len(mapping)]:
            raise ValueError('Smoke invariants failed')
        (output / 'smoke.json').write_text(json.dumps(checks, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(checks, indent=2)); return
    generator = torch.Generator().manual_seed(config['seed'])
    train_loader = DataLoader(FrozenImages(rows['train'], transform), batch_size=config['batch_size'], shuffle=True,
                              generator=generator, num_workers=config['num_workers'])
    val_loader = DataLoader(FrozenImages(rows['val'], transform), batch_size=config['batch_size'], shuffle=False,
                            num_workers=config['num_workers'])
    best, history = (-1.0, float('-inf')), []
    for epoch in range(1, config['epochs'] + 1):
        started = time.monotonic(); train_mode(model); loss_sum = batches = 0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True); loss = criterion(model(images), labels)
            if not torch.isfinite(loss): raise ValueError('Nonfinite training loss')
            loss.backward(); optimizer.step(); loss_sum += loss.item(); batches += 1
        validation = evaluate(model, val_loader, device, len(mapping))
        record = {'epoch': epoch, 'training_weighted_mean_batch_loss': loss_sum / batches,
                  'validation': validation, 'seconds': time.monotonic() - started}
        history.append(record)
        score = (validation['macro_f1'], -validation['loss'])
        if score > best:
            best = score
            torch.save({'model_state_dict': model.state_dict(), 'epoch': epoch, 'metadata': metadata, 'validation': validation}, output / 'best.pt')
        (output / 'history.json').write_text(json.dumps(history, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'epoch': epoch, 'validation_macro_f1': validation['macro_f1'], 'validation_loss': validation['loss']}), flush=True)
    (output / 'complete.json').write_text(json.dumps({'epochs': len(history), 'best_validation_macro_f1': best[0], 'test_evaluated': False}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

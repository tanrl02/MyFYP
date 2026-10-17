"""Frozen-data validation and metrics without importing the training libraries."""
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text_digest(content):
    return hashlib.sha256(content.replace(b'\r\n', b'\n')).hexdigest()


def load_baseline_data(config, root=ROOT):
    root = Path(root)
    folder = root / 'ai/manifests' / config['dataset_version']
    locked_bytes = (folder / 'dataset.json').read_bytes()
    if text_digest(locked_bytes) != config['dataset_lock_sha256_lf']:
        raise ValueError('Frozen dataset metadata changed')
    locked = json.loads(locked_bytes)
    if locked['dataset_version'] != config['dataset_version']:
        raise ValueError('Wrong frozen version')
    for name, expected in locked['manifest_sha256_normalised_lf'].items():
        if text_digest((folder / name).read_bytes()) != expected:
            raise ValueError(f'Frozen manifest changed: {name}')
    mapping = json.loads((folder / 'class_to_index.json').read_text(encoding='utf-8'))
    if sorted(mapping.values()) != list(range(len(mapping))):
        raise ValueError('Invalid output class indices')
    splits, seen = {}, set()
    # Test CSV integrity is checked above; its rows/pixels are not loaded for fitting.
    for split in ('train', 'val'):
        rows = list(csv.DictReader(io.StringIO((folder / f'{split}.csv').read_text(encoding='utf-8'))))
        if len(rows) != locked['split_counts'][split]: raise ValueError('Frozen count mismatch')
        for row in rows:
            if row['partition'] != split or mapping.get(row['target_class']) != int(row['class_index']):
                raise ValueError('Wrong frozen partition or class index')
            if row['md5hash'] in seen: raise ValueError('Repeated image across training/validation')
            seen.add(row['md5hash'])
            path = (root / row['local_path']).resolve()
            if not path.is_relative_to((root / 'ai/data/fitzpatrick17k/images').resolve()):
                raise ValueError('Image outside the expected data directory')
        if set(row['target_class'] for row in rows) != set(mapping): raise ValueError('Missing class')
        splits[split] = rows
    return mapping, splits, locked


def training_class_weights(rows, class_count):
    counts = Counter(int(row['class_index']) for row in rows)
    if set(counts) != set(range(class_count)): raise ValueError('Missing training class')
    return [len(rows) / (class_count * counts[index]) for index in range(class_count)]


def classification_metrics(targets, predictions, class_count):
    if len(targets) != len(predictions) or not targets: raise ValueError('Invalid prediction count')
    confusion = [[0] * class_count for _ in range(class_count)]
    for target, predicted in zip(targets, predictions):
        if not 0 <= target < class_count or not 0 <= predicted < class_count:
            raise ValueError('Invalid class index')
        confusion[target][predicted] += 1
    per_class = []
    for index in range(class_count):
        tp = confusion[index][index]
        support = sum(confusion[index])
        predicted_total = sum(row[index] for row in confusion)
        precision = tp / predicted_total if predicted_total else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class.append({'class_index': index, 'support': support, 'precision': precision, 'recall': recall, 'f1': f1})
    return {'accuracy': sum(confusion[i][i] for i in range(class_count)) / len(targets),
            'macro_f1': sum(row['f1'] for row in per_class) / class_count,
            'confusion_matrix': confusion, 'per_class': per_class}

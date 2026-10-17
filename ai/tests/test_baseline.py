import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

from ai.baseline_data import ROOT, classification_metrics, load_baseline_data, text_digest, training_class_weights

HAS_TORCH = importlib.util.find_spec('torch') is not None
if HAS_TORCH:
    import torch
    from ai.train_baseline import build_model, features_digest, seed_everything, train_mode


class BaselineDataTests(unittest.TestCase):
    def test_macro_f1_includes_failed_minority_class(self):
        result = classification_metrics([0, 0, 1, 1], [0, 0, 0, 0], 2)
        self.assertEqual(result['accuracy'], 0.5)
        self.assertAlmostEqual(result['macro_f1'], 1 / 3)
        self.assertEqual(result['per_class'][1]['recall'], 0)
        self.assertEqual(result['confusion_matrix'], [[2, 0], [2, 0]])

    def test_metrics_reject_invalid_predictions(self):
        for targets, predictions in [([], []), ([0], []), ([0], [2])]:
            with self.assertRaises(ValueError): classification_metrics(targets, predictions, 2)

    def test_weights_come_from_training_frequency(self):
        rows = [{'class_index': '0'}] * 3 + [{'class_index': '1'}]
        self.assertEqual(training_class_weights(rows, 2), [2 / 3, 2.0])
        with self.assertRaises(ValueError): training_class_weights(rows, 3)

    def test_frozen_manifest_integrity_and_test_rows_not_used(self):
        temporary_root = ROOT / 'tmp/baseline-tests'
        temporary_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as temporary:
            root = Path(temporary)
            folder = root / 'ai/manifests/example'
            folder.mkdir(parents=True)
            files = {'class_to_index.json': json.dumps({'a': 0, 'b': 1}).encode(), 'test.csv': b'not-read-as-training-data\n', 'excluded.csv': b'excluded\n'}
            for split in ('train', 'val'):
                handle = io.StringIO(newline='')
                writer = csv.DictWriter(handle, fieldnames=['md5hash', 'partition', 'target_class', 'class_index', 'local_path'])
                writer.writeheader()
                for index, label in enumerate(('a', 'b')):
                    writer.writerow({'md5hash': f'{split}-{label}', 'partition': split, 'target_class': label, 'class_index': index,
                                     'local_path': f'ai/data/fitzpatrick17k/images/{split}-{label}.jpg'})
                files[split + '.csv'] = handle.getvalue().encode()
            for name, content in files.items(): (folder / name).write_bytes(content)
            lock = {'dataset_version': 'example', 'split_counts': {'train': 2, 'val': 2},
                    'manifest_sha256_normalised_lf': {name: text_digest(content) for name, content in files.items()}}
            lock_bytes = json.dumps(lock).encode()
            (folder / 'dataset.json').write_bytes(lock_bytes)
            config = {'dataset_version': 'example', 'dataset_lock_sha256_lf': text_digest(lock_bytes)}
            mapping, rows, _ = load_baseline_data(config, root)
            self.assertEqual(mapping, {'a': 0, 'b': 1})
            self.assertEqual(set(rows), {'train', 'val'})
            (folder / 'train.csv').write_bytes(files['train.csv'] + b'changed\n')
            with self.assertRaises(ValueError): load_baseline_data(config, root)


@unittest.skipUnless(HAS_TORCH, 'Training checks require .venv-ai')
class BaselineModelTests(unittest.TestCase):
    def test_frozen_features_including_batchnorm_buffers_stay_unchanged(self):
        seed_everything(3403, 2)
        model = build_model(8, pretrained=False)
        before = features_digest(model)
        head = model.classifier[-1].weight.detach().clone()
        optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=0.01)
        train_mode(model)
        self.assertFalse(model.features.training)
        self.assertTrue(model.classifier.training)
        output = model(torch.randn(2, 3, 64, 64))
        torch.nn.functional.cross_entropy(output, torch.tensor([0, 7])).backward()
        optimizer.step()
        self.assertEqual(tuple(output.shape), (2, 8))
        self.assertEqual(before, features_digest(model))
        self.assertFalse(torch.equal(head, model.classifier[-1].weight))
        self.assertTrue(all(p.grad is None for p in model.features.parameters()))

    def test_seed_reproduces_new_output_layer(self):
        seed_everything(3403, 2)
        first = build_model(8, pretrained=False).classifier[-1].weight.detach().clone()
        seed_everything(3403, 2)
        second = build_model(8, pretrained=False).classifier[-1].weight.detach().clone()
        self.assertTrue(torch.equal(first, second))


if __name__ == '__main__':
    unittest.main()

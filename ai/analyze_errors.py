"""Validation error and train-image framing audit; never trains or reads test pixels."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
import random
from urllib.parse import urlparse

try:
    from ai.train_baseline import FrozenImages, build_model, seed_everything, torch, Image, ImageOps
    from ai.baseline_data import ROOT, load_baseline_data, classification_metrics
except ModuleNotFoundError:
    from train_baseline import FrozenImages, build_model, seed_everything, torch, Image, ImageOps
    from baseline_data import ROOT, load_baseline_data, classification_metrics
from PIL import ImageDraw
from torch.utils.data import DataLoader
from torchvision import transforms
from torchvision.models import EfficientNet_B0_Weights

FOCUS = ('eczema', 'allergic_contact_dermatitis', 'seborrheic_dermatitis')
SHORT = {'eczema': 'ECZ', 'allergic_contact_dermatitis': 'ACD', 'seborrheic_dermatitis': 'SD',
         'psoriasis': 'PSO', 'acne': 'ACNE', 'folliculitis': 'FOL', 'urticaria': 'URT', 'scabies': 'SCA'}


def retained_frame(row):
    width, height = int(row['width']), int(row['height'])
    # Original validation preprocessing: shorter edge 256, then centre crop 224.
    long_edge = int(256 * max(width, height) / min(width, height))
    return 224 * 224 / (256 * long_edge)


def sheet(selected, local):
    for page, start in enumerate(range(0, len(selected), 18), 1):
        batch = selected[start:start + 18]
        canvas = Image.new('RGB', (1200, math.ceil(len(batch) / 3) * 205), '#eeeeee')
        draw = ImageDraw.Draw(canvas)
        for offset, row in enumerate(batch):
            x, y = offset % 3 * 400, offset // 3 * 205
            content = (ROOT / row['local_path']).read_bytes()
            if hashlib.sha256(content).hexdigest() != row['sha256']: raise ValueError('Changed review image')
            with Image.open(ROOT / row['local_path']) as raw:
                image = ImageOps.exif_transpose(raw).convert('RGB')
                crop = transforms.CenterCrop(224)(transforms.Resize(256, interpolation=transforms.InterpolationMode.BICUBIC)(image))
                for part, dx in ((image, 0), (crop, 200)):
                    part = part.copy(); part.thumbnail((192, 145))
                    canvas.paste(part, (x + dx + (192 - part.width) // 2, y + 52 + (145 - part.height) // 2))
            label = SHORT[row['target_class']]
            pred = SHORT[row['prediction']] if 'prediction' in row else 'not evaluated'
            draw.text((x + 4, y + 2), f'{start + offset + 1} {row["md5hash"][:8]} {row["partition"]} {label} -> {pred}', fill='black')
            draw.text((x + 4, y + 18), f'{row["width"]}x{row["height"]} frame kept {retained_frame(row):.0%}', fill='black')
            draw.text((x + 4, y + 34), 'Original', fill='black'); draw.text((x + 204, y + 34), 'Model centre crop', fill='black')
        canvas.save(local / f'review-{page}.png')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    args = parser.parse_args()
    evidence = json.loads((ROOT / 'docs/ai/finetune_results/summary.json').read_text(encoding='utf-8'))
    config = evidence['config']
    mapping, rows, _ = load_baseline_data(config)
    names = {index: name for name, index in mapping.items()}
    path = ROOT / 'ai/runs' / evidence['run_id'] / 'best.pt'
    if hashlib.sha256(path.read_bytes()).hexdigest() != evidence['checkpoint_sha256']:
        raise ValueError('Fine-tuned checkpoint changed')
    checkpoint = torch.load(path, map_location='cpu', weights_only=True)
    if checkpoint['metadata']['config'] != config or checkpoint['metadata']['class_to_index'] != mapping:
        raise ValueError('Checkpoint config or class mapping differs')
    seed_everything(config['seed'], config['cpu_threads'])
    device = torch.device(args.device)
    model = build_model(len(mapping), pretrained=False).to(device)
    model.load_state_dict(checkpoint['model_state_dict']); model.eval()
    loader = DataLoader(FrozenImages(rows['val'], EfficientNet_B0_Weights.IMAGENET1K_V1.transforms()), batch_size=config['batch_size'])
    predictions = []
    with torch.inference_mode():
        for images, _ in loader:
            logits = model(images.to(device))
            if not torch.isfinite(logits).all(): raise ValueError('Nonfinite logits')
            predictions.extend(logits.argmax(1).cpu().tolist())
    metrics = classification_metrics([int(row['class_index']) for row in rows['val']], predictions, len(mapping))
    if any(metrics[key] != evidence['finetuned'][key] for key in metrics):
        raise ValueError('Predictions do not reproduce the verified checkpoint')
    validation = [{**row, 'prediction': names[prediction], 'correct': int(row['class_index']) == prediction}
                  for row, prediction in zip(rows['val'], predictions)]
    registry = json.loads((ROOT / 'ai/metadata_sources.json').read_text(encoding='utf-8'))
    source = next(item for item in registry['sources'] if item['name'] == 'fitz_corrected_zenodo')
    source_path = ROOT / source['local_path']
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != source['sha256']: raise ValueError('Source metadata changed')
    with source_path.open(encoding='utf-8', newline='') as handle:
        origins = {row['md5hash']: row for row in csv.DictReader(handle)}
    statistics = {}
    for name in mapping:
        statistics[name] = {}
        for split, collection in (('train', rows['train']), ('val', validation)):
            subset = [row for row in collection if row['target_class'] == name]
            kept = sorted(retained_frame(row) for row in subset)
            stats = {'images': len(subset), 'source_labels': dict(Counter(row['source_label'] for row in subset)),
                     'source_domains': dict(Counter(urlparse(origins[row['md5hash']]['url']).netloc.lower() for row in subset)),
                     'frame_retained_min': min(kept), 'frame_retained_median': (kept[(len(kept)-1)//2] + kept[len(kept)//2]) / 2,
                     'frame_below_half': sum(value < 0.5 for value in kept),
                     'short_edge_below_224': sum(min(int(row['width']), int(row['height'])) < 224 for row in subset)}
            if split == 'val':
                stats['predictions'] = dict(Counter(row['prediction'] for row in subset))
                stats['correct'] = sum(row['correct'] for row in subset)
                stats['below_half_correct'] = sum(row['correct'] for row in subset if retained_frame(row) < 0.5)
            statistics[name][split] = stats
    # Review all eczema validation cases, plus a deterministic technical sample from train.
    selected = [row for row in validation if row['target_class'] == 'eczema']
    # Eight wrong ACD validation examples ordered by amount of frame retained.
    selected += sorted((row for row in validation if row['target_class'] == 'allergic_contact_dermatitis' and not row['correct']),
                       key=lambda row: (retained_frame(row), row['md5hash']))[:8]
    for name in FOCUS:
        subset = sorted((row for row in rows['train'] if row['target_class'] == name), key=lambda row: (retained_frame(row), row['md5hash']))
        extremes = [subset[0], subset[-1]]
        remaining = [row for row in subset if row not in extremes]
        selected += extremes + random.Random(config['seed']).sample(remaining, 4)
    local = ROOT / 'ai/data/error_review'
    local.mkdir(parents=True, exist_ok=True)
    (local / 'validation_predictions.json').write_text(json.dumps(validation, indent=2) + '\n', encoding='utf-8')
    (local / 'selected.json').write_text(json.dumps(selected, indent=2) + '\n', encoding='utf-8')
    sheet(selected, local)
    output = ROOT / 'docs/ai/error_analysis'
    output.mkdir(parents=True, exist_ok=True)
    summary = {'run_id': evidence['run_id'], 'checkpoint_sha256': evidence['checkpoint_sha256'],
               'dataset_version': config['dataset_version'], 'test_images_read': 0, 'training_performed': False,
               'validation_predictions_verified': True, 'statistics': statistics,
               'review_selection': [{'image_id': row['md5hash'], 'partition': row['partition'], 'source_class': row['target_class']} for row in selected],
               'selection_count': len(selected), 'visual_review_record': 'ai/error_visual_review.json',
               'frame_metric': 'Geometric image area retained by resize256/centre224; not measured lesion area'}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'validation_images': len(validation), 'review_images': len(selected), 'test_images': 0,
                      'sheets': str(local), 'focus_statistics': {name: statistics[name] for name in FOCUS}}, indent=2))


if __name__ == '__main__': main()

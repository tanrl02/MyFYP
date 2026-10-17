"""Export the recorded visual triage and compare ten exact-label class candidates.

This does not diagnose, relabel, approve training data, or change exclusions.
Optional contact sheets stay in ignored local data; no network requests.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

try:
    from ai.audit_metadata import ROOT, load_locked_sources, read_csv
except ModuleNotFoundError:
    from audit_metadata import ROOT, load_locked_sources, read_csv

EXTRA = {'rosacea': ['rosacea'], 'vitiligo': ['vitiligo']}


def validate_review(review, rows):
    by_id = {row['md5hash']: row for row in rows}
    if len(by_id) != len(rows): raise ValueError('Repeated manifest image ID')
    flagged, sampled = review['flagged_image_ids'], review['sample_image_ids']
    if len(set(flagged)) != len(flagged) or len(set(sampled)) != len(sampled):
        raise ValueError('Repeated visual review ID')
    if set(flagged) & set(sampled): raise ValueError('Review sample overlaps original flagged set')
    if not (set(flagged) | set(sampled)) <= set(by_id):
        raise ValueError('Reviewed image missing from current manifest')
    grouped = set()
    for group in review['confirmed_visual_groups']:
        members = group['members']
        if len(members) < 2 or len(set(members)) != len(members):
            raise ValueError('Invalid visual group')
        if not set(members) <= set(flagged) or grouped & set(members):
            raise ValueError('Unreviewed or ambiguous visual group membership')
        grouped.update(members)
        if (len({by_id[identity]['partition'] for identity in members}) > 1) != group['cross_split']:
            raise ValueError('Recorded cross-split finding does not match source partitions')
    return by_id


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def contact_sheets(ids, by_id, prefix):
    output = ROOT / 'ai/data/review'
    output.mkdir(parents=True, exist_ok=True)
    for page, start in enumerate(range(0, len(ids), 20), 1):
        canvas = Image.new('RGB', (1280, 1500), '#eeeeee')
        draw = ImageDraw.Draw(canvas)
        for offset, identity in enumerate(ids[start:start + 20]):
            row = by_id[identity]
            x, y = offset % 4 * 320, offset // 4 * 300
            content = (ROOT / row['local_path']).read_bytes()
            if hashlib.sha256(content).hexdigest() != row['sha256']:
                raise ValueError('Image changed since preparation')
            with Image.open(ROOT / row['local_path']) as image:
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((310, 240))
                canvas.paste(image, (x + (320 - image.width) // 2, y + 45))
            draw.text((x + 5, y + 3), f'{start + offset + 1}: {identity[:8]} {row["target_class"]}', fill='black')
            draw.text((x + 5, y + 18), f'{row["partition"]} {row["width"]}x{row["height"]}', fill='black')
        canvas.save(output / f'{prefix}-{page}.jpg', quality=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sheets', action='store_true', help='Regenerate local contact sheets for the recorded review set')
    args = parser.parse_args()
    review = json.loads((ROOT / 'ai/visual_review.json').read_text(encoding='utf-8'))
    manifest = read_csv(ROOT / 'docs/ai/preparation/image_manifest.csv')
    by_id = validate_review(review, manifest)
    groups = {identity: group['group'] for group in review['confirmed_visual_groups'] for identity in group['members']}
    records = []
    for scope, ids in [('initial_flagged_78', review['flagged_image_ids']), ('initial_five_class_sample_40', review['sample_image_ids'])]:
        for identity in ids:
            row = by_id[identity]
            records.append({'md5hash': identity, 'target_class': row['target_class'], 'partition': row['partition'],
                            'review_scope': scope, 'reviewer': review['reviewer'],
                            'observation': 'matching_crop_or_resize' if identity in groups else 'thumbnail_content_triaged',
                            'visual_group': groups.get(identity, ''), 'current_mechanical_flags': row['quality_flags'],
                            'clinical_label_review': 'not performed',
                            'disposition': 'keep_quarantined' if scope == 'initial_flagged_78' else 'sample_only_no_training_approval'})
    _, sources = load_locked_sources()
    corrected = read_csv(sources['fitz_corrected_zenodo'])
    rules = json.loads((ROOT / 'ai/candidate_classes.json').read_text(encoding='utf-8'))
    candidates = {target: item['fitzpatrick'] for target, item in rules['classes'].items()} | EXTRA
    counts = []
    for target, aliases in candidates.items():
        rows = [row for row in corrected if row['label'] in aliases]
        splits = Counter(row['partition'] for row in rows)
        counts.append({'target_class': target, 'exact_source_labels': '|'.join(aliases),
                       'selected_by_user': target in rules['classes'], 'metadata_entries': len(rows),
                       'train': splits['train'], 'val': splits['val'], 'test': splits['test'],
                       'evidence_level': 'metadata only; image QA counts are separate'})
    output = ROOT / 'docs/ai/review'
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / 'visual_triage.csv', records)
    write_csv(output / 'class_scope.csv', counts)
    summary = {'reviewed_on': review['reviewed_on'], 'original_manifest_checkpoint': review['source_checkpoint'],
               'original_manifest_sha256': review['initial_manifest_sha256'],
               'original_flagged_thumbnails_reviewed': len(review['flagged_image_ids']),
               'original_five_class_sample_thumbnails_reviewed': len(review['sample_image_ids']),
               'visually_matching_groups': len(review['confirmed_visual_groups']),
               'visually_matching_groups_across_splits': sum(group['cross_split'] for group in review['confirmed_visual_groups']),
               'false_hash_match_examples': len(review['false_match_examples']),
               'selected_classes': list(rules['classes']), 'selected_metadata_entries': sum(row['metadata_entries'] for row in counts if row['selected_by_user']),
               'additional_images_visually_reviewed': 0, 'clinical_label_validation': False,
               'all_images_visually_reviewed': False, 'training_ready': False}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    if args.sheets:
        contact_sheets(review['flagged_image_ids'], by_id, 'flagged')
        contact_sheets(review['sample_image_ids'], by_id, 'sample')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()

"""Freeze conservative research manifests; verify images, keep source partitions.

No training, downloading, augmentation, relabelling or application changes.
Existing version files are accepted only when LF-normalised bytes match the export.
"""
import csv
import hashlib
import io
import json
from pathlib import Path

try:
    from ai.audit_metadata import ROOT, load_locked_sources, read_csv
    from ai.prepare_images import selected_rows
    from ai.review_dataset import validate_review
except ModuleNotFoundError:
    from audit_metadata import ROOT, load_locked_sources, read_csv
    from prepare_images import selected_rows
    from review_dataset import validate_review

VERSION = 'eight-class-v1'
SPLITS = ('train', 'val', 'test')


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def curate(rows, source_rows, rules, initial_review, expanded_review):
    by_id = validate_review(initial_review, rows)
    selected = selected_rows(source_rows, rules)
    source = {row['md5hash']: row for row in selected}
    if set(by_id) != set(source): raise ValueError('Prepared membership differs from locked source subset')
    initial_flags = set(initial_review['flagged_image_ids'])
    flagged = {identity for identity, row in by_id.items() if row['quality_flags']}
    new_flags = expanded_review['new_flagged_image_ids']
    if len(new_flags) != len(set(new_flags)) or set(new_flags) != flagged - initial_flags:
        raise ValueError('Expanded flagged review is incomplete or inconsistent')
    if not initial_flags <= flagged: raise ValueError('Initial quarantines were removed')
    sample = expanded_review['additional_class_sample_ids']
    if len(sample) != len(set(sample)) or not set(sample) <= set(by_id) or set(sample) & flagged:
        raise ValueError('Invalid expanded sample review')
    policy = expanded_review['research_freeze_policy']
    if not all(policy[key] is True for key in ('exclude_all_mechanical_flags', 'manual_exclusions_apply', 'keep_original_partitions')):
        raise ValueError('Freeze requires conservative exclusions and original partitions')
    if policy['augment_before_split'] is not False: raise ValueError('Pre-split augmentation is forbidden')
    manual = {}
    for decision in expanded_review['manual_exclusions']:
        identity, related = decision['md5hash'], decision['related_md5hash']
        if identity in manual or identity not in by_id or related not in by_id:
            raise ValueError('Invalid manual exclusion evidence')
        if identity == related or related not in flagged:
            raise ValueError('Manual related-image exclusion must reference a quarantined image')
        manual[identity] = decision['reason'] + ':' + related
    classes = {label: index for index, label in enumerate(rules['classes'])}
    accepted = {split: [] for split in SPLITS}
    excluded = []
    for row in sorted(rows, key=lambda item: (classes[item['target_class']], item['md5hash'])):
        identity = row['md5hash']
        expected = source[identity]
        if (row['partition'], row['target_class'], row['source_label']) != (expected['partition'], expected['target_class'], expected['label']):
            raise ValueError('Source split or label changed')
        reasons = row['quality_flags']
        if identity in manual: reasons = '|'.join(filter(None, (reasons, manual[identity])))
        exported = {key: row[key] for key in ('md5hash', 'sha256', 'pixel_sha256', 'local_path', 'target_class', 'source_label', 'partition', 'width', 'height', 'fst')}
        exported['class_index'] = classes[row['target_class']]
        if reasons:
            excluded.append({**exported, 'exclusion_reasons': reasons})
        else:
            accepted[row['partition']].append(exported)
    # Exact decoded-pixel/hash equality must never cross frozen partitions.
    for field in ('md5hash', 'sha256', 'pixel_sha256'):
        seen = {}
        for split, records in accepted.items():
            for row in records:
                value = row[field]
                if value in seen and seen[value] != split:
                    raise ValueError(f'Cross-split duplicate {field}')
                seen[value] = split
    for split, records in accepted.items():
        if set(row['target_class'] for row in records) != set(classes):
            raise ValueError(f'Missing class after exclusions in {split}')
    return accepted, excluded, classes


def csv_bytes(rows):
    handle = io.StringIO(newline='')
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
    return handle.getvalue().encode()


def write_frozen(output, files):
    """Check the entire version before writing anything; never replace a version."""
    output = Path(output)
    if output.exists():
        existing = {path.name for path in output.iterdir() if path.is_file()}
        if existing != set(files) or any((output / name).read_bytes().replace(b'\r\n', b'\n') != content for name, content in files.items()):
            raise ValueError('Frozen version differs; create a new dataset version instead of overwriting')
        return
    output.mkdir(parents=True)
    for name, content in files.items(): (output / name).write_bytes(content)


def main():
    _, sources = load_locked_sources()
    def read_json(name): return json.loads((ROOT / name).read_text(encoding='utf-8'))
    rules = read_json('ai/candidate_classes.json')
    initial = read_json('ai/visual_review.json')
    expanded = read_json('ai/expanded_review.json')
    rows = read_csv(ROOT / 'docs/ai/preparation/image_manifest.csv')
    source = read_csv(sources['fitz_corrected_zenodo'])
    accepted, excluded, classes = curate(rows, source, rules, initial, expanded)
    for index, row in enumerate(rows):
        path = (ROOT / row['local_path']).resolve()
        if not path.is_relative_to((ROOT / 'ai/data/fitzpatrick17k/images').resolve()):
            raise ValueError('Image path outside expected data directory')
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Image changed since hash/decode verification')
        if (index + 1) % 500 == 0: print(f'Verified {index + 1}/{len(rows)} image SHA-256 values', flush=True)
    files = {split + '.csv': csv_bytes(records) for split, records in accepted.items()}
    files['excluded.csv'] = csv_bytes(excluded)
    files['class_to_index.json'] = (json.dumps(classes, indent=2) + '\n').encode()
    per_class = {label: {split: sum(row['target_class'] == label for row in records) for split, records in accepted.items()} for label in classes}
    summary = {'dataset_version': VERSION, 'frozen_on': expanded['reviewed_on'],
               'research_baseline_manifests_frozen': True, 'clinical_use_validated': False,
               'all_images_visually_reviewed': False, 'source_partitions_preserved': True,
               'source_image_entries': len(rows), 'included_images': sum(map(len, accepted.values())),
               'excluded_images': len(excluded), 'split_counts': {split: len(records) for split, records in accepted.items()},
               'per_class': per_class, 'visual_triage_flagged_images': len(initial['flagged_image_ids']) + len(expanded['new_flagged_image_ids']),
               'visual_triage_sample_images': len(initial['sample_image_ids']) + len(expanded['additional_class_sample_ids']),
               'rules_semantic_sha256': digest_json(rules), 'initial_review_semantic_sha256': digest_json(initial),
               'expanded_review_semantic_sha256': digest_json(expanded), 'preparation_rows_semantic_sha256': digest_json(rows),
               'manifest_sha256_normalised_lf': {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
               'limitations': ['Labels inherited from source, not clinically revalidated', 'Technical visual review is partial; every image has not been manually reviewed',
                               'No participant IDs; patient independence unproven', 'Difference hashing and sample review cannot rule out every near duplicate',
                               'No training, model performance or phone-domain validation', 'Noncommercial research data source; retain original attribution/licence notices']}
    files['dataset.json'] = (json.dumps(summary, indent=2, sort_keys=True) + '\n').encode()
    output = ROOT / 'ai/manifests' / VERSION
    write_frozen(output, files)
    print(json.dumps({'output': str(output), 'included': summary['included_images'], 'excluded': len(excluded), 'splits': summary['split_counts']}, indent=2))


if __name__ == '__main__':
    main()

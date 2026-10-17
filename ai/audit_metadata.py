"""Reproducible metadata-only audit. Standard library; never fetches images."""
import argparse
import ast
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def literal_weights(value):
    if not value.strip():
        return {}
    if len(value) > 100000:
        raise ValueError('Oversized label cell')
    result = ast.literal_eval(value)
    if not isinstance(result, dict):
        raise ValueError('Expected a weight dictionary')
    if any(not isinstance(k, str) or isinstance(v, bool) or not isinstance(v, (int, float))
           or not math.isfinite(v) or not 0 <= v <= 1 for k, v in result.items()):
        raise ValueError('Invalid label weight')
    return {k: float(v) for k, v in result.items() if v > 0}


def leading_label(weights):
    ranked = sorted(weights.items(), key=lambda item: (-item[1], item[0]))
    if not ranked:
        return None, 0, 0
    second = ranked[1][1] if len(ranked) > 1 else 0
    if math.isclose(ranked[0][1], second, abs_tol=1e-9):
        return None, ranked[0][1], 0
    return ranked[0][0], ranked[0][1], ranked[0][1] - second


def index_unique(rows, key):
    result = {}
    for row in rows:
        if not row.get(key) or row[key] in result:
            raise ValueError(f'Missing or duplicate {key}; do not count duplicate rows as cases')
        result[row[key]] = row
    return result


def audit_scin(cases, labels, thresholds):
    cases = index_unique(cases, 'case_id')
    labels = index_unique(labels, 'case_id')
    if set(cases) != set(labels):
        raise ValueError('SCIN case/label identifiers do not match')
    counts = defaultdict(Counter)
    stats = Counter()
    paths = Counter()
    path_cases = defaultdict(set)
    gradability = Counter()
    for case_id, case in cases.items():
        row = labels[case_id]
        images = [case[f'image_{i}_path'].strip() for i in (1, 2, 3) if case[f'image_{i}_path'].strip()]
        paths.update(images)
        for path in images:
            path_cases[path].add(case_id)
        grades = [row[f'dermatologist_gradable_for_skin_condition_{i}'] for i in (1, 2, 3)]
        gradability.update(grades)
        weights = literal_weights(row['weighted_skin_condition_label'])
        if not weights:
            stats['without_weighted_label'] += 1
        for label in weights:
            counts[label]['any_weight_cases'] += 1
        top, weight, margin = leading_label(weights)
        if weights and top is None:
            stats['tied_top_cases'] += 1
        if top is not None:
            stats['unique_top_cases'] += 1
            counts[top]['unique_top_cases'] += 1
            counts[top]['unique_top_image_references'] += len(images)
            weight_screen = (weight + 1e-9 >= thresholds['minimum_top_weight']
                             and margin + 1e-9 >= thresholds['minimum_margin'])
            grade_screen = 'DEFAULT_YES_IMAGE_QUALITY_SUFFICIENT' in grades
            if weight_screen and grade_screen and images:
                stats['screened_cases'] += 1
                counts[top]['screened_cases'] += 1
                counts[top]['screened_image_references'] += len(images)
    summary = {
        'case_count': len(cases), 'label_row_count': len(labels),
        'releases': dict(Counter(row['release'] for row in cases.values())),
        'image_references': sum(paths.values()), 'distinct_image_paths': len(paths),
        'repeated_path_references': sum(paths.values()) - len(paths),
        'paths_shared_between_cases': sum(len(group) > 1 for group in path_cases.values()),
        'missing_image_cases': sum(not any(row[f'image_{i}_path'].strip() for i in (1, 2, 3)) for row in cases.values()),
        'gradability_values': dict(gradability), **dict(stats),
        'screen_rule': 'unique top; weight >=0.60; margin >=0.20; at least one default-gradable rating; at least one image reference',
        'image_bytes_or_existence_checked': False, 'patient_id_available': False,
    }
    return summary, {label: dict(values) for label, values in sorted(counts.items())}


def audit_fitz(rows, corrected=False):
    if not rows:
        raise ValueError('Empty Fitzpatrick metadata')
    counts = defaultdict(Counter)
    hashes = Counter()
    hash_splits = defaultdict(set)
    url_splits = defaultdict(set)
    for row in rows:
        label = row['label']
        counts[label]['images'] += 1
        identity = row['md5hash'].strip()
        if not identity:
            raise ValueError('Missing image hash')
        hashes[identity] += 1
        if corrected:
            split = row['partition']
            if split not in ('train', 'val', 'test'):
                raise ValueError('Unknown provided split')
            counts[label][split] += 1
            hash_splits[identity].add(split)
            if row['url'].strip():
                url_splits[row['url'].strip()].add(split)
    return {
        'rows': len(rows), 'unique_md5_identifiers': len(hashes),
        'repeated_md5_rows': len(rows) - len(hashes),
        'cross_split_repeated_md5': sum(len(group) > 1 for group in hash_splits.values()),
        'cross_split_repeated_literal_urls': sum(len(group) > 1 for group in url_splits.values()),
        'partitions': dict(Counter(row['partition'] for row in rows)) if corrected else {},
        'skin_type_counts': dict(Counter(row.get('fst', row.get('fitzpatrick_scale', '')) for row in rows)),
        'image_bytes_or_existence_checked': False, 'patient_id_available': False,
    }, {label: dict(values) for label, values in sorted(counts.items())}


def candidate_table(rules, scin, original, corrected):
    result = []
    for name, mapping in rules['classes'].items():
        values = {'candidate_class': name, 'scin_labels': ' | '.join(mapping['scin']),
                  'fitz_labels': ' | '.join(mapping['fitzpatrick'])}
        for field in ('any_weight_cases', 'unique_top_cases', 'screened_cases', 'screened_image_references'):
            values['scin_' + field] = sum(scin.get(label, {}).get(field, 0) for label in mapping['scin'])
        values['fitz_original_images'] = sum(original.get(label, {}).get('images', 0) for label in mapping['fitzpatrick'])
        for field in ('images', 'train', 'val', 'test'):
            values['fitz_c_' + field] = sum(corrected.get(label, {}).get(field, 0) for label in mapping['fitzpatrick'])
        result.append(values)
    return result


def load_locked_sources(download=False):
    registry = json.loads((ROOT / 'ai/metadata_sources.json').read_text(encoding='utf-8'))
    locations = {}
    for source in registry['sources']:
        path = ROOT / source['local_path']
        if download and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            request = Request(source['url'], headers={'User-Agent': 'SmartSkin-FYP-metadata-audit'})
            with urlopen(request, timeout=60) as response:
                content = response.read(10000001)
            if len(content) > 10000000:
                raise ValueError('Refusing a source larger than 10 MB')
            if hashlib.sha256(content).hexdigest() != source['sha256']:
                raise ValueError('Source changed; inspect it before updating the lock')
            path.write_bytes(content)
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != source['sha256']:
            raise ValueError(f"Hash mismatch: {source['name']}")
        locations[source['name']] = path
    return registry, locations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Fetch missing locked metadata only, maximum 10 MB per file')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'docs/ai/data_audit')
    args = parser.parse_args()
    registry, paths = load_locked_sources(args.download)
    rules = json.loads((ROOT / 'ai/candidate_classes.json').read_text(encoding='utf-8'))
    scin_summary, scin = audit_scin(read_csv(paths['scin_cases']), read_csv(paths['scin_labels']), rules['scin_screen'])
    original_summary, original = audit_fitz(read_csv(paths['fitz_original']))
    corrected_rows = read_csv(paths['fitz_corrected_zenodo'])
    corrected_summary, corrected = audit_fitz(corrected_rows, True)
    github_rows = read_csv(paths['fitz_corrected_github'])
    github_summary, _ = audit_fitz(github_rows, True)
    def membership(rows):return {(row['md5hash'], row['label'], row['partition']) for row in rows}
    comparison = {'github_rows': len(github_rows), 'zenodo_rows': len(corrected_rows),
                  'membership_label_split_sets_equal': membership(github_rows) == membership(corrected_rows),
                  'github_summary': github_summary}
    summary = {'audited_on': registry['audited_on'], 'scope': 'metadata only; counts are not verified usable image counts',
               'scin': scin_summary, 'fitzpatrick_original': original_summary,
               'fitzpatrick_corrected': corrected_summary, 'corrected_source_comparison': comparison,
               'candidate_classes': candidate_table(rules, scin, original, corrected)}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    def dump(name, value):
        (args.output_dir / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    dump('summary.json', summary)
    dump('scin_all_labels.json', scin)
    dump('fitzpatrick_original_labels.json', original)
    dump('fitzpatrick_corrected_labels.json', corrected)
    with (args.output_dir / 'candidate_counts.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary['candidate_classes'][0]))
        writer.writeheader(); writer.writerows(summary['candidate_classes'])
    print(json.dumps({'scin_cases': scin_summary['case_count'], 'corrected_images_in_metadata': corrected_summary['rows'],
                      'corrected_sources_match': comparison['membership_label_split_sets_equal'],
                      'output': str(args.output_dir)}, indent=2))


if __name__ == '__main__':
    main()

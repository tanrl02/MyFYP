"""Offline SCIN candidate screening. Ranking weights are not disease probabilities."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import PurePosixPath

try:
    from ai.audit_metadata import ROOT, read_csv, load_locked_sources, index_unique, literal_weights, leading_label
except ModuleNotFoundError:
    from audit_metadata import ROOT, read_csv, load_locked_sources, index_unique, literal_weights, leading_label

POSITIVE = 'DEFAULT_YES_IMAGE_QUALITY_SUFFICIENT'
FOCUS = ('eczema', 'allergic_contact_dermatitis', 'seborrheic_dermatitis')


def screen_case(case, label, shared_paths):
    weights = literal_weights(label['weighted_skin_condition_label'])
    top, weight, margin = leading_label(weights)
    grades = [label.get(f'dermatologist_gradable_for_skin_condition_{i}', '').strip() for i in (1, 2, 3)]
    grades = [grade for grade in grades if grade]
    images = []
    for index in (1, 2, 3):
        path = case.get(f'image_{index}_path', '').strip()
        if path:
            images.append({'path': path, 'shot_type': case.get(f'image_{index}_shot_type', '').strip()})
    valid_paths = bool(images) and len({item['path'] for item in images}) == len(images)
    for item in images:
        path = PurePosixPath(item['path'])
        valid_paths = valid_paths and len(path.parts) == 3 and path.parts[:2] == ('dataset', 'images') and '..' not in path.parts
        valid_paths = valid_paths and path.suffix.lower() in ('.png', '.jpg', '.jpeg')
    initial = bool(top and weight + 1e-9 >= .6 and margin + 1e-9 >= .2 and POSITIVE in grades and images)
    all_gradable = bool(grades) and all(grade == POSITIVE for grade in grades)
    strict = bool(top and weight + 1e-9 >= .8 and margin + 1e-9 >= .4 and all_gradable and valid_paths
                  and not any(item['path'] in shared_paths for item in images))
    return {'top_label': top, 'top_weight': weight, 'margin': margin, 'initial_screen': initial,
            'strict_screen': strict, 'multiple_graders_strict': strict and len(grades) >= 2,
            'positive_graders': grades.count(POSITIVE), 'gradable_disagreement': POSITIVE in grades and not all_gradable,
            'image_references': images}


def main():
    registry, paths = load_locked_sources()
    cases = index_unique(read_csv(paths['scin_cases']), 'case_id')
    labels = index_unique(read_csv(paths['scin_labels']), 'case_id')
    if set(cases) != set(labels): raise ValueError('Case and annotation identifiers differ')
    rules = json.loads((ROOT / 'ai/candidate_classes.json').read_text(encoding='utf-8'))
    source_to_target = {}
    for target, rule in rules['classes'].items():
        for source_label in rule['scin']:
            if source_label in source_to_target: raise ValueError('Ambiguous source mapping')
            source_to_target[source_label] = target
    path_cases = defaultdict(set)
    for case_id, case in cases.items():
        for index in (1, 2, 3):
            path = case[f'image_{index}_path'].strip()
            if path: path_cases[path].add(case_id)
    shared = {path for path, identities in path_cases.items() if len(identities) > 1}
    statistics = {target: Counter() for target in rules['classes']}
    eligible = defaultdict(list)
    for case_id, case in cases.items():
        label = labels[case_id]
        for name in literal_weights(label['weighted_skin_condition_label']):
            if name in source_to_target: statistics[source_to_target[name]]['any_weight_cases'] += 1
        result = screen_case(case, label, shared)
        target = source_to_target.get(result['top_label'])
        if not target: continue
        stats = statistics[target]
        stats['unique_top_cases'] += 1
        stats['top_cases_with_gradability_disagreement'] += result['gradable_disagreement']
        for tier in ('initial_screen', 'strict_screen', 'multiple_graders_strict'):
            if result[tier]:
                stats[tier + '_cases'] += 1
                stats[tier + '_image_references'] += len(result['image_references'])
        if result['strict_screen']:
            stats['strict_positive_graders_' + str(result['positive_graders'])] += 1
            eligible[target].append({'case_id': case_id, 'target_candidate': target,
                'source_top_label': result['top_label'], 'top_weight': result['top_weight'], 'margin': result['margin'],
                'positive_graders': result['positive_graders'], 'image_references': result['image_references'],
                'original_differential_labels': label['dermatologist_skin_condition_on_label_name'],
                'original_differential_confidence': label['dermatologist_skin_condition_confidence'],
                'status': 'review_only_no_split_not_training_approved'})
    batch = []
    for target in FOCUS:
        candidates = sorted(eligible[target], key=lambda item: (
            -item['positive_graders'], -item['top_weight'], -item['margin'],
            hashlib.sha256(('3403:' + item['case_id']).encode()).hexdigest()))
        for item in candidates[:20]:
            images = item['image_references']
            preferred = min(images, key=lambda image: (image['shot_type'] != 'CLOSE_UP', image['path']))
            batch.append({**item, 'preferred_first_review_image': preferred})
    local = ROOT / 'ai/data/scin/review'
    local.mkdir(parents=True, exist_ok=True)
    (local / 'eligible_cases.json').write_text(json.dumps(dict(eligible), indent=2) + '\n', encoding='utf-8')
    (local / 'first_batch.json').write_text(json.dumps(batch, indent=2) + '\n', encoding='utf-8')
    summary = {'audited_on': '2026-10-18', 'scope': 'Existing SHA-locked SCIN metadata only',
        'case_count': len(cases), 'releases': dict(Counter(case['release'] for case in cases.values())),
        'sources': [{key: source[key] for key in ('name', 'url', 'sha256')} for source in registry['sources'] if source['name'].startswith('scin_')],
        'shared_image_paths_between_cases': len(shared), 'class_statistics': statistics,
        'screen_rules': {
            'initial': 'Unique top, weight>=0.60, margin>=0.20, at least one default-positive case-grade and image reference (historical rule)',
            'strict': 'Unique top, weight>=0.80, margin>=0.40, ALL available case-graders default-positive, valid distinct paths and no literal path shared with another case',
            'multiple_graders_strict': 'Strict rule plus at least two available default-positive case-graders; not proof of diagnostic consensus'},
        'first_batch': {'cases_by_class': dict(Counter(item['target_candidate'] for item in batch)), 'total_cases': len(batch),
                        'first_review_image_references': len(batch),
                        'all_case_image_references': sum(len(item['image_references']) for item in batch),
                        'preferred_close_ups': sum(item['preferred_first_review_image']['shot_type'] == 'CLOSE_UP' for item in batch)},
        'image_bytes_downloaded': 0, 'image_availability_or_quality_verified': False,
        'training_approved': False, 'test_images_used': 0,
        'limitations': ['Weights rank differential diagnoses; they are not calibrated disease probabilities',
                       'Case IDs are not participant IDs; participant independence is not established',
                       'Gradability fields describe case raters, not matching image numbers',
                       'No file bytes or perceptual duplicates checked; no clinical label verification',
                       'Original confidence values are retained for review but are not used by this ranking-weight screen',
                       'Exact mapped labels still need cross-source taxonomy review; no source labels silently merged']}
    output = ROOT / 'docs/ai/scin_expansion'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()

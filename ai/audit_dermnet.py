"""Public Kaggle Dermnet file-list audit. Downloads JSON metadata only, never images."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'ai/data/dermnet/raw'
BASE = 'https://www.kaggle.com/api/v1/datasets/'
REF = 'shubhamgoel27/dermnet'


def read_json(path): return json.loads(path.read_text(encoding='utf-8'))


def fetch_json(url):
    with urlopen(Request(url, headers={'User-Agent': 'SmartSkin-FYP-metadata-audit'}), timeout=25) as response:
        content = response.read(5000001)
    if len(content) > 5000000: raise ValueError('Metadata response exceeds 5 MB')
    json.loads(content)
    return content


def download_metadata():
    RAW.mkdir(parents=True, exist_ok=True)
    before = fetch_json(BASE + 'view/' + REF)
    if (RAW / 'view.json').exists() and any(
        read_json(RAW / 'view.json').get(key) != json.loads(before).get(key)
        for key in ('currentVersionNumber', 'lastUpdated', 'totalBytes')):
        raise ValueError('Dataset version/size changed; review before replacing metadata')
    token, seen, total = '', set(), len(before)
    pages = []
    for page in range(1, 121):
        url = BASE + 'list/' + REF + '?' + urlencode({'pageSize': 200, **({'pageToken': token} if token else {})})
        path = RAW / f'files-{page:04d}.json'
        content = path.read_bytes() if path.exists() else fetch_json(url)
        total += len(content)
        if total > 16000000: raise ValueError('Refusing more than 16 MB of metadata')
        data = json.loads(content)
        if data.get('errorMessage'): raise ValueError('Kaggle file-list error')
        files = data.get('datasetFiles')
        if not isinstance(files, list) or not files: raise ValueError('Unexpected empty file page')
        path.write_bytes(content)
        pages.append({'file': path.name, 'sha256': hashlib.sha256(content).hexdigest(), 'entries': len(files)})
        next_token = data.get('nextPageToken', '')
        if not next_token: break
        if next_token in seen: raise ValueError('Repeated pagination token')
        seen.add(next_token); token = next_token
        if page % 10 == 0: print(f'Cached {page} file-list pages; no image requests', flush=True)
    else: raise ValueError('Refusing more than 120 file-list pages')
    after = fetch_json(BASE + 'view/' + REF)
    if any(json.loads(before).get(key) != json.loads(after).get(key) for key in ('currentVersionNumber', 'lastUpdated', 'totalBytes')):
        raise ValueError('Dataset changed during audit')
    (RAW / 'view.json').write_bytes(before)
    manifest = {'dataset_ref': REF, 'complete': True, 'version': json.loads(before)['currentVersionNumber'],
                'view_sha256': hashlib.sha256(before).hexdigest(), 'pages': pages}
    (RAW / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


def aggregate(files):
    counts, seen = defaultdict(Counter), set()
    basenames = defaultdict(set)
    category_basenames = defaultdict(set)
    category_sizes = defaultdict(dict)
    bytes_by_split = Counter()
    for item in files:
        name = item['name']
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or len(path.parts) != 3 or path.parts[0] not in ('train', 'test'):
            raise ValueError('Unexpected file-list path')
        if name in seen: raise ValueError('Repeated file-list entry')
        if path.suffix.lower() not in ('.jpg', '.jpeg', '.png'): raise ValueError('Unexpected image extension')
        seen.add(name)
        split, category, filename = path.parts
        counts[category][split] += 1
        bytes_by_split[split] += item['totalBytes']
        basenames[filename.lower()].add(split)
        category_basenames[(category, filename.lower())].add(split)
        category_sizes[(category, filename.lower())][split] = item['totalBytes']
    return {'file_entries': len(seen), 'categories': {name: dict(count) for name, count in sorted(counts.items())},
            'bytes_by_split': dict(bytes_by_split),
            'basenames_shared_between_train_test': sum(len(splits) > 1 for splits in basenames.values()),
            'category_basenames_shared_between_train_test': sum(len(splits) > 1 for splits in category_basenames.values()),
            'same_category_name_size_pairs_by_category': dict(Counter(category for (category, _), sizes in category_sizes.items()
                if set(sizes) == {'train', 'test'} and sizes['train'] == sizes['test'])),
            'basename_check_is_not_content_duplicate_check': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true', help='Fetch public JSON file-list metadata only, bounded to 16 MB')
    args = parser.parse_args()
    if args.fetch: download_metadata()
    lock = read_json(RAW / 'manifest.json')
    if not lock['complete'] or lock['dataset_ref'] != REF: raise ValueError('Incomplete metadata manifest')
    view_bytes = (RAW / 'view.json').read_bytes()
    if hashlib.sha256(view_bytes).hexdigest() != lock['view_sha256']: raise ValueError('Dataset description changed')
    files = []
    for page in lock['pages']:
        content = (RAW / page['file']).read_bytes()
        if hashlib.sha256(content).hexdigest() != page['sha256']: raise ValueError('File-list page changed')
        entries = json.loads(content)['datasetFiles']
        if len(entries) != page['entries']: raise ValueError('File-list count changed')
        files.extend(entries)
    view = json.loads(view_bytes)
    counts = aggregate(files)
    if sum(counts['bytes_by_split'].values()) != view['totalBytes']:
        raise ValueError('File-list byte totals do not match the publisher; incomplete or changed snapshot')
    result = {'audited_on': '2026-10-18', 'dataset_ref': REF, 'dataset_version': lock['version'],
              'uploader_declared_license': view.get('licenseName'), 'publisher_total_bytes': view['totalBytes'],
              'metadata_manifest_sha256': hashlib.sha256((RAW / 'manifest.json').read_bytes()).hexdigest(),
              'metadata_pages': len(lock['pages']), **counts, 'image_bytes_downloaded': 0,
              'image_existence_decode_hash_or_quality_verified': False, 'training_approved': False}
    output = ROOT / 'docs/ai/dermnet_audit'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    (output / 'metadata_lock.json').write_text(json.dumps(lock, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()

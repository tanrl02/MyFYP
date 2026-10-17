"""Acquire/check the locked 45-image SCIN review batch, never train or edit splits."""
import argparse
import ast
import base64
from collections import Counter
import hashlib
import json
from pathlib import PurePosixPath
import re
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageOps
try:
    from ai.audit_metadata import ROOT, read_csv, load_locked_sources
    from ai.prepare_images import image_properties
    from ai.freeze_dataset import digest_json
    from ai.baseline_data import load_baseline_data
except ModuleNotFoundError:
    from audit_metadata import ROOT, read_csv, load_locked_sources
    from prepare_images import image_properties
    from freeze_dataset import digest_json
    from baseline_data import load_baseline_data

LOCAL = ROOT / 'ai/data/scin/review'
LICENSE = 'https://raw.githubusercontent.com/google-research-datasets/scin/main/LICENSE'
README = 'https://raw.githubusercontent.com/google-research-datasets/scin/main/README.md'


def crc32c(content):
    table = []
    for byte in range(256):
        value = byte
        for _ in range(8): value = (value >> 1) ^ (0x82F63B78 if value & 1 else 0)
        table.append(value)
    checksum = 0xffffffff
    for byte in content: checksum = table[(checksum ^ byte) & 255] ^ (checksum >> 8)
    return checksum ^ 0xffffffff


def source_path(value):
    if not re.fullmatch(r'dataset/images/-?\d+\.(?:png|jpg|jpeg)', value):
        raise ValueError('Unexpected SCIN object path')
    return PurePosixPath(value).name


def checked_properties(content, headers, limit):
    if len(content) > limit: raise ValueError('Image exceeds size limit')
    if headers.get('Content-Length') and len(content) != int(headers['Content-Length']):
        raise ValueError('Truncated image response')
    advertised = expected_crc = None
    for field in headers.get('x-goog-hash', '').split(','):
        if field.strip().startswith('md5='):
            advertised = base64.b64decode(field.strip()[4:], validate=True).hex()
        if field.strip().startswith('crc32c='):
            expected_crc = int.from_bytes(base64.b64decode(field.strip()[7:], validate=True), 'big')
    md5 = hashlib.md5(content).hexdigest()
    if advertised is not None and md5 != advertised: raise ValueError('Server MD5 mismatch')
    if expected_crc is not None and crc32c(content) != expected_crc: raise ValueError('Server CRC32C mismatch')
    return {**image_properties(content, advertised or md5), 'md5': md5,
            'server_md5_verified': advertised is not None, 'server_crc32c_verified': expected_crc is not None}


def pair_match(first, second):
    if first['sha256'] == second['sha256']: return 'exact_bytes'
    if first['pixel_sha256'] == second['pixel_sha256']: return 'exact_pixels'
    if (int(first['dhash'], 16) ^ int(second['dhash'], 16)).bit_count() <= 4: return 'dhash_candidate'
    return None


def make_sheets(records):
    for page, start in enumerate(range(0, len(records), 15), 1):
        canvas = Image.new('RGB', (1200, 1400), '#eeeeee')
        draw = ImageDraw.Draw(canvas)
        for offset, row in enumerate(records[start:start + 15]):
            x, y = offset % 3 * 400, offset // 3 * 280
            with Image.open(ROOT / row['local_path']) as image:
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((390, 215))
                canvas.paste(image, (x + (400-image.width)//2, y + 60 + (215-image.height)//2))
            draw.text((x+4, y+3), f'{start+offset+1}: {row["target_candidate"]}', fill='black')
            draw.text((x+4, y+19), f'case {row["case_id"]}', fill='black')
            draw.text((x+4, y+35), f'{row["width"]}x{row["height"]} grades={row["positive_graders"]} weight={row["top_weight"]}', fill='black')
        canvas.save(LOCAL / f'photos-{page}.jpg', quality=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--sheets', action='store_true')
    args = parser.parse_args()
    config = json.loads((ROOT / 'ai/scin_review_config.json').read_text())
    batch_bytes = (LOCAL / 'first_batch.json').read_bytes()
    if hashlib.sha256(batch_bytes).hexdigest() != config['batch_sha256']: raise ValueError('Review batch changed')
    batch = json.loads(batch_bytes)
    if len(batch) != config['expected_cases'] or len({r['case_id'] for r in batch}) != len(batch): raise ValueError('Wrong case count')
    if dict(Counter(r['target_candidate'] for r in batch)) != config['expected_classes']: raise ValueError('Wrong class counts')
    names = [source_path(r['preferred_first_review_image']['path']) for r in batch]
    if len(set(names)) != len(names): raise ValueError('Repeated selected image')
    load_locked_sources()
    model_config = json.loads((ROOT / 'ai/finetune_config.json').read_text())
    _, _, frozen = load_baseline_data(model_config)
    old = read_csv(ROOT / 'docs/ai/preparation/image_manifest.csv')
    if digest_json(old) != frozen['preparation_rows_semantic_sha256']: raise ValueError('Prior image fingerprint manifest changed')
    images = LOCAL / 'images'; images.mkdir(parents=True, exist_ok=True)
    state_path = LOCAL / 'downloads.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    downloaded = 0
    if args.download:
        for name, url in (('LICENSE.txt', LICENSE), ('README.md', README)):
            path = LOCAL / name
            if not path.exists():
                with urlopen(Request(url, headers={'User-Agent': 'SmartSkin-FYP-research-review'}), timeout=25) as response:
                    data = response.read(100001)
                if len(data) > 100000: raise ValueError('Source notice exceeds limit')
                path.write_bytes(data)
    if not (LOCAL / 'LICENSE.txt').exists(): raise ValueError('SCIN licence notice missing; use --download')
    records, failures = [], []
    for index, item in enumerate(batch, 1):
        object_path = item['preferred_first_review_image']['path']
        path = images / source_path(object_path)
        try:
            if path.exists() and object_path in state:
                content = path.read_bytes()
                if hashlib.sha256(content).hexdigest() != state[object_path]['sha256']: raise ValueError('Cached image changed')
                headers = state[object_path]['headers']
            else:
                if not args.download: raise ValueError('Image unavailable offline')
                url = config['source_bucket'] + object_path
                limit = min(config['max_image_bytes'], config['max_run_bytes'] - downloaded)
                if limit <= 0: raise ValueError('Network byte budget exhausted')
                with urlopen(Request(url, headers={'User-Agent': 'SmartSkin-FYP-research-review'}), timeout=30) as response:
                    if response.geturl() != url: raise ValueError('Unexpected image redirect')
                    content = response.read(limit + 1)
                    headers = {key: response.headers.get(key, '') for key in ('Content-Length', 'Content-Type', 'x-goog-hash', 'ETag')}
                downloaded += len(content)
                checked_properties(content, headers, limit)
                if path.exists() and path.read_bytes() != content: raise ValueError('Untracked local image differs from server')
                path.write_bytes(content)
                state[object_path] = {'sha256': hashlib.sha256(content).hexdigest(), 'headers': headers, 'url': url}
                state_path.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
            properties = checked_properties(content, headers, config['max_image_bytes'])
            scores = ast.literal_eval(item['original_differential_confidence'])
            if not isinstance(scores, list) or any(type(score) is not int or not 1 <= score <= 5 for score in scores):
                raise ValueError('Unexpected original confidence values')
            records.append({**item, **properties, 'source_max_original_confidence': max(scores) if scores else None,
                            'local_path': path.relative_to(ROOT).as_posix(), 'source_url': config['source_bucket']+object_path})
        except (OSError, ValueError) as error:
            failures.append({'case_id': item['case_id'], 'path': object_path, 'error': str(error)})
        if index % 5 == 0: print(f'Checked {index}/{len(batch)} selected images; fetched {downloaded//1048576} MiB', flush=True)
    pairs = []
    for index, row in enumerate(records):
        for other in old:
            match = pair_match(row, other)
            if match: pairs.append({'new_case': row['case_id'], 'other_source': 'fitzpatrick', 'other_id': other['md5hash'],
                                    'other_partition': other['partition'], 'match': match})
        for other in records[:index]:
            match = pair_match(row, other)
            if match: pairs.append({'new_case': row['case_id'], 'other_source': 'scin_review', 'other_id': other['case_id'], 'match': match})
    (LOCAL / 'image_manifest.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    if args.sheets: make_sheets(records)
    summary = {'prepared_on': '2026-10-18', 'purpose': 'Technical review only; no training/split assignment',
        'batch_sha256': config['batch_sha256'], 'selected_cases': len(batch), 'verified_images': len(records),
        'verified_by_class': dict(Counter(r['target_candidate'] for r in records)),
        'server_md5_verified_images': sum(r['server_md5_verified'] for r in records),
        'server_crc32c_verified_images': sum(r['server_crc32c_verified'] for r in records),
        'cases_with_max_original_confidence_below3': [r['case_id'] for r in records if (r['source_max_original_confidence'] or 0) < 3],
        'short_edge_below128': sum(min(r['width'], r['height']) < 128 for r in records),
        'comparisons_to_prior_fingerprints': len(records)*len(old), 'prior_images_including_excluded': len(old),
        'within_batch_fingerprint_comparisons': len(records)*(len(records)-1)//2,
        'duplicate_candidates': pairs, 'failures': failures,
        'notice_sha256': {name: hashlib.sha256((LOCAL/name).read_bytes()).hexdigest() for name in ('LICENSE.txt','README.md') if (LOCAL/name).exists()},
        'image_manifest_sha256': hashlib.sha256((LOCAL/'image_manifest.json').read_bytes()).hexdigest(),
        'test_pixels_read': 0, 'test_inference_performed': False, 'training_approved': False,
        'limitations': ['dHash is a candidate heuristic, not proof that all near duplicates are absent',
                       'Hashes for prior images are precomputed; no prior test image pixels opened',
                       'No independent clinical label verification or participant-independence claim']}
    output = ROOT / 'docs/ai/scin_preparation'; output.mkdir(parents=True, exist_ok=True)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))
    if failures: raise SystemExit(1)


if __name__ == '__main__': main()

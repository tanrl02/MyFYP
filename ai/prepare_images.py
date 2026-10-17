"""Prepare a local noncommercial research subset from the authors' ZIP archive.

Downloads only needed 8 MiB ranges, never follows original atlas image URLs.
No training, augmentation, diagnosis or application changes.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen
import zipfile

from PIL import Image, ImageOps

try:
    from ai.audit_metadata import ROOT, load_locked_sources, read_csv
except ModuleNotFoundError:
    from audit_metadata import ROOT, load_locked_sources, read_csv

ARCHIVE = 'https://zenodo.org/api/records/11101338/files/Fitzpatrick17k_CategorizedAbbrvs.zip/content'
ARCHIVE_SIZE = 1422904980
ARCHIVE_MD5 = '8f2640a6a45bbaf5c9b776d2d68fccc6'
BLOCK_SIZE = 8 * 1024 * 1024
DATA = ROOT / 'ai/data/fitzpatrick17k'


class RangeArchive(io.RawIOBase):
    """Bounded cached range reads; reject servers ignoring Range and redirects."""
    def __init__(self, cache, fetch=None, size=ARCHIVE_SIZE, block_size=BLOCK_SIZE):
        self.cache, self.fetch = Path(cache), fetch or self.fetch_range
        self.size, self.block_size, self.position = size, block_size, 0
        self.downloaded = 0
        self.last_block = (None, None)
        self.cache.mkdir(parents=True, exist_ok=True)

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.position

    def seek(self, offset, whence=0):
        position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        if whence not in (0, 1, 2) or position < 0:
            raise ValueError('Invalid archive seek')
        self.position = position
        return position

    @staticmethod
    def fetch_range(start, end, size):
        request = Request(ARCHIVE, headers={
            'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity',
            'User-Agent': 'SmartSkin-FYP-noncommercial-dataset-preparation'})
        for attempt in range(3):
            try:
                with urlopen(request, timeout=45) as response:
                    expected = f'bytes {start}-{end}/{size}'
                    if response.status != 206 or response.headers.get('Content-Range') != expected:
                        raise ValueError('Server did not return the requested archive range')
                    if response.geturl().split('?')[0] != ARCHIVE:
                        raise ValueError('Unexpected archive redirect')
                    content = response.read(end - start + 2)
                if len(content) != end - start + 1:
                    raise ValueError('Truncated or oversized archive range')
                return content
            except (OSError, TimeoutError):
                if attempt == 2: raise
                time.sleep(1 + attempt)

    def read(self, count=-1):
        end = self.size if count < 0 else min(self.size, self.position + count)
        output = bytearray()
        while self.position < end:
            start = self.position // self.block_size * self.block_size
            stop = min(self.size, start + self.block_size)
            path = self.cache / f'{start}-{stop - 1}.bin'
            if self.last_block[0] == start:
                content = self.last_block[1]
            elif path.exists():
                content = path.read_bytes()
                if len(content) != stop - start:
                    raise ValueError('Invalid cached range length; remove the affected cache file')
            else:
                if self.downloaded + stop - start > 512 * 1024 * 1024:
                    raise ValueError('512 MiB per-run network limit reached; rerun to resume')
                content = self.fetch(start, stop - 1, self.size)
                if len(content) != stop - start:
                    raise ValueError('Invalid range length')
                path.write_bytes(content)
                self.downloaded += len(content)
                print(f'Cached archive range; fetched {self.downloaded // 1048576} MiB this run', flush=True)
            self.last_block = (start, content)
            offset = self.position - start
            length = min(end - self.position, stop - self.position)
            output.extend(content[offset:offset + length])
            self.position += length
        return bytes(output)


def selected_rows(rows, rules):
    mapping = {}
    for target, aliases in rules['classes'].items():
        for source in aliases['fitzpatrick']:
            if source in mapping:
                raise ValueError('Overlapping label aliases')
            mapping[source] = target
    result, seen = [], set()
    for row in rows:
        if row['label'] not in mapping: continue
        identity = row['md5hash']
        if not re.fullmatch('[a-f0-9]{32}', identity) or identity in seen:
            raise ValueError('Invalid or repeated selected image identity')
        if row['partition'] not in ('train', 'val', 'test'):
            raise ValueError('Invalid source partition')
        seen.add(identity)
        result.append({**row, 'target_class': mapping[row['label']]})
    if set(mapping.values()) != {row['target_class'] for row in result}:
        raise ValueError('A selected class has no source rows')
    return sorted(result, key=lambda row: (row['target_class'], row['partition'], row['md5hash']))


def image_properties(content, expected_md5):
    if hashlib.md5(content).hexdigest() != expected_md5:
        raise ValueError('Image bytes do not match the source metadata MD5')
    with Image.open(io.BytesIO(content)) as image:
        image.verify()
    with Image.open(io.BytesIO(content)) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        width, height = image.size
        pixel_hash = hashlib.sha256(f'{width}x{height}:RGB:'.encode() + image.tobytes()).hexdigest()
        small = image.convert('L').resize((9, 8), Image.Resampling.LANCZOS).tobytes()
        dhash = 0
        for y in range(8):
            for x in range(8):
                dhash = dhash << 1 | int(small[y * 9 + x] > small[y * 9 + x + 1])
    return {'width': width, 'height': height, 'sha256': hashlib.sha256(content).hexdigest(),
            'pixel_sha256': pixel_hash, 'dhash': f'{dhash:016x}'}


def duplicate_flags(records):
    """Conservatively flag dHash neighbours; these are candidates for review."""
    flags = defaultdict(set)
    pairs = []
    for index, first in enumerate(records):
        for second in records[index + 1:]:
            distance = (int(first['dhash'], 16) ^ int(second['dhash'], 16)).bit_count()
            exact = first['pixel_sha256'] == second['pixel_sha256']
            if not exact and distance > 4: continue
            cross_split = first['partition'] != second['partition']
            reason = 'exact_pixels' if exact else 'possible_near_duplicate'
            for record in (first, second):
                flags[record['md5hash']].add(reason)
                if cross_split: flags[record['md5hash']].add('possible_split_leakage')
                if first['target_class'] != second['target_class']:
                    flags[record['md5hash']].add('label_conflict_candidate')
            pairs.append({'first': first['md5hash'], 'second': second['md5hash'],
                          'reason': reason, 'dhash_distance': distance, 'cross_split': cross_split})
    return flags, pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Fetch missing selected images from Zenodo ranges')
    args = parser.parse_args()
    _, sources = load_locked_sources()
    rules = json.loads((ROOT / 'ai/candidate_classes.json').read_text(encoding='utf-8'))
    selected = selected_rows(read_csv(sources['fitz_corrected_zenodo']), rules)
    output = ROOT / 'docs/ai/preparation'
    output.mkdir(parents=True, exist_ok=True)
    records, failures = [], []
    remote = RangeArchive(DATA / 'archive_ranges') if args.download else None
    archive = zipfile.ZipFile(remote) if remote else None
    members = {}
    if archive:
        for info in archive.infolist():
            if info.is_dir(): continue
            key = '/'.join(info.filename.split('/')[-2:])
            if key in members: raise ValueError('Ambiguous ZIP member')
            members[key] = info
    try:
        # Archive offset order minimises range downloads; final output order is stable.
        work = sorted(selected, key=lambda row: members[row['filepath']].header_offset) if archive else selected
        for index, row in enumerate(work):
            identity = row['md5hash']
            path = DATA / 'images' / f'{identity}.jpg'
            try:
                if not path.exists():
                    if not archive: raise ValueError('Image not downloaded; run with --download')
                    info = members[row['filepath']]
                    if info.file_size > 20 * 1024 * 1024:
                        raise ValueError('Oversized image')
                    content = archive.read(info)  # CRC is checked by zipfile.
                    props = image_properties(content, identity)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                else:
                    props = image_properties(path.read_bytes(), identity)
                records.append({'md5hash': identity, 'target_class': row['target_class'],
                                'source_label': row['label'], 'partition': row['partition'],
                                'archive_member': row['filepath'], 'original_url': row['url'],
                                'local_path': path.relative_to(ROOT).as_posix(), 'fst': row['fst'], **props})
            except (ValueError, OSError, zipfile.BadZipFile, KeyError) as error:
                failures.append({'md5hash': identity, 'reason': str(error)})
            if (index + 1) % 100 == 0: print(f'Checked {index + 1}/{len(work)} images', flush=True)
    finally:
        if archive: archive.close()
    records.sort(key=lambda row: (row['target_class'], row['partition'], row['md5hash']))
    flags, pairs = duplicate_flags(records)
    counts = defaultdict(Counter)
    for row in records:
        reasons = flags[row['md5hash']]
        if min(row['width'], row['height']) < 128: reasons.add('short_edge_under_128')
        row['quality_flags'] = '|'.join(sorted(reasons))
        row['manual_review'] = 'pending'
        row['preparation_status'] = 'quarantined' if reasons else 'mechanical_checks_passed'
        counts[row['target_class']][row['partition']] += 1
        counts[row['target_class']][row['preparation_status']] += 1
    def dump(name, value):
        (output / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    dump('summary.json', {'source_record': 'https://zenodo.org/records/11101338',
                         'archive_bytes': ARCHIVE_SIZE, 'published_whole_archive_md5': ARCHIVE_MD5,
                         'whole_archive_digest_verified': False,
                         'image_metadata_md5_verified': True,
                         'selected_entries': len(selected), 'verified_images': len(records),
                         'failures': failures, 'counts': dict(counts), 'duplicate_candidate_pairs': len(pairs),
                         'quarantined_images': sum(bool(row['quality_flags']) for row in records),
                         'visual_clinical_review': 'not performed; pending for every image',
                         'training_ready': False, 'pillow_version': Image.__version__})
    dump('duplicate_candidates.json', pairs)
    if records:
        with (output / 'image_manifest.csv').open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]))
            writer.writeheader(); writer.writerows(records)
    print(json.dumps({'verified': len(records), 'failures': len(failures), 'output': str(output)}, indent=2))
    if failures: raise SystemExit(1)


if __name__ == '__main__':
    main()

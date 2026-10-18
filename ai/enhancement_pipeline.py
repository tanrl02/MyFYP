"""Versioned, research-only model inputs and deterministic contrast correction."""
import hashlib
import json
from io import BytesIO
from pathlib import Path
from PIL import Image,ImageOps

ROOT=Path(__file__).resolve().parents[1]
CONTRACT='rgb-fit1600-png-v1'
VARIANTS=('baseline','train_jitter','contrast_blend')
MANIFEST=ROOT/'ai/data/enhancement-v1/manifest.json'


def digest(path):return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def prepare_input(content):
    # Model-input preparation, separate from HTTP file-size admission rules.
    with Image.open(BytesIO(content)) as image:
        if min(image.size)<32 or image.width*image.height>25_000_000:raise ValueError('Unsupported source geometry')
        pixels=ImageOps.exif_transpose(image).convert('RGB');pixels.thumbnail((1600,1600))
        clean=Image.new('RGB',pixels.size);clean.paste(pixels)
    buffer=BytesIO();clean.save(buffer,format='PNG',compress_level=6)
    data=buffer.getvalue()
    if len(data)>5*1024*1024:raise ValueError('Prepared output exceeds 5 MiB; no silent dropping or lossy fallback')
    return data


class ContrastBlend:
    def __call__(self,image):
        if image.mode!='RGB':raise ValueError('Expected RGB')
        corrected=ImageOps.autocontrast(image,cutoff=0,preserve_tone=True)
        return Image.blend(image,corrected,.25)

    def __repr__(self):return 'ContrastBlend(autocontrast_cutoff0_preserve_toneTrue_alpha0.25)'


def expected_config(control,variant,seed=3403):
    if variant not in VARIANTS or seed not in (3403,3404):raise ValueError('Unregistered trial/seed')
    config=dict(control,experiment='enhancement-v1',architectures=['efficientnet_b0'],seed=seed,
        report_folder='enhancement',input_contract=CONTRACT,enhancement_variant=variant,
        prepared_manifest_sha256_lf=digest(MANIFEST),preprocessing_code_sha256_lf=digest(Path(__file__)))
    config['preprocessing']=CONTRACT+'_'+control['preprocessing']
    if variant=='train_jitter':config['augmentation']+='_train_only_ColorJitter_brightness0.1_contrast0.1'
    if variant=='contrast_blend':config['preprocessing']+='_ContrastBlend_alpha0.25_both'
    return config


def validate_config(config,control):
    if config!=expected_config(control,config['enhancement_variant'],config['seed']):
        raise ValueError('Enhancement changed an undeclared setting or locked processing/cache')


def prepared_rows(config,raw):
    if config['input_contract']!=CONTRACT or digest(MANIFEST)!=config['prepared_manifest_sha256_lf']:
        raise ValueError('Prepared manifest/contract changed')
    if digest(Path(__file__))!=config['preprocessing_code_sha256_lf']:raise ValueError('Processing implementation changed')
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if manifest['contract']!=CONTRACT or manifest['test_pixels_read']!=0:raise ValueError('Wrong cache provenance')
    output={}
    for split in ('train','val'):
        cached=manifest['rows'][split]
        if len(cached)!=len(raw[split]):raise ValueError('Prepared split size changed')
        output[split]=[]
        for source,item in zip(raw[split],cached):
            if any(source[k]!=item['source'][k] for k in ('sha256','class_index','partition','target_class','local_path')):
                raise ValueError('Prepared input differs from source split/class/order')
            path=(ROOT/item['local_path']).resolve()
            if not path.is_relative_to(MANIFEST.parent.resolve()) or path.suffix!='.png':raise ValueError('Invalid prepared path')
            output[split].append(dict(source,local_path=item['local_path'],sha256=item['sha256']))
    return output

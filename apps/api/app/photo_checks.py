"""Local photo-admission checks, separate from simulated disease predictions."""
from collections import OrderedDict
from io import BytesIO
import hashlib
from pathlib import Path
from threading import Lock
from PIL import Image,ImageOps
from .photos import normalise_photo
from .store import RuleError

ROOT=Path(__file__).resolve().parents[3]
MODEL_PATH=ROOT/'ai/weights/photo-check/ViT-B-32.pt'
VERSION='photo-check-v1'
POSITIVE=(
    'a close-up photograph of human skin',
    'a close-up photograph of a skin rash on a human arm',
    'a close-up photograph of skin on a human face',
    'a close-up photograph of human skin on a hand',
    'a close-up photograph of human skin on a leg',
    'a clinical photograph of a human skin condition',
    'a close-up photograph of healthy human skin',
    'a close-up photograph of dark human skin')
NEGATIVE=(
    'a photograph of a household object', 'a photograph of furniture',
    'a photograph of food or a cup of coffee', 'a photograph of plants or grass',
    'a photograph of a cat or dog with fur', 'a photograph of a brick or stone wall',
    'a screenshot of a computer application', 'a scanned document or printed text',
    'a drawing or cartoon illustration', 'a chart or graphic design',
    'a microscope image of tissue', 'an x-ray or medical scan',
    'a close-up photograph of fabric or clothing', 'a photograph of wood or a floor',
    'a photograph of a phone or computer screen displaying a skin photograph',
    'a photograph of a fully clothed person taken from a distance')


def photo_quality(image):
    import numpy as np
    reasons=[]
    if min(image.size)<224:reasons.append('Use a higher-resolution photo, at least 224 pixels on each side.')
    sample=image.copy();sample.thumbnail((512,512))
    gray=np.asarray(sample.convert('L'),dtype=np.float32)
    std=float(gray.std());p5,p95=np.percentile(gray,(5,95))
    dark=float((gray<=8).mean());bright=float((gray>=248).mean())
    if dark>.98 and p95-p5<10:reasons.append('The photo is too dark to show skin detail. Use even lighting and retake it.')
    elif bright>.98 and p95-p5<10:reasons.append('The photo is washed out. Avoid glare or flash and retake it.')
    elif std<2:reasons.append('No clear surface detail is visible. Move back slightly, focus and retake the photo.')
    lap=4*gray[1:-1,1:-1]-gray[:-2,1:-1]-gray[2:,1:-1]-gray[1:-1,:-2]-gray[1:-1,2:]
    sharpness=float(lap.var()) if lap.size else 0
    if std>=2 and sharpness<4:reasons.append('The photo may be severely blurred. Hold still, tap to focus and retake it.')
    return reasons,{'gray_std':std,'laplacian_variance':sharpness,'dark_fraction':dark,'bright_fraction':bright}


class SkinScreener:
    def __init__(self):
        import clip
        import torch
        if not MODEL_PATH.exists():raise RuntimeError('Local skin-content model is missing')
        expected=clip.clip._MODELS['ViT-B/32'].split('/')[-2]
        if hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()!=expected:raise RuntimeError('Local model hash mismatch')
        torch.set_num_threads(4)
        model,self.preprocess=clip.load(str(MODEL_PATH),device='cpu',jit=False)
        model.eval()
        with torch.inference_mode():
            text=model.encode_text(clip.tokenize(list(POSITIVE+NEGATIVE)))
            self.text=text/text.norm(dim=-1,keepdim=True)
        self.visual=model.visual.eval()
        self.lock=Lock();self.cache=OrderedDict()

    def classify(self,image,key):
        import torch
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key);return self.cache[key]
            with torch.inference_mode():
                features=self.visual(self.preprocess(image).unsqueeze(0))
                features=features/features.norm(dim=-1,keepdim=True)
                scores=(features@self.text.T)[0]
                positive=float(scores[:len(POSITIVE)].max());negative=float(scores[len(POSITIVE):].max())
            margin=positive-negative
            status='likely_skin' if positive>=.22 and margin>=.015 else ('not_skin' if margin<-.015 else 'uncertain')
            result={'status':status,'positive_similarity':positive,'margin':margin}
            self.cache[key]=result
            if len(self.cache)>128:self.cache.popitem(last=False)
            return result


_screener=None
_initialise_lock=Lock()
def get_screener():
    global _screener
    with _initialise_lock:
        if _screener is None:_screener=SkinScreener()
    return _screener


def check_photo(content,screener=None):
    normalise_photo(content)  # Existing format, decode, geometry and byte limits.
    with Image.open(BytesIO(content)) as source:image=ImageOps.exif_transpose(source).convert('RGB')
    try:reasons,_=photo_quality(image)
    except ImportError as error:
        raise RuleError('Photo checking is unavailable. Start the API with its photo-check environment and retry.',503) from error
    status='not_checked'
    if not reasons:
        try:decision=(screener or get_screener()).classify(image,hashlib.sha256(content).hexdigest())
        except (ImportError,RuntimeError,OSError) as error:
            raise RuleError('Photo checking is unavailable. Start the API with its photo-check environment and retry.',503) from error
        status=decision['status']
        if status=='not_skin':reasons.append('This does not appear to be a close-up skin photo. Retake a photo of the affected skin, without objects or screens.')
        elif status!='likely_skin':reasons.append('Skin content could not be confirmed. Take a closer, clear photo of the skin without a screen or document.')
    return {'accepted':not reasons,'version':VERSION,'skin_content':status,'reasons':reasons,
            'message':'Photo checks passed. You can continue; this is not a diagnosis.' if not reasons else 'Retake or choose another photo.'}

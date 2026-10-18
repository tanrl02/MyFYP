"""Research-only storage recipes. Production helper is imported, never modified."""
from io import BytesIO
from pathlib import Path
import sys
from PIL import Image,ImageOps

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/api'))
from app.photos import normalise_photo

RECIPE_NAMES=('current_jpeg85','jpeg95_default','jpeg95_444','png_lossless')


def encode(clean,recipe):
    if recipe not in RECIPE_NAMES:raise ValueError('Unregistered recipe')
    buffer=BytesIO()
    if recipe=='png_lossless':clean.save(buffer,format='PNG',compress_level=6)
    elif recipe=='jpeg95_444':clean.save(buffer,format='JPEG',quality=95,subsampling=0)
    else:clean.save(buffer,format='JPEG',quality=85 if recipe=='current_jpeg85' else 95)
    return buffer.getvalue()


def render_variants(content):
    # Apply the actual current input/file constraints before every candidate.
    current,width,height=normalise_photo(content)
    with Image.open(BytesIO(content)) as image:
        output=ImageOps.exif_transpose(image).convert('RGB')
        output.thumbnail((1600,1600))
        clean=Image.new('RGB',output.size);clean.paste(output)
    if clean.size!=(width,height) or encode(clean,'current_jpeg85')!=current:
        raise ValueError('Research geometry/JPEG85 no longer matches production helper')
    return {name:current if name=='current_jpeg85' else encode(clean,name) for name in RECIPE_NAMES},clean.size

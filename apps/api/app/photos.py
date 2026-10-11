from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
from .store import RuleError

MAX_BYTES = 5 * 1024 * 1024

def normalise_photo(content):
    if not content or len(content) > MAX_BYTES:
        raise RuleError('Choose a photo no larger than 5 MB.', 422)
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise RuleError('Choose a JPEG, PNG or WebP image.', 422)
            if image.width < 32 or image.height < 32 or image.width * image.height > 25_000_000:
                raise RuleError('Photo must be at least 32 pixels per side and no more than 25 megapixels.', 422)
            image.load()
            output = ImageOps.exif_transpose(image).convert('RGB')
            output.thumbnail((1600, 1600))
            # Save pixels only: discard EXIF/GPS and all source file metadata.
            clean = Image.new('RGB', output.size)
            clean.paste(output)
            buffer = BytesIO()
            clean.save(buffer, format='JPEG', quality=85)
            return buffer.getvalue(), clean.width, clean.height
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise RuleError('The file is not a supported readable photo.', 422) from error

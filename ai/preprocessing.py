"""Full-frame geometry alternative for the controlled preprocessing comparison."""
import torch
from torchvision.transforms import functional as F, InterpolationMode

MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)


def fit_geometry(width, height, size=224):
    if min(width, height, size) <= 0: raise ValueError('Positive dimensions required')
    scale = size / max(width, height)
    new_width = max(1, min(size, round(width * scale)))
    new_height = max(1, min(size, round(height * scale)))
    return new_width, new_height, (size - new_width) // 2, (size - new_height) // 2


class FullFrame224:
    """Bicubic fit inside 224, centred exact ImageNet-mean padding, normalisation.

    No cropping or stretching apart from unavoidable integer size rounding.
    Padding is applied in floating RGB [0,1] before normalisation, becoming zero.
    RGB conversion and EXIF correction belong to the shared FrozenImages loader.
    """
    def __call__(self, image):
        if image.mode != 'RGB': raise ValueError('Expected EXIF-corrected RGB input')
        width, height, left, top = fit_geometry(*image.size)
        resized = F.to_tensor(F.resize(image, [height, width], interpolation=InterpolationMode.BICUBIC, antialias=True))
        canvas = torch.tensor(MEAN, dtype=resized.dtype).view(3, 1, 1).expand(3, 224, 224).clone()
        canvas[:, top:top + height, left:left + width] = resized
        return F.normalize(canvas, MEAN, STD)

    def __repr__(self):
        return 'FullFrame224(bicubic fit-long-edge224, centred floating ImageNet-mean padding, ImageNet normalisation)'

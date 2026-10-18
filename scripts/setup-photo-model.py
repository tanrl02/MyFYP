"""Download the pinned official CLIP weights once; runtime never downloads them."""
import hashlib
from pathlib import Path
import urllib.request

SHA = '40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af'
URL = f'https://openaipublic.azureedge.net/clip/models/{SHA}/ViT-B-32.pt'
TARGET = Path(__file__).resolve().parents[1] / 'ai/weights/photo-check/ViT-B-32.pt'


def main():
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.exists():
        with TARGET.open('rb') as source:
            verified = hashlib.file_digest(source, 'sha256').hexdigest() == SHA
        if verified:
            print('Verified existing photo-check model.'); return
    temporary = TARGET.with_suffix('.download')
    try:
        with urllib.request.urlopen(URL, timeout=120) as response, temporary.open('wb') as output:
            while chunk := response.read(1024 * 1024): output.write(chunk)
        with temporary.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != SHA:
                raise RuntimeError('Downloaded model hash does not match; model not installed.')
        temporary.replace(TARGET)
    finally:
        temporary.unlink(missing_ok=True)
    print('Photo-check model installed and SHA-256 verified.')


if __name__ == '__main__': main()

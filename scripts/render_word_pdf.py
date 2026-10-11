"""Use the packaged DOCX PNG pipeline with a locally Word-exported PDF.

Windows adaptation: Word supplies layout, pypdfium2 supplies rasterisation.
Neither LibreOffice nor an external upload is needed.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import tempfile
import pypdfium2 as pdfium
from PIL import ImageChops

SKILL = Path(r'C:\Users\chenr\.codex\plugins\cache\openai-primary-runtime\documents\26.1009.11318\skills\documents')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace.resolve()
    exported = root / 'tmp/docx/word-render'
    out = exported / 'pages'
    spec = importlib.util.spec_from_file_location('packaged_docx_renderer', SKILL / 'render_docx.py')
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    tempfile.tempdir = str(root / 'tmp/docx')
    renderer.convert_to_pdf = lambda *a, **kw: (str(exported / 'candidate.pdf'), 'Verified local Word PDF export')
    def raster(pdf_path, dpi, output_folder, **kwargs):
        paths = []
        pdf = pdfium.PdfDocument(pdf_path)
        for index in range(len(pdf)):
            path = Path(output_folder) / f'word-{index + 1}.png'
            pdf[index].render(scale=dpi / 72).to_pil().save(path)
            paths.append(str(path))
        return paths
    renderer.convert_from_path = raster
    paths = renderer.rasterize(str(root / 'tmp/docx/approved-design.docx'), str(out), 100, verbose=False, emit_pdf=False)
    baseline = pdfium.PdfDocument(str(exported / 'baseline.pdf'))
    candidate = pdfium.PdfDocument(str(exported / 'candidate.pdf'))
    assert len(baseline) == len(candidate) == len(paths)
    changed = []
    for i in range(len(candidate)):
        a = baseline[i].render(scale=100/72).to_pil().convert('RGB')
        b = candidate[i].render(scale=100/72).to_pil().convert('RGB')
        if a.size != b.size or ImageChops.difference(a, b).getbbox():
            changed.append(i+1)
    (exported / 'changed-pages.json').write_text(json.dumps(changed), encoding='utf-8')
    print(f'Generated {len(paths)} candidate page PNGs; pixel-changed pages: {changed}')

if __name__ == '__main__':
    main()

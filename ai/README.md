# AI metadata audit

This is a metadata audit, not a trained model. Read [the findings](../docs/ai/DATASET_AUDIT.md) before selecting training data.

From the MyFYP root, using the existing Python environment:

```powershell
.\.venv\Scripts\python.exe ai/audit_metadata.py
.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -v
```

The first command runs offline when the five source CSVs are present. On a new checkout, add `--download` to fetch only the five metadata files in `metadata_sources.json`. It never follows image URLs. Each file is limited to 10 MB and verified against a locked SHA-256 before saving or use. Upstream changes deliberately fail verification; review them before updating the registry.

Raw metadata is ignored under `ai/data/`; aggregate results are tracked under `docs/ai/data_audit/`. `--output-dir` selects another output directory. No additional Python packages are required. Candidate class mappings and SCIN screening thresholds are explicit in `candidate_classes.json`. The five-class mapping is fixed for this preparation checkpoint; final training taxonomy and visual label suitability remain open.

## Local image preparation

Read [the source decision](../docs/ai/SOURCE_AND_LABEL_DECISION.md) first. The existing environment already has Pillow 12.3.0; the image preparation script uses it without installing or changing application dependencies.

```powershell
.\.venv\Scripts\python.exe ai/prepare_images.py --download
.\.venv\Scripts\python.exe ai/prepare_images.py
```

The first command fetches needed 8 MiB blocks from the authors' fixed Zenodo ZIP and extracts only the selected manifest entries. Adjacent unselected archive bytes may occur inside cached blocks; the full archive is not fetched. There is a 512 MiB per-run network limit. Reruns resume from ignored local cache/images. Network access is opt-in; the second command checks existing image files offline. Every selected image must match the source metadata MD5, pass ZIP CRC on extraction, and decode successfully. SHA-256 and EXIF-normalised pixel hashes are recorded alongside dimensions and a difference hash. No files from archive paths are extracted directly; output names are validated source hashes.

Outputs in `docs/ai/preparation/` preserve the authors' partitions. Exact-pixel duplicates, dHash distance <=4 candidate pairs, potential cross-split matches, conflicting labels and short edges under128px are flagged. Flagged images are quarantined in the manifest, not deleted or moved between splits. All images remain pending human review. Neither difference hashing nor the absence of flags proves clinical quality, patient independence or freedom from all near duplicates. Raw images and archive ranges remain ignored under `ai/data/`. No model training or augmentation is performed.

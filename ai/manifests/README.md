# Frozen research manifests

`eight-class-v1/` is the current eight-condition research baseline dataset: 1,374 train, 193 validation, 401 test, 108 excluded from the original 2,076 files. See [the freeze report](../../docs/ai/FROZEN_DATASET.md).

Image paths are relative to the MyFYP repository root; binary images remain ignored under `ai/data/fitzpatrick17k/images/`. Use the frozen CSVs and `class_to_index.json` for model work, not the larger preparation manifest. Source annotations are inherited; no clinical validation or model performance is claimed.

Do not edit version files to change the split or exclusions. `ai/freeze_dataset.py` recreates the expected export from locked metadata, the preparation manifest and both review records, rechecks image hashes and refuses any conflicting existing version. Create a new dataset version for later changes. Text checksums are LF-normalised for cross-platform checkouts.

Source/licence provenance is retained in [the source decision](../../docs/ai/SOURCE_AND_LABEL_DECISION.md). These data are prepared for local noncommercial FYP research; image collection redistribution or clinical deployment is outside this freeze.

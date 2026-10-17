# Frozen eight-class research dataset

Completed 18 October 2026. Version `eight-class-v1` is the current conservative research baseline split. It contains **1,968 images**, with **108 exclusions**. No model has been trained. The application, running services and Word report were unchanged.

## Counts after exclusions

| Class | Train | Validation | Test | Included |
|---|---:|---:|---:|---:|
| Acne |287|42|81|410|
| Eczema |118|16|34|168|
| Psoriasis |356|49|105|510|
| Folliculitis |98|12|35|145|
| Urticaria |88|13|26|127|
| Allergic contact dermatitis |209|30|58|297|
| Seborrhoeic dermatitis |79|11|23|113|
| Scabies |139|20|39|198|
| Total |1,374|193|401|1,968|

Original source partition assignments are retained. No validation/test image was reassigned to training. The source pool remains 2,076 files; exclusions do not delete or modify any original file.

## Review completed and decisions

The agent inspected all 29 newly flagged thumbnails and 24 stratified sample thumbnails from the three added conditions, then compared four images at larger resolution. Combined with the first review, technical visual triage covered all 107 flagged images and 64 sampled images, 171 unique images in total. This is partial visual QA, not an exhaustive visual inspection or dermatologist verification of disease labels.

All 107 mechanical flags remain excluded in this conservative first version, including low resolution, possible duplicate relationships and possible label conflicts. Some hash matches are visually distinct; those images are not automatically restored. The exclusions intentionally favour reproducibility over recovering every potentially usable image.

One sampled test image, `563c07deb927f07e5fac7da4ce43a1f7`, showed strongly overlapping photograph content with already-quarantined `692165241f3c213969652e1e0f6e90cd`. Different framing meant that the simple hash screen had not flagged the sampled image. It is additionally excluded as a conservative related-scene decision, not a diagnosis or assertion of patient identity. Thus the total is 107 mechanical exclusions plus one manual exclusion. A separately compared pair of scalp photographs was not grouped because the visible structures did not establish a matching image.

The [expanded review record](../../ai/expanded_review.json) contains all newly inspected IDs, sampling method, observations and the manual decision. The [initial review record](../../ai/visual_review.json) preserves the earlier 78 flagged and 40 sampled images, including 11 visually matching crop/resize groups. No clinical labels were changed. Source watermarks, masks and varied anatomical framing remain dataset limitations.

## Scope of this freeze

The freeze follows the flags-plus-stratified-sample procedure requested for this checkpoint: whole-set mechanical checks, visual triage of every flag and a sample from every class/split, conservative exclusions and inherited source annotations. This replaces earlier blanket wording about per-image visual approval for a research training export. It does **not** establish clinical correctness, patient independence or suitability for real diagnosis. Every image has not been visually reviewed. Dataset status distinguishes frozen research manifests from clinical validation.

The accepted subset has no exact MD5, SHA-256 or decoded-pixel hash value shared across partitions. This does not prove that every perceptual duplicate or related case has been detected. There are no patient identifiers in the metadata to support a patient-independent split claim. Test images received pretraining data-quality screening; later model predictions and test metrics must not guide tuning or further favourable curation of this version.

## Files and reproducibility

The version is saved under [ai/manifests/eight-class-v1](../../ai/manifests/eight-class-v1/dataset.json):

- `train.csv`, `val.csv`, `test.csv`: selected image IDs, paths, original labels, target labels, class indices, dimensions, skin-type annotations and hashes.
- `excluded.csv`: all 108 excluded rows and their reasons.
- `class_to_index.json`: fixed eight-class output ordering.
- `dataset.json`: split/class counts, QA coverage, input fingerprints, output hashes and limitations.

Input fingerprints use canonical JSON to avoid line-ending-only differences. Output hashes use LF-normalised text. Raw source images remain in ignored local storage. The [source/licence decision](SOURCE_AND_LABEL_DECISION.md) still applies: local noncommercial FYP research with original source attribution retained; no public/commercial image redistribution is authorised by this export.

```powershell
.\.venv\Scripts\python.exe ai/freeze_dataset.py
.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -q
```

The freeze script runs offline, rechecks all 2,076 local image SHA-256 values, validates source membership/labels/partitions and review coverage, and checks cross-split exact hashes. Rerunning the same inputs accepts the existing version unchanged. Any different export requires a new version; the script refuses to overwrite it. The entire expected file set is checked before writing to an existing version.

Verification: 21 tests passed, including five new tests for exclusion conservation, preserved source labels/splits, cross-split exact-pixel duplicates, incomplete review/manual exclusion evidence and version immutability. The full freeze run and repeated run both verified all source images and produced the same version contents.

Next small task: select and configure an ImageNet-pretrained baseline and a reproducible training run using these fixed manifests. Fine-tuning, validation-based model selection, final test evaluation and app integration remain separate work.

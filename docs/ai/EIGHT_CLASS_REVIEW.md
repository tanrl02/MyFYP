# Eight-class scope and visual review checkpoint

Follow-up complete: the [frozen dataset checkpoint](FROZEN_DATASET.md) records review of the 29 new flags and 24 added-class samples, one additional manual exclusion and the current fixed research splits. The preparation counts below remain historical screening evidence.

18 October 2026. The user selected the recommended eight-condition scope. This extends the first five-class batch; it does not change the application's simulated predictions or the Word report.

## Selected data

All 2,076 selected images are now local and passed original-byte MD5, ZIP extraction CRC and decode checks, with zero acquisition/verification failures. The 630 added entries are allergic contact dermatitis, seborrhoeic dermatitis and scabies. The same [source/licence decision](SOURCE_AND_LABEL_DECISION.md) applies; only the authors' fixed noncommercial archive was used. No original atlas image URLs were followed.

| Working class | Verified images | Train | Validation | Test | Quarantined |
|---|---:|---:|---:|---:|---:|
| Acne |420|294|42|84|10|
| Eczema |176|123|18|35|8|
| Psoriasis |534|374|53|107|24|
| Folliculitis |182|127|18|37|37|
| Urticaria |134|94|13|27|7|
| Allergic contact dermatitis |314|220|31|63|17|
| Seborrhoeic dermatitis |113|79|11|23|0|
| Scabies |203|142|20|41|4|
| Total |2,076|1,453|206|417|107|

The exact source label `seborrheic dermatitis` is retained in machine-readable mappings; the table uses the UK spelling. Both dermatitis classes stay separate from eczema. Acne retains the previously documented grouping of `acne` and `acne vulgaris`. There is no inferred healthy/other class or new clinical relabelling.

Ten candidates were compared in [class_scope.csv](review/class_scope.csv). Rosacea has 79 metadata entries (55/8/16 train/validation/test), and vitiligo has 113 (79/11/23); neither is selected in this checkpoint. These counts alone do not establish suitable image quality. No exact tinea-versicolor or herpes-zoster label was found in the corrected label table, so those earlier possibilities were not added from this source.

## Actual visual review performed

The agent inspected all 78 initially flagged image thumbnails and a reproducible 40-image sample from the original five classes, spanning their train/validation/test partitions. A larger comparison sheet was inspected for 17 images when checking specific groups. This was technical image-content triage, not dermatologist review or disease diagnosis. Contact sheets remain local and ignored by Git.

Eleven pairs/groups were visually judged to show matching crops or resized versions. Five span source splits, demonstrating that zero repeated MD5 values does not establish freedom from visual duplication. Examples are `3befc60a`/`f1a0afa5`, `3e00be95`/`e0a38024`, `c17a51bd`/`dfae71d7`, `e46b53d5`/`cd67345f` (train/validation), and `50ce8968`/`6f3da617` (train/test). Full image hashes and observations are in [visual_review.json](../../ai/visual_review.json). These are matches of photograph content, not assertions about patient identity.

Two recorded hash-match examples showed clearly different photograph content: `0d03469c`/`6fa3bc93` and `9dee2cef`/`c2c7aed8`. The simple difference hash also joins several visually unrelated images into larger components. Automated flags must not be counted as confirmed duplicates or evidence of incorrect disease labels. The 101 initial candidate pairs were not all individually adjudicated. None of the 78 original quarantines was automatically reinstated.

The sample showed varied framing, lighting and backgrounds, source watermarks/borders, nail-only views and intimate anatomical views alongside general skin photographs. This creates a capture-domain question for later training/app evaluation; the sample is not a clinical assessment. No source image is added to app demo records or shown in the patient UI.

The reviewed image IDs, original working-file SHA-256 and source checkpoint `ff908dc` are recorded. The [visual triage CSV](review/visual_triage.csv) explicitly distinguishes the 78 flagged images from the 40 sampled images and records the current expanded-set flags. It does not claim exhaustive review.

## Expanded mechanical screen and remaining work

The eight-class screen flags 107 distinct images, leaving 1,969 without mechanical flags. It finds 159 candidate pairs involving 98 images; 67 images have a candidate relationship across splits and 74 have a candidate relationship across class labels. Nineteen have a short edge below 128 px. Reasons overlap. These are screening results, not confirmed error counts. The newly expanded screen adds 29 flagged image IDs beyond the original 78.

Provided split membership is preserved. Unflagged entries currently number 1,374 train/193 validation/402 test; files are not deleted or moved. No training manifests have been approved or exported. See [the current preparation summary](preparation/summary.json), [image manifest](preparation/image_manifest.csv) and [review summary](review/summary.json).

Next manageable task: visually triage the 29 additional flagged images and sample the three added classes, record conservative exclusion decisions, then freeze research training manifests. Remaining ambiguous matches stay excluded; test images must not be reassigned to training. Full clinical label validation and patient independence remain unestablished. Dataset size/class imbalance and source watermarks must be considered when interpreting later model results. No model training or accuracy measurement occurred in this checkpoint.

## Verification

Sixteen audit/preparation/review tests passed. The review exporter validates image IDs, sample membership and cross-split group evidence; contact-sheet regeneration checks image SHA-256. A complete offline recheck verified all 2,076 images again. Audit, preparation and review outputs were regenerated and checked for byte-for-byte agreement. Application code, installed dependencies, running services and the Word report were untouched.

The corrected subset and its published partitions come from the [authors' dataset repository](https://github.com/kakumarabhishek/Corrected-Skin-Image-Datasets) and [project page](https://derm.cs.sfu.ca/critique/). Our visual observations above are this project's findings, not claims made by those authors.

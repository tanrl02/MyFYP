# Kaggle Dermnet suitability audit

Completed 18 October 2026. Dataset: [shubhamgoel27/dermnet](https://www.kaggle.com/datasets/shubhamgoel27/dermnet), version 1. This audit fetches descriptions and file-list JSON only. **No images were downloaded, viewed, merged or used for training.**

## Verified metadata coverage

The public Kaggle API returned 98 pages with **19,559 image file entries**, in 23 categories: **15,557 train and 4,002 test**. Summed file sizes exactly matched the publisher's 1,850,517,236-byte total. The publisher's description names `dermnet.com` as the original source. These are metadata counts, not verified usable-image or patient counts. Existing image content, accessibility, diagnoses, resolution, corruption and overlap with Fitzpatrick have not been verified.

The raw snapshots remain ignored under `ai/data/dermnet/raw`. Tracked [metadata locks](dermnet_audit/metadata_lock.json) preserve page hashes and entries, and [the summary](dermnet_audit/summary.json) preserves all folder counts and split totals. `ai/audit_dermnet.py` checks cached page hashes and aggregate byte coverage before producing results.

## Eight-condition mapping review

| Our target | Kaggle folder | Publisher train / test | Decision from metadata |
|---|---|---:|---|
| Acne |Acne and Rosacea Photos|840 / 312|Mixed category; needs verified image-level labels|
| Eczema |Eczema Photos|1,235 / 309|Candidate for review; not yet approved training data|
| Psoriasis |Psoriasis pictures Lichen Planus and related diseases|1,405 / 352|Mixed category; needs verified image-level labels|
| Folliculitis |No dedicated folder|—|Broader bacterial-infections folder is not an exact mapping|
| Urticaria |Urticaria Hives|212 / 53|Candidate for review; not yet approved training data|
| Allergic contact dermatitis |Poison Ivy Photos and other Contact Dermatitis|260 / 65|Mixed/unspecified contact-dermatitis scope|
| Seborrhoeic dermatitis |No dedicated folder|—|Do not map the similarly named keratoses/benign-tumours folder|
| Scabies |Scabies Lyme Disease and other Infestations and Bites|431 / 108|Mixed category; needs verified image-level labels|

`Atopic Dermatitis Photos` separately contains 489 train and 123 test entries. Do not silently combine it with eczema or allergic contact dermatitis; review the clinical label policy and source annotations first. Likewise, do not infer a single disease from a mixed folder or assign labels using filename keywords. This audit identifies folder-name compatibility, not clinically confirmed diagnoses.

The two most direct folder-name matches contain **1,447 publisher-training entries** (1,235 eczema and 212 urticaria). Their 362 publisher-test entries are counted separately, not reassigned to training. This does not mean 1,447 unique, correctly labelled, independent new training examples are available. The [machine-readable mapping review](../../ai/dermnet_mapping_review.json) explicitly remains review-only and must not be passed to the training pipeline as an approved mapping.

## Split and duplicate concerns

There are 397 case-insensitive basenames present on both sides of the publisher split, including cross-category collisions. More specifically, **270 acne/rosacea pairs have the same category, filename and byte size in both train and test**. These are suspected duplicate candidates; without file bytes/hashes they are not confirmed content duplicates. The metadata provides no verified patient/case grouping for leakage-safe splitting.

Before any later use, hash and decode images, inspect near duplicates and related-image sequences, and compare against all existing Fitzpatrick train/validation/test and excluded examples. Do not trust the publisher train/test split without that check or equate filename uniqueness with patient independence. Keep source-specific evaluation separate from the current atlas validation. The existing 401-image research test set remains reserved.

## Permission findings

The [uploader's dataset card](https://www.kaggle.com/shubhamgoel27/dermnet/kernels) declares **CC BY-NC-ND4.0** and describes collecting from Dermnet.com. A declaration by an uploader does not establish its authority for every source image. The [original site](https://dermnet.com/) currently shows a redesign notice; original image-use terms or a grant covering this redistribution were not verified during this audit.

The [CC legal text](https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.en) distinguishes noncommercial reproduction from sharing adapted material and grants only rights the licensor can grant. The ND label alone is not treated here as a universal AI-training prohibition. Source authority, the intended training/augmentation use, and any planned sharing of images or derived material still need a defensible basis. This audit does not make a legal determination about model weights.

**Dermnet.com and DermNet NZ are different sources.** [DermNet NZ's image licence](https://dermnetnz.org/image-licence) expressly restricts AI training/testing of its free website images and offers a separate licensable AI dataset. That NZ restriction is not automatically applied to this Kaggle collection attributed to Dermnet.com. Conversely, a Kaggle licence tag does not override another rightsholder's terms.

Current project decision: **review-only; no automatic ingestion or training**. Resolve source/use documentation before an acquisition/training step, and obtain finer image labels for mixed folders before considering them for our eight-condition model. No message has been sent to the uploader or image owner by the agent.

## Concrete next increment

A deterministic, ignored metadata plan (`ai/data/dermnet/review_batch.json`) identifies **20 training-folder eczema and 20 training-folder urticaria images** for a possible first review batch. It has no image bytes and confers no training approval. After source/use documentation is established, acquire this bounded batch, check content/quality/duplicates/label suitability and decide whether expansion is justified. Do not download the whole collection first.

While that clarification is pending, complete the SCIN metadata/label screening as the documented alternative. The interrupted SCIN audit had only read metadata and official documentation; it produced no new image batch or model. Keep the eight-class final scope, the user-selected centre-crop model, and the current dataset intact. Combining sources is conditional on verified mapping and data quality; larger combined counts do not guarantee 90% precision.

## Verification and reproduction

Two focused tests passed for split/category counts, filename-collision interpretation, duplicate manifest entries and invalid layout rejection. The complete offline audit passed against all 98 cached page hashes; aggregate byte totals matched the publisher. A repeated offline run reproduced both aggregate and metadata-lock outputs byte-for-byte. No GPU, dependency installation, application test or phone check is needed for this metadata-only change.

```powershell
.\.venv\Scripts\python.exe ai/audit_dermnet.py
.\.venv\Scripts\python.exe -m unittest ai.tests.test_dermnet_audit -v
```

On a fresh snapshot, `--fetch` requests public JSON metadata only, bounded to 120 pages/16MB. It stops on unexpected paths, version/size changes, pagination loops or incomplete byte coverage. New online responses may contain changing counters/tokens, so byte-identical fresh downloads are not promised. Cached offline reproduction is the verification target. No image URLs are requested. Raw snapshots and image-reference lists stay untracked; the original source conditions and attribution must be retained for any future acquisition.

The app continues to use simulated AI. Word edits, real authentication, services and model weights are unchanged. The pre-existing user modification to `BASELINE_SETUP.md` remains untouched.

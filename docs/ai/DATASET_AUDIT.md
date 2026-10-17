# Skin dataset metadata audit — 18 October 2026

Current class scope: [eight-class review checkpoint](EIGHT_CLASS_REVIEW.md). The table below records the initial five-class comparison; regenerated machine-readable class counts now include the three user-selected additions.

Follow-up: the [source and label decision](SOURCE_AND_LABEL_DECISION.md) resolves the apparent licence conflict by distinguishing newer metadata from the older noncommercial image release. It records the working five-class preparation route and supersedes the initial acquisition hold below. Image preparation evidence is recorded separately; historical metadata counts remain unchanged.

## Decision

**Fitzpatrick17k-C is the strongest conditional training candidate for the current common-condition scope.** A provisional five-class subset contains 1,446 metadata entries. Resolve image-source permissions and availability, then review the label mapping before downloading a selective image subset. No dataset is training-ready from metadata alone.

SCIN is useful as a possible later source of phone-style evaluation images, but its limited clear acne/psoriasis labels make it a weaker sole training source. Do not combine sources until duplicate and label compatibility checks are complete. All nine application modules remain required; these five classes describe the proposed classifier only.

## Counted evidence

Five public CSVs were downloaded and locked by SHA-256 in [the source registry](../../ai/metadata_sources.json). No image collection was downloaded or visually reviewed. Counts below are metadata counts, not verified usable images.

| Proposed class | SCIN screened cases | Fitzpatrick17k-C entries | Train | Validation | Test |
|---|---:|---:|---:|---:|---:|
| Acne | 33 | 420 | 294 | 42 | 84 |
| Eczema | 231 | 176 | 123 | 18 | 35 |
| Psoriasis | 32 | 534 | 374 | 53 | 107 |
| Folliculitis | 68 | 182 | 127 | 18 | 37 |
| Urticaria | 131 | 134 | 94 | 13 | 27 |
| Total | 495 | 1,446 | 1,012 | 144 | 290 |

Fitzpatrick counts retain the authors' published partitions. Acne combines the explicit source labels `acne` and `acne vulgaris`; this mapping needs documented review before training. Other classes use exact source labels. Related subtypes such as dyshidrotic eczema, pustular psoriasis and urticaria pigmentosa are excluded. No healthy/other class is inferred from unlabelled records.

### SCIN

Release 1.0.0 contains 5,033 matching unique case and label rows, with 10,407 image-path references representing 10,380 distinct paths. Fifteen paths occur across cases. This is a metadata reuse check; actual image duplicates, visual quality and availability were not tested.

1,972 cases have no weighted label, 925 have tied leading labels, and 2,136 have a unique leading label. The audit's heuristic screen requires a unique leading weight of at least 0.60, a margin of at least 0.20, at least one `DEFAULT_YES_IMAGE_QUALITY_SUFFICIENT` rating and an image reference. Across all conditions, 1,268 cases pass. Screened case counts must not be interpreted as confirmed diagnoses or independent image counts.

The weights summarise dermatologist differential rankings; they are not calibrated disease probabilities. Gradability is a case-level screen here: it does not establish that every referenced image is suitable. Keep all images from a case together, then group duplicate images before any new split. There is no participant identifier in the audited tables, so patient-independent splitting cannot be established. US contributor photos do not demonstrate performance in Malaysia.

### Original and corrected Fitzpatrick17k

The original metadata has 16,577 entries. The corrected manifest has 11,394 entries: 7,975 train, 1,139 validation and 2,280 test. Its pinned GitHub and canonical Zenodo manifests agree on image identifier, label and partition membership. There are no repeated MD5 identifiers or literal image URLs across partitions in this corrected metadata. This does not rule out perceptual duplicates, incorrect labels or overlap with other datasets.

The corrected manifest is preferred over randomly splitting the original atlas collection because the authors explicitly address duplicates and outliers. Patient identifiers are unavailable, so the published partitions are not proven patient-independent. Fitzpatrick skin-type annotations are not proof of diagnostic correctness. The smallest proposed test class has only 27 examples, and the largest class is about four times the smallest; report uncertainty and per-class results.

## Licence and suitability review

| Source | Published declarations | Consequence |
|---|---|---|
| [SCIN](https://github.com/google-research-datasets/scin) | [Custom SCIN Data Use Licence](https://github.com/google-research-datasets/scin/blob/main/LICENSE), including attribution and no re-identification | Preserve source/licence/changes as required; do not describe it as MIT or CC BY. |
| [Original Fitzpatrick17k](https://github.com/mattgroh/fitzpatrick17k) | README declares CC BY-NC-SA 3.0; images originate from dermatology atlases | Check image rights, redistribution and attribution conditions before acquisition/export. |
| [Corrected dataset repository](https://github.com/kakumarabhishek/Corrected-Skin-Image-Datasets), [Zenodo version 12739457](https://zenodo.org/records/12739457) | Repository code is Apache 2.0; Zenodo metadata declares CC BY 4.0 | These declarations differ from the original dataset terms. Code/metadata licences do not settle the rights to all underlying images. Image-source rights remain unresolved. |
| [Stanford DDI](https://aimi.stanford.edu/datasets/ddi-diverse-dermatology-images) | Research Use Agreement through the [dataset site](https://ddi-dataset.github.io/index.html) | Source review only: no metadata downloaded or class counts computed. Its 656 pathology-confirmed images from 570 patients serve a different, lesion-focused task; not the proposed primary common-condition training source. |

The licence comparison records published statements, not a resolved grant covering all images. Preserve provenance and clarify conflicting declarations with the dataset providers if the source documentation cannot resolve them.

## Small implementation sequence

1. **Next task:** resolve image-source rights/access and finalise the five-class mapping. Produce a source/label decision before selective image preparation.
2. Prepare the permitted subset: image availability, corruption/quality review, exact/perceptual duplicate grouping, source overlap and fixed split manifests. Recount after exclusions. Keep test images untouched by tuning and augment training images only after splitting.
3. Train a modest ImageNet-pretrained baseline, then fine-tune selected layers. MobileNetV3 and EfficientNet-B0 are candidates to compare later, not selected or benchmarked models. Record seeds, weights, preprocessing, experiments and model versions.
4. Evaluate macro-F1, per-class precision/recall, confusion matrix and uncertainty; examine skin-tone/source subgroups only where sample sizes and annotations support it. Tune any abstention threshold on validation data. A confidence threshold alone does not detect arbitrary non-skin images. No accuracy target is promised.
5. Integrate the evaluated model through the existing Python backend, preserving model version and explicit uncertainty in saved assessments. Phone photo performance needs separate validation; doctor suggestions remain advisory. Existing simulation stays in place until this work is complete.

## Reproduction and limits

See [audit instructions](../../ai/README.md), [summary](data_audit/summary.json) and [class-count CSV](data_audit/candidate_counts.csv). The source registry records URLs, byte sizes and SHA-256 hashes; corrected GitHub metadata uses commit `ac655ac5a5b93264c57d69d6d520778d915bfc89`, and the canonical Zenodo version is `12739457`. SCIN schema and weighting are documented in the [official schema](https://github.com/google-research-datasets/scin/blob/main/dataset_schema.md) and [demonstration notebook](https://github.com/google-research-datasets/scin/blob/main/scin_demo.ipynb).

This increment changes no application routes, predictions, services, dependencies or Word report. No model was trained and no image-level clinical or quality judgement was made.

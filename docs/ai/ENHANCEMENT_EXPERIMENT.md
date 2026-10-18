# Controlled image-enhancement experiment

Predeclared 18 October 2026 before model fitting. Test whether mild enhancement improves the eight-condition task, with a consistent common model-input flow. Do not assume an improvement or promise 85% accuracy. The live app remains simulated, with its current storage helper unchanged.

## Three matched trials

All trials freshly start from the same cached ImageNet EfficientNet-B0 weights, with seed 3403. Preserve the frozen 1,374/193 training/validation cases, eight labels, all BatchNorm affine/running state frozen, batch 16, weighted training cross-entropy, AdamW, 3 head-only epochs and up to 15 full-feature fine-tuning epochs. Keep feature/head learning rates 0.0001/0.0005, cosine schedule and five-stale-epoch early stopping after at least six fine-tuning epochs. Select each checkpoint by accuracy, macro-F1, then lower validation loss. No SCIN additions, label changes or final-test pixels.

Prepare every training/validation input once with EXIF correction, RGB conversion, aspect-preserving fit within 1600 x 1600, metadata-free PNG encoding and a strict 5 MiB output bound. Originals stay unchanged. Any preparation failure aborts rather than silently dropping a case. Cache source/derived SHAs, split/order/classes and a versioned contract. Hash-check prepared images on every training load. Input transport limits and model-input preparation are separate concerns; this research model-input helper does not install a new HTTP upload policy.

| Trial | Training | Validation and future prediction |
|---|---|---|
| Baseline | Common prepared input; existing crop/flip augmentation | Common prepared input; existing deterministic model transform |
| Mild training jitter | Add brightness and contrast factors randomly sampled within 0.9–1.1 | Same as baseline; no random jitter |
| Gentle contrast blend | Blend 25% tone-preserving autocontrast (cutoff 0) with 75% prepared RGB; then existing crop/flip | Identical deterministic contrast blend; then deterministic model transform |

All use bicubic model geometry and ImageNet channel normalisation. The contrast method is global, not CLAHE or a learned lesion segmenter. “Tone-preserving” is the Pillow operation's name, not evidence of clinical colour fidelity. Colour correction and train-only augmentation are separate experiments; do not combine them after seeing scores. Random augmentation sequences need not match after adding jitter's random draws. Existing 65.28% raw-input control is historical context, not the matched baseline for this prepared-input experiment.

## Verification and decision rule

Smoke-test each trial's head and full stages. Checkpoint verification checks immutable history/selection, frozen BatchNorm and changed features, and reproduces all clean validation metrics/confusion counts. Also evaluate each selected model on two predeclared synthetic brightness probes (0.8 and 1.2), applied before deterministic correction/model geometry. These reuse the same 193 cases, not 386 independent patients or a real-camera benchmark.

An enhancement is **promising for replication** only if, compared with the matched baseline, its selected checkpoint has higher clean accuracy AND macro-F1, no individual class recall loss above 0.10 absolute, AND no lower mean accuracy over the two lighting probes. The 10-point recall guard is an engineering screening choice on small supports, not a clinically validated safety limit. Report every class and every trial even if rejected. The best passing candidate is ranked by the original accuracy/F1/loss rule.

If a candidate passes, replicate the baseline and that candidate with the predeclared second seed 3404, using the same settings/data. Call an improvement replicated only if the same guard passes for seed 3404 as well; otherwise report inconclusive evidence and retain the baseline as reference. If none passes at seed 3403, stop after the three trials and report no verified enhancement benefit. Do not add more variants, tune contrast strength, remove weak classes or inspect the final test to rescue the result. Even a replicated development gain is not final-test or clinical validation.

## Results

Stopped at the user's request on 18 October 2026 to prioritise photo quality and skin-content admission. The seed-3403 baseline completed: 120/193 validation cases correct (62.18%), macro-F1 0.5585; checkpoint reproduction and the two lighting probes passed. Mild training jitter was interrupted after epoch 7 and has no completed/verified result. Contrast blend completed smoke checks only. No enhancement comparison or replication conclusion can be drawn. Do not use partial-run scores to select a model. Aggregate evidence is retained under `docs/ai/enhancement/`.

Prepared-input cache and run checkpoints remain ignored. Word, real accounts, source images, eight classes, current offline user-selected pointer and disease simulation remain unchanged. Final-test pixels were not used.

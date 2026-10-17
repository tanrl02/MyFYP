# Full-frame preprocessing comparison

Experiment date: 18 October 2026. Tests the framing hypothesis documented in [the error review](ERROR_ANALYSIS.md). This is a validation-based development experiment on all eight agreed classes, not a clinical or phone-domain evaluation.

## Fixed comparison procedure

The candidate starts again from the **same frozen-head baseline epoch-8 checkpoint** as fine-tuning v1, not from the fine-tuned incumbent. Source SHA-256 is locked in `ai/full_frame_config.json`. The dataset remains frozen `eight-class-v1`: 1,374 training, 193 validation and 401 reserved test images.

Only image geometry changes. The candidate fits the complete RGB frame inside 224 × 224 with bicubic interpolation, preserving aspect ratio up to integer pixel rounding. It centres the resized image on floating-point ImageNet-mean-coloured padding before ImageNet normalisation. Padding therefore normalises exactly to zero. EXIF correction and RGB conversion still occur in the shared hash-checking loader. No image region is deliberately cropped; no stretching to a square occurs. Very extreme aspect ratios need a one-pixel minimum short edge. Context preservation can reduce the image's effective resolution, and padding can become a learned cue, so improvement is not assumed.

The original comparator uses short-edge resize 256 followed by centre crop 224. Both use the same training-only horizontal flip probability 0.5. All other experimental settings remain the same: ten epochs, seed 3403, batch 16, AdamW feature LR 1e-5/classifier LR 1e-4/weight decay 1e-4, feature blocks 6–8 plus classifier trainable, all BatchNorm parameters/statistics and earlier layers frozen, inverse-training-frequency weighted cross-entropy, unweighted validation loss and checkpoint selection by macro-F1 then lower loss. The configuration guard rejects other changed settings. Experiment names and descriptive augmentation text necessarily differ; flip behaviour does not.

Each checkpoint is replayed using its own preprocessing. In particular, the source baseline and previous fine-tuned incumbent always use their original centre-crop pipeline. The candidate must beat the incumbent on validation macro-F1, then lower loss on an exact F1 tie, to replace it. An exact tie retains the incumbent. Scores are reported across all eight classes; no per-class choice between models is made.

The implementation uses [Torchvision bicubic resizing](https://docs.pytorch.org/vision/stable/generated/torchvision.transforms.functional.resize.html). Mean padding uses floating tensors to avoid RGB integer rounding. Tests verify landscape/portrait corner markers survive in the correct locations, padding normalises to zero, geometry and centred placement obey integer-rounding limits, square input has no padding, repeated transforms agree and non-geometric configuration changes are rejected.

## Run and verify

```powershell
.\.venv-ai\Scripts\python.exe -m unittest discover -s ai/tests -v
.\.venv-ai\Scripts\python.exe ai/train_finetune.py --mode smoke --run-id efficientnet-b0-full-frame-smoke-v1 --experiment full-frame --device cuda
.\.venv-ai\Scripts\python.exe ai/train_finetune.py --mode train --run-id efficientnet-b0-full-frame-v1 --experiment full-frame --device cuda
.\.venv-ai\Scripts\python.exe ai/train_finetune.py --mode verify --run-id efficientnet-b0-full-frame-v1 --device cuda
```

Training/smoke require a new run ID for a deliberate rerun. Verification reads the saved run configuration, so it does not depend on the CLI experiment default. Existing crop runs remain supported. Full-frame evidence is written to `docs/ai/full_frame_results`, preserving previous `finetune_results`. All binary checkpoints and raw images remain local and ignored by Git.

## Results

All ten epochs completed successfully. The candidate's **epoch 8** was selected by validation macro-F1. Epoch 10 was not substituted just because its accuracy was slightly higher.

| Validation measure (193 images) | Frozen-head baseline | Centre-crop fine-tuning v1 | Full-frame candidate |
|---|---:|---:|---:|
| Accuracy |56.48% (109/193)|59.59% (115/193)|58.55% (113/193)|
| Macro precision |48.25%|53.07%|53.28%|
| Macro-F1 |0.4855|0.5214|0.5288|
| Unweighted cross-entropy |1.2832|1.2834|1.2391|

The **full-frame candidate is selected under the predeclared macro-F1 rule**. Against centre-crop fine-tuning, macro-F1 increased by only 0.0074 and macro precision by 0.21 percentage points; accuracy decreased by 1.04 points (two fewer correct predictions). The result is a marginal development gain, not demonstrated statistical significance or an improvement in every class. It does not establish 90% precision, clinical reliability or phone-photo performance.

| Inherited source class | Support | Centre-crop precision / recall / F1 | Full-frame precision / recall / F1 |
|---|---:|---:|---:|
| Acne |42|0.7872 / 0.8810 / 0.8315|0.8182 / 0.8571 / 0.8372|
| Eczema |16|0.2308 / 0.1875 / 0.2069|0.2609 / 0.3750 / 0.3077|
| Psoriasis |49|0.6863 / 0.7143 / 0.7000|0.7250 / 0.5918 / 0.6517|
| Folliculitis |12|0.3333 / 0.5000 / 0.4000|0.4667 / 0.5833 / 0.5185|
| Urticaria |13|0.5833 / 0.5385 / 0.5600|0.5556 / 0.3846 / 0.4545|
| Allergic contact dermatitis |30|0.5000 / 0.3667 / 0.4231|0.4483 / 0.4333 / 0.4407|
| Seborrhoeic dermatitis |11|0.6250 / 0.4545 / 0.5263|0.4167 / 0.4545 / 0.4348|
| Scabies |20|0.5000 / 0.5500 / 0.5238|0.5714 / 0.6000 / 0.5854|

Eczema correct classifications increased from 3/16 to 6/16, but its precision remains only 26.09%: 6 correct among 23 eczema predictions, with 17 false positives. Folliculitis and scabies F1 improved; psoriasis, urticaria and seborrhoeic dermatitis F1 decreased. This experiment does not establish that cropping caused all previous errors or that padding is generally superior. The source baseline was trained with cropping, so this comparison specifically evaluates the two fine-tuning pipelines starting from that same checkpoint.

All **33 AI tests** and the full-frame GPU smoke passed. Independent verification reloaded the full-frame candidate, centre-crop incumbent and baseline with `weights_only=True`, verified source/incumbent hashes, class mappings, dataset locks, selection and recorded metrics, and replayed all 193 validation images for each model with its own geometry. Accuracy, macro-F1, per-class metrics and confusion counts matched exactly; losses matched within 1e-6. Frozen parameters and BatchNorm buffers stayed identical to the source, while blocks 6–8 and the classifier changed. Both previous checkpoints are retained. No second complete training run or cross-seed replication was performed.

Tracked [summary and selection evidence](full_frame_results/summary.json), [epoch aggregates](full_frame_results/epochs.json) and [per-class CSV](full_frame_results/per_class.csv) preserve the comparison. The local candidate checkpoint is `ai/runs/efficientnet-b0-full-frame-v1/best.pt`; its SHA and measured epoch runtime are in the summary. Raw images and weights remain ignored. Selection is for offline research: no model has been integrated into the app.

All **401 test images remain unevaluated**. No labels/exclusions, application code, services, dependencies or Word files were changed. The pre-existing user modification to `BASELINE_SETUP.md` remains untouched.

Next manageable task: audit additional permitted, suitably labelled data for eczema and the dermatitis classes before downloading or training. Current marginal gains and remaining class errors favour addressing coverage/annotation limitations over repeatedly extending training on the same small validation split. Keep the eight-class scope and existing reserved test data; any later data addition needs explicit provenance, duplicate checks and a new versioned training manifest.

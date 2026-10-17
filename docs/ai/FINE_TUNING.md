# Upper-block fine-tuning experiment

Experiment date: 18 October 2026. This is one development experiment on the frozen eight-condition dataset, starting from the verified baseline checkpoint. The app continues to use simulated predictions. Word edits remain deferred.

## Predeclared procedure

- Same frozen `eight-class-v1` images, class mapping and source partitions: 1,374 train, 193 validation, 401 reserved test. Test CSV integrity is checked but its rows and images are never loaded by this runner.
- Initialise from baseline epoch 8, SHA-256 `c13595ca48d53e69ecf83feec287920494285c10c1d273b590ab7ba289e41d1c`. Reject a different source hash or class/dataset mapping. No weight downloads or dependency changes.
- EfficientNet-B0 feature blocks 6, 7 and 8 plus classifier train: 3,140,132 parameters. Earlier feature blocks remain frozen in evaluation mode. All BatchNorm affine parameters and running statistics remain frozen, including those in selected blocks. Upper-block stochastic depth and classifier dropout are active during training.
- AdamW, feature learning rate 0.00001, classifier learning rate 0.0001, weight decay 0.0001, batch 16, seed 3403, ten epochs, four CPU threads, zero loader workers. Fresh optimiser; this is a new training stage, not a resumed baseline optimiser.
- Training-only horizontal flip with probability 0.5 before the original RGB/EXIF, bicubic resize 256, centre crop 224 and ImageNet normalisation. No colour changes, extra random crops or validation augmentation. Inherited centre-crop limitations remain.
- Same inverse-training-frequency weighted cross-entropy; validation loss remains unweighted. Select the best fine-tuned epoch by validation macro-F1, then lower validation loss, earliest epoch on exact tie. Compare it with the original baseline rather than assuming it must be better.
- Keep the 401-image test set reserved until model selection is finished. No threshold search or test-based tuning in this experiment.

This package changes both trainable layers and training augmentation; it cannot separately establish the contribution of each. It is a single-seed development comparison, not a generalisation guarantee or a claim of 90% precision. Small validation classes and inherited, clinically unverified labels limit conclusions. Accuracy, macro precision, macro-F1 and per-class precision/recall/F1 must be reported together.

The implementation follows [PyTorch's transfer-learning workflow](https://docs.pytorch.org/tutorials/beginner/transfer_learning_tutorial.html) and uses [Torchvision horizontal flips](https://docs.pytorch.org/vision/stable/generated/torchvision.transforms.RandomHorizontalFlip.html). Learning rates, block boundary and frozen BatchNorm policy are explicit experiment choices, not promised optimal settings.

## Run and verify

From the MyFYP root, using the existing isolated training environment:

```powershell
.\.venv-ai\Scripts\python.exe -m unittest discover -s ai/tests -v
.\.venv-ai\Scripts\python.exe ai/train_finetune.py --mode smoke --run-id efficientnet-b0-finetune-smoke-v1 --device cuda
.\.venv-ai\Scripts\python.exe ai/train_finetune.py --mode train --run-id efficientnet-b0-finetune-v1 --device cuda
.\.venv-ai\Scripts\python.exe ai/train_finetune.py --mode verify --run-id efficientnet-b0-finetune-v1 --device cuda
```

Existing training/smoke run IDs are immutable; a deliberate rerun requires a new ID. Smoke performs one update on eight training images and discards the model. It verifies that every selected feature block and the classifier changed, while every frozen parameter and buffer stayed identical. The automated test additionally detects accidental frozen-buffer mutation.

The separate verification mode checks completion, metadata and checkpoint selection, verifies the source hash and frozen data, reloads with `weights_only=True`, checks trainable/frozen state differences, and replays all 193 validation images for both baseline and fine-tuned checkpoints. Confusion counts, accuracy, per-class metrics and macro-F1 must match exactly; unweighted loss tolerance is 1e-6. It exports aggregate summaries and CSV under `docs/ai/finetune_results`. No source photos or binary weights are tracked in Git.

## Results

All ten epochs completed successfully. The predeclared selection rule chose **epoch 7**. Epoch 10 had higher macro precision (53.48%) but lower macro-F1 (0.5199); it was not substituted after seeing those results.

| Validation measure (193 images) | Frozen-head baseline | Fine-tuned epoch 7 |
|---|---:|---:|
| Accuracy |56.48% (109/193)|59.59% (115/193)|
| Macro precision (equal weight per class) |48.25%|53.07%|
| Macro-F1 |0.4855|0.5214|
| Unweighted cross-entropy |1.2832|1.2834|

Accuracy increased by 3.11 percentage points (six additional correct validation classifications); macro precision increased by 4.82 points and macro-F1 by 0.0360. Validation loss did not improve. These are descriptive changes on a single development split, not established statistical significance or independent test performance. The 90% precision target has not been reached.

| Inherited source class | Validation support | Baseline precision | Fine-tuned precision | Fine-tuned recall | Fine-tuned F1 |
|---|---:|---:|---:|---:|---:|
| Acne |42|75.51%|78.72%|88.10%|0.8315|
| Eczema |16|21.43%|23.08%|18.75%|0.2069|
| Psoriasis |49|76.19%|68.63%|71.43%|0.7000|
| Folliculitis |12|31.58%|33.33%|50.00%|0.4000|
| Urticaria |13|36.84%|58.33%|53.85%|0.5600|
| Allergic contact dermatitis |30|50.00%|50.00%|36.67%|0.4231|
| Seborrhoeic dermatitis |11|50.00%|62.50%|45.45%|0.5263|
| Scabies |20|44.44%|50.00%|55.00%|0.5238|

Eczema still has only 3/16 correct classifications; four are predicted as psoriasis and four as allergic contact dermatitis. Psoriasis precision decreased while recall increased. Seborrhoeic dermatitis precision increased while recall decreased. These trade-offs reinforce the need to evaluate all classes rather than optimise one headline percentage. They do not justify changing inherited labels without qualified evidence.

Recorded epoch work totalled 201.39 seconds, excluding startup, smoke checks and replay verification. The selected local model is `ai/runs/efficientnet-b0-finetune-v1/best.pt` (ignored), SHA-256 `b7eb8b2762f4f5d246ad29b07c64c1dfcccea83ab6d38992da781e04f792ead8`. Run configuration, ten-epoch history and completion marker remain alongside it.

Independent checkpoint reload reproduced the validation metrics for both models: accuracy, macro-F1, per-class scores and confusion counts matched exactly; loss matched within 1e-6. Earlier/frozen parameters and all BatchNorm buffers were identical to the baseline, while each selected feature block and the classifier changed. The GPU smoke check passed and all 29 AI tests passed; the two new boundary tests also passed after their optional-environment skip guard was added. Backend Python can still run the dependency-free metric tests and skips neural tests without installing Torch. No full second training run was performed.

Tracked [summary and provenance](finetune_results/summary.json), [ten-epoch aggregates](finetune_results/epochs.json) and [per-class CSV](finetune_results/per_class.csv) preserve the evidence. All **401 test images remain unevaluated**. No new model is integrated into the app; Word, app dependencies and clinic services are unchanged. The pre-existing user edit to `BASELINE_SETUP.md` remains untouched.

Next manageable task: examine eczema/dermatitis errors and the available training examples, document annotation/preprocessing limitations, and choose one further targeted experiment. Avoid promising that more epochs or a larger model will reach 90%. Additional model selection continues to use development data; final test evaluation comes after that process is complete.

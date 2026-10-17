# Three-model comparison: protocol and results

Started 18 October 2026 following the user's request to compare models and target at least 85% accuracy. This experiment interprets 85% as overall classification accuracy, not a displayed confidence score or a claim that every condition has 85% precision. Results must be measured; reaching the target is not promised.

## Predeclared comparison

Compare ImageNet-pretrained **EfficientNet-B0**, **ResNet-50** and **DenseNet-121** under the same new protocol. The previous B0 experiments remain historical references, not matched controls for this stronger training schedule. The new B0 run is the matched control.

Data remains the same frozen eight-condition research subset: 1,374 training images, 193 validation images and 401 reserved test images. No SCIN images are added during this architecture comparison: the 37 reviewed SCIN candidates still need their separate versioned data/split definition. No class is removed or merged. No test image is read for fitting, model selection or final scoring in this experiment.

| Setting | Shared protocol |
|---|---|
| Seed | 3403 |
| Batch size | 16 |
| Optimiser / decay |AdamW / 0.0001|
| Head warm-up |3 epochs, output head only, LR 0.001|
| Full fine-tuning |Up to 15 further epochs, all non-BatchNorm parameters; feature LR 0.0001, head LR 0.0005|
| Frozen state |All BatchNorm affine parameters and running statistics throughout; all features additionally frozen during warm-up|
| Scheduler |Cosine during fine-tuning, eta_min 1e-6|
| Early stopping |Five consecutive fine-tuning epochs without improvement, only after at least six fine-tuning epochs|
| Training loss |Cross-entropy weighted by inverse training-class frequency only|
| Validation loss |Unweighted cross-entropy|
| Training augmentation |RandomResizedCrop 224, scale 0.85–1.0, ratio 0.9–1.1; horizontal flip 0.5; bicubic; ImageNet normalisation|
| Validation |Common bicubic short-edge resize 256, centre crop 224, ImageNet normalisation|
| Checkpoint selection |Among fine-tuning epochs only: highest validation accuracy, then macro-F1, then lower loss; earliest exact tie|
| Precision |FP32|

All models get the same maximum budget and stopping rule, though actual early-stopped epoch counts may differ. Weight versions are EfficientNet_B0_Weights.IMAGENET1K_V1, ResNet50_Weights.IMAGENET1K_V2 and DenseNet121_Weights.IMAGENET1K_V1. Their ImageNet training histories and architectural regularisation differ; this is a controlled practical comparison of these pretrained model configurations, not isolation of architecture alone. Common preprocessing deliberately replaces model-specific default resize/interpolation choices.

User priority changed to accuracy for this comparison, so its selection rule explicitly differs from the earlier macro-F1-based experiments. Historical selection rules/results are retained. Report accuracy, macro precision, macro-F1, per-class precision/recall/F1, confusion counts, parameter count and measured training time. A model with higher overall accuracy may still have unacceptable weak classes. An ImageNet benchmark accuracy does not establish skin-condition accuracy.

## Implementation and verification

`ai/compare_models.py` implements fetch/smoke/train/verify. Weights are downloaded only in explicit fetch mode from the official PyTorch model URLs, hash-prefix checked and recorded by full SHA. Runs are immutable and store config, environment, pretrained source hash, history and best checkpoint in ignored `ai/runs`. Smoke tests both training stages without retaining a model. Unit checks cover all three output shapes/stage boundaries/frozen state and the selection rule.

Independent verify mode requires a complete run, checks dataset/class/weight/checkpoint selection, validates frozen BatchNorm state and an actual feature change, then replays all 193 validation images. Accuracy, macro-F1, per-class metrics and confusion counts must match exactly; loss tolerance 1e-6. Tracked aggregates are written under `docs/ai/model_comparison`, not the older experiment folders. No application model is automatically changed by an experimental result.

References: [Torchvision ResNet-50](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.resnet50.html), [DenseNet-121](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.densenet121.html), [EfficientNet-B0](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.efficientnet_b0.html). Repository dependency versions remain pinned and unchanged.

## Execution

For each architecture, use a fresh run ID:

```powershell
.\.venv-ai\Scripts\python.exe ai/compare_models.py --mode fetch --architecture resnet50
.\.venv-ai\Scripts\python.exe ai/compare_models.py --mode smoke --architecture resnet50 --run-id comparison-v1-resnet50-smoke
.\.venv-ai\Scripts\python.exe ai/compare_models.py --mode train --architecture resnet50 --run-id comparison-v1-resnet50
.\.venv-ai\Scripts\python.exe ai/compare_models.py --mode verify --architecture resnet50 --run-id comparison-v1-resnet50
```

Equivalent runs use `efficientnet_b0` and `densenet121`. Training needs cached weights and makes no network requests. Existing clinic services, app predictions, original Word report, authentication and the user-modified `BASELINE_SETUP.md` remain unchanged.

## Results

All three runs completed 18 epochs on the local RTX 4060 Laptop GPU. Each selected checkpoint passed a separate verification pass that reproduced all recorded validation metrics and confusion counts on 193 images. These are single-seed development results, not final test accuracy.

| Model | Correct / 193 | Accuracy | Macro precision | Macro-F1 | Selected epoch | Parameters | Epoch time total |
|---|---:|---:|---:|---:|---:|---:|---:|
| EfficientNet-B0 | 126 | **65.28%** | **64.42%** | **0.6003** | 15 | 4,017,796 | 5.20 min |
| DenseNet-121 | 113 | 58.55% | 59.73% | 0.5233 | 14 | 6,962,056 | 6.09 min |
| ResNet-50 | 112 | 58.03% | 58.35% | 0.5299 | 15 | 23,524,424 | 5.78 min |

Times sum training/validation epoch durations and exclude weight acquisition, startup and checkpoint verification; they are not deployment latency measurements. The historical user-selected B0 partial-fine-tuning run achieved 115/193 (59.59%), macro precision 53.07% and macro-F1 0.5214 under a different protocol. The new B0 therefore adds 11 correct predictions (+5.70 percentage points), but that historical comparison does not isolate the cause of improvement.

**The 85% target was not reached.** With 193 images it requires at least 165 correct predictions; the best run is 39 correct predictions short. No class or difficult image was dropped, no confidence threshold was used to hide errors, and the 401 reserved test images remain unevaluated. The previous and new runs use the same repeatedly consulted validation set, so the measured improvement needs replication and eventual independent evaluation.

### Leading model: condition-level checks

| Condition | Validation images | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Acne | 42 | 86.05% | 88.10% | 0.8706 |
| Eczema | 16 | 50.00% | 43.75% | 0.4667 |
| Psoriasis | 49 | 61.67% | 75.51% | 0.6789 |
| Folliculitis | 12 | 50.00% | 50.00% | 0.5000 |
| Urticaria | 13 | 100.00% | 53.85% | 0.7000 |
| Allergic contact dermatitis | 30 | 50.00% | 50.00% | 0.5000 |
| Seborrhoeic dermatitis | 11 | 36.36% | 36.36% | 0.3636 |
| Scabies | 20 | 81.25% | 65.00% | 0.7222 |

Urticaria's 100% precision is only seven correct predictions out of seven predictions of that class; six true urticaria images were missed. It is not evidence of perfect recognition. Eczema improves over the previous B0 (recall 3/16 to 7/16), while seborrhoeic dermatitis falls from 5/11 to 4/11 and psoriasis recall rises but its precision falls. Overall gains do not establish improvement for every condition. Class supports are small and labels are inherited research annotations, not independently confirmed diagnoses.

### Recommendation and next bounded experiment

Use the new **EfficientNet-B0 as the leading research candidate**: it leads this matched comparison on all three aggregate metrics and has the fewest parameters. Its checkpoint is `ai/runs/comparison-v1-efficientnet_b0/best.pt`, SHA256 `ea91f5ca8a6dc278c0faf5570c7a1db6e4bdcef67a55e17f88846368ec6879c9`. Keep the original user-selected offline pointer in `ai/model_selection.json` unchanged during this comparison; app predictions remain simulated. No candidate is presented as ready for clinical use.

Next small experiment: predeclare a limited lower-learning-rate versus partial-freezing comparison for B0, then replicate the chosen setting with additional seeds. Separately finish the versioned case-grouped SCIN expansion/holdout definition before any new source enters training. Focus data review on the weakest classes, especially eczema, contact dermatitis and seborrhoeic dermatitis. Only two reviewed SCIN seborrhoeic-dermatitis cases are available so far, so that batch cannot establish a reliable improvement for this class. Neither more tuning nor adding the current 37 candidates guarantees 85%; stop bounded experiments and reassess data/labels if progress plateaus. Reserve the final test until the pipeline and model are fixed.

### Saved evidence

- [Aggregate comparison JSON](model_comparison/comparison.json), plus architecture-specific `summary.json` and complete `epochs.json` histories.
- [Aggregate metric chart](model_comparison/metrics.png), [per-condition F1](model_comparison/per_class_f1.png), [learning curves](model_comparison/learning_curves.png). All three charts visually reviewed.
- Two new unit tests passed, covering all three architectures' output sizes, both freeze stages and checkpoint ranking. All three GPU smoke checks and all three checkpoint validation replays passed. Test images evaluated: zero.

Recreate the aggregates and figures after the three verified runs:

```powershell
.\.venv\Scripts\python.exe ai/summarize_model_comparison.py
.\.venv-ai\Scripts\python.exe ai/plot_model_comparison.py
```

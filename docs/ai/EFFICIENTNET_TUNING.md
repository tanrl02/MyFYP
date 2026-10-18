# EfficientNet-B0: two bounded tuning trials

Predeclared 18 October 2026 before either training run. The matched architecture comparison favoured B0: 126/193 validation images correct (65.28%), macro-F1 0.6003. The target remains at least 85% overall accuracy across all eight classes, requiring 165/193 correct on this development set. This target is not guaranteed.

## Controlled settings

Both trials start afresh from the same cached ImageNet weights as the comparison B0, not its selected checkpoint. Keep seed 3403, frozen 1,374 training / 193 validation images, three head-only warm-up epochs, up to 15 further fine-tuning epochs, batch 16, AdamW, inverse-frequency weighted training loss, cosine schedule, image transformations and frozen BatchNorm parameters/statistics identical to the control. Checkpoint ranking remains validation accuracy, macro-F1, then lower unweighted loss; early stopping remains five stale fine-tuning epochs after at least six fine-tuning epochs. Final-test pixels remain unused. No SCIN images or new classes enter training.

| Trial | Trainable image features | Feature / head LR after warm-up | Change versus control |
|---|---|---|---|
| Existing control | All non-BatchNorm features | 0.0001 / 0.0005 | Prior matched B0 run |
| Lower LR, full | All non-BatchNorm features | 0.00003 / 0.00015 | Both rates multiplied by 0.3 |
| Partial freezing | Blocks 6, 7, 8; lower blocks frozen | 0.0001 / 0.0005 | Feature-block freezing/mode only |

The partial variant also keeps frozen lower blocks in evaluation mode, disabling their stochastic-depth training behaviour. This is part of the freezing policy. It need not generate exactly the same stochastic augmentation sequence after warm-up as full fine-tuning. Neither trial changes the classifier warm-up LR (0.001). Do not mix additional hyperparameter changes into either trial after seeing scores. Report every completed trial and retain the control even if both alternatives lose.

## Execution and checks

`ai/compare_models.py` now accepts `--config`; its default architecture-comparison behaviour is retained. Strict tuning-config validation allows only the settings in the table. The partial variant hashes every frozen lower-block/BatchNorm parameter and buffer each epoch; verification also checks that every selected upper block changed. Independent checkpoint replay must reproduce aggregate validation metrics and confusion counts. Verify the three warm-up epochs against the existing control as a matching check. Weights, images and run checkpoints remain ignored; only aggregate evidence is tracked.

```powershell
.\.venv-ai\Scripts\python.exe ai/compare_models.py --mode train --architecture efficientnet_b0 --config ai/tuning_lower_lr_full_config.json --run-id tuning-v1-lower-lr-full
.\.venv-ai\Scripts\python.exe ai/compare_models.py --mode verify --architecture efficientnet_b0 --run-id tuning-v1-lower-lr-full
.\.venv-ai\Scripts\python.exe ai/compare_models.py --mode train --architecture efficientnet_b0 --config ai/tuning_partial_freeze_config.json --run-id tuning-v1-partial-freeze
.\.venv-ai\Scripts\python.exe ai/compare_models.py --mode verify --architecture efficientnet_b0 --run-id tuning-v1-partial-freeze
```

Single-seed results on a repeatedly used validation set are development evidence. Seed replication and final independent evaluation remain separate work. Do not move validation cases into training, drop weak classes or evaluate the final test while tuning. The current offline model pointer, app simulation and Word report remain unchanged during this experiment.

## Results

Both trials completed and their selected checkpoints passed separate validation replays. All three warm-up epochs in each trial match the control's recorded aggregate metrics and confusion counts; loss matches within 1e-6. The partial-freezing replay verified frozen lower-block/BatchNorm state and actual changes in each selected block (6, 7, 8).

| Setting | Correct / 193 | Accuracy | Macro precision | Macro-F1 | Selected / completed epochs |
|---|---:|---:|---:|---:|---:|
| Control, full | 126 | 65.28% | **64.42%** | **0.6003** | 15 / 18 |
| Lower LR, full | 124 | 64.25% | 59.29% | 0.5764 | 13 / 18 |
| Partial freezing | 128 | **66.32%** | 61.06% | 0.5854 | 12 / 17 |

Partial freezing stopped after five fine-tuning epochs without a better ranked score. It is the winner under the predeclared accuracy-first rule, adding two correct predictions (+1.04 percentage points). It is not a uniform improvement: macro-F1 and macro precision decline. The lower-LR variant did not beat the control on any of those three metrics. Its validation loss is lower (1.2805 versus 1.6292), which does not establish better classification accuracy or clinical calibration.

### Per-condition trade-off

| Condition | Support | Control F1 | Lower-LR F1 | Partial-freezing F1 |
|---|---:|---:|---:|---:|
| Acne | 42 | 0.8706 | 0.8478 | 0.8506 |
| Eczema | 16 | 0.4667 | 0.3636 | 0.2963 |
| Psoriasis | 49 | 0.6789 | 0.7158 | 0.7850 |
| Folliculitis | 12 | 0.5000 | 0.5000 | 0.5000 |
| Urticaria | 13 | 0.7000 | 0.6364 | 0.6400 |
| Allergic contact dermatitis | 30 | 0.5000 | 0.5263 | 0.4561 |
| Seborrhoeic dermatitis | 11 | 0.3636 | 0.4211 | 0.4706 |
| Scabies | 20 | 0.7222 | 0.6000 | 0.6842 |

Partial freezing recognises 42/49 psoriasis images versus 37/49 for the control, but only 4/16 eczema images versus 7/16. This is why the higher overall accuracy should not be described as a generally superior classifier. Seborrhoeic-dermatitis recall remains 4/11; its higher F1 comes from fewer false-positive predictions rather than more true cases recognised.

**85% remains unmet:** 165 correct predictions are needed; partial freezing reaches 128, leaving a gap of 37. These small validation differences are not evidence of a reliable gain on new patients or phone photos. No final-test image was evaluated, no class was removed, and no selective confidence rejection was applied.

### Candidate decision and evidence

Retain both finalists for a bounded seed-replication comparison: the original full-feature control for its stronger macro metrics, and partial freezing for its accuracy-first result. Repeat both settings with two additional predeclared seeds before selecting a pipeline. Do not silently replace the current user-selected offline pointer or integrate this small validation gain into the app. If replication does not show a consistent useful gain, stop this tuning branch and prioritise reviewed data/labels and the versioned SCIN case-grouped development holdout. None of these steps guarantees 85%.

Partial-freezing checkpoint: `ai/runs/tuning-v1-partial-freeze/best.pt`, SHA256 `ae07a0f6e25c033441e2d77ce09676084f201da765a5a74b11148665759c9c99`. Lower-LR checkpoint: `ai/runs/tuning-v1-lower-lr-full/best.pt`, SHA256 `0e26ed9a63262513fb961890c7cf1f92ff492bdb7472e1cb0cddad0324e42178`. Both remain ignored local research artifacts.

Four unit tests passed (including preserved three-architecture behaviour, partial-block invariants and strict config boundaries), both GPU smoke checks passed, and both checkpoint replays passed. [Aggregate JSON](efficientnet_tuning/comparison.json) includes full per-class metrics/confusion counts; each trial folder retains its run metadata and full epoch history. [Comparison and learning-curve chart](efficientnet_tuning/tuning.png) visually reviewed. Source images, pretrained weights, app, Word report, dependency versions and existing user edits remain unchanged; the two new research checkpoints remain local.

Rebuild aggregate evidence with `ai/summarize_tuning.py`, then `ai/plot_tuning.py`. Aggregation refuses unmatched control metadata, warm-up results or unverified checkpoints.

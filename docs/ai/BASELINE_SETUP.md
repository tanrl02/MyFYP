# Pretrained baseline setup

18 October 2026. This task selects and prepares the first baseline; a full baseline training run and fine-tuning are separate tasks. Application predictions remain simulated, and the Word report is unchanged.

## Model and hardware decision

Use **EfficientNet-B0**, explicitly selecting `EfficientNet_B0_Weights.IMAGENET1K_V1`, and replace its original output layer with eight outputs in the frozen class order. The [official model documentation](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.efficientnet_b0.html) lists about 5.29 million original parameters, 0.39 GFLOPS and 20.5 MB weights. [MobileNetV3 Small](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html) is a lighter alternative (about 2.54 million, 0.06 GFLOPS, 9.8 MB). It remains a possible later comparison; neither model has measured skin-condition performance in this project yet. ImageNet benchmark scores are not skin-disease accuracy.

The actual laptop check found NVIDIA GeForce RTX 4060 Laptop GPU, 8,188 MiB GPU memory, driver 566.24 and 15.7 GiB system RAM. This supports trying a modest 224 px/batch 16 baseline locally. GPU operation must be established by the actual smoke check, not inferred from the hardware name alone.

Training uses the separate ignored `.venv-ai`; FastAPI continues using `.venv`. There is one application backend. Pinned PyTorch 2.13.0+cu126 and Torchvision 0.28.0+cu126 come from the [official supported version-pair installation page](https://pytorch.org/get-started/previous-versions/) and CUDA 12.6 wheel index. The wheel pair and transitive dependencies are pinned in `ai/requirements-ai.txt`. No application dependency file is modified, and no driver/system CUDA toolkit installation is performed.

## Fixed baseline protocol

Configuration: [baseline_config.json](../../ai/baseline_config.json). Data: frozen `eight-class-v1`, 1,374 training/193 validation/401 test. The runner verifies the frozen dataset lock and every manifest checksum, including the held-out CSV's integrity. Only training and validation rows/images are loaded for fitting or smoke checks. Image bytes are SHA-256-checked when loaded.

- Seed 3403; deterministic PyTorch operations and CuDNN settings; explicit cuBLAS workspace setting. Reproducibility is scoped to the recorded hardware/software, not guaranteed across all platforms/releases.
- First stage: freeze all pretrained feature parameters and keep feature blocks in evaluation mode, so BatchNorm statistics and stochastic-depth behaviour also remain fixed. Train only the new eight-output linear layer with classifier dropout.
- Start with 10 epochs, batch 16, AdamW learning rate 0.001 and weight decay 0.0001. These are initial settings, not validation/test-optimised results.
- Training cross-entropy uses inverse class-frequency weights calculated only from training rows. Validation loss is unweighted cross-entropy; macro-F1 is the primary checkpoint criterion, with lower validation loss breaking ties.
- Baseline preprocessing follows the selected weights: EXIF-corrected RGB, bicubic resize short edge 256, centre crop 224, ImageNet mean/std. It is deterministic, with no augmentation in this first baseline. Centre cropping can omit peripheral lesions; this is a recorded limitation to assess during later model work.
- Test-image evaluation is absent from this runner. No final accuracy is inferred from the small smoke batch or the ImageNet weights.

The frozen-head approach follows the [official transfer-learning tutorial](https://docs.pytorch.org/tutorials/beginner/transfer_learning_tutorial.html). It establishes a comparator before the required later fine-tuning work; it is not the final FYP AI contribution by itself. Later work should compare frozen-head and selected-block fine-tuning using validation results, then evaluate the selected model on the fixed test set.

## Setup and commands

From MyFYP, create `.venv-ai` with the existing Python 3.12 and install the pinned AI requirements. `scripts/setup-ai.ps1` automates these commands without modifying the app environment. GPU wheels are a substantial local download/install; model weights themselves are about 20.5 MB. Both environments and generated artifacts are ignored by Git.

```powershell
.\.venv\Scripts\python.exe -m venv .venv-ai
.\.venv-ai\Scripts\python.exe -m pip install --only-binary=:all: -r ai/requirements-ai.txt
.\.venv-ai\Scripts\python.exe -m unittest discover -s ai/tests -q
.\.venv-ai\Scripts\python.exe ai/train_baseline.py --mode smoke --run-id smoke-example --device cuda --download-weights
```

Weights are fetched from the [official published checkpoint URL](https://download.pytorch.org/models/efficientnet_b0_rwightman-7f5810bc.pth), cached under ignored `ai/weights/`, checked against the official hash prefix and recorded by full SHA-256 in each run. Subsequent runs use that local cache and do not require the download option. Each run ID is immutable: choose a new ID for another run.

Smoke mode takes one training and one validation image per class, performs one classifier optimisation step, verifies finite loss/eight outputs, checks feature-state immutability and classifier updates, and discards its updated model. It saves `run.json` and `smoke.json` only, not a model checkpoint or a meaningful performance estimate.

When starting the separately agreed full baseline run:

```powershell
.\.venv-ai\Scripts\python.exe ai/train_baseline.py --mode train --run-id efficientnet-b0-baseline-v1 --device cuda
```

This command is documented for the next task, not run as part of setup. Outputs go to ignored `ai/runs/<run-id>/`: recorded configuration/environment/weight hashes, validation history, best validation checkpoint and a completion marker. Missing completion/smoke markers mean the corresponding task did not finish. It does not upload images, start another server, update app predictions or provide a clinical assessment.

Full baseline metrics, feature fine-tuning, final test evaluation, uncertainty handling, inference packaging and app integration remain pending. Dataset/source/domain limitations in [the frozen dataset report](FROZEN_DATASET.md) still apply.

## Verified setup result

The RTX 4060 CUDA smoke run succeeded on 18 October 2026. After replacing the original output layer, the model has 4,017,796 total parameters and 10,248 trainable classifier parameters. Eight training images completed one optimisation step and eight validation images produced eight logits each; feature parameters/BatchNorm state were unchanged, the output layer changed, loss was finite and zero test images were evaluated. The updated smoke model was discarded; no `.pt` checkpoint exists in the smoke run folder.

All 27 AI tests passed, including six new baseline data/metric/model tests. `pip check` found no broken requirements. The app environment still has no PyTorch installed; only `.venv-ai` received training dependencies. Launcher syntax was checked. Runtime versions, GPU details, full ImageNet weight SHA-256 and smoke invariants are recorded in [baseline_setup_check.json](baseline_setup_check.json). These checks establish pipeline operation, not disease prediction accuracy. The full 10-epoch baseline command above has not been run.

# AI metadata audit

Completed experiment: [10-epoch EfficientNet-B0 baseline results](../docs/ai/BASELINE_RESULTS.md). Selected epoch 8 validation macro-F1 is 0.4855 and accuracy 56.48%; the 401 test images remain unevaluated. The saved checkpoint is local under ignored `ai/runs/efficientnet-b0-baseline-v1/`. This is the frozen-feature comparator for the next fine-tuning task; app predictions remain simulated.

Training setup: [EfficientNet-B0 baseline guide](../docs/ai/BASELINE_SETUP.md). The isolated `.venv-ai` is for offline model work; app `.venv` stays separate. Use `ai/train_baseline.py --mode smoke` for a small pipeline check, or explicitly `--mode train` for the future full baseline run. Smoke checkpoints are never saved as trained models.

Current research data: [frozen eight-class dataset](../docs/ai/FROZEN_DATASET.md), version `eight-class-v1`. Use its fixed manifests for the upcoming baseline. Preparation/review summaries below are stage-specific evidence; they do not override the frozen version's 1,968 included/108 excluded decisions.

This is a metadata audit, not a trained model. Read [the findings](../docs/ai/DATASET_AUDIT.md) before selecting training data.

From the MyFYP root, using the existing Python environment:

```powershell
.\.venv\Scripts\python.exe ai/audit_metadata.py
.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -v
```

The first command runs offline when the five source CSVs are present. On a new checkout, add `--download` to fetch only the five metadata files in `metadata_sources.json`. It never follows image URLs. Each file is limited to 10 MB and verified against a locked SHA-256 before saving or use. Upstream changes deliberately fail verification; review them before updating the registry.

Raw metadata is ignored under `ai/data/`; aggregate results are tracked under `docs/ai/data_audit/`. `--output-dir` selects another output directory. No additional Python packages are required. Candidate class mappings and SCIN screening thresholds are explicit in `candidate_classes.json`. The user selected eight working classes on 18 October 2026; the expanded review checkpoint records the scope and remaining quality work.

## Local image preparation

Read [the source decision](../docs/ai/SOURCE_AND_LABEL_DECISION.md) first. The existing environment already has Pillow 12.3.0; the image preparation script uses it without installing or changing application dependencies.

```powershell
.\.venv\Scripts\python.exe ai/prepare_images.py --download
.\.venv\Scripts\python.exe ai/prepare_images.py
```

The first command fetches needed 8 MiB blocks from the authors' fixed Zenodo ZIP and extracts only the selected manifest entries. Adjacent unselected archive bytes may occur inside cached blocks; the full archive is not fetched. There is a 512 MiB per-run network limit. Reruns resume from ignored local cache/images. Network access is opt-in; the second command checks existing image files offline. Every selected image must match the source metadata MD5, pass ZIP CRC on extraction, and decode successfully. SHA-256 and EXIF-normalised pixel hashes are recorded alongside dimensions and a difference hash. No files from archive paths are extracted directly; output names are validated source hashes.

Outputs in `docs/ai/preparation/` preserve the authors' partitions. Exact-pixel duplicates, dHash distance <=4 candidate pairs, potential cross-split matches, conflicting labels and short edges under128px are flagged. Flagged images are quarantined in the manifest, not deleted or moved between splits. All images remain pending human review. Neither difference hashing nor the absence of flags proves clinical quality, patient independence or freedom from all near duplicates. Raw images and archive ranges remain ignored under `ai/data/`. No model training or augmentation is performed.

## Visual triage and expanded class scope

`ai/visual_review.json` records the actual first review: 78 flagged thumbnails, 40 sampled unflagged thumbnails from the original five classes, 11 visually matching crop/resize groups and 2 false-match examples. These are technical observations, not clinical relabelling. The original source manifest is identified by SHA-256 and Git checkpoint.

```powershell
.\.venv\Scripts\python.exe ai/review_dataset.py
.\.venv\Scripts\python.exe ai/review_dataset.py --sheets
```

Both commands run offline. Results go to `docs/ai/review/`; optional contact sheets go to ignored `ai/data/review/`. The script checks visual group IDs/partitions and hashes image bytes when rendering sheets. It exports only the recorded review set, without claiming that new classes or the entire dataset were visually reviewed. Current preparation results cover the expanded eight-class set; the first five-class checkpoint remains in Git history at `ff908dc`. See [the eight-class review](../docs/ai/EIGHT_CLASS_REVIEW.md).

## Upper-block fine-tuning

The next development experiment starts from the saved baseline and trains feature blocks 6–8 plus the classifier with lower learning rates and training-only horizontal flips. All BatchNorm state and earlier feature blocks stay frozen. Read [the procedure and results](../docs/ai/FINE_TUNING.md) and `finetune_config.json`; use `train_finetune.py --mode smoke|train|verify --run-id <new-id> --device cuda`. Verification replays validation predictions for both checkpoints and checks frozen/trainable state changes. No test images are fitted or evaluated, and the application remains simulated.


## Validation error analysis

Run `.venv-ai\Scripts\python.exe ai/analyze_errors.py --device cuda` to replay the saved fine-tuned validation predictions and generate source/count/framing aggregates plus local original/crop contact sheets. It never trains or reads test pixels. See [the error review and proposed preprocessing experiment](../docs/ai/ERROR_ANALYSIS.md). The separate `error_visual_review.json` records actual technical visual inspection; generating sheets alone does not constitute visual review.

## Full-frame preprocessing comparison

`train_finetune.py --experiment full-frame` selects `full_frame_config.json` for smoke/training. It fits the whole frame inside224 with mean-coloured padding and retains the earlier experiment's training settings. Verification uses each checkpoint's saved preprocessing, independently replays the baseline and incumbent, and writes to `docs/ai/full_frame_results`. See [the comparison procedure and results](../docs/ai/FULL_FRAME_COMPARISON.md). Old centre-crop checkpoints retain their original preprocessing.


## Current offline choice and dataset-access plan

`model_selection.json` records the user's current offline model preference: the previous centre-crop fine-tuned checkpoint. Experimental verifiers report metric winners in their own result folders and do not change this preference. This file does not deploy a model into the application. Read [the Fitzpatrick17k access and fallback plan](../docs/ai/DATA_ACCESS_PLAN.md) before acquiring more data or starting another experiment.


## Kaggle Dermnet audit

Read [the permissions and class-mapping findings](../docs/ai/DERMNET_AUDIT.md). `audit_dermnet.py` inspects public file-list JSON only; it never fetches images. Run it offline against cached metadata, or use `--fetch` for a bounded fresh public metadata audit. `dermnet_mapping_review.json` records review candidates and mixed/missing categories; it is not an approved training mapping. Current model/data remain unchanged.

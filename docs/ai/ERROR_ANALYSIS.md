# Eczema and dermatitis error review

Completed 18 October 2026, following the first upper-block fine-tuning experiment. This task reviews development errors and proposes one further experiment. It does not retrain, change source labels, alter exclusions or inspect test images.

## Evidence and scope

`ai/analyze_errors.py` verifies the frozen train/validation manifests and fine-tuned checkpoint hash/class mapping. It replays all 193 validation images and checks that accuracy, macro-F1, per-class metrics and confusion counts exactly reproduce the verified epoch-7 results. It hashes the corrected source metadata before joining historical provenance domains. Source URLs are not followed.

Technical visual review covered **42 unique images**, comparing the original frame with the actual resize-256/centre-crop-224 model view:

- All 16 eczema validation images, including correct and incorrect classifications.
- Eight incorrectly classified allergic-contact-dermatitis validation images, selected by lowest retained frame area. This is a deliberately crop-focused error sample, not a representative random sample.
- Six training images per focus class (eczema, allergic contact dermatitis, seborrhoeic dermatitis): two aspect-ratio extremes and four fixed-seed sampled remaining images per class.

The three local contact sheets and per-image predictions remain ignored under `ai/data/error_review`. [Aggregate evidence](error_analysis/summary.json) records selection and class statistics; [the visual review record](../../ai/error_visual_review.json) identifies the inspected sheets and observations. Visual observations are technical, not diagnostic confirmation or an exhaustive dataset review.

## What the data shows

| Focus class | Train | Validation | Correct validation predictions | Train short edge below 224 px | Median training frame area retained |
|---|---:|---:|---:|---:|---:|
| Eczema |118|16|3|27|51.4%|
| Allergic contact dermatitis |209|30|11|17|54.9%|
| Seborrhoeic dermatitis |79|11|5|0|57.3%|

**Eczema errors are spread across classes.** Four of 16 source-labelled eczema images are predicted as psoriasis, four as allergic contact dermatitis, two as scabies and one each as acne, urticaria and folliculitis. Three are correct. Simply merging two classes would not resolve all these errors and would change the agreed scope.

**The class mapping has no detected implementation mismatch.** Frozen class indices, checkpoint mapping, exact source labels and recorded predictions agree. The three focus classes retain separate exact source strings. Those strings do not provide a clinically validated decision rule for distinguishing them. The project has no independent confirmation that all inherited image labels are correct. No individual case was diagnosed or relabelled during this review.

**Source coverage is narrow.** All 118 training and 16 validation eczema images have historical `www.dermaamin.com` provenance. Allergic contact dermatitis has 197/209 training and 28/30 validation images from that domain. Seborrhoeic dermatitis has 50/79 and 7/11 respectively, with the remainder from Atlas Dermatologico. These are provenance counts, not proof of site-independent or phone-photo generalisation. Eczema also has fewer training images than acne (287) and psoriasis (356).

**Some useful context is visibly cropped.** Examples include an eczema-labelled periocular image (`851055fe`, validation) whose crop removes the outer parts of the bilateral view, and training skin-region views (`961d7614`, `d875ed29`) that lose peripheral anatomy. An SD-labelled forehead image (`ea252217`, training) becomes a smaller texture view. This establishes a framing change, not that the cropped-away pixels determine the source diagnosis. Lesion boundaries were not annotated or measured.

**Cropping alone does not explain the low eczema score.** Only three eczema validation frames retain under half their original geometric area: one is correct and two are incorrect. Among the other 13 frames, only two are correct. Acne has ten validation frames below half, all classified correctly. These small observational groups do not establish causation. The area metric measures the original frame retained after resizing/cropping, not the percentage of lesion retained. Even a square frame retains only 76.6% under this preprocessing.

**Image content and scale vary.** The reviewed examples contain close-ups, wider body-region views, different backgrounds/lighting and some low-resolution source images. One eczema-labelled training example (`d49f3bcd`) is an oral close-up rather than a typical external-skin view; its relevance to the intended phone-photo task merits qualified annotation review. This observation does not establish an incorrect source label, and it was not excluded. Eye/face details are visible in some source pictures; contact sheets remain local and untracked.

The original dataset documents clinical-atlas sourcing. The corrected-dataset authors describe duplicate, leakage and labelling issues in their dataset-quality study. These motivate keeping provenance and uncertainty explicit; they do not establish which of our retained examples are mislabelled. Sources: [original dataset](https://github.com/mattgroh/fitzpatrick17k), [corrected-dataset study](https://www.nature.com/articles/s41597-025-04382-5). The project's existing conservative exclusions and frozen partitions are retained.

## Recommended next experiment

Test **full-frame, aspect-preserving resize and padding to 224 × 224**, replacing the current resize-256/centre-crop-224 preprocessing. Use ImageNet-mean-coloured padding before normalisation. This preserves the whole image frame without stretching it, but may reduce visible detail in very wide/tall images and introduce padding cues; improvement is not guaranteed.

Start again from the **same baseline epoch-8 checkpoint**, not the already fine-tuned model. Keep the same 1,374 training images, validation set, seed, upper trainable blocks, frozen BatchNorm, optimiser, learning rates, horizontal-flip probability, ten epochs and macro-F1 selection. Apply the replacement geometry consistently to training and validation. This creates one preprocessing comparison against fine-tuning v1 without adding extra training to only one arm. Preprocessing code and a meaningful geometry check must precede that run; no such training has started here.

Compare all eight classes' precision/recall/F1, macro precision, macro-F1, accuracy and loss. Keep the incumbent if the candidate loses under the predeclared selection rule; do not choose by whichever headline metric looks best. Continued selection on the same validation split remains development and can overfit that split. All **401 test images remain reserved** until final model selection.

If this does not materially help, prioritise qualified review and permitted additional training examples for weak classes. Do not promise 90% from longer training, merge labels for a higher score or remove validation errors to improve reported performance.

## Reproduce this analysis

```powershell
.\.venv-ai\Scripts\python.exe ai/analyze_errors.py --device cuda
```

This regenerates analysis and local contact sheets only. It does not itself perform the separately recorded visual review, train a model, download images, change frozen data or modify the application. The app remains simulated, Word edits and real authentication stay deferred, and the existing user edit to `BASELINE_SETUP.md` is preserved.

# Upload recipe comparison

Predeclared 18 October 2026 before examining candidate scores. The preceding upload audit found that both B0 finalists reached 121/193 (62.69%) after the existing upload recipe, compared with 126/193 and 128/193 on original validation images. This experiment compares four fixed storage recipes without model fitting, disease changes, app changes or final-test inference.

## Fixed comparison

All recipes share the actual production input limits (5 MiB; JPEG/PNG/WebP; 32-pixel minimum side; maximum 25 megapixels), EXIF correction, RGB conversion, aspect-preserving fit within 1600 x 1600 and metadata stripping. Current JPEG85 encoding must match the production helper byte-for-byte for every accepted photo before a candidate is evaluated.

| Recipe | Encoding difference |
|---|---|
| Current JPEG85 | Actual unmodified production helper, quality 85, default chroma subsampling |
| JPEG95 default | Quality 95, same default subsampling |
| JPEG95 4:4:4 | Quality 95, subsampling disabled |
| Lossless PNG | Same resized RGB pixels, lossless PNG encoding, compression level 6 |

The original source may already be lossy; PNG cannot recover information absent from it. Lossless here describes the additional storage encoding after shared geometry/RGB handling. Model preprocessing remains bicubic short-edge resize256, centre crop224 and ImageNet channel normalisation for every recipe.

Use all 193 fixed validation images and both existing checkpoint hashes. Verify original-image metrics against the saved training results and current-JPEG85 metrics against the prior upload audit. No new candidates or parameter adjustments after looking at results. All original input failures must be reported; do not silently optimise on a smaller accepted subset. Images remain in memory and are not written or published.

Primary criterion is **prediction preservation**, not highest disease accuracy: choose the recipe with the fewest changed predictions for its worse-performing model, then fewer total changed predictions, then fewer total encoded bytes. Report paired correct-to-wrong/wrong-to-correct transitions, accuracy, macro precision, macro-F1, per-class metrics, prediction agreement and output size. The old classifiers can themselves be wrong; preserving their predictions is not evidence of clinical correctness. Recipe-induced accuracy changes on a repeatedly used validation set do not establish improved generalisation.

Byte size is a practical trade-off. Report mean/median/maximum bytes and outputs exceeding 5 MiB; this is distinct from the unchanged input-size limit. Actual phone latency, bandwidth, phone-side compression and database/storage policy are not evaluated here. No recipe is automatically installed in the backend or selected as the final model pipeline.

## Results

Completed on all 193 validation images with zero input rejections. Current JPEG85 matches the production helper byte-for-byte for all 193 photos. All 772 encoded outputs pass the shared geometry, RGB and stripped-source-metadata checks. Original-image checkpoint replays and the previous current-upload result also match their recorded metrics and paired transition counts.

| Recipe | Full-feature B0 accuracy | Partial-freezing B0 accuracy | Changed predictions: full / partial | Mean encoded size |
|---|---:|---:|---:|---:|
| Current JPEG85 | 62.69% (121/193) | 62.69% (121/193) | 9 / 9 | 56.6 KiB |
| JPEG95 default | 64.77% (125/193) | 66.32% (128/193) | 2 / 1 | 97.1 KiB |
| JPEG95 4:4:4 | 63.73% (123/193) | 66.32% (128/193) | 3 / 0 | 114.4 KiB |
| **Lossless PNG** | **65.28% (126/193)** | **66.32% (128/193)** | **0 / 0** | **404.5 KiB** |

The original-image reference is 65.28% for the full-feature control and 66.32% for partial freezing. PNG restores those original prediction counts on this sample; it does **not** improve the underlying classifiers beyond their original performance. The 85% target remains unmet. A wrong-to-different-wrong prediction can leave accuracy unchanged, as happens for the partial model under JPEG95 default; prediction agreement is therefore reported separately.

Under the predeclared preservation rule, ranking is PNG, JPEG95 default, JPEG95 4:4:4, current JPEG85. More chroma detail did not monotonically improve predictions for both models. Do not assume a visually higher-quality lossy setting always increases classification accuracy.

### Preservation and size trade-offs

| Recipe | Full / partial macro-F1 | Correct to wrong: full / partial | Wrong to correct: full / partial | Maximum output |
|---|---:|---:|---:|---:|
| Current JPEG85 | 0.5609 / 0.5259 | 6 / 7 | 1 / 0 | 355.4 KiB |
| JPEG95 default | 0.5919 / 0.5855 | 1 / 0 | 0 / 0 | 578.2 KiB |
| JPEG95 4:4:4 | 0.5855 / 0.5854 | 3 / 0 | 0 / 0 | 853.0 KiB |
| Lossless PNG | 0.6003 / 0.5854 | 0 / 0 | 0 / 0 | 2,957.6 KiB |

PNG averages 7.14 times the current processed-JPEG size in this sample, not seven times the original input size. No candidate output exceeds 5 MiB here. That observation does not guarantee a size bound for every future 1600-pixel photo; a future PNG storage policy must enforce a measured output budget as well as the existing input-size limit. All source images retain their original bytes; no newly encoded image was saved or published during this experiment.

Zero changed top-1 predictions does not establish identical logits or clinical reliability. Five original validation photos exceed the shared resize bound; this experiment is not an identity transformation of every original pixel. Real phone lighting, framing, prior device compression, unsupported diseases and source shift remain untested. Class support and labels are unchanged; no test-set image or training step was used.

## Recommendation

Use the PNG recipe as the **research reference for a versioned common model-input pipeline**, subject to explicit output-size limits and a separate real-phone/storage check. JPEG95 default is a smaller candidate if later storage constraints justify accepting some observed prediction changes. Do not choose between them on these reused validation scores alone or automatically install either in the live backend.

Next small task: define and test one reusable processing contract for training and future inference (orientation/RGB/geometry/encoding/version), while keeping the existing app simulation intact. Confirm the data/class scope before another training run, then conduct a controlled training comparison using the chosen processing contract on both training and validation. After pipeline/model selection, perform the reserved evaluation and phone checks. This experiment does not supply validated blur/exposure/unknown-disease detection or confidence calibration.

## Verification and reproducibility

Two new unit tests passed: EXIF rotation/privacy stripping and exact PNG pixels; shared resize and current input limits. Actual experiment checks cover every validation photo/recipe, both original checkpoint replays, current-helper bytes, current-upload metric/transition replays and immutable checkpoint hashes. The [aggregate JSON](upload_recipes/summary.json) contains all per-class metrics/confusion counts, source/helper hashes, environment, output sizes and ranking. [Comparison chart](upload_recipes/comparison.png) visually reviewed.

```powershell
.\.venv\Scripts\python.exe -m unittest ai.tests.test_upload_recipes -v
.\.venv-ai\Scripts\python.exe ai/compare_upload_recipes.py
.\.venv-ai\Scripts\python.exe ai/plot_upload_recipes.py
```

The scripts use local data/cached checkpoints and require no new dependencies or network. Backend, database, mobile/dashboard, current user-selected offline model pointer and Word report remain unchanged.

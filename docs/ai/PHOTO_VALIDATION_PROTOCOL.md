# Photo-admission development challenge protocol

Predeclared 18 October 2026 before this challenge run. Evaluate the current `photo-check-v1` implementation without changing its prompts, thresholds, model, upload handling or disease predictions. This is an engineering challenge set, not a clinical or independent accuracy benchmark. No disease-model training or reserved final-test images.

Reuse only the 37 retained, previously reviewed SCIN skin photographs, selected by `ai/scin_photo_review.json`, with review/image-manifest/source hashes checked. Reuse the six existing public object/texture fixtures with their manifest hashes and notices. No new photographs acquired. Keep all raw/derived images in ignored local data, and commit only protocol, code and numerical/text evidence.

For each skin photograph, evaluate the original bytes and six deterministic RGB derivatives. Geometry for derivatives fits within 1024 pixels, preserving aspect ratio. Encode derivatives as metadata-free PNG:

| Group | Fixed construction | Interpretation |
|---|---|---|
| original skin | Unmodified original upload bytes | Expected acceptance based on earlier technical photo review, not clinical adequacy |
| dimmer | Brightness × 0.65 | Stress probe; no automatic usable/unusable ground truth |
| brighter | Brightness × 1.35 | Stress probe; no automatic usable/unusable ground truth |
| severe blur | Gaussian radius 20 at bounded geometry | Expected rejection of deliberately degraded detail; synthetic challenge only |
| low resolution | Fit within 100 × 100 pixels | Expected rejection by minimum-side rule |
| skin screenshot | 1024 × 800 synthetic browser frame with 560 × 600 contained skin image, heading and text | Expected rejection under requested screen-exclusion policy; known difficult case for centre-crop content screening |
| cropped skin screenshot | Pixel-identical PNG re-encoding of bounded skin image | Ambiguity probe; provenance cannot be inferred reliably from pixels |

Also evaluate six unmodified object photographs, plus five synthetic negatives: text document, application dashboard, coarse patterned fabric-like graphic, black frame and white frame (all 768 × 768). These negatives are generated engineering fixtures, not additional real photographs. The document/dashboard graphics contain no skin or private information. The 37 originals × 7 plus 6 objects plus 5 graphics yield **270 checks** from only **43 real source images**. Derived images are correlated; do not count them as new patients or pool all groups into a headline accuracy.

Call the production `check_photo` function on each byte sequence, retaining its accepted/status/reasons or expected RuleError rejection. Record quality metrics, SHA-256, source/group IDs and paired original/derivative decisions. Fail on missing/mutated sources or unexpected runtime errors; never silently omit a case. A rejection alone is not evidence the correct subsystem worked: separately count quality vs content rejection. Summarise each group and every expected-accept/reject disagreement; lighting and cropped-screenshot probes have no correctness label. Confirm originals reproduce earlier decisions. Record model/code/input hashes for reproducibility. No tuning or production changes after seeing this run; propose any correction as a separate bounded task.

No skin-tone subgroup accuracy can be reported: these 37 cases have no verified subgroup labels in this challenge. Real-phone capture variability, independent negatives and expert assessment of photographic adequacy remain future work. Phone smoke checks previously passed but do not replace that evaluation.

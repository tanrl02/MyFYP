# Whole-frame photo-context comparison

Frozen 18 October 2026 before candidate inference. Offline comparison only; no production edits, disease-model fitting or final-test images. Known failures from challenge-v1 motivate these hypotheses and cannot be counted as independent validation.

Compare three fixed rules with the same local CLIP weights and unchanged quality checks:

1. Baseline: existing centre-crop prompts, positive similarity ≥0.22 and skin/non-skin margin ≥0.015.
2. Whole-frame: baseline must pass AND the same scores/cutoffs must pass on the entire image fitted into a 224 × 224 RGB(127,127,127) square with bicubic interpolation. No cropping or distortion in the additional view.
3. Whole-frame with context prompts: baseline must pass AND the whole-frame view must pass against existing negative prompts plus exactly: “a screenshot of a web page containing a skin photograph”, “a checkerboard pattern”, “a screenshot of a medical application displaying a skin image”. Positive prompts/cutoffs stay unchanged. This tests both geometry and added negative context, so compare it separately from rule 2.

All screenshots with visible UI and artificial patterns are expected rejects. Pixel-identical cropped skin remains provenance-ambiguous and is not used as a correctness target. No extra cutoffs, prompt changes or additional candidates after results.

Reuse the 37 earlier reviewed skin images, split by ascending SHA-256 of case ID: first18 development, remaining19 validation. Keep each source and all its derivatives together. Both groups were previously observed as originals and in challenge-v1; the latter is a **reused-skin validation challenge**, not an unseen patient holdout. For each source use original bytes, the prior browser screenshot and one novel UI layout: development uses a desktop side-panel frame, validation uses a tall phone-gallery frame. Reuse original skin pixels; do not interpret rendered UI as a real screen photograph. No severity/skin-tone labels inferred.

Negatives: prior six public object examples and old checkerboard are development only. Add four new scikit-image v0.25.2 fixtures with upstream SHA verification: development camera/eagle; validation clock/horse. Licence notes and source notices are retained. Three additional fixed artificial checkerboard/pattern fixtures per split use different cell sizes/colours. This is limited new negative coverage, not a representative independent negative dataset. Pattern colours are fixture choices, never skin-detection rules. Screens, patterns and real objects are reported separately.

Select at most one candidate using development only: all18 development skin originals must remain accepted, no development real object may newly pass, and the combined development screenshot/pattern false acceptance count must strictly fall against baseline. Rank eligible candidates by lowest such false acceptance count, then favour simpler rule2. Freeze selection to disk before validation inference. Validation may only reject promotion: require all19 originals accepted, no validation real object accepted, and fewer screenshot/pattern false acceptances than baseline. Report both candidates regardless of selection and every changed decision. These small technical guards are not clinical criteria. Even if they pass, independent new skin/phone data are still required before any live-gate change.

Prepare/freeze case hashes, splits, source/model/checker/script/protocol hashes before inference. Reproduce baseline decisions on known cases, account for all cases, and replay representative decisions. No downloads of patient data, raw-image commits, hosted changes, Word edits or new app dependencies. The app remains on photo-check-v1 and simulated disease predictions throughout.

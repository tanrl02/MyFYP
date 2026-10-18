# Photo validation: development findings

18 October 2026. The frozen challenge exercised the existing production photo-admission function. It did not change the app, thresholds, eight disease classes or disease-model selection. See [protocol](PHOTO_VALIDATION_PROTOCOL.md) and [complete results](photo_checks/challenge-v1/RESULTS.md).

| Development category | Result | Meaning |
|---|---|---|
| Reviewed original skin photos | 37/37 accepted | Reproduces the earlier development check; not independent validation |
| Six public object/texture photos | 0/6 accepted | These particular examples were correctly blocked |
| Severe synthetic blur | 0/37 accepted; all blocked by quality checks | Deliberate Gaussian degradation detected; not a real-camera blur benchmark |
| Low resolution | 0/37 accepted; all blocked by quality checks | Minimum-side rule works on these 100-pixel variants |
| Black and white frames | Both blocked by quality checks | Blank/extreme-exposure rule works on these fixtures |
| Dimmer / brighter skin variants | 36/37 accepted in each group | One content decision changes in each group; photographic adequacy is unlabelled |
| Synthetic browser pages displaying skin | **35/37 wrongly accepted** | Current gate does not reliably exclude screenshots containing skin |
| Cropped skin screenshot probe | 37/37 accepted | Identical skin pixels reveal no screenshot provenance; not scored as a correctness test |
| Synthetic text document / app dashboard | Both blocked | Ordinary UI/text fixtures are easier than pages containing skin |
| Synthetic checkerboard graphic | **Accepted incorrectly** | Current prompts/model also have a non-skin pattern false acceptance |

These are **270 correlated checks from 43 real source images**, plus synthetic graphics. Do not report a pooled accuracy, clinical suitability, calibrated confidence or skin-tone fairness score. The 37 skin sources have already been seen in development; no new independent skin set was acquired. The 401 reserved disease-test images were untouched. Disease recognition remains simulated in the app and these numbers do not improve its disease-classification accuracy.

The two lighting changes were content rejections rather than quality rejections. All per-case messages and quality measurements are preserved in `results.json`; do not infer the altered photographs were genuinely unusable. No prompts or cutoffs were adjusted after seeing failures. A stronger screenshot-exclusion claim would be unsupported.

Recommended next bounded task: investigate a whole-frame context check alongside the centre crop, using additional independently sourced screen/object negatives and a separate validation split before changing the live gate. This may help visible screen frames/text; it cannot establish whether pixel-identical cropped skin came from a camera or screenshot. Keep the current “likely skin” wording and retake option. Model fine-tuning toward the user's disease-accuracy target remains a separate task.

## Reproduction

From the project root, with existing local sources, pinned environment and weights:

```powershell
.\.venv-ai\Scripts\python.exe -m unittest ai.tests.test_photo_validation_evaluation -v
.\.venv-ai\Scripts\python.exe -m ai.evaluate_photo_validation
.\.venv-ai\Scripts\python.exe -m ai.verify_photo_validation
```

The runner freezes hashes before inference and refuses a changed contract. Derived fixtures remain in ignored `ai/data/photo-validation-v1/`. `challenge-v1/` contains the contract, runtime versions, full results and verification evidence. Three unit tests cover deterministic metadata-free construction, mutated-source rejection and paired/group accounting. Verification audits all 270 case hashes and replays a representative from each of the 13 groups, including the changed lighting decisions and a falsely accepted skin screenshot. Raw/derived images and model weights are not committed.

The [expanded phone checklist](photo_checks/PHONE_VALIDATION_CHECKLIST.md) remains explicitly pending; earlier Android smoke checks are recorded separately. No new phone test is claimed by this offline challenge.

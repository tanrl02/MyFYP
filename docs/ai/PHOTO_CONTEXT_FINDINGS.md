# Whole-frame context experiment findings

18 October 2026. **Neither candidate qualifies to replace the current photo gate.** Whole-frame checking reduces some screenshot false acceptances but loses a valid skin-original acceptance on the reused-skin validation challenge. Added context prompts reject substantially more skin originals. The app remains unchanged.

The [predeclared protocol](PHOTO_CONTEXT_PROTOCOL.md) compared the current centre crop, centre crop plus whole-frame with the same prompts, and centre crop plus whole-frame with three added negative prompts. All candidates share the original quality checks and numerical cutoffs. Candidate selection was written to `selection.json` after development and before validation inference; no settings changed after results.

| Validation challenge | Current gate | Whole-frame | Whole-frame + context prompts |
|---|---:|---:|---:|
| Skin originals accepted (want 19) | 19/19 | **18/19** | **12/19** |
| Prior browser screenshots accepted (want 0) | 18/19 | 12/19 | 0/19 |
| Novel gallery screens accepted (want 0) | 18/19 | 14/19 | 0/19 |
| Pattern graphics accepted (want 0) | 0/3 | 0/3 | 0/3 |
| New public negatives accepted (want 0) | 0/2 | 0/2 | 0/2 |

On development, whole-frame preserved all18 skin originals and reduced screen/pattern false acceptances from36 to20; it was the only eligible candidate. The expanded prompts reduced that count to0 but accepted only13/18 skin originals, failing the predeclared preservation guard. On validation the selected whole-frame candidate reduced false acceptances from36 to26 but accepted only18/19 skin originals, so its guard failed. Do not select the other candidate after looking at validation results.

The 128 fixtures comprise37 reused skin originals and their two screen variants,10 public negative images (6 earlier +4 new) and7 artificial patterns. All variants of each skin source stay within one split. Skin originals and prior screen layouts had already appeared in development work; this is not an unseen patient holdout. The two validation negatives, three pattern designs and tall gallery layout were new to candidate selection, but too few and too synthetic for a reliability claim. New camera/eagle/clock/horse fixtures and the two novel layout examples were visually inspected. A distant person with camera is a negative for the close-up-skin requirement; it is not labelled non-human.

The public negatives are from the official scikit-image data collection. Camera/eagle/horse carry CC0 notes, and clock is marked public domain in its [upstream data descriptions](https://github.com/scikit-image/scikit-image/blob/v0.25.2/skimage/data/_fetchers.py). Exact URLs, authors, split assignments and verified upstream SHA-256 values are in `photo_checks/context-v1/negative_sources.json`; upstream notices remain beside ignored local images. No new package installation was needed.

## Decision and next step

Keep the current prototype gate; do not claim it reliably rejects screenshots or patterns. Whole-frame context alone is insufficient, and adding broad negative prompts can discard genuine skin photos. Pixel-identical cropped skin has no reliable screenshot provenance signal. No disease-model accuracy improvement, clinical validation or skin-tone fairness result follows from this experiment. The401 disease-test images remain untouched; eight classes, offline model pointer, Word report, accounts and live services are unchanged.

Stop adding screenshot prompt variants to this small set. Further admission work needs independent real-phone skin and diverse object/screen examples with separate development/validation data. The next higher-value project increment is reviewing weak disease classes and dataset quality before another controlled disease-model experiment toward the85% target. That target remains unmet; no new training was run here.

## Reproduction and evidence

```powershell
.\.venv-ai\Scripts\python.exe ai/prepare_photo_context_negatives.py
.\.venv-ai\Scripts\python.exe -m unittest ai.tests.test_photo_context -v
.\.venv-ai\Scripts\python.exe -m ai.photo_context_experiment
.\.venv-ai\Scripts\python.exe -m ai.verify_photo_context
```

The runner refuses a changed frozen contract. Numerical evidence is under `photo_checks/context-v1/`: contract, selection, full per-case scores/decisions, results table and verification. Three unit tests cover full-frame edge preservation, rejection of skin-loss/object-regression tradeoffs, and group-isolated split accounting. The verifier audits all128 fixture/dependency hashes, known baseline reproduction, summary/selection accounting and representative decision replays including the whole-frame skin false rejection. Raw images and derivatives stay in ignored `ai/data/photo-context-v1/`; the app does not import this experiment.

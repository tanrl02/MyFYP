# First SCIN photo acquisition and technical review

Completed 18 October 2026. Acquired the locked 45-case batch from the public SCIN bucket, one preferred close-up per case. This is a research-data preparation checkpoint; no model was trained and no frozen dataset was changed.

## Results

| Source candidate label | Photos acquired | Candidates for further research preparation | Quarantined |
|---|---:|---:|---:|
| Eczema |20|18|2|
| Allergic contact dermatitis |20|17|3|
| Seborrhoeic dermatitis |5|2|3|
| Total |45|37|8|

All 45 downloaded images decoded successfully. Total source-image bytes were 64,720,899 (about 61.7 MiB). None had a short edge below 128 px. Local original bytes are retained unchanged under ignored `ai/data/scin/review/images`; existing case references and annotations remain alongside them.

## Integrity and duplicate checks

All 45 images were checked against the **server-advertised CRC32C** checksum, then recorded with local SHA-256, MD5, EXIF-normalised RGB pixel hash and dHash. Responses supplied CRC32C rather than MD5, so the report does not claim server-MD5 verification. The CRC32C implementation was tested against the standard `123456789` check value, distinguishing it from the different CRC32 polynomial. Cached reruns verify source headers/checksums and local SHA without redownloading.

There were 93,420 fingerprint comparisons against all 2,076 existing Fitzpatrick preparation records, covering current train/validation/test and all local exclusions, plus 990 comparisons within the 45-photo batch. No exact-byte, exact-pixel or dHash-distance≤4 candidates were found. This does not rule out every near duplicate, repeated subject or related clinical view.

Prior fingerprints were checked against the frozen preparation-manifest semantic lock. **No prior test-image pixels were opened, and no test inference was run.** Hash comparisons protect split isolation without treating test examples as development images. The 401-image final test set remains reserved.

## Actual technical review

All three local contact sheets were visually inspected, covering all 45 selected photos. [The tracked review record](../../ai/scin_photo_review.json) identifies every inspected case/image SHA, the sheet SHA values, decisions and observations. Thumbnail inspection is technical triage, not independent clinical annotation.

Four photos have source-provided black privacy-mask overlays: one eczema image (position 18) and three seborrhoeic-dermatitis images (positions 41–43). They are quarantined from the first expansion candidate pool because the masks could become artificial classification cues. In this small batch, masks are particularly concentrated in the seborrhoeic class. Originals and masks were not removed or altered.

Four other cases have maximum original differential-confidence scores below 3 on the source's 1–5 scale: one eczema case and three allergic-contact-dermatitis cases. They are quarantined from the first candidate pool despite high differential ranking weights. This is a conservative preparation choice, not a clinically validated confidence threshold. A normalised top ranking weight of 1.0 can coexist with an original confidence of 1; it must not be described as 100% certainty.

The remaining 37 photos depict skin regions with varied lighting, backgrounds and framing. No additional obvious non-skin/error picture or text-based identifying detail was detected at contact-sheet scale. Some face/beard regions, jewellery and surroundings remain visible; no identification was attempted. Darker skin or low apparent contrast alone was not an exclusion criterion. Source labels are retained as inherited research annotations, not newly diagnosed or certified by the agent.

## What is ready, and what comes next

The 37 cases are **candidates for research preparation only**. They are not yet assigned to train/development splits or approved as a new training dataset. One photo per case is present; the other 55 views referenced by these 45 cases were not downloaded. Quarantined originals are retained, not deleted, and no replacement cases were silently fetched.

Next manageable task: define a documented case/duplicate-group split and create a separately versioned expansion manifest for the retained candidates, including a source-specific development holdout. Keep the original Fitzpatrick validation and reserved-test sets fixed. With only two retained seborrhoeic cases, source-specific evaluation will be very small and must not support a robust performance claim. Describe the inherited differential labels and cross-source taxonomy limits explicitly before any mixed-source training experiment.

Only after that data-definition checkpoint should a controlled fine-tuning comparison be run. The current offline choice remains the user's centre-crop fine-tuned model. No improvement or 90% precision is claimed from acquiring images.

## Provenance, verification and reproduction

Source: [SCIN project](https://github.com/google-research-datasets/scin), associated with Ward and colleagues' 2024 dataset work. The [SCIN Data Use License](https://github.com/google-research-datasets/scin/blob/main/LICENSE) and project README were saved locally with hashes in the [preparation summary](scin_preparation/summary.json). This custom licence is retained with the data; no re-identification, external messaging, publication or redistribution was performed. Original downloads are unmodified; derived fingerprints and contact sheets remain local.

`ai/scin_review_config.json` locks the selected batch SHA and limits acquisition to 45 selected objects, 10 MiB per image and 192 MiB of image bytes per run. Only fixed public bucket paths are accepted; source notices are separately limited to 100 KB each. Download state records URL, headers and first-acquisition SHA. The script never follows original atlas URLs, trains a model or changes split membership.

Four focused tests passed: response-length/MD5 failures, size limits, source-path restriction, exact versus heuristic matches and CRC32C verification. Full acquisition exited successfully with zero failures; offline revalidation also passed. The final summary and image manifest reproduced byte-for-byte on repeated offline runs. All 45 decisions, three inspected sheet hashes, 37 candidate counts and eight quarantine counts matched the saved records.

```powershell
.\.venv\Scripts\python.exe ai/prepare_scin_review.py
.\.venv\Scripts\python.exe -m unittest ai.tests.test_scin_preparation -v
```

On a new permitted acquisition, add `--download`; `--sheets` regenerates local review thumbnails without changing image originals. Existing snapshots are verified and reused. Raw images, cached responses, candidate/reference-level manifests and sheets stay ignored in Git. Tracked outputs contain aggregate integrity information and technical decisions only. App predictions remain simulated; Word, authentication, services and dependencies are unchanged. The existing user edit to `BASELINE_SETUP.md` is preserved.

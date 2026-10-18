# Temporary experimental disease-model integration

18 October 2026. New saved assessments now run real local inference with the user-selected `efficientnet-b0-finetune-v1` checkpoint. This is the earlier selected centre-crop model, not the later 66.32% research candidate. Its recorded development validation accuracy is59.59% on193 images, macro-F1 0.5214. The85% target is unmet; the401 reserved final-test images remain unevaluated. Integrating the checkpoint does not improve its accuracy or establish performance on phone photos.

The Expo phone app calls the same Python API as the dashboard. No second backend, paid service, cloud image upload, new dependency, device-side model or offline-phone capability was added. The existing `.venv-ai` environment supplies Torch/Torchvision and the photo gate. Keep the API and Expo launcher running on the same private Wi-Fi.

## Patient and doctor flow

1. Android → Ava → Skin check → take/select a clear, non-sensitive close-up skin photo. Existing quality/likely-skin checks must pass.
2. Tap **Analyse & save assessment**. The API checks the photo again, runs the classifier and atomically saves the photo and prediction. First model loading may take longer.
3. Read **AI suggestions · EXPERIMENTAL**: top three of eight classes, uncalibrated model scores, recorded validation performance and model version. Scores are not diagnostic certainty. No healthy/unknown classifier was added; a condition outside these eight can still receive one of the eight labels.
4. Reopen from Assessment history. Each stored result is a snapshot; a future model change does not rescore it. Existing assessments remain simulations and are not automatically analysed.
5. Use existing sharing/appointment-link controls to authorise a doctor. Dashboard → `/reviews` → chosen doctor → shared assessment displays the same model snapshot next to the photo. `/consultations` and patient visit details also display the snapshot when linked. No extra access is granted by AI inference.
6. “Find a suitable doctor” uses the saved top-ranked condition for existing Acne/Eczema/Psoriasis expertise fields. Other classes fall back to general skin concerns; manual concern selection remains available. Ranking is not a verified referral or diagnosis, and booking alone does not share the photo.

Doctor review remains a separate human action. AI output does not publish a review, issue medication, dispense stock, complete a visit, create a bill or authorise payment. Prescriptions and billing keep their existing workflow; payments remain simulated. Secure login and Word editing remain deferred.

## Pinned model and input contract

`apps/api/disease_model.json` pins the existing checkpoint path, SHA-256, eight-class order, epoch and preprocessing. `ai/model_selection.json` now records experimental local integration without changing the chosen checkpoint. The server refuses missing/changed weights, mismatched classes/metadata or unexpected preprocessing; a failed new inference returns503 with no saved assessment and no silent simulation fallback.

The loader constructs EfficientNet-B0 with `weights=None`, strictly loads the local hash-verified checkpoint with `weights_only=True`, and uses CPU evaluation/inference mode with four threads. Runtime does not download weights. Original uploaded bytes receive EXIF orientation correction, RGB conversion and the exact recorded official ImageNet EfficientNet-B0 evaluation transform: resize256, bicubic centre crop224, ImageNet normalisation. No enhancement or random augmentation is applied. Training code is not imported into the service.

Inference uses the admitted **original upload**, before the existing metadata-stripped1600px/JPEG85 storage conversion. This avoids introducing that additional lossy conversion before inference. Phone image-picker compression still happens upstream, so raw research validation accuracy is not a claim about the phone pipeline. Prediction snapshots retain the original upload SHA, checkpoint SHA, preprocessing ID, dataset version, scores and creation time. The stored display photo remains the existing JPEG; reproducing from that JPEG can differ from the original-upload prediction. No original EXIF/GPS is retained in the database.

SQLite migration adds nullable `prediction_json` to assessments and preserves existing rows. Retries with the same patient/request/upload hash return the already saved snapshot without rerunning inference, including if the model later becomes unavailable. Conflicting bytes return409. Concurrent saves retain one result; newer predictions do not overwrite an existing snapshot. New model versions require an explicit contract update and API restart; no automatic checkpoint selection or retraining is performed.

To run on another machine, install the existing pinned AI/API/photo-check requirements and copy the user-owned research checkpoint to the ignored path in the runtime contract, preserving its SHA. Preserve dataset/model attribution and research-use restrictions. The model is not committed to Git or fetched from an unverified mirror. Existing photo-gate weights are set up separately in [PHOTO_CHECKS.md](PHOTO_CHECKS.md).

## Verification

All95 API tests passed, including five new prediction tests for immutable results/retries/concurrency, migration, failures, doctor sharing and patient separation. Both TypeScript checks, Android export and dashboard production build passed. The real classifier/API was also compared against a separate direct checkpoint forward on three existing public SCIN development photos: top-three class order/scores match, stored results survive reopening, another patient is denied, and a corrupt-model failure saves no row. This used an isolated database and no reserved disease-test images. Evidence: `docs/ai/mobile_integration/verification.json`; reproduce with `.venv-ai\Scripts\python.exe -m ai.verify_mobile_inference`.

Browser inspection confirmed old history remains labelled Simulation, the updated experimental warning is visible, and a newly saved experimental result renders all three scores, validation performance and model version. No fresh doctor consent was created by the browser check. The user confirmed Android prediction, reopening persistence and patient separation on18 October2026. No new clinical accuracy, independent test, screenshot-detection or skin-tone fairness claim is made. The current photo gate retains its documented screenshot/pattern limitations.

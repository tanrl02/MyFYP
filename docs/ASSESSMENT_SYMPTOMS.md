# Patient-reported symptom details

18 October 2026. Each new assessment can include body area, onset, itching, pain and an optional description. These are saved patient statements for doctor review. They are not clinical findings and are not used by the image-only disease model or photo-admission gate.

## Patient flow

Skin check → take/select photo → wait for photo checks → enter **Body area** and **When did it start?** → choose **Yes / No / Not sure** for itching and pain → optionally describe the concern → **Analyse & save assessment**.

Body area accepts up to80 characters, onset100 and description1000. Write “not sure” when appropriate, or “no concern / not sure” for onset when testing an image without symptoms. Itching and pain start at **Not sure**, not No. Save stays disabled until the photo passes and body area/onset are entered.

The saved result displays a separate **Patient-reported symptoms** panel. Reopening from history restores that assessment's context. Choosing a new photo or discarding the preview clears the form; cancelling photo selection preserves the previous preview/context. At the first save attempt, details are locked for an unchanged retry. If a response is uncertain, refresh history before starting another assessment; no request ID is silently rotated when details change. Existing saved assessments are not edited in place.

## Doctor flow and access

Use existing direct sharing or an appointment link. The authorised doctor opens `/reviews` or `/consultations` and sees the saved symptoms beside the photo and AI ranking. Patient My visits → linked assessment also shows the same context. Symptoms do not create access, publish a doctor assessment, issue prescriptions or choose a disease automatically. Another patient, staff and an unauthorised doctor do not gain this clinical context. Existing revocation rules still apply.

The prepared demonstration is Ava assessment `90ee5393` (18 October,10:34pm), shared with Dr. Lim (share `8975ee04`). It uses an existing public acne-labelled dataset image and explicitly fictional context: Forearm (fictional),3 days ago (demo), Itching Yes, Pain No. This is a workflow fixture, not a clinical case. The doctor can inspect it without publishing a new review. The image ranking remained Acne92.1%, as for the earlier upload of the same image.

## Storage and compatibility

The multipart save request includes a bounded JSON `symptoms` form field. The API validates and trims it before photo checks/inference. Unknown keys, blank required strings, unsupported choice values and excessive lengths return422 without inference or a new record. The field is optional for older API clients; omission means context was not recorded, not that symptoms were absent.

SQLite adds nullable `symptoms_json` to assessments, preserving old rows and their prediction snapshots. Older assessments display **No symptom details were recorded for this assessment**. Save stores the photo, prediction and context atomically. Idempotent retry compares the original photo hash and canonical symptom values: reordered JSON keys/trimmed whitespace replay correctly, while changed details with the same request ID return409. Concurrent conflicting context cannot overwrite the first saved record. Original-photo and model checkpoint hashes keep their existing meanings; symptoms are never mixed into model input or prediction identity.

No training, class/threshold/model change, additional dependency, second backend, login, payment or Word-report edit was added. The experimental model's limitations and recorded validation performance remain unchanged.

## Verification

103 API tests passed, including five new tests for validation/unknown choices, unchanged model input, canonical retries/conflicts, concurrency, reopening, migration and authorised sharing. TypeScript checks, Android export and dashboard production build passed. Live browser checks confirmed Save disabled before required details, fictional context saved, context visible after reload, same authorised-doctor context, legacy missing-context wording, and Noah unable to see Ava's assessment. Screenshot: ignored `tmp/saved-assessment-symptoms.png`.

Android saved-details/form/reopening/patient-separation confirmation is pending the user's test-card reply.

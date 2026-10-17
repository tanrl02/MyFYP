# Dataset access plan and current model choice

Updated 18 October 2026. The user confirmed that their author request is for the full **Fitzpatrick17k** dataset. No reply or new delivery is assumed. No email or follow-up has been sent by this agent.

## Current choice

The user asked to return to the previous model. The current **offline development choice** is therefore `efficientnet-b0-finetune-v1`, centre-crop preprocessing, best epoch 7: validation accuracy 59.59%, macro precision 53.07%, macro-F1 0.5214. The local checkpoint hash was rechecked against the verified evidence before recording this choice in [model_selection.json](../../ai/model_selection.json).

This user preference supersedes the full-frame experiment's metric-based recommendation. The full-frame run, code and results are retained as research evidence; historical numeric results and its recorded metric-rule winner are not rewritten. Neither model is integrated into the application, which continues to show simulated predictions. The 401 test images remain reserved and unevaluated. No retraining is required to select the existing checkpoint.

## What full Fitzpatrick17k access would change

The [original dataset](https://github.com/mattgroh/fitzpatrick17k) describes 16,577 atlas images across 114 conditions and offers author contact for image access. Our preparation already extracted the selected eight-condition images from the corrected authors' renamed Fitzpatrick archive. We did not download the whole archive to disk; the acquisition tool fetched the necessary archive ranges and extracted the selected images.

| Local evidence | Entries/images | Meaning |
|---|---:|---|
| Original metadata, all conditions |16,577|Full collection, not all relevant to the eight-class task|
| Original metadata, our eight exact-label groups |2,763|Raw entries before corrected-manifest filtering|
| Corrected manifest, our eight groups |2,076|All selected images already acquired and hash/decode checked|
| Current frozen subset |1,968|After 108 local conservative quality/duplicate exclusions|
| Current frozen split |1,374 / 193 / 401|Train / validation / reserved test|

Original eight-group counts are acne518, eczema204, psoriasis653, folliculitis342, urticaria151, allergic contact dermatitis430, seborrhoeic dermatitis126 and scabies339. These counts were recomputed from the SHA-locked original metadata. They are raw metadata entries, not verified additional training images. The difference of 687 between original and corrected eight-group totals is not an approved expansion pool.

The [corrected-dataset study](https://www.nature.com/articles/s41597-025-04382-5) documents duplicate, label-conflict and erroneous-image cleaning and supplies fixed partitions. Receiving the original full archive does not resolve those issues. We must reconcile any apparent extra cases with the corrected manifest, source label changes and exclusions before deciding whether any are eligible. Do not add rejected examples back merely to increase sample count. A genuinely new or independently relabelled release could be useful, but its contents need inspection first.

## If the author replies with data

1. Keep the original delivery separate. Record the dataset/version, checksum, licence/use conditions, label documentation and any grouping identifiers. If available, retain the author's explanation of corrected labels or newly collected examples. Do not post private download tokens in Git.
2. Compare identifiers, hashes and exact/near duplicates with all existing train/validation/test and excluded images. Establish whether the delivery is the same archive, additional condition classes, genuinely new examples of our eight classes, or a clinically relabelled version. A larger ZIP is not itself evidence of more relevant data.
3. If it is the same material, retain the current corrected subset and use any useful documentation; no retraining just for a different download route. Keep unrelated condition classes outside the agreed task unless scope is explicitly revised later.
4. For eligible new images, review quality and label compatibility, group related case/patient/duplicate images where metadata permits, and create a new versioned training/development manifest. Keep current validation/test images and all their detected neighbours out of added training. Do not claim patient independence when identifiers are absent. Do not automatically re-admit corrected/local exclusions.
5. Train one controlled comparison with the same eight output classes and a documented preprocessing policy. Compare validation accuracy, macro precision, macro-F1 and all class recalls/F1. Retain a candidate only on documented development criteria. Evaluate the reserved test set after model selection, not repeatedly to tune candidates. Any later corrected labels/test changes require a new evaluation version, not silent replacement of old evidence.

More usable, correctly labelled examples may help; full archive access does not guarantee 90% precision.

## If the author does not reply, or sends no useful new examples

Continue using the corrected subset already available. There is no need to block the whole project on this request. Keep all eight agreed conditions; avoid another round of longer training simply because a reply is pending.

The next data task should be a **small alternative-source audit**, initially focused on eczema and dermatitis. [SCIN](https://github.com/google-research-datasets/scin) is a candidate because it provides contributor photos, case metadata and dermatologist differential labels. We already have its metadata, not its images. Our earlier screen found 231 eczema cases and 509 image references under the recorded ranking-weight rule; this is an audit count, not clinically confirmed labels or independent examples. Differential weights are not calibrated disease probabilities. Recheck label meaning, use conditions, image availability and cross-source duplication before selecting any acquisition batch. Split by case and any available patient/duplicate grouping, not by individual image. Keep source-specific validation visible rather than assuming atlas and contributor photos behave alike.

If no suitable extra data is accessible, finish a reproducible FYP pipeline with the available data: meaningful pretrained-model adaptation, honest evaluation, documented class limitations and a review path for uncertain assessments. Final performance claims must match measured results. The current scores do not justify a reliable diagnostic claim or a promise of 90%. The full system scope remains nine modules; data access does not require removing modules or hiding weak classes.

## Work while waiting

Keep one manageable task per turn. First audit alternative data options and count genuinely usable candidates; do not bulk-download or retrain in this planning task. Application work can proceed independently with a clear model interface that will carry version, per-class scores and uncertainty once real inference is implemented. Keep simulated results explicitly labelled until that integration is implemented and verified. Neither data-access outcome calls for changing the mobile/web architecture or adding another application backend.

Word report edits remain deferred until implementation and evaluation settle. Record the access attempt and measured limitations for the eventual report, without describing a pending dataset as acquired.

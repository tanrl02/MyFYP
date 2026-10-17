# SCIN expansion screening

Completed 18 October 2026. This audit uses the existing SHA-locked SCIN release 1.0.0 metadata: 5,033 cases. It does not download images, create a training split, modify the current dataset or train a model.

## Screening results

| Target | Earlier screen: cases | Stricter screen: cases | Image references in stricter pool | Strict cases with at least 2 available positive graders |
|---|---:|---:|---:|---:|
| Acne |33|14|26|1|
| Eczema |231|121|264|6|
| Psoriasis |32|17|33|0|
| Folliculitis |68|36|69|1|
| Urticaria |131|86|163|6|
| Allergic contact dermatitis |111|38|72|0|
| Seborrhoeic dermatitis |10|5|11|0|
| Scabies |1|0|0|0|

The earlier screen required a unique top differential label, ranking weight ≥0.60, margin ≥0.20, at least one default-positive case grade and an image reference. The new exploratory rule requires a unique top label, weight ≥0.80, margin ≥0.40, all available case-graders default-positive, distinct valid image paths and no literal image path shared with another case. Fifteen shared paths exist across the metadata; all participating cases are excluded from the stricter pool. Thresholds are development-screening choices, not clinically validated cutoffs.

The term “stricter” describes a metadata rule only. A weight of 0.80 is **not an 80% probability of the condition**. Most retained focus cases have only one available grader: eczema 115/121, allergic contact dermatitis 38/38 and seborrhoeic dermatitis 5/5. Multiple positive gradability ratings also do not establish diagnostic consensus. Original confidence lists are retained locally for review; the ranking-weight screen does not filter their absolute values.

## Annotation and mapping limits

The [official SCIN schema](https://github.com/google-research-datasets/scin/blob/main/dataset_schema.md) describes up to three diagnoses per labeler and up to three labelers. Confidence-derived ranks are combined into normalised differential weights. Its example maps multiple original eczema terms to a broader Eczema label. Numbered gradability fields refer to dermatologists rating the case, not to correspondingly numbered photos. A single case can have up to three images.

Our mapping retains the eight agreed exact weighted-label names. Eczema is mapped only from `Eczema`; the two named dermatitis conditions keep their own labels. Other dermatitis categories are not silently merged. Exact string matching does not establish complete equivalence with inherited Fitzpatrick diagnoses. Review taxonomy and original differential annotations before using these candidates as hard training labels. No diagnostic relabelling has been performed.

Case IDs allow grouping related submitted photos, but do not establish participant independence across cases. Literal-path checks cannot identify all near duplicates or overlap with Fitzpatrick. US contributor photos need source-specific evaluation; they do not establish performance on Malaysian phone photos.

## Proposed first review batch

Prepared a deterministic local reference list for **45 cases**:

- 20 eczema cases out of 121 eligible;
- 20 allergic contact dermatitis cases out of 38;
- All 5 eligible seborrhoeic dermatitis cases.

The list prefers more available positive graders, then larger ranking weight/margin, then a seeded case-ID hash. This is a purposive review batch, not a representative random sample. All 45 preferred first-review references are marked CLOSE_UP. The selected cases contain 100 total image references; the first acquisition should fetch only one preferred image per case, preserving every case's associated references for later grouping. None have been downloaded or verified accessible. Lists remain ignored under `ai/data/scin/review` and have `review_only_no_split_not_training_approved` status.

## Next manageable task

Acquire the 45 preferred images as a **bounded technical review batch**, retaining provenance and the [SCIN Data Use License](https://github.com/google-research-datasets/scin/blob/main/LICENSE). Check availability, decode/quality, hashes and near duplicates against the old training, validation, reserved-test and excluded images. Review original labels and the actual photos without claiming independent clinical confirmation. Do not train or add images to the frozen dataset in that acquisition task.

Then decide which images are eligible for a separately versioned data expansion, with case/duplicate grouping and a source-specific development holdout. Keep any photo from a selected holdout case out of training. Additional views from the same case are not additional independent cases. The current 401-image test set stays reserved; any overlapping new examples must not enter training. Substantial diagnostic ambiguity should be quarantined or retained only in an explicitly weak-label experiment, not silently treated as certainty.

SCIN's custom licence calls for attribution and retained notices/changes when sharing and prohibits re-identification/re-linking of subjects. It is not a CC or MIT declaration. Images, reference-level metadata and case annotations should remain local to this research workflow. No external messages, publication or redistribution have been performed.

Dermnet remains a parallel option after source/use clarification and narrower labels for mixed folders. SCIN is prioritised for the next small batch because its case annotations and public access route are documented, not because these candidates are proven clinically accurate. All eight final classes and all nine system modules remain in scope.

## Verification and artifacts

`ai/audit_scin_expansion.py` verifies the original metadata SHA locks and case/label key consistency, then produces [the aggregate summary](scin_expansion/summary.json). Tests cover gradability disagreement, case-level raters versus multiple photos, ties, shared paths and invalid paths. All three new tests and six existing metadata-audit tests passed. Offline regeneration is checked against saved aggregate/reference output hashes. No network or GPU is used by the screening script.

```powershell
.\.venv\Scripts\python.exe ai/audit_scin_expansion.py
.\.venv\Scripts\python.exe -m unittest ai.tests.test_scin_expansion ai.tests.test_audit_metadata -v
```

Current offline model remains the user-selected centre-crop fine-tuned checkpoint. App predictions are still simulated. Word, real authentication, services, dependencies and model weights are unchanged; the user's existing `BASELINE_SETUP.md` edit remains untouched.

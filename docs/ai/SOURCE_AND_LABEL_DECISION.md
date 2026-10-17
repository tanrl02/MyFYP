# Image source and working label decision

Scope update: the user has selected [eight working classes](EIGHT_CLASS_REVIEW.md). That checkpoint supersedes the five-class preparation table below; the source/licence route is unchanged.

Checked 18 October 2026. This decision supersedes the unresolved licence-scope question in the first metadata audit. It selects a local noncommercial research preparation route, not a commercial deployment licence or a final classifier.

## Licence scope resolved from the actual releases

The [newer Zenodo release 12739457](https://zenodo.org/records/12739457) explicitly assigns CC BY 4.0 to its metadata files. Its file list contains no Fitzpatrick image ZIP. Thus its metadata licence was not a replacement licence for the images.

The authors' [project website](https://derm.cs.sfu.ca/critique/) links the renamed Fitzpatrick image archive in [earlier release 11101338](https://zenodo.org/records/11101338), whose dataset declaration is CC BY-NC 4.0. The [original Fitzpatrick17k repository](https://github.com/mattgroh/fitzpatrick17k) also states CC BY-NC-SA 3.0. We retain both notices, use the images locally for noncommercial FYP research and retain source attribution. Renaming by the corrected-dataset authors is not treated as erasing original conditions. The project does not relicense or redistribute this image collection. Apache 2.0 covers the corrected repository's code, which was not copied into the preparation script.

This provides a documented route for the present local research preparation using the authors' published noncommercial release. It does not establish that contributors can grant every privacy/personality right, or that a later commercial/public distribution of images or model weights has been cleared. Any such later use needs its own scope review. The [CC BY-NC 4.0 terms](https://creativecommons.org/licenses/by-nc/4.0/) and [original CC BY-NC-SA 3.0 terms](https://creativecommons.org/licenses/by-nc-sa/3.0/) remain linked here.

## Image source selected

- Archive: `Fitzpatrick17k_CategorizedAbbrvs.zip`, Zenodo record 11101338.
- Published size: 1,422,904,980 bytes; whole-archive MD5: `8f2640a6a45bbaf5c9b776d2d68fccc6`.
- Membership/labels/partitions: already SHA-256-locked corrected metadata, version12739457, agreeing with pinned GitHub commit.
- Fetch needed archive byte ranges only; extract members matching the corrected subset. Individual original-byte MD5 values must match the locked metadata. Since the whole archive is not downloaded, its whole-file MD5 is recorded but not claimed as verified.
- Preserve original bytes locally; output filenames use source MD5 identifiers. Record source URL, archive member, target class, source label, partition, hashes and technical checks.

The archive contains all 16,577 original images; it is not itself the corrected subset. We explicitly filter by the 11,394-entry corrected manifest, then by the five-class mapping. Do not train on every archive member.

An access check of the original DermaAmin homepage now returned unrelated gambling content. No medical images or current permissions were inferred from it, and original atlas URLs are never followed by the downloader. [Atlas Dermatológico](https://atlasdermatologico.com.br/) states noncommercial use with a source link, but it is not substituted for the fixed archive. Source URLs in manifests are historical provenance fields.

## Working mapping for this preparation task

| Target label | Exact source labels included | Metadata entries |
|---|---|---:|
| acne | acne; acne vulgaris |420|
| eczema | eczema |176|
| psoriasis | psoriasis |534|
| folliculitis | folliculitis |182|
| urticaria | urticaria |134|

This is a five-class working subset, not a claim that these are the only skin conditions or enough to classify arbitrary photos. Acne is an explicit project grouping of two source labels. Other labels retain exact source names; related conditions/subtypes are not silently merged. Dataset labels are inherited research annotations, not independently confirmed diagnoses. No healthy/non-skin/unknown class is manufactured. Keep the mapping fixed for this preparation checkpoint; extra classes can be audited in a separate increment before the final training taxonomy is fixed.

## Quality and split policy

Preserve authors' train/validation/test membership. No augmentation, new split, test-based threshold selection or model training in this task. Decode and hash checks are mechanical evidence only. Potential duplicates (including within a split), cross-split neighbours, label conflicts and images below 128 px on the short edge are quarantined for review. A conservative dHash distance threshold of 4 is a retrieval heuristic, not a clinical or validated duplicate decision. Both members of a candidate pair are flagged; no test image is silently moved into training.

All images await visual suitability review before any training manifest is approved. Review for non-skin/error images, severe quality problems, overlays/identifying details and inconsistent inherited labels. A coding agent's visual inspection cannot clinically certify disease labels. Keep ambiguous cases excluded and record decisions; do not inspect model test predictions to curate favourable performance. No participant identifiers are available, so no patient-independent split claim is made.

Attribution: original Fitzpatrick17k dataset by Matthew Groh and colleagues (CVPR Workshops 2021), sourced from DermaAmin and Atlas Dermatológico; corrected manifests and renamed archive by Kumar Abhishek, Aditi Jain and Ghassan Hamarneh, *Investigating the Quality of DermaMNIST and Fitzpatrick17k Dermatological Image Datasets* (Scientific Data 2025), DOI[10.1038/s41597-025-04382-5](https://doi.org/10.1038/s41597-025-04382-5). Changes in this project: selection, explicit acne grouping, local hash filenames and added QA metadata; no alteration of stored image bytes. No endorsement is implied. Preserve source notices if material is later shared.

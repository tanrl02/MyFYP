# First image preparation checkpoint

Historical first five-class batch. The [eight-class review checkpoint](EIGHT_CLASS_REVIEW.md) contains current counts and scope; the machine-readable files under `preparation/` now cover all eight selected classes. The original five-class files remain in Git checkpoint `ff908dc`.

Completed 18 October 2026. See [the source/label decision](SOURCE_AND_LABEL_DECISION.md) for the noncommercial research route and working five-class mapping. These classes are the first preparation batch; additional classes remain open for a later audit.

## Verified local data

All 1,446 selected image files were obtained from the authors' fixed Zenodo image archive, matched to the corrected manifest, checked against their original-byte MD5 values, checked on ZIP extraction for CRC errors, and successfully decoded. There were zero acquisition/hash/decode failures. Stored original images total 124,331,072 bytes. Approximately 180 MiB of archive blocks were fetched instead of the entire 1.42 GB ZIP; blocks may contain adjacent unselected compressed data. The whole-archive digest was not verified because the entire archive was not fetched.

Images remain locally ignored under `ai/data/fitzpatrick17k/images/`. Source URLs, archive members, original labels, target classes, source partitions, dimensions and hashes are recorded in the [image manifest](preparation/image_manifest.csv).

| Working class | Verified files | No mechanical flags | Quarantined for review |
|---|---:|---:|---:|
| Acne |420|411|9|
| Eczema |176|169|7|
| Psoriasis |534|514|20|
| Folliculitis |182|145|37|
| Urticaria |134|129|5|
| Total |1,446|1,368|78|

The authors' partitions remain unchanged: 1,012 train/144 validation/290 test. Among unflagged entries, the counts are 954/133/281. This is a filtered view of the supplied partitions, not an approved final training split.

## Review findings

The conservative difference-hash screen found 101 candidate pairs involving 69 images. Of those images, 42 have a candidate match across source splits, and 47 have at least one candidate match assigned to a different target class. These are potential duplicates/leakage/conflicts, not confirmed errors; visually similar backgrounds can produce false matches. No exact decoded-pixel matches were found. Nineteen images have a short edge below 128 px. Reasons overlap, giving 78 distinct flagged images altogether. Both members of each candidate pair are marked in the manifest. Files were not deleted or moved between partitions.

Detailed [candidate pairs](preparation/duplicate_candidates.json) and [summary](preparation/summary.json) are saved. No flags does not prove that an image is clinically suitable or independent of all others. Every image still has `manual_review=pending`, and `training_ready=false` is explicit. No visual/clinical label validation, training, augmentation or model accuracy measurement was performed.

## Verification

- 13 audit/preparation unit tests passed, covering safe label parsing, source identity/split validation, case counting, ZIP range reads/resumption, oversized/full-download response rejection, truncated ranges, image/hash validation, duplicate flags and label conflicts.
- A complete offline recheck of all 1,446 images succeeded with zero failures. Its three result files matched the download-run outputs byte-for-byte.
- Raw images/archive ranges are excluded by Git. No app routes, predictions, services, installed dependencies or Word report changed.

Next manageable task: review flagged pairs and image suitability, record exclusions, then settle the final training class list. Do not begin baseline training by treating every mechanically unflagged entry as clinically approved. The current mapping is a research project grouping of inherited labels, not a clinical diagnosis standard.

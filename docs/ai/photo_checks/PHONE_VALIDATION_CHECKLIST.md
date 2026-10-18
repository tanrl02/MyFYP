# Independent phone validation log

Use new, non-sensitive test captures when available. Do not put identifying details or real patient records into the demo. Keep photos local; record observations here with anonymous IDs. A skin photograph is not automatically clinically usable. No skin-tone categories should be guessed or inferred.

The earlier Android smoke check confirmed accepted saving and unsuitable-photo rejection after the copy fix. The following expanded matrix is **not yet tested on a phone**. Synthetic challenge results must not be entered as phone observations.

| ID | Capture | Expected behaviour | Observed / retake reason | Status |
|---|---|---|---|---|
| P01 | Clear close-up skin, even light, camera | Check completes; reasonable skin close-up can pass; Save available only on pass | — | Pending |
| P02 | Same photo selected from gallery | Same decision as identical uploaded bytes; no missing-file error | — | Pending |
| P03 | Clear object photo | Retake guidance; Save disabled | — | Pending |
| P04 | Camera covered / near-black frame | Lighting/detail guidance; Save disabled | — | Pending |
| P05 | Intentionally severe out-of-focus photo | Retake guidance; Save disabled | — | Pending |
| P06 | Skin in lower but usable light | Record decision without assuming rejection is correct | — | Pending |
| P07 | Skin with glare or overexposure | Record decision and visible loss of detail; no clinical adequacy claim | — | Pending |
| P08 | Text document / ordinary app screenshot | Retake guidance; Save disabled | — | Pending |
| P09 | Screen containing a large skin photograph | Challenge expected to expose possible false acceptance; record honestly | — | Pending |
| P10 | Accepted photo saved, reopened, patient switched | Saved result returns for owner; another patient cannot see it | — | Pending |

For a failure record camera/gallery, app reload state, approximate check duration, exact visible message, whether Save was enabled and an anonymous photo ID. Do not paste full device file paths, private photographs or identifying information into a committed log. Do not tune thresholds on these cases and then describe the same cases as independent validation.

# Skin-condition education cards

Sources checked: 29 October 2026. Editorial paraphrases of public clinical information; this is not a clinician sign-off or a diagnosis. Both interfaces use packages/shared/src/conditionInformation.ts. Card actions are local state and never change assessments, predictions, reviews or permissions.

## Source mapping

| Model ID | Sources |
| --- | --- |
| acne | [NHS](https://www.nhs.uk/conditions/acne/) |
| eczema | [DermNet dermatitis](https://dermnetnz.org/topics/dermatitis), [NHS atopic eczema](https://www.nhs.uk/conditions/atopic-eczema/) (one subtype; model subtype unspecified) |
| psoriasis | [NHS](https://www.nhs.uk/conditions/psoriasis/) |
| folliculitis | [DermNet](https://dermnetnz.org/topics/folliculitis), [Mayo Clinic](https://www.mayoclinic.org/diseases-conditions/folliculitis/symptoms-causes/syc-20361634) |
| urticaria | [NHS hives](https://www.nhs.uk/conditions/hives/) |
| allergic_contact_dermatitis | [DermNet](https://dermnetnz.org/topics/allergic-contact-dermatitis), NHS [symptoms](https://www.nhs.uk/conditions/contact-dermatitis/symptoms/) and [review guidance](https://www.nhs.uk/conditions/contact-dermatitis/) |
| seborrheic_dermatitis | [DermNet](https://dermnetnz.org/topics/seborrhoeic-dermatitis), [Mayo Clinic](https://www.mayoclinic.org/diseases-conditions/seborrheic-dermatitis/symptoms-causes/syc-20352710) |
| scabies | [NHS](https://www.nhs.uk/conditions/scabies/) |

Definitions/signs use topic references. Review/urgent-care paragraphs use NHS or, for folliculitis and seborrhoeic dermatitis, Mayo Clinic. Guidance is educational, never calculated from a photo or score. No medicine selection/doses, reference images, automated severity judgement or source-provider endorsement. UK service numbers are not copied into the Malaysia app.

## Behaviour and maintenance

About buttons use exact known model IDs. Unknown future IDs remain plain labels. Browse offers all eight topics, including on legacy simulations; simulation labels are not interpreted as predictions. Keyed result components reset open information when assessment ID changes. Existing ownership/sharing/revocation still controls the enclosing record.

Card text is bundled, with no live content fetch. Opening a protected assessment still needs the normal API/access checks. Full source pages need a network connection and open only on an explicit tap, using static HTTPS URLs without assessment/identity parameters. Dashboard source links use noreferrer/noopener. The source-check date records an editorial check, not a medical review. Recheck links/guidance and update the shared catalogue/date together during maintenance; clinical deployment needs the project's clinical content review.

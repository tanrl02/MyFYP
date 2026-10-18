# Photo admission checks

Implemented 18 October 2026. Capture/select → local backend check → preview with pass or retake explanation → Save. Save checks its actual uploaded bytes again. Preflight never saves an assessment. Existing saved photos remain accessible without retroactive checks. Disease results remain explicitly simulated.

Quality checks reject undecodable/unsupported images, files above 5 MiB, sides below 224 pixels, nearly blank dark/washed-out frames, flat frames and severe blur. These conservative engineering thresholds do not establish clinical image quality. Skin content uses a local, frozen OpenAI CLIP ViT-B/32 with skin and non-skin text prompts; no skin-colour threshold or demographic classifier is used. Low-confidence content is blocked along with non-skin content. Missing dependencies/weights fail closed with a retry message.

## Local setup

Use the existing `.venv-ai` environment (Python 3.11+), including the pinned Torch stack in `ai/requirements-ai.txt`, then from the project root:

```powershell
.\.venv-ai\Scripts\python.exe -m pip install -r apps/api/requirements-photo-check.txt
.\.venv-ai\Scripts\python.exe scripts/setup-photo-model.py
.\Start-API.cmd
```

The one-time download is approximately 354 MB and verifies the complete SHA-256. Weights live in ignored `ai/weights/photo-check/`; setup can be rerun safely. The API launcher uses `.venv-ai`, serving the same single backend on port 8000. No separate inference server is required. Requests send photos only to this local backend; no external photo service is called. The first check loads the model and can take longer; the client allows 60 seconds. Inference runs on CPU with four Torch threads. The bounded in-memory cache holds hashes and decisions, not photo bytes.

## Prototype limits and evidence

`docs/ai/photo_checks/development_checks.json` records a fixed development check: 37 reviewed SCIN skin photographs and six public object/texture examples. All 37 skin images passed; all six negatives were rejected or uncertain. No final disease-test images were used. This small convenience set is not a held-out benchmark, a sensitivity estimate or clinical validation. Quality rejection tests use synthetic small, blank and blurred images. API tests inject a content screener so request boundaries can be tested independently of the heavyweight model.

CLIP uses a centre crop. It can miss peripheral context, accept a screen containing a large skin photograph, or confuse unfamiliar objects/textures with skin. A cropped screenshot of skin cannot reliably be distinguished from the original photograph. Prompts mentioning screenshots do not guarantee screenshot detection. Retake messages describe likely content, not proof. Thresholds (`positive >= 0.22`, skin/non-skin margin `>= 0.015`) are prototype engineering choices; the similarity values are not calibrated probabilities. More independent real-phone, skin-tone and negative examples are required before claiming reliability.

Source and licence: [official CLIP repository](https://github.com/openai/CLIP), [model card](https://github.com/openai/CLIP/blob/main/model-card.md). Keep the upstream MIT licence with redistributed weights/code. The local six negative fixtures retain their upstream scikit-image notices and hashes; raw photographs and weights are not committed.

## Manual Android check

1. Ava → Skin check → capture a clear, non-sensitive close-up of skin. Expect Checking then either Passed or an explained retake request. Save stays disabled until Passed.
2. Choose a normal object photo, then a severely blurred/dark photo. Expect retake guidance and disabled Save. A disagreement is evidence to investigate, not permission to claim reliable detection.
3. Save an accepted photo, reopen it from history after restarting, then switch to Noah and confirm Ava's assessment is hidden.
4. If checking fails due to connection/model availability, retry after starting the API. Failure must not enable Save.

Physical-phone verification is pending until confirmed by the user.

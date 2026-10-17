# AI metadata audit

This is a metadata audit, not a trained model. Read [the findings](../docs/ai/DATASET_AUDIT.md) before selecting training data.

From the MyFYP root, using the existing Python environment:

```powershell
.\.venv\Scripts\python.exe ai/audit_metadata.py
.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -v
```

The first command runs offline when the five source CSVs are present. On a new checkout, add `--download` to fetch only the five metadata files in `metadata_sources.json`. It never follows image URLs. Each file is limited to 10 MB and verified against a locked SHA-256 before saving or use. Upstream changes deliberately fail verification; review them before updating the registry.

Raw metadata is ignored under `ai/data/`; aggregate results are tracked under `docs/ai/data_audit/`. `--output-dir` selects another output directory. No additional Python packages are required. Candidate class mappings and SCIN screening thresholds are explicit in `candidate_classes.json`; they remain proposals pending label/source review.

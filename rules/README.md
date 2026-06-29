Step2C rule documents live in this folder.

Files here are the source-of-truth for fixed normalization/storage decisions:
- `age_band_mapping.csv`: age-term mapping carried forward from the prior age normalizer.
- `age_rule.json`: age storage contract, vector format, and infant error rule.
- `storage_contract.json`: canonical storage contract for Step2C fields.
- `gender_rule.json`: male-proportion storage rule.
- `ethnicity_rule.json`: top-6 ethnicity-vector rule and storage format.
- `occupation_rule.json`: occupation storage rule and generated codebook contract.
- `follow_up_time_rule.json`: unit conversion to months.
- `severity_codebook.json`: mild/moderate/severe codes.
- `social_status_codebook.json`: six-category social-status schema.
- `treatment_history_rule.json`: treatment-history storage rule.
- `sample_size_policy.md`: row-level sample-size policy notes.

Generated data-driven codebooks are also written here by Step2C:
- `ethnicity_codebook.csv`
- `occupation_codebook.csv`

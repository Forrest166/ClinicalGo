DEFAULT_PROMPT_TEMPLATE = """You extract initial structured study rows from PubMed-style abstract records.

Hard constraints:
- Return ONLY JSON with shape: {"rows": [ ... ]}.
- Each row must contain exactly these keys:
  source_index, indication, population_raw, severity, treatment_history, target, intervention, intervention_type,
  comparator, outcome_direction, phase, sample_size, follow_up_time, evidence_snippet.
- source_index is required and must match the RECORD id shown in the batch payload.
- If a field is absent, output "".
- Do not fabricate facts.

Row granularity:
- Extract all explicit intervention-comparator-result rows that are supported by the abstract.
- Multi-arm studies may produce multiple rows.
- If a record contains no extractable study row, return no row for that record.

Indication rules:
- indication must contain diagnosis/subtype/comorbidity only, not pure population labels.
- Do not include population descriptors in indication unless they are part of the disease subtype itself.
- If multiple supported conditions are present, join them with " || ".
- Keep the disease phrase concise instead of writing a long narrative label.

Target rules:
- Keep target blank unless a molecular target, receptor, pathway, or biomarker mechanism is explicitly stated.

Intervention / comparator rules:
- intervention and comparator should be short standardized arm labels.
- Keep only the core intervention or comparator label. Exclude arm/group wording, study-design wording, scheduling details, and non-essential abbreviations unless they are needed to distinguish arms.
- Do not place result wording, conclusion wording, population wording, or study-design wording into intervention or comparator.
- intervention_type must be exactly one of:
  Drug, Device, Biological, Procedure, Radiation, Behavioral, Genetic,
  Dietary Supplement, Combination Product, Diagnostic Test, Other

Intervention rules:
- For single-agent drug interventions, prefer this four-slot format exactly:
  DrugName|ReleaseType|DosageFormOrRoute|Dose
- Keep all four slots. If a slot is unknown, leave it empty rather than inventing a value.
- Normalize release type into short codes when possible, such as:
  ER, SR, CR, IR, DR, MR, PR, OROS, Depot
- Preserve explicit dose, dosage form, route, and release type concisely when available, and do not invent missing drug details.
- For non-drug interventions, prefer the shortest canonical label, such as:
  CBT, CBT-I, Exercise, rTMS, tDCS, ECT, MBCT, Mindfulness-based therapy
- For combined active interventions, prefer:
  A + B
- Examples:
  "Aerobic exercise (AE)" -> "Exercise"
  "Esketamine 84 mg nasal spray" -> "Esketamine||nasal spray|84 mg"
  "Venlafaxine XR 75 mg/day" -> "Venlafaxine|ER||75 mg/day"
  "Esketamine/antidepressant (AD)" -> "Esketamine + Antidepressant"

Comparator rules:
- First decide whether the comparator is a standard control condition or an active comparator.
- If the comparator is a standard control condition, normalize it to one of these exact labels only:
  Placebo
  Sham
  Usual care
  Standard care
  Waitlist
  Attention control
  No intervention
  Control
- Common aliases that should collapse into those exact labels include:
  PBO -> Placebo
  normal saline -> Placebo
  TAU / care-as-usual / routine care -> Usual care
  WL / waiting-list / delayed treatment control -> Waitlist
- If the comparator is active rather than a standard control condition, normalize it like intervention instead of forcing it into a control label.
- For active drug comparators, preserve explicit dose, dosage form, route, and release type concisely when available.
- If normalization is uncertain, keep the shortest clean label that preserves treatment identity.

Population Raw rules:
- population_raw is a raw trace field, not normalized population output.
- Keep 1 to 3 short original snippets only.
- Recall-first: preserve concise original enrollment-defining snippets instead of collapsing them into tiny labels.
- Prioritize snippets about age, sex, ethnicity, occupation, social identity/context, and prior/current treatment history or treatment status.
- If space remains, other explicit enrollment-defining context may be kept when concise, such as care setting or a major non-severity comorbidity.
- Prefer complete short snippets over fragmented tokens like "children || 8-18 years" when one short original clause can preserve more information.
- Hard cap: never output more than 3 snippets total. If there are more than 3 candidates, keep the 3 most informative snippets.
- When trimming to 3, prefer numeric age, sex, ethnicity, occupation, social identity/context, or treatment-history snippets over generic referral wording such as "clinically referred adolescents".
- Join multiple snippets with " || ".
- Never place severity scales, score thresholds, sample counts, completer counts, risk stratification,
  diagnosis-only text, study-purpose wording, or arm-assignment wording into population_raw.
- Diagnosis-only text is forbidden, but a richer short original snippet may still contain diagnosis wording if it is needed to keep the snippet readable and the snippet also carries other population context.
- Forbidden examples for population_raw:
  HDRS-17 score >16
  N = 245
  722 completers
  at risk for recurrent depression
  patients with major depressive disorder

Severity rules:
- severity stores baseline severity or enrollment severity/risk qualifiers only.
- Put severity scales, score thresholds, severity labels, and risk stratification here.
- Allowed examples:
  moderate-to-severe
  HDRS-17 score >16
  PHQ-9 >=10
  at risk for recurrent depression
  familial risk for depression
- Do not place pure sample counts or completer counts into severity.

Treatment History rules:
- treatment_history stores prior treatment history, treatment exposure, treatment resistance, or current treatment status only.
- Allowed examples:
  previously untreated
  medication-free
  treatment-naive
  not currently receiving treatment
  prior antidepressant treatment
- Do not place age, sex, ethnicity, occupation, social identity, or severity wording into treatment_history.
- If there are multiple supported treatment-history snippets, join concise snippets with " || ".

Sample size / follow-up rules:
- sample_size should be a clean participant count for the specific extracted row when the arm/group count is explicit.
- If the row-specific arm count is explicit, prefer that arm count over the total study sample size.
- If only the total study sample size is explicit, use the total only when it is clearly row-compatible.
- Prefer "" over guessed arm counts, subgroup counts, completion counts, or narrative text.
- follow_up_time should contain only the main follow-up duration.
- Do not output visit schedules, assessment timelines, or multiple timepoints.
- If multiple follow-up timepoints are reported, return only the latest main follow-up time.

Outcome rules:
- evidence_snippet keeps the strongest short result-supporting sentence or clause.
- evidence_snippet must be a results sentence, not an objective/background/design sentence.
- Do not use study-purpose wording such as "this study aims", "we aim", "objective was", or
  arm-listing/design-only text as evidence_snippet.
- Do not use pure sample-count, completer-count, or risk-enrollment text as evidence_snippet.
- outcome_direction must be exactly one of:
  Positive, Neutral, Negative, Mixed or Unknown

Light-touch rule:
- Keep target, phase, and evidence_snippet close to the abstract wording while staying concise.
"""

DEFAULT_POPULATION_RESCUE_PROMPT = """You repair missing record-level population fields for clinical abstract records.

Hard constraints:
- Return ONLY JSON with shape: {"rows": [ ... ]}.
- Each row must contain exactly these keys:
  source_index, population_raw, severity.
- source_index is required and must match the RECORD id shown in the batch payload.
- Return at most one row per record.
- If a field is absent, output "".
- Do not fabricate facts.

Task:
- Work at the whole-record level, not the intervention-arm level.
- Recover population_raw and severity only when they are explicitly supported by the abstract.

Population Raw rules:
- population_raw is a raw trace field, not a normalized demographic summary.
- Keep 1 to 3 short original snippets only.
- Recall-first: preserve concise original enrollment-defining snippets instead of collapsing them into tiny labels.
- Prioritize snippets about age, sex, ethnicity, occupation, social identity/context, and prior/current treatment history or treatment status.
- If space remains, other explicit enrollment-defining context may be kept when concise, such as care setting or a major non-severity comorbidity.
- Prefer complete short snippets over fragmented tokens like "children || 8-18 years" when one short original clause can preserve more information.
- Hard cap: never output more than 3 snippets total. If there are more than 3 candidates, keep the 3 most informative snippets.
- When trimming to 3, prefer numeric age, sex, ethnicity, occupation, social identity/context, or treatment-history snippets over generic referral wording such as "clinically referred adolescents".
- Join multiple snippets with " || ".
- Never place severity scales, score thresholds, severity labels, sample counts, completer counts,
  risk stratification, diagnosis-only text, study-purpose wording, or arm-assignment wording into population_raw.
- Diagnosis-only text is forbidden, but a richer short original snippet may still contain diagnosis wording if it is needed to keep the snippet readable and the snippet also carries other population context.

Severity rules:
- severity stores baseline severity or enrollment severity/risk qualifiers only.
- Put severity scales, score thresholds, severity labels, and risk stratification here.
- Allowed examples:
  moderate to severe
  HDRS-17 score >16
  PHQ-9 >=10
  at risk for recurrent depression
  current subsyndromal symptoms
- Do not place pure sample counts or completer counts into severity.

Evidence discipline:
- Prefer information from TITLE, PATIENTS, PARTICIPANTS, METHODS, DESIGN, SETTING, BACKGROUND, SUMMARY,
  or any other section that explicitly states who was enrolled.
- Do not infer unstated demographics from diagnosis alone.
- Do not rewrite or normalize into abstract labels if the paper only gives a short original phrase.
"""

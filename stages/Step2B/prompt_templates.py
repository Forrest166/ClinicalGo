DEFAULT_PROMPT_TEMPLATE = """You refine row-level population characteristics from Population Raw only.

Hard constraints:
- Return ONLY JSON with shape: {"rows": [ ... ]}.
- Return exactly one output row for every input row_id.
- Each row must contain exactly these keys:
  row_id, age, gender, ethnicity, occupation, social_status, treatment_history.
- If a field is absent, output "".
- Use Population Raw and the optional Treatment History helper only.
- Population Focus is a helper excerpt derived from Population Raw only.
- Treatment History helper is a raw trace carried over from Step2A; use it only for treatment_history.
- Ignore title-like, intervention-like, outcome-like, and study-design noise.
- Do not fabricate facts.

Field definitions:
- age is participant age information only.
- gender is participant sex/gender composition only.
- ethnicity is participant ethnicity/race only.
- occupation is participant role, job, or student identity.
- social_status is contextual identity or structural/physiological status such as pregnant, postpartum,
  HIV-positive, incarcerated, caregiver, refugee, veteran, low income, or substance use history.
- treatment_history is prior treatment exposure, prior/current treatment status, resistance, or medication status only.
- A detail may appear in more than one field only when it genuinely supports both fields.

Age rules:
- If numeric age is stated, prefer numeric age over descriptive labels.
- Format age range as A-B, mean with SD as A+/-B, and median age as Median A.
- If no numeric age is stated, you may use a short descriptor such as Older adults, Young adults, Adolescents, or 8th grade students.
- If the text looks like sample size rather than age, output "".

Gender rules:
- If gender/sex is stated, normalize men/males/boys as Male and women/females/girls as Female.
- If counts or percentages are stated, report them as X% Male, X% Female, or X% Male + Y% Female.
- If both Male and Female are present without percentages, output Male + Female.
- If gender/sex is absent, uncertain, or cannot be cleanly normalized, output "".

Ethnicity rules:
- If ethnicity/race is stated, normalize it to a concise standard label when possible.
- Use labels such as White, Black, Asian, Hispanic/Latino, Indigenous, Mixed, or Other when they clearly match the source.
- If percentages are stated, report them as X% Label or X% Label + Y% Label.
- If multiple groups are stated without percentages, output Label + Label.
- If ethnicity/race is absent, uncertain, or cannot be cleanly normalized, output "".

Occupation and social status rules:
- Keep both concise.
- Put work/study identity in occupation.
- Put contextual identity or structural/physiological context in social_status.
- Caregiver, parenthood, veteran, refugee, low income, pregnancy, postpartum, HIV-positive,
  incarceration, homelessness, and substance use history belong in social_status.
- Treatment history or treatment status such as previously untreated, unmedicated, medication-free,
  treatment-naive, prior antidepressant treatment, or not currently receiving treatment belongs in treatment_history.
- Do not put study design, severity, or study results in either field.
- Maternal roles such as mother or new mother imply Female when the participant is the mother.
- Do not use dependent or child age, gestational age, or postpartum duration as participant age.

Final self-check:
- Preserve every row_id.
- Output only the allowed keys.
- Leave uncertain fields as "".
"""

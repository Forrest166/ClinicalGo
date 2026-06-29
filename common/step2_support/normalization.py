import re
from typing import Any, Dict, List, Sequence, Tuple

from common.step2_support import population_slots as pop_slots


def normalize_source_index_value(raw_value: Any) -> str:
    text = "" if raw_value is None else str(raw_value).strip()
    if not text:
        return ""
    if text.isdigit():
        return text
    match = re.search(r"\b(\d+)\b", text)
    if match:
        return match.group(1)
    return text



def is_depression_related_indication(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return False
    depression_terms = [
        "depress",
        "mdd",
        "major depressive",
        "treatment-resistant depression",
        "trd",
        "postpartum depression",
        "ppd",
        "peripartum depression",
        "melancholic",
        "atypical depression",
        "psychotic depression",
        "psychotic features",
        "catatonic",
        "seasonal pattern depression",
        "seasonal affective disorder",
        "anxious distress",
        "dysthymi",
        "depressive episode",
        "bipolar depression",
        "perinatal depression",
    ]
    return any(term in lowered for term in depression_terms)



def extract_follow_up_time_from_text(*texts: str) -> str:
    merged = " ".join(str(t or "") for t in texts)
    if not merged.strip():
        return ""

    cleaned = re.sub(r"\s+", " ", merged)
    duration = r"\d+(?:\.\d+)?(?:\s*(?:to|\-|–)\s*\d+(?:\.\d+)?)?\s*(?:-|–|\s)?(?:day|days|week|weeks|month|months|year|years)"
    patterns = [
        rf"\bfollow[- ]?up(?:\s*(?:period|duration|time))?\s*(?:of|for|at|was|is|:)?\s*({duration})\b",
        rf"\b({duration})\s*(?:of\s*)?follow[- ]?up\b",
        rf"\bfollowed\s+(?:participants|patients|subjects)?\s*(?:for)?\s*({duration})\b",
        rf"\bpost[- ]?treatment\s*(?:follow[- ]?up)?\s*(?:at|of|for)?\s*({duration})\b",
    ]

    hits: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, cleaned, flags=re.I):
            value = re.sub(r"\s+", " ", match.group(1)).strip(" ,;.")
            if value and value.lower() not in {h.lower() for h in hits}:
                hits.append(value)
            if len(hits) >= 2:
                break
        if len(hits) >= 2:
            break

    if not hits:
        return ""
    return "; ".join(hits)



def normalize_row_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    def value(key: str) -> str:
        raw = data.get(key, "")
        return "" if raw is None else str(raw).strip()

    def collapse_text(text: str) -> str:
        text = re.sub(r"[\t\r\n]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^\S\r\n]+$", "", text)
        return text.strip(" ;|,-")

    def clean_common_noise(text: str) -> str:
        text = collapse_text(text)
        replacements = {
            "鈥?": "-",
            "鈥": "-",
            "—": "-",
            "–": "-",
            "路": ".",
            "聽": " ",
        }
        for bad, good in replacements.items():
            text = text.replace(bad, good)
        text = re.sub(r"^(intervention|treatment|arm|group|comparator|target|indication)\s*[:：-]\s*", "", text, flags=re.I)
        return text.strip()

    def normalize_intervention_type(raw_type: str, intervention: str) -> str:
        text = clean_common_noise(raw_type).lower()
        intervention_l = intervention.lower()
        if any(marker in intervention_l for marker in [" + ", " plus ", " combined with ", " combining ", " with "]):
            active_combo = not any(token in intervention_l for token in ["usual care", "standard care", "waitlist", "attention control", "sham", "placebo only"])
            if active_combo:
                return "Combination Product"
        mapping = {
            "drug": "Drug",
            "pharmacological": "Drug",
            "medication": "Drug",
            "device": "Device",
            "procedure": "Procedure",
            "surgery": "Procedure",
            "surgical": "Procedure",
            "radiation": "Radiation",
            "behavioral": "Behavioral",
            "behavioural": "Behavioral",
            "psychotherapy": "Behavioral",
            "therapy": "Behavioral",
            "exercise": "Behavioral",
            "lifestyle": "Behavioral",
            "genetic": "Genetic",
            "gene": "Genetic",
            "biological": "Biological",
            "biologic": "Biological",
            "vaccine": "Biological",
            "dietary supplement": "Dietary Supplement",
            "supplement": "Dietary Supplement",
            "combination product": "Combination Product",
            "diagnostic test": "Diagnostic Test",
            "other": "Other",
        }
        for key, normalized in mapping.items():
            if key in text:
                return normalized

        if any(token in intervention_l for token in ["placebo", "ketamine", "escitalopram", "sertraline", "fluoxetine", "drug "]):
            return "Drug"
        if any(token in intervention_l for token in ["exercise", "cbt", "cognitive behavioral", "psychotherapy", "behavioral activation", "mindfulness"]):
            return "Behavioral"
        if any(token in intervention_l for token in ["vitamin", "omega-3", "fish oil", "supplement", "probiotic", "folate", "melatonin"]):
            return "Dietary Supplement"
        if any(token in intervention_l for token in ["rtms", "itbs", "transcranial", "stimulation", "device"]):
            return "Device"
        return "Other"

    def normalize_nct_id(raw_text: str) -> str:
        text = clean_common_noise(raw_text).upper()
        match = re.search(r"\bNCT\d{8}\b", text)
        return match.group(0) if match else ""

    def dedupe_keep_order(items: Sequence[str]) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for item in items:
            value = clean_common_noise(item)
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(value)
        return ordered

    def has_people_descriptor(text: str) -> bool:
        return bool(
            re.search(
                r"\b("
                r"individuals?|persons?|people|patients?|participants?|subjects?|adults?|children|adolescents?|"
                r"schoolchildren|women|men|workers?|employees?|nurses?|students?|veterans?|clients?|"
                r"mothers?|fathers?|survivors?|immigrants?|refugees?|caregivers?"
                r")\b",
                text,
                flags=re.I,
            )
        )

    def split_indication_population_hint(raw_text: str) -> Tuple[str, str]:
        cleaned = clean_common_noise(raw_text)
        if not cleaned:
            return "", ""
        patterns = [
            r"\b(?:in|among|for)\s+([^.;:]{3,180})$",
            r"\b(?:in|among|for)\s+([^.;:]{3,180})(?=[,;.]|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, cleaned, flags=re.I)
            if not match:
                continue
            hint = clean_common_noise(match.group(1))
            if hint and has_people_descriptor(hint):
                base = clean_common_noise(cleaned[: match.start()])
                return base, hint
        return cleaned, ""

    def canonicalize_condition_phrase(text: str) -> str:
        lowered = clean_common_noise(text).lower()
        if not lowered:
            return ""
        mapping = [
            (
                r"\b(?:major depressive disorder|mdd|depressive disorder|depressive episode|depression)\s+with\s+melancholic\s+features\b|"
                r"\bmelancholic depression\b|\bmelancholia\b|\bmelancholic features\b",
                "Melancholic Depression",
            ),
            (
                r"\b(?:major depressive disorder|mdd|depressive disorder|depressive episode|depression)\s+with\s+atypical\s+features\b|"
                r"\batypical depression\b|\batypical features\b",
                "Atypical Depression",
            ),
            (
                r"\b(?:major depressive disorder|mdd|depressive disorder|depressive episode|depression)\s+with\s+psychotic\s+features\b|"
                r"\bpsychotic depression\b|\bdepressive psychosis\b",
                "Psychotic Depression",
            ),
            (
                r"\b(?:major depressive disorder|mdd|depressive disorder|depressive episode|depression)\s+with\s+catatonic\s+features\b|"
                r"\bcatatonic depression\b|\bdepression with catatonia\b",
                "Catatonic Depression",
            ),
            (
                r"\bseasonal affective disorder\b|\bseasonal pattern depression\b|\bdepression with seasonal pattern\b|"
                r"\bmajor depressive disorder with seasonal pattern\b|\bwinter depression\b",
                "Seasonal Pattern Depression",
            ),
            (
                r"\bperipartum depression\b|\bdepression with peripartum onset\b|"
                r"\bpostpartum depression\b|\bpostnatal depression\b|\bpost-natal depression\b|"
                r"\bperinatal depression\b|\bantenatal depression\b|\bprenatal depression\b",
                "Peripartum Depression",
            ),
            (
                r"\b(?:major depressive disorder|mdd|depressive disorder|depressive episode|depression)\s+with\s+anxious distress\b|"
                r"\banxious distress depression\b|\banxious depression\b",
                "Anxious Distress Depression",
            ),
            (r"\bpartially remitted\s+(?:major depressive disorder|mdd)\b", "partially remitted major depressive disorder"),
            (r"\bmajor depressive disorder\b|\bmdd\b|\bmajor depression\b", "major depressive disorder"),
            (r"\btreatment[- ]resistant depression\b|\btrd\b", "treatment-resistant depression"),
            (r"\bbipolar depression\b", "bipolar depression"),
            (r"\bunipolar depressive disorder\b|\bunipolar depression\b", "unipolar depressive disorder"),
            (r"\bdysthymic disorder\b|\bdysthymi[ac]\b", "dysthymic disorder"),
            (r"\bsubthreshold depression\b|\bsubsyndromal depression\b", "subthreshold depression"),
            (r"\bminor depression\b", "minor depression"),
            (r"\bdepressive symptoms?\b", "depressive symptoms"),
            (r"\bdepressive disorder\b", "depressive disorder"),
            (r"\bdepressive episode\b", "depressive episode"),
            (r"\bdepression\b|\bdepressed\b", "depression"),
            (r"\banxiety(?: disorder| symptoms?)?\b", "anxiety"),
            (r"\bpost[- ]traumatic stress disorder\b|\bptsd\b", "post-traumatic stress disorder"),
            (r"\bchronic pain\b", "chronic pain"),
            (r"\binsomnia\b", "insomnia"),
            (r"\bstress\b", "stress"),
            (r"\bhiv(?:/aids)?\b|\baids\b|\bhiv[- ]infected\b", "hiv infection"),
            (r"\balcohol(?: use disorder| dependence| misuse| abuse)?\b", "alcohol use"),
            (r"\bsubstance use(?: disorder)?\b", "substance use"),
            (r"\binjection drug use\b", "injection drug use"),
            (r"\bmethamphetamine(?: use| users?)?\b", "methamphetamine use"),
            (r"\bdiabetes\b", "diabetes"),
            (r"\bobesity\b", "obesity"),
            (r"\bcancer\b", "cancer"),
            (r"\bcopd\b|\bchronic obstructive pulmonary disease\b", "copd"),
            (r"\bparkinson(?:'s)? disease\b|\bpd\b", "parkinson disease"),
            (r"\btraumatic brain injury\b|\btbi\b", "traumatic brain injury"),
        ]
        for pattern, canonical in mapping:
            if re.search(pattern, lowered, flags=re.I):
                return canonical
        if has_people_descriptor(lowered):
            return ""
        trimmed = re.sub(r"\b(?:symptoms?|disorder|syndrome|patients?|individuals?|participants?)\b", "", lowered, flags=re.I)
        trimmed = clean_common_noise(trimmed)
        if not trimmed or len(trimmed) > 60:
            return ""
        return trimmed

    def normalize_indication(raw_text: str, context_text: str = "") -> str:
        text = clean_common_noise(raw_text)
        if not text:
            return ""

        core_text, _ = split_indication_population_hint(text)
        core_text = core_text or text
        context = clean_common_noise(context_text)
        core_canonical = canonicalize_condition_phrase(core_text)
        context_canonical = canonicalize_condition_phrase(context)

        if not is_depression_related_indication(core_text):
            if core_canonical:
                return core_canonical
            if context_canonical:
                return context_canonical
            if has_people_descriptor(core_text):
                return ""
            return core_text

        def is_depression_like(label: str) -> bool:
            lowered = (label or "").lower()
            return (
                "depress" in lowered
                or lowered in {
                    "major depressive disorder",
                    "treatment-resistant depression",
                    "bipolar depression",
                    "postpartum depression",
                    "perinatal depression",
                    "unipolar depressive disorder",
                    "dysthymic disorder",
                    "subthreshold depression",
                    "minor depression",
                    "depressive disorder",
                    "depressive episode",
                    "depression",
                }
            )

        def is_dsm5_subtype(label: str) -> bool:
            return (label or "").strip().lower() in {
                "melancholic depression",
                "atypical depression",
                "psychotic depression",
                "catatonic depression",
                "seasonal pattern depression",
                "peripartum depression",
                "anxious distress depression",
            }

        def extract_context_comorbidities(text_blob: str) -> List[str]:
            blob = clean_common_noise(text_blob).lower()
            if not blob:
                return []
            mapping = [
                (r"\bobesity\b", "obesity"),
                (r"\bcancer\b", "cancer"),
                (r"\bhiv(?:/aids)?\b|\baids\b|\bhiv[- ]infected\b", "hiv infection"),
                (r"\bdiabetes\b", "diabetes"),
                (r"\banxiety(?: disorder| symptoms?)?\b", "anxiety"),
                (r"\bpost[- ]traumatic stress disorder\b|\bptsd\b", "post-traumatic stress disorder"),
                (r"\binsomnia\b", "insomnia"),
                (r"\bchronic pain\b", "chronic pain"),
                (r"\bcopd\b|\bchronic obstructive pulmonary disease\b", "copd"),
                (r"\bparkinson(?:'s)? disease\b|\bpd\b", "parkinson disease"),
                (r"\btraumatic brain injury\b|\btbi\b", "traumatic brain injury"),
                (r"\balcohol(?: use disorder| dependence| misuse| abuse)?\b", "alcohol use"),
                (r"\bsubstance use(?: disorder)?\b", "substance use"),
                (r"\binjection drug use\b", "injection drug use"),
                (r"\bmethamphetamine(?: use| users?)?\b", "methamphetamine use"),
            ]
            hits: List[str] = []
            for pattern, canonical in mapping:
                if re.search(pattern, blob, flags=re.I):
                    hits.append(canonical)
            return dedupe_keep_order(hits)

        findings: List[str] = []
        depression_patterns = [
            r"\b(?:major depressive disorder|mdd|depressive disorder|depressive episode|depression)\s+with\s+melancholic\s+features\b|\bmelancholic depression\b|\bmelancholia\b|\bmelancholic features\b",
            r"\b(?:major depressive disorder|mdd|depressive disorder|depressive episode|depression)\s+with\s+atypical\s+features\b|\batypical depression\b|\batypical features\b",
            r"\b(?:major depressive disorder|mdd|depressive disorder|depressive episode|depression)\s+with\s+psychotic\s+features\b|\bpsychotic depression\b|\bdepressive psychosis\b",
            r"\b(?:major depressive disorder|mdd|depressive disorder|depressive episode|depression)\s+with\s+catatonic\s+features\b|\bcatatonic depression\b|\bdepression with catatonia\b",
            r"\bseasonal affective disorder\b|\bseasonal pattern depression\b|\bdepression with seasonal pattern\b|\bmajor depressive disorder with seasonal pattern\b|\bwinter depression\b",
            r"\bperipartum depression\b|\bdepression with peripartum onset\b|\bpostpartum depression\b|\bpostnatal depression\b|\bpost-natal depression\b|\bperinatal depression\b|\bantenatal depression\b|\bprenatal depression\b",
            r"\b(?:major depressive disorder|mdd|depressive disorder|depressive episode|depression)\s+with\s+anxious distress\b|\banxious distress depression\b|\banxious depression\b",
            r"\bpartially remitted\s+(?:major depressive disorder|mdd)\b",
            r"\btreatment[- ]resistant depression\b|\btrd\b",
            r"\bmajor depressive disorder\b|\bmdd\b|\bmajor depression\b",
            r"\bbipolar depression\b",
            r"\bunipolar depressive disorder\b|\bunipolar depression\b",
            r"\bdysthymic disorder\b|\bdysthymi[ac]\b",
            r"\bsubthreshold depression\b|\bsubsyndromal depression\b",
            r"\bminor depression\b",
            r"\bdepressive symptoms?\b",
            r"\bdepressive disorder\b",
            r"\bdepressive episode\b",
            r"\bdepression\b|\bdepressed\b",
        ]
        for pattern in depression_patterns:
            for match in re.finditer(pattern, core_text, flags=re.I):
                canonical = canonicalize_condition_phrase(match.group(0))
                if canonical:
                    findings.append(canonical)

        coordination_patterns = [
            r"([^,;:.]{2,80})\s+(?:and|or|/)\s+([^,;:.]{2,80})",
            r"([^,;:.]{2,80})\s+with\s+([^,;:.]{2,80})",
        ]
        for pattern in coordination_patterns:
            for match in re.finditer(pattern, core_text, flags=re.I):
                for chunk in (match.group(1), match.group(2)):
                    canonical = canonicalize_condition_phrase(chunk)
                    if canonical:
                        findings.append(canonical)

        context_blob = " ".join(part for part in [core_text, context] if part)
        findings.extend(extract_context_comorbidities(context_blob))

        findings = dedupe_keep_order(findings)
        if len(findings) > 1:
            if any(is_dsm5_subtype(item) for item in findings):
                findings = [item for item in findings if is_dsm5_subtype(item) or not is_depression_like(item)]
            lowered_findings = [(item, item.lower()) for item in findings]
            if any(lowered != "depression" and "depress" in lowered for item, lowered in lowered_findings):
                findings = [item for item in findings if item.lower() != "depression"]
            lowered_findings = [(item, item.lower()) for item in findings]
            if any(lowered != "depressive disorder" and "depressive" in lowered for item, lowered in lowered_findings):
                findings = [item for item in findings if item.lower() != "depressive disorder"]
            depression_first = [item for item in findings if is_depression_like(item)]
            non_depression = [item for item in findings if not is_depression_like(item)]
            findings = depression_first + non_depression
        if not findings:
            return "depression"
        return " || ".join(findings)

    def normalize_population_characteristics(raw_population: str, raw_population_raw: str, raw_indication: str, sample_size: str) -> str:
        population_text = clean_common_noise(raw_population)
        population_raw_text = clean_common_noise(raw_population_raw)
        indication_text = clean_common_noise(raw_indication)
        _, indication_hint = split_indication_population_hint(indication_text)
        merged = clean_common_noise("; ".join(part for part in [population_text, population_raw_text, indication_hint] if part))
        if not merged:
            return "NOT Provided"

        normalized_sample_size = clean_common_noise(sample_size)
        if normalized_sample_size:
            merged = re.sub(rf"\b{re.escape(normalized_sample_size)}\b", "", merged)
        merged = re.sub(r"\bn\s*=\s*\d+\b", "", merged, flags=re.I)
        merged = re.sub(r"\b\d+\s+(?:participants|patients|subjects|individuals|clients)\b", "", merged, flags=re.I)
        merged = collapse_text(merged)

        def extract_age(text: str) -> str:
            range_patterns = [
                r"\baged?\s+(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s*(years?|yrs?)\b",
                r"\baged?\s+(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\b",
                r"\bages?\s+(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\b",
                r"\bage\s+(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s*(years?|yrs?)\b",
                r"\bage\s+(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\b",
                r"\bbetween\s+(\d{1,2})\s+and\s+(\d{1,2})\s*(years?|yrs?)\b",
                r"\b(\d{1,2})\s*(?:-|to)\s*(\d{1,2})-year-old\b",
            ]
            for pattern in range_patterns:
                match = re.search(pattern, text, flags=re.I)
                if match:
                    unit = match.group(3) if match.lastindex and match.lastindex >= 3 else "years"
                    return f"{match.group(1)}-{match.group(2)} {unit}"

            mean_with_sd_patterns = [
                r"\bmean age\s*(?:of|=|:|was)?\s*(\d{1,3}(?:\.\d+)?)\s*(?:years?|yrs?)?\s*(?:±|\+/-)\s*(\d{1,3}(?:\.\d+)?)\b",
                r"\bmean age\s*(?:of|=|:|was)?\s*(\d{1,3}(?:\.\d+)?)\s*(?:years?|yrs?)?\s*(?:\(|,)?\s*(?:sd|s\.d\.|std(?:\.|andard)?\s*deviation)\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*\)?",
            ]
            for pattern in mean_with_sd_patterns:
                match = re.search(pattern, text, flags=re.I)
                if match:
                    return f"Mean {match.group(1)} ± {match.group(2)} years"

            median_match = re.search(r"\bmedian age\s*(?:of|=|:|was)?\s*(\d{1,3}(?:\.\d+)?)", text, flags=re.I)
            if median_match:
                return f"Median {median_match.group(1)} years"

            mean_only_match = re.search(r"\bmean age\s*(?:of|=|:|was)?\s*(\d{1,3}(?:\.\d+)?)", text, flags=re.I)
            if mean_only_match:
                return f"Mean {mean_only_match.group(1)} years"

            textual_age_map = [
                (r"\bschoolchildren\b", "Schoolchildren"),
                (r"\bchildren\b", "Children"),
                (r"\badolescents?\b|\bteenagers?\b", "Adolescents"),
                (r"\byoung adults?\b", "Young adults"),
                (r"\bolder adults?\b|\belderly\b|\bgeriatric\b", "Older adults"),
                (r"\badults?\b", "Adults"),
            ]
            for pattern, label in textual_age_map:
                if re.search(pattern, text, flags=re.I):
                    return label
            return ""

        def extract_gender(text: str) -> str:
            percent_matches: List[str] = []
            for pattern in [
                r"(\d{1,3}(?:\.\d+)?)%\s*(female|women)\b",
                r"(\d{1,3}(?:\.\d+)?)%\s*(male|men)\b",
                r"\b(female|women)\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)%",
                r"\b(male|men)\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)%",
            ]:
                for match in re.finditer(pattern, text, flags=re.I):
                    if match.lastindex == 2 and match.group(1).replace(".", "", 1).isdigit():
                        pct, gender = match.group(1), match.group(2)
                    else:
                        gender, pct = match.group(1), match.group(2)
                    label = "Female" if gender.lower() in {"female", "women"} else "Male"
                    percent_matches.append(f"{pct}% {label}")
            percent_matches = dedupe_keep_order(percent_matches)
            if percent_matches:
                return ", ".join(percent_matches)
            if re.search(r"\b(?:women|female)\b", text, flags=re.I):
                return "Female"
            if re.search(r"\b(?:men|male)\b", text, flags=re.I):
                return "Male"
            return ""

        def extract_severity(text: str) -> str:
            hits: List[str] = []
            patterns = [
                r"\b(?:mild|moderate|severe)(?:\s*(?:to|-)\s*(?:moderate|severe))?\b",
                r"\bfirst[- ]episode\b",
                r"\bnewly diagnosed\b",
                r"\bpartially remitted\b",
                r"\bremitted\b",
                r"\bresidual symptoms?\b",
                r"\b(?:ham-d|hdrs|madrs|bdi|phq-?9?)\s*(?:score|scores)?\s*(?:>=|=>|>|<|<=|=)?\s*\d+(?:\.\d+)?(?:\s*(?:-|to)\s*\d+(?:\.\d+)?)?",
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, text, flags=re.I):
                    hit = clean_common_noise(match.group(0))
                    if hit:
                        hits.append(hit)
            hits = dedupe_keep_order(hits)
            return ", ".join(hits[:3])

        def extract_ethnicity(text: str) -> str:
            hits: List[str] = []
            patterns = [
                (r"\bafrican[- ]american\b", "African-American"),
                (r"\bblack\b", "Black"),
                (r"\bwhite\b|\bcaucasian\b", "White"),
                (r"\bhispanic\b|\blatino\b|\blatina\b", "Hispanic/Latino"),
                (r"\basian\b", "Asian"),
                (r"\bindigenous\b|\bnative american\b", "Indigenous"),
            ]
            for pattern, label in patterns:
                if re.search(pattern, text, flags=re.I):
                    hits.append(label)
            hits = dedupe_keep_order(hits)
            return ", ".join(hits)

        def extract_occupation(text: str) -> str:
            patterns = [
                (r"\boffice workers?\b", "Office workers"),
                (r"\bnurses?\b", "Nurses"),
                (r"\bhealthcare workers?\b", "Healthcare workers"),
                (r"\bteachers?\b", "Teachers"),
                (r"\bemployees?\b", "Employees"),
                (r"\bworkers?\b", "Workers"),
                (r"\bcaregivers?\b", "Caregivers"),
            ]
            for pattern, label in patterns:
                if re.search(pattern, text, flags=re.I):
                    return label
            return ""

        def extract_social_status(text: str) -> str:
            hits: List[str] = []
            patterns = [
                (r"\b(?:living with\s+)?hiv(?:/aids)?\b|\bplwha\b|\bhiv[- ]infected\b", "HIV-infected individuals"),
                (r"\bhiv-related stigma\b", "HIV-related stigma"),
                (r"\bpregnant\b|\bpregnancy\b", "Pregnant"),
                (r"\bpostpartum\b", "Postpartum"),
                (r"\bperinatal\b", "Perinatal"),
                (r"\bveterans?\b", "Veterans"),
                (r"\brural\b", "Rural"),
                (r"\burban\b", "Urban"),
                (r"\blow[- ]income\b|\bpoverty\b|\bpoor\b", "Low-income or poverty"),
                (r"\bhomeless\b", "Homeless"),
                (r"\bimmigrants?\b|\bmigrants?\b|\brefugees?\b", "Immigrant or migrant status"),
                (r"\bleft-behind\b", "Left-behind status"),
                (r"\binjection drug use\b", "History of injection drug use"),
                (r"\balcohol(?: use| misuse| abuse| dependence)?\b", "Alcohol use history"),
                (r"\bsubstance use(?: disorder)?\b", "Substance use history"),
                (r"\bmethamphetamine(?: use| users?)?\b", "Methamphetamine use history"),
            ]
            for pattern, label in patterns:
                if re.search(pattern, text, flags=re.I):
                    hits.append(label)
            hits = dedupe_keep_order(hits)
            return ", ".join(hits)

        def extract_previous_treatment(text: str) -> str:
            hits: List[str] = []
            patterns = [
                (r"\bantidepressant[- ]na[iï]ve\b|\btreatment[- ]na[iï]ve\b|\bdrug[- ]na[iï]ve\b", "Treatment-naive"),
                (r"\bfailed\s+[^.;,]{0,80}?(?:therapy|treatment|antidepressants?)\b", None),
                (r"\bnonresponsive to\s+[^.;,]{0,80}\b", None),
                (r"\bresistant to\s+[^.;,]{0,80}\b", None),
                (r"\bpreviously treated with\s+[^.;,]{0,80}\b", None),
                (r"\bhistory of\s+[^.;,]{0,80}?(?:therapy|treatment)\b", None),
            ]
            for pattern, label in patterns:
                for match in re.finditer(pattern, text, flags=re.I):
                    hit = label or clean_common_noise(match.group(0))
                    if hit:
                        hits.append(hit)
            hits = dedupe_keep_order(hits)
            return ", ".join(hits[:2])

        field_values = [
            ("Age", extract_age(merged)),
            ("Gender", extract_gender(merged)),
            ("Severity", extract_severity(merged)),
            ("Ethnicity", extract_ethnicity(merged)),
            ("Occupation", extract_occupation(merged)),
            ("Social Status", extract_social_status(merged)),
            ("Previous Treatment", extract_previous_treatment(merged)),
        ]
        rendered = [f"{label}: {value}" for label, value in field_values if value]
        return "; ".join(rendered) if rendered else "NOT Provided"

    def normalize_outcome_direction(raw_text: str, result_text: str, evidence_text: str) -> str:
        raw = clean_common_noise(raw_text).lower()
        result = clean_common_noise(result_text).lower()
        evidence = clean_common_noise(evidence_text).lower()
        text = " ".join([raw, result, evidence]).strip()
        if not text:
            return "Mixed or Unknown"

        if raw in {"positive", "improvement", "improved", "increase", "better"}:
            return "Positive"
        if raw in {"neutral", "no difference", "no change", "no significant difference", "no effect"}:
            return "Neutral"
        if raw in {"negative", "worsening", "worsened", "worse", "decrease"}:
            return "Negative"
        if raw in {"mixed", "unknown"} and not result and not evidence:
            return "Mixed or Unknown"

        strong_neutral_terms = [
            "no difference",
            "no change",
            "not significant",
            "no significant",
            "no statistically significant",
            "nonsignificant",
            "non-significant",
            "did not differ",
            "similar improvements",
            "similar improvement",
            "comparable",
            "equivalent",
            "non-inferior",
            "failed to demonstrate",
            "does not support",
            "not effective",
        ]
        strong_positive_terms = [
            "improvement",
            "improved",
            "effective",
            "efficacy",
            "superior",
            "favor of",
            "favouring",
            "benefit",
            "beneficial",
            "response",
            "remission",
            "reduction in depression",
            "reduced depression",
            "reduced depressive",
            "decrease in depression",
            "decrease in depressive",
            "lower depressive",
            "lower depression",
            "alleviation",
            "symptom reduction",
            "recovered",
            "cost-effective",
        ]
        strong_negative_terms = [
            "worsening",
            "worsened",
            "worse",
            "deteriorat",
            "inferior",
            "adverse",
            "higher depression",
            "higher depressive",
            "increased depression",
            "increased depressive",
        ]
        result_evidence_text = " ".join([result, evidence]).strip()

        mixed_patterns = [
            r"\bmixed\s+(?:result|results|finding|findings|effect|effects)\b",
            r"\binconclusive\b",
            r"\bunclear\b",
        ]
        if any(re.search(pattern, result_evidence_text) for pattern in mixed_patterns):
            return "Mixed or Unknown"

        if any(term in text for term in strong_neutral_terms):
            return "Neutral"

        positive_context_patterns = [
            r"(decrease|decreased|reduction|reduced|lower|decline|declined).{0,40}(depress|symptom|ham-d|hdrs|madrs|bdi|phq|suicid)",
            r"(increase|increased|improve|improved).{0,40}(response|remission|help-seeking|working memory|cognition|quality of life)",
            r"(significant|greater|large effect size|favouring|favoring).{0,60}(exercise|intervention|therapy|program|treatment)",
        ]
        negative_context_patterns = [
            r"(increase|increased|higher|worse|worsened|worsening).{0,40}(depress|symptom|ham-d|hdrs|madrs|bdi|phq|suicid)",
        ]

        pos = any(term in text for term in strong_positive_terms) or any(re.search(p, text) for p in positive_context_patterns)
        neg = any(term in text for term in strong_negative_terms) or any(re.search(p, text) for p in negative_context_patterns)

        if pos and not neg:
            return "Positive"
        if neg and not pos:
            return "Negative"
        return "Mixed or Unknown"

    def extract_statistical_metrics(*texts: str) -> str:
        merged = " ".join(clean_common_noise(t) for t in texts if t).strip()
        if not merged:
            return ""
        patterns = [
            r"\bp\s*[<=>]\s*0?\.\d+\b",
            r"\b(?:OR|RR|HR|MD|SMD|aOR|beta)\s*[=:\-]?\s*-?\d+(?:\.\d+)?\b",
            r"\b95%\s*CI\s*[:=\[]\s*[^;,.]{3,60}",
            r"\bCI\s*[:=\[]\s*[^;,.]{3,60}",
            r"\b(?:response|remission)\s*rate\s*[=:\-]?\s*\d+(?:\.\d+)?%?\b",
            r"\b\d+(?:\.\d+)?\s*%\s*(?:vs|compared with)\s*\d+(?:\.\d+)?\s*%",
        ]
        hits: List[str] = []
        for pattern in patterns:
            for match in re.finditer(pattern, merged, flags=re.I):
                snippet = match.group(0).strip(" ,;.")
                if snippet and snippet not in hits:
                    hits.append(snippet)
                if len(hits) >= 8:
                    break
            if len(hits) >= 8:
                break
        return "; ".join(hits)

    def format_component_name(raw_name: str) -> str:
        cleaned = clean_common_noise(raw_name).strip("()[]")
        if not cleaned:
            return ""
        lowered = cleaned.lower()
        fixed = {
            "cbt": "CBT",
            "cbt-i": "CBT-I",
            "ct": "CT",
            "tms": "TMS",
            "rtms": "rTMS",
            "itbs": "iTBS",
            "tdcs": "tDCS",
            "ect": "ECT",
            "fmri": "fMRI",
            "eeg": "EEG",
            "ad": "AD",
            "uc": "UC",
            "sh": "SH",
            "ketamine": "Ketamine",
            "esketamine": "Esketamine",
            "midazolam": "Midazolam",
            "imipramine": "Imipramine",
            "mirtazapine": "Mirtazapine",
            "sertraline": "Sertraline",
            "fluoxetine": "Fluoxetine",
            "escitalopram": "Escitalopram",
            "venlafaxine": "Venlafaxine",
            "duloxetine": "Duloxetine",
            "quetiapine": "Quetiapine",
            "paroxetine": "Paroxetine",
            "citalopram": "Citalopram",
            "bupropion": "Bupropion",
            "nortriptyline": "Nortriptyline",
            "amitriptyline": "Amitriptyline",
            "trazodone": "Trazodone",
            "aripiprazole": "Aripiprazole",
            "olanzapine": "Olanzapine",
            "lithium": "Lithium",
            "placebo": "Placebo",
            "antidepressant": "Antidepressant",
            "psychotherapy": "Psychotherapy",
            "exercise": "Exercise",
            "acetylsalicylic acid": "Acetylsalicylic Acid",
            "aspirin": "Aspirin",
            "buspirone": "Buspirone",
            "lamotrigine": "Lamotrigine",
            "desvenlafaxine": "Desvenlafaxine",
            "vortioxetine": "Vortioxetine",
            "agomelatine": "Agomelatine",
            "mianserin": "Mianserin",
            "milnacipran": "Milnacipran",
            "clomipramine": "Clomipramine",
            "trimipramine": "Trimipramine",
            "moclobemide": "Moclobemide",
            "phenelzine": "Phenelzine",
            "tranylcypromine": "Tranylcypromine",
        }
        if lowered in fixed:
            return fixed[lowered]
        return " ".join(word.upper() if len(word) <= 4 and word.isupper() else word.capitalize() for word in cleaned.split())

    def standardize_control_term(raw_text: str) -> str:
        text = clean_common_noise(raw_text)
        lowered = text.lower()
        mappings = [
            (r"\bpill placebo\b", "Pill placebo"),
            (r"\bplacebo\b", "Placebo"),
            (r"\busual care\b|\btreatment as usual\b|\btau\b", "Usual care"),
            (r"\benhanced usual care\b", "Enhanced usual care"),
            (r"\bstandard care\b", "Standard care"),
            (r"\bwaiting[- ]list control\b|\bwaitlist control\b", "Waitlist control"),
            (r"\battention[- ]control\b|\battention control\b", "Attention control"),
            (r"\bsham(?: stimulation| treatment| control)?\b", "Sham control"),
            (r"\bcontrol condition\b|\bcontrol group\b", "Control"),
            (r"\bno intervention\b", "No intervention"),
            (r"\bobservational\b", "Observational"),
        ]
        for pattern, label in mappings:
            if re.search(pattern, lowered, flags=re.I):
                return label
        return ""

    def extract_dose(raw_text: str) -> str:
        text = clean_common_noise(raw_text)
        patterns = [
            r"\b\d+(?:\.\d+)?\s*(?:mg|g|mcg|ug|μg|ml|mL|IU|units|mmol|mEq)\s*/\s*(?:kg|day|week|dose)\b",
            r"\b\d+(?:\.\d+)?\s*(?:mg|g|mcg|ug|μg|ml|mL|IU|units|mmol|mEq)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                return clean_common_noise(match.group(0))
        return ""

    def extract_dosage_form(raw_text: str) -> str:
        text = clean_common_noise(raw_text)
        mappings = [
            (r"\bnasal spray\b|\bintranasal\b", "nasal spray"),
            (r"\boral\b|\btablets?\b|\bcapsules?\b|\bpills?\b", "oral"),
            (r"\bintravenous\b|\biv\b|\binfusions?\b", "infusion"),
            (r"\binjections?\b|\bintramuscular\b|\bsubcutaneous\b", "injection"),
            (r"\bpatch(?:es)?\b|\btransdermal\b", "transdermal"),
        ]
        for pattern, label in mappings:
            if re.search(pattern, text, flags=re.I):
                return label
        return ""

    def extract_local_dose(raw_text: str, start: int, end: int) -> str:
        window = raw_text[max(0, start - 10) : min(len(raw_text), end + 40)]
        return extract_dose(window)

    def extract_local_dosage_form(raw_text: str, start: int, end: int) -> str:
        window = raw_text[max(0, start - 10) : min(len(raw_text), end + 40)]
        return extract_dosage_form(window)

    def format_component_spec(name: str, dose: str = "", dosage_form: str = "") -> str:
        parts = [f"Name: {name}"]
        if dosage_form:
            parts.append(f"DosageForm: {dosage_form}")
        if dose:
            parts.append(f"Dose: {dose}")
        return "; ".join(parts)

    def format_combination_component(name: str, dose: str = "", dosage_form: str = "") -> str:
        parts = [name]
        if dosage_form:
            parts.append(f"DosageForm: {dosage_form}")
        if dose:
            parts.append(f"Dose: {dose}")
        return "; ".join(parts)

    NON_DRUG_COMPONENT_LABELS = {
        "TMS",
        "rTMS",
        "iTBS",
        "tDCS",
        "ECT",
        "CBT-I",
        "CBT",
        "CT",
        "Psychotherapy",
        "Exercise",
    }

    def extract_named_components_with_pos(raw_text: str) -> List[Tuple[int, int, str]]:
        text = clean_common_noise(raw_text)
        lowered = text.lower()
        patterns = [
            (r"\besketamine\b", "Esketamine"),
            (r"\bketamine\b", "Ketamine"),
            (r"\bmidazolam\b", "Midazolam"),
            (r"\bimipramine\b", "Imipramine"),
            (r"\bmirtazapine\b", "Mirtazapine"),
            (r"\bsertraline\b", "Sertraline"),
            (r"\bfluoxetine\b", "Fluoxetine"),
            (r"\bescitalopram\b", "Escitalopram"),
            (r"\bvenlafaxine(?:-er| extended-release)?\b", "Venlafaxine"),
            (r"\bduloxetine\b", "Duloxetine"),
            (r"\bquetiapine\b", "Quetiapine"),
            (r"\bparoxetine\b", "Paroxetine"),
            (r"\bcitalopram\b", "Citalopram"),
            (r"\bbupropion\b", "Bupropion"),
            (r"\bnortriptyline\b", "Nortriptyline"),
            (r"\bamitriptyline\b", "Amitriptyline"),
            (r"\btrazodone\b", "Trazodone"),
            (r"\baripiprazole\b", "Aripiprazole"),
            (r"\bolanzapine\b", "Olanzapine"),
            (r"\blithium\b", "Lithium"),
            (r"\bplacebo\b", "Placebo"),
            (r"\bacetylsalicylic acid\b|\baspirin\b", "Acetylsalicylic Acid"),
            (r"\bbuspirone\b", "Buspirone"),
            (r"\blamotrigine\b", "Lamotrigine"),
            (r"\bdesvenlafaxine\b", "Desvenlafaxine"),
            (r"\bvortioxetine\b", "Vortioxetine"),
            (r"\bagomelatine\b", "Agomelatine"),
            (r"\bmianserin\b", "Mianserin"),
            (r"\bmilnacipran\b", "Milnacipran"),
            (r"\bclomipramine\b", "Clomipramine"),
            (r"\btrimipramine\b", "Trimipramine"),
            (r"\bmoclobemide\b", "Moclobemide"),
            (r"\bphenelzine\b", "Phenelzine"),
            (r"\btranylcypromine\b", "Tranylcypromine"),
            (r"\btranscranial magnetic stimulation\b|\btms\b", "TMS"),
            (r"\brtms\b", "rTMS"),
            (r"\bitbs\b", "iTBS"),
            (r"\btdcs\b", "tDCS"),
            (r"\bect\b", "ECT"),
            (r"\bcognitive[- ]behavio(?:u)?ral therapy for insomnia\b|\bcbt-i\b", "CBT-I"),
            (r"\bcognitive[- ]behavio(?:u)?ral therapy\b|\bcbt\b", "CBT"),
            (r"\bcognitive therapy\b", "CT"),
            (r"\bantidepressants?\b|\bantidepressant\b", "Antidepressant"),
            (r"\bpsychotherapy\b", "Psychotherapy"),
            (r"\bexercise\b", "Exercise"),
        ]
        hits_with_pos: List[Tuple[int, int, str]] = []
        for pattern, label in patterns:
            for match in re.finditer(pattern, lowered, flags=re.I):
                hits_with_pos.append((match.start(), match.end(), label))
        hits_with_pos.sort(key=lambda item: item[0])
        seen: set[str] = set()
        ordered: List[Tuple[int, int, str]] = []
        for start, end, label in hits_with_pos:
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append((start, end, label))
        return ordered

    def extract_named_components(raw_text: str) -> List[str]:
        return [label for _, _, label in extract_named_components_with_pos(raw_text)]

    def looks_drug_like(raw_text: str, intervention_type: str) -> bool:
        lowered = clean_common_noise(raw_text).lower()
        if intervention_type in {"Drug", "Combination Product"}:
            return True
        if extract_dose(lowered) or extract_dosage_form(lowered):
            return True
        return bool(extract_named_components(lowered))

    def strip_arm_noise(raw_text: str) -> str:
        text = clean_common_noise(raw_text)
        text = re.sub(r"^(intervention|comparator|treatment|arm|group)\s*[:：-]\s*", "", text, flags=re.I)
        text = re.sub(r"^(?:switch(?:ing)? to|switch to|add[- ]on|adding|adjunctive|augmentation with|continu(?:e|ing)|combined?|combining|received|treated with)\s+", "", text, flags=re.I)
        text = re.sub(r"^\b(?:single|double|six repeated|repeated|repeat|once[- ]daily|twice[- ]daily)\b\s+", "", text, flags=re.I)
        text = collapse_text(text)
        return text

    def clean_non_drug_label(raw_text: str) -> str:
        text = strip_arm_noise(raw_text)
        control = standardize_control_term(text)
        if control:
            return control
        text = re.sub(r"\b(control condition|intervention condition|active comparator)\b", "", text, flags=re.I)
        text = re.sub(r"\bintervention\b$", "", text, flags=re.I)
        text = collapse_text(text)
        if len(text) > 140:
            text = re.split(r"[;,.]", text, maxsplit=1)[0].strip()
        return text

    def standardize_drugish_segment(raw_text: str) -> str:
        text = strip_arm_noise(raw_text)
        control = standardize_control_term(text)
        if control and control != "Placebo":
            return control
        component_hits = extract_named_components_with_pos(text)
        components = [label for _, _, label in component_hits]
        global_dose = extract_dose(text)
        global_dosage_form = extract_dosage_form(text)
        parts: List[str] = []
        active_placebo = "active placebo" in text.lower()
        non_placebo_components = [item for item in components if item != "Placebo"]
        if active_placebo and len(non_placebo_components) == 1:
            label = non_placebo_components[0]
            if label in NON_DRUG_COMPONENT_LABELS:
                parts.append(label)
            else:
                parts.append(format_component_spec(label))
        elif len(components) >= 2:
            combo_parts: List[str] = []
            for start, end, label in component_hits:
                combo_parts.append(
                    format_combination_component(
                        label,
                        extract_local_dose(text, start, end),
                        extract_local_dosage_form(text, start, end),
                    )
                )
            parts.append(f"Combination: {' + '.join(part for part in combo_parts if part)}")
        elif components == ["Placebo"]:
            parts.append(format_component_spec("Placebo"))
        elif len(components) == 1:
            label = components[0]
            if label in NON_DRUG_COMPONENT_LABELS:
                parts.append(label)
            else:
                parts.append(format_component_spec(label, global_dose, global_dosage_form))
        else:
            fallback = clean_non_drug_label(text)
            if fallback:
                return fallback
        return " + ".join(part for part in parts if part)

    def standardize_arm_text(raw_text: str, intervention_type: str) -> str:
        text = clean_common_noise(raw_text)
        if not text:
            return ""
        segments = [seg.strip() for seg in re.split(r"\s*;\s*", text) if seg.strip()]
        standardized_segments: List[str] = []
        for segment in segments or [text]:
            standardized = standardize_drugish_segment(segment) if looks_drug_like(segment, intervention_type) else clean_non_drug_label(segment)
            standardized_segments.append(standardized or clean_non_drug_label(segment))
        return " | ".join(seg for seg in standardized_segments if seg)

    def clean_intervention(raw_text: str) -> str:
        text = clean_common_noise(raw_text)
        text = re.sub(r"^\d+\s+(?:daily|weekly|monthly)\s+(?:therapy\s+)?sessions?\s+of\s+", "", text, flags=re.I)
        text = re.sub(r"^\d+\s*(?:year|years|week|weeks|month|months|day|days)\s+of\s+", "", text, flags=re.I)
        text = re.sub(r"\bconsisted of\b.*$", "", text, flags=re.I)
        text = re.sub(r"\s*\((control|placebo|active comparator|usual care|uc)\)\s*$", "", text, flags=re.I)
        text = re.sub(r"\b(randomized|randomised|assigned|allocation|group|arm)\b.*$", "", text, flags=re.I)
        text = re.sub(
            r"\b\d+\s*(?:year|years|week|weeks|month|months|day|days|(?:therapy\s+)?session|(?:therapy\s+)?sessions|visit|visits|minute|minutes|min)\b.*$",
            "",
            text,
            flags=re.I,
        )
        text = re.sub(r"\b(delivered|provided|administered|compared?|versus|vs\.?)\b.*$", "", text, flags=re.I)
        text = collapse_text(text)
        if len(text) > 120:
            text = re.split(r"[;,.]", text, maxsplit=1)[0].strip()
        return text

    def clean_target(raw_text: str, intervention: str, indication: str) -> str:
        text = clean_common_noise(raw_text)
        if not text:
            return ""
        lowered = text.lower()
        if lowered in {intervention.lower(), indication.lower()}:
            return ""
        if any(bad in lowered for bad in ["randomized", "depression", "study", "trial", "patients", "psychotherapy", "exercise", "session", "weekly"]):
            target_signals = ["receptor", "pathway", "axis", "transporter", "inflammation", "bdnf", "nmda", "gaba", "5-ht", "seroton", "dopamin", "glutamat", "hpa", "trkb", "d2", "d3", "mao"]
            if not any(sig in lowered for sig in target_signals):
                return ""
        if len(text.split()) > 8:
            return ""
        if len(text) > 80:
            return ""
        return text

    def parse_population_characteristics_fields(text: str) -> Dict[str, str]:
        return pop_slots.parse_population_characteristics_fields(text, clean_common_noise)

    def render_population_characteristics_fields(fields: Dict[str, str]) -> str:
        return pop_slots.render_population_characteristics_fields(fields, clean_common_noise)

    def normalize_slot_value(raw_value: str, label: str = "") -> str:
        return pop_slots.normalize_slot_value(raw_value, clean_common_noise, label)
        value = clean_common_noise(raw_value)
        if not value:
            return ""
        if label:
            value = re.sub(rf"^{re.escape(label)}\s*[:：]\s*", "", value, flags=re.I)
            value = clean_common_noise(value)
        if value.lower() in {"not provided", "unknown", "n/a", "na"}:
            return ""
        return value

    def normalize_age_from_slots(slots: Dict[str, str]) -> str:
        return pop_slots.normalize_age_from_slots(slots, clean_common_noise)
        age_type = normalize_slot_value(slots.get("population_age_type", "")).lower()
        age_value = normalize_slot_value(slots.get("population_age_value", ""))
        age_sd = normalize_slot_value(slots.get("population_age_sd", ""))
        age_unit = normalize_slot_value(slots.get("population_age_unit", "")).lower()
        age_descriptor = normalize_slot_value(slots.get("population_age_descriptor", ""))

        if not age_value and age_descriptor:
            descriptor_map = [
                (r"\bschoolchildren\b", "Schoolchildren"),
                (r"\bchildren?\b", "Children"),
                (r"\badolescents?\b|\bteenagers?\b", "Adolescents"),
                (r"\byoung adults?\b", "Young adults"),
                (r"\bolder adults?\b|\belderly\b|\bgeriatric\b", "Older adults"),
                (r"\badults?\b", "Adults"),
            ]
            lowered = age_descriptor.lower()
            for pattern, label in descriptor_map:
                if re.search(pattern, lowered, flags=re.I):
                    return label
            return age_descriptor
        if not age_value:
            return ""

        unit = "years"
        if "month" in age_unit:
            unit = "months"
        elif "week" in age_unit:
            unit = "weeks"
        elif "day" in age_unit:
            unit = "days"
        elif "year" in age_unit or age_unit in {"yr", "yrs", "y"}:
            unit = "years"

        if age_type in {"mean", "average", "avg"}:
            return f"Mean {age_value} ± {age_sd} {unit}" if age_sd else f"Mean {age_value} {unit}"
        if age_type in {"median"}:
            return f"Median {age_value} {unit}"
        if age_type in {"range"}:
            return f"{age_value} {unit}" if not re.search(r"\b(?:day|days|week|weeks|month|months|year|years|yr|yrs)\b", age_value, flags=re.I) else age_value
        if age_type in {"text", "textual", "descriptor"}:
            return age_value

        if age_sd:
            return f"Mean {age_value} ± {age_sd} {unit}"
        return f"{age_value} {unit}" if re.search(r"\d", age_value) and not re.search(r"\b(?:day|days|week|weeks|month|months|year|years|yr|yrs)\b", age_value, flags=re.I) else age_value

    def merge_population_slots(
        base_population_characteristics: str,
        slots: Dict[str, str],
    ) -> str:
        return pop_slots.merge_population_slots(base_population_characteristics, slots, clean_common_noise)
        fields = parse_population_characteristics_fields(base_population_characteristics)

        age_from_slots = normalize_age_from_slots(slots)
        if age_from_slots:
            fields["Age"] = age_from_slots

        slot_to_label = {
            "population_gender": "Gender",
            "population_severity": "Severity",
            "population_ethnicity": "Ethnicity",
            "population_occupation": "Occupation",
            "population_social_status": "Social Status",
            "population_previous_treatment": "Previous Treatment",
        }
        for slot_key, label in slot_to_label.items():
            value = normalize_slot_value(slots.get(slot_key, ""), label)
            if value:
                fields[label] = value

        return render_population_characteristics_fields(fields)

    raw_indication = value("indication")
    raw_population = value("population_characteristics")
    raw_population_raw = value("population_raw")
    raw_sample_size = value("sample_size")
    raw_intervention = value("intervention")
    raw_comparator = value("comparator")

    preliminary_intervention = clean_intervention(raw_intervention)
    intervention_type = normalize_intervention_type(value("intervention_type"), preliminary_intervention or raw_intervention)
    intervention = standardize_arm_text(raw_intervention or preliminary_intervention, intervention_type)
    comparator = standardize_arm_text(raw_comparator, intervention_type)
    indication_context = "; ".join(part for part in [raw_population_raw, raw_population] if part)
    indication = normalize_indication(raw_indication, indication_context)
    llm_population_slots = pop_slots.collect_population_slots(value)
    population_characteristics_base = normalize_population_characteristics(raw_population, raw_population_raw, raw_indication, raw_sample_size)
    population_characteristics = pop_slots.merge_population_slots(
        population_characteristics_base,
        llm_population_slots,
        clean_common_noise,
    )
    population_age_type = normalize_slot_value(llm_population_slots.get("population_age_type", ""))
    population_age_value = pop_slots.normalize_age_export_value(llm_population_slots, clean_common_noise)
    population_age_sd = normalize_slot_value(llm_population_slots.get("population_age_sd", ""))
    population_age_unit = normalize_slot_value(llm_population_slots.get("population_age_unit", ""))
    population_age_descriptor = normalize_slot_value(llm_population_slots.get("population_age_descriptor", ""))
    population_age_evidence_span = clean_common_noise(llm_population_slots.get("population_age_evidence_span", ""))
    population_gender = pop_slots.normalize_gender_from_slot(llm_population_slots.get("population_gender", ""), clean_common_noise)
    population_gender_evidence_span = clean_common_noise(llm_population_slots.get("population_gender_evidence_span", ""))
    population_severity = normalize_slot_value(llm_population_slots.get("population_severity", ""), "Severity")
    population_severity_evidence_span = clean_common_noise(llm_population_slots.get("population_severity_evidence_span", ""))
    population_ethnicity = pop_slots.normalize_ethnicity_from_slot(llm_population_slots.get("population_ethnicity", ""), clean_common_noise)
    population_ethnicity_evidence_span = clean_common_noise(llm_population_slots.get("population_ethnicity_evidence_span", ""))
    population_occupation = normalize_slot_value(llm_population_slots.get("population_occupation", ""), "Occupation")
    population_occupation_evidence_span = clean_common_noise(llm_population_slots.get("population_occupation_evidence_span", ""))
    population_social_status = normalize_slot_value(llm_population_slots.get("population_social_status", ""), "Social Status")
    population_social_status_evidence_span = clean_common_noise(llm_population_slots.get("population_social_status_evidence_span", ""))
    population_previous_treatment = normalize_slot_value(llm_population_slots.get("population_previous_treatment", ""), "Previous Treatment")
    population_previous_treatment_evidence_span = clean_common_noise(llm_population_slots.get("population_previous_treatment_evidence_span", ""))
    population_raw = clean_common_noise(raw_population_raw or raw_population)
    target = clean_target(value("target"), intervention, indication)
    result_text = clean_common_noise(value("result"))
    evidence_text = clean_common_noise(value("evidence_snippet"))
    statistical_metrics = clean_common_noise(value("statistical_metrics")) or extract_statistical_metrics(result_text, evidence_text, value("notes"))
    follow_up_time = clean_common_noise(value("follow_up_time")) or extract_follow_up_time_from_text(
        value("follow_up_time"),
        result_text,
        evidence_text,
        value("notes"),
    )
    if evidence_text and statistical_metrics and not re.search(r"\b(?:p\s*[<=>]\s*0?\.\d+|95%\s*CI|OR\s*[=:\-]?|RR\s*[=:\-]?|HR\s*[=:\-]?)", evidence_text, flags=re.I):
        evidence_text = f"{evidence_text} | Stats: {statistical_metrics}"
    outcome_direction = normalize_outcome_direction(value("outcome_direction"), result_text, evidence_text)

    return dict(
        source_index=normalize_source_index_value(value("source_index")),
        pmid=clean_common_noise(value("pmid")),
        nct_id=normalize_nct_id(value("nct_id")),
        journal=clean_common_noise(value("journal")),
        year=value("year"),
        indication=indication,
        population_characteristics=population_characteristics,
        population_raw=population_raw,
        target=target,
        intervention=intervention,
        intervention_type=intervention_type,
        comparator=comparator,
        result=result_text,
        outcome_direction=outcome_direction,
        phase=value("phase"),
        sample_size=raw_sample_size,
        follow_up_time=follow_up_time,
        evidence_snippet=evidence_text,
        statistical_metrics=statistical_metrics,
        notes=clean_common_noise(value("notes")),
        population_age_type=population_age_type,
        population_age_value=population_age_value,
        population_age_sd=population_age_sd,
        population_age_unit=population_age_unit,
        population_age_descriptor=population_age_descriptor,
        population_age_evidence_span=population_age_evidence_span,
        population_gender=population_gender,
        population_gender_evidence_span=population_gender_evidence_span,
        population_severity=population_severity,
        population_severity_evidence_span=population_severity_evidence_span,
        population_ethnicity=population_ethnicity,
        population_ethnicity_evidence_span=population_ethnicity_evidence_span,
        population_occupation=population_occupation,
        population_occupation_evidence_span=population_occupation_evidence_span,
        population_social_status=population_social_status,
        population_social_status_evidence_span=population_social_status_evidence_span,
        population_previous_treatment=population_previous_treatment,
        population_previous_treatment_evidence_span=population_previous_treatment_evidence_span,
    )

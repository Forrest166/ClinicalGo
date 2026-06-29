import re
from typing import Callable, Dict


POPULATION_FIELD_ORDER = [
    "Age",
    "Gender",
    "Severity",
    "Ethnicity",
    "Occupation",
    "Social Status",
    "Previous Treatment",
]

SLOT_LABEL_MAP = {
    "population_gender": "Gender",
    "population_severity": "Severity",
    "population_ethnicity": "Ethnicity",
    "population_occupation": "Occupation",
    "population_social_status": "Social Status",
    "population_previous_treatment": "Previous Treatment",
}

ETHNICITY_CANONICAL_LABELS = [
    (r"(?:\bafrican[- ]american\b)", "African-American"),
    (r"(?:\bblack\b)", "Black"),
    (r"(?:\bwhite\b|\bcaucasian\b)", "White"),
    (r"(?:\bhispanic\b|\blatino\b|\blatina\b)", "Hispanic/Latino"),
    (r"(?:\basian\b)", "Asian"),
    (r"(?:\bindigenous\b|\bnative american\b)", "Indigenous"),
    (r"(?:\bmixed\b|\bmultiracial\b)", "Mixed"),
    (r"(?:\bother\b)", "Other"),
]

_FULLWIDTH_COLON_RE = "(?:\\:|" + chr(0xFF1A) + ")"
_DASH_VARIANTS_RE = r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFE58\uFE63\uFF0D]"
_PLUS_MINUS_VARIANTS_RE = r"(?:\+/-|\u00B1)"


def parse_population_characteristics_fields(
    text: str,
    clean_fn: Callable[[str], str],
) -> Dict[str, str]:
    cleaned = clean_fn(text)
    if not cleaned or cleaned.lower() in {"not provided", "unknown", "n/a", "na"}:
        return {}
    fields: Dict[str, str] = {}
    known_labels = {
        "age": "Age",
        "gender": "Gender",
        "severity": "Severity",
        "ethnicity": "Ethnicity",
        "occupation": "Occupation",
        "social status": "Social Status",
        "previous treatment": "Previous Treatment",
    }
    for part in [p.strip() for p in cleaned.split(";") if p.strip()]:
        if ":" not in part:
            continue
        raw_label, raw_value = part.split(":", 1)
        label = known_labels.get(raw_label.strip().lower())
        value = clean_fn(raw_value)
        if label and value:
            fields[label] = value
    return fields


def render_population_characteristics_fields(
    fields: Dict[str, str],
    clean_fn: Callable[[str], str],
) -> str:
    parts = [f"{label}: {clean_fn(fields.get(label, ''))}" for label in POPULATION_FIELD_ORDER if clean_fn(fields.get(label, ""))]
    return "; ".join(parts) if parts else "NOT Provided"


def normalize_slot_value(
    raw_value: str,
    clean_fn: Callable[[str], str],
    label: str = "",
) -> str:
    value = clean_fn(raw_value)
    if not value:
        return ""
    if label:
        value = re.sub(rf"^{re.escape(label)}\s*{_FULLWIDTH_COLON_RE}\s*", "", value, flags=re.I)
        value = clean_fn(value)
    if value.lower() in {"not provided", "unknown", "n/a", "na", "not specified", "unspecified", "none reported", "not reported"}:
        return ""
    return value


def normalize_age_export_value(
    slots: Dict[str, str],
    clean_fn: Callable[[str], str],
) -> str:
    age_value = normalize_slot_value(slots.get("population_age_value", ""), clean_fn)
    age_sd = normalize_slot_value(slots.get("population_age_sd", ""), clean_fn)
    age_type = normalize_slot_value(slots.get("population_age_type", ""), clean_fn).lower()
    if not age_value:
        return ""

    value = re.sub(_PLUS_MINUS_VARIANTS_RE, "+/-", age_value)
    value = re.sub(_DASH_VARIANTS_RE, "-", value)
    value = re.sub(r"\bto\b", "-", value, flags=re.I)
    value = re.sub(r"\band\b", "-", value, flags=re.I)
    value = re.sub(r"^(?:mean|average|avg|median|aged)\s*", "", value, flags=re.I)
    value = re.sub(r"\b(?:years?|yrs?|yr|months?|mos?|weeks?|wks?|days?)\b", "", value, flags=re.I)
    value = re.sub(r"[\(\)\[\]]", "", value)
    value = re.sub(r"\s+", "", value)

    range_match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*[-/]\s*(\d{1,3}(?:\.\d+)?)", value)
    if range_match:
        return f"{range_match.group(1)}-{range_match.group(2)}"

    plus_minus_match = re.search(r"(\d{1,3}(?:\.\d+)?)\+/-\s*(\d{1,3}(?:\.\d+)?)", value)
    if plus_minus_match:
        return f"{plus_minus_match.group(1)}+/-{plus_minus_match.group(2)}"

    number_hits = re.findall(r"\d{1,3}(?:\.\d+)?", value)
    if age_type == "range" and len(number_hits) >= 2:
        return f"{number_hits[0]}-{number_hits[1]}"

    if age_sd:
        sd_value = re.sub(_PLUS_MINUS_VARIANTS_RE, "+/-", age_sd)
        sd_value = re.sub(r"\b(?:years?|yrs?|yr|months?|mos?|weeks?|wks?|days?)\b", "", sd_value, flags=re.I)
        sd_value = re.sub(r"\s+", "", sd_value)
        left_match = re.search(r"(\d{1,3}(?:\.\d+)?)", value)
        right_match = re.search(r"(\d{1,3}(?:\.\d+)?)", sd_value)
        if left_match and right_match:
            return f"{left_match.group(1)}+/-{right_match.group(1)}"

    plain_match = re.search(r"(\d{1,3}(?:\.\d+)?)", value)
    if plain_match:
        return plain_match.group(1)
    return ""


def normalize_gender_from_slot(
    raw_value: str,
    clean_fn: Callable[[str], str],
) -> str:
    value = normalize_slot_value(raw_value, clean_fn, "Gender")
    if not value:
        return ""

    text = value.lower()
    text = text.replace("women", "female").replace("woman", "female")
    text = text.replace("men", "male").replace("man", "male")
    text = text.replace("girls", "female").replace("boys", "male")

    percent_hits = []
    for pattern in [
        r"(\d{1,3}(?:\.\d+)?)\s*%\s*(female|male)\b",
        r"\b(female|male)\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*%",
    ]:
        for match in re.finditer(pattern, text, flags=re.I):
            if match.group(1).replace(".", "", 1).isdigit():
                pct, gender = match.group(1), match.group(2)
            else:
                gender, pct = match.group(1), match.group(2)
            percent_hits.append(f"{pct}% {gender.lower()}")
    percent_hits = list(dict.fromkeys(percent_hits))
    if percent_hits:
        return ";".join(percent_hits)

    has_female = bool(re.search(r"\bfemale\b", text, flags=re.I))
    has_male = bool(re.search(r"\bmale\b", text, flags=re.I))
    if has_female and has_male:
        return "male;female"
    if has_female:
        return "female"
    if has_male:
        return "male"
    return ""


def normalize_ethnicity_from_slot(
    raw_value: str,
    clean_fn: Callable[[str], str],
) -> str:
    value = normalize_slot_value(raw_value, clean_fn, "Ethnicity")
    if not value:
        return ""

    text = value.lower()
    percent_hits = []
    for pattern, label in ETHNICITY_CANONICAL_LABELS:
        for percent_pattern in [
            rf"(\d{{1,3}}(?:\.\d+)?)\s*%\s*{pattern}",
            rf"{pattern}\s*[:=]?\s*(\d{{1,3}}(?:\.\d+)?)\s*%",
        ]:
            for match in re.finditer(percent_pattern, text, flags=re.I):
                pct = match.group(1)
                percent_hits.append(f"{pct}% {label}")
    percent_hits = list(dict.fromkeys(percent_hits))
    if percent_hits:
        return ";".join(percent_hits)

    labels = []
    for pattern, label in ETHNICITY_CANONICAL_LABELS:
        if re.search(pattern, text, flags=re.I):
            labels.append(label)
    labels = list(dict.fromkeys(labels))
    return ";".join(labels)


def normalize_age_from_slots(
    slots: Dict[str, str],
    clean_fn: Callable[[str], str],
) -> str:
    age_type = normalize_slot_value(slots.get("population_age_type", ""), clean_fn).lower()
    age_value = normalize_slot_value(slots.get("population_age_value", ""), clean_fn)
    age_sd = normalize_slot_value(slots.get("population_age_sd", ""), clean_fn)
    age_unit = normalize_slot_value(slots.get("population_age_unit", ""), clean_fn).lower()
    age_descriptor = normalize_slot_value(slots.get("population_age_descriptor", ""), clean_fn)

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
        return f"Mean {age_value} +/- {age_sd} {unit}" if age_sd else f"Mean {age_value} {unit}"
    if age_type == "median":
        return f"Median {age_value} {unit}"
    if age_type == "range":
        normalized_range = normalize_age_export_value(slots, clean_fn)
        if normalized_range:
            return f"{normalized_range} {unit}"
        if re.search(r"\b(?:day|days|week|weeks|month|months|year|years|yr|yrs)\b", age_value, flags=re.I):
            return age_value
        return f"{age_value} {unit}"
    if age_type in {"text", "textual", "descriptor"}:
        return age_value

    if age_sd:
        return f"Mean {age_value} +/- {age_sd} {unit}"
    if re.search(r"\d", age_value) and not re.search(r"\b(?:day|days|week|weeks|month|months|year|years|yr|yrs)\b", age_value, flags=re.I):
        return f"{age_value} {unit}"
    return age_value


def merge_population_slots(
    base_population_characteristics: str,
    slots: Dict[str, str],
    clean_fn: Callable[[str], str],
) -> str:
    fields = parse_population_characteristics_fields(base_population_characteristics, clean_fn)

    age_from_slots = normalize_age_from_slots(slots, clean_fn)
    if age_from_slots:
        fields["Age"] = age_from_slots

    for slot_key, label in SLOT_LABEL_MAP.items():
        if slot_key == "population_gender":
            value = normalize_gender_from_slot(slots.get(slot_key, ""), clean_fn)
        elif slot_key == "population_ethnicity":
            value = normalize_ethnicity_from_slot(slots.get(slot_key, ""), clean_fn)
        else:
            value = normalize_slot_value(slots.get(slot_key, ""), clean_fn, label)
        if value:
            fields[label] = value

    return render_population_characteristics_fields(fields, clean_fn)


def collect_population_slots(value_getter: Callable[[str], str]) -> Dict[str, str]:
    return {
        "population_age_type": value_getter("population_age_type"),
        "population_age_value": value_getter("population_age_value"),
        "population_age_sd": value_getter("population_age_sd"),
        "population_age_unit": value_getter("population_age_unit"),
        "population_age_descriptor": value_getter("population_age_descriptor"),
        "population_age_evidence_span": value_getter("population_age_evidence_span"),
        "population_gender": value_getter("population_gender"),
        "population_gender_evidence_span": value_getter("population_gender_evidence_span"),
        "population_severity": value_getter("population_severity"),
        "population_severity_evidence_span": value_getter("population_severity_evidence_span"),
        "population_ethnicity": value_getter("population_ethnicity"),
        "population_ethnicity_evidence_span": value_getter("population_ethnicity_evidence_span"),
        "population_occupation": value_getter("population_occupation"),
        "population_occupation_evidence_span": value_getter("population_occupation_evidence_span"),
        "population_social_status": value_getter("population_social_status"),
        "population_social_status_evidence_span": value_getter("population_social_status_evidence_span"),
        "population_previous_treatment": value_getter("population_previous_treatment"),
        "population_previous_treatment_evidence_span": value_getter("population_previous_treatment_evidence_span"),
    }

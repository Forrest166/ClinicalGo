from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Tuple

try:
    import pandas as pd
except Exception:  # pragma: no cover - optional helper only
    pd = None

DEFAULT_MAX_AGE = 100.0
DEFAULT_MIN_AGE = 0.0
DEFAULT_RELATIVE_SPREAD = 0.25
DEFAULT_MAPPING_PATH = Path(__file__).resolve().parents[2] / "rules" / "age_band_mapping.csv"


@dataclass
class AgeNormalizationResult:
    age_detected_type: str = ""
    age_norm_method: str = ""
    age_norm_stage: str = ""
    age_norm_confidence: str = ""
    age_distribution_type: str = ""
    age_norm_lower_years: float | None = None
    age_norm_upper_years: float | None = None
    age_norm_center_years: float | None = None
    age_norm_scale_years: float | None = None
    age_source_kind: str = ""
    age_stage_major: str = ""
    age_stage_detail: str = ""
    age_original_unit: str = ""
    age_lower_open: int = 0
    age_upper_open: int = 0
    age_requires_manual_review: int = 0
    age_reported_lower_years: float | None = None
    age_reported_upper_years: float | None = None
    age_reported_center_years: float | None = None
    age_reported_scale_years: float | None = None
    age_inferred_lower_years: float | None = None
    age_inferred_upper_years: float | None = None
    age_inferred_center_years: float | None = None
    age_inferred_scale_years: float | None = None

    def to_row(self) -> Dict[str, object]:
        row = asdict(self)
        for key, value in list(row.items()):
            if value is None:
                row[key] = ""
        return row


def normalize_text(value: str) -> str:
    txt = str(value).strip()
    replacements = {"\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2265": ">=", "\u2264": "<=", "\u00a0": " ", "\u00b1": " +/- "}
    for src, dst in replacements.items():
        txt = txt.replace(src, dst)
    return re.sub(r"\s+", " ", txt).strip()


def _round_age(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 1)


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    txt = str(value).strip()
    if not txt:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def _default_scale(center: float) -> float:
    return max(1.0, float(center) * DEFAULT_RELATIVE_SPREAD)


def _unit_factor_to_years(low: str) -> float:
    unit_hits = {
        "year": bool(re.search(r"\b(?:years?|yrs?|y/o)\b", low)),
        "month": bool(re.search(r"\b(?:months?|mos?|mo)\b", low)),
        "week": bool(re.search(r"\b(?:weeks?|wks?|wk)\b", low)),
        "day": bool(re.search(r"\b(?:days?)\b", low)),
    }
    matched = [name for name, present in unit_hits.items() if present]
    if len(matched) != 1:
        return 1.0
    return {
        "year": 1.0,
        "month": 1.0 / 12.0,
        "week": 1.0 / 52.0,
        "day": 1.0 / 365.0,
    }[matched[0]]


def _detect_unit_label(low: str) -> str:
    if re.search(r"\b(?:months?|mos?|mo)\b", low):
        return "months"
    if re.search(r"\b(?:weeks?|wks?|wk)\b", low):
        return "weeks"
    if re.search(r"\b(?:days?)\b", low):
        return "days"
    if re.search(r"\b(?:years?|yrs?|y/o)\b", low):
        return "years"
    return ""


def _stage_parts(stage: str) -> Tuple[str, str]:
    cleaned = str(stage or "").strip()
    if not cleaned:
        return "", ""
    if "-" in cleaned:
        major, detail = cleaned.split("-", 1)
        return major, detail
    return cleaned, ""


def _make_result(
    detected_type: str,
    method: str,
    stage: str,
    confidence: str,
    distribution_type: str,
    lower: float | None,
    upper: float | None,
    center: float | None,
    scale: float | None,
) -> AgeNormalizationResult:
    return AgeNormalizationResult(
        age_detected_type=detected_type,
        age_norm_method=method,
        age_norm_stage=stage,
        age_norm_confidence=confidence,
        age_distribution_type=distribution_type,
        age_norm_lower_years=_round_age(lower),
        age_norm_upper_years=_round_age(upper),
        age_norm_center_years=_round_age(center),
        age_norm_scale_years=_round_age(scale),
    )


def _coerce_bounds(a: float, b: float) -> tuple[float, float]:
    lower = min(a, b)
    upper = max(a, b)
    return max(DEFAULT_MIN_AGE, lower), max(DEFAULT_MIN_AGE, upper)


def _distribution_from_mapping_family(dist_family: str, lower: float | None, upper: float | None) -> str:
    family = (dist_family or "").strip().lower()
    if family in {"normal", "truncnorm", "fixed", "mixture"}:
        return family
    if lower is not None and upper is not None:
        return "uniform"
    return ""


def _source_kind_from_result(result: AgeNormalizationResult) -> str:
    if not result.age_detected_type and not result.age_norm_method:
        return "missing"
    if result.age_detected_type in {"numeric_range", "mean_sd", "mean", "median", "single_value"}:
        return "reported_numeric"
    if result.age_detected_type in {"lower_bound", "upper_bound"}:
        return "reported_open_bound"
    if result.age_detected_type == "age_term_manual_review":
        return "manual_review"
    if result.age_detected_type == "unknown":
        return "unmapped"
    if result.age_detected_type == "age_term":
        major, _detail = _stage_parts(result.age_norm_stage)
        method = result.age_norm_method.lower()
        if major == "Mixed" or "mixture" in method:
            return "mixed_term"
        if major in {"Contextual", "Noise"} or "contextual" in method or "education_proxy" in method:
            return "contextual_proxy"
        return "mapped_stage"
    return "unmapped"


def _finalize_result(result: AgeNormalizationResult, raw_text: str) -> AgeNormalizationResult:
    low = normalize_text(raw_text).lower()
    unit = _detect_unit_label(low)
    stage_major, stage_detail = _stage_parts(result.age_norm_stage)
    source_kind = _source_kind_from_result(result)

    result.age_source_kind = source_kind
    result.age_stage_major = stage_major
    result.age_stage_detail = stage_detail
    result.age_original_unit = unit
    result.age_lower_open = int(result.age_detected_type == "lower_bound")
    result.age_upper_open = int(result.age_detected_type == "upper_bound")
    result.age_requires_manual_review = int(source_kind in {"manual_review", "unmapped"})

    result.age_inferred_lower_years = result.age_norm_lower_years
    result.age_inferred_upper_years = result.age_norm_upper_years
    result.age_inferred_center_years = result.age_norm_center_years
    result.age_inferred_scale_years = result.age_norm_scale_years

    if result.age_detected_type == "numeric_range":
        result.age_reported_lower_years = result.age_norm_lower_years
        result.age_reported_upper_years = result.age_norm_upper_years
    elif result.age_detected_type == "single_value":
        result.age_reported_center_years = result.age_norm_center_years
        result.age_reported_lower_years = result.age_norm_center_years
        result.age_reported_upper_years = result.age_norm_center_years
        result.age_reported_scale_years = 0.0
    elif result.age_detected_type == "mean_sd":
        result.age_reported_center_years = result.age_norm_center_years
        result.age_reported_scale_years = result.age_norm_scale_years
    elif result.age_detected_type in {"mean", "median"}:
        result.age_reported_center_years = result.age_norm_center_years
        if "reported_" in result.age_norm_method and "_sd_" in result.age_norm_method:
            result.age_reported_scale_years = result.age_norm_scale_years
        if "_with_range_" in result.age_norm_method:
            result.age_reported_lower_years = result.age_norm_lower_years
            result.age_reported_upper_years = result.age_norm_upper_years
    elif result.age_detected_type == "lower_bound":
        result.age_reported_lower_years = result.age_norm_lower_years
    elif result.age_detected_type == "upper_bound":
        result.age_reported_upper_years = result.age_norm_upper_years

    return result


@lru_cache(maxsize=4)
def load_age_term_mapping(mapping_path: str | Path | None = None) -> Dict[str, Dict[str, object]]:
    path = Path(mapping_path) if mapping_path else DEFAULT_MAPPING_PATH
    mapping: Dict[str, Dict[str, object]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            term_key = normalize_text(row["term_key"]).lower()
            mapping[term_key] = {
                "rule_type": row.get("rule_type", ""),
                "stage_major": row.get("stage_major", ""),
                "stage_detail": row.get("stage_detail", ""),
                "normalized_stage": row.get("normalized_stage", ""),
                "age_min_years": _to_float(row.get("age_min_years")),
                "age_max_years": _to_float(row.get("age_max_years")),
                "dist_family": row.get("dist_family", ""),
                "dist_mean_years": _to_float(row.get("dist_mean_years")),
                "dist_sd_years": _to_float(row.get("dist_sd_years")),
                "confidence": row.get("confidence", ""),
                "normalization_action": row.get("normalization_action", ""),
            }
    return mapping


def _normalize_range(low: str) -> AgeNormalizationResult | None:
    match = re.search(r"(?<![a-z])(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)(?![a-z])", low)
    if not match:
        return None
    factor = _unit_factor_to_years(low)
    lower, upper = _coerce_bounds(float(match.group(1)) * factor, float(match.group(2)) * factor)
    return _make_result(
        detected_type="numeric_range",
        method="range_to_uniform_interval" if factor == 1.0 else "range_to_uniform_interval_unit_scaled_to_years",
        stage="",
        confidence="high",
        distribution_type="uniform",
        lower=lower,
        upper=upper,
        center=(lower + upper) / 2.0,
        scale=(upper - lower) / (12.0 ** 0.5),
    )


def _normalize_plus_minus(low: str) -> AgeNormalizationResult | None:
    match = re.search(r"(?:\bmean\b|\bage\b)?[^\d]{0,12}(\d+(?:\.\d+)?)\s*(?:\+/-|±)\s*(\d+(?:\.\d+)?)", low)
    if not match:
        return None
    factor = _unit_factor_to_years(low)
    center = float(match.group(1)) * factor
    scale = float(match.group(2)) * factor
    return _make_result(
        detected_type="mean_sd",
        method="reported_mean_sd_to_normal_interval" if factor == 1.0 else "reported_mean_sd_to_normal_interval_unit_scaled_to_years",
        stage="",
        confidence="high",
        distribution_type="normal",
        lower=max(DEFAULT_MIN_AGE, center - scale),
        upper=center + scale,
        center=center,
        scale=scale,
    )


def _normalize_mean_sd_text(low: str) -> AgeNormalizationResult | None:
    match = re.search(r"\bmean\b[^\d]{0,12}(\d+(?:\.\d+)?).*?\bsd\b[^\d]{0,12}(\d+(?:\.\d+)?)", low)
    if not match:
        return None
    factor = _unit_factor_to_years(low)
    center = float(match.group(1)) * factor
    scale = float(match.group(2)) * factor
    return _make_result(
        detected_type="mean_sd",
        method="reported_mean_sd_to_normal_interval" if factor == 1.0 else "reported_mean_sd_to_normal_interval_unit_scaled_to_years",
        stage="",
        confidence="high",
        distribution_type="normal",
        lower=max(DEFAULT_MIN_AGE, center - scale),
        upper=center + scale,
        center=center,
        scale=scale,
    )


def _normalize_median(low: str) -> AgeNormalizationResult | None:
    match = re.search(r"\bmedian\b[^\d]{0,12}(\d+(?:\.\d+)?)", low)
    if not match:
        return None
    factor = _unit_factor_to_years(low)
    center = float(match.group(1)) * factor
    range_match = re.search(r"(?<![a-z])(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)(?![a-z])", low)
    sd_match = re.search(r"\bsd\b[^\d]{0,12}(\d+(?:\.\d+)?)", low)
    scale = (float(sd_match.group(1)) * factor) if sd_match else _default_scale(center)
    lower = max(DEFAULT_MIN_AGE, center - scale)
    upper = center + scale
    method = "median_default_sd_to_normal_interval" if sd_match is None else "reported_median_sd_to_normal_interval"
    confidence = "medium" if sd_match is None else "medium_high"
    if range_match:
        lower, upper = _coerce_bounds(float(range_match.group(1)) * factor, float(range_match.group(2)) * factor)
        method = "median_with_range_to_bounded_normal_interval"
        confidence = "medium_high"
    if factor != 1.0:
        method += "_unit_scaled_to_years"
    return _make_result(
        detected_type="median",
        method=method,
        stage="",
        confidence=confidence,
        distribution_type="normal",
        lower=lower,
        upper=upper,
        center=center,
        scale=scale,
    )


def _normalize_mean(low: str) -> AgeNormalizationResult | None:
    match = re.search(r"\b(?:mean|average|avg)\b[^\d]{0,12}(\d+(?:\.\d+)?)", low)
    if not match:
        return None
    factor = _unit_factor_to_years(low)
    center = float(match.group(1)) * factor
    range_match = re.search(r"(?<![a-z])(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)(?![a-z])", low)
    scale = _default_scale(center)
    lower = max(DEFAULT_MIN_AGE, center - scale)
    upper = center + scale
    method = "mean_default_sd_to_normal_interval"
    confidence = "medium"
    if range_match:
        lower, upper = _coerce_bounds(float(range_match.group(1)) * factor, float(range_match.group(2)) * factor)
        method = "mean_with_range_to_bounded_normal_interval"
        confidence = "medium_high"
    if factor != 1.0:
        method += "_unit_scaled_to_years"
    return _make_result(
        detected_type="mean",
        method=method,
        stage="",
        confidence=confidence,
        distribution_type="normal",
        lower=lower,
        upper=upper,
        center=center,
        scale=scale,
    )


def _normalize_lower_bound(low: str) -> AgeNormalizationResult | None:
    plus_match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*\+", low)
    if plus_match:
        factor = _unit_factor_to_years(low)
        lower = float(plus_match.group(1)) * factor
        return _make_result(
            detected_type="lower_bound",
            method="open_lower_bound_to_uniform_interval" if factor == 1.0 else "open_lower_bound_to_uniform_interval_unit_scaled_to_years",
            stage="",
            confidence="low",
            distribution_type="uniform",
            lower=lower,
            upper=DEFAULT_MAX_AGE,
            center=(lower + DEFAULT_MAX_AGE) / 2.0,
            scale=(DEFAULT_MAX_AGE - lower) / (12.0 ** 0.5),
        )

    match = re.search(
        r"(?:>=|>\s*=?|at least|older than|or older|and older|years? or older|over)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:(?:years?|yrs?|months?|mos?|mo|weeks?|wks?|wk|days?)\s*)?(?:or older|and older|and above|years and over|years or more|and over|or above)",
        low,
    )
    if not match:
        return None
    lower_txt = match.group(1) or match.group(2)
    factor = _unit_factor_to_years(low)
    lower = float(lower_txt) * factor
    return _make_result(
        detected_type="lower_bound",
        method="open_lower_bound_to_uniform_interval" if factor == 1.0 else "open_lower_bound_to_uniform_interval_unit_scaled_to_years",
        stage="",
        confidence="low",
        distribution_type="uniform",
        lower=lower,
        upper=DEFAULT_MAX_AGE,
        center=(lower + DEFAULT_MAX_AGE) / 2.0,
        scale=(DEFAULT_MAX_AGE - lower) / (12.0 ** 0.5),
    )


def _normalize_upper_bound(low: str) -> AgeNormalizationResult | None:
    match = re.search(
        r"(?:<=|<\s*=?|at most|younger than|or younger|and younger|under)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:(?:years?|yrs?|months?|mos?|mo|weeks?|wks?|wk|days?)\s*)?(?:or younger|and younger|or less|or below|and below)",
        low,
    )
    if not match:
        return None
    upper_txt = match.group(1) or match.group(2)
    factor = _unit_factor_to_years(low)
    upper = float(upper_txt) * factor
    return _make_result(
        detected_type="upper_bound",
        method="open_upper_bound_to_uniform_interval" if factor == 1.0 else "open_upper_bound_to_uniform_interval_unit_scaled_to_years",
        stage="",
        confidence="low",
        distribution_type="uniform",
        lower=DEFAULT_MIN_AGE,
        upper=upper,
        center=upper / 2.0,
        scale=upper / (12.0 ** 0.5),
    )


def _normalize_single_value(low: str) -> AgeNormalizationResult | None:
    match = re.fullmatch(r"(?:age\s*)?(\d+(?:\.\d+)?)\s*(?:years?|yrs?|y/o|months?|mos?|mo|weeks?|wks?|wk|days?)?", low)
    if not match:
        return None
    factor = _unit_factor_to_years(low)
    center = float(match.group(1)) * factor
    return _make_result(
        detected_type="single_value",
        method="single_value_to_point_interval" if factor == 1.0 else "single_value_to_point_interval_unit_scaled_to_years",
        stage="",
        confidence="high",
        distribution_type="fixed",
        lower=center,
        upper=center,
        center=center,
        scale=0.0,
    )


def _normalize_age_term(low: str, mapping_path: str | Path | None = None) -> AgeNormalizationResult | None:
    mapping = load_age_term_mapping(mapping_path)
    item = mapping.get(low)
    if item is None:
        return None

    lower = item["age_min_years"]
    upper = item["age_max_years"]
    center = item["dist_mean_years"]
    if center is None and lower is not None and upper is not None:
        center = (lower + upper) / 2.0
    scale = item["dist_sd_years"]
    if scale is None and lower is not None and upper is not None:
        scale = (upper - lower) / (12.0 ** 0.5)

    distribution_type = _distribution_from_mapping_family(str(item["dist_family"]), lower, upper)
    detected_type = "age_term_manual_review" if item["normalization_action"] == "manual_review" else "age_term"
    method = f"mapping_library:{item['rule_type'] or 'term'}"

    return _make_result(
        detected_type=detected_type,
        method=method,
        stage=str(item["normalized_stage"] or ""),
        confidence=str(item["confidence"] or ""),
        distribution_type=distribution_type,
        lower=lower,
        upper=upper,
        center=center,
        scale=scale,
    )


def normalize_age_expression(value: str, mapping_path: str | Path | None = None) -> AgeNormalizationResult:
    txt = normalize_text(value)
    low = txt.lower()
    if not low:
        return _finalize_result(AgeNormalizationResult(), txt)

    for normalizer in (
        _normalize_plus_minus,
        _normalize_mean_sd_text,
        _normalize_median,
        _normalize_mean,
        _normalize_range,
        _normalize_lower_bound,
        _normalize_upper_bound,
        _normalize_single_value,
    ):
        result = normalizer(low)
        if result is not None:
            return _finalize_result(result, txt)

    mapped = _normalize_age_term(low, mapping_path)
    if mapped is not None:
        return _finalize_result(mapped, txt)

    return _finalize_result(_make_result(
        detected_type="unknown",
        method="unmapped",
        stage="",
        confidence="very_low",
        distribution_type="",
        lower=None,
        upper=None,
        center=None,
        scale=None,
    ), txt)


def normalize_age_values_dataframe(
    df: pd.DataFrame,
    value_column: str = "value",
    mapping_path: str | Path | None = None,
) -> pd.DataFrame:
    if pd is None:
        raise ImportError("pandas is required for normalize_age_values_dataframe")
    rows = [normalize_age_expression(value, mapping_path).to_row() for value in df[value_column].fillna("").astype(str)]
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)

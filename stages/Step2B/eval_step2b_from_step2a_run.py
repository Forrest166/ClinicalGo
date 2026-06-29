from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.api_keys import load_api_key_bundle
from llm_client import Step2BExtractionClient
from models import Step2BInputRow
from pipeline import (
    AGE_SIGNAL_PATTERN,
    ETHNICITY_PATTERNS,
    GENDER_SIGNAL_PATTERN,
    OCCUPATION_SIGNAL_PATTERN,
    SOCIAL_STATUS_SIGNAL_PATTERN,
    _build_population_focus,
    _build_rule_based_output,
    _clean_text,
    _count_populated_fields,
    _has_population_signal,
    _needs_llm_refinement,
    _normalize_output,
)
from prompt_templates import DEFAULT_PROMPT_TEMPLATE
from common.step2_support.parsing import iter_pubmed_records_from_file, parse_record_structured


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Step2B against a saved Step2A live-sample run.")
    parser.add_argument("--step2a-run", required=True)
    parser.add_argument("--source-txt", required=True)
    parser.add_argument("--out-run", required=True)
    parser.add_argument("--out-audit", required=True)
    parser.add_argument("--provider", default="NVIDIA NIM")
    parser.add_argument("--model", default="qwen/qwen3-next-80b-a3b-instruct")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--base-url", default="")
    return parser.parse_args()


def _load_step2a_results(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("results") or [])


def _load_pmids_for_record_ids(source_txt: Path, wanted: Sequence[int]) -> Dict[int, str]:
    wanted_ids = {int(value) for value in wanted}
    pmids: Dict[int, str] = {}
    for record_id, raw_record in enumerate(iter_pubmed_records_from_file(str(source_txt)), start=1):
        if record_id not in wanted_ids:
            continue
        parsed = parse_record_structured(raw_record, record_id=record_id)
        pmids[record_id] = _clean_text(parsed.pmid)
        if len(pmids) >= len(wanted_ids):
            break
    return pmids


def _has_ethnicity_signal(text: str) -> bool:
    low = _clean_text(text).lower()
    if not low:
        return False
    return any(re.search(pattern, low, flags=re.I) for pattern, _ in ETHNICITY_PATTERNS)


def _has_treatment_status_signal(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:previously untreated|currently untreated|untreated|unmedicated|medication[- ]free|drug[- ]free|"
            r"treatment[- ]naive|antidepressant[- ]naive|no prior antidepressant treatment|"
            r"none currently receiving treatment|not currently receiving treatment)\b",
            _clean_text(text),
            flags=re.I,
        )
    )


def _has_age_signal_for_audit(text: str) -> bool:
    low = _clean_text(text).lower()
    if not low:
        return False
    if re.search(r"\b(?:mothers?|parents?|caregivers?)\s+of\b.{0,40}\b(?:children|child|adolescents?|infants?)\b", low):
        return False
    if re.search(r"\bgeriatric\b", low) and re.search(r"\b(?:depression|depressive|scores?)\b", low):
        return False
    return bool(
        re.search(
            r"\b(?:age(?:d|s)?\s+(?:between\s+)?\d+(?:\.\d+)?|aged?\s*(?:>=|=>|<=|=<|>|<)\s*\d+(?:\.\d+)?|"
            r"aged?\s+\d+(?:\.\d+)?\+|age\s*(?:>=|=>|<=|=<|>|<)\s*\d+(?:\.\d+)?|"
            r"aged?\s+\d+(?:\.\d+)?\s+(?:or|and)\s+(?:older|over|above|more)|"
            r"at least\s+\d+(?:\.\d+)?\s*years?\s+old|\d+(?:\.\d+)?\s*years?\s+(?:or|and)\s+(?:older|over|above|more)|"
            r"\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*years?|\d+(?:\.\d+)?\s*-\s*to\s*\d+(?:\.\d+)?-year-olds?|"
            r"mean age|median age|older adults?|young adults?|adolescents?|children|schoolchildren|elderly|geriatric|late-life)\b",
            low,
            flags=re.I,
        )
    )


def _age_output_looks_suspicious(output: str, source_text: str) -> bool:
    age = _clean_text(output)
    low = _clean_text(source_text).lower()
    if not age:
        return False
    if age in {"Students", "College students", "Schoolchildren"}:
        return True
    has_explicit_age_context = bool(re.search(r"\b(?:aged?|age|years?\s+of\s+age|years?\s+old)\b", low, flags=re.I))
    if re.search(r"\b(?:weeks?|months?)\s+postpartum\b", low, flags=re.I) and not has_explicit_age_context and re.fullmatch(
        r"\d+(?:\.\d+)?-\d+(?:\.\d+)?",
        age,
    ):
        return True
    if re.search(r"\bgestation(?:al)?\b|\bpostmenstrual\b", low, flags=re.I) and not has_explicit_age_context and re.fullmatch(
        r"\d+(?:\.\d+)?-\d+(?:\.\d+)?",
        age,
    ):
        return True
    return False


def _ethnicity_output_looks_suspicious(output: str, source_text: str) -> bool:
    ethnicity = _clean_text(output).lower()
    source_low = _clean_text(source_text).lower()
    if not ethnicity:
        return False
    if "hispanic/latino" in ethnicity and re.search(r"\bnon[- ]hispanic\b", source_low, flags=re.I) and not re.search(
        r"(?<!non[- ])\bhispanic\b|(?<!non[- ])\blatino\b|(?<!non[- ])\blatina\b",
        source_low,
        flags=re.I,
    ):
        return True
    if ethnicity == "other" and not re.search(r"\bother\s+(?:race|ethnicity|racial|ethnic)\b", source_low, flags=re.I):
        return True
    return False


def _occupation_output_looks_suspicious(output: str, source_text: str) -> bool:
    occupation = _clean_text(output)
    low = _clean_text(source_text).lower()
    if not occupation:
        return False
    return bool(
        re.search(r"\bwithout a doctor\b|\bphysician services?\b|\bdoctor visits?\b|\bprovided by\b|\bdelivered by\b", low)
    )


def _social_output_looks_suspicious(output: str, source_text: str) -> bool:
    social = _clean_text(output)
    low = _clean_text(source_text).lower()
    if not social:
        return False
    if social == "Rural" and "rural" not in low:
        return True
    return False


def _build_inputs(step2a_results: Sequence[Dict[str, Any]], pmids: Dict[int, str]) -> List[Step2BInputRow]:
    rows: List[Step2BInputRow] = []
    for item in step2a_results:
        source_index = int(item.get("source_index", 0) or 0)
        population_raw = _clean_text(item.get("normalized_population_raw") or item.get("model_population_raw") or "")
        rows.append(
            Step2BInputRow(
                record_id=str(source_index),
                pmid=pmids.get(source_index, ""),
                population_raw=population_raw,
                treatment_history=_clean_text(item.get("treatment_history") or ""),
                population_focus=_build_population_focus(population_raw),
            )
        )
    return rows


def _run_llm_rows(
    client: Step2BExtractionClient,
    llm_rows: Sequence[Step2BInputRow],
    batch_size: int,
    outputs: Dict[str, Dict[str, Any]],
    usage_totals: Dict[str, int],
) -> None:
    for start in range(0, len(llm_rows), max(1, int(batch_size))):
        batch = list(llm_rows[start : start + max(1, int(batch_size))])
        items = [
            {
                "row_id": idx + 1,
                "record_id": row.record_id,
                "pmid": row.pmid,
                "population_raw": row.population_raw,
                "population_focus": row.population_focus,
            }
            for idx, row in enumerate(batch)
        ]
        response = client.run_batch(items)
        usage_totals["prompt_tokens"] += int(response.usage.prompt_tokens or 0)
        usage_totals["completion_tokens"] += int(response.usage.completion_tokens or 0)
        usage_totals["total_tokens"] += int(response.usage.total_tokens or 0)
        response_map = {str(item["row_id"]): batch[idx] for idx, item in enumerate(items)}
        for raw_row in response.rows:
            if not isinstance(raw_row, dict):
                continue
            source_row = response_map.get(str(raw_row.get("row_id", "")))
            if not source_row:
                continue
            normalized = _normalize_output(raw_row, source_row)
            payload = outputs[source_row.record_id]
            payload["age"] = normalized.age
            payload["gender"] = normalized.gender
            payload["ethnicity"] = normalized.ethnicity
            payload["occupation"] = normalized.occupation
            payload["social_status"] = normalized.social_status
            payload["treatment_history"] = normalized.treatment_history
            payload["used_llm"] = True


def _audit(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    input_non_empty_population_raw = 0
    llm_row_count = 0
    rows_with_any_field = 0
    rows_all_empty = 0
    rows_with_2plus = 0
    rows_with_3plus = 0
    field_non_empty = {
        "age": 0,
        "gender": 0,
        "ethnicity": 0,
        "occupation": 0,
        "social_status": 0,
        "treatment_history": 0,
    }
    signal_rows = {
        "age": 0,
        "gender": 0,
        "ethnicity": 0,
        "occupation": 0,
        "social_status": 0,
        "treatment": 0,
    }
    signal_hits = {key: 0 for key in signal_rows.keys()}
    suspicious_counts = {
        "age": 0,
        "ethnicity": 0,
        "occupation": 0,
        "social_status": 0,
    }
    age_missed_examples: List[List[str]] = []
    social_missed_examples: List[List[str]] = []
    treatment_missed_examples: List[List[str]] = []
    suspicious_examples = {
        "age": [],
        "ethnicity": [],
        "occupation": [],
        "social_status": [],
    }

    for row in rows:
        population_raw = _clean_text(row.get("population_raw", ""))
        if not population_raw:
            continue
        input_non_empty_population_raw += 1
        if row.get("used_llm"):
            llm_row_count += 1
        populated = 0
        for field in field_non_empty.keys():
            if _clean_text(row.get(field, "")):
                field_non_empty[field] += 1
                populated += 1
        if populated:
            rows_with_any_field += 1
        else:
            rows_all_empty += 1
        if populated >= 2:
            rows_with_2plus += 1
        if populated >= 3:
            rows_with_3plus += 1

        if _has_age_signal_for_audit(population_raw):
            signal_rows["age"] += 1
            if _clean_text(row.get("age", "")):
                signal_hits["age"] += 1
            elif len(age_missed_examples) < 20:
                age_missed_examples.append([row["record_id"], population_raw])
        if re.search(GENDER_SIGNAL_PATTERN, population_raw, flags=re.I):
            signal_rows["gender"] += 1
            if _clean_text(row.get("gender", "")):
                signal_hits["gender"] += 1
        if _has_ethnicity_signal(population_raw):
            signal_rows["ethnicity"] += 1
            if _clean_text(row.get("ethnicity", "")):
                signal_hits["ethnicity"] += 1
        if re.search(OCCUPATION_SIGNAL_PATTERN, population_raw, flags=re.I):
            signal_rows["occupation"] += 1
            if _clean_text(row.get("occupation", "")):
                signal_hits["occupation"] += 1
        if re.search(SOCIAL_STATUS_SIGNAL_PATTERN, population_raw, flags=re.I):
            signal_rows["social_status"] += 1
            if _clean_text(row.get("social_status", "")):
                signal_hits["social_status"] += 1
            elif len(social_missed_examples) < 20:
                social_missed_examples.append([row["record_id"], population_raw])
        if _has_treatment_status_signal(population_raw):
            signal_rows["treatment"] += 1
            if _clean_text(row.get("treatment_history", "")):
                signal_hits["treatment"] += 1
            elif len(treatment_missed_examples) < 20:
                treatment_missed_examples.append([row["record_id"], population_raw])

        if _age_output_looks_suspicious(row.get("age", ""), population_raw):
            suspicious_counts["age"] += 1
            if len(suspicious_examples["age"]) < 20:
                suspicious_examples["age"].append([row["record_id"], population_raw, _clean_text(row.get("age", ""))])
        if _ethnicity_output_looks_suspicious(row.get("ethnicity", ""), population_raw):
            suspicious_counts["ethnicity"] += 1
            if len(suspicious_examples["ethnicity"]) < 20:
                suspicious_examples["ethnicity"].append(
                    [row["record_id"], population_raw, _clean_text(row.get("ethnicity", ""))]
                )
        if _occupation_output_looks_suspicious(row.get("occupation", ""), population_raw):
            suspicious_counts["occupation"] += 1
            if len(suspicious_examples["occupation"]) < 20:
                suspicious_examples["occupation"].append(
                    [row["record_id"], population_raw, _clean_text(row.get("occupation", ""))]
                )
        if _social_output_looks_suspicious(row.get("social_status", ""), population_raw):
            suspicious_counts["social_status"] += 1
            if len(suspicious_examples["social_status"]) < 20:
                suspicious_examples["social_status"].append(
                    [row["record_id"], population_raw, _clean_text(row.get("social_status", ""))]
                )

    signal_recall = {
        key: (round(signal_hits[key] / signal_rows[key], 4) if signal_rows[key] else None) for key in signal_rows.keys()
    }
    return {
        "metrics": {
            "input_non_empty_population_raw": input_non_empty_population_raw,
            "llm_row_count": llm_row_count,
            "field_non_empty_age": field_non_empty["age"],
            "field_non_empty_gender": field_non_empty["gender"],
            "field_non_empty_ethnicity": field_non_empty["ethnicity"],
            "field_non_empty_occupation": field_non_empty["occupation"],
            "field_non_empty_social_status": field_non_empty["social_status"],
            "field_non_empty_treatment_history": field_non_empty["treatment_history"],
            "rows_with_any_field_from_nonempty_raw": rows_with_any_field,
            "rows_all_empty_from_nonempty_raw": rows_all_empty,
            "rows_with_2plus_fields": rows_with_2plus,
            "rows_with_3plus_fields": rows_with_3plus,
            "age_signal_rows": signal_rows["age"],
            "age_signal_recall_proxy": signal_recall["age"],
            "gender_signal_rows": signal_rows["gender"],
            "gender_signal_recall_proxy": signal_recall["gender"],
            "ethnicity_signal_rows": signal_rows["ethnicity"],
            "ethnicity_signal_recall_proxy": signal_recall["ethnicity"],
            "occupation_signal_rows": signal_rows["occupation"],
            "occupation_signal_recall_proxy": signal_recall["occupation"],
            "social_signal_rows": signal_rows["social_status"],
            "social_signal_recall_proxy": signal_recall["social_status"],
            "treatment_signal_rows": signal_rows["treatment"],
            "treatment_signal_recall_proxy": signal_recall["treatment"],
            "suspicious_age_count": suspicious_counts["age"],
            "suspicious_ethnicity_count": suspicious_counts["ethnicity"],
            "suspicious_occupation_count": suspicious_counts["occupation"],
            "suspicious_social_status_count": suspicious_counts["social_status"],
        },
        "age_missed_examples": age_missed_examples,
        "social_missed_examples": social_missed_examples,
        "treatment_missed_examples": treatment_missed_examples,
        "suspicious_age_examples": suspicious_examples["age"],
        "suspicious_ethnicity_examples": suspicious_examples["ethnicity"],
        "suspicious_occupation_examples": suspicious_examples["occupation"],
        "suspicious_social_status_examples": suspicious_examples["social_status"],
    }


def main() -> None:
    args = _parse_args()
    step2a_run_path = Path(args.step2a_run)
    source_txt_path = Path(args.source_txt)
    out_run_path = Path(args.out_run)
    out_audit_path = Path(args.out_audit)
    provider_keys, base_urls, _ = load_api_key_bundle([PROJECT_ROOT])
    api_key = provider_keys.get(args.provider, "")
    if not api_key:
        raise SystemExit(f"Missing API key for provider: {args.provider}")
    base_url = args.base_url or base_urls.get("nvidia_nim_base_url", "")

    started = time.time()
    step2a_results = _load_step2a_results(step2a_run_path)
    source_ids = [int(item.get("source_index", 0) or 0) for item in step2a_results if int(item.get("source_index", 0) or 0) > 0]
    pmids = _load_pmids_for_record_ids(source_txt_path, source_ids)
    inputs = _build_inputs(step2a_results, pmids)

    client = Step2BExtractionClient(
        provider=args.provider,
        model=args.model,
        api_key=api_key,
        base_url=base_url,
        prompt_template=DEFAULT_PROMPT_TEMPLATE,
        timeout_seconds=int(args.timeout_seconds),
        retries=int(args.retries),
        should_stop=None,
        user_agent="Step2B-SampleEval/1.0 (+desktop)",
    )

    outputs: Dict[str, Dict[str, Any]] = {}
    llm_rows: List[Step2BInputRow] = []
    for source_row in inputs:
        rule_output = _build_rule_based_output(source_row)
        outputs[source_row.record_id] = {
            "record_id": source_row.record_id,
            "pmid": source_row.pmid,
            "population_raw": source_row.population_raw,
            "population_focus": source_row.population_focus,
            "age": rule_output.age,
            "gender": rule_output.gender,
            "ethnicity": rule_output.ethnicity,
            "occupation": rule_output.occupation,
            "social_status": rule_output.social_status,
            "treatment_history": rule_output.treatment_history,
            "rule_age": rule_output.age,
            "rule_gender": rule_output.gender,
            "rule_ethnicity": rule_output.ethnicity,
            "rule_occupation": rule_output.occupation,
            "rule_social_status": rule_output.social_status,
            "rule_treatment_history": rule_output.treatment_history,
            "rule_field_count": _count_populated_fields(rule_output),
            "has_population_signal": _has_population_signal(source_row.population_raw),
            "used_llm": False,
        }
        if _needs_llm_refinement(source_row, rule_output):
            llm_rows.append(source_row)

    usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    if llm_rows:
        _run_llm_rows(client, llm_rows, int(args.batch_size), outputs, usage_totals)

    run_rows = [outputs[row.record_id] for row in inputs]
    run_payload = {
        "provider": args.provider,
        "model": args.model,
        "source_step2a_run": str(step2a_run_path.resolve()),
        "run_record_count": len(run_rows),
        "llm_row_count": len(llm_rows),
        "usage": usage_totals,
        "elapsed_seconds": round(time.time() - started, 3),
        "rows": run_rows,
    }
    audit_payload = {
        "provider": args.provider,
        "model": args.model,
        "source_step2a_run": str(step2a_run_path.resolve()),
        **_audit(run_rows),
    }

    out_run_path.write_text(json.dumps(run_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_audit_path.write_text(json.dumps(audit_payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

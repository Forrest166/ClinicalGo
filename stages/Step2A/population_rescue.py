from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from local_rules import (
    clean_common_noise,
    has_population_cue,
    has_severity_cue,
    normalize_population_raw_trace,
    normalize_severity_trace,
    normalize_source_index_value,
)
from models import Step2ARow
from population_rescue_client import Step2APopulationRescueClient
from common.step2_support.scheduler import recover_missing_rows, run_batch_adaptive


_POPULATION_RESCUE_SECTIONS = (
    "PATIENTS",
    "PARTICIPANTS",
    "METHODS",
    "DESIGN",
    "SETTING",
    "BACKGROUND",
    "OBJECTIVE",
    "OBJECTIVES",
    "SUMMARY",
    "RESULTS",
)


@dataclass
class PopulationRescueSummary:
    records_examined: int = 0
    rows_examined: int = 0
    broadcast_rows: int = 0
    local_population_rows: int = 0
    local_severity_rows: int = 0
    llm_population_rows: int = 0
    llm_severity_rows: int = 0
    llm_records_queued: int = 0
    llm_records_applied: int = 0
    unresolved_records: int = 0
    no_cue_records: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "records_examined": int(self.records_examined),
            "rows_examined": int(self.rows_examined),
            "broadcast_rows": int(self.broadcast_rows),
            "local_population_rows": int(self.local_population_rows),
            "local_severity_rows": int(self.local_severity_rows),
            "llm_population_rows": int(self.llm_population_rows),
            "llm_severity_rows": int(self.llm_severity_rows),
            "llm_records_queued": int(self.llm_records_queued),
            "llm_records_applied": int(self.llm_records_applied),
            "unresolved_records": int(self.unresolved_records),
            "no_cue_records": int(self.no_cue_records),
            "prompt_tokens": int(self.prompt_tokens),
            "completion_tokens": int(self.completion_tokens),
            "total_tokens": int(self.total_tokens),
        }


@dataclass
class PopulationRescuePlan:
    records_examined: int = 0
    rows_examined: int = 0
    candidate_record_ids: List[int] = field(default_factory=list)
    population_candidate_count: int = 0
    severity_candidate_count: int = 0
    no_cue_record_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "records_examined": int(self.records_examined),
            "rows_examined": int(self.rows_examined),
            "candidate_record_ids": [int(value) for value in self.candidate_record_ids],
            "candidate_record_count": int(len(self.candidate_record_ids)),
            "population_candidate_count": int(self.population_candidate_count),
            "severity_candidate_count": int(self.severity_candidate_count),
            "no_cue_record_count": int(self.no_cue_record_count),
        }


@dataclass
class _RecordRescueContext:
    record_id: int
    source: Any
    rows: List[Step2ARow]
    population_context_text: str
    rescue_prompt_text: str
    has_population_cue: bool
    has_severity_cue: bool
    local_population: str
    local_severity: str


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _build_population_context_text(source: Any) -> str:
    parts = [_clean_text(getattr(getattr(source, "parsed", None), "title", ""))]
    sections = getattr(getattr(source, "parsed", None), "sections", {}) or {}
    for section in _POPULATION_RESCUE_SECTIONS:
        section_text = _clean_text(sections.get(section, ""))
        if not section_text:
            continue
        if section == "RESULTS" and not (has_population_cue(section_text) or has_severity_cue(section_text)):
            continue
        parts.append(section_text)
    return " ".join(part for part in parts if part)


def _build_population_rescue_prompt_text(source: Any) -> str:
    lines: List[str] = []
    title = _clean_text(getattr(getattr(source, "parsed", None), "title", ""))
    if title:
        lines.append(f"TITLE: {title}")
    sections = getattr(getattr(source, "parsed", None), "sections", {}) or {}
    for section in _POPULATION_RESCUE_SECTIONS:
        section_text = _clean_text(sections.get(section, ""))
        if not section_text:
            continue
        if section == "RESULTS" and not (has_population_cue(section_text) or has_severity_cue(section_text)):
            continue
        lines.append(f"{section}: {section_text}")
    return "\n".join(lines).strip()


def _first_non_empty(rows: Sequence[Step2ARow], field_name: str) -> str:
    for row in rows:
        value = clean_common_noise(getattr(row, field_name, ""))
        if value:
            return value
    return ""


def _covered_record_ids(rows: Sequence[Any]) -> List[int]:
    covered: List[int] = []
    seen: set[int] = set()
    for row in rows:
        if isinstance(row, dict):
            source_index = normalize_source_index_value(row.get("source_index", ""))
        else:
            source_index = normalize_source_index_value(getattr(row, "source_index", ""))
        if not source_index.isdigit():
            continue
        record_id = int(source_index)
        if record_id in seen:
            continue
        seen.add(record_id)
        covered.append(record_id)
    return covered


def _merge_llm_value(existing: str, candidate: str) -> str:
    current = clean_common_noise(existing)
    probe = clean_common_noise(candidate)
    if current and not probe:
        return current
    if probe and not current:
        return probe
    if len(probe) > len(current):
        return probe
    return current


class PopulationRescueService:
    def __init__(
        self,
        *,
        client: Optional[Step2APopulationRescueClient] = None,
        progress: Optional[Callable[[str], None]] = None,
        on_state: Optional[Callable[[Dict[str, Any]], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        cancel_exception_cls: type[Exception] = RuntimeError,
        max_batch_records: int = 10,
        max_workers: int = 1,
    ) -> None:
        self.client = client
        self.progress = progress
        self.on_state = on_state
        self.should_stop = should_stop
        self.cancel_exception_cls = cancel_exception_cls
        self.max_batch_records = max(1, int(max_batch_records))
        self.max_workers = max(1, int(max_workers))

    def plan_rows(
        self,
        rows: Sequence[Step2ARow],
        source_by_id: Mapping[int, Any],
    ) -> PopulationRescuePlan:
        contexts = self._collect_contexts(rows, source_by_id)
        plan = PopulationRescuePlan(
            records_examined=len(source_by_id),
            rows_examined=len(rows),
        )
        for context in contexts:
            needs_population = self._needs_population_candidate(context)
            needs_severity = self._needs_severity_candidate(context)
            if needs_population or needs_severity:
                plan.candidate_record_ids.append(int(context.record_id))
            if needs_population:
                plan.population_candidate_count += 1
            if needs_severity:
                plan.severity_candidate_count += 1
            if not context.has_population_cue and not context.has_severity_cue:
                if any(
                    not clean_common_noise(row.population_raw) or not clean_common_noise(row.severity)
                    for row in context.rows
                ):
                    plan.no_cue_record_count += 1
        plan.candidate_record_ids = sorted(set(plan.candidate_record_ids))
        return plan

    def enrich_rows(
        self,
        rows: Sequence[Step2ARow],
        source_by_id: Mapping[int, Any],
    ) -> PopulationRescueSummary:
        summary = PopulationRescueSummary(
            records_examined=len(source_by_id),
            rows_examined=len(rows),
        )
        if not rows or not source_by_id:
            return summary

        row_marks: Dict[int, Dict[str, bool]] = {
            id(row): {"broadcast": False, "local": False, "llm": False} for row in rows
        }
        initial_state: Dict[int, Tuple[bool, bool]] = {
            id(row): (bool(clean_common_noise(row.population_raw)), bool(clean_common_noise(row.severity))) for row in rows
        }

        contexts = self._collect_contexts(rows, source_by_id)
        llm_candidates: List[_RecordRescueContext] = []
        for context in contexts:
            self._broadcast_shared_values(context, row_marks, summary)
            self._apply_local_rescue(context, row_marks, summary)
            if self._needs_llm_rescue(context):
                llm_candidates.append(context)
        local_done = max(0, len(contexts) - len(llm_candidates))
        if self.on_state:
            self.on_state(
                {
                    "processed_records": int(local_done),
                    "total_records": int(len(contexts)),
                    "prompt_tokens": int(summary.prompt_tokens),
                    "completion_tokens": int(summary.completion_tokens),
                    "total_tokens": int(summary.total_tokens),
                }
            )

        llm_payloads = (
            self._run_llm_rescue(
                llm_candidates,
                summary,
                base_processed_records=local_done,
                total_records=len(contexts),
            )
            if llm_candidates
            else {}
        )
        for context in llm_candidates:
            payload = llm_payloads.get(context.record_id, ("", ""))
            self._apply_llm_rescue(context, payload, row_marks, summary)

        for context in contexts:
            if any(clean_common_noise(row.population_raw) for row in context.rows):
                continue
            if any(clean_common_noise(row.severity) for row in context.rows):
                continue
            if context.has_population_cue or context.has_severity_cue:
                summary.unresolved_records += 1
            else:
                summary.no_cue_records += 1

        for context in contexts:
            self._finalize_population_status(context, initial_state, row_marks)

        if self.progress and (
            summary.broadcast_rows
            or summary.local_population_rows
            or summary.local_severity_rows
            or summary.llm_records_queued
        ):
            self.progress(
                "Population rescue summary: "
                f"broadcast rows={summary.broadcast_rows}, "
                f"local population fills={summary.local_population_rows}, "
                f"local severity fills={summary.local_severity_rows}, "
                f"llm queued records={summary.llm_records_queued}, "
                f"llm applied records={summary.llm_records_applied}."
            )
        return summary

    def _collect_contexts(
        self,
        rows: Sequence[Step2ARow],
        source_by_id: Mapping[int, Any],
    ) -> List[_RecordRescueContext]:
        row_groups: Dict[int, List[Step2ARow]] = {}
        for row in rows:
            source_index = normalize_source_index_value(row.source_index)
            if not source_index.isdigit():
                continue
            record_id = int(source_index)
            if record_id in source_by_id:
                row_groups.setdefault(record_id, []).append(row)
        contexts: List[_RecordRescueContext] = []
        for record_id, source in source_by_id.items():
            record_rows = row_groups.get(record_id, [])
            if not record_rows:
                continue
            population_context = _build_population_context_text(source)
            contexts.append(
                _RecordRescueContext(
                    record_id=record_id,
                    source=source,
                    rows=record_rows,
                    population_context_text=population_context,
                    rescue_prompt_text=_build_population_rescue_prompt_text(source),
                    has_population_cue=has_population_cue(population_context),
                    has_severity_cue=has_severity_cue(population_context),
                    local_population=normalize_population_raw_trace("", population_context),
                    local_severity=normalize_severity_trace("", "", population_context),
                )
            )
        return contexts

    @staticmethod
    def _needs_population_candidate(context: _RecordRescueContext) -> bool:
        if not any(not clean_common_noise(row.population_raw) for row in context.rows):
            return False
        if _first_non_empty(context.rows, "population_raw"):
            return True
        if clean_common_noise(context.local_population):
            return True
        return context.has_population_cue

    @staticmethod
    def _needs_severity_candidate(context: _RecordRescueContext) -> bool:
        if not any(not clean_common_noise(row.severity) for row in context.rows):
            return False
        if _first_non_empty(context.rows, "severity"):
            return True
        if clean_common_noise(context.local_severity):
            return True
        return context.has_severity_cue

    def _broadcast_shared_values(
        self,
        context: _RecordRescueContext,
        row_marks: Dict[int, Dict[str, bool]],
        summary: PopulationRescueSummary,
    ) -> None:
        shared_population = _first_non_empty(context.rows, "population_raw")
        shared_severity = _first_non_empty(context.rows, "severity")
        for row in context.rows:
            changed = False
            if shared_population and not clean_common_noise(row.population_raw):
                row.population_raw = shared_population
                changed = True
            if shared_severity and not clean_common_noise(row.severity):
                row.severity = shared_severity
                changed = True
            if changed:
                row_marks[id(row)]["broadcast"] = True
                summary.broadcast_rows += 1

    def _apply_local_rescue(
        self,
        context: _RecordRescueContext,
        row_marks: Dict[int, Dict[str, bool]],
        summary: PopulationRescueSummary,
    ) -> None:
        for row in context.rows:
            if context.local_population and not clean_common_noise(row.population_raw):
                row.population_raw = context.local_population
                row_marks[id(row)]["local"] = True
                summary.local_population_rows += 1
            if context.local_severity and not clean_common_noise(row.severity):
                row.severity = context.local_severity
                row_marks[id(row)]["local"] = True
                summary.local_severity_rows += 1

    def _needs_llm_rescue(self, context: _RecordRescueContext) -> bool:
        if self.client is None or not context.rescue_prompt_text:
            return False
        needs_population = any(not clean_common_noise(row.population_raw) for row in context.rows) and context.has_population_cue
        needs_severity = any(not clean_common_noise(row.severity) for row in context.rows) and context.has_severity_cue
        return needs_population or needs_severity

    def _run_llm_rescue(
        self,
        contexts: Sequence[_RecordRescueContext],
        summary: PopulationRescueSummary,
        *,
        base_processed_records: int = 0,
        total_records: int = 0,
    ) -> Dict[int, Tuple[str, str]]:
        if self.client is None or not contexts:
            return {}
        summary.llm_records_queued += len(contexts)
        if self.progress:
            self.progress(f"Population rescue queued {len(contexts)} source records for dedicated LLM rescue.")
        llm_payloads: Dict[int, Tuple[str, str]] = {}
        chunks = [
            list(contexts[start : start + self.max_batch_records])
            for start in range(0, len(contexts), self.max_batch_records)
        ]
        total_chunks = max(1, len(chunks))
        processed_llm_records = 0
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(chunks))) as executor:
            future_map = {
                executor.submit(self._run_llm_chunk, chunk_index, total_chunks, chunk): (chunk_index, chunk)
                for chunk_index, chunk in enumerate(chunks, start=1)
            }
            pending = dict(future_map)
            while pending:
                if self.should_stop and self.should_stop():
                    for future in list(pending.keys()):
                        future.cancel()
                    raise self.cancel_exception_cls("Stopped by user request.")
                done, _ = wait(list(pending.keys()), timeout=0.2, return_when=FIRST_COMPLETED)
                if not done:
                    continue
                for future in done:
                    chunk_index, chunk = pending.pop(future)
                    (
                        _chunk_index,
                        recovered_segments,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                    ) = future.result()
                    summary.prompt_tokens += int(prompt_tokens)
                    summary.completion_tokens += int(completion_tokens)
                    summary.total_tokens += int(total_tokens)
                    context_by_id = {context.record_id: context for context in chunk}
                    for raw_result, _covered_ids in recovered_segments:
                        for raw_row in raw_result.rows:
                            if not isinstance(raw_row, dict):
                                continue
                            source_index = normalize_source_index_value(raw_row.get("source_index", ""))
                            if not source_index.isdigit():
                                continue
                            record_id = int(source_index)
                            context = context_by_id.get(record_id)
                            if context is None:
                                continue
                            population = normalize_population_raw_trace(raw_row.get("population_raw", ""), context.population_context_text)
                            severity = normalize_severity_trace(
                                raw_row.get("severity", ""),
                                raw_row.get("population_raw", ""),
                                context.population_context_text,
                            )
                            existing_population, existing_severity = llm_payloads.get(record_id, ("", ""))
                            llm_payloads[record_id] = (
                                _merge_llm_value(existing_population, population),
                                _merge_llm_value(existing_severity, severity),
                            )
                    processed_llm_records += len(chunk)
                    if self.progress:
                        self.progress(
                            f"Population rescue LLM batch {chunk_index}/{total_chunks} completed "
                            f"(completed={base_processed_records + processed_llm_records}/{max(total_records, len(contexts))}, "
                            f"tokens={summary.prompt_tokens}/{summary.completion_tokens}/{summary.total_tokens})."
                        )
                    if self.on_state:
                        self.on_state(
                            {
                                "processed_records": int(base_processed_records + processed_llm_records),
                                "total_records": int(max(total_records, len(contexts))),
                                "prompt_tokens": int(summary.prompt_tokens),
                                "completion_tokens": int(summary.completion_tokens),
                                "total_tokens": int(summary.total_tokens),
                            }
                        )
        return llm_payloads

    def _run_llm_chunk(
        self,
        chunk_index: int,
        total_chunks: int,
        chunk: Sequence[_RecordRescueContext],
    ) -> Tuple[int, List[Tuple[Any, List[int]]], int, int, int]:
        if self.should_stop and self.should_stop():
            raise self.cancel_exception_cls("Stopped by user request.")
        if self.progress:
            self.progress(
                f"Population rescue LLM batch {chunk_index}/{total_chunks} started "
                f"(records={len(chunk)})."
            )
        record_texts = [context.rescue_prompt_text for context in chunk]
        record_ids = [context.record_id for context in chunk]
        segments = run_batch_adaptive(
            self.client.run_batch,
            record_texts,
            record_ids,
            progress=self.progress,
            should_stop=self.should_stop,
            cancel_exception_cls=self.cancel_exception_cls,
        )
        recovered_segments: List[Tuple[Any, List[int]]] = []
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        for raw_result, completed_ids in segments:
            prompt_tokens += int(getattr(raw_result.usage, "prompt_tokens", 0) or 0)
            completion_tokens += int(getattr(raw_result.usage, "completion_tokens", 0) or 0)
            total_tokens += int(getattr(raw_result.usage, "total_tokens", 0) or 0)
            recovered_segments.append((raw_result, _covered_record_ids(raw_result.rows)))
            missing_ids = [record_id for record_id in completed_ids if record_id not in set(_covered_record_ids(raw_result.rows))]
            if not missing_ids:
                continue
            missing_contexts = [context for context in chunk if context.record_id in set(missing_ids)]
            extra_segments = recover_missing_rows(
                self.client.run_batch,
                [context.rescue_prompt_text for context in missing_contexts],
                [context.record_id for context in missing_contexts],
                _covered_record_ids,
                progress=self.progress,
                should_stop=self.should_stop,
                cancel_exception_cls=self.cancel_exception_cls,
            )
            for extra_result, extra_ids in extra_segments:
                prompt_tokens += int(getattr(extra_result.usage, "prompt_tokens", 0) or 0)
                completion_tokens += int(getattr(extra_result.usage, "completion_tokens", 0) or 0)
                total_tokens += int(getattr(extra_result.usage, "total_tokens", 0) or 0)
                recovered_segments.append((extra_result, extra_ids))
        return chunk_index, recovered_segments, prompt_tokens, completion_tokens, total_tokens

    def _apply_llm_rescue(
        self,
        context: _RecordRescueContext,
        payload: Tuple[str, str],
        row_marks: Dict[int, Dict[str, bool]],
        summary: PopulationRescueSummary,
    ) -> None:
        llm_population, llm_severity = payload
        record_used_llm = False
        for row in context.rows:
            if llm_population and not clean_common_noise(row.population_raw):
                row.population_raw = llm_population
                row_marks[id(row)]["llm"] = True
                record_used_llm = True
                summary.llm_population_rows += 1
            if llm_severity and not clean_common_noise(row.severity):
                row.severity = llm_severity
                row_marks[id(row)]["llm"] = True
                record_used_llm = True
                summary.llm_severity_rows += 1
        if record_used_llm:
            summary.llm_records_applied += 1

    def _finalize_population_status(
        self,
        context: _RecordRescueContext,
        initial_state: Dict[int, Tuple[bool, bool]],
        row_marks: Dict[int, Dict[str, bool]],
    ) -> None:
        has_any_cue = context.has_population_cue or context.has_severity_cue
        for row in context.rows:
            row_id = id(row)
            initial_population, initial_severity = initial_state.get(row_id, (False, False))
            marks = row_marks.get(row_id, {})
            base_status = clean_common_noise(row.population_status)
            if not any(marks.values()) and base_status:
                continue
            final_population = bool(clean_common_noise(row.population_raw))
            final_severity = bool(clean_common_noise(row.severity))
            if final_population:
                if initial_population:
                    if not initial_severity and final_severity:
                        if marks.get("llm"):
                            row.population_status = "main_pass_plus_llm_severity"
                        elif marks.get("local"):
                            row.population_status = "main_pass_plus_local_severity"
                        else:
                            row.population_status = "main_pass"
                    else:
                        row.population_status = "main_pass"
                    continue
                if marks.get("llm"):
                    row.population_status = (
                        "llm_rescue_population_and_severity"
                        if final_severity and not initial_severity
                        else "llm_rescue_population"
                    )
                elif marks.get("local"):
                    row.population_status = (
                        "local_rescue_population_and_severity"
                        if final_severity and not initial_severity
                        else "local_rescue_population"
                    )
                elif marks.get("broadcast"):
                    row.population_status = "record_broadcast"
                else:
                    row.population_status = "main_pass"
                continue
            if final_severity:
                if initial_severity:
                    row.population_status = "main_pass_severity_only"
                elif marks.get("llm"):
                    row.population_status = "llm_rescue_severity_only"
                elif marks.get("local"):
                    row.population_status = "local_rescue_severity_only"
                elif marks.get("broadcast"):
                    row.population_status = "record_broadcast"
                else:
                    row.population_status = "main_pass_severity_only"
                continue
            row.population_status = "cue_present_unresolved" if has_any_cue else "no_population_cue"

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Sequence, Tuple


@dataclass
class ParsedRecord:
    record_id: int
    journal_line: str = ""
    pmid: str = ""
    nct_id: str = ""
    doi: str = ""
    year: str = ""
    date_line: str = ""
    title: str = ""
    sections: Dict[str, str] = None

    def __post_init__(self) -> None:
        if self.sections is None:
            self.sections = {}


def split_pubmed_records(text: str) -> List[str]:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        return []

    separator_split = re.split(r"(?m)^\s*=+\s*$", cleaned)
    separated_records = [chunk.strip() for chunk in separator_split if chunk.strip()]
    bracketed_records = [chunk for chunk in separated_records if re.match(r"^\[\d+\]\s", chunk)]
    if len(bracketed_records) >= 2:
        return bracketed_records

    matches = list(re.finditer(r"(?m)^(?:\d+\.\s|\[\d+\]\s)", cleaned))
    if len(matches) >= 2:
        records: List[str] = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
            chunk = cleaned[start:end].strip()
            if chunk:
                records.append(chunk)
        return records

    chunks = re.split(r"\n\s*\n(?=[A-Z][^\n]{10,200}\n)", cleaned)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def iter_pubmed_records_from_file(source_path: str) -> Iterator[str]:
    text = Path(source_path).read_text(encoding="utf-8", errors="replace")
    for record in split_pubmed_records(text):
        yield record


_SECTION_HEADERS = {
    "BACKGROUND",
    "METHODS",
    "RESULTS",
    "CONCLUSIONS",
    "OBJECTIVE",
    "OBJECTIVES",
    "DESIGN",
    "SETTING",
    "PATIENTS",
    "PARTICIPANTS",
    "INTERVENTIONS",
    "MAIN OUTCOME MEASURES",
    "MAIN OUTCOMES AND MEASURES",
    "TRIAL REGISTRATION",
    "LIMITATIONS",
    "FUNDING",
    "ABSTRACT",
    "SUMMARY",
}

_SECTION_KEYWORDS = sorted(_SECTION_HEADERS, key=len, reverse=True)
_SECTION_SPLIT_RE = re.compile(r"(?i)\b(" + "|".join(re.escape(x) for x in _SECTION_KEYWORDS) + r")\s*:\s*")


def _is_section_header(line: str) -> bool:
    text = line.strip()
    if ":" not in text:
        return False
    key = text.split(":", 1)[0].strip().upper()
    return key in _SECTION_HEADERS


def _is_date_line(text: str) -> bool:
    if re.match(r"^(?:Epub\s+)?\d{4}\s+[A-Za-z]{3}\s+\d{1,2}\.?$", text):
        return True
    if re.match(r"^[A-Za-z]{3}\s+\d{1,2}\.?$", text):
        return True
    return False


def _is_metadata_line(line: str) -> bool:
    text = line.strip()
    if not text:
        return True
    if text.startswith("[") and "]" in text[:8]:
        return True
    if text.upper().startswith("PMID:") or " DOI:" in text.upper() or " YEAR:" in text.upper():
        return True
    if _is_date_line(text):
        return True
    return False


def _clean_title_candidate(text: str) -> str:
    title = re.sub(r"\s+", " ", text).strip(" .;-")
    if not title:
        return ""
    lower = title.lower()
    if "doi:" in lower or "pmid:" in lower:
        return ""
    if _is_section_header(title + ":"):
        return ""
    if re.match(r"^\d{4}\s+[A-Za-z]{3}\s+\d{1,2}$", title):
        return ""
    return title


def _is_probable_title(text: str) -> bool:
    cleaned = _clean_title_candidate(text)
    if not cleaned:
        return False
    words = cleaned.split()
    if len(cleaned) < 15 or len(cleaned) > 240:
        return False
    if len(words) > 36:
        return False
    if cleaned.count(". ") > 1:
        return False
    return True


def _normalize_section_name(raw_name: str) -> str:
    key = raw_name.strip().upper()
    if key.startswith("CONCLUSIONS"):
        return "CONCLUSIONS"
    if key.startswith("OBJECTIVE"):
        return "OBJECTIVE"
    if key.startswith("MAIN OUTCOME"):
        return "MAIN OUTCOMES AND MEASURES"
    return key


def _extract_section_chunks(line: str) -> List[Tuple[str, str]]:
    chunks: List[Tuple[str, str]] = []
    matches = list(_SECTION_SPLIT_RE.finditer(line))
    if not matches:
        return chunks
    for idx, match in enumerate(matches):
        section = _normalize_section_name(match.group(1))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(line)
        content = line[start:end].strip()
        chunks.append((section, content))
    return chunks


def parse_record_structured(record_text: str, record_id: int) -> ParsedRecord:
    lines = [line.strip() for line in record_text.replace("\r\n", "\n").split("\n")]
    parsed = ParsedRecord(record_id=record_id)
    if not lines:
        return parsed

    first_idx = next((idx for idx, line in enumerate(lines) if line), -1)
    if first_idx == -1:
        return parsed
    parsed.journal_line = re.sub(r"^\[\d+\]\s*", "", lines[first_idx]).strip()
    cursor = first_idx + 1

    while cursor < len(lines):
        line = lines[cursor]
        if not line:
            cursor += 1
            continue
        upper = line.upper()
        if "PMID:" in upper or "DOI:" in upper or "YEAR:" in upper:
            pmid_match = re.search(r"\bPMID:\s*([0-9]+)\b", line, flags=re.I)
            doi_match = re.search(r"\bDOI:\s*([^\s]+)", line, flags=re.I)
            year_match = re.search(r"\bYear:\s*(\d{4})\b", line, flags=re.I)
            nct_match = re.search(r"\b(NCT\d{8})\b", line, flags=re.I)
            if pmid_match:
                parsed.pmid = pmid_match.group(1)
            if doi_match:
                parsed.doi = doi_match.group(1).rstrip(".;,")
            if year_match:
                parsed.year = year_match.group(1)
            if nct_match and not parsed.nct_id:
                parsed.nct_id = nct_match.group(1).upper()
            cursor += 1
            continue
        nct_match = re.search(r"\b(NCT\d{8})\b", line, flags=re.I)
        if nct_match and not parsed.nct_id:
            parsed.nct_id = nct_match.group(1).upper()
        if _is_date_line(line):
            if not parsed.date_line:
                parsed.date_line = line
            cursor += 1
            continue
        break

    if not parsed.nct_id:
        nct_match = re.search(r"\b(NCT\d{8})\b", record_text, flags=re.I)
        if nct_match:
            parsed.nct_id = nct_match.group(1).upper()

    if not parsed.year:
        for probe in lines[first_idx : min(first_idx + 6, len(lines))]:
            year_match = re.search(r"\b(19|20)\d{2}\b", probe)
            if year_match:
                parsed.year = year_match.group(0)
                break

    title_start = cursor
    title_lines: List[str] = []
    while cursor < len(lines):
        line = lines[cursor]
        if not line:
            if title_lines:
                cursor += 1
                break
            cursor += 1
            continue
        if _is_section_header(line) or _is_metadata_line(line) or line.lower().startswith("conflict of interest statement"):
            break
        title_lines.append(line)
        cursor += 1
        if len(title_lines) >= 3:
            break

    joined_title = _clean_title_candidate(" ".join(title_lines))
    if _is_probable_title(joined_title):
        parsed.title = joined_title
    else:
        parsed.title = ""
        cursor = title_start

    current_section = ""
    saw_structured_sections = False
    summary_lines: List[str] = []
    for line in lines[cursor:]:
        if not line:
            continue
        if line.lower().startswith("conflict of interest statement"):
            break
        if _is_metadata_line(line):
            continue
        chunks = _extract_section_chunks(line)
        if chunks:
            saw_structured_sections = True
            for section, content in chunks:
                current_section = section
                if content:
                    existing = parsed.sections.get(section, "")
                    parsed.sections[section] = f"{existing} {content}".strip()
            continue
        if current_section:
            existing = parsed.sections.get(current_section, "")
            parsed.sections[current_section] = f"{existing} {line}".strip()
        else:
            summary_lines.append(line)

    if summary_lines:
        parsed.sections["SUMMARY"] = " ".join(summary_lines).strip()
    elif not saw_structured_sections:
        parsed.sections["SUMMARY"] = ""

    return parsed


def format_parsed_record_for_llm(parsed: ParsedRecord) -> str:
    core_sections = [
        "OBJECTIVE",
        "OBJECTIVES",
        "BACKGROUND",
        "PATIENTS",
        "PARTICIPANTS",
        "METHODS",
        "INTERVENTIONS",
        "MAIN OUTCOMES AND MEASURES",
        "MAIN OUTCOME MEASURES",
        "RESULTS",
        "CONCLUSIONS",
        "TRIAL REGISTRATION",
    ]
    lines: List[str] = []
    # Title/journal/date metadata is handled separately and does not need to
    # be re-sent to the model for intervention/result extraction.
    if parsed.nct_id:
        lines.append(f"NCT ID: {parsed.nct_id}")
    for key in core_sections:
        value = parsed.sections.get(key, "")
        if value:
            lines.append(f"{key}: {value}")
    # Skip free-form extra sections to reduce token bloat/noise.
    summary = parsed.sections.get("SUMMARY", "")
    if summary:
        lines.append(f"SUMMARY: {summary}")
    return "\n".join(lines).strip()


def parse_record_metadata(record_text: str) -> Dict[str, str]:
    parsed = parse_record_structured(record_text, record_id=0)
    return {"title": parsed.title, "year": parsed.year}

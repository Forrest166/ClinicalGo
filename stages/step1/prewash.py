#!/usr/bin/env python3
"""
Clinical Trial Extraction Pipeline  v2.0
=========================================
Full-spectrum: Rule engine + NER + Semantic classification

Three output files (Step1 naming):
  1. Step1_<source_file_stem>_<YYMMDDHH>_cleaned_abstracts.txt
  2. Step1_<source_file_stem>_<YYMMDDHH>_extraction_results.csv
  3. Step1_<source_file_stem>_<YYMMDDHH>_quality_metrics.txt

Extracted fields:
  PMID | Index | Title | Journal | Year | DOI
  NCT  | objective(效果研究/机制研究/其他) | drugs | indication
  outcome(有效/无效/安全/有毒/未知)
  dose | followup | OS | PFS | p_values | CI | OR_RR_HR | sample_size | toxicity

Deps: pip install pandas  (tkinter is stdlib)
Run:  python pipeline_v2.py
"""

import re, os, sys, time, threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict
import pandas as pd

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: PARSER
# Handles all PubMed numbered-list edge cases:
#   - DOI wrap across line 1/2
#   - Author info / Comment in / Copyright / PMCID noise blocks
#   - DOI+PMID in same paragraph (scan line-by-line)
# ══════════════════════════════════════════════════════════════════════════════

_REC_LINE   = re.compile(r"^(\d+)\.\s+\S")
_DOI_CONT   = re.compile(r"^10\.\d{4,}/\S")
_DOI_LINE   = re.compile(r"^DOI:\s*(.+)", re.I)
_PMID_LINE  = re.compile(r"^PMID:\s*(\d+)", re.I)
_PMCID_LINE = re.compile(r"^PMCID:\s*", re.I)
_HEADER_DOI = re.compile(r"\bdoi:\s*(10\.\d{4,}/\S+)", re.I)
_DATE_ONLY  = re.compile(r"^(?:Epub\s+)?(?:19|20)\d{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\.?$", re.I)
_ARTICLE_IN = re.compile(r"^\[Article in [^\]]+\]", re.I)
_AUTHOR_LINE = re.compile(
    r"^[A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+)*"
    r"(?:\s+(?:[A-Z]{1,4}|[A-Z][a-z]+))?"
    r"(?:\([^)]*\)|\s+\d+(?:st|nd|rd|th))"
)
def _paragraphs(lines):
    groups, cur = [], []
    for ln in lines:
        if ln.strip():
            cur.append(ln)
        elif cur:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


@dataclass
class RawRecord:
    index:          int  = 0
    pmid:           str  = ""
    doi:            str  = ""
    journal_line:   str  = ""
    title:          str  = ""
    abstract_clean: str  = ""


def _clean_doi(doi: str) -> str:
    return doi.strip().rstrip(".,;)]")


def _extract_doi(text: str) -> str:
    m = _HEADER_DOI.search(text)
    if m:
        return _clean_doi(m.group(1))
    m = re.search(r"\b(10\.\d{4,}/\S+)", text)
    return _clean_doi(m.group(1)) if m else ""


def _strip_doi_from_citation(text: str) -> str:
    text = _HEADER_DOI.sub("", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*\.\s*\.\s*", ". ", text)
    return text.strip(" .")


def _is_record_start_line(lines, idx: int) -> bool:
    return bool(_REC_LINE.match(lines[idx]) and (idx == 0 or not lines[idx - 1].strip()))


def _looks_like_author_group(group) -> bool:
    text = " ".join(ln.strip() for ln in group if ln.strip())
    if not text:
        return False
    if "no authors listed" in text.lower():
        return True
    if len(text) > 500 or ":" in text:
        return False
    if re.match(r"^[A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+)*\(\d+\)", text) and text.count(",") >= 1:
        return True
    name_hits = re.findall(
        r"\b[A-Z][a-zA-Z'.-]+(?:-[A-Z][a-zA-Z'.-]+)?\s+"
        r"(?:[A-Z]{1,4}(?:\s+Jr)?|[A-Z][a-z]+(?:\s+[A-Z]{1,3})?)\b",
        text,
    )
    return len(name_hits) >= 3 and text.count(",") >= 2


def _is_noise_block(first_line: str) -> bool:
    text = re.sub(r"\s+", " ", first_line).strip()
    if not text:
        return False
    if _ARTICLE_IN.match(text):
        return True
    if text.startswith(("©", "(C)", "(c)", "漏")):
        return True

    lower = text.casefold()
    prefixes = (
        "author information:",
        "collaborators:",
        "comment in",
        "comment on",
        "erratum in",
        "erratum for",
        "update in",
        "update of",
        "retraction in",
        "retraction of",
        "republished from",
        "republished in",
        "expression of concern in",
        "expression of concern over",
        "corrected and republished in",
        "published erratum",
        "study funding/competing interests:",
        "conflict of interest statement:",
        "conflict of interest disclosures:",
        "declaration of competing interest",
        "declaration of competing interests",
        "competing interests:",
        "competing interest statement:",
        "disclosure:",
        "disclosures:",
        "publisher's note:",
        "electronic address:",
    )
    if lower.startswith(prefixes):
        return True
    if re.match(r"^(?:crown\s+)?copyright\b", lower):
        return True
    return bool(
        re.match(
            r"^(?:comment|erratum|update|retraction|republished|"
            r"expression of concern|corrected and republished)\s+"
            r"(?:in|for|from|of)\b",
            text,
            re.I,
        )
    )


def _strip_inline_noise(text: str) -> str:
    text = re.sub(
        r"\bSTUDY FUNDING/COMPETING INTERESTS:.*?(?=\bTRIALS?\s+REGISTRATION|\bTRIAL REGISTRATION DATE\b|$)",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\b(?:Conflict of interest statement:|Declaration of competing interests?:)\s*.*$",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\b(?:None of the authors have any conflicts of interest to declare\.|"
        r"There were no competing interests\.|"
        r"The authors declare no competing (?:financial )?interests\.)",
        "",
        text,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", text).strip()


def parse_block(block: str) -> Optional[RawRecord]:
    lines = block.splitlines()
    if not lines:
        return None
    m = re.match(r"^(\d+)\.\s+(.*)", lines[0])
    if not m:
        return None
    rec = RawRecord()
    rec.index = int(m.group(1))
    header_lines = [m.group(2).strip()]
    pos = 1
    while pos < len(lines) and lines[pos].strip():
        header_lines.append(lines[pos].strip())
        pos += 1

    header_text = re.sub(r"\s+", " ", " ".join(header_lines)).strip()
    rec.doi = _extract_doi(header_text)
    rec.journal_line = _strip_doi_from_citation(header_text)

    groups = _paragraphs(lines[pos + 1:] if pos < len(lines) else [])
    if not groups:
        for ln in lines:
            mp = _PMID_LINE.match(ln.strip())
            if mp:
                rec.pmid = mp.group(1)
                break
        return rec

    grp_idx = 0
    while grp_idx < len(groups):
        candidate = " ".join(l.strip() for l in groups[grp_idx]).strip()
        if candidate and not _is_noise_block(groups[grp_idx][0].strip()) and not _DATE_ONLY.match(candidate):
            rec.title = candidate
            grp_idx += 1
            break
        grp_idx += 1

    while grp_idx < len(groups) and _looks_like_author_group(groups[grp_idx]):
        grp_idx += 1

    body_parts = []
    for grp in groups[grp_idx:]:
        first = grp[0].strip()
        if _is_noise_block(first) or _looks_like_author_group(grp):
            continue
        kept = []
        for ln in grp:
            ls = ln.strip()
            if not ls:
                continue
            if _is_noise_block(ls):
                break
            if _PMCID_LINE.match(ls):
                continue
            md = _DOI_LINE.match(ls)
            if md:
                if not rec.doi:
                    rec.doi = _clean_doi(md.group(1))
                continue
            mp = _PMID_LINE.match(ls)
            if mp:
                rec.pmid = mp.group(1)
                continue
            if _DOI_CONT.match(ls) and not kept:
                if not rec.doi:
                    rec.doi = _clean_doi(ls)
                continue
            kept.append(ls)
        if kept:
            cleaned = _strip_inline_noise(" ".join(kept))
            if cleaned:
                body_parts.append(cleaned)

    rec.abstract_clean = "\n\n".join(body_parts)
    if not rec.pmid:
        for ln in lines:
            mp = _PMID_LINE.match(ln.strip())
            if mp:
                rec.pmid = mp.group(1)
                break
    if not rec.doi:
        rec.doi = _extract_doi(block)
    return rec


def parse_file(path: str, max_records: int = 0) -> list:
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()
    starts = [i for i in range(len(lines)) if _is_record_start_line(lines, i)]
    limit = max_records if max_records > 0 else len(starts)
    records = []
    for i, s in enumerate(starts[:limit]):
        e = starts[i+1] if i+1 < len(starts) else len(lines)
        r = parse_block("\n".join(lines[s:e]))
        if r:
            records.append(r)
    return records


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: TEXT CLEANER + SECTION SEGMENTER
# ══════════════════════════════════════════════════════════════════════════════

_UNICODE_MAP = {
    "\u2013":"-", "\u2014":"-", "\u2212":"-",
    "\u2264":"<=", "\u2265":">=", "\u00b1":"+-",
    "\u2018":"'", "\u2019":"'", "\u201c":'"', "\u201d":'"',
    "\u00a0":" ", "\u2009":" ", "\u00d7":"x",
}

_SECTION_SPECS = [
    (r"DESIGN,\s*SETTING,\s*AND\s*(?:PATIENTS?|PARTICIPANTS?|SUBJECTS?)", "methods"),
    (r"DESIGN,\s*SETTING,\s*PATIENTS?,\s*AND\s*INTERVENTIONS", "methods"),
    (r"MEASUREMENTS?\s+AND\s+RESULTS?", "results"),
    (r"CONCLUSIONS?\s+AND\s+RELEVANCE", "conclusions"),
    (r"CLINICAL\s+TRIAL\s+REGISTRATION(?:\s+INFORMATION)?", "trial_registration"),
    (r"TRIALS?\s+REGISTRATION(?:\s+NUMBER)?", "trial_registration"),
    (r"MAIN\s+OUTCOME\s+MEASURES?", "main_outcomes"),
    (r"OUTCOME\s+MEASURES?", "main_outcomes"),
    (r"STUDY\s+OBJECTIVE[S]?", "objective"),
    (r"OBJECTIVE[S]?|AIM[S]?|PURPOSE", "objective"),
    (r"RATIONALE|IMPORTANCE|INTRODUCTION|BACKGROUND|CONTEXT", "background"),
    (r"METHODS?|MATERIALS?\s+AND\s+METHODS?|DESIGN(?:\s+AND\s+SETTING)?", "methods"),
    (r"SETTING[S]?", "setting"),
    (r"PATIENTS?|PARTICIPANTS?|SUBJECTS?", "patients"),
    (r"INTERVENTIONS?", "interventions"),
    (r"RESULTS?|FINDINGS?", "results"),
    (r"LIMITATIONS?", "limitations"),
    (r"FUNDING", "funding"),
    (r"CONCLUSIONS?|CONCLUSION|SUMMARY|INTERPRETATION|DISCUSSION", "conclusions"),
]

_SECTION_RE = re.compile(
    r"\b(" + "|".join(f"(?:{pat})" for pat, _ in _SECTION_SPECS) + r")\s*:[ \t]*",
    re.I,
)


def clean_text(t: str) -> str:
    for s, r in _UNICODE_MAP.items():
        t = t.replace(s, r)
    t = re.sub(r"(\d)(mg|g|ml|kg|mcg|ug)\b", r"\1 \2", t, flags=re.I)
    t = re.sub(r"(?<![.!?:;])\n(?=[a-z(])", " ", t)
    return re.sub(r"[ \t]+", " ", t).strip()


def segment(text: str):
    secs = {key: "" for key in {k for _, k in _SECTION_SPECS}}
    parts = _SECTION_RE.split(text)
    if len(parts) <= 1:
        return secs, False
    lead = parts[0].strip()
    if lead:
        secs["background"] = lead
    i = 1
    while i < len(parts) - 1:
        label = parts[i].strip().upper()
        content = parts[i+1].strip() if i+1 < len(parts) else ""
        for pat, key in _SECTION_SPECS:
            if re.fullmatch(pat, label, re.I):
                secs[key] = (secs[key] + " " + content).strip() if secs[key] else content
                break
        i += 2
    return secs, True


def extract_year(journal_line: str) -> str:
    m = re.search(r"\b(19|20)\d{2}\b", journal_line)
    return m.group(0) if m else "NaN"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: FIELD EXTRACTORS
# Each returns a string or "NaN"
# ══════════════════════════════════════════════════════════════════════════════

# ── NCT number ───────────────────────────────────────────────────────────────
def extract_nct(text: str) -> str:
    m = re.search(r"NCT\s*(\d{6,8})", text)
    return f"NCT{m.group(1)}" if m else "NaN"


# ── Drug / intervention names ─────────────────────────────────────────────────
_DRUG_LIST_RE = re.compile(
    r"\b(fluoxetine|sertraline|paroxetine|escitalopram|citalopram|fluvoxamine|"
    r"venlafaxine|desvenlafaxine|duloxetine|milnacipran|levomilnacipran|"
    r"mirtazapine|bupropion|nortriptyline|imipramine|amitriptyline|clomipramine|"
    r"desipramine|doxepin|trimipramine|nefazodone|trazodone|vilazodone|vortioxetine|"
    r"moclobemide|phenelzine|tranylcypromine|selegiline|"
    r"lithium|quetiapine|olanzapine|aripiprazole|risperidone|ziprasidone|"
    r"ketoconazole|tianeptine|psilocybin|ketamine|esketamine|"
    r"lamotrigine|valproate|carbamazepine|topiramate|gabapentin|"
    r"methylphenidate|amphetamine|modafinil|arecoline|benztropine|fluphenazine|"
    r"ECT|electro.?convulsive\s+therapy|"
    r"rTMS|TMS|transcranial\s+magnetic\s+stimulation|"
    r"DBS|deep\s+brain\s+stimulation|"
    r"CBT|cognitive.behavioral\s+therapy|cognitive\s+behavioural\s+therapy|"
    r"MBCT|mindfulness.based\s+cognitive\s+therapy|"
    r"IPT|interpersonal\s+(?:psycho)?therapy|"
    r"PST|problem.solving\s+therapy|CBASP|"
    r"behavioral\s+activation|psychotherapy|psychodynamic\s+therapy|"
    r"light\s+therapy|phototherapy|"
    r"placebo|sham|treatment\s+as\s+usual|TAU)\b",
    re.I,
)
_DRUG_SUFFIX_RE = re.compile(
    r"\b[a-z]{5,}(?:mab|nib|zumab|ximab|pril|sartan|olol|pine|"
    r"cycline|mycin|cillin|floxacin|statin|prazole|xetine|"
    r"zepam|zolam|done|pramine|triptyline|azine|ridone|setron)\b",
    re.I,
)

def extract_drugs(text: str) -> str:
    seen, found = set(), []
    for m in _DRUG_LIST_RE.finditer(text):
        d = m.group(0).lower().strip()
        if d not in seen:
            seen.add(d)
            found.append(m.group(0))
    for m in _DRUG_SUFFIX_RE.finditer(text):
        d = m.group(0).lower()
        if d not in seen and len(d) > 6:
            seen.add(d)
            found.append(m.group(0))
    return "; ".join(found[:5]) if found else "NaN"


# ── Indication / disease area ─────────────────────────────────────────────────
_INDICATIONS = [
    (re.compile(r"\bmajor depressive disorder\b|\bMDD\b",       re.I), "Major Depressive Disorder"),
    (re.compile(r"\btreatment.resistant depression\b|\bTRD\b",  re.I), "Treatment-Resistant Depression"),
    (re.compile(r"\bdysthymia\b|\bpersistent depressive disorder\b", re.I), "Dysthymia"),
    (re.compile(r"\bbipolar\b",                                 re.I), "Bipolar Disorder"),
    (re.compile(r"\bschizophrenia\b",                           re.I), "Schizophrenia"),
    (re.compile(r"\banxiety disorder\b",                        re.I), "Anxiety Disorder"),
    (re.compile(r"\bPTSD\b|post.traumatic stress",              re.I), "PTSD"),
    (re.compile(r"\bOCD\b|obsessive.compulsive",                re.I), "OCD"),
    (re.compile(r"\bADHD\b|attention.deficit",                  re.I), "ADHD"),
    (re.compile(r"\bAlzheimer\b|\bdementia\b",                  re.I), "Alzheimer/Dementia"),
    (re.compile(r"\bpost.?stroke\b",                            re.I), "Post-Stroke Depression"),
    (re.compile(r"\bmultiple sclerosis\b|\bMS\b",               re.I), "Multiple Sclerosis"),
    (re.compile(r"\bcancer\b|\boncolog\w+",                     re.I), "Cancer"),
    (re.compile(r"\bdiabet\w+",                                 re.I), "Diabetes"),
    (re.compile(r"\bcardiac\b|\bmyocardial\b",                  re.I), "Cardiac Disease"),
    (re.compile(r"\bParkinson\b",                               re.I), "Parkinson Disease"),
    (re.compile(r"\bpostnatal depression\b|\bpostpartum depression\b", re.I), "Postpartum Depression"),
    (re.compile(r"\bdepression\b",                              re.I), "Depression (unspecified)"),
]

def extract_indication(text: str) -> str:
    for pattern, label in _INDICATIONS:
        if pattern.search(text):
            return label
    return "NaN"


# ── Study objective classifier ─────────────────────────────────────────────────
_EFF_SIG = re.compile(
    r"\b(?:efficac\w+|effective\w*|treatment\s+effect|clinical\s+trial|"
    r"randomized|double.blind|placebo.controlled|response\s+rate|remission|"
    r"relapse|antidepressant\s+effect|therapeutic\s+effect|clinical\s+outcome|"
    r"controlled\s+trial|comparative\s+study)\b", re.I,
)
_MECH_SIG = re.compile(
    r"\b(?:mechanism|pathway|neurobiolog\w+|pharmacokinetic\w*|pharmacodynamic\w*|"
    r"biomarker|genetic|molecular|receptor|neurotransmitter|serotonin|"
    r"dopamine|norepinephrine|cortisol|HPA\s+axis|neuroimaging|fMRI|EEG|"
    r"neuroplasticity|epigenetic|proteom\w+|metabolom\w+|"
    r"sleep\s+EEG|polysomnograph\w+|cholinergic|adrenergic)\b", re.I,
)

def classify_objective(text: str) -> str:
    eff  = len(_EFF_SIG.findall(text))
    mech = len(_MECH_SIG.findall(text))
    if eff == 0 and mech == 0:
        return "其他"
    if mech > eff:
        return "机制研究"
    return "效果研究"


# ── Outcome result classifier ──────────────────────────────────────────────────
_OUT_POS = re.compile(
    r"\b(?:significantly\s+(?:improved?|reduced?|better|superior|greater|"
    r"decreas\w+|lower\w*|higher\w*|fewer|more\s+effective)|"
    r"superior\s+to\s+(?:placebo|control)|"
    r"significant\s+(?:improvement|reduction|benefit|response|remission|"
    r"decrease|advantage|difference)|"
    r"efficacious|clinically\s+significant|treatment\s+response\b|"
    r"significantly\s+reduc\w+|significantly\s+improv\w+)\b", re.I,
)
_OUT_NEG = re.compile(
    r"\b(?:no\s+significant\s+(?:difference|improvement|effect|benefit|change)|"
    r"not\s+significantly|did\s+not\s+significantly|"
    r"failed\s+to\s+(?:demonstrate|show|achieve|reach)|"
    r"no\s+statistically\s+significant|non.significant\b|"
    r"comparable\s+to\s+placebo|not\s+superior\s+to\s+placebo|"
    r"did\s+not\s+(?:differ|improve|reduce))\b", re.I,
)
_TOX_POS = re.compile(
    r"\b(?:adverse\s+(?:event|effect|reaction)|poorly\s+tolerated|"
    r"toxicity\b|significant\s+(?:adverse|side)\s+effects?|"
    r"discontinued\s+due\s+to|serious\s+adverse|hepatotoxic|"
    r"cardiotoxic|QT\s+prolongation|suicidal\s+ideation)\b", re.I,
)
_SAFE_POS = re.compile(
    r"\b(?:well.tolerated|generally\s+well\s+tolerated|good\s+tolerability|"
    r"no\s+significant\s+(?:adverse|side)\s+effects?|safe\s+and\s+well|"
    r"no\s+serious\s+adverse|minimal\s+(?:adverse|side)\s+effects?)\b", re.I,
)

def classify_outcome(text: str) -> str:
    pos  = len(_OUT_POS.findall(text))
    neg  = len(_OUT_NEG.findall(text))
    tox  = len(_TOX_POS.findall(text))
    safe = len(_SAFE_POS.findall(text))
    if pos == 0 and neg == 0 and tox == 0 and safe == 0:
        return "未知"
    if tox > 0 and pos == 0 and neg == 0 and safe == 0:
        return "有毒"
    if safe > 0 and tox == 0 and pos == 0 and neg == 0:
        return "安全"
    if pos > 0 and neg == 0:
        return "有效"
    if neg > 0 and pos == 0:
        return "无效"
    return "有效" if pos > neg else "无效"


# ── Dose ──────────────────────────────────────────────────────────────────────
_DOSE_RE = re.compile(
    r"(\d+\.?\d*)\s*(mg(?:/(?:kg|d|day))?|g\b|ml\b|mcg\b|ug\b|ng\b|IU\b|units?)\b",
    re.I,
)

def extract_dose(text: str) -> str:
    seen, found = set(), []
    for m in _DOSE_RE.finditer(text):
        key = (m.group(1), m.group(2).lower())
        if key not in seen:
            seen.add(key)
            found.append(m.group(0).strip())
    return "; ".join(found[:4]) if found else "NaN"


# ── Follow-up duration ────────────────────────────────────────────────────────
_FU_PATS = [
    re.compile(r"(\d+)[- ]?(week|month|year)s?\s+follow[- ]?up",    re.I),
    re.compile(r"follow[- ]?up\s+(?:of\s+)?(\d+)\s+(week|month|year)s?", re.I),
    re.compile(r"(\d+)[- ]?(week|month|year)s?\s+(?:study|trial|treatment\s+period)", re.I),
    re.compile(r"over\s+(?:a\s+)?(\d+)[- ]?(week|month|year)s?\s+(?:period|study)", re.I),
    re.compile(r"assessed\s+over\s+(?:a\s+)?(\d+)[- ]?(week|month|year)s?", re.I),
]

def extract_followup(text: str) -> str:
    for pat in _FU_PATS:
        m = pat.search(text)
        if m:
            n, unit = m.group(1), m.group(2).lower()
            suffix = "s" if int(n) > 1 and not unit.endswith("s") else ""
            return f"{n} {unit}{suffix}"
    return "NaN"


# ── Overall Survival ──────────────────────────────────────────────────────────
_OS_PATS = [
    re.compile(r"overall\s+survival[^.]{0,100}?(\d+\.?\d*)\s*(months?|years?|%)", re.I),
    re.compile(r"\bOS\b[^.]{0,80}?(\d+\.?\d*)\s*(months?|years?|%)",              re.I),
    re.compile(r"median\s+(?:overall\s+)?survival[^.]{0,80}?(\d+\.?\d*)\s*(months?|years?)", re.I),
]

def extract_os(text: str) -> str:
    for pat in _OS_PATS:
        m = pat.search(text)
        if m:
            return m.group(0).strip()[:100]
    return "NaN"


# ── Progression-Free Survival ─────────────────────────────────────────────────
_PFS_PATS = [
    re.compile(r"progression.free\s+survival[^.]{0,100}?(\d+\.?\d*)\s*(months?|years?|%)", re.I),
    re.compile(r"\bPFS\b[^.]{0,80}?(\d+\.?\d*)\s*(months?|years?|%)",                     re.I),
    re.compile(r"time\s+to\s+progression[^.]{0,80}?(\d+\.?\d*)\s*(months?|years?)",        re.I),
]

def extract_pfs(text: str) -> str:
    for pat in _PFS_PATS:
        m = pat.search(text)
        if m:
            return m.group(0).strip()[:100]
    return "NaN"


# ── P-values ──────────────────────────────────────────────────────────────────
_PVAL_PATS = [
    re.compile(r"p\s*[<>=]\s*0\.\d+",                 re.I),
    re.compile(r"p\s*[<>=]\s*\.\d+",                  re.I),
    re.compile(r"p\s*values?\s*[<>=]\s*\.?\d+",       re.I),
    re.compile(r"p\s*=\s*\.\d+",                       re.I),
]

def extract_pvalues(text: str) -> str:
    seen, found = set(), []
    for pat in _PVAL_PATS:
        for m in pat.finditer(text):
            v = m.group(0).strip().lower()
            # normalise whitespace for dedup
            vn = re.sub(r"\s+", "", v)
            if vn not in seen:
                seen.add(vn)
                found.append(m.group(0).strip())
    return "; ".join(found[:6]) if found else "NaN"


# ── Confidence Intervals ──────────────────────────────────────────────────────
_CI_RE = re.compile(
    r"9[05]%?\s*(?:confidence\s*interval[s]?|CI)[,\s:=]*"
    r"[\[(]?\s*(-?\d+\.?\d*)\s*(?:to|[-])\s*(-?\d+\.?\d*)\s*[\])]?",
    re.I,
)

def extract_ci(text: str) -> str:
    found = [f"{m.group(1)} to {m.group(2)}" for m in _CI_RE.finditer(text)]
    return "; ".join(found[:4]) if found else "NaN"


# ── OR / RR / HR ──────────────────────────────────────────────────────────────
_RATIO_RE = re.compile(
    r"(?:"
    r"(?:odds\s+ratio|relative\s+risk|hazard\s+ratio)"
    r"[\s\[\(]*(?:OR|RR|HR)?[\s\]\)]*[,=\s]\s*"
    r"|(?:\bOR|\bRR|\bHR|\bNNT|\bSMD)\s*[=:,]\s*"
    r")(-?\d+\.?\d*)",
    re.I,
)

def extract_ratios(text: str) -> str:
    found = [m.group(0).strip() for m in _RATIO_RE.finditer(text)]
    return "; ".join(found[:4]) if found else "NaN"


# ── Sample size ───────────────────────────────────────────────────────────────
_N_PATS = [
    re.compile(r"(?:[nN]|N)\s*=\s*(\d{2,5})",                                     re.I),
    re.compile(r"\b(\d{2,5})\s+(?:participants?|patients?|subjects?|adults?)\b",    re.I),
    re.compile(r"total\s+of\s+(\d{2,5})\s+(?:participants?|patients?)",            re.I),
    re.compile(r"(?:randomized?|enrolled?|recruited?)\s+(\d{2,5})",                 re.I),
]

def extract_sample_size(text: str) -> str:
    ns = set()
    for pat in _N_PATS:
        for m in pat.finditer(text):
            n = int(m.group(1))
            if 5 <= n <= 99999:
                ns.add(n)
    return "; ".join(str(x) for x in sorted(ns)[:5]) if ns else "NaN"


# ── Toxicity / adverse events ─────────────────────────────────────────────────
_TOX_KW = re.compile(
    r"\b(nausea|vomiting|dizziness|headache|insomnia|fatigue|somnolence|"
    r"weight\s+gain|sexual\s+dysfunction|dry\s+mouth|constipation|"
    r"tremor|seizure|hepatotoxicity|cardiotoxicity|QT\s+prolongation|"
    r"suicidal\s+ideation|self.harm|manic\s+episode|hypomania|"
    r"agranulocytosis|akathisia|tardive\s+dyskinesia|"
    r"serotonin\s+syndrome|discontinuation\s+syndrome|"
    r"orthostatic\s+hypotension|tachycardia|"
    r"discontinued|dropout|drop.out)\b",
    re.I,
)
_TOX_SENT = re.compile(
    r"[^.]*(?:adverse\s+event[s]?|side\s+effect[s]?|toxicit\w+|"
    r"poorly\s+tolerated|discontinued\s+due\s+to)[^.]*\.",
    re.I,
)

def extract_toxicity(text: str) -> str:
    seen, kws = set(), []
    for m in _TOX_KW.finditer(text):
        kw = m.group(0).lower().strip()
        if kw not in seen:
            seen.add(kw)
            kws.append(m.group(0))
    if kws:
        return "; ".join(kws[:8])
    # fallback: grab a sentence containing adverse-event language
    m = _TOX_SENT.search(text)
    return m.group(0).strip()[:150] if m else "NaN"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: QUALITY METRICS
# ══════════════════════════════════════════════════════════════════════════════

def compute_quality(df: pd.DataFrame, elapsed: float) -> list:
    total = len(df)
    lines = []

    def pct(n): return f"{n}/{total} ({100*n//total if total else 0}%)"

    lines += [
        "=" * 70,
        "  CLINICAL TRIAL EXTRACTION — QUALITY METRICS REPORT",
        f"  Input records : {total}",
        f"  Processing    : {elapsed:.1f}s  ({total/elapsed:.0f} rec/s)" if elapsed > 0 else "",
        "=" * 70,
        "",
        "【字段完整率 Field Completeness Rate】",
        f"  {'Field':<22} {'Filled':>10}   {'Rate':>6}",
        f"  {'-'*42}",
    ]

    fields = [
        ("PMID",        "pmid",       lambda df: (df["pmid"] != "NaN") & (df["pmid"] != "")),
        ("NCT号",       "nct",        lambda df: df["nct"] != "NaN"),
        ("药物名称",     "drugs",      lambda df: df["drugs"] != "NaN"),
        ("适应症",       "indication", lambda df: df["indication"] != "NaN"),
        ("剂量",        "dose",       lambda df: df["dose"] != "NaN"),
        ("随访时间",     "followup",   lambda df: df["followup"] != "NaN"),
        ("P值",         "p_values",   lambda df: df["p_values"] != "NaN"),
        ("CI",          "ci",         lambda df: df["ci"] != "NaN"),
        ("OR/RR/HR",    "or_rr_hr",   lambda df: df["or_rr_hr"] != "NaN"),
        ("样本量",       "sample_size",lambda df: df["sample_size"] != "NaN"),
        ("OS",          "os",         lambda df: df["os"] != "NaN"),
        ("PFS",         "pfs",        lambda df: df["pfs"] != "NaN"),
        ("毒性事件",     "toxicity",   lambda df: df["toxicity"] != "NaN"),
        ("摘要结构化",   "is_structured", lambda df: df["is_structured"] == True),
    ]

    for label, col, fn in fields:
        try:
            n = int(fn(df).sum())
            lines.append(f"  {label:<22} {pct(n):>16}")
        except Exception:
            lines.append(f"  {label:<22} {'error':>16}")

    lines += [
        "",
        "【研究目标分布 Study Objective Distribution】",
    ]
    for val in ["效果研究", "机制研究", "其他"]:
        n = int((df["objective"] == val).sum())
        lines.append(f"  {val:<12} {pct(n)}")

    lines += [
        "",
        "【结果分类分布 Outcome Classification Distribution】",
    ]
    for val in ["有效", "无效", "安全", "有毒", "未知"]:
        n = int((df["outcome"] == val).sum())
        lines.append(f"  {val:<8} {pct(n)}")

    lines += [
        "",
        "【年份分布 Year Distribution (top 10)】",
    ]
    try:
        year_counts = df[df["year"] != "NaN"]["year"].value_counts().head(10)
        for yr, cnt in year_counts.items():
            lines.append(f"  {yr}  {cnt}")
    except Exception:
        lines.append("  (unavailable)")

    lines += [
        "",
        "【说明 Notes】",
        "  NCT号  : 本数据集时间跨度1966-2005, 早期文献多无ClinicalTrials.gov注册",
        "  OS/PFS : 主要见于肿瘤学文献, 本抑郁症数据集极少出现",
        "  outcome: 基于摘要关键词语义分类 (非人工标注, 建议抽样验证)",
        "  结构化  : 有BACKGROUND/METHODS/RESULTS标签的摘要, 提取精度更高",
        "=" * 70,
    ]
    return lines


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: PIPELINE ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

def _step1_output_paths(input_file: str, out_dir: Path) -> dict[str, Path]:
    source_name = Path(input_file).stem or "input"
    source_name = source_name.replace(os.path.sep, "_").replace("/", "_")
    timestamp = time.strftime("%y%m%d%H", time.localtime())
    base = f"Step1_{source_name}_{timestamp}"
    return {
        "cleaned": out_dir / f"{base}_cleaned_abstracts.txt",
        "extracted": out_dir / f"{base}_extraction_results.csv",
        "quality": out_dir / f"{base}_quality_metrics.txt",
    }


def _resolve_step1_output_dir(output_dir: str | Path, source_file: str) -> Path:
    output_root = Path(output_dir) if output_dir else Path.home() / "pipeline_output"
    if output_root.name != "pipeline_output":
        output_root = output_root / "pipeline_output"
    source_name = Path(source_file).stem or "input"
    run_dir = output_root / "Step1" / f"step1_run_{source_name}"
    if not output_root.exists():
        output_root.mkdir(parents=True, exist_ok=False)
    step1_dir = output_root / "Step1"
    if not step1_dir.exists():
        step1_dir.mkdir(parents=True, exist_ok=False)
    if not run_dir.exists():
        run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def run_pipeline(input_file, output_dir, max_records, log_fn, progress_fn, done_fn):
    try:
        out = _resolve_step1_output_dir(output_dir, input_file)
        t0 = time.time()
        log_fn(f"  Output directory: {out}")
        outputs = _step1_output_paths(input_file, out)
        f1_path = outputs["cleaned"]
        f2_path = outputs["extracted"]
        f3_path = outputs["quality"]

        # ── Step 1: Parse ────────────────────────────────────────────────────
        log_fn("▶ [1/5] Parsing file…")
        records = parse_file(input_file, max_records)
        total   = len(records)
        log_fn(f"  → {total} records  ({time.time()-t0:.1f}s)")
        if total == 0:
            log_fn("  ⚠ No records found. Check file format.")
            done_fn({})
            return

        # ── Step 2: Clean + segment + File 1 ────────────────────────────────
        log_fn("▶ [2/5] Cleaning & writing cleaned_abstracts.txt…")
        f1_lines  = []
        augmented = []      # (body_clean, sections, is_struct, year)

        for i, rec in enumerate(records):
            body  = clean_text(rec.abstract_clean)
            secs, is_s = segment(body)
            year  = extract_year(rec.journal_line)
            augmented.append((body, secs, is_s, year))

            # ── FILE 1: clean text ─────────────────────────────────────────
            sep = "=" * 68
            f1_lines += [
                sep,
                f"[{rec.index}]  {rec.journal_line}",
                f"PMID: {rec.pmid or 'N/A'}   DOI: {rec.doi or 'N/A'}   Year: {year}",
                "",
                rec.title,
                "",
            ]
            f1_lines += [body, ""]
            f1_lines.append("")
            progress_fn(i+1, total*3)

        f1_path.write_text("\n".join(f1_lines), encoding="utf-8")
        log_fn(f"  → File 1: {f1_path.name}  ({total} records, {f1_path.stat().st_size//1024} KB)")

        # ── Step 3: Full extraction ──────────────────────────────────────────
        log_fn("▶ [3/5] Extracting all fields…")
        rows = []

        for i, (rec, (body, secs, is_s, year)) in enumerate(zip(records, augmented)):
            res_text  = secs.get("results","")
            meth_text = secs.get("methods","")
            full      = body

            # combine title + full for broad search
            broad = rec.title + " " + full

            nct        = extract_nct(broad)
            objective  = classify_objective(full)
            drugs      = extract_drugs(broad)
            indication = extract_indication((rec.title + " " + full[:500]))
            outcome    = classify_outcome(res_text or full)
            dose       = extract_dose(meth_text + " " + full)
            followup   = extract_followup(broad)
            os_v       = extract_os(full)
            pfs_v      = extract_pfs(full)
            pvals      = extract_pvalues(res_text or full)
            ci_v       = extract_ci(res_text or full)
            ratios     = extract_ratios(res_text or full)
            tox        = extract_toxicity(full)
            n_size     = extract_sample_size(full)

            rows.append({
                "index":        rec.index,
                "pmid":         rec.pmid    or "NaN",
                "year":         year,
                "journal":      rec.journal_line[:80],
                "title":        rec.title[:120],
                "doi":          rec.doi     or "NaN",
                "is_structured":is_s,
                "nct":          nct,
                "objective":    objective,
                "drugs":        drugs,
                "indication":   indication,
                "outcome":      outcome,
                "dose":         dose,
                "followup":     followup,
                "os":           os_v,
                "pfs":          pfs_v,
                "p_values":     pvals,
                "ci":           ci_v,
                "or_rr_hr":     ratios,
                "sample_size":  n_size,
                "toxicity":     tox,
                "results_snippet": (res_text or full)[:300],
            })
            progress_fn(total+i+1, total*3)

        # ── Step 4: Write File 2 (CSV) ───────────────────────────────────────
        log_fn("▶ [4/5] Writing extraction_results.csv…")
        df = pd.DataFrame(rows, columns=[
            "index","pmid","year","journal","title","doi","is_structured",
            "nct","objective","drugs","indication","outcome",
            "dose","followup","os","pfs",
            "p_values","ci","or_rr_hr","sample_size","toxicity",
            "results_snippet",
        ])
        df.to_csv(f2_path, index=False, encoding="utf-8-sig")
        log_fn(f"  → File 2: {f2_path.name}  ({len(df)} rows, {f2_path.stat().st_size//1024} KB)")

        # ── Step 5: Write File 3 (quality report) ────────────────────────────
        log_fn("▶ [5/5] Computing quality metrics…")
        elapsed = time.time() - t0
        report  = compute_quality(df, elapsed)
        f3_path.write_text("\n".join(report), encoding="utf-8")
        log_fn(f"  → File 3: {f3_path.name}")

        progress_fn(total*3, total*3)
        log_fn("")
        log_fn("✅  Pipeline complete!")
        log_fn("")

        stats = {
            "total":              total,
            "elapsed_s":          round(elapsed,1),
            "structured":         int(df["is_structured"].sum()),
            "has_drug":           int((df["drugs"]!="NaN").sum()),
            "has_pvalue":         int((df["p_values"]!="NaN").sum()),
            "outcome_effective":  int((df["outcome"]=="有效").sum()),
            "outcome_unknown":    int((df["outcome"]=="未知").sum()),
            "obj_efficacy":       int((df["objective"]=="效果研究").sum()),
        }
        done_fn(stats)

    except Exception as exc:
        import traceback
        log_fn(f"\n❌ Error: {exc}")
        log_fn(traceback.format_exc())
        done_fn({})


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: GUI  (dark research-tool aesthetic)
# ══════════════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Clinical Trial Extraction Pipeline  v2.0")
        self.geometry("980x740")
        self.minsize(750, 560)
        self.configure(bg="#0f1923")
        self._build()

    # ── widget helpers ───────────────────────────────────────────────────────
    def _lf(self, parent, text, **kw):
        return tk.LabelFrame(parent, text=text, bg="#162030",
                             fg="#7eb8d4", font=("Helvetica",9,"bold"),
                             relief=tk.FLAT, bd=1,
                             highlightbackground="#253545",
                             highlightthickness=1, **kw)

    def _entry_row(self, parent, label, varname, cmd, default=""):
        fr = self._lf(parent, label, padx=10, pady=6)
        fr.pack(fill=tk.X, pady=(0,8))
        var = tk.StringVar(value=default)
        setattr(self, varname, var)
        tk.Entry(fr, textvariable=var, font=("Courier",9),
                 bg="#0d1b2a", fg="#d0e8f5",
                 insertbackground="#7eb8d4", relief=tk.FLAT, bd=0,
                 ).grid(row=0, column=0, sticky="ew", ipady=4, padx=(0,8))
        tk.Button(fr, text="Browse…", command=cmd,
                  bg="#1e6fa5", fg="white", font=("Helvetica",9),
                  relief=tk.FLAT, padx=10, pady=3,
                  activebackground="#2a8fc7", cursor="hand2",
                  ).grid(row=0, column=1)
        fr.columnconfigure(0, weight=1)

    # ── layout ───────────────────────────────────────────────────────────────
    def _build(self):
        hdr = tk.Frame(self, bg="#0a1520", pady=14)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="Clinical Trial Extraction Pipeline",
                 font=("Helvetica",16,"bold"), fg="#5bc8f5", bg="#0a1520").pack()
        tk.Label(hdr, text="Parse · Clean · Rule-NER · Classify · Evaluate   v2.0",
                 font=("Helvetica",9), fg="#4a7a99", bg="#0a1520").pack()

        body = tk.Frame(self, bg="#0f1923", padx=20, pady=14)
        body.pack(fill=tk.BOTH, expand=True)

        self._entry_row(body, " 📂  Input file (.txt)",
                        "file_var", self._browse_in)
        self._entry_row(body, " 📁  Output directory",
                        "out_var",  self._browse_out,
                        default=str(Path.home()/"pipeline_output"))

        # options
        opt = self._lf(body, " ⚙️  Options", padx=12, pady=8)
        opt.pack(fill=tk.X, pady=(0,10))
        self.limit_var = tk.BooleanVar(value=True)
        self.limit_n   = tk.IntVar(value=50)
        tk.Checkbutton(opt, text="Process only first",
                       variable=self.limit_var, bg="#162030", fg="#a8c8e0",
                       selectcolor="#0f1923", activebackground="#162030",
                       font=("Helvetica",10),
                       command=self._toggle).grid(row=0, column=0, sticky="w")
        self.spin = tk.Spinbox(opt, from_=10, to=999999, width=9,
                               textvariable=self.limit_n,
                               font=("Helvetica",10), bg="#0d1b2a", fg="#d0e8f5",
                               buttonbackground="#1e6fa5", relief=tk.FLAT)
        self.spin.grid(row=0, column=1, padx=6)
        tk.Label(opt, text="records", bg="#162030", fg="#a8c8e0",
                 font=("Helvetica",10)).grid(row=0, column=2, sticky="w")
        tk.Button(opt, text="Process ALL", command=self._set_all,
                  bg="#1b3d5c", fg="#7eb8d4", font=("Helvetica",9),
                  relief=tk.FLAT, padx=10, pady=2,
                  cursor="hand2").grid(row=0, column=3, padx=(28,0))

        # buttons
        bf = tk.Frame(body, bg="#0f1923")
        bf.pack(fill=tk.X, pady=(0,8))
        self.run_btn = tk.Button(bf, text="▶  Run Pipeline", command=self._start,
                                 bg="#0e7a45", fg="white",
                                 font=("Helvetica",11,"bold"),
                                 relief=tk.FLAT, padx=22, pady=7,
                                 activebackground="#12a05a", cursor="hand2")
        self.run_btn.pack(side=tk.LEFT)
        tk.Button(bf, text="Clear Log", command=self._clear_log,
                  bg="#1e3040", fg="#7eb8d4", font=("Helvetica",9),
                  relief=tk.FLAT, padx=14, pady=7,
                  cursor="hand2").pack(side=tk.RIGHT)

        # progress
        pf = tk.Frame(body, bg="#0f1923")
        pf.pack(fill=tk.X, pady=(0,8))
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("c.Horizontal.TProgressbar",
                        troughcolor="#162030", background="#1e9fd4",
                        thickness=16, bordercolor="#253545")
        self.bar = ttk.Progressbar(pf, style="c.Horizontal.TProgressbar",
                                   mode="determinate")
        self.bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,8))
        self.pct = tk.Label(pf, text=" 0%", bg="#0f1923", fg="#5bc8f5",
                            font=("Courier",10,"bold"), width=5)
        self.pct.pack(side=tk.LEFT)

        # log
        lf = self._lf(body, " 📋  Pipeline Log")
        lf.pack(fill=tk.BOTH, expand=True)
        self.log_w = scrolledtext.ScrolledText(
            lf, font=("Courier",9), bg="#060d15", fg="#9ecfea",
            relief=tk.FLAT, padx=10, pady=8,
            state=tk.DISABLED, insertbackground="white")
        self.log_w.pack(fill=tk.BOTH, expand=True)
        self.log_w.tag_config("ok",    foreground="#2ecc71")
        self.log_w.tag_config("stage", foreground="#5bc8f5")
        self.log_w.tag_config("arrow", foreground="#27ae60")
        self.log_w.tag_config("warn",  foreground="#f39c12")
        self.log_w.tag_config("err",   foreground="#e74c3c")
        self.log_w.tag_config("info",  foreground="#7f8c8d")

        # status
        self.status = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status, bg="#0a1520", fg="#4a7a99",
                 relief=tk.FLAT, anchor=tk.W, padx=12,
                 font=("Helvetica",8)).pack(side=tk.BOTTOM, fill=tk.X, pady=(1,0))

    # ── callbacks ────────────────────────────────────────────────────────────
    def _toggle(self):
        self.spin.config(state=tk.NORMAL if self.limit_var.get() else tk.DISABLED)

    def _set_all(self):
        self.limit_var.set(False)
        self.spin.config(state=tk.DISABLED)

    def _browse_in(self):
        p = filedialog.askopenfilename(title="Select PubMed export .txt",
                                       filetypes=[("Text","*.txt"),("All","*.*")])
        if p:
            self.file_var.set(p)
            self.out_var.set(str(Path(p).parent/"pipeline_output"))

    def _browse_out(self):
        p = filedialog.askdirectory(title="Select output directory")
        if p: self.out_var.set(p)

    def _clear_log(self):
        self.log_w.config(state=tk.NORMAL)
        self.log_w.delete("1.0", tk.END)
        self.log_w.config(state=tk.DISABLED)

    def _log(self, msg: str):
        if   msg.startswith("✅"):   tag = "ok"
        elif msg.startswith("▶"):    tag = "stage"
        elif msg.startswith("  →"):  tag = "arrow"
        elif msg.startswith("⚠"):    tag = "warn"
        elif msg.startswith("❌"):   tag = "err"
        else:                         tag = "info"
        def _w():
            self.log_w.config(state=tk.NORMAL)
            self.log_w.insert(tk.END, msg+"\n", tag)
            self.log_w.see(tk.END)
            self.log_w.config(state=tk.DISABLED)
        self.after(0, _w)

    def _set_bar(self, cur, total):
        def _u():
            p = int(cur/total*100) if total else 0
            self.bar["value"] = p
            self.pct.config(text=f"{p:2d}%")
        self.after(0, _u)

    def _start(self):
        fp = self.file_var.get().strip()
        if not fp or not Path(fp).exists():
            messagebox.showerror("Error","Please select a valid input file."); return
        od = self.out_var.get().strip()
        if not od:
            messagebox.showerror("Error","Please specify an output directory."); return
        max_r = self.limit_n.get() if self.limit_var.get() else 0
        self.run_btn.config(state=tk.DISABLED)
        self.bar["value"] = 0
        self.pct.config(text=" 0%")
        lim = "ALL" if max_r==0 else str(max_r)
        self.status.set(f"⏳ Running…  {Path(fp).name}   limit: {lim}")
        self._log("="*60)
        self._log("Pipeline v2.0 started")
        self._log(f"  Input : {fp}")
        self._log(f"  Output: {od}")
        self._log(f"  Limit : {lim} records")
        self._log("="*60)
        threading.Thread(
            target=run_pipeline,
            args=(fp, od, max_r, self._log, self._set_bar, self._on_done),
            daemon=True,
        ).start()

    def _on_done(self, stats: dict):
        def _u():
            self.run_btn.config(state=tk.NORMAL)
            if stats:
                self.status.set(
                    f"✅ Done  records:{stats.get('total',0)}  "
                    f"structured:{stats.get('structured',0)}  "
                    f"有效:{stats.get('outcome_effective',0)}  "
                    f"效果研究:{stats.get('obj_efficacy',0)}  "
                    f"p值:{stats.get('has_pvalue',0)}  "
                    f"{stats.get('elapsed_s',0)}s"
                )
                self._log("")
                self._log("📊 Summary:")
                for k,v in stats.items():
                    self._log(f"   {k:<28} {v}")
                self._log("")
                self._log("📂 Output files:")
                self._log("   1. cleaned_abstracts.txt   -- 初步清洗文本")
                self._log("   2. extraction_results.csv  -- 完整结构化提取")
                self._log("   3. quality_metrics.txt     -- 提取质量评价报告")
                self.after(300, self._ask_open)
            else:
                self.status.set("❌ Error — see log")
        self.after(0, _u)

    def _ask_open(self):
        od = self.out_var.get()
        if messagebox.askyesno("Done", f"Pipeline complete!\n\nOpen output folder?\n{od}"):
            if sys.platform=="win32":    os.startfile(od)
            elif sys.platform=="darwin":
                import subprocess; subprocess.call(["open",od])
            else:
                import subprocess; subprocess.call(["xdg-open",od])


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    App().mainloop()

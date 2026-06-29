from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Tuple

from arm_normalization import normalize_arm_label as normalize_step2a_arm_label


SCALE_NAME_PATTERN = r"(?:GRID-)?(?:HAM-?D|HDRS|HRSD|MADRS|PHQ-?9|PHQ-?8|BDI(?:-?II)?|CGI(?:-?[SI])?|CSDD|QIDS(?:-SR)?|IDS(?:-SR)?)"
POPULATION_ENTITY_NOUN_PATTERN = (
    r"\b(?:participants?|patients?|subjects?|individuals?|people|persons?|adults?|women|men|boys|girls|children|"
    r"adolescents?|youth|students?|schoolchildren|outpatients?|inpatients?|clients?|consumers?|residents?|"
    r"caregivers?|volunteers?|workers?|employees?|nurses?|teachers?|physicians?|doctors?|mothers?|fathers?|"
    r"couples?|veterans?|undergraduates?|survivors?|soldiers?|families?|infants?|toddlers?)\b"
)
PARTICIPANT_COUNT_NOUN_PATTERN = (
    rf"(?:{POPULATION_ENTITY_NOUN_PATTERN}|completers?)"
)
WRITTEN_NUMBER_PATTERN = (
    r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
    r"eighty|ninety|hundred|thousand)(?:[\s-]+(?:and|one|two|three|four|five|six|seven|eight|"
    r"nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand))*"
)
AGE_SIGNAL_PATTERN = (
    r"\b(?:aged?\s+(?:between\s+)?\d+(?:\.\d+)?|aged?\s*(?:>=|=>|<=|=<|>|<)\s*\d+(?:\.\d+)?(?:\s*years?)?|ages?\s+\d+(?:\.\d+)?|mean age|median age|average age|mage|"
    r"age\s*(?:>=|=>|<=|=<|>|<)?\s*\d+(?:\.\d+)?(?:\s*(?:\+/-|\+-|±)\s*\d+(?:\.\d+)?)?\s*years?|"
    r">=\s*\d+(?:\.\d+)?\s*years?|older than\s+\d+(?:\.\d+)?\s*years?|"
    r"at least\s+\d+(?:\.\d+)?\s*years?\s+old|"
    r"aged?\s+less than\s+\d+(?:\.\d+)?\s*(?:months?|years?)|"
    r"between\s+\d+(?:\.\d+)?\s+and\s+\d+(?:\.\d+)?\s*(?:y|yr|yrs|years?)\s+of age|"
    r"\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*years?|"
    r"\d+(?:\.\d+)?\s*-\s*to\s*\d+(?:\.\d+)?\s*years?|"
    r"\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?-year-olds?|"
    r"\d+(?:\.\d+)?\s*-\s*to\s*\d+(?:\.\d+)?-year-olds?|"
    r"\d+(?:\.\d+)?\s*years?\s+or older|"
    r"\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*weeks?\s+gestation|"
    r"older adults?|young adults?|adolescents?|children|schoolchildren|elderly|geriatric|late-life|"
    r"older\s+(?:patients?|participants?|subjects?|people|individuals?)|"
    r"young\s+(?:patients?|participants?|subjects?|people|individuals?))\b"
)
GENDER_SIGNAL_PATTERN = r"\b(?:male|males|female|females|men|women|boys|girls)\b|\b\d+(?:\.\d+)?%\s*(?:male|female|men|women)\b"
ETHNICITY_SIGNAL_PATTERN = r"\b(?:african[- ]american|black|blacks|white|whites|caucasian|caucasians|asian|asians|pacific islanders?|hispanic|hispanics|latino|latina|latinos|latinas|chinese americans?|chinese han|han chinese|indigenous|native american|multiracial|mixed[- ](?:race|ethnicity))\b"
OCCUPATION_SIGNAL_PATTERN = r"\b(?:students?|schoolchildren|undergraduates?|workers?|employees?|nurses?|teachers?|caregivers?|physicians?|doctors?)\b"
SETTING_SIGNAL_PATTERN = (
    r"\b(?:primary care|out-?patients?|in-?patients?|outpatient clinics?|inpatient units?|community(?: dwelling)?|"
    r"hospital(?:-based)?|admitted for|adult schools?)\b"
)
RELATION_SIGNAL_PATTERN = r"\b(?:healthy controls?|matched healthy controls?|healthy volunteers?|first-degree relatives?)\b"
CLINICAL_POPULATION_CONTEXT_PATTERN = (
    r"\b(?:unmedicated|treatment-resistant|inadequate response|history of [^.;|]{0,50}?episodes?|"
    r"depressed|depressive|non-depressed|comorbid depressive symptoms|acute unipolar|nonpsychotic)\b"
)
PROVIDER_ROLE_PATTERN = (
    r"\b(?:study[- ]?nurses?|nurses?|physicians?|doctors?|psychiatrists?|psychologists?|"
    r"therapists?|pharmacists?|clinicians?|epileptologists?|supervisors?|research assistants?|"
    r"study personnel|occupational physicians?)\b"
)
PROVIDER_CONTEXT_PATTERN = (
    r"\b(?:delivered by|provided by|administered by|treated by|managed by|guided and supported|guided|supported them|"
    r"monitoring data|usual treatment practices|decision aid|audio-recorded sessions|lifestyle counselling|"
    r"health education|intervention group|control group|training|supervisor|services?)\b"
)
SOCIAL_STATUS_SIGNAL_PATTERN = (
    r"\b(?:pregnant|pregnancy|postpartum|perinatal|peri[- ]menopausal|post[- ]menopausal|"
    r"peri[- ]?and\s+post[- ]?menopausal|menopausal|"
    r"hiv(?:/aids)?|hiv[- ]positive|"
    r"refugees?|immigrants?|migrants?|incarcerated|homeless|orphaned|bereaved|divorcees?|new mothers?|help[- ]seeking|"
    r"low[- ]income|poverty|substance use|alcohol use|smokers?|veterans?|active duty|military)\b"
)
TREATMENT_HISTORY_SIGNAL_PATTERN = (
    r"\b(?:treatment[- ]naive|drug[- ]naive|medication[- ]naive|antidepressant[- ]naive|psychotherapy[- ]naive|"
    r"antidepressant[- ]refractory|treatment[- ]refractory|partial responders? to|treatment failure|treatment success|"
    r"unmedicated|hitherto untreated|psychotropic medication[- ]free|"
    r"currently untreated|previously untreated|untreated|"
    r"not currently receiving treatment|not currently in treatment|currently not receiving treatment|"
    r"currently receiving treatment|currently in treatment|"
    r"treatment[- ]free|drug[- ]free|medication[- ]free|antidepressant[- ]free|free of psychotropic medication|off medication|"
    r"no prior (?:treatment|therapy|psychotherapy|antidepressant(?: treatment)?|medication use)|"
    r"no history of (?:treatment|therapy|psychotherapy|antidepressant(?: treatment)?|medication use)|"
    r"prior (?:treatment|therapy|psychotherapy|antidepressant(?: treatment)?|medication use|exposure)|"
    r"history of (?:antidepressant use|psychotherapy|treatment)|"
    r"none of whom were currently receiving treatment|none currently receiving treatment)\b"
)
RISK_SIGNAL_PATTERN = (
    r"\b(?:at risk(?:\s+for)?|high risk(?:\s+for)?|low risk(?:\s+for)?|moderate risk(?:\s+for)?|"
    r"familial risk(?:\s+for)?|individual risk(?:\s+for)?|parental depression|"
    r"subsyndromal symptoms?|clinically relevant depressive symptoms?|elevated depressive symptoms?)\b"
)
SAMPLE_COUNT_PATTERN = (
    rf"\b(?:N\s*=\s*\d{{1,5}}(?:,\d{{3}})*|"
    rf"\d{{1,3}}(?:,\d{{3}})*\s+{PARTICIPANT_COUNT_NOUN_PATTERN}|"
    rf"{WRITTEN_NUMBER_PATTERN}\s+{PARTICIPANT_COUNT_NOUN_PATTERN})\b"
)
RESULT_STAT_PATTERN = r"\b(?:p\s*[<=>]\s*0?\.\d+|95%\s*CI|OR\s*[=:\-]?|RR\s*[=:\-]?|HR\s*[=:\-]?|Cohen d|effect size|mean difference)\b"
RESULT_VERB_PATTERN = r"\b(?:benefit(?:ed|s|ing)?|improv(?:ed|es|ing)|reduc(?:ed|es|ing)|increase(?:d|s|ing)?|decrease(?:d|s|ing)?|respond(?:ed|ers?|ing)|predict(?:ed|s|ing)|odds|versus|vs\.?)\b"


def clean_common_noise(value: Any) -> str:
    text = "" if value is None else str(value)
    text = (
        text.replace("naïve", "naive")
        .replace("naïve", "naive")
        .replace("ï", "i")
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
        .replace("‑", "-")
    )
    text = text.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ;|,-")


def normalize_source_index_value(raw_value: Any) -> str:
    text = clean_common_noise(raw_value)
    if not text:
        return ""
    if text.isdigit():
        return text
    match = re.search(r"\b(\d+)\b", text)
    return match.group(1) if match else text


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


def _clip_text(value: str, limit: int) -> str:
    text = clean_common_noise(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip(" ,;:-") + "..."


def _split_candidate_fragments(*texts: str) -> List[str]:
    fragments: List[str] = []
    for text in texts:
        cleaned = clean_common_noise(text)
        if not cleaned:
            continue
        for fragment in re.split(r"\s*\|\|\s*|(?<=[.;?!])\s+(?=[A-Z0-9])", cleaned):
            value = clean_common_noise(fragment)
            if value:
                fragments.append(value)
    return dedupe_keep_order(fragments)


def _has_population_signal(text: str) -> bool:
    low = clean_common_noise(text).lower()
    if not low:
        return False
    contextual_shape = bool(
        re.search(POPULATION_ENTITY_NOUN_PATTERN, low, flags=re.I)
        and (
            re.search(SETTING_SIGNAL_PATTERN, low, flags=re.I)
            or re.search(RELATION_SIGNAL_PATTERN, low, flags=re.I)
            or re.search(CLINICAL_POPULATION_CONTEXT_PATTERN, low, flags=re.I)
        )
    )
    return bool(
        re.search(AGE_SIGNAL_PATTERN, low, flags=re.I)
        or re.search(GENDER_SIGNAL_PATTERN, low, flags=re.I)
        or re.search(ETHNICITY_SIGNAL_PATTERN, low, flags=re.I)
        or re.search(OCCUPATION_SIGNAL_PATTERN, low, flags=re.I)
        or re.search(SOCIAL_STATUS_SIGNAL_PATTERN, low, flags=re.I)
        or re.search(TREATMENT_HISTORY_SIGNAL_PATTERN, low, flags=re.I)
        or contextual_shape
    )


def has_population_cue(text: str) -> bool:
    return _has_population_signal(text)


def has_severity_cue(text: str) -> bool:
    cleaned = clean_common_noise(text)
    if not cleaned:
        return False
    return bool(
        re.search(r"\b(?:mild|moderate|severe)(?:\s*(?:to|-)\s*(?:moderate|severe))?\b", cleaned, flags=re.I)
        or re.search(rf"\b{SCALE_NAME_PATTERN}\b", cleaned, flags=re.I)
        or re.search(RISK_SIGNAL_PATTERN, cleaned, flags=re.I)
        or re.search(r"\b(?:subthreshold|subsyndromal|residual symptoms?|remitted|partially remitted)\b", cleaned, flags=re.I)
    )


def _strip_leading_sample_count(text: str) -> str:
    cleaned = clean_common_noise(text)
    if not cleaned:
        return ""
    cleaned = re.sub(
        rf"^(?:\(?N\s*=\s*\d{{1,5}}(?:,\d{{3}})*\)?|(?:a total of|of the)\s+\d{{1,5}}(?:,\d{{3}})*|\d{{1,5}}(?:,\d{{3}})*|{WRITTEN_NUMBER_PATTERN})\s+"
        rf"((?:[A-Za-z0-9'/-]+\s+){{0,4}}{POPULATION_ENTITY_NOUN_PATTERN}\b)",
        r"\1",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"^\(?N\s*=\s*\d{1,5}(?:,\d{3})*\)?\s*[:,-]?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^(?:a total of|of the)\s+\d{1,5}(?:,\d{3})*\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(
        rf"^\d{{1,3}}(?:,\d{{3}})*\s+{PARTICIPANT_COUNT_NOUN_PATTERN}\b\s*[:,-]?\s*",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        rf"^(?:a total of|of the)\s+{WRITTEN_NUMBER_PATTERN}\s+{PARTICIPANT_COUNT_NOUN_PATTERN}\b\s*[:,-]?\s*",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        rf"^{WRITTEN_NUMBER_PATTERN}\s+{PARTICIPANT_COUNT_NOUN_PATTERN}\b\s*[:,-]?\s*",
        "",
        cleaned,
        flags=re.I,
    )
    return clean_common_noise(cleaned)


def _clean_population_fragment(fragment: str) -> str:
    text = _strip_leading_sample_count(fragment)
    if not text:
        return ""
    pre_diagnosis_text = text
    strong_start = re.search(
        rf"\b(?:previously untreated|currently untreated|treatment[- ]naive|drug[- ]naive|medication[- ]naive|antidepressant[- ]naive|psychotherapy[- ]naive|"
        rf"aged?\s+(?:between\s+)?\d|mean age|median age|average age|"
        rf"\d+(?:\.\d+)?%\s*(?:female|male|women|men|african[- ]american|black|white|caucasian|asian|hispanic|latino|latina|indigenous|native american|multiracial|mixed[- ](?:race|ethnicity))|"
        rf"(?:pregnant|postpartum|perinatal|orphaned|low[- ]income|older adults?|young adults?|adolescents?|children|schoolchildren|women|men|students?|workers?|caregivers?|veterans?|residents?|clients?|consumers?)\b(?:\s+(?:with|who|aged|from|living|presenting|in)\b)?)",
        text,
        flags=re.I,
    )
    if strong_start and strong_start.start() > 18:
        prefix = text[: strong_start.start()]
        if ":" in prefix or re.search(r"(?:[A-Z][A-Za-z0-9'/-]+(?:\s+[A-Z][A-Za-z0-9'/-]+){3,})", prefix):
            text = text[strong_start.start() :]
    numeric_population_start = re.search(
        rf"\b(?:(?:a total of|of the)\s+)?(?:\d{{1,5}}(?:,\d{{3}})*|{WRITTEN_NUMBER_PATTERN})\s+(?:[A-Za-z0-9'/-]+\s+){{0,4}}{POPULATION_ENTITY_NOUN_PATTERN}\b",
        text,
        flags=re.I,
    )
    if numeric_population_start and numeric_population_start.start() > 18:
        prefix = text[: numeric_population_start.start()]
        if ":" in prefix or re.search(r"(?:[A-Z][A-Za-z0-9'/-]+(?:\s+[A-Z][A-Za-z0-9'/-]+){2,})", prefix):
            text = text[numeric_population_start.start() :]
    text = re.sub(r"^(?:background|objective|objectives|aim|aims|methods?|results?|discussion|interpretation|summary)\s*:\s*", " ", text, flags=re.I)
    text = re.sub(r"\(\s*(?:N|n)\s*=\s*\d{1,5}(?:,\d{3})*\s*\)", " ", text, flags=re.I)
    text = re.sub(r"\b(?:N|n)\s*=\s*\d{1,5}(?:,\d{3})*\b", " ", text, flags=re.I)
    text = re.sub(rf"\b{SCALE_NAME_PATTERN}\b[^|;,.]{{0,80}}", " ", text, flags=re.I)
    text = re.sub(r"\b\d{1,3}(?:,\d{3})*\s+at risk(?:\s+for)?\b[^|;,.]{0,90}", " ", text, flags=re.I)
    text = re.sub(rf"(?:,\s*|and\s+)?{RISK_SIGNAL_PATTERN}[^|;,.]{{0,90}}", " ", text, flags=re.I)
    text = re.sub(r"\b\d{1,3}(?:,\d{3})*\s+completers?\b", " ", text, flags=re.I)
    text = re.sub(r"\bcompleters?\b", " ", text, flags=re.I)
    text = re.sub(
        r"\bmeeting\s+[^.;|]{0,140}?\bcriteria\s+for\s+(?:the\s+diagnosis\s+of\s+)?(?:major depressive disorder|mdd|depression|depressive symptoms?|unipolar depressive disorder)\b",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\b(?:with|having)\s+(?:a\s+)?(?:primary\s+|current\s+)?diagnosis\s+of\s+(?:major depressive disorder|mdd|depression|depressive symptoms?|unipolar depressive disorder)\b",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\bdiagnosed with\s+(?:major depressive disorder|mdd|depression|depressive symptoms?|unipolar depressive disorder)\b(?=$|[.;|,)])",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\bwith\s+(?P<prefix>(?:postpartum|perinatal|pregnant)\s+)?(?:major depressive disorder|mdd|depression|depressive symptoms?|unipolar depressive disorder)\b(?=$|[.;|,)])",
        lambda match: match.group("prefix") or " ",
        text,
        flags=re.I,
    )
    text = re.sub(r"\bwith\s+significant levels? of [^,.;|]{0,80}\b", " ", text, flags=re.I)
    text = re.sub(r"\bbased on clinically elevated scores on [^,.;|]{0,80}\b", " ", text, flags=re.I)
    text = re.sub(
        r"^(?:recruited|eligible)\s+(?:patients?|participants?|subjects?)\s+fulfilled the following inclusion criteria:\s*",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(r"\bfulfilled the following inclusion criteria:\s*", " ", text, flags=re.I)
    text = re.sub(r"\b(?:that|who)\s+met\s+the\s+inclusion criteria\b", " ", text, flags=re.I)
    text = re.sub(r"\bwho consented to the (?:trial|study)\b", " ", text, flags=re.I)
    text = re.sub(r"\bconsented to participate\b", " ", text, flags=re.I)
    text = re.sub(r"^\b(?:participants?|patients?|subjects?|individuals?|people|clients?|consumers?)\s+were\s+", "", text, flags=re.I)
    text = re.sub(r"^\bat\s+\d+(?:\.\d+)?\s*(?:day|days|week|weeks|month|months|year|years)\b[^,;:.]{0,20}[:,]?\s*", " ", text, flags=re.I)
    text = re.sub(r"\bfollowing acute dose\b[^.;|]{0,140}$", " ", text, flags=re.I)
    text = re.sub(r"\bby defining\b[^.;|]{0,140}$", " ", text, flags=re.I)
    text = re.sub(r"\b(?:and|to)\s+(?:provide|offer)\s+(?:a\s+)?(?:scientific\s+)?basis\b[^.;|]{0,160}$", " ", text, flags=re.I)
    text = re.sub(r"\b(?:guided and supported|supported)\s+them\b[^.;|]{0,120}$", " ", text, flags=re.I)
    text = re.sub(r"\bmanaged by (?:their|the) physician\b[^.;|]{0,140}$", " ", text, flags=re.I)
    text = re.sub(r"\bwere followed up to\b[^.;|]{0,80}$", " ", text, flags=re.I)
    text = re.sub(r"\b(?:compare[sd]?|comparing)\s+[^.;|]{0,40}\buntreated controls?\b[^.;|]{0,140}$", " ", text, flags=re.I)
    text = re.sub(r"\bin the original study\b[^.;|]{0,160}$", " ", text, flags=re.I)
    text = re.sub(r"\bparticipated(?: within)?(?: this study)?\b[^.;|]{0,160}$", " ", text, flags=re.I)
    text = re.sub(r"\brecruited through\b[^.;|]{0,120}$", " ", text, flags=re.I)
    text = re.sub(r"\bcompleted one of [^.;|]{0,120} trials?\b[^.;|]{0,120}$", " ", text, flags=re.I)
    text = re.sub(r"\b(?:were provided with|were asked to)\b[^.;|]{0,180}$", " ", text, flags=re.I)
    text = re.sub(r"\b(?:our team|we)\s+(?:developed|designed)\b[^.;|]{0,180}$", " ", text, flags=re.I)
    text = re.sub(r"\bpreliminarily\s+(?:examine|evaluate|assess)\b[^.;|]{0,180}$", " ", text, flags=re.I)
    text = re.sub(r"\bin our hospital who needed\b[^.;|]{0,140}$", " ", text, flags=re.I)
    text = re.sub(r"\bconvenience sample population\b", "patients", text, flags=re.I)
    text = re.sub(r"\bshortening waiting lists\b[^.;|]{0,160}$", " ", text, flags=re.I)
    text = re.sub(r"\bstudy[- ]?nurse\b[^.;|]{0,140}$", " ", text, flags=re.I)
    text = re.sub(r"\b(?:community|patients?|participants?|subjects?|youth|women|men|students?)\s+recruited\s+(?:from|at)\s+", lambda m: m.group(0).split()[0] + " ", text, flags=re.I)
    text = re.sub(r"\benrolled\s+(patients?|participants?|subjects?|students?)\b", r"\1", text, flags=re.I)
    text = re.sub(rf"\b((?:[A-Za-z0-9'/-]+\s+){{0,2}}{POPULATION_ENTITY_NOUN_PATTERN})\s+enrolled\s+in\b", r"\1 in", text, flags=re.I)
    text = re.sub(r"\bstudents?\s+enrolled\s+in\b", "students in ", text, flags=re.I)
    text = re.sub(r"\b(?:at|from)\s+(?:two\s+)?Department of Veteran Affairs medical centers?\b[^.;|]{0,120}$", " ", text, flags=re.I)
    text = re.sub(
        r"\b(?:at|from)\s+(?![^.;|]{0,40}\b(?:outpatient|inpatient|community|primary care|hospital-based)\b)[^.;|]{0,80}(?:medical centers?|hospital|hospitals|university|universities|clinic|clinics|sites?)\b[^.;|]{0,80}$",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(r"\bat trial baseline\b[^.;|]{0,60}$", " ", text, flags=re.I)
    text = re.sub(r"\bfor a treatment study\b[^.;|]{0,60}$", " ", text, flags=re.I)
    text = re.sub(r"\bpresenting for a treatment study\b[^.;|]{0,60}$", " ", text, flags=re.I)
    text = re.sub(r"\battended their assigned program\b[^.;|]{0,80}$", " ", text, flags=re.I)
    text = re.sub(r"\b(?:the study|this study|current study)\b[^.;|]{0,180}[.;]?$", " ", text, flags=re.I)
    text = re.sub(r"\b(?:were|was)\s+(?:recruited|enrolled|included|selected|invited|randomi[sz]ed|allocated|assigned)\b[^.;|]{0,220}[.;]?$", " ", text, flags=re.I)
    text = re.sub(r"\b(?:completed|underwent|received|withdrew|participated in|took part in)\b[^.;|]{0,220}[.;]?$", " ", text, flags=re.I)
    text = re.sub(r"\b(?:for|into|in)\s+the\s+(?:study|trial)\b[^.;|]{0,140}[.;]?$", " ", text, flags=re.I)
    text = re.sub(r"[()]", " ", text)
    text = re.sub(r"\(\s*\)", " ", text)
    text = re.sub(r"\]\s*$", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?:,\s*|\s+)(?:and|or)\s+(?:at|with|who|from|in)\s*$", " ", text, flags=re.I)
    text = re.sub(r"^(?:with|and|or|among|for)\b\s*", "", text, flags=re.I)
    text = re.sub(r"\bwith\s+(?:a|an|the|no|any|some)\b\s*$", " ", text, flags=re.I)
    text = re.sub(r"\bwho\s+(?:w|wa|we|ha|had|was|were)\b\s*$", " ", text, flags=re.I)
    text = re.sub(r"\bpresenting\b\s*$", " ", text, flags=re.I)
    text = re.sub(r"\b(?:with|and|or|who|having|none of whom)\b\s*$", "", text, flags=re.I)
    cleaned = clean_common_noise(text)
    if re.fullmatch(r"(?:adults?|adult|women|men|patients?|participants?|subjects?|outpatients?|inpatients?)", cleaned, flags=re.I):
        if re.search(r"\b(?:diagnosed with|with)\s+(?:major depressive disorder|mdd|depression|depressive symptoms?|unipolar depressive disorder)\b", pre_diagnosis_text, flags=re.I):
            return clean_common_noise(pre_diagnosis_text)
    return cleaned


def _looks_like_contextful_population_phrase(text: str) -> bool:
    cleaned = clean_common_noise(text)
    if not cleaned:
        return False
    if not re.search(POPULATION_ENTITY_NOUN_PATTERN, cleaned, flags=re.I):
        return False
    if re.search(r"\b(?:study|trial|randomi[sz]ed|double-blind|placebo-controlled|study protocol|trial protocol|data from|results? from)\b", cleaned, flags=re.I):
        return False
    return bool(
        re.search(
            r"\b(?:with|who|from|in|suffering from|exposed to|presenting|meeting|diagnosed with|history of|admitted for|admitted to|on hemodialysis|working in|remitted from|experiencing|lasting|partial responders? to)\b",
            cleaned,
            flags=re.I,
        )
    )


def _looks_useful_population_fragment(text: str) -> bool:
    cleaned = clean_common_noise(text)
    if not cleaned:
        return False
    low = cleaned.lower()
    if _looks_like_population_purpose_fragment(cleaned):
        return False
    if re.fullmatch(r"(?:adults?|women|men|children|adolescents?|older adults?|young adults?|infants?|toddlers?)", low):
        return True
    if re.fullmatch(
        r"(?:[A-Za-z][A-Za-z'/-]*\s+){0,3}(?:adults?|women|men|children|adolescents?|students?|workers?|employees?|"
        r"veterans?|caregivers?|volunteers?|outpatients?|inpatients?|undergraduates?|survivors?|soldiers?|families?|infants?|toddlers?)",
        cleaned,
        flags=re.I,
    ) and not re.search(r"\b(?:depression|depressive|disorder|mdd|cancer|epilepsy|diabetes|fracture)\b", low):
        return True
    if re.fullmatch(r"(?:[A-Za-z][A-Za-z'/-]*\s+){0,2}survivors?", cleaned, flags=re.I):
        return True
    if not _has_population_signal(cleaned):
        if _looks_like_contextful_population_phrase(cleaned):
            pass
        else:
            return False
    if re.search(SAMPLE_COUNT_PATTERN, cleaned, flags=re.I):
        return False
    if re.search(rf"\b{SCALE_NAME_PATTERN}\b", cleaned, flags=re.I):
        return False
    if re.search(RISK_SIGNAL_PATTERN, cleaned, flags=re.I):
        return False
    if re.search(RESULT_VERB_PATTERN, cleaned, flags=re.I):
        return False
    if re.search(r"\b(?:delivered by|administered by|provided by)\b", cleaned, flags=re.I):
        return False
    if re.fullmatch(PROVIDER_ROLE_PATTERN, cleaned, flags=re.I):
        return False
    if re.search(r"\b(?:veterans affairs|department of veteran affairs)\b", cleaned, flags=re.I):
        return False
    if re.search(PROVIDER_ROLE_PATTERN, cleaned, flags=re.I) and re.search(
        PROVIDER_CONTEXT_PATTERN,
        cleaned,
        flags=re.I,
    ):
        return False
    if re.fullmatch(TREATMENT_HISTORY_SIGNAL_PATTERN, cleaned, flags=re.I):
        if low in {
            "untreated",
            "currently untreated",
            "currently receiving treatment",
            "currently in treatment",
            "treatment-free",
            "drug-free",
            "medication-free",
            "antidepressant-free",
            "off medication",
        }:
            return False
    if re.search(TREATMENT_HISTORY_SIGNAL_PATTERN, cleaned, flags=re.I) and not re.search(
        POPULATION_ENTITY_NOUN_PATTERN, cleaned, flags=re.I
    ):
        if low not in {
            "previously untreated",
            "treatment-naive",
            "drug-naive",
            "medication-naive",
            "antidepressant-naive",
            "psychotherapy-naive",
            "unmedicated",
            "hitherto untreated",
            "none of whom were currently receiving treatment",
        }:
            return False
    if low in {"medication free", "medication-free", "prior treatment", "history of treatment"}:
        return False
    if low in {"mixed", "alcohol use", "substance use"}:
        return False
    if low in {"depression", "major depressive disorder", "mdd"}:
        return False
    return True


def _looks_like_population_purpose_fragment(text: str) -> bool:
    cleaned = clean_common_noise(text).lower()
    if not cleaned:
        return False
    patterns = [
        r"^(?:background|objective|objectives|aim|aims|methods?|design|setting|summary|interpretation)\b",
        r"\bthis study aims?\b",
        r"\bwe aim(?:ed)?\b",
        r"\bthe aim(?:s|ed)?\b",
        r"\bobjective(?: was|s)? to\b",
        r"\bto assess\b",
        r"\bto evaluate\b",
        r"\bto test\b",
        r"\bto compare\b",
        r"\bto determine whether\b",
        r"\beffects? of\b",
        r"\befficacy of\b",
        r"\bbenefits? of\b",
        r"\beffectiveness\b",
        r"\bpredictors? of\b",
        r"\bthe role of\b",
        r"\buse of\b",
        r"\bresults? from\b",
        r"\bpilot study\b",
        r"\bsecondary analysis\b",
        r"\bmoderator analysis\b",
        r"\bthe present study\b",
        r"\bthis paper\b",
        r"\bthis study assessed whether\b",
        r"\bthis study examined whether\b",
        r"\bthis study examined\b",
        r"\bcurrent study\b",
        r"\btreatment study\b",
        r"\bpresenting for a treatment study\b",
        r"\bhas presently enrolled\b",
        r"\bfulfilled the following inclusion criteria\b",
        r"\bguided by the health belief model\b",
        r"\bthis study provided\b",
        r"\bour team\s+(?:developed|designed)\b",
        r"\bpreliminarily\s+(?:examine|evaluate|assess)\b",
        r"\bto offer a scientific basis\b",
        r"\bfollowing acute dose\b",
        r"\bby defining\b",
        r"\bguided and supported them\b",
        r"\bmanaged by their physician\b",
        r"\bwere followed up to\b",
        r"\benrolled with\b",
        r"\bin a validated [^.;|]{0,100} program\b",
        r"\bin our hospital who needed\b",
        r"\bphysician services\b",
        r"\bstudy-nurse\b",
        r"\bin the original study\b",
        r"\bparticipated within this study\b",
        r"\bshortening waiting lists\b",
        r"\bpotentially reach untreated patients\b",
        r"\breassessed\b",
        r"\bwe (?:used|investigated|examined|assessed|evaluated|analyzed|conducted|compared|collected|invited|identified)\b",
        r"\bthe statistical population consisted\b",
        r"\bwere recruited into the study\b",
        r"\bwere enrolled in the study\b",
        r"\bwere randomly assigned\b",
        r"\bdelivered by\b",
        r"\black of clinical trials\b",
        r"\bcan help manage\b",
        r"\bintervention group\b",
        r"\bcontrol group\b",
        r"\brandomi[sz]ed\b",
        r"\brandomi[sz]ed controlled trial\b",
        r"\bclinical trial\b",
        r"\bdouble-blind\b",
        r"\bplacebo-controlled\b",
        r"\bproof-of-concept trial\b",
        r"\bnon-inferiority study\b",
        r"\bwait-list\b",
        r"\bmultisite\b",
        r"\bexploratory re-analysis\b",
    ]
    return any(re.search(pattern, cleaned, flags=re.I) for pattern in patterns)


def _extract_population_signal_snippets(text: str) -> List[str]:
    cleaned = clean_common_noise(text)
    if not cleaned:
        return []
    patterns = [
        rf"\b(?:pregnant|postpartum|perinatal|peri[- ]menopausal|post[- ]menopausal|orphaned|homeless|incarcerated|low[- ]income|hiv(?:/aids)?|hiv[- ]positive)\s+(?:[A-Za-z0-9'/-]+\s+){{0,3}}{POPULATION_ENTITY_NOUN_PATTERN}\b[^.;|]{{0,80}}",
        rf"\b(?:predominantly\s+)?(?:african[- ]american|black|white|caucasian|asian|hispanic|latino|latina|indigenous|native american|multiracial|mixed[- ](?:race|ethnicity))(?:\s+[A-Za-z0-9'/-]+){{0,3}}\s+{POPULATION_ENTITY_NOUN_PATTERN}\b[^.;|]{{0,60}}",
        rf"\b(?:patients?|participants?|subjects?|individuals?)\s+of\s+(?:Chinese Han|Han Chinese)\s+ethnicity\b[^.;|]{{0,40}}",
        r"\b(?:muslim|peri[- ]and\s+post[- ]menopausal|peri[- ]menopausal|post[- ]menopausal)\s+(?:women|men|adults?|adolescents?|children)\b[^.;|]{0,40}",
        r"\bnew mothers?\b[^.;|]{0,40}",
        r"\b(?:university|college|secondary school|high school)\s+students?\b",
        r"\bundergraduates?\b[^.;|]{0,60}",
        r"\bhelp[- ]seeking\s+\d+(?:\.\d+)?\s*-\s*to\s*\d+(?:\.\d+)?-year-olds?\b[^.;|]{0,40}",
        r"\b(?:[A-Za-z0-9'/-]+\s+){0,2}survivors?\b(?:\s+(?:with|who|from|of)\b[^.;|]{0,70})?",
        r"\b(?:[A-Za-z0-9'/-]+\s+){0,2}residents?\s+of\b[^.;|]{0,70}",
        rf"\b(?:eligible\s+)?{POPULATION_ENTITY_NOUN_PATTERN}\s+(?:presenting|with|who|aged|living|from)\b[^.;|]{{0,80}}",
        rf"\b(?:healthy|matched healthy|non-depressed|depressed|depressive|unmedicated|treatment-resistant|primary care|community dwelling|chinese|french|latinos?|latinas?|first-degree)\s+(?:[A-Za-z0-9'/-]+\s+){{0,4}}{POPULATION_ENTITY_NOUN_PATTERN}\b[^.;|]{{0,80}}",
        rf"\b(?:untreated|currently untreated|previously untreated|treatment[- ]naive|drug[- ]naive|medication[- ]naive|antidepressant[- ]naive|psychotherapy[- ]naive)\s+(?:[A-Za-z0-9'/-]+\s+){{0,4}}{POPULATION_ENTITY_NOUN_PATTERN}\b[^.;|]{{0,60}}",
        rf"\b(?:[A-Za-z0-9'/-]+\s+){{0,4}}{POPULATION_ENTITY_NOUN_PATTERN}\s+(?:with\s+)?(?:no prior (?:treatment|therapy|psychotherapy|antidepressant(?: treatment)?|medication use)|not currently receiving treatment|currently untreated|previously untreated|currently receiving treatment|currently in treatment|treatment[- ]free|drug[- ]free|medication[- ]free|antidepressant[- ]free|free of psychotropic medication|off medication)\b[^,.;|]{{0,60}}",
        r"\bnone of whom were currently receiving treatment\b",
        rf"\b{POPULATION_ENTITY_NOUN_PATTERN}\s+(?:admitted for|with inadequate response to|with a history of|in outpatient clinics?|receiving multimodal inpatient psychotherapy)\b[^.;|]{{0,90}}",
        r"\bhealthy controls?\b[^.;|]{0,40}",
        r"\bfirst-degree relatives?\b[^.;|]{0,60}",
        rf"\b{POPULATION_ENTITY_NOUN_PATTERN}\s+\(?(?:aged?|ages?)\s+[^.;|]{{0,80}}",
        rf"\b{POPULATION_ENTITY_NOUN_PATTERN}\s+\(?\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*years?\)?[^.;|]{{0,40}}",
        rf"\b{POPULATION_ENTITY_NOUN_PATTERN}\s+[^.;|]{{0,20}}\b(?:mean|median|average) age[^.;|]{{0,30}}",
        rf"\b{POPULATION_ENTITY_NOUN_PATTERN}\s+[^.;|]{{0,20}}\bmage\b[^.;|]{{0,30}}",
        rf"\b{POPULATION_ENTITY_NOUN_PATTERN}\s+(?:living in|residing in|from|in)\s+[^.;|]{{0,60}}",
        r"\baged?\s*(?:>=|=>|<=|=<|>|<)\s*\d+(?:\.\d+)?(?:\s*years?)?\b",
        r"\b(?:aged?|ages?)\s+(?:between\s+)?\d+(?:\.\d+)?(?:\s*(?:-|to|and)\s*\d+(?:\.\d+)?)?\s*years?\b(?:\s+or older)?",
        r"\b(?:mean age|mage|age)[^\d]{0,12}\d+(?:\.\d+)?(?:\s*(?:\+/-|±)\s*\d+(?:\.\d+)?)?\b",
        r"\bmedian age[^\d]{0,12}\d+(?:\.\d+)?\b",
        r"\bage\s*(?:>=|=>|<=|=<|>|<)\s*\d+(?:\.\d+)?\s*years?\b",
        r"\bat least\s+\d+(?:\.\d+)?\s*years?\s+old\b",
        r"\baged?\s+less than\s+\d+(?:\.\d+)?\s*(?:months?|years?)\b",
        r"\bbetween\s+\d+(?:\.\d+)?\s+and\s+\d+(?:\.\d+)?\s*(?:y|yr|yrs|years?)\s+of age\b",
        r"\b>=\s*\d+(?:\.\d+)?\s*years?\b",
        r"\bolder than\s+\d+(?:\.\d+)?\s*years?\b",
        r"\b\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?-year-olds?\b",
        r"\b\d+(?:\.\d+)?\s*-\s*to\s*\d+(?:\.\d+)?-year-olds?\b",
        r"\b\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*weeks?\s+gestation\b",
        r"\b\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*years?\b",
        r"\b\d+(?:\.\d+)?\s*(?:\+/-|\+-|±)\s*\d+(?:\.\d+)?\s*years\b",
        r"\b\d+(?:\.\d+)?%\s*(?:female|male|women|men)\b",
        GENDER_SIGNAL_PATTERN,
        r"\b\d+(?:\.\d+)?%\s*(?:african[- ]american|black|white|caucasian|asian|hispanic|latino|latina|indigenous|native american|multiracial|mixed[- ](?:race|ethnicity))\b",
        ETHNICITY_SIGNAL_PATTERN,
        OCCUPATION_SIGNAL_PATTERN,
        SOCIAL_STATUS_SIGNAL_PATTERN,
        TREATMENT_HISTORY_SIGNAL_PATTERN,
        r"\bolder adults?\b|\byoung adults?\b|\badolescents?\b|\bchildren\b|\bschoolchildren\b|\belderly\b|\bgeriatric\b",
    ]
    hits: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, cleaned, flags=re.I):
            window = cleaned[max(0, match.start() - 60) : min(len(cleaned), match.end() + 60)]
            hit = clean_common_noise(match.group(0))
            if hit:
                if re.search(OCCUPATION_SIGNAL_PATTERN, hit, flags=re.I) and re.search(
                    rf"(?:{PROVIDER_CONTEXT_PATTERN}|\btherapists?\b|\bpsychiatrist services?\b)",
                    window,
                    flags=re.I,
                ):
                    continue
                if re.search(TREATMENT_HISTORY_SIGNAL_PATTERN, hit, flags=re.I) and re.search(
                    r"\b(?:potentially reach|shortening waiting lists|could increase the efficacy)\b",
                    window,
                    flags=re.I,
                ):
                    continue
                if re.fullmatch(PROVIDER_ROLE_PATTERN, hit, flags=re.I):
                    continue
                hits.append(hit)
    return dedupe_keep_order(hits)


def _append_population_fragment(fragments: List[str], candidate: str) -> None:
    value = clean_common_noise(candidate)
    if not value:
        return
    key = value.lower()
    for index, existing in enumerate(list(fragments)):
        existing_key = existing.lower()
        if key == existing_key or re.search(rf"(?<![A-Za-z0-9]){re.escape(key)}(?![A-Za-z0-9])", existing_key):
            return
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(existing_key)}(?![A-Za-z0-9])", key):
            fragments[index] = value
            return
    fragments.append(value)


def _population_fragment_score(text: str) -> int:
    cleaned = clean_common_noise(text)
    if not cleaned:
        return -999
    score = 0
    if re.search(r"\b(?:mean age|median age|average age|aged?\s+(?:between\s+)?\d|\d+(?:\.\d+)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*years?|\d+(?:\.\d+)?\s*years?\s+or older)\b", cleaned, flags=re.I):
        score += 5
    elif re.search(r"\b(?:older adults?|young adults?|adolescents?|children|schoolchildren|elderly|geriatric|late-life)\b", cleaned, flags=re.I):
        score += 2
    if re.search(GENDER_SIGNAL_PATTERN, cleaned, flags=re.I):
        score += 4
    if re.search(ETHNICITY_SIGNAL_PATTERN, cleaned, flags=re.I):
        score += 4
    if re.search(OCCUPATION_SIGNAL_PATTERN, cleaned, flags=re.I):
        score += 3
    if re.search(SOCIAL_STATUS_SIGNAL_PATTERN, cleaned, flags=re.I):
        score += 3
    if re.search(TREATMENT_HISTORY_SIGNAL_PATTERN, cleaned, flags=re.I):
        score += 3
    if re.search(SETTING_SIGNAL_PATTERN, cleaned, flags=re.I):
        score += 2
    if re.search(RELATION_SIGNAL_PATTERN, cleaned, flags=re.I):
        score += 2
    if re.search(CLINICAL_POPULATION_CONTEXT_PATTERN, cleaned, flags=re.I):
        score += 1
    if re.search(r"\b(?:county|school|clinic|hospital|community|veterans?)\b", cleaned, flags=re.I):
        score += 1
    if re.search(r"\b(?:clinically referred|participating|eligible|study|trial)\b", cleaned, flags=re.I):
        score -= 2
    if re.fullmatch(r"(?:mixed|multiracial)", cleaned, flags=re.I):
        score -= 2
    return score


def _population_fragment_needs_context_support(text: str) -> bool:
    cleaned = clean_common_noise(text)
    if not cleaned:
        return True
    if re.fullmatch(
        r"(?:adults?|older adults?|young adults?|elderly|outpatients?|inpatients?|patients?|participants?|subjects?|"
        r"treatment-naive|drug-naive|medication-naive|antidepressant-naive|psychotherapy-naive|"
        r"previously untreated|currently untreated|treatment-free|drug-free|medication-free|antidepressant-free)",
        cleaned,
        flags=re.I,
    ):
        return True
    if len(cleaned) <= 18 and re.search(
        r"\b(?:adults?|older adults?|young adults?|elderly|outpatients?|inpatients?|patients?|participants?|subjects?|"
        r"treatment[- ]naive|drug[- ]naive|medication[- ]naive|antidepressant[- ]naive|psychotherapy[- ]naive|"
        r"previously untreated|currently untreated)\b",
        cleaned,
        flags=re.I,
    ):
        return True
    return False


def _is_generic_population_fragment(text: str) -> bool:
    cleaned = clean_common_noise(text)
    if not cleaned:
        return True
    return bool(
        re.fullmatch(
            r"(?:adults?|adult|older adults?|older patients?|young adults?|elderly|participants?|patients?|subjects?|"
            r"women|men|boys|girls|adolescents?|children|outpatients?|inpatients?|workers?|employees?|students?|veterans?)",
            cleaned,
            flags=re.I,
        )
    )


def extract_follow_up_time_from_text(*texts: str) -> str:
    merged = " ".join(clean_common_noise(text) for text in texts if text).strip()
    if not merged:
        return ""

    duration = r"\d+(?:\.\d+)?(?:\s*(?:to|-)\s*\d+(?:\.\d+)?)?\s*(?:-| )?\s*(?:day|days|week|weeks|month|months|year|years)"
    patterns = [
        rf"\bfollow[- ]?up(?:\s*(?:period|duration|time))?\s*(?:of|for|at|was|is|:)?\s*({duration})\b",
        rf"\b({duration})\s*(?:of\s*)?follow[- ]?up\b",
        rf"\bfollowed\s+(?:participants|patients|subjects)?\s*(?:for)?\s*({duration})\b",
        rf"\bpost[- ]?(?:treatment|intervention)\s*(?:follow[- ]?up)?\s*(?:at|of|for)?\s*({duration})\b",
        rf"\b({duration})\s*post[- ]?(?:treatment|intervention)\b",
    ]

    hits: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, merged, flags=re.I):
            value = clean_common_noise(match.group(1)).strip(" ,;.")
            if value and value.lower() not in {item.lower() for item in hits}:
                hits.append(value)
            if len(hits) >= 2:
                break
        if len(hits) >= 2:
            break
    return "; ".join(hits)


def _normalize_count_text(value: str) -> str:
    digits = re.sub(r"[^\d]", "", value or "")
    return str(int(digits)) if digits else ""


def _extract_simple_sample_size(text: str) -> str:
    cleaned = clean_common_noise(text)
    if not cleaned:
        return ""
    if re.fullmatch(r"\d{1,5}(?:,\d{3})*", cleaned):
        return _normalize_count_text(cleaned)
    simple_patterns = [
        r"^(?:n|N)\s*=\s*(\d{1,5}(?:,\d{3})*)$",
        r"^(\d{1,5}(?:,\d{3})*)\s*(?:participants|patients|subjects|adults|women|men|children|adolescents|individuals)\b",
        r"^(?:included|enrolled|recruited|randomi[sz]ed)\s+(\d{1,5}(?:,\d{3})*)\b",
    ]
    for pattern in simple_patterns:
        match = re.search(pattern, cleaned, flags=re.I)
        if match:
            return _normalize_count_text(match.group(1))
    return ""


def _extract_total_from_arm_breakdown(text: str) -> str:
    cleaned = clean_common_noise(text)
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if any(token in lowered for token in ["completed", "completion", "retested", "healthy", "depressed", "remitted", "non-remitted", "cohort", "replication", "follow", "year", "month", "week", "day", "/"]):
        return ""
    counts = re.findall(r"\bn\s*=\s*(\d{1,5}(?:,\d{3})*)\b", cleaned, flags=re.I)
    if not (2 <= len(counts) <= 4):
        return ""
    total = sum(int(_normalize_count_text(value)) for value in counts if _normalize_count_text(value))
    return str(total) if total > 0 else ""


def _row_allows_total_sample_size_context_fallback(raw_row: Dict[str, Any]) -> bool:
    intervention = clean_common_noise(raw_row.get("intervention", "")).lower()
    comparator = clean_common_noise(raw_row.get("comparator", "")).lower()
    evidence = clean_common_noise(raw_row.get("evidence_snippet", "")).lower()
    if intervention and comparator and intervention != comparator:
        return False
    if comparator and any(token in evidence for token in [" versus ", " vs ", " compared with ", " compared to "]):
        return False
    return True


def normalize_sample_size(raw_text: str, context_text: str = "", allow_aggregate_fallback: bool = True) -> str:
    raw = clean_common_noise(raw_text)
    if raw:
        simple = _extract_simple_sample_size(raw)
        if simple:
            return simple
        total_from_breakdown = _extract_total_from_arm_breakdown(raw) if allow_aggregate_fallback else ""
        if total_from_breakdown:
            return total_from_breakdown

    context = clean_common_noise(context_text)
    if not context or not allow_aggregate_fallback:
        return ""
    patterns = [
        r"\btotal\s+(?:sample|participants?|patients?|subjects?)\s*(?:size)?\s*[:=]?\s*(\d{1,5}(?:,\d{3})*)\b",
        r"\b(?:n|N)\s*=\s*(\d{1,5}(?:,\d{3})*)\b",
        r"\b(\d{2,5}(?:,\d{3})*)\s+(?:participants|patients|subjects|adults|women|men|children|adolescents|individuals)\b",
        r"\b(?:included|enrolled|recruited|randomi[sz]ed)\s+(\d{2,5}(?:,\d{3})*)\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, context, flags=re.I):
            window = clean_common_noise(context[max(0, match.start() - 30) : min(len(context), match.end() + 40)])
            if any(token in window.lower() for token in ["completed", "completion", "retested", "healthy", "depressed", "remitted", "non-remitted", "follow-up", "followed-up"]):
                continue
            if re.search(r"\d\s*/\s*\d", window):
                continue
            return _normalize_count_text(match.group(1))
    return ""


def _duration_to_days(amount_text: str, unit: str) -> float:
    try:
        if "-" in amount_text:
            end_value = amount_text.split("-")[-1].strip()
            amount = float(end_value)
        else:
            amount = float(amount_text)
    except Exception:
        return -1.0
    lowered_unit = unit.lower()
    if lowered_unit.startswith("day"):
        return amount
    if lowered_unit.startswith("week"):
        return amount * 7
    if lowered_unit.startswith("month"):
        return amount * 30
    if lowered_unit.startswith("year"):
        return amount * 365
    return -1.0


def _normalize_duration_label(raw_text: str) -> str:
    cleaned = clean_common_noise(raw_text)
    word_numbers = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "ten": "10",
        "eleven": "11",
        "twelve": "12",
    }
    for word, digit in word_numbers.items():
        cleaned = re.sub(rf"\b{word}\b", digit, cleaned, flags=re.I)
    match = re.search(
        r"\b(\d+(?:\.\d+)?(?:\s*(?:to|-)\s*\d+(?:\.\d+)?)?)\s*(?:-| )?\s*(day|days|week|weeks|month|months|year|years)\b",
        cleaned,
        flags=re.I,
    )
    if not match:
        return ""
    amount = clean_common_noise(match.group(1)).replace(" to ", "-")
    unit = match.group(2).lower()
    singular = {"days": "day", "weeks": "week", "months": "month", "years": "year"}
    plural = {"day": "days", "week": "weeks", "month": "months", "year": "years"}
    if re.fullmatch(r"1(?:\.0+)?", amount):
        unit = singular.get(unit, unit)
    else:
        unit = plural.get(unit, unit)
    return f"{amount} {unit}"


def _looks_like_follow_up_schedule(text: str) -> bool:
    cleaned = clean_common_noise(text).lower()
    if not cleaned:
        return False
    if len(cleaned) > 60:
        return True
    schedule_signals = [
        "baseline",
        "posttest",
        "session",
        "day 1",
        "day 2",
        "day 3",
        "t1",
        "t2",
        "t3",
        "immediately after",
        "following day",
        "first day",
        "second day",
        "third day",
        "assessment",
        "pre-treatment",
        "preintervention",
        "post-treatment,",
        "post-intervention,",
    ]
    if any(signal in cleaned for signal in schedule_signals):
        return True
    duration_count = len(
        re.findall(
            r"\b\d+(?:\.\d+)?(?:\s*(?:to|-)\s*\d+(?:\.\d+)?)?\s*(?:-| )?\s*(?:day|days|week|weeks|month|months|year|years)\b",
            cleaned,
            flags=re.I,
        )
    )
    return duration_count >= 2 and any(char in cleaned for char in [",", ";"])


def _extract_follow_up_candidates(text: str) -> List[str]:
    extracted = extract_follow_up_time_from_text(text)
    candidates = [clean_common_noise(part) for part in extracted.split(";") if clean_common_noise(part)]
    normalized = [_normalize_duration_label(part) for part in candidates]
    return [value for value in normalized if value]


def _extract_all_duration_candidates(text: str) -> List[str]:
    cleaned = clean_common_noise(text)
    if not cleaned:
        return []
    word_numbers = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "ten": "10",
        "eleven": "11",
        "twelve": "12",
    }
    for word, digit in word_numbers.items():
        cleaned = re.sub(rf"\b{word}\b", digit, cleaned, flags=re.I)
    hits = re.findall(
        r"\b\d+(?:\.\d+)?(?:\s*(?:to|-)\s*\d+(?:\.\d+)?)?\s*(?:-| )?\s*(?:day|days|week|weeks|month|months|year|years)\b",
        cleaned,
        flags=re.I,
    )
    return dedupe_keep_order(_normalize_duration_label(hit) for hit in hits)


def _pick_latest_duration(candidates: Sequence[str]) -> str:
    best = ""
    best_days = -1.0
    for candidate in candidates:
        match = re.search(r"^(.+?)\s+(day|days|week|weeks|month|months|year|years)$", candidate, flags=re.I)
        if not match:
            continue
        days = _duration_to_days(match.group(1), match.group(2))
        if days > best_days:
            best = candidate
            best_days = days
    return best


def normalize_follow_up_time(raw_text: str, context_text: str = "") -> str:
    raw = clean_common_noise(raw_text)
    if raw:
        all_raw_durations = _extract_all_duration_candidates(raw)
        if len(all_raw_durations) >= 2:
            return _pick_latest_duration(all_raw_durations) or all_raw_durations[-1]
        simple = _normalize_duration_label(raw)
        if simple and not _looks_like_follow_up_schedule(raw):
            return simple
        raw_candidates = _extract_follow_up_candidates(raw)
        if raw_candidates:
            return _pick_latest_duration(raw_candidates) or raw_candidates[-1]

    context_candidates = _extract_follow_up_candidates(context_text)
    if context_candidates:
        return _pick_latest_duration(context_candidates) or context_candidates[-1]
    return ""


def normalize_population_raw_trace(raw_text: str, population_context_text: str = "") -> str:
    fragments: List[str] = []
    merge_anchor = ""
    for fragment in _split_candidate_fragments(raw_text):
        raw_candidates: List[str] = []
        if merge_anchor and re.match(r"^(?:with|who|aged?|ages?|diagnosed|meeting|from|in)\b", fragment, flags=re.I):
            raw_candidates.append(f"{merge_anchor} {fragment}")
        raw_candidates.append(fragment)
        for raw_candidate in raw_candidates:
            cleaned = _clean_population_fragment(raw_candidate)
            if _looks_useful_population_fragment(cleaned) and not _looks_like_population_purpose_fragment(raw_candidate):
                _append_population_fragment(fragments, _clip_text(cleaned, 180))
                continue
            for hit in _extract_population_signal_snippets(raw_candidate):
                cleaned_hit = _clean_population_fragment(hit)
                if _looks_useful_population_fragment(cleaned_hit):
                    _append_population_fragment(fragments, _clip_text(cleaned_hit, 180))
        if not re.match(r"^(?:recruited|enrolled|selected|included|randomi[sz]ed|allocated|assigned|at|from)\b", fragment, flags=re.I):
            merge_anchor = fragment
    if not fragments or (len(fragments) == 1 and _population_fragment_needs_context_support(fragments[0])):
        for fragment in _split_candidate_fragments(population_context_text):
            frag_clean = clean_common_noise(fragment)
            if _looks_like_population_purpose_fragment(frag_clean):
                continue
            if re.search(r"^(?:results?|conclusions?)\b", frag_clean, flags=re.I):
                continue
            if re.search(r"\b(?:intervention group|control group|were provided with|were asked to)\b", frag_clean, flags=re.I):
                continue
            candidate_hits = _extract_population_signal_snippets(fragment)
            for hit in candidate_hits:
                clipped = _clip_text(_clean_population_fragment(hit) or hit, 180)
                if not _looks_useful_population_fragment(clipped):
                    continue
                if not clean_common_noise(raw_text) and _is_generic_population_fragment(clipped):
                    continue
                _append_population_fragment(fragments, clipped)
                if len(fragments) >= 3:
                    break
            if len(fragments) >= 3:
                break
    ordered = dedupe_keep_order(fragments)
    if len(ordered) <= 3:
        return " || ".join(ordered)
    ranked = sorted(
        list(enumerate(ordered)),
        key=lambda item: (-_population_fragment_score(item[1]), item[0]),
    )[:3]
    keep_indexes = {index for index, _value in ranked}
    selected = [value for index, value in enumerate(ordered) if index in keep_indexes]
    return " || ".join(selected)


def normalize_severity_trace(raw_severity: str, raw_population: str = "", population_context_text: str = "") -> str:
    merged_sources = [raw_severity, raw_population, population_context_text]
    patterns = [
        r"\b(?:mild|moderate|severe)(?:\s*(?:to|-)\s*(?:moderate|severe))?(?:\s+depression|\s+depressive symptoms?)?\b",
        r"\bfirst[- ]episode\b",
        r"\bnewly diagnosed\b",
        r"\bpartially remitted\b",
        r"\bremitted\b",
        r"\bresidual symptoms?\b",
        r"\bsubthreshold depression\b|\bsubsyndromal (?:depression|depressive symptoms?|symptoms?)\b",
        r"\b(?:suicidal ideation|suicide attempt|suicidality)\b",
        rf"\b{SCALE_NAME_PATTERN}\b[^.;|]{{0,40}}?\bscores?\b[^.;|]{{0,20}}?(?:>=|=>|<=|=<|>|<|=)\s*\d+(?:\.\d+)?(?:\s*(?:-|to)\s*\d+(?:\.\d+)?)?",
        rf"\b{SCALE_NAME_PATTERN}\b[^.;|]{{0,20}}?(?:>=|=>|<=|=<|>|<|=)\s*\d+(?:\.\d+)?(?:\s*(?:-|to)\s*\d+(?:\.\d+)?)?",
        r"\b(?:at risk(?:\s+for)?|high risk(?:\s+for)?|low risk(?:\s+for)?|moderate risk(?:\s+for)?|familial risk(?:\s+for)?|individual risk(?:\s+for)?)\b[^.;|]{0,90}",
        r"\b(?:current subsyndromal symptoms?|clinically relevant depressive symptoms?|elevated depressive symptoms?)\b",
    ]
    hits: List[str] = []
    for source in merged_sources:
        text = clean_common_noise(source)
        if not text:
            continue
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                hit = _strip_leading_sample_count(match.group(0))
                hit = clean_common_noise(hit)
                if hit:
                    hits.append(hit)
    return " || ".join(dedupe_keep_order(hits[:3]))


def normalize_treatment_history_trace(
    raw_treatment_history: str,
    raw_population: str = "",
    population_context_text: str = "",
) -> str:
    hits: List[str] = []
    for source in [raw_treatment_history, raw_population, population_context_text]:
        for fragment in _split_candidate_fragments(source):
            if _looks_like_population_purpose_fragment(fragment):
                continue
            for match in re.finditer(TREATMENT_HISTORY_SIGNAL_PATTERN, fragment, flags=re.I):
                hit = clean_common_noise(match.group(0))
                if hit:
                    hits.append(hit)
    return " || ".join(dedupe_keep_order(hits[:3]))


def _looks_like_evidence_purpose_sentence(text: str) -> bool:
    cleaned = clean_common_noise(text).lower()
    if not cleaned:
        return False
    patterns = [
        r"^(?:background|objective|objectives|aim|aims|methods?)\b",
        r"\bthis study aims?\b",
        r"\bwe aim(?:ed)?\b",
        r"\bobjective was to\b",
        r"\bwas designed to\b",
        r"\btrial compared\b",
        r"\bcompared the effectiveness of\b",
        r"\bto assess the effectiveness\b",
        r"\bto evaluate the (?:clinical and )?cost-effectiveness\b",
    ]
    return any(re.search(pattern, cleaned, flags=re.I) for pattern in patterns)


def _sanitize_evidence_candidate(text: str) -> str:
    cleaned = clean_common_noise(text)
    if not cleaned:
        return ""
    cleaned = re.sub(r"^(?:among|in)\s+\(?N\s*=\s*\d{1,5}(?:,\d{3})*\)?\s*(?:participants?|patients?|subjects?)?\s*[:,]?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(
        r"^(?:among|in)\s+\d{1,3}(?:,\d{3})*\s+(?:participants?|patients?|subjects?|adults?|children|women|men|completers?)\b\s*[:,]?\s*",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"^(?:among|in)\s+(?:participants?\s+)?(?:at|high|low|moderate)\s+risk(?:\s+for\s+[^,.;]{1,80})?,\s*", "", cleaned, flags=re.I)
    return clean_common_noise(cleaned)


def _score_evidence_sentence(text: str) -> int:
    cleaned = clean_common_noise(text)
    if not cleaned:
        return -999
    low = cleaned.lower()
    score = 0
    if _looks_like_evidence_purpose_sentence(cleaned):
        score -= 8
    if re.search(RESULT_STAT_PATTERN, cleaned, flags=re.I):
        score += 4
    if any(
        term in low
        for term in [
            "significant",
            "improved",
            "improvement",
            "reduced",
            "reduction",
            "decreased",
            "lower",
            "higher",
            "non-inferior",
            "no significant",
            "did not differ",
            "comparable",
            "similar",
            "favored",
            "favour",
            "response",
            "remission",
            "effective",
            "efficacy",
        ]
    ):
        score += 3
    if any(token in low for token in ["compared", "versus", "vs ", "group", "between-group"]):
        score += 1
    if re.search(SAMPLE_COUNT_PATTERN, cleaned, flags=re.I) and not re.search(RESULT_STAT_PATTERN, cleaned, flags=re.I):
        score -= 2
    if re.search(RISK_SIGNAL_PATTERN, cleaned, flags=re.I) and not re.search(RESULT_STAT_PATTERN, cleaned, flags=re.I):
        score -= 2
    if len(cleaned) > 420:
        score -= 1
    return score


def normalize_evidence_snippet(raw_text: str, evidence_context_text: str = "") -> str:
    def best_candidate(candidates: Sequence[str]) -> Tuple[str, int]:
        best_text = ""
        best_score = -999
        for candidate in candidates:
            cleaned = _sanitize_evidence_candidate(candidate)
            if not cleaned:
                continue
            score = _score_evidence_sentence(cleaned)
            if score > best_score:
                best_score = score
                best_text = cleaned
        return best_text, best_score

    raw_best_text, raw_best_score = best_candidate(_split_candidate_fragments(raw_text))
    if raw_best_score >= 2:
        return _clip_text(raw_best_text, 420)

    context_candidates = (
        re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", clean_common_noise(evidence_context_text))
        if clean_common_noise(evidence_context_text)
        else []
    )
    best_text, best_score = best_candidate(context_candidates)
    if best_score < 2:
        return ""
    return _clip_text(best_text, 420)


def is_depression_related_indication(text: str) -> bool:
    lowered = clean_common_noise(text).lower()
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
        lowered = clean_common_noise(label).lower()
        return (
            "depress" in lowered
            or lowered
            in {
                "major depressive disorder",
                "treatment-resistant depression",
                "bipolar depression",
                "peripartum depression",
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
        return clean_common_noise(label).lower() in {
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

    findings.extend(extract_context_comorbidities(" ".join(part for part in [core_text, context] if part)))
    findings = dedupe_keep_order(findings)
    if len(findings) > 1:
        if any(is_dsm5_subtype(item) for item in findings):
            findings = [item for item in findings if is_dsm5_subtype(item) or not is_depression_like(item)]
        if any(item.lower() != "depression" and "depress" in item.lower() for item in findings):
            findings = [item for item in findings if item.lower() != "depression"]
        if any(item.lower() != "depressive disorder" and "depressive" in item.lower() for item in findings):
            findings = [item for item in findings if item.lower() != "depressive disorder"]
        depression_first = [item for item in findings if is_depression_like(item)]
        non_depression = [item for item in findings if not is_depression_like(item)]
        findings = depression_first + non_depression
    return " || ".join(findings) if findings else "depression"


def normalize_intervention_type(raw_type: str, intervention: str) -> str:
    text = clean_common_noise(raw_type).lower()
    intervention_l = clean_common_noise(intervention).lower()
    if any(marker in intervention_l for marker in [" + ", " plus ", " combined with ", " with "]):
        active_combo = not any(token in intervention_l for token in ["usual care", "standard care", "waitlist", "attention control", "sham", "placebo"])
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

    if any(token in intervention_l for token in ["ketamine", "esketamine", "escitalopram", "sertraline", "fluoxetine", "bupropion", "venlafaxine", "duloxetine", "paroxetine", "citalopram", "mirtazapine", "placebo"]):
        return "Drug"
    if any(token in intervention_l for token in ["exercise", "cbt", "psychotherapy", "behavioral activation", "mindfulness", "yoga", "acupuncture", "collaborative care"]):
        return "Behavioral"
    if any(token in intervention_l for token in ["rtms", "itbs", "tms", "transcranial", "stimulation", "tdcs", "ect"]):
        return "Device"
    if any(token in intervention_l for token in ["vitamin", "omega-3", "fish oil", "supplement", "probiotic", "folate", "melatonin"]):
        return "Dietary Supplement"
    return "Other"


# Intervention/comparator normalization now lives in arm_normalization.py.


def clean_target(raw_text: str, intervention: str, indication: str) -> str:
    text = clean_common_noise(raw_text)
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {clean_common_noise(intervention).lower(), clean_common_noise(indication).lower()}:
        return ""
    if any(bad in lowered for bad in ["randomized", "depression", "study", "trial", "patients", "psychotherapy", "exercise", "session", "weekly"]):
        target_signals = ["receptor", "pathway", "axis", "transporter", "inflammation", "bdnf", "nmda", "gaba", "5-ht", "seroton", "dopamin", "glutamat", "hpa", "trkb", "d2", "d3", "mao"]
        if not any(signal in lowered for signal in target_signals):
            return ""
    if len(text.split()) > 8 or len(text) > 80:
        return ""
    return text


def normalize_outcome_direction(raw_text: str, evidence_text: str) -> str:
    raw = clean_common_noise(raw_text).lower()
    evidence = clean_common_noise(evidence_text).lower()
    text = " ".join(part for part in [raw, evidence] if part).strip()
    if not text:
        return "Mixed or Unknown"

    if raw in {"positive", "improvement", "improved", "increase", "better"}:
        return "Positive"
    if raw in {"neutral", "no difference", "no change", "no significant difference", "no effect"}:
        return "Neutral"
    if raw in {"negative", "worsening", "worsened", "worse", "decrease"}:
        return "Negative"
    if raw in {"mixed", "unknown"} and not evidence:
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

    if any(term in text for term in ["mixed result", "mixed results", "mixed finding", "mixed findings", "inconclusive", "unclear"]):
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

    pos = any(term in text for term in strong_positive_terms) or any(re.search(pattern, text) for pattern in positive_context_patterns)
    neg = any(term in text for term in strong_negative_terms) or any(re.search(pattern, text) for pattern in negative_context_patterns)
    if pos and not neg:
        return "Positive"
    if neg and not pos:
        return "Negative"
    return "Mixed or Unknown"


def normalize_step2a_fields(
    raw_row: Dict[str, Any],
    context_text: str = "",
    population_context_text: str = "",
    evidence_context_text: str = "",
) -> Dict[str, str]:
    def value(key: str) -> str:
        return clean_common_noise(raw_row.get(key, ""))

    population_context = population_context_text or context_text
    evidence_context = evidence_context_text or context_text
    raw_intervention = value("intervention")
    raw_comparator = value("comparator")
    inferred_type = normalize_intervention_type(value("intervention_type"), raw_intervention or raw_comparator)
    intervention = normalize_step2a_arm_label(raw_intervention, inferred_type)
    comparator = normalize_step2a_arm_label(raw_comparator, inferred_type)
    indication_context = " ; ".join(part for part in [value("population_raw"), context_text] if part)
    indication = normalize_indication(value("indication"), indication_context)
    evidence_text = normalize_evidence_snippet(value("evidence_snippet"), evidence_context)
    population_raw = normalize_population_raw_trace(value("population_raw"), population_context)
    severity = normalize_severity_trace(value("severity"), value("population_raw"), population_context)
    treatment_history = normalize_treatment_history_trace(
        value("treatment_history"),
        value("population_raw"),
        population_context,
    )
    allow_aggregate_sample_size = _row_allows_total_sample_size_context_fallback(raw_row)
    return {
        "source_index": normalize_source_index_value(value("source_index")),
        "indication": indication,
        "population_raw": population_raw,
        "severity": severity,
        "treatment_history": treatment_history,
        "intervention": intervention,
        "intervention_type": inferred_type,
        "comparator": comparator,
        "target": clean_target(value("target"), intervention, indication),
        "outcome_direction": normalize_outcome_direction(value("outcome_direction"), evidence_text),
        "sample_size": normalize_sample_size(
            value("sample_size"),
            context_text,
            allow_aggregate_fallback=allow_aggregate_sample_size,
        ),
        "follow_up_time": normalize_follow_up_time(value("follow_up_time"), context_text or evidence_text),
        "evidence_snippet": evidence_text,
    }

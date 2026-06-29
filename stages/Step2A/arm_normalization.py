from __future__ import annotations

import re
from typing import Any, List, Sequence, Tuple


def _clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\u00ae", "").replace("\u2122", "")
    text = text.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ;|,-")


def _dedupe_keep_order(items: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for item in items:
        value = _clean_text(item)
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(value)
    return ordered


RELEASE_PATTERNS: List[Tuple[str, str]] = [
    (r"\boros\b|\bosmotic(?:[- ]release)?\b|\bosmotic pump\b", "OROS"),
    (r"\bdelayed[- ]release\b|\bdelayed release\b|\bdr\b|\benteric[- ]coated\b|\benteric coated\b|\bgastro[- ]resistant\b", "DR"),
    (r"\bextended[- ]release\b|\bextended release\b|\bxr\b|\bxl\b|\ber\b|\brepeat[- ]action\b|\blong[- ]acting\b", "ER"),
    (r"\bsustained[- ]release\b|\bsustained release\b|\bsustained[- ]action\b|\bsr\b|\bslow[- ]release\b", "SR"),
    (r"\bcontrolled[- ]release\b|\bcontrolled release\b|\bcr\b", "CR"),
    (r"\bimmediate[- ]release\b|\bimmediate release\b|\bir\b", "IR"),
    (r"\bmodified[- ]release\b|\bmodified release\b|\bmr\b", "MR"),
    (r"\bprolonged[- ]release\b|\bprolonged release\b|\bpr\b", "PR"),
    (r"\bdepot\b|\blong[- ]acting injectable\b|\blai\b", "Depot"),
]


SALT_PATTERNS: List[str] = [
    r"\bacetate\b",
    r"\bhydrochloride\b",
    r"\bdihydrochloride\b",
    r"\bsulfate\b",
    r"\bsodium\b",
    r"\bphosphate\b",
    r"\bmaleate\b",
    r"\bmesylate\b",
    r"\bnitrate\b",
    r"\btartrate\b",
    r"\bcitrate\b",
    r"\bhydrobromide\b",
    r"\bhemihydrobromide\b",
    r"\bpotassium\b",
    r"\bsuccinate\b",
    r"\bhcl\b",
    r"\bhci\b",
    r"\bmonohydrate\b",
    r"\bh2o\b",
    r"\bfumarate\b",
]


DOSAGE_FORM_PATTERNS: List[Tuple[str, str]] = [
    (r"\bnasal spray\b", "nasal spray"),
    (r"\bintranasal\b", "intranasal"),
    (r"\btransdermal patch(?:es)?\b|\bpatch(?:es)?\b", "transdermal patch"),
    (r"\btransdermal\b", "transdermal"),
    (r"\bvaginal tablets?\b|\bvaginal\b", "vaginal tablet"),
    (r"\bintravenous infusion\b|\biv infusion\b|\binfusions?\b", "IV infusion"),
    (r"\bintravenous\b|\biv\b", "IV"),
    (r"\bintramuscular\b|\bim\b", "IM injection"),
    (r"\bsubcutaneous\b|\bsubcut(?:aneous)?\b|\bsc\b", "SC injection"),
    (r"\btopical\b", "topical"),
    (r"\binhalation\b|\bnebuli[sz]ed\b", "inhalation"),
    (r"\binjections?\b|\binjectable\b", "injection"),
    (r"\bsublingual\b", "sublingual"),
    (r"\bbuccal\b", "buccal"),
    (r"\borally disintegrating tablets?\b|\borally disintegrating\b|\bodt\b", "oral tablet"),
    (r"\btablets?\b", "oral tablet"),
    (r"\bcapsules?\b", "oral capsule"),
    (r"\bsolutions?\b", "oral solution"),
    (r"\bsuspensions?\b", "oral suspension"),
    (r"\bgranules?\b", "granules"),
    (r"\bpowders?\b", "oral powder"),
    (r"\bgum\b", "gum"),
    (r"\bpills?\b|\boral\b|\bp\.?o\.?\b|\bper os\b", "oral"),
    (r"\bfilms?\b", "film"),
    (r"\blozenges?\b|\btroches?\b", "lozenge"),
    (r"\bimplants?\b|\bpellets?\b", "implant"),
    (r"\bsuppositor(?:y|ies)\b", "suppository"),
    (r"\benema\b", "enema"),
    (r"\bcream\b", "topical cream"),
    (r"\bgel\b", "topical gel"),
    (r"\bointment\b", "topical ointment"),
    (r"\bdrops?\b", "drops"),
]


FREQUENCY_REPLACEMENTS: List[Tuple[str, str]] = [
    (r"\bb\.?\s*i\.?\s*d\.?\b", "BID"),
    (r"\bt\.?\s*i\.?\s*d\.?\b", "TID"),
    (r"\bq\.?\s*i\.?\s*d\.?\b", "QID"),
    (r"\bq\.?\s*h\.?\s*s\.?\b", "QHS"),
    (r"\bq\.?\s*o\.?\s*d\.?\b", "every other day"),
    (r"\bonce daily\b|\bdaily\b|\bq\.?\s*d\.?\b|\bod\b", "/day"),
    (r"\bhours?\b|\bhrs?\b", "hour"),
    (r"\bweekly\b", "/week"),
    (r"\bmonthly\b", "/month"),
]


DRUG_COMPONENT_PATTERNS: List[Tuple[str, str]] = [
    (r"\blpcn[- ]?1154a\b", "Brexanolone"),
    (r"\blu[- ]?aa[- ]?21004\b|\bluaa21004\b", "Vortioxetine"),
    (r"\bprt[- ]?042\b", "Ketamine"),
    (r"\bcle[- ]?100\b", "Esketamine"),
    (r"\bsls[- ]?002\b", "Ketamine"),
    (r"\bci[- ]?581a\b|\bci[- ]?581b\b", "Ketamine"),
    (r"\btnx[- ]?601\b", "Tianeptine"),
    (r"\bsep[- ]?4199\b", "Amisulpride"),
    (r"\bes[- ]citalopram\b|\bs[- ]citalopram\b", "Escitalopram"),
    (r"\bspt[- ]?300\b", "Brexanolone prodrug"),
    (r"\bbci[- ]?024\b", "Buspirone"),
    (r"\bbci[- ]?049\b", "Melatonin"),
    (r"\b(?:apex[- ]?002[- ]?a02|psil428)\b", "Psilocybin"),
    (r"\bele[- ]?101\b", "Psilocin"),
    (r"\b(?:bmnd08|bpl[- ]?003|gh001)\b", "5-MeO-DMT"),
    (r"\besketamine\b", "Esketamine"),
    (r"\bketamine\b", "Ketamine"),
    (r"\bmidazolam\b", "Midazolam"),
    (r"\bimipramine\b", "Imipramine"),
    (r"\bmirtazapine\b", "Mirtazapine"),
    (r"\bsertraline\b", "Sertraline"),
    (r"\bfluvoxamine\b", "Fluvoxamine"),
    (r"\bfluoxetine\b", "Fluoxetine"),
    (r"\bescitalopram\b", "Escitalopram"),
    (r"\bvenlafaxine(?:-er| extended[- ]release)?\b", "Venlafaxine"),
    (r"\bdesvenlafaxine\b", "Desvenlafaxine"),
    (r"\bduloxetine\b", "Duloxetine"),
    (r"\blevomilnacipran\b", "Levomilnacipran"),
    (r"\bvortioxetine\b", "Vortioxetine"),
    (r"\bagomelatine\b", "Agomelatine"),
    (r"\bvilazodone\b", "Vilazodone"),
    (r"\blurasidone\b", "Lurasidone"),
    (r"\bbrexpiprazole\b", "Brexpiprazole"),
    (r"\bcariprazine\b", "Cariprazine"),
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
    (r"\bmemantine\b", "Memantine"),
    (r"\bnaltrexone\b", "Naltrexone"),
    (r"\bmifepristone\b", "Mifepristone"),
    (r"\bmetyrapone\b", "Metyrapone"),
    (r"\briluzole\b", "Riluzole"),
    (r"\blisdexamfetamine(?: dimesylate)?\b", "Lisdexamfetamine"),
    (r"\batomoxetine\b", "Atomoxetine"),
    (r"\brasagiline\b", "Rasagiline"),
    (r"\bonabotulinumtoxina\b", "OnabotulinumtoxinA"),
    (r"\bbuprenorphine\b", "Buprenorphine"),
    (r"\bsamidorphan\b", "Samidorphan"),
    (r"\bgalcanezumab\b", "Galcanezumab"),
    (r"\bixekizumab\b", "Ixekizumab"),
    (r"\badalimumab\b", "Adalimumab"),
    (r"\bbrodalumab\b", "Brodalumab"),
    (r"\baspirin\b|\bacetylsalicylic acid\b", "Aspirin"),
    (r"\batorvastatin\b", "Atorvastatin"),
    (r"\bestradiol\b", "Estradiol"),
    (r"\bciticoline\b", "Citicoline"),
    (r"\bpalmitoylethanolamide\b", "Palmitoylethanolamide"),
    (r"\bvitamin d3?\b", "Vitamin D"),
    (r"\bomega[- ]?3\b|\bn[- ]?3 pufas?\b|\bfish oil\b|\bo3fa\b", "Omega-3"),
    (r"\bsaffron\b|\baffron\b", "Saffron"),
    (r"\bcoenzyme q10\b", "Coenzyme Q10"),
    (r"\bcreatine(?: monohydrate)?\b", "Creatine"),
    (r"\bprobiotic\b|\bsynbiotic\b", "Probiotic"),
    (r"\bmelatonin\b", "Melatonin"),
    (r"\btianeptine\b", "Tianeptine"),
    (r"\bamisulpride\b", "Amisulpride"),
    (r"\bbuspirone\b", "Buspirone"),
    (r"\bpsilocybin\b", "Psilocybin"),
    (r"\bpsilocin\b", "Psilocin"),
    (r"\b5[- ]?meo[- ]?dmt\b", "5-MeO-DMT"),
    (r"\bdmt\b", "DMT"),
    (r"\bsame\b|\bs-adenosyl methionine\b", "SAMe"),
    (r"\bst\.?\s*john'?s wort(?: extract)?\b|\bst john'?s wort(?: extract)?\b", "St John's wort"),
    (r"\bwuling (?:powder|capsule)\b", "Wuling"),
    (r"\bshugan jieyu\b|\bshu gan yi yang\b", "Shugan Jieyu"),
    (r"\bpanax ginseng\b", "Panax ginseng"),
    (r"\bciwujia\b", "Ciwujia"),
    (r"\bantidepressants?\b|\bantidepressant\b|\bssris?\b|\bssri\b", "Antidepressant"),
    (r"\bplacebo\b|\bpbo\b", "Placebo"),
]


NON_DRUG_PATTERNS: List[Tuple[str, str]] = [
    (r"\bcognitive[- ]behavio(?:u)?ral therapy for insomnia\b|\bcbt-i\b", "CBT-I"),
    (r"\bcognitive[- ]behavio(?:u)?ral therapy\b|\bcbt\b", "CBT"),
    (r"\binterpersonal psychotherapy\b|\bipt\b", "IPT"),
    (r"\binternet[- ]based cognitive[- ]behavio(?:u)?ral (?:therapy|intervention)\b|\bicbt\b|\bccbt\b", "iCBT"),
    (r"\bmindfulness[- ]based cognitive therapy\b|\bmbct\b", "MBCT"),
    (r"\bmindfulness[- ]based therapy\b", "Mindfulness-based therapy"),
    (r"\bbehavioral activation\b|\bbehavioural activation\b", "Behavioral activation"),
    (r"\btranscranial magnetic stimulation\b|\btms\b", "TMS"),
    (r"\brtms\b", "rTMS"),
    (r"\bitbs\b", "iTBS"),
    (r"\btdcs\b", "tDCS"),
    (r"\bect\b|\belectroconvulsive therapy\b", "ECT"),
    (r"\baerobic exercise\b|\bphysical activity\b|\bexercise\b", "Exercise"),
    (r"\bcollaborative care\b", "Collaborative care"),
    (r"\bacupuncture\b", "Acupuncture"),
    (r"\byoga\b", "Yoga"),
    (r"\bbright light therapy\b", "Bright light therapy"),
    (r"\bdeep brain stimulation\b|\bdbs\b", "DBS"),
    (r"\bprogressive muscle relaxation\b", "Progressive muscle relaxation"),
    (r"\bmindfulness meditation\b", "Mindfulness meditation"),
    (r"\bmusic therapy\b", "Music therapy"),
    (r"\bqigong\b", "Qigong"),
    (r"\beducation\b|\bpsychoeducation\b", "Education"),
]


def extract_release_type(raw_text: str) -> str:
    text = _clean_text(raw_text).lower()
    for pattern, label in RELEASE_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            return label
    return ""


def extract_dosage_form(raw_text: str) -> str:
    text = _clean_text(raw_text)
    for pattern, label in DOSAGE_FORM_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            return label
    return ""


def _normalize_unit(unit: str) -> str:
    lowered = unit.lower()
    if lowered in {"ug", "mcg", "\u00b5g", "\u03bcg"}:
        return "mcg"
    if lowered == "kiu":
        return "kIU"
    if lowered == "iu":
        return "IU"
    if lowered == "u":
        return "U"
    if lowered == "meq":
        return "mEq"
    if lowered == "ml":
        return "mL"
    return unit


def _normalize_dose_text(raw_text: str) -> str:
    text = _clean_text(raw_text)
    text = re.sub(
        r"(?i)\b(\d[\d,]*(?:\.\d+)?)\s*(kiu|mcg|ug|[\u00b5\u03bc]g|mg|g|ng|pg|ml|iu|u|units|mmol|meq)\b",
        lambda match: f"{match.group(1)} {_normalize_unit(match.group(2))}",
        text,
    )
    text = re.sub(r"(?i)\s*/\s*d\b", "/day", text)
    text = re.sub(r"(?i)\s*/\s*day\b", "/day", text)
    text = re.sub(r"(?i)\s*/\s*wk\b", "/week", text)
    text = re.sub(r"(?i)\s*/\s*week\b", "/week", text)
    text = re.sub(r"(?i)\s*/\s*mo\b", "/month", text)
    text = re.sub(r"(?i)\s*/\s*month\b", "/month", text)
    text = re.sub(r"(?i)\s*/\s*hr\b", "/hour", text)
    text = re.sub(r"(?i)\s*/\s*h\b", "/hour", text)
    text = re.sub(r"(?i)\s*/\s*hour\b", "/hour", text)
    text = re.sub(r"(?i)\s*/\s*min\b", "/min", text)
    text = re.sub(r"(?i)\s*/\s*minute\b", "/min", text)
    text = re.sub(r"(?i)\s*/\s*kg\b", "/kg", text)
    text = re.sub(r"(?i)\s*/\s*dose\b", "/dose", text)
    for pattern, replacement in FREQUENCY_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" /", "/").replace("/ ", "/")
    return text.strip(" ;,.()")


def extract_dose(raw_text: str) -> str:
    text = _clean_text(raw_text)
    if not text:
        return ""

    amount = r"\d[\d,]*(?:\.\d+)?(?:\s*(?:-|to|/)\s*\d[\d,]*(?:\.\d+)?)*"
    unit = r"(?:kiu|mcg|ug|[\u00b5\u03bc]g|mg|g|ng|pg|ml|mL|iu|u|units|mmol|mEq)"
    rate = r"(?:kg|day|d|week|wk|month|mo|dose|h|hr|hour|min|minute)"
    frequency = (
        r"(?:once daily|twice daily|three times daily|four times daily|daily|weekly|monthly|"
        r"b\.?\s*i\.?\s*d\.?|t\.?\s*i\.?\s*d\.?|q\.?\s*i\.?\s*d\.?|q\.?\s*h\.?\s*s\.?|"
        r"q\.?\s*o\.?\s*d\.?|q\.?\s*d\.?|od|bid|tid|qid|qhs|"
        r"every other day|every \d+\s*(?:day|days|week|weeks|month|months))"
    )
    patterns = [
        rf"\b{amount}\s*{unit}\s*/\s*{rate}(?:\s*/\s*(?:day|d|week|wk|month|mo))?\b",
        rf"\b{amount}\s*{unit}\s*{frequency}\b",
        rf"\b{amount}\s*{unit}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return _normalize_dose_text(match.group(0))
    return ""


def strip_arm_noise(raw_text: str) -> str:
    text = _clean_text(raw_text)
    if not text:
        return ""
    text = re.sub(r"^\[[^\]]+\]-?\s*", "", text)
    text = re.sub(r"\s*(?:->|=>|\u2192).*$", "", text, flags=re.DOTALL)
    text = re.sub(r"\badministered\b.*$", "", text, flags=re.I | re.DOTALL)
    text = re.sub(r"^(?:intervention|comparator|treatment|arm|group)\s*[:\-]\s*", "", text, flags=re.I)
    text = re.sub(r"^(?:received|treated with|assigned to|randomized to|randomised to)\s+", "", text, flags=re.I)
    text = re.sub(r"^(?:switch(?:ing)? to|switch to|add[- ]on(?: to)?|adding|adjunctive|augmentation with|continu(?:e|ing)|combined?|combining)\s+", "", text, flags=re.I)
    text = re.sub(r"^\b(?:single|double|repeated|repeat|once[- ]daily|twice[- ]daily)\b\s+", "", text, flags=re.I)
    text = re.sub(r"\b(?:randomized|randomised|assignment|allocation)\b", "", text, flags=re.I)
    text = re.sub(r"\s*\(([A-Z][A-Z0-9-]{1,9})\)\s*$", "", text)
    text = re.sub(r"\b(?:group|arm)\b$", "", text, flags=re.I)
    return _clean_text(text)


def split_arm_components(raw_text: str) -> List[str]:
    text = strip_arm_noise(raw_text)
    if not text:
        return []
    parts = re.split(r"\s*(?:\+|&|\bplus\b|\bcombined with\b|\badd[- ]on to\b)\s*", text, flags=re.I)
    expanded: List[str] = []
    for part in parts:
        cleaned = _clean_text(part)
        if not cleaned:
            continue
        if "/" in cleaned and not re.search(r"\d", cleaned):
            expanded.extend(piece for piece in re.split(r"\s*/\s*", cleaned) if _clean_text(piece))
        else:
            expanded.append(cleaned)
    return [_clean_text(part) for part in expanded if _clean_text(part)]


def _format_component_name(raw_name: str) -> str:
    cleaned = _clean_text(raw_name).strip("()[]")
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    fixed = {
        "cbt": "CBT",
        "cbt-i": "CBT-I",
        "mbct": "MBCT",
        "tms": "TMS",
        "rtms": "rTMS",
        "itbs": "iTBS",
        "tdcs": "tDCS",
        "ect": "ECT",
        "dbs": "DBS",
        "ipt": "IPT",
        "icbt": "iCBT",
        "ssri": "SSRI",
        "ssris": "SSRIs",
    }
    if lowered in fixed:
        return fixed[lowered]
    code_match = re.fullmatch(r"([A-Za-z]{2,6})([- ]?)(\d{2,6}[A-Za-z]?)", cleaned)
    if code_match:
        return f"{code_match.group(1).upper()}-{code_match.group(3).upper()}"

    words: List[str] = []
    for word in cleaned.split():
        if re.fullmatch(r"[A-Z0-9-]{2,}", word):
            words.append(word)
        elif re.search(r"\d", word):
            words.append(word.upper() if word.upper() == word else word.capitalize())
        elif len(word) <= 4 and word.isupper():
            words.append(word)
        else:
            words.append(word.capitalize())
    return " ".join(words)


def standardize_control_term(raw_text: str) -> str:
    text = strip_arm_noise(raw_text)
    if not text:
        return ""
    lowered = text.lower()

    if re.search(r"\b(?:placebo|pbo|active placebo|matched pill placebo|pill placebo|saline|saline placebo|normal saline|saline infusion|placebo nasal spray)\b", lowered):
        return "Placebo"
    if re.search(
        r"\b(?:usual care|care[- ]as[- ]usual|care as usual|as[- ]usual|treatment as usual|tau|routine care|usual gp care|service as usual|physician'?s usual care|standard treatment|conventional treatment|enhanced usual care|enhanced treatment as usual|enhanced care[- ]as[- ]usual|enhanced tau|optimized treatment as usual|improved treatment as usual)\b",
        lowered,
    ):
        return "Usual care"
    if re.search(r"\b(?:standard care|standard of care|soc)\b", lowered):
        return "Standard care"
    if re.search(r"\b(?:waiting[- ]list|wait[- ]?list|wait[- ]listed|wl|active waiting list|delayed treatment control)\b", lowered):
        return "Waitlist"
    if re.search(r"\battention[- ]control\b|\battention control\b", lowered):
        return "Attention control"
    if re.search(r"\bsham(?:[- ]?(?:stimulation|treatment|tms|tdcs|dbs|tbs|ctbs|acupuncture|acupressure|control|training|waa|cpap|lllt))?\b", lowered):
        return "Sham"
    if re.search(r"\b(?:no intervention|no treatment|untreated)\b", lowered):
        return "No intervention"
    if re.fullmatch(r"(?:control condition|control group|control|comparison|comparison treatment|active control|noninterventional control|minimal (?:contact|support) control|monitoring control|supportive control|forum-only control|control training)", lowered):
        return "Control"
    return ""


def canonicalize_non_drug_label(raw_text: str) -> str:
    text = strip_arm_noise(raw_text)
    if not text:
        return ""
    control = standardize_control_term(text)
    if control:
        return control
    for pattern, label in NON_DRUG_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            return label
    return text


def extract_named_components_with_pos(raw_text: str) -> List[Tuple[int, int, str]]:
    text = _clean_text(raw_text)
    lowered = text.lower()
    hits_with_pos: List[Tuple[int, int, str]] = []
    for pattern, label in DRUG_COMPONENT_PATTERNS:
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


def _extract_local_window(raw_text: str, start: int, end: int) -> str:
    return raw_text[max(0, start - 12) : min(len(raw_text), end + 48)]


def _remove_pattern_list(text: str, patterns: Sequence[Tuple[str, str]]) -> str:
    cleaned = text
    for pattern, _ in patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.I)
    return cleaned


def _extract_fallback_drug_name(raw_text: str) -> str:
    text = strip_arm_noise(raw_text)
    if not text:
        return ""
    text = re.sub(
        r"\b\d[\d,]*(?:\.\d+)?(?:\s*(?:-|to|/)\s*\d[\d,]*(?:\.\d+)?)*\s*(?:mcg|ug|[\u00b5\u03bc]g|mg|g|ng|pg|ml|mL|iu|u|units|mmol|mEq)(?:\s*/\s*(?:kg|day|d|week|wk|month|mo|dose|h|hr|hour|min|minute))?(?:\s*(?:once daily|twice daily|three times daily|four times daily|daily|weekly|monthly|b\.?\s*i\.?\s*d\.?|t\.?\s*i\.?\s*d\.?|q\.?\s*i\.?\s*d\.?|q\.?\s*h\.?\s*s\.?|q\.?\s*o\.?\s*d\.?|q\.?\s*d\.?|od|bid|tid|qid|qhs|every other day|every \d+\s*(?:day|days|week|weeks|month|months)))?\b",
        " ",
        text,
        flags=re.I,
    )
    text = _remove_pattern_list(text, RELEASE_PATTERNS)
    text = _remove_pattern_list(text, DOSAGE_FORM_PATTERNS)
    for pattern in SALT_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.I)
    text = re.sub(r"\b(?:flexible[- ]dose|fixed[- ]dose|higher dose|lower dose|high[- ]dose|low[- ]dose|dose)\b", " ", text, flags=re.I)
    text = re.sub(r"\((?:[^)]{0,40})\)", " ", text)
    text = re.sub(r"[/|]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = _clean_text(text)
    if not text:
        return ""
    return _format_component_name(text)


def _format_drug_component(name: str, release: str = "", dosage_form: str = "", dose: str = "") -> str:
    return f"{_format_component_name(name)}|{release}|{dosage_form}|{dose}"


def normalize_drug_label(raw_text: str) -> str:
    text = strip_arm_noise(raw_text)
    if not text:
        return ""

    control = standardize_control_term(text)
    if control:
        return control

    component_hits = extract_named_components_with_pos(text)
    if len(component_hits) >= 2:
        parts: List[str] = []
        for start, end, label in component_hits:
            window = _extract_local_window(text, start, end)
            parts.append(
                _format_drug_component(
                    label,
                    extract_release_type(window),
                    extract_dosage_form(window),
                    extract_dose(window),
                )
            )
        return " + ".join(part for part in _dedupe_keep_order(parts) if part)

    if len(component_hits) == 1:
        label = component_hits[0][2]
        return _format_drug_component(
            label,
            extract_release_type(text),
            extract_dosage_form(text),
            extract_dose(text),
        )

    fallback_name = _extract_fallback_drug_name(text)
    if fallback_name:
        return _format_drug_component(
            fallback_name,
            extract_release_type(text),
            extract_dosage_form(text),
            extract_dose(text),
        )
    return text


def _looks_drug_like(raw_text: str, intervention_type: str) -> bool:
    text = _clean_text(raw_text)
    if not text:
        return False
    if standardize_control_term(text):
        return False
    for pattern, _ in NON_DRUG_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            return False
    if intervention_type == "Drug":
        return True
    if extract_named_components(text):
        return True
    return bool(extract_dose(text) or extract_dosage_form(text) or extract_release_type(text))


def normalize_arm_label(raw_text: str, intervention_type: str) -> str:
    text = strip_arm_noise(raw_text)
    if not text:
        return ""

    components = split_arm_components(text)
    if len(components) >= 2:
        normalized_components: List[str] = []
        for component in components:
            control = standardize_control_term(component)
            if control:
                normalized_components.append(control)
                continue
            if _looks_drug_like(component, intervention_type):
                normalized_components.append(normalize_drug_label(component))
            else:
                normalized_components.append(canonicalize_non_drug_label(component))
        return " + ".join(part for part in _dedupe_keep_order(normalized_components) if part)

    control = standardize_control_term(text)
    if control:
        return control
    if _looks_drug_like(text, intervention_type):
        return normalize_drug_label(text)
    return canonicalize_non_drug_label(text)

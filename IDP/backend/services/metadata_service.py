"""Metadata extraction for legal documents using spaCy and regex heuristics.

Provides best-effort extraction and returns empty structures on failure.
"""
from typing import Dict, List
import re

from typing import Dict, List, Tuple
import re

try:
    import spacy
    _NLP = spacy.load("en_core_web_sm")
except Exception:
    _NLP = None


"""Metadata extraction for legal documents using spaCy and regex heuristics.

Provides best-effort extraction and returns empty structures on failure.
"""
from typing import Dict
import re

try:
    import spacy
    _NLP = spacy.load("en_core_web_sm")
except Exception:
    _NLP = None


_CASE_RE = re.compile(
    r"(?:(?:CASE\s*(?:NO\.?|NUMBER)?|CASE\s+NO\.|PETITION\s+NO\.|CRL\.?P\.?\s+NO\.|CRIMINAL PETITION\s+NO\.|COMPANY PETITION\s+NO\.|WP\s+NO\.|WRIT PETITION\s+NO\.)[:\-\s]{0,6}([A-Za-z0-9\-/\\.]+))",
    re.I,
)

_FIR_RE = re.compile(r"(?:FIR\s*(?:NO\.?|NUMBER)?|CRIME\s*(?:NO\.?|NUMBER)?|CR\. NO\.)[:#\-\s]*([A-Za-z0-9\-/\\.]+)", re.I)
_DATE_RE = re.compile(r"(\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b|\b\d{4}[\-/]\d{1,2}[\-/]\d{1,2}\b)")
_IPC_RE = re.compile(r"\bIPC\s*(?:Sections?|Sec\.?|S\.)?\s*[:\-]?\s*([0-9AB\-\/\,\s]+)", re.I)


def _normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\r", "\n")
    s = re.sub(r"\n+", "\n", s)
    s = s.replace("\n", " ")
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = s.strip()
    s = re.sub(r"^[\-\:\,\.\;\"']+", "", s)
    s = re.sub(r"[\-\:\,\.\;\"']+$", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _extract_party_from_line(line: str, label: str) -> str:
    m = re.search(rf"{label}[^A-Za-z0-9\n\r\:]*[:\-\s]+(.+)$", line, re.I)
    if m:
        return _normalize_text(m.group(1))
    return ""


def extract_metadata(text: str, return_raw: bool = False):
    """Extract metadata from OCR text.

    Returns a cleaned metadata dict. If return_raw=True, also returns a raw_candidates dict
    containing initial regex/NER hits so callers can inspect raw vs cleaned outputs.
    """
    if not text:
        empty = {
            "case_number": "",
            "fir_number": "",
            "date": "",
            "petitioner": "",
            "respondent": "",
            "appellant": "",
            "defendant": "",
            "plaintiff": "",
            "judge_name": "",
            "persons": [],
            "organizations": [],
            "addresses": [],
            "ipc_sections": [],
        }
        return (empty, empty) if return_raw else empty

    try:
        raw_candidates: Dict = {}
        cleaned: Dict = {
            "case_number": "",
            "fir_number": "",
            "date": "",
            "petitioner": "",
            "respondent": "",
            "appellant": "",
            "defendant": "",
            "plaintiff": "",
            "judge_name": "",
            "persons": [],
            "organizations": [],
            "addresses": [],
            "ipc_sections": [],
        }

        lines = [l.strip() for l in re.split(r"[\n\r]+", text) if l.strip()]

        m_fir = _FIR_RE.search(text)
        raw_candidates["fir_raw"] = m_fir.group(1).strip() if m_fir else ""

        m_case = _CASE_RE.search(text)
        raw_candidates["case_raw"] = m_case.group(1).strip() if m_case else ""

        m_date = _DATE_RE.search(text)
        raw_candidates["date_raw"] = m_date.group(1) if m_date else ""

        m_ipc = _IPC_RE.search(text)
        raw_candidates["ipc_raw"] = m_ipc.group(1).strip() if m_ipc else ""

        raw_candidates["ner_persons"] = []
        raw_candidates["ner_orgs"] = []
        raw_candidates["ner_gpes"] = []
        if _NLP is not None:
            doc = _NLP(text)
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    raw_candidates["ner_persons"].append(ent.text)
                elif ent.label_ == "ORG":
                    raw_candidates["ner_orgs"].append(ent.text)
                elif ent.label_ in ("GPE", "LOC", "FAC"):
                    raw_candidates["ner_gpes"].append(ent.text)

        case_cand = raw_candidates.get("case_raw", "")
        if case_cand and re.search(r"\d{1,}", case_cand) and 2 <= len(case_cand) <= 120:
            cleaned["case_number"] = _normalize_text(case_cand)

        fir_cand = raw_candidates.get("fir_raw", "")
        if fir_cand and re.search(r"\d", fir_cand):
            cleaned["fir_number"] = _normalize_text(fir_cand)

        if raw_candidates.get("date_raw"):
            cleaned["date"] = raw_candidates["date_raw"].strip()

        if raw_candidates.get("ipc_raw"):
            sections = re.split(r"[\,\s]+", raw_candidates["ipc_raw"]) if raw_candidates["ipc_raw"] else []
            cleaned["ipc_sections"] = [s.strip() for s in sections if s.strip()]

        for ln in lines:
            ln_norm = ln.upper()
            if re.search(r"PETITIONER|PETITIONERS|PETITIONER\(S\)|PET\.|PET\s+NO\.", ln_norm):
                pet = _extract_party_from_line(ln, "PETITIONER")
                if pet:
                    cleaned["petitioner"] = pet
            if re.search(r"RESPONDENT|RESPONDENTS", ln_norm):
                resp = _extract_party_from_line(ln, "RESPONDENT")
                if resp:
                    cleaned["respondent"] = resp
            if re.search(r"APPELLANT|APPELLANTS", ln_norm):
                app = _extract_party_from_line(ln, "APPELLANT")
                if app:
                    cleaned["appellant"] = app
            if re.search(r"DEFENDANT|PLAINTIFF", ln_norm):
                if "DEFENDANT" in ln_norm:
                    d = _extract_party_from_line(ln, "DEFENDANT")
                    if d:
                        cleaned["defendant"] = d
                if "PLAINTIFF" in ln_norm:
                    p = _extract_party_from_line(ln, "PLAINTIFF")
                    if p:
                        cleaned["plaintiff"] = p
            if re.search(r"\b\w+\b\s+v\.?s?\.?\s+\b\w+\b", ln, re.I):
                vs_parts = re.split(r"\bvs?\.?\b|\bv\.\b", ln, flags=re.I)
                if len(vs_parts) >= 2 and not cleaned["petitioner"]:
                    cleaned["petitioner"] = _normalize_text(vs_parts[0])
                    cleaned["respondent"] = _normalize_text(vs_parts[1])
            if re.search(r"HON(?:'|’)??BLE\s+JUSTICE|HONOURABLE\s+JUSTICE|JUSTICE\b|JUDGE\b", ln_norm):
                jm = re.split(r"HON(?:'|’)??BLE\s+JUSTICE|HONOURABLE\s+JUSTICE|JUSTICE|JUDGE", ln, flags=re.I)
                if len(jm) >= 2:
                    candidate = _normalize_text(jm[1])
                    if candidate and len(candidate.split()) <= 6:
                        cleaned["judge_name"] = candidate

        if _NLP is not None:
            doc = _NLP(text)
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    cleaned["persons"].append(_normalize_text(ent.text))
                elif ent.label_ == "ORG":
                    cleaned["organizations"].append(_normalize_text(ent.text))
                elif ent.label_ in ("GPE", "LOC", "FAC"):
                    cleaned["addresses"].append(_normalize_text(ent.text))

        cleaned["persons"] = list(dict.fromkeys(cleaned["persons"]))
        cleaned["organizations"] = list(dict.fromkeys(cleaned["organizations"]))
        cleaned["addresses"] = list(dict.fromkeys(cleaned["addresses"]))

        if not cleaned["petitioner"] and lines:
            first = _normalize_text(lines[0])
            if len(first.split()) <= 8:
                cleaned["petitioner"] = first

        return (raw_candidates, cleaned) if return_raw else cleaned
    except Exception:
        empty = {
            "case_number": "",
            "fir_number": "",
            "date": "",
            "petitioner": "",
            "respondent": "",
            "appellant": "",
            "defendant": "",
            "plaintiff": "",
            "judge_name": "",
            "persons": [],
            "organizations": [],
            "addresses": [],
            "ipc_sections": [],
        }
        return (empty, empty) if return_raw else empty

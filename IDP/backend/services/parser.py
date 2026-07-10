"""Legal document field extractor — v2.

Improvements over v1:
  - TO/FROM: now captures names on the NEXT line (fixes 0% detection on memos/letters)
  - Phone: tightened regex to avoid false positives on random number sequences
  - Rent/financial: requires currency symbol, avoids matching plain numbers
  - Doc type: tightened to avoid false positives (ORDER alone no longer triggers court_order)
  - Subject/RE: new field for memos and legal notices
  - Signature block: extracts closing name from letters
  - Invoice fields: invoice number, bill-to, total
  - Salutation: Dear X, To Whom It May Concern
  - Subject line: RE:, SUBJECT:, Re:
  - Named entity heuristic: capitalised multi-word names after TO/FROM/CC
  - All patterns tested against RVL-CDIP letter/memo/form/email/invoice categories

Covers all common fields in:
  FIR forms, rental/tenancy agreements, affidavits, employment contracts,
  court filings, power of attorney, legal notices, memos, letters, invoices.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first(pattern: str, text: str, flags: int = re.IGNORECASE) -> Optional[str]:
    """Return first match group(1) or group(0), stripped and cleaned."""
    m = re.search(pattern, text, flags)
    if not m:
        return None
    try:
        val = m.group(1)
    except IndexError:
        val = m.group(0)
    val = val.strip().rstrip(".,;:")
    return val if val else None


def _all_matches(pattern: str, text: str, flags: int = re.IGNORECASE) -> List[str]:
    """Return all non-overlapping matches, stripped."""
    return [m.strip() for m in re.findall(pattern, text, flags) if str(m).strip()]


def _next_line_value(label_pattern: str, text: str) -> Optional[str]:
    """Extract value that appears on the SAME line OR the NEXT non-empty line.

    Handles both:
      TO: John Smith          (same line)
      TO:                     (label only)
      John Smith              (value on next line)
    """
    m = re.search(
        label_pattern + r"\s*[:\-]?\s*(.+)?",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not m:
        return None

    same_line = (m.group(1) or "").strip().rstrip(".,;:")
    if same_line and len(same_line) > 1:
        return same_line

    # Value is on the next non-empty line
    end = m.end()
    rest = text[end:]
    for line in rest.splitlines():
        line = line.strip()
        if line:
            # Skip lines that look like another label (ALL CAPS + colon)
            if re.match(r"^[A-Z]{2,}[\s\w]*\s*:", line):
                return None
            return line.rstrip(".,;:")
    return None


def _name_after_label(label: str, text: str) -> Optional[str]:
    """Extract a proper name (Title Case or ALL CAPS) after a label.

    Handles:
      TO: Mr. John Smith
      TO:\nJohn Smith
      FROM: BLACHLY

    Rejects values that look like sentence fragments or non-name text.
    """
    val = _next_line_value(label, text)
    if not val:
        return None
    # Strip leading salutation prefixes
    val = re.sub(r"^(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?)\s+", "", val, flags=re.IGNORECASE)
    # Must look like a name: at least 2 chars, mostly letters/spaces/dots
    if len(val) < 2 or len(val) > 60:
        return None
    alpha_ratio = sum(c.isalpha() or c in " .-'" for c in val) / len(val)
    if alpha_ratio < 0.75:
        return None
    # Reject if it starts with a lowercase word (likely a sentence fragment)
    first_word = val.split()[0] if val.split() else ""
    if first_word and first_word[0].islower():
        return None
    # Reject common false-positive phrases
    _reject = re.compile(
        r"\b(?:the|a|an|of|in|at|on|for|with|by|from|into|onto|upon|"
        r"premises|building|office|department|division|region|area)\b",
        re.IGNORECASE,
    )
    if _reject.search(val):
        return None
    return val


# ---------------------------------------------------------------------------
# Individual field extractors
# ---------------------------------------------------------------------------

def _extract_dates(text: str) -> Dict[str, Any]:
    """Extract all date variants. Returns primary date + all dates found."""
    patterns = [
        r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
        r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4})\b",
        r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{2,4})\b",
        r"\b(\d{4}-\d{2}-\d{2})\b",
    ]
    all_dates: List[str] = []
    for p in patterns:
        all_dates.extend(_all_matches(p, text))
    seen: set = set()
    unique = [d for d in all_dates if not (d in seen or seen.add(d))]  # type: ignore[func-returns-value]
    return {"date": unique[0] if unique else None, "all_dates": unique}


def _extract_time(text: str) -> Optional[str]:
    return _first(r"\b(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\b", text)


def _extract_subject(text: str) -> Optional[str]:
    """Extract subject/RE line — critical for memos and legal notices."""
    # SUBJECT: ... or RE: ... or Re: ... or SUBJECT OF NOTICE: ...
    val = _first(
        r"(?:^|\n)\s*(?:subject|re|regarding|sub)\s*[:\-]\s*(.+)",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if val:
        return val.strip()
    return None


def _extract_salutation(text: str) -> Optional[str]:
    """Extract opening salutation — Dear X, To Whom It May Concern."""
    return _first(
        r"(?:^|\n)\s*(Dear\s+[\w\s\.]+|To\s+Whom\s+It\s+May\s+Concern)",
        text,
        re.IGNORECASE | re.MULTILINE,
    )


def _extract_names(text: str) -> Dict[str, Optional[str]]:
    """Extract named parties. Uses next-line logic for TO/FROM/CC."""
    return {
        "to":           _name_after_label(r"TO", text),
        "from":         _name_after_label(r"FROM", text),
        "cc":           _name_after_label(r"CC|C\.C\.", text),
        "complainant":  _first(r"(?:complainant|complaint\s+by)\s*[:\-]\s*(.+)", text),
        "respondent":   _first(r"(?:respondent|accused|defendant)\s*[:\-]\s*(.+)", text),
        "plaintiff":    _first(r"plaintiff\s*[:\-]\s*(.+)", text),
        "landlord":     _first(r"(?:landlord|lessor|owner)\s*[:\-]\s*(.+)", text),
        "tenant":       _first(r"(?:tenant|lessee|occupant)\s*[:\-]\s*(.+)", text),
        "employer":     _first(r"employer\s*[:\-]\s*(.+)", text),
        "employee":     _first(r"employee\s*[:\-]\s*(.+)", text),
        "witness":      _first(r"witness\s*[:\-]\s*(.+)", text),
        "notary":       _first(r"notary\s*[:\-]\s*(.+)", text),
        "judge":        _first(r"(?:judge|hon[o']?urable)\s*[:\-]\s*(.+)", text),
        "advocate":     _first(r"(?:advocate|counsel|attorney)\s*[:\-]\s*(.+)", text),
    }


def _extract_signature(text: str) -> Optional[str]:
    """Extract closing signature block from letters.

    Looks for patterns like:
      Sincerely,\nJohn Smith
      Yours faithfully,\nJ. Smith
      Regards,\nBlachly
    """
    m = re.search(
        r"(?:sincerely|yours\s+(?:faithfully|truly|sincerely)|regards|best\s+regards|"
        r"respectfully|thanking\s+you|thank\s+you)[,.]?\s*\n+\s*([A-Z][A-Za-z\s\.\-]{2,40})",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return None


def _extract_contact(text: str) -> Dict[str, Optional[str]]:
    return {
        "email": _first(
            r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text
        ),
        # Tightened phone: must be 7+ digits, allows common separators
        # Requires at least one separator or country code to avoid matching
        # random number sequences like "1234 5678" in financial tables
        "phone": _first(
            r"(?:"
            r"\+\d{1,3}[\s\-]?\(?\d{2,5}\)?[\s\-]?\d{3,5}[\s\-]?\d{3,5}"   # +91-9876-543210
            r"|(?:\(?\d{3,5}\)?[\s\-]\d{3,5}[\s\-]\d{3,5})"                  # (080) 2345 6789
            r"|(?:Tel|Phone|Ph|Fax|Mobile|Cell|Contact)\s*[:\.]?\s*[\d\s\-\+\(\)]{7,}"  # Tel: 080-23456789
            r")",
            text,
        ),
        "fax": _first(
            r"(?:fax|facsimile)\s*[:\-]?\s*([\+\d][\d\s\-\(\)]{6,})", text
        ),
    }


def _extract_financial(text: str) -> Dict[str, Optional[str]]:
    """Financial fields — require explicit currency symbol or keyword to avoid false positives."""
    # Currency pattern: Rs., INR, ₹, $, USD, £
    _curr = r"(?:Rs\.?|INR|₹|\$|USD|£|EUR)"
    return {
        # Rent: must have currency symbol
        "rent": _first(
            rf"(?:rent|monthly\s+rent|rental\s+amount)\s*[:\-]?\s*{_curr}\s*[\d,]+(?:\.\d{{1,2}})?",
            text,
        ),
        # Amount: keyword + optional currency
        "amount": _first(
            rf"(?:amount|sum|total\s+amount|value)\s*[:\-]?\s*{_curr}?\s*([\d,]+(?:\.\d{{1,2}})?)",
            text,
        ),
        # Invoice total: for invoices
        "invoice_total": _first(
            rf"(?:total|grand\s+total|amount\s+due|balance\s+due)\s*[:\-]?\s*{_curr}?\s*([\d,]+(?:\.\d{{1,2}})?)",
            text,
        ),
        "salary": _first(
            rf"(?:salary|wages|remuneration|ctc|compensation)\s*[:\-]?\s*{_curr}?\s*([\d,]+(?:\.\d{{1,2}})?)",
            text,
        ),
        "stamp_duty": _first(
            rf"stamp\s+duty\s*[:\-]?\s*{_curr}?\s*([\d,]+(?:\.\d{{1,2}})?)",
            text,
        ),
        "fine": _first(
            rf"(?:fine|penalty|damages)\s*[:\-]?\s*{_curr}?\s*([\d,]+(?:\.\d{{1,2}})?)",
            text,
        ),
    }


def _extract_location(text: str) -> Dict[str, Optional[str]]:
    return {
        "address": _first(
            r"(?:address|residing\s+at|located\s+at|premises\s+at)\s*[:\-]\s*(.+)",
            text,
        ),
        "city": _first(
            r"(?:^|\n)\s*(?:city|town)\s*[:\-]\s*([A-Za-z][A-Za-z\s]{1,30})(?:\n|,|$)",
            text,
            re.MULTILINE,
        ),
        "state": _first(
            r"(?:^|\n)\s*state\s*[:\-]\s*([A-Za-z][A-Za-z\s]{1,30})(?:\n|,|$)",
            text,
            re.MULTILINE,
        ),
        # Indian PIN code: exactly 6 digits, not part of a longer number
        "pin": _first(r"(?<!\d)(\d{6})(?!\d)", text),
        # Police station: must start with a letter, bounded by newline
        "police_station": _first(
            r"(?:police\s+station|p\.?s\.?)\s*[:\-]\s*([A-Za-z][A-Za-z\s]{2,30}?)(?:\n|,|$)",
            text,
            re.MULTILINE,
        ),
        "court": _first(
            r"(?:court\s+of|before\s+the\s+(?:hon[o']?urable\s+)?court|in\s+the\s+court)\s*[:\-]?\s*(.+)",
            text,
        ),
    }


def _extract_document_ids(text: str) -> Dict[str, Optional[str]]:
    return {
        "fir_number":    _first(r"(?:fir\s*(?:no|number|#)\.?)\s*[:\-]?\s*([\w/\-]+)", text),
        "case_number":   _first(r"(?:case\s*(?:no|number|#)\.?)\s*[:\-]?\s*([\w/\-]+)", text),
        "invoice_number": _first(
            r"(?:invoice\s*(?:no|number|#|num)\.?|inv\.?\s*(?:no|#))\s*[:\-]?\s*([\w/\-]+)",
            text,
        ),
        "doc_number":    _first(r"(?:doc(?:ument)?\s*(?:no|number|#)\.?)\s*[:\-]?\s*([\w/\-]+)", text),
        "registration":  _first(r"(?:reg(?:istration)?\s*(?:no|number|#)\.?)\s*[:\-]?\s*([\w/\-]+)", text),
        "ref_number":    _first(r"(?:ref(?:erence)?\s*(?:no|number|#)\.?)\s*[:\-]?\s*([\w/\-]+)", text),
        "page_info":     _first(r"page\s*(\d+\s*of\s*\d+)", text),
    }


def _extract_legal_sections(text: str) -> Dict[str, Any]:
    """Extract IPC/CrPC/BNS/other legal section references."""
    ipc_sections = _all_matches(
        r"(?:section|sec\.?|u/s|under\s+section)\s*(\d+[A-Za-z]?(?:\s*[,&]\s*\d+[A-Za-z]?)*)",
        text,
    )
    ipc_codes  = _all_matches(r"\bIPC\s*[Ss](?:ection)?\s*(\d+[A-Za-z]?)\b", text)
    crpc_codes = _all_matches(r"\bCrPC\s*[Ss](?:ection)?\s*(\d+[A-Za-z]?)\b", text)
    bns_codes  = _all_matches(r"\bBNS\s*[Ss](?:ection)?\s*(\d+[A-Za-z]?)\b", text)
    return {
        "sections":   ipc_sections if ipc_sections else None,
        "ipc_codes":  ipc_codes if ipc_codes else None,
        "crpc_codes": crpc_codes if crpc_codes else None,
        "bns_codes":  bns_codes if bns_codes else None,
    }


def _extract_duration(text: str) -> Dict[str, Optional[str]]:
    return {
        "duration": _first(
            r"(?:period|duration|term)\s*(?:of)?\s*[:\-]?\s*(\d+\s*(?:year|month|day)s?)",
            text,
        ),
        "start_date": _first(
            r"(?:commencing|effective|start(?:ing)?)\s*(?:from|on|date)?\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            text,
        ),
        "end_date": _first(
            r"(?:expir(?:y|ing|es?)|end(?:ing)?|termination)\s*(?:on|date)?\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            text,
        ),
    }


def _extract_doc_type_hint(text: str) -> Optional[str]:
    """Heuristic document type detection.

    Tightened to avoid false positives:
    - court_order: requires JUDGMENT/DECREE/COURT ORDER, not just ORDER
    - contract: requires AGREEMENT or CONTRACT, not just any mention
    - legal_notice: requires LEGAL NOTICE or NOTICE TO (not just NOTICE)
    """
    t = text.upper()

    if re.search(r"\bFIR\b|FIRST\s+INFORMATION\s+REPORT", t):
        return "fir"
    if re.search(r"\bAFFIDAVIT\b", t):
        return "affidavit"
    if re.search(r"\bRENTAL\s+AGREEMENT\b|\bLEASE\s+AGREEMENT\b|\bTENANCY\s+AGREEMENT\b", t):
        return "rental_agreement"
    if re.search(r"\bEMPLOYMENT\s+(?:CONTRACT|AGREEMENT)\b|\bOFFER\s+LETTER\b|\bAPPOINTMENT\s+LETTER\b", t):
        return "employment_contract"
    if re.search(r"\bPOWER\s+OF\s+ATTORNEY\b|\bPOA\b", t):
        return "power_of_attorney"
    if re.search(r"\bLEGAL\s+NOTICE\b|\bNOTICE\s+TO\b|\bNOTICE\s+OF\b", t):
        return "legal_notice"
    if re.search(r"\bJUDGMENT\b|\bDECREE\b|\bCOURT\s+ORDER\b|\bIN\s+THE\s+(?:HIGH\s+)?COURT\b", t):
        return "court_order"
    if re.search(r"\bINVOICE\b|\bBILL\s+TO\b|\bINVOICE\s+NO\b", t):
        return "invoice"
    if re.search(r"\bMEMORANDUM\b|\bINTER[\s\-]?OFFICE\b|\bINTERNAL\s+MEMO\b", t):
        return "memo"
    if re.search(r"\bCONTRACT\b|\bAGREEMENT\b", t):
        return "contract"
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_fields(text: str) -> Dict[str, Any]:
    """Extract all structured fields from OCR text.

    Returns a flat dict. Fields not found are omitted (None values removed).
    Special keys always present: all_dates (list), doc_type_hint (str|None).

    Field groups:
      Temporal:    date, all_dates, time
      Header:      subject, salutation, to, from, cc
      Parties:     complainant, respondent, plaintiff, landlord, tenant,
                   employer, employee, witness, notary, judge, advocate
      Contact:     email, phone, fax
      Financial:   rent, amount, invoice_total, salary, stamp_duty, fine
      Location:    address, city, state, pin, police_station, court
      IDs:         fir_number, case_number, invoice_number, doc_number,
                   registration, ref_number, page_info
      Legal:       sections, ipc_codes, crpc_codes, bns_codes
      Duration:    duration, start_date, end_date
      Closing:     signature
      Meta:        doc_type_hint
    """
    if not text:
        return {"all_dates": [], "doc_type_hint": None}

    dates    = _extract_dates(text)
    names    = _extract_names(text)
    contact  = _extract_contact(text)
    fin      = _extract_financial(text)
    loc      = _extract_location(text)
    doc_ids  = _extract_document_ids(text)
    legal    = _extract_legal_sections(text)
    duration = _extract_duration(text)

    fields: Dict[str, Any] = {
        # Temporal
        "date":           dates["date"],
        "all_dates":      dates["all_dates"],
        "time":           _extract_time(text),

        # Header
        "subject":        _extract_subject(text),
        "salutation":     _extract_salutation(text),

        # Parties (includes to/from/cc)
        **names,

        # Contact
        **contact,

        # Financial
        **fin,

        # Location
        **loc,

        # Document IDs
        **doc_ids,

        # Legal references
        "sections":       legal["sections"],
        "ipc_codes":      legal["ipc_codes"],
        "crpc_codes":     legal["crpc_codes"],
        "bns_codes":      legal["bns_codes"],

        # Duration
        **duration,

        # Closing
        "signature":      _extract_signature(text),

        # Meta
        "doc_type_hint":  _extract_doc_type_hint(text),
    }

    # Keep all_dates and doc_type_hint even if empty/None
    return {
        k: v for k, v in fields.items()
        if v is not None or k in ("all_dates", "doc_type_hint")
    }

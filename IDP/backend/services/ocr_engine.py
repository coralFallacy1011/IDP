"""OCR engine with multilingual support.

Supports two backends:
- Tesseract (default): fast, good for English + Indian scripts with language packs
- PaddleOCR (optional): better for degraded/rotated docs, strong multilingual support

Multilingual language codes (Tesseract):
  English:    eng
  Hindi:      hin
  Tamil:      tam
  Telugu:     tel
  Kannada:    kan
  Malayalam:  mal
  Bengali:    ben
  Gujarati:   guj
  Punjabi:    pan
  Marathi:    mar  (uses hin tessdata)
  Urdu:       urd
  Arabic:     ara

Install language packs:
  brew install tesseract-lang          # macOS — installs all packs
  sudo apt install tesseract-ocr-hin   # Ubuntu — per language

PaddleOCR install (optional, for research comparison):
  pip install paddlepaddle paddleocr
"""

from __future__ import annotations

import re
import os
from typing import Dict, List, Optional, Tuple

import pytesseract
from PIL import Image
from rapidfuzz import fuzz

# Point pytesseract to Tesseract executable (update path if installed elsewhere)
_TESSERACT_PATHS = [
    r"D:\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]
for _p in _TESSERACT_PATHS:
    if os.path.exists(_p):
        pytesseract.pytesseract.tesseract_cmd = _p
        break

# ---------------------------------------------------------------------------
# Legal keyword vocabulary (English + transliterated common terms)
# ---------------------------------------------------------------------------
LEGAL_TERMS_EN = [
    "AFFIDAVIT", "AGREEMENT", "NOTICE", "LANDLORD", "TENANT",
    "EMPLOYER", "DEED", "POWER OF ATTORNEY", "CONTRACT", "PETITION",
    "PLAINTIFF", "DEFENDANT", "COMPLAINANT", "RESPONDENT", "WITNESS",
    "NOTARY", "JURISDICTION", "ARBITRATION", "INDEMNITY", "COVENANT",
]

# Hindi legal terms (Devanagari) — used for post-correction in Hindi docs
LEGAL_TERMS_HI = [
    "शपथपत्र", "अनुबंध", "नोटिस", "मकान मालिक", "किरायेदार",
    "नियोक्ता", "विलेख", "मुख्तारनामा", "अनुबंध", "याचिका",
]

# Tesseract language pack → script family mapping
_LANG_SCRIPT: Dict[str, str] = {
    "eng": "latin", "hin": "devanagari", "mar": "devanagari",
    "tam": "tamil", "tel": "telugu", "kan": "kannada",
    "mal": "malayalam", "ben": "bengali", "guj": "gujarati",
    "pan": "gurmukhi", "urd": "arabic", "ara": "arabic",
}

# Default Tesseract config per script family
_SCRIPT_CONFIG: Dict[str, str] = {
    "latin":       "--oem 3 --psm 4",
    "devanagari":  "--oem 1 --psm 4",   # LSTM only — better for Devanagari
    "tamil":       "--oem 1 --psm 4",
    "telugu":      "--oem 1 --psm 4",
    "kannada":     "--oem 1 --psm 4",
    "malayalam":   "--oem 1 --psm 4",
    "bengali":     "--oem 1 --psm 4",
    "gujarati":    "--oem 1 --psm 4",
    "gurmukhi":    "--oem 1 --psm 4",
    "arabic":      "--oem 1 --psm 4",
}


def _get_config(lang: str, psm: int, oem: int) -> str:
    """Build Tesseract config string, using script-optimised OEM if not overridden."""
    script = _LANG_SCRIPT.get(lang, "latin")
    default_cfg = _SCRIPT_CONFIG.get(script, f"--oem {oem} --psm {psm}")
    # Allow caller to override psm while keeping script-optimal oem
    cfg = re.sub(r"--psm \d+", f"--psm {psm}", default_cfg)
    return cfg


# ---------------------------------------------------------------------------
# Garbage token filter
# ---------------------------------------------------------------------------

# Tokens that are almost certainly OCR noise — single non-alphanumeric chars,
# pure symbol strings, or known Tesseract artefacts.
_GARBAGE_PATTERN = re.compile(
    r"^(?:"
    r"[^A-Za-z0-9\u0900-\u0D7F\u0600-\u06FF]{1,2}"   # 1-2 non-alphanumeric chars
    r"|[«»§¶©®™°±×÷√∞≈≠≤≥←→↑↓]+"                     # unicode symbols
    r"|[|\\/<>~`^]{2,}"                                 # repeated special chars
    r"|@{2,}"                                            # double @
    r")$"
)

# Tokens that look like pure noise even if they have letters:
# e.g. "Bt:", "«=", single letters with punctuation like "K." are kept
# but things like "PSOS", "PTLD" with conf < 50 are filtered by confidence.
_MIN_CONF_DEFAULT = 45.0   # raised from 25 — eliminates most garbage tokens
_MIN_CONF_STRICT  = 60.0   # use for clean_text (higher quality output)


def _is_garbage(token: str) -> bool:
    """Return True if the token is almost certainly OCR noise."""
    if not token:
        return True
    # Pure punctuation / symbol strings
    if _GARBAGE_PATTERN.match(token):
        return True
    # Tokens with no alphanumeric characters at all
    if not re.search(r"[A-Za-z0-9\u0900-\u0D7F]", token):
        return True
    # Short all-caps tokens with no vowels — classic OCR noise (e.g. PSOS, PTLD, Bt)
    # Exception: known abbreviations like TO, FROM, FIR, IPC, NO, ID, OK
    _KNOWN_ABBREVS = {"TO", "FROM", "FIR", "IPC", "NO", "ID", "OK", "PS",
                      "MR", "MS", "DR", "VS", "RE", "CC", "BCC", "PO", "PIN"}
    alpha_only = re.sub(r"[^A-Za-z]", "", token)
    if (2 <= len(alpha_only) <= 5
            and alpha_only.isupper()
            and not re.search(r"[AEIOU]", alpha_only)
            and alpha_only not in _KNOWN_ABBREVS):
        return True
    return False


def extract_text_and_boxes(
    path: str,
    *,
    psm: int = 4,
    oem: int = 3,
    lang: str = "eng",
    min_conf: float = _MIN_CONF_DEFAULT,
    strict: bool = False,
) -> Tuple[str, List[Dict]]:
    """Run Tesseract OCR and return (text, word_boxes).

    Args:
        path:     Path to the (preprocessed) image.
        psm:      Tesseract page segmentation mode. 4 = single column (default).
                  Use 6 for uniform blocks, 11 for sparse text.
        oem:      OCR engine mode. Overridden per-script for non-Latin scripts.
        lang:     Tesseract language code(s). Use '+' for multi-language:
                  e.g. "eng+hin" for bilingual English/Hindi documents.
        min_conf: Minimum word confidence to include (0-100).
                  Default raised to 45 to filter garbage tokens like «=, PSOS.
        strict:   If True, use min_conf=60 for highest-quality clean_text output.

    Returns:
        text:  Cleaned extracted text with line breaks preserved.
        boxes: List of word dicts with keys: text, conf, x, y, w, h.
               Only includes words that passed the confidence + garbage filter.
    """
    if strict:
        min_conf = max(min_conf, _MIN_CONF_STRICT)

    img = Image.open(path)
    config = _get_config(lang, psm, oem)

    data = pytesseract.image_to_data(
        img,
        lang=lang,
        output_type=pytesseract.Output.DICT,
        config=config,
    )

    words: List[Dict] = []
    text_parts: List[str] = []
    last_line: Optional[Tuple] = None

    for i in range(len(data["text"])):
        word = data["text"][i].strip()
        try:
            conf_val = float(data["conf"][i])
        except (ValueError, TypeError):
            conf_val = -1.0

        # Filter 1: confidence threshold
        if not word or conf_val < min_conf:
            continue

        # Filter 2: garbage token detector
        if _is_garbage(word):
            continue

        try:
            line_id = (
                data["block_num"][i],
                data["par_num"][i],
                data["line_num"][i],
            )
        except (KeyError, IndexError):
            line_id = None

        if last_line is not None and line_id is not None and line_id != last_line:
            text_parts.append("\n")
        last_line = line_id

        text_parts.append(word)
        words.append({
            "text": word,
            "conf": conf_val,
            "x": data["left"][i],
            "y": data["top"][i],
            "w": data["width"][i],
            "h": data["height"][i],
        })

    text = " ".join(text_parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip(), words


def extract_text_paddleocr(
    path: str,
    *,
    lang: str = "en",
) -> Tuple[str, List[Dict]]:
    """PaddleOCR backend — optional, for research comparison.

    PaddleOCR language codes differ from Tesseract:
      en, ch, hi, ta, te, ka, mr, ar, ...

    Install: pip install paddlepaddle paddleocr

    Returns same (text, boxes) format as extract_text_and_boxes.
    """
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except ImportError:
        raise ImportError(
            "PaddleOCR is not installed. Run: pip install paddlepaddle paddleocr"
        )

    ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
    result = ocr.ocr(path, cls=True)

    words: List[Dict] = []
    lines: List[str] = []

    if result and result[0]:
        for line in result[0]:
            box_pts, (text, conf) = line
            xs = [p[0] for p in box_pts]
            ys = [p[1] for p in box_pts]
            words.append({
                "text": text,
                "conf": conf * 100,
                "x": int(min(xs)),
                "y": int(min(ys)),
                "w": int(max(xs) - min(xs)),
                "h": int(max(ys) - min(ys)),
            })
            lines.append(text)

    return "\n".join(lines), words


def detect_language_hint(text: str) -> str:
    """Heuristic language detection from extracted text.

    Returns a Tesseract language code hint. Useful for auto-selecting
    the right language pack for a second-pass OCR.

    This is a lightweight character-range check — for production use,
    replace with langdetect or lingua-language-detector.
    """
    if not text:
        return "eng"

    devanagari = sum(1 for c in text if "\u0900" <= c <= "\u097F")
    tamil      = sum(1 for c in text if "\u0B80" <= c <= "\u0BFF")
    telugu     = sum(1 for c in text if "\u0C00" <= c <= "\u0C7F")
    kannada    = sum(1 for c in text if "\u0C80" <= c <= "\u0CFF")
    malayalam  = sum(1 for c in text if "\u0D00" <= c <= "\u0D7F")
    bengali    = sum(1 for c in text if "\u0980" <= c <= "\u09FF")
    gujarati   = sum(1 for c in text if "\u0A80" <= c <= "\u0AFF")
    gurmukhi   = sum(1 for c in text if "\u0A00" <= c <= "\u0A7F")
    arabic     = sum(1 for c in text if "\u0600" <= c <= "\u06FF")

    scores = {
        "hin": devanagari, "tam": tamil, "tel": telugu,
        "kan": kannada, "mal": malayalam, "ben": bengali,
        "guj": gujarati, "pan": gurmukhi, "urd": arabic,
    }
    best_lang = max(scores, key=lambda k: scores[k])
    return best_lang if scores[best_lang] > 5 else "eng"


def legal_keyword_correction(text: str, *, threshold: int = 92, lang: str = "eng") -> str:
    """Conservative correction for common legal header terms.

    Only rewrites tokens that are:
    - Mostly uppercase (likely headings/keywords)
    - At least 5 characters long
    - Match a known legal term with high fuzzy similarity

    For non-English documents, skips correction (Devanagari/Tamil etc.
    tokens won't match English legal terms).
    """
    # Skip correction for non-Latin scripts
    script = _LANG_SCRIPT.get(lang, "latin")
    if script != "latin":
        return text

    terms = LEGAL_TERMS_EN
    tokens = re.split(r"(\s+)", text or "")
    out: List[str] = []

    for tok in tokens:
        if tok.isspace() or not tok:
            out.append(tok)
            continue

        stripped = re.sub(r"[^A-Za-z ]", "", tok)
        if len(stripped) < 5:
            out.append(tok)
            continue

        alpha = re.sub(r"[^A-Za-z]", "", tok)
        if not alpha:
            out.append(tok)
            continue

        upper_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)
        if upper_ratio < 0.8:
            out.append(tok)
            continue

        best_term = tok
        best_score = 0
        for term in terms:
            score = fuzz.ratio(stripped.upper(), term)
            if score > best_score:
                best_term = term
                best_score = score

        out.append(best_term if best_score >= threshold else tok)

    text = "".join(out)
    return re.sub(r"\s+", " ", text).strip()

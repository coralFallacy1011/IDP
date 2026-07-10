"""Document classification service using HuggingFace zero-shot classifier.

Falls back gracefully if the model cannot be loaded or inference fails.
"""
from typing import Dict

LABELS = [
    "FIR",
    "Contract",
    "Affidavit",
    "Court Judgment",
    "Property Record",
    "Legal Notice",
    "Other",
]


def _load_pipeline():
    try:
        from transformers import pipeline

        # facebook/bart-large-mnli is a robust zero-shot classifier
        return pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    except Exception:
        return None


_ZSP = None


def classify(text: str) -> Dict:
    """Classify a document string into one of LABELS.

    Returns: {"document_type": str, "confidence": float}
    If classification fails, returns {"document_type": "Other", "confidence": 0.0}
    """
    global _ZSP
    if _ZSP is None:
        _ZSP = _load_pipeline()

    if not text or _ZSP is None:
        return {"document_type": "Other", "confidence": 0.0}

    try:
        # For long documents, make a best-effort by using the leading 5120 characters
        # zero-shot works best on reasonably short inputs.
        snippet = text.strip()[:5000]
        out = _ZSP(snippet, LABELS, multi_label=False)
        label = out.get("labels", [None])[0]
        score = out.get("scores", [0.0])[0]
        if label is None:
            return {"document_type": "Other", "confidence": 0.0}
        return {"document_type": label, "confidence": float(score)}
    except Exception:
        return {"document_type": "Other", "confidence": 0.0}

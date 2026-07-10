"""Document summarization service using HuggingFace transformers.

Provides short description and a longer executive summary.
Falls back to returning OCR text if summarization fails.
"""
from typing import Dict


def _load_summarizer():
    try:
        from transformers import pipeline
        # prefer bart-large-cnn; flan-t5-base is an alternative
        return pipeline("summarization", model="facebook/bart-large-cnn")
    except Exception:
        try:
            from transformers import pipeline
            return pipeline("summarization", model="google/flan-t5-base")
        except Exception:
            return None


_SUM = None


def summarize(text: str) -> Dict:
    """Return {"short_description": str, "summary": str}.

    If summarization fails, return OCR text as summary and an empty short description.
    """
    global _SUM
    if _SUM is None:
        _SUM = _load_summarizer()

    if not text:
        return {"short_description": "", "summary": ""}

    if _SUM is None:
        return {"short_description": "", "summary": text[:2000]}

    try:
        # Keep a reasonable token window: chunk text if needed
        snippet = text.strip()[:8000]
        out = _SUM(snippet, max_length=300, min_length=80, do_sample=False)
        summary_text = out[0]["summary_text"] if out and isinstance(out, list) else ""
        # short description: first sentence or 140 chars
        short = (summary_text.split(".")[0] + ".") if "." in summary_text else summary_text[:140]
        return {"short_description": short.strip(), "summary": summary_text.strip()}
    except Exception:
        return {"short_description": "", "summary": text[:2000]}

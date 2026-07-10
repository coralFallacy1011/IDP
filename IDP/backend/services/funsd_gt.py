import json
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class FUNSDExample:
    """Represents a single FUNSD sample.

    We expose:
    - full_text: concatenated text of all words in natural reading order (approx).
    - kv_pairs: mapping of question-text -> answer-text based on `linking`.
    """

    id: str
    full_text: str
    kv_pairs: Dict[str, str]


def _normalize_space(s: str) -> str:
    return " ".join((s or "").split())


def load_funsd_annotation(json_path: str) -> FUNSDExample:
    """Load FUNSD annotation JSON (one file) into text + key-value pairs."""

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    form = data.get("form", [])

    # Build per-entity text and store label.
    ent_text: Dict[int, str] = {}
    ent_label: Dict[int, str] = {}
    links: List[Tuple[int, int]] = []

    for ent in form:
        ent_id = int(ent.get("id"))
        ent_label[ent_id] = ent.get("label", "other")

        # Prefer entity-level text if present, else concatenate words.
        raw_text = ent.get("text") or ""
        if not raw_text.strip():
            words = ent.get("words") or []
            raw_text = " ".join((w.get("text") or "") for w in words)
        ent_text[ent_id] = _normalize_space(raw_text)

        for a, b in ent.get("linking") or []:
            links.append((int(a), int(b)))

    # full-page text: concat all entity texts that have content.
    full_text = _normalize_space(" ".join(t for t in ent_text.values() if t))

    # KV pairs: for each (question, answer) linked pair.
    kv_pairs: Dict[str, str] = {}
    for a, b in links:
        # Identify which side is question/answer to make mapping stable.
        if ent_label.get(a) == "question" and ent_label.get(b) == "answer":
            qid, aid = a, b
        elif ent_label.get(b) == "question" and ent_label.get(a) == "answer":
            qid, aid = b, a
        else:
            continue

        q = ent_text.get(qid, "").strip()
        a_txt = ent_text.get(aid, "").strip()
        if q:
            kv_pairs[q] = a_txt

    sample_id = os.path.splitext(os.path.basename(json_path))[0]
    return FUNSDExample(id=sample_id, full_text=full_text, kv_pairs=kv_pairs)


def load_funsd_dataset(annotations_dir: str, limit: int | None = None) -> List[FUNSDExample]:
    """Load all FUNSD annotation files from a directory."""

    files = sorted(
        f for f in os.listdir(annotations_dir) if f.lower().endswith(".json")
    )
    if limit is not None:
        files = files[:limit]

    return [load_funsd_annotation(os.path.join(annotations_dir, f)) for f in files]

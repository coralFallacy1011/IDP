from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, Iterable, Tuple


def _norm_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def cer(gt: str, pred: str) -> float:
    """Character error rate: 1 - similarity ratio."""

    gt = _norm_text(gt)
    pred = _norm_text(pred)
    if not gt and not pred:
        return 0.0
    return 1.0 - _ratio(gt, pred)


def wer(gt: str, pred: str) -> float:
    """Word error rate using SequenceMatcher over tokens."""

    gt_words = _norm_text(gt).split()
    pr_words = _norm_text(pred).split()
    if not gt_words and not pr_words:
        return 0.0
    return 1.0 - SequenceMatcher(None, gt_words, pr_words).ratio()


@dataclass
class PRF1:
    precision: float
    recall: float
    f1: float


def prf1(tp: int, fp: int, fn: int) -> PRF1:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * p * r) / (p + r) if (p + r) else 0.0
    return PRF1(precision=p, recall=r, f1=f1)


def kv_pair_f1(gt: Dict[str, str], pred: Dict[str, str]) -> Tuple[int, int, int, PRF1]:
    """Exact-match key-value evaluation.

    - A predicted (k,v) counts as TP if k exists in gt and normalized v matches.
    - FP if k not in gt or v doesn't match.
    - FN for any gt key missing from pred.

    This is intentionally strict (research-friendly baseline).
    """

    gt_n = { _norm_text(k): _norm_text(v) for k,v in (gt or {}).items() }
    pr_n = { _norm_text(k): _norm_text(v) for k,v in (pred or {}).items() }

    tp = 0
    fp = 0
    for k, v in pr_n.items():
        if k in gt_n and v == gt_n[k]:
            tp += 1
        else:
            fp += 1

    fn = sum(1 for k in gt_n.keys() if k not in pr_n)
    return tp, fp, fn, prf1(tp, fp, fn)


def approx_kv_pair_f1(
    gt: Dict[str, str],
    pred: Dict[str, str],
    key_match_threshold: float = 0.85,
    val_match_threshold: float = 0.85,
) -> Tuple[int, int, int, PRF1]:
    """Fuzzy key-value evaluation using similarity thresholds.

    Matches each predicted key to the best GT key (greedy) by SequenceMatcher ratio.
    """

    gt_items = [(_norm_text(k), _norm_text(v)) for k, v in (gt or {}).items() if _norm_text(k)]
    pr_items = [(_norm_text(k), _norm_text(v)) for k, v in (pred or {}).items() if _norm_text(k)]

    used_gt: set[str] = set()
    tp = 0
    fp = 0

    for pk, pv in pr_items:
        best = None
        best_score = 0.0
        for gk, gv in gt_items:
            if gk in used_gt:
                continue
            sc = _ratio(pk.lower(), gk.lower())
            if sc > best_score:
                best_score = sc
                best = (gk, gv)

        if best is None or best_score < key_match_threshold:
            fp += 1
            continue

        gk, gv = best
        used_gt.add(gk)

        vs = _ratio(pv.lower(), gv.lower()) if (pv or gv) else 1.0
        if vs >= val_match_threshold:
            tp += 1
        else:
            fp += 1

    fn = max(0, len(gt_items) - len(used_gt))
    return tp, fp, fn, prf1(tp, fp, fn)

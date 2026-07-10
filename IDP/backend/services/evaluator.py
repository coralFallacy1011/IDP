from difflib import SequenceMatcher

def cer(gt, pred):
    return 1 - SequenceMatcher(None, gt, pred).ratio()

def wer(gt, pred):
    gt_words = gt.split()
    pr_words = pred.split()
    return 1 - SequenceMatcher(None, gt_words, pr_words).ratio()
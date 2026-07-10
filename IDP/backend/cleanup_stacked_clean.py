"""One-time cleanup: remove all _clean*.png files from dataset/images.

These were created by the old preprocess_image() which wrote output
alongside the source file. The new version writes to preprocessed_cache/.

Run once from the backend/ directory:
    python cleanup_stacked_clean.py [--dry-run]
"""

import argparse
import os
import re

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "images")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Print files that would be deleted without deleting them")
    args = ap.parse_args()

    pattern = re.compile(r"_clean.*\.png$", re.IGNORECASE)

    deleted = 0
    for fname in sorted(os.listdir(IMAGES_DIR)):
        if pattern.search(fname):
            fpath = os.path.join(IMAGES_DIR, fname)
            if args.dry_run:
                print(f"[dry-run] would delete: {fname}")
            else:
                os.remove(fpath)
                print(f"deleted: {fname}")
            deleted += 1

    action = "Would delete" if args.dry_run else "Deleted"
    print(f"\n{action} {deleted} stacked _clean files.")
    if args.dry_run:
        print("Run without --dry-run to actually delete them.")


if __name__ == "__main__":
    main()

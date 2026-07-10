"""Image preprocessing for OCR.

Key design decisions:
- Preprocessed images are ALWAYS written to a dedicated temp directory
  (backend/preprocessed_cache/) rather than alongside the source file.
  This prevents the _clean_clean_clean... pollution that occurs when the
  same image is preprocessed multiple times.
- The output filename is a flat hash of the absolute source path so
  repeated calls return the same cached file without re-processing.
- Multilingual support: the pipeline is language-agnostic at the image
  level; language selection happens in the OCR engine (Tesseract lang param).
"""

import hashlib
import os
import tempfile

import cv2
import numpy as np

# All preprocessed images land here — never in the source directory.
_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "preprocessed_cache")


def _ensure_cache_dir() -> str:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    return _CACHE_DIR


def _cache_path(source_path: str) -> str:
    """Deterministic output path based on source file's absolute path."""
    key = hashlib.md5(os.path.abspath(source_path).encode()).hexdigest()
    return os.path.join(_ensure_cache_dir(), f"{key}_clean.png")


def _preprocess_variant(gray: np.ndarray, *, block_size: int, c: int, denoise_h: int) -> np.ndarray:
    if denoise_h and denoise_h > 0:
        gray = cv2.fastNlMeansDenoising(gray, None, denoise_h, 7, 21)

    gray = deskew(gray)

    if block_size % 2 == 0:
        block_size += 1
    block_size = max(3, block_size)

    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        c,
    )
    white_ratio = float((thresh > 0).mean())
    if white_ratio < 0.05 or white_ratio > 0.95:
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def deskew(gray: np.ndarray) -> np.ndarray:
    """Correct skew by finding the orientation of text elements.

    Uses horizontal morphological dilation to group characters into text lines
    and minAreaRect to calculate the skew angle accurately.
    """
    # 1. Binarize a copy: text is white, background is black for coordinates
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    
    # 2. Dilate horizontally to merge letters into line regions
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
    dilated = cv2.dilate(thresh, kernel, iterations=2)
    
    # 3. Find coordinates of all foreground text pixels
    coords = np.column_stack(np.where(dilated > 0))
    if len(coords) < 10:
        return gray
        
    # 4. Find minAreaRect angle
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    elif angle > 45:
        angle = 90 - angle
    else:
        angle = -angle
        
    # Skip tiny corrections (prevent false-rotation blur on straight documents)
    if abs(angle) < 1.5 or abs(angle) > 45:
        return gray
        
    (h, w) = gray.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h),
                          flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def upscale_if_small(img: np.ndarray, min_height: int = 1400) -> np.ndarray:
    """Upscale images that are too small for reliable OCR.

    Tesseract performs best on images where text height is ~30-40px.
    Upscaling low-res scans significantly improves CER/WER.

    Threshold raised to 1400px: FUNSD images are ~1000px and benefit
    from 2x upscaling even though they exceed the old 1000px threshold.
    """
    h, w = img.shape[:2]
    if h < min_height:
        scale = min_height / h
        img = cv2.resize(img, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_CUBIC)
    return img


def preprocess_image(
    path: str,
    *,
    denoise_h: int = 10,
    threshold_block_size: int = 31,
    threshold_C: int = 11,
    apply_sharpen: bool = False,
    auto_select: bool = True,
    use_cache: bool = True,
    grayscale_only: bool = False,
) -> str:
    """Preprocess a scanned document image for OCR.

    Pipeline (in order):
    1. Upscale if image is too small (< 1400px tall)
    2. Convert to grayscale
    3. Apply robust text-line deskewing
    4. Bilateral edge-preserving denoising (if denoise_h > 0)
    5. CLAHE contrast normalisation
    6. If grayscale_only=True: skip binarisation, apply optional unsharp masking and return
    7. Adaptive binarisation (auto-selects best params if auto_select=True)
    8. Fallback to grayscale if binarisation is too extreme
    9. Unsharp mask sharpening

    Output is written to backend/preprocessed_cache/ — NEVER alongside the
    source file.

    Returns the path to the preprocessed image.
    """
    # Include mode in cache key so grayscale_only and binarised don't collide
    mode_tag = "gray" if grayscale_only else "bin"
    key = hashlib.md5(
        (os.path.abspath(path) + mode_tag).encode()
    ).hexdigest()
    out_path = os.path.join(_ensure_cache_dir(), f"{key}_clean.png")

    if use_cache and os.path.exists(out_path):
        return out_path

    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Could not read image: {path}")

    # Step 1: upscale small images
    img = upscale_if_small(img, min_height=1400)

    # Step 2: grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Step 3: deskew (aligned before noise filter)
    gray = deskew(gray)

    # Step 4: Bilateral filter for edge-preserving denoising (if requested)
    if denoise_h > 0:
        gray = cv2.bilateralFilter(gray, 5, 50, 50)

    # Step 5: CLAHE contrast normalisation
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Step 6: grayscale-only mode (skip binarisation)
    if grayscale_only:
        out_img = gray
        if apply_sharpen:
            blurred = cv2.GaussianBlur(out_img, (0, 0), 3)
            out_img = cv2.addWeighted(out_img, 1.5, blurred, -0.5, 0)
        cv2.imwrite(out_path, out_img)
        return out_path

    if auto_select:
        # Try parameter variants; pick the one with highest text-line variance.
        candidates = [
            (threshold_block_size, threshold_C, denoise_h),
            (31, 9, denoise_h),
            (41, 13, denoise_h),
            (51, 15, denoise_h),
            (31, 11, 0),          # no denoising
            (21, 7, 0),           # fine-grained
        ]

        best: np.ndarray | None = None
        best_score = -1.0
        for bs, c, dh in candidates:
            th = _preprocess_variant(gray.copy(), block_size=bs, c=c, denoise_h=dh)
            proj = (255 - th).mean(axis=1)
            score = float(proj.var())
            if score > best_score:
                best_score = score
                best = th

        thresh = best if best is not None else _preprocess_variant(
            gray, block_size=threshold_block_size, c=threshold_C, denoise_h=denoise_h
        )
    else:
        thresh = _preprocess_variant(
            gray, block_size=threshold_block_size, c=threshold_C, denoise_h=denoise_h
        )

    # Fallback: if binarisation is too extreme, use CLAHE grayscale
    white_ratio_final = float((thresh > 0).mean())
    if white_ratio_final < 0.10 or white_ratio_final > 0.92:
        out_img = gray
    else:
        out_img = thresh

    # Optional unsharp mask
    if apply_sharpen:
        blurred = cv2.GaussianBlur(out_img, (0, 0), 3)
        out_img = cv2.addWeighted(out_img, 1.5, blurred, -0.5, 0)

    cv2.imwrite(out_path, out_img)
    return out_path
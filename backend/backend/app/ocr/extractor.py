"""app/ocr/extractor.py – OCR extraction utilities using pytesseract.

Provides a single high‑level function ``extract_text`` that accepts a
``Path`` to a pre‑processed image (as returned by ``preprocess_image``) and
returns the raw OCR string together with an optional per‑word confidence map.

The function raises ``RuntimeError`` with a clear message when Tesseract is
missing or when OCR fails for any other reason.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple, Dict

from PIL import Image

try:
    import pytesseract
    from pytesseract import Output, TesseractNotFoundError
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("pytesseract is required for OCR extraction but is not installed.") from exc


def extract_text(image_path: Path) -> Tuple[str, Dict[str, int]]:
    """Extract OCR text and word‑level confidences from *image_path*.

    Parameters
    ----------
    image_path: Path
        Path to a pre‑processed image (RGB/L mode) ready for Tesseract.

    Returns
    -------
    Tuple[str, Dict[str, int]]
        ``(raw_text, confidence_map)`` where ``raw_text`` is the concatenated
        OCR output and ``confidence_map`` maps each recognized word to its
        confidence (0‑100). Words without a numeric confidence are omitted.

    Raises
    ------
    RuntimeError
        If Tesseract is not installed, cannot be executed, or any other OCR
        error occurs.
    """
    if not isinstance(image_path, Path):
        raise ValueError("image_path must be a pathlib.Path instance")

    try:
        img = Image.open(image_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to open image for OCR: {exc}") from exc

    try:
        raw_text: str = pytesseract.image_to_string(img)
        data = pytesseract.image_to_data(img, output_type=Output.DICT)
        confidence_map: Dict[str, int] = {}
        for word, conf in zip(data.get("text", []), data.get("conf", [])):
            if not word or not word.strip():
                continue
            try:
                confidence_map[word] = int(conf)
            except Exception:
                continue
        return raw_text, confidence_map
    except TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract OCR executable not found. Install Tesseract and ensure it is on the system PATH."
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"OCR extraction failed: {exc}") from exc

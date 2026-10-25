"""
app/ocr/preprocessor.py — Image preprocessing utilities for OCR.

Provides a single high‑level function ``preprocess_image`` that
* loads an image from a path or ``UploadFile``-like object,
* corrects EXIF orientation,
* resizes the image so the longer side does not exceed ``max_dim`` (default 1500px),
* converts to greyscale, and
* applies a modest contrast enhancement.

All operations use Pillow (PIL) and return a ``PIL.Image`` ready for
``pytesseract``.

The module validates file extensions (PNG, JPEG, JPG, BMP, TIFF) and raises
a ``ValueError`` for unsupported types or images that are too large (>10 MP).
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import BinaryIO, Union

from PIL import Image, ExifTags, ImageOps, ImageEnhance

# Allowed image extensions – case‑insensitive
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

# Maximum pixel count to guard against gigantic uploads (10 MP)
MAX_PIXELS = 10_000_000


def _validate_extension(file_path: Path) -> None:
    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported image type: {file_path.suffix!r}")


def _load_image(source: Union[Path, BinaryIO]) -> Image.Image:
    """Open an image from a ``Path`` or a binary file‑like object.

    Pillow can read many formats directly; we simply defer to ``Image.open``.
    """
    if isinstance(source, Path):
        _validate_extension(source)
        img = Image.open(source)
    else:
        # ``source`` is a file‑like object (e.g. UploadFile.file)
        img = Image.open(source)
    img.load()  # Force loading – catches truncated images early
    return img


def _correct_orientation(img: Image.Image) -> Image.Image:
    """Apply EXIF orientation tag if present (common for phone photos)."""
    try:
        exif = img._getexif()
        if exif is None:
            return img
        orientation_key = next(
            k for k, v in ExifTags.TAGS.items() if v == "Orientation"
        )
        orientation = exif.get(orientation_key, 1)
        # Pillow >=9.1.0 has ImageOps.exif_transpose which does this safely.
        img = ImageOps.exif_transpose(img)
    except Exception:
        # If anything goes wrong we simply return the original image.
        pass
    return img


def _resize(img: Image.Image, max_dim: int = 1500) -> Image.Image:
    """Resize preserving aspect ratio such that the longer side <= ``max_dim``."""
    width, height = img.size
    if max(width, height) <= max_dim:
        return img
    scaling = max_dim / float(max(width, height))
    new_size = (int(width * scaling), int(height * scaling))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def _to_grayscale(img: Image.Image) -> Image.Image:
    return img.convert("L")


def _enhance_contrast(img: Image.Image, factor: float = 1.5) -> Image.Image:
    enhancer = ImageEnhance.Contrast(img)
    return enhancer.enhance(factor)


def preprocess_image(
    source: Union[Path, BinaryIO], *, max_dim: int = 1500, contrast_factor: float = 1.5
) -> Image.Image:
    """Load and preprocess an image for OCR.

    Parameters
    ----------
    source:
        ``Path`` to an image file on disk or a binary file‑like object (e.g. the
        ``file`` attribute of a FastAPI ``UploadFile``).
    max_dim:
        Maximum dimension (width or height) after resizing.
    contrast_factor:
        Multiplicative factor for contrast enhancement.

    Returns
    -------
    PIL.Image.Image
        The processed image ready for ``pytesseract.image_to_string``.
    """
    img = _load_image(source)
    if img.width * img.height > MAX_PIXELS:
        raise ValueError("Image is too large for processing")
    img = _correct_orientation(img)
    img = _resize(img, max_dim=max_dim)
    img = _to_grayscale(img)
    img = _enhance_contrast(img, factor=contrast_factor)
    return img

"""Local document extraction. Uploaded bytes are never saved to disk."""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
import threading

MAX_BYTES = 8 * 1024 * 1024
MAX_PAGES = 25
MAX_TEXT = 180_000
_OCR_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _ocr_engine():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise ValueError("Local OCR requires rapidocr-onnxruntime. Install requirements-housing.txt or paste verified text.") from exc
    return RapidOCR(intra_op_num_threads=2, inter_op_num_threads=2)


def _ocr_image(data: bytes) -> str:
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
        import numpy as np
    except ImportError as exc:
        raise ValueError("Image extraction requires Pillow and numpy; install requirements-housing.txt.") from exc
    try:
        with Image.open(BytesIO(data)) as image:
            if image.width * image.height > 25_000_000:
                raise ValueError("Image exceeds 25 megapixels; resize it before upload.")
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((2400, 3200))
            pixels = np.asarray(image)
        with _OCR_LOCK:
            rows, _ = _ocr_engine()(pixels)
        text = "\n".join(str(row[1]) for row in (rows or []) if float(row[2]) >= 0.5)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not read this image. Upload a clear, upright image or paste verified text.") from exc
    if not text.strip():
        raise ValueError("No readable text detected. Try a clearer image or paste the agreement text.")
    return text


def extract_bytes(filename: str, data: bytes) -> str:
    """Extract UTF-8 text, text PDFs, scanned PDFs or images using local tools.

    OCR is approximate, intended for English agreements; the interface asks the
    user to check the extracted text before reviewing it.
    """
    if not isinstance(filename, str) or not isinstance(data, bytes):
        raise ValueError("Provide a filename and document bytes.")
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Document must be nonempty and no larger than 8 MB.")
    extension = Path(filename).suffix.lower()
    if extension in {".txt", ".md"}:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Text files must use UTF-8 encoding.") from exc
    elif extension == ".pdf":
        if not data.lstrip().startswith(b"%PDF-"):
            raise ValueError("This file does not have a PDF header.")
        try:
            import pymupdf
        except ImportError as exc:
            raise ValueError("PDF extraction requires PyMuPDF; install requirements-housing.txt.") from exc
        try:
            with pymupdf.open(stream=data, filetype="pdf") as document:
                if document.needs_pass:
                    raise ValueError("Password-protected PDFs are unsupported; upload an unlocked copy.")
                if not 0 < len(document) <= MAX_PAGES:
                    raise ValueError("Upload a PDF with 1 to 25 pages.")
                pages = []
                for page in document:
                    value = page.get_text(sort=True).strip()
                    if not value:
                        # Render scanned pages at bounded resolution for local OCR.
                        scale = min(2, 2400 / max(page.rect.width, 1), 3200 / max(page.rect.height, 1))
                        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                        value = _ocr_image(pixmap.tobytes("png"))
                    pages.append(value)
                text = "\f".join(pages)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Could not extract this PDF. Try an unlocked PDF or paste readable text.") from exc
    elif extension in {".png", ".jpg", ".jpeg", ".webp"}:
        text = _ocr_image(data)
    else:
        raise ValueError("Supported files: .txt, .md, .pdf, .png, .jpg, .jpeg, .webp.")
    if not text.strip():
        raise ValueError("The document contains no readable text.")
    if len(text) > MAX_TEXT:
        raise ValueError("Extracted text exceeds 180,000 characters; split the document.")
    return text

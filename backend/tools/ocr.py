"""Sarvam Vision photo extraction; images and results stay in local memory.

Contract: https://docs.sarvam.ai/api-reference/doc-ai/job/digitise
Only images the caller has already redacted may be sent to the remote service.
Attestation is a user declaration, not automated verification of pixel content.
"""
from __future__ import annotations

from io import BytesIO
import os
import re
import time
from typing import Any, Literal

import httpx
from PIL import Image, UnidentifiedImageError

from backend.tools.agreement import read_agreement, redact_pii
from housing.documents import MAX_BYTES, MAX_TEXT


class OCRError(RuntimeError):
    """An OCR service error safe to show without provider response bodies."""


def _photo(data: bytes) -> tuple[bytes, str, str]:
    if not isinstance(data, bytes) or not data or len(data) > MAX_BYTES:
        raise ValueError("Provide a JPEG or PNG photo no larger than 8 MB")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG"}:
                raise ValueError("Only JPEG and PNG agreement photos are supported")
            if image.width * image.height > 25_000_000:
                raise ValueError("Photo exceeds 25 megapixels; resize it first")
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("Upload one still agreement photo at a time")
            image.load()
            # Strip EXIF and other metadata rather than forwarding location data.
            stream = BytesIO()
            image.convert("RGB").save(stream, format="PNG")
            clean = stream.getvalue()
            if len(clean) > MAX_BYTES:
                raise ValueError("Decoded photo exceeds 8 MB; resize it first")
            return clean, "agreement.png", "image/png"
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Could not read this photo; upload a valid JPEG or PNG") from exc


def _json(response: httpx.Response) -> dict[str, Any]:
    if response.status_code >= 400:
        raise OCRError(f"Sarvam OCR request failed (HTTP {response.status_code}); check credits and Vision access")
    if len(response.content) > 4 * 1024 * 1024:
        raise OCRError("Sarvam OCR returned an oversized result")
    try:
        value = response.json()
    except ValueError as exc:
        raise OCRError("Sarvam OCR returned an unreadable result") from exc
    if not isinstance(value, dict):
        raise OCRError("Sarvam OCR returned an invalid result")
    return value


def _result_text(payload: dict[str, Any]) -> str:
    """Read digitise text blocks only; never include filenames or metadata."""
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise OCRError("Sarvam OCR result has no document text")
    chunks: list[str] = []

    def visit(node: Any, depth: int = 0) -> None:
        if depth > 12:
            raise OCRError("Sarvam OCR result is too deeply nested")
        if isinstance(node, list):
            for item in node:
                visit(item, depth + 1)
        elif isinstance(node, dict):
            if isinstance(node.get("text"), str):
                chunks.append(node["text"])
            else:
                for key in ("result", "pages", "blocks", "elements", "content"):
                    if key in node:
                        visit(node[key], depth + 1)

    visit(documents)
    text = "\n".join(chunks).strip()
    if not text or len(text) > MAX_TEXT:
        raise OCRError("OCR text is empty or too long; try a clearer single page")
    return text


def read_photo(
    data: bytes, *, image_already_redacted: bool, consent_to_remote_ocr: bool,
    language: Literal["en-IN", "kn-IN", "hi-IN"] = "en-IN",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Extract a pre-redacted image, then redact detected identifiers again.

    No original pixels are retained locally. Sarvam receives the sanitized image;
    this function makes no claim about provider-side storage or retention.
    """
    if image_already_redacted is not True or consent_to_remote_ocr is not True:
        raise ValueError("Remove Aadhaar, PAN and phone numbers from the photo and explicitly consent to remote Sarvam OCR")
    if language not in {"en-IN", "kn-IN", "hi-IN"}:
        raise ValueError("Choose en-IN, kn-IN or hi-IN for OCR language")
    photo, filename, mime = _photo(data)
    key = os.getenv("SARVAM_API_KEY", "").strip()
    if not key:
        raise OCRError("Configure SARVAM_API_KEY with Vision access to scan photos")
    headers = {"api-subscription-key": key}
    base = "https://api.sarvam.ai/doc-ai/v1/job"
    own_client = client is None
    connection = client or httpx.Client(timeout=20.0, follow_redirects=False)
    deadline = time.monotonic() + 90
    try:
        created = _json(connection.post(f"{base}/digitise", headers=headers,
            files={"file": (filename, photo, mime)},
            data={"language": language, "output_format": "json", "content_type": "printed"}))
        job_id = created.get("job_id")
        if not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,150}", job_id):
            raise OCRError("Sarvam OCR did not return a valid job identifier")
        # Bounded polling. Do not retry creation: that could duplicate billing.
        for attempt in range(30):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            status = _json(connection.get(f"{base}/{job_id}/status", headers=headers, timeout=min(20.0, remaining)))
            state = str(status.get("status", "")).lower()
            if state in {"failed", "rejected", "partially_completed"}:
                raise OCRError("Sarvam OCR did not fully process the photo; retry with a clearer image or paste verified text")
            if state == "completed":
                result = _json(connection.get(f"{base}/{job_id}/results", headers=headers, params={"format": "json"}))
                text, counts = redact_pii(_result_text(result))
                agreement = read_agreement(text)
                return {"text": text, "clauses": agreement["clauses"], "redactions": counts,
                        "provider": "sarvam-vision", "requires_review": True}
            if state not in {"pending", "running"}:
                raise OCRError("Sarvam OCR returned an unknown processing state")
            if attempt < 29:
                time.sleep(2)
        raise OCRError("Sarvam OCR is still processing; wait before retrying or paste verified text")
    except httpx.HTTPError as exc:
        raise OCRError("Sarvam OCR could not be reached; retry later or paste verified text") from exc
    finally:
        if own_client:
            connection.close()

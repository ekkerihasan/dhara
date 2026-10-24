"""Explicitly opted-in photo OCR, returning text for tenant review first."""
from __future__ import annotations

import base64
import binascii
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from backend.tools.ocr import OCRError, read_photo

router = APIRouter(prefix="/api", tags=["photo OCR"])


class OCRRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_base64: str = Field(min_length=1, max_length=11_184_812)
    image_already_redacted: StrictBool = False
    consent_to_remote_ocr: StrictBool = False
    language: Literal["en-IN", "kn-IN", "hi-IN"] = "en-IN"


class OCRResponse(BaseModel):
    text: str
    clauses: list[dict[str, Any]]
    redactions: dict[str, int]
    provider: Literal["sarvam-vision"]
    requires_review: Literal[True]


@router.post("/ocr", response_model=OCRResponse)
def scan_photo(request: OCRRequest) -> dict[str, Any]:
    """OCR a pre-redacted PNG/JPEG; inspect the text before starting a review."""
    if not request.image_already_redacted or not request.consent_to_remote_ocr:
        raise HTTPException(400, "Remove personal identifiers from the image and consent to remote Sarvam OCR first")
    try:
        data = base64.b64decode(request.image_base64, validate=True)
        return read_photo(data, image_already_redacted=request.image_already_redacted,
                          consent_to_remote_ocr=request.consent_to_remote_ocr, language=request.language)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(400, "Invalid photo or encoding" if isinstance(exc, binascii.Error) else str(exc)) from exc
    except OCRError as exc:
        raise HTTPException(502, str(exc)) from exc

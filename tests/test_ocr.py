from io import BytesIO
import base64
import json

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from backend.ocr_api import router
from backend.tools.ocr import OCRError, _photo, _result_text, read_photo


def photo() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (30, 30), "white").save(stream, "PNG")
    return stream.getvalue()


def test_remote_photo_workflow_redacts_result_and_never_forwards_filename(monkeypatch, caplog):
    monkeypatch.setenv("SARVAM_API_KEY", "test-only-credential")
    seen = []
    def handler(request):
        seen.append(request)
        assert request.headers["api-subscription-key"] == "test-only-credential"
        if request.method == "POST":
            assert b'name="file"; filename="agreement.png"' in request.content
            assert b'en-IN' in request.content
            return httpx.Response(201, json={"job_id": "job-1", "status": "pending"})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"status": "completed"})
        assert request.url.params["format"] == "json"
        return httpx.Response(200, json={"documents": [{"filename": "private.png", "pages": [{"blocks": [
            {"text": "1. Deposit INR 150000. Phone 9876543210; PAN ABCDE1234F; Aadhaar 1234 5678 9012."}
        ]}]}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = read_photo(photo(), image_already_redacted=True, consent_to_remote_ocr=True, client=client)
    rendered = json.dumps(result) + caplog.text
    for secret in ["9876543210", "ABCDE1234F", "1234 5678 9012", "private.png", "test-only-credential"]:
        assert secret not in rendered
    assert result["requires_review"] is True
    assert result["redactions"] == {"aadhaar": 1, "pan": 1, "phone": 1}
    assert "150000" in result["text"]
    assert len(seen) == 3


@pytest.mark.parametrize("redacted,consent", [(False, False), (True, False), (False, True)])
def test_missing_consent_never_contacts_provider(redacted, consent):
    with pytest.raises(ValueError, match="explicitly consent"):
        read_photo(photo(), image_already_redacted=redacted, consent_to_remote_ocr=consent)


@pytest.mark.parametrize("data", [b"broken", b"", b"x" * (8 * 1024 * 1024 + 1)], ids=["broken", "empty", "oversized"])
def test_invalid_photos_rejected_before_remote(data):
    with pytest.raises(ValueError):
        read_photo(data, image_already_redacted=True, consent_to_remote_ocr=True)


def test_photo_metadata_removed_before_remote():
    stream = BytesIO()
    image = Image.new("RGB", (30, 30), "white")
    exif = Image.Exif()
    exif[270] = "private location and owner metadata"
    image.save(stream, "JPEG", exif=exif)
    clean, filename, mime = _photo(stream.getvalue())
    with Image.open(BytesIO(clean)) as decoded:
        assert not decoded.getexif()
    assert b"private location" not in clean
    assert filename == "agreement.png" and mime == "image/png"


def test_missing_credential_has_actionable_error(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    with pytest.raises(OCRError, match="Configure SARVAM_API_KEY"):
        read_photo(photo(), image_already_redacted=True, consent_to_remote_ocr=True)


@pytest.mark.parametrize("payload", [{}, {"documents": []}, {"documents": [{"filename": "not-text.png"}]}])
def test_missing_text_is_not_treated_as_an_agreement(payload):
    with pytest.raises(OCRError):
        _result_text(payload)


@pytest.mark.parametrize("status", ["failed", "rejected", "partially_completed"])
def test_incomplete_photo_never_returns_partial_agreement(monkeypatch, status):
    monkeypatch.setenv("SARVAM_API_KEY", "test-only")
    def handler(request):
        return httpx.Response(200, json={"job_id": "job-1", "status": status})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OCRError, match="fully process"):
            read_photo(photo(), image_already_redacted=True, consent_to_remote_ocr=True, client=client)


def test_polling_is_bounded_without_duplicate_upload(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-only")
    monkeypatch.setattr("backend.tools.ocr.time.sleep", lambda _: None)
    calls = []
    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json={"job_id": "job-1", "status": "pending"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OCRError, match="still processing"):
            read_photo(photo(), image_already_redacted=True, consent_to_remote_ocr=True, client=client)
    assert calls.count("POST") == 1
    assert calls.count("GET") == 30


def test_provider_error_does_not_expose_body(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-only")
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(403, text="sensitive-provider-body"))) as client:
        with pytest.raises(OCRError) as error:
            read_photo(photo(), image_already_redacted=True, consent_to_remote_ocr=True, client=client)
    assert "sensitive-provider-body" not in str(error.value)
    assert "HTTP 403" in str(error.value)


def test_ocr_route_validates_input_and_returns_review_text(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    payload = {"image_base64": base64.b64encode(photo()).decode()}
    assert client.post("/api/ocr", json=payload).status_code == 400
    payload.update(image_already_redacted=True, consent_to_remote_ocr=True)
    monkeypatch.setattr("backend.ocr_api.read_photo", lambda *a, **kw: {
        "text": "1. Deposit INR 150000", "clauses": [], "redactions": {},
        "provider": "sarvam-vision", "requires_review": True,
    })
    response = client.post("/api/ocr", json=payload)
    assert response.status_code == 200
    assert response.json()["requires_review"] is True
    payload["image_base64"] = "!!!"
    assert client.post("/api/ocr", json=payload).status_code == 400
    payload["consent_to_remote_ocr"] = "yes"
    assert client.post("/api/ocr", json=payload).status_code == 422

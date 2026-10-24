# Agreement photo OCR

Open `/scan` in the frontend with the backend running. The scanner always uses the live API, including when sample agreement mode is enabled.

1. Cover Aadhaar, PAN and phone numbers in an image editor. Export a flattened JPEG/PNG. The app cannot verify that identifiers have been removed from the pixels.
2. Select the image and document language. Confirm the image was already redacted and agree to send it to Sarvam.
3. Scan, inspect every clause and amount, correct mistakes, then copy the text into the agreement intake form. Multiple photos can be scanned separately and their checked text combined.

Configure `SARVAM_API_KEY` in the backend environment with Vision/Document Intelligence access and sufficient credits. No extra Sarvam SDK is used. Images must be JPEG/PNG, at most 8 MB and 25 megapixels. Dhara strips EXIF/metadata and holds the image in memory; it does not save an upload locally. Sarvam receives the photo and creates a remote processing job. Dhara does not promise provider-side deletion or a retention period. Extracted text is redacted before being returned and must be checked before a tenancy review.

## API

`POST /api/ocr` accepts JSON:

```json
{
  "image_base64": "<base64 JPEG or PNG bytes, without a data-URL prefix>",
  "image_already_redacted": true,
  "consent_to_remote_ocr": true,
  "language": "en-IN"
}
```

`language` supports `en-IN`, `kn-IN`, `hi-IN`. Both booleans are mandatory opt-ins; their default is false. This is a declaration by the caller, not automatic pixel redaction.

The response contains `text`, `clauses`, `redactions`, `provider: "sarvam-vision"`, and `requires_review: true`. It does not start a tenancy run or send a message. Invalid images/consent return 400; malformed payloads return 422; provider or configuration errors return 502 without exposing provider response bodies or credentials. OCR processing is bounded; if it times out, wait before submitting again because a remote job may still be running and a new scan may incur another charge.

Implementation follows Sarvam's current [digitise endpoint](https://docs.sarvam.ai/api-reference/doc-ai/job/digitise), [status endpoint](https://docs.sarvam.ai/api-reference/doc-ai/job/status), and [results endpoint](https://docs.sarvam.ai/api-reference/doc-ai/job/results), verified on 25 October 2026. This uses `/doc-ai/v1`, rather than the legacy `/doc-digitization/job/v1` API.

## Validation

A live smoke test on 25 October 2026 generated a synthetic PNG entirely in memory with three lines: monthly rent INR 25000, deposit INR 150000, and one month notice. Sarvam returned all three lines verbatim; Dhara split them into three clauses and returned `requires_review: true`. This verifies the hosted API path and response parsing for one clean English image; it does not establish general OCR accuracy for photographs, handwriting, or Kannada.

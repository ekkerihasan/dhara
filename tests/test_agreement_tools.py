from io import BytesIO
import json
from pathlib import Path

import pymupdf
from pypdf import PdfWriter
import pytest

from backend.tools.agreement import read_agreement, redact_pii


def test_redacts_before_clauses_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    text = "1. Aadhaar 1234 5678 9012; PAN ABCDE1234F.\n2. Call +91 9876543210 or 1234567890."
    with caplog.at_level("INFO"):
        result = read_agreement(text)
    assert len(result["clauses"]) == 2
    assert result["redaction_count"] == 4
    rendered = json.dumps(result) + caplog.text
    for secret in ("1234 5678 9012", "ABCDE1234F", "9876543210", "1234567890"):
        assert secret not in rendered
    assert result["redactions"] == {"aadhaar": 1, "pan": 1, "phone": 2}


def test_redaction_does_not_modify_money_or_section_ids() -> None:
    text = "INR 150000; ICA-74; notice 30 days."
    assert redact_pii(text)[0] == text


def test_pdf_memory_extraction_preserves_page_numbers() -> None:
    with pymupdf.open() as pdf:
        for text in ("1. Phone 9876543210", "2. Deposit INR 150000"):
            pdf.new_page().insert_text((72, 72), text)
        data = pdf.tobytes()
    result = read_agreement(data)
    assert [clause["page"] for clause in result["clauses"]] == [1, 2]
    assert "9876543210" not in str(result)


def test_encrypted_pdf_is_rejected() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("password")
    stream = BytesIO()
    writer.write(stream)
    with pytest.raises(ValueError, match="Unlock"):
        read_agreement(stream.getvalue())


@pytest.mark.parametrize("document", ["", " " * 10, "a" * 180001, b"not a pdf", b"%PDF-garbage", b"a" * (8 * 1024 * 1024 + 1), None],
                         ids=["empty", "whitespace", "long-text", "not-pdf", "broken-pdf", "large-pdf", "wrong-type"])
def test_rejects_invalid_documents(document: object) -> None:
    with pytest.raises(ValueError):
        read_agreement(document)


def test_fixture_labels_use_prototype_splitter() -> None:
    task = json.loads((Path(__file__).parents[1] / "env/tasks/blr_flat.json").read_text())
    assert len(read_agreement(task["agreement_text"])["clauses"]) == 6

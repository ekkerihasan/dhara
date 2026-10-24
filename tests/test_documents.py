"""Synthetic, in-memory intake checks; no user agreements are retained."""
from io import BytesIO
import unittest
from unittest.mock import patch

import pymupdf
from PIL import Image

from housing.documents import MAX_BYTES, MAX_PAGES, MAX_TEXT, extract_bytes


def pdf_bytes(texts, encrypted=False):
    with pymupdf.open() as document:
        for text in texts:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        if encrypted:
            return document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="reader")
        return document.tobytes()


class DocumentTests(unittest.TestCase):
    def test_utf8_bom_and_supported_text_extensions(self):
        for name in ("lease.txt", "LEASE.MD"):
            self.assertEqual(extract_bytes(name, "\ufeffSynthetic lease — deposit 6 months.".encode()), "Synthetic lease — deposit 6 months.")

    def test_bad_input_sizes_encoding_and_extensions(self):
        for name, data in [("a.txt", b""), ("a.txt", b"x" * (MAX_BYTES + 1)), ("a.txt", b"\xff"), ("a.docx", b"data"), ("a.txt", b"  "), ("a.txt", b"x" * (MAX_TEXT + 1))]:
            with self.subTest(name=name, length=len(data)):
                with self.assertRaises(ValueError):
                    extract_bytes(name, data)
        with self.assertRaises(ValueError):
            extract_bytes("a.txt", "not bytes")

    def test_real_text_pdf_preserves_pages_and_bypasses_ocr(self):
        data = pdf_bytes(["1. Security deposit is 6 months of rent.", "2. Notice is 30 days."])
        with patch("housing.documents._ocr_image") as ocr:
            result = extract_bytes("lease.pdf", data)
        self.assertIn("Security deposit is 6 months", result)
        self.assertIn("Notice is 30 days", result)
        self.assertEqual(len(result.split("\f")), 2)
        ocr.assert_not_called()

    def test_corrupt_encrypted_and_excess_page_pdf(self):
        for data in [b"not a PDF", b"%PDF-1.7\ncorrupt", pdf_bytes(["Private synthetic lease"], encrypted=True), pdf_bytes(["Synthetic"] * (MAX_PAGES + 1))]:
            with self.assertRaises(ValueError):
                extract_bytes("lease.pdf", data)

    def test_images_dispatch_to_local_ocr(self):
        image = Image.new("RGB", (400, 100), "white")
        stream = BytesIO()
        image.save(stream, format="PNG")
        with patch("housing.documents._ocr_image", return_value="Deposit is 6 months.") as ocr:
            self.assertEqual(extract_bytes("lease.png", stream.getvalue()), "Deposit is 6 months.")
            ocr.assert_called_once_with(stream.getvalue())

    def test_scanned_pdf_page_uses_rendered_png_ocr(self):
        with patch("housing.documents._ocr_image", return_value="Synthetic scanned lease") as ocr:
            result = extract_bytes("scan.pdf", pdf_bytes([""]))
        self.assertEqual(result, "Synthetic scanned lease")
        rendered = ocr.call_args.args[0]
        self.assertTrue(rendered.startswith(b"\x89PNG"))
        with Image.open(BytesIO(rendered)) as image:
            self.assertLessEqual(image.width, 2400)
            self.assertLessEqual(image.height, 3200)

    def test_ocr_errors_are_exposed_to_caller(self):
        with patch("housing.documents._ocr_image", side_effect=ValueError("No readable text detected")):
            with self.assertRaisesRegex(ValueError, "No readable"):
                extract_bytes("photo.jpg", b"synthetic")


if __name__ == "__main__":
    unittest.main()

"""End-to-end synthetic document smoke check; --ocr exercises real local OCR."""
import argparse
import json
from io import BytesIO
from pathlib import Path

from housing import review_document
from housing.documents import extract_bytes
from housing.negotiation import negotiate


def verify(include_ocr=False):
    import pymupdf
    text = "1. Security deposit is 6 months of rent."
    document = pymupdf.open()
    page = document.new_page(width=900, height=220)
    page.insert_text((40, 100), text, fontsize=24)
    pdf_bytes = document.tobytes()
    png_bytes = page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
    document.close()
    documents = [("lease.txt", text.encode()), ("lease.pdf", pdf_bytes)]
    if include_ocr:
        scanned = pymupdf.open()
        page = scanned.new_page(width=900, height=220)
        page.insert_image(page.rect, stream=png_bytes)
        documents += [("lease.png", png_bytes), ("scanned.pdf", scanned.tobytes())]
        scanned.close()
    rows = []
    for name, data in documents:
        extracted = extract_bytes(name, data)
        review = review_document(extracted, "Karnataka", {"max_deposit_months": 2})
        finding = next(f for f in review["findings"] if f["category"] == "preference")
        result = negotiate(review, finding["clause_id"], "Security deposit is 2 months of rent.")
        passed = result["decision"] == "accept" and "6 months" in extracted
        passed = passed and all(review["messages"].get(language) for language in ("english", "kannada", "hindi"))
        rows.append({"input": name, "passed": bool(passed), "decision": result["decision"]})
    return {"evaluation": "synthetic document-to-negotiation smoke check", "ocr_enabled": include_ocr,
            "passed": sum(row["passed"] for row in rows), "cases": len(rows), "results": rows,
            "limitations": ["Synthetic English documents only; not evidence of OCR accuracy on arbitrary agreements.",
                            "No API calls or real personal documents used."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.ocr)
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if report["passed"] == report["cases"] else 1)

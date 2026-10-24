"""Usage: python -m housing lease.txt --state Karnataka --preferences '{...}'."""
import argparse
import json
import sys

from . import extract_document, review_document


def main():
    parser = argparse.ArgumentParser(description="Offline lease preference review; no API key needed")
    parser.add_argument("document", help="Text, PDF or image; PDF/OCR dependencies in requirements-housing.txt")
    parser.add_argument("--state", default="")
    parser.add_argument("--preferences", default="{}", help="JSON object of explicit numerical preferences")
    parser.add_argument("--facts", default="{}", help="JSON object of confirmed jurisdiction facts")
    args = parser.parse_args()
    try:
        preferences = json.loads(args.preferences)
        if not isinstance(preferences, dict):
            raise ValueError("Preferences must be a JSON object")
        facts = json.loads(args.facts)
        if not isinstance(facts, dict):
            raise ValueError("Facts must be a JSON object")
        result = review_document(extract_document(args.document), args.state, preferences, facts)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    # ensure_ascii makes output portable to Windows legacy console encodings.
    sys.stdout.write(json.dumps(result, ensure_ascii=True, indent=2) + "\n")


if __name__ == "__main__":
    main()

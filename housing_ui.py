"""Run the private, dependency-free housing review demo: python housing_ui.py."""

import argparse
import base64
import binascii
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from housing import review_document

STATIC = Path(__file__).parent / "static" / "housing"
MAX_BODY = 256 * 1024
MAX_DOCUMENT = 8 * 1024 * 1024
MAX_EXTRACT_BODY = 12 * 1024 * 1024


class HousingHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Do not log uploaded agreements or request data."""

    def respond(self, status, body, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def error_json(self, status, message):
        self.respond(status, json.dumps({"error": message}).encode())

    def do_GET(self):
        routes = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
        route = routes.get(self.path)
        if route is None:
            self.error_json(404, "Not found")
            return
        name, mime = route
        self.respond(200, (STATIC / name).read_bytes(), mime + "; charset=utf-8")

    def do_POST(self):
        if self.path not in {"/api/review", "/api/extract", "/api/negotiate"}:
            self.error_json(404, "Not found")
            return
        # Only this local interface may submit agreements through a browser.
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.headers.get("Host", ""):
            self.error_json(403, "Cross-origin requests are not allowed")
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self.error_json(415, "Send application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            limit = MAX_EXTRACT_BODY if self.path == "/api/extract" else MAX_BODY
            if length <= 0 or length > limit:
                self.error_json(413, "Request exceeds the endpoint size limit")
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Expected an object")
            if self.path == "/api/extract":
                from housing.documents import extract_bytes
                filename = payload.get("filename")
                encoded = payload.get("data_base64")
                if not isinstance(filename, str) or not isinstance(encoded, str):
                    raise ValueError("Provide filename and data_base64 strings")
                try:
                    document = base64.b64decode(encoded, validate=True)
                except (ValueError, binascii.Error):
                    raise ValueError("Invalid base64 document") from None
                if len(document) > MAX_DOCUMENT:
                    self.error_json(413, "Document must be smaller than 8 MB")
                    return
                text = extract_bytes(filename, document)
                self.respond(200, json.dumps({"text": text}, ensure_ascii=False).encode("utf-8"))
                return
            if self.path == "/api/negotiate":
                from housing.negotiation import negotiate
                review = payload.get("review")
                clause_id = payload.get("clause_id")
                offer = payload.get("offer")
                history = payload.get("history", [])
                if not isinstance(review, dict) or not isinstance(clause_id, str) or not isinstance(offer, str) or not isinstance(history, list):
                    raise ValueError("Invalid negotiation request")
                if not isinstance(review.get("clauses", []), list) or not isinstance(review.get("findings", []), list):
                    raise ValueError("Invalid review clauses or findings")
                if any(not isinstance(item, dict) for item in history + review.get("clauses", []) + review.get("findings", [])):
                    raise ValueError("Negotiation entries must be objects")
                result = negotiate(review, clause_id, offer, history)
                self.respond(200, json.dumps(result, ensure_ascii=False).encode("utf-8"))
                return
            text = payload.get("text", "")
            state = payload.get("state", "")
            preferences = payload.get("preferences", {})
            facts = payload.get("facts", {})
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Paste a non-empty agreement")
            if not isinstance(state, str) or not isinstance(preferences, dict) or not isinstance(facts, dict):
                raise ValueError("Invalid state or preferences")
            clean_preferences = {}
            for key in ("max_deposit_months", "max_notice_days", "min_notice_days", "max_refund_days", "min_entry_notice_hours", "max_rent_increase_percent"):
                value = preferences.get(key)
                if value is not None:
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 10000:
                        raise ValueError("Preferences must be numbers between 0 and 10000")
                    clean_preferences[key] = value
            result = review_document(text, state, clean_preferences, facts)
            self.respond(200, json.dumps(result, ensure_ascii=False).encode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            self.error_json(400, str(exc))
        except Exception:
            self.error_json(500, "Review failed. Check the local setup and try again.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=7861)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), HousingHandler)
    print(f"Dhara housing demo: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

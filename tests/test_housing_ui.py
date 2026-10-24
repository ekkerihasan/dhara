"""Exercise the local HTTP boundary using real requests, without API credentials."""
import base64
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from housing_ui import HousingHandler


class HousingHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), HousingHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, data=None, headers=None):
        request = urllib.request.Request(self.base + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            return response.status, response.headers, body

    def test_static_assets_and_no_store(self):
        for path in ("/", "/app.js", "/style.css"):
            status, headers, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertTrue(body)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.request("/../housing_ui.py")[0], 404)

    def test_text_extraction_then_review_and_negotiate(self):
        text = "1. Security deposit is 6 months of rent."
        status, _, body = self.request("/api/extract", {
            "filename": "agreement.txt", "data_base64": base64.b64encode(text.encode()).decode()})
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)["text"], text)
        status, _, body = self.request("/api/review", {
            "text": text, "state": "Karnataka", "preferences": {"max_deposit_months": 2},
            "facts": {"city": "Bengaluru", "residential": True}})
        self.assertEqual(status, 200, body)
        review = json.loads(body)
        self.assertTrue(review["findings"])
        status, _, body = self.request("/api/negotiate", {
            "review": review, "clause_id": review["findings"][0]["clause_id"],
            "offer": "Security deposit is 2 months of rent.", "history": []})
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)["decision"], "accept")

    def test_invalid_inputs_are_rejected(self):
        for path, data in (("/api/extract", {"filename": "x.txt", "data_base64": "!"}),
                           ("/api/review", {"text": ""}),
                           ("/api/review", {"text": "x", "facts": []}),
                           ("/api/negotiate", {"review": {}, "clause_id": "C1", "offer": "x", "history": [1]})):
            status, _, body = self.request(path, data)
            self.assertEqual(status, 400, body)
        self.assertEqual(self.request("/api/review", {"text": "x"}, {"Origin": "http://external.test"})[0], 403)
        self.assertEqual(self.request("/api/review", {"text": "x"}, {"Content-Type": "text/plain"})[0], 415)

    def test_optional_preferences_are_preserved(self):
        preferences = {"max_deposit_months": 2, "max_notice_days": 90,
                       "min_notice_days": 30, "max_refund_days": 15,
                       "min_entry_notice_hours": 24, "max_rent_increase_percent": 5}
        status, _, body = self.request("/api/review", {
            "text": "Rent is due monthly.", "preferences": preferences})
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)["preferences"], preferences)

    def test_oversize_requests_rejected(self):
        self.assertEqual(self.request("/api/review", {"text": "x" * (256 * 1024)})[0], 413)
        content = base64.b64encode(b"x" * (8 * 1024 * 1024 + 1)).decode()
        self.assertEqual(self.request("/api/extract", {"filename": "large.txt", "data_base64": content})[0], 413)


if __name__ == "__main__":
    unittest.main()

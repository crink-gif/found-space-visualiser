"""
Found—Space Visualiser — local preview server (Python standard library only).

Run it with no installs:

    python3 server.py

then open http://localhost:8000

Serves the static front-end and the same /api/visualise + /api/lead logic that
runs on Vercel. With no GEMINI_API_KEY set it runs in demo mode; set the key to
get live AI renders:

    GEMINI_API_KEY=your_key python3 server.py
"""

import os
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import visualiser_core as core

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8000"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def log_message(self, fmt, *args):
        print("·", fmt % args)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def _send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/api/visualise":
            return self._handle_visualise()
        if self.path == "/api/lead":
            return self._handle_lead()
        self._send_json(404, {"error": "Not found"})

    def _handle_visualise(self):
        try:
            data = self._read_json()
        except Exception:
            return self._send_json(400, {"error": "Invalid request."})
        if not data.get("image") or not data.get("saunaId"):
            return self._send_json(400, {"error": "Please provide a photo and choose a model."})
        try:
            return self._send_json(200, core.render(data["image"], data["saunaId"], data.get("sizeId")))
        except ValueError as e:
            return self._send_json(400, {"error": str(e)})
        except Exception as e:
            print("[VISUALISE] error:", repr(e))
            return self._send_json(502, {"error": core.gemini_error_message(e)})

    def _handle_lead(self):
        try:
            data = self._read_json()
        except Exception:
            return self._send_json(400, {"error": "Invalid request."})
        if not data.get("firstName") or not data.get("email") or not data.get("phone"):
            return self._send_json(400, {"error": "Name, email and phone are required."})
        try:
            return self._send_json(200, core.save_lead(data))
        except Exception as e:
            print("[LEAD] error:", repr(e))
            return self._send_json(502, {"error": "Could not submit."})


if __name__ == "__main__":
    mode = "AI (Gemini)" if os.environ.get("GEMINI_API_KEY", "").strip() else "DEMO (no API key set)"
    print("\n  Found—Space Visualiser")
    print("  Mode:   %s" % mode)
    print("  Open:   http://localhost:%d\n" % PORT)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

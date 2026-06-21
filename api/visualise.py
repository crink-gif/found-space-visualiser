"""Vercel serverless function: POST /api/visualise"""
import os
import sys
import json
from http.server import BaseHTTPRequestHandler

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import visualiser_core as core


class handler(BaseHTTPRequestHandler):
    def _json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(400, {"error": "Invalid request."})

        image = data.get("image")
        sauna_id = data.get("saunaId")
        size_id = data.get("sizeId")
        if not image or not sauna_id:
            return self._json(400, {"error": "Please provide a photo and choose a model."})

        try:
            result = core.render(image, sauna_id, size_id)
            return self._json(200, result)
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:
            print("[VISUALISE] error:", repr(e))
            return self._json(502, {"error": core.gemini_error_message(e)})

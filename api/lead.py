"""Vercel serverless function: POST /api/lead"""
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

        if not data.get("firstName") or not data.get("email") or not data.get("phone"):
            return self._json(400, {"error": "Name, email and phone are required."})

        try:
            return self._json(200, core.save_lead(data))
        except Exception as e:
            print("[LEAD] error:", repr(e))
            return self._json(502, {"error": "Could not submit. Please try again."})

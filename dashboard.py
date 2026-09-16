#!/usr/bin/env python3
"""Local-only HTTP server for the DemandRadar dashboard."""

import argparse
import http.server
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def make_handler(data_path):
    data_path = Path(data_path).resolve()
    index_path = WEB_DIR / "index.html"
    app_path = WEB_DIR / "app.js"

    class DashboardHandler(http.server.BaseHTTPRequestHandler):
        def _send(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            for name, value in SECURITY_HEADERS.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/":
                self._send(200, index_path.read_bytes(), "text/html; charset=utf-8")
                return
            if path == "/app.js":
                self._send(200, app_path.read_bytes(), "text/javascript; charset=utf-8")
                return
            if path == "/data":
                try:
                    body = data_path.read_bytes()
                except OSError:
                    self._send(404, b'{"error":"data file not found"}', "application/json; charset=utf-8")
                    return
                self._send(200, body, "application/json; charset=utf-8")
                return
            self._send(404, b"Not found", "text/plain; charset=utf-8")

        def log_message(self, _format, *_args):
            return

    return DashboardHandler


def build_parser():
    parser = argparse.ArgumentParser(description="Serve the DemandRadar dashboard locally")
    parser.add_argument("data", nargs="?", default="data/results.json")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    handler = make_handler(args.data)
    address = ("127.0.0.1", args.port)
    print(f"DemandRadar dashboard: http://{address[0]}:{address[1]}")
    with http.server.ThreadingHTTPServer(address, handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()

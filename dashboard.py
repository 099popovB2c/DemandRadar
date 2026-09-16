#!/usr/bin/env python3
import http.server, json, sys, webbrowser
from pathlib import Path
DATA=Path(sys.argv[1] if len(sys.argv)>1 else 'data/results.json').resolve()
HTML=Path(__file__).with_name('web').joinpath('index.html').read_text(encoding='utf8')
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/data'):
            b=DATA.read_bytes(); self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(b)
        else:
            b=HTML.encode(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(b)
    def log_message(self,*a): pass
print('DemandRadar dashboard: http://127.0.0.1:8765')
http.server.HTTPServer(('127.0.0.1',8765),H).serve_forever()

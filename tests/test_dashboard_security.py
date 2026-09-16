import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class DashboardSecurityTests(unittest.TestCase):
    def test_frontend_does_not_use_html_injection_sinks(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        forbidden = ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"]
        for token in forbidden:
            self.assertNotIn(token, source)
        self.assertIn("textContent", source)
        self.assertIn("replaceChildren", source)

    def test_external_links_have_protocol_allowlist(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("url.protocol === 'http:'", source)
        self.assertIn("url.protocol === 'https:'", source)
        self.assertIn("noopener noreferrer", source)

    def test_index_has_no_inline_script(self):
        source = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<script src="/app.js" defer></script>', source)
        self.assertEqual(source.count("<script"), 1)

    def test_server_sets_security_headers_and_local_binding(self):
        source = (ROOT / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn("Content-Security-Policy", source)
        self.assertIn("X-Content-Type-Options", source)
        self.assertIn("nosniff", source)
        self.assertIn('("127.0.0.1", args.port)', source)
        self.assertIn("frame-ancestors 'none'", source)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CAPTURE_PATH = ROOT / "data" / "oauth_callback_url.txt"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        full_url = f"http://{self.headers.get('Host')}{self.path}"
        CAPTURE_PATH.parent.mkdir(exist_ok=True)
        CAPTURE_PATH.write_text(full_url, encoding="utf-8")
        body = b"""
        <html>
          <head><title>Spotify authorization received</title></head>
          <body style="font-family: Arial, sans-serif; margin: 48px;">
            <h1>Spotify authorization received</h1>
            <p>You can return to the Spotify Analytics dashboard now.</p>
          </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8888), OAuthCallbackHandler)
    server.serve_forever()

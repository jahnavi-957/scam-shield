"""Self-contained S3-compatible mock server for local development.

Emulates AWS S3 path-style operations used by Scam Shield:
- PUT /{bucket}/{key} (direct browser presigned upload)
- GET /{bucket}/{key} (backend fetch for OCR)
- HEAD /{bucket}/{key} (backend object existence check)
- DELETE /{bucket}/{key} (backend post-analysis cleanup)
- OPTIONS /{any} (CORS preflight for browser uploads)
- GET /health (container healthcheck)
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("s3mock")

DATA_DIR = os.environ.get("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)


class S3MockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, DELETE, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Expose-Headers", "ETag, Content-Length, Content-Type")

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _safe_file_path(self) -> str | None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.strip("/")
        if not path:
            return None
        safe = os.path.normpath(os.path.join(DATA_DIR, path))
        if not safe.startswith(os.path.abspath(DATA_DIR)):
            return None
        return safe

    def do_GET(self) -> None:
        if self.path in ("/health", "/healthz"):
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "15")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        file_path = self._safe_file_path()
        if not file_path or not os.path.isfile(file_path):
            self.send_response(404)
            self._cors()
            self.send_header("Content-Type", "application/xml")
            body = b"<Error><Code>NoSuchKey</Code><Message>The specified key does not exist.</Message></Error>"
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        size = os.path.getsize(file_path)
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("ETag", f'"{size}"')
        self.end_headers()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)

    def do_HEAD(self) -> None:
        file_path = self._safe_file_path()
        if not file_path or not os.path.isfile(file_path):
            self.send_response(404)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        size = os.path.getsize(file_path)
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("ETag", f'"{size}"')
        self.end_headers()

    def do_PUT(self) -> None:
        file_path = self._safe_file_path()
        if not file_path:
            self.send_response(400)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            remaining = content_length
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    break
                f.write(chunk)
                remaining -= len(chunk)

        logger.info("Saved %d bytes to %s", content_length, file_path)
        self.send_response(200)
        self._cors()
        self.send_header("ETag", f'"{content_length}"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_DELETE(self) -> None:
        file_path = self._safe_file_path()
        if file_path and os.path.isfile(file_path):
            try:
                os.remove(file_path)
                logger.info("Deleted %s", file_path)
            except OSError:
                pass
        self.send_response(204)
        self._cors()
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        logger.info("%s - - [%s] %s", self.client_address[0], self.log_date_time_string(), format % args)


def main() -> None:
    port = int(os.environ.get("PORT", "4566"))
    server = HTTPServer(("0.0.0.0", port), S3MockHandler)
    logger.info("Local S3 mock listening on port %d, data dir: %s", port, DATA_DIR)
    server.serve_forever()


if __name__ == "__main__":
    main()

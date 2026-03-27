from __future__ import annotations

import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, urlunsplit

from sentinel_alpha.config import get_settings
from sentinel_alpha.webapp import static_dir


class LegacyRedirectHandler(SimpleHTTPRequestHandler):
    def _redirect_target(self) -> str:
        target_port = os.getenv("SENTINEL_NICEGUI_PORT", "8010")
        host = self.headers.get("Host", "")
        host_name = host.split(":", 1)[0] if host else "127.0.0.1"
        current = urlsplit(self.path)
        destination = urlunsplit(("http", f"{host_name}:{target_port}", "/", current.query, ""))
        return destination

    def do_GET(self) -> None:  # pragma: no cover - exercised via HTTP smoke test
        self.send_response(302)
        self.send_header("Location", self._redirect_target())
        self.end_headers()

    def do_HEAD(self) -> None:  # pragma: no cover - exercised via HTTP smoke test
        self.send_response(302)
        self.send_header("Location", self._redirect_target())
        self.end_headers()


def run() -> None:
    settings = get_settings()
    directory = str(static_dir())
    handler = partial(LegacyRedirectHandler, directory=directory)
    server = ThreadingHTTPServer((settings.frontend_host, settings.frontend_port), handler)
    print(
        "Sentinel-Alpha legacy static WebUI is deprecated and now only serves HTTP redirects. "
        f"Directory={directory} URL=http://{settings.frontend_host}:{settings.frontend_port}"
    )
    server.serve_forever()


if __name__ == "__main__":
    run()

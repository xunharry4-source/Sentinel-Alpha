from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from sentinel_alpha.config import get_settings
from sentinel_alpha.webapp import static_dir


def run() -> None:
    settings = get_settings()
    directory = str(static_dir())
    handler = partial(SimpleHTTPRequestHandler, directory=directory)
    server = ThreadingHTTPServer((settings.frontend_host, settings.frontend_port), handler)
    print(f"Sentinel-Alpha web module serving {directory} at http://{settings.frontend_host}:{settings.frontend_port}")
    server.serve_forever()


if __name__ == "__main__":
    run()

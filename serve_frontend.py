#!/usr/bin/env python3
"""Midair.io — スタンドアロン配信サーバー（/Midair.io/ サブパス対応）

Cloudflare Tunnel から localhost:8090 に来たリクエストを、
frontend/dist の静的ファイル（サブパス /Midair.io/ 配下）へマッピングして返す。

- /Midair.io/            → frontend/dist/index.html
- /Midair.io/assets/xxx  → frontend/dist/assets/xxx
- SPA フォールバック: /Midair.io/ 以下の未知パス → index.html

API / WebSocket はトンネルの ingress で localhost:8000 に振り分けられるため、
このサーバーは静的配信のみを担当する。
"""
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
PREFIX = "/Midair.io"
PORT = int(os.environ.get("PORT", "8090"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def _strip_prefix(self):
        path = self.path
        if path == PREFIX:
            path = PREFIX + "/"
        if path.startswith(PREFIX + "/"):
            return path[len(PREFIX):]
        return path

    def do_GET(self):
        self.path = self._strip_prefix()
        # SPA フォールバック（拡張子のないパスは index.html）
        local = self.translate_path(self.path)
        if not os.path.exists(local) and "." not in os.path.basename(self.path):
            self.path = "/index.html"
        return super().do_GET()

    def do_HEAD(self):
        self.path = self._strip_prefix()
        local = self.translate_path(self.path)
        if not os.path.exists(local) and "." not in os.path.basename(self.path):
            self.path = "/index.html"
        return super().do_HEAD()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    os.chdir(DIST_DIR)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Midair.io frontend serving on http://127.0.0.1:{PORT}{PREFIX}/")
    server.serve_forever()

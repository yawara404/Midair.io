#!/usr/bin/env python3
"""Midair.io — スタンドアロン配信サーバー（サブドメインのルート直下配信）

Cloudflare Tunnel から localhost:8090 に来たリクエストを、
frontend/dist の静的ファイルへマッピングして返す。

- /            → frontend/dist/index.html
- /assets/xxx  → frontend/dist/assets/xxx
- SPA フォールバック: 未知パス（拡張子なし） → index.html

API / WebSocket はトンネルの ingress で localhost:8000 に振り分けられるため、
このサーバーは静的配信のみを担当する。

公開URL: https://radio.wawa-app.me/（専用サブドメイン・ルート配信）
旧サブパス配信（/Midair.io/ など）に戻す場合は PREFIX=/Midair.io を指定する。
"""
import os
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
# ルート配信なら空。サブパス配信（例: /Midair.io）に戻すときだけ環境変数で指定する。
PREFIX = os.environ.get("PREFIX", "").rstrip("/")
PORT = int(os.environ.get("PORT", "8090"))

# ハッシュ付きファイル名（Viteのビルド成果物）。内容が変わると名前も変わるので長期キャッシュできる
HASHED = re.compile(r"-[A-Za-z0-9_-]{8,}\.(js|css|png|jpg|jpeg|svg|webp|woff2?)$", re.I)
# ほぼ静的なファイル（内容が変わるときはURLかキャッシュ期間で調整）
STATIC_EXT = re.compile(r"\.(png|jpg|jpeg|svg|webp|ico|woff2?|txt|xml)$", re.I)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def _strip_prefix(self):
        path = self.path
        if not PREFIX:
            # ルート配信（radio.wawa-app.me）ではそのまま
            return path
        if path == PREFIX:
            path = PREFIX + "/"
        if path.startswith(PREFIX + "/"):
            return path[len(PREFIX):]
        return path

    def _redirect_root(self):
        """サブパス配信（PREFIX 指定）では、サブドメインのルートを PREFIX/ へ302する。

        vocaloid.hz（Nuxt が / を /Vocaloid.hz/ へ302）と同じ振る舞いに揃えるため。
        ルート配信（PREFIX が空）では何もしない。
        """
        if not PREFIX:
            return False
        if self.path.split("?")[0] not in ("", "/"):
            return False
        self.send_response(302)
        self.send_header("Location", PREFIX + "/")
        self.end_headers()
        return True

    def do_GET(self):
        if self._redirect_root():
            return
        self.path = self._strip_prefix()
        # SPA フォールバック（拡張子のないパスは index.html）
        local = self.translate_path(self.path)
        if not os.path.exists(local) and "." not in os.path.basename(self.path):
            self.path = "/index.html"
        return super().do_GET()

    def do_HEAD(self):
        if self._redirect_root():
            return
        self.path = self._strip_prefix()
        local = self.translate_path(self.path)
        if not os.path.exists(local) and "." not in os.path.basename(self.path):
            self.path = "/index.html"
        return super().do_HEAD()

    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        """負荷対策（再訪時の転送量削減）: 内容に応じた Cache-Control を付ける。"""
        path = self.path.split("?")[0]
        if HASHED.search(os.path.basename(path)):
            # ビルド成果物（ハッシュ付き）は内容が変わるとURLも変わる
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        elif path.endswith("/") or path.endswith(".html"):
            # HTMLは常に最新を確認（デプロイ直後の取りこぼし防止）
            self.send_header("Cache-Control", "no-cache")
        elif STATIC_EXT.search(path):
            self.send_header("Cache-Control", "public, max-age=86400")
        else:
            self.send_header("Cache-Control", "public, max-age=3600")
        super().end_headers()


if __name__ == "__main__":
    os.chdir(DIST_DIR)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Midair.io frontend serving on http://127.0.0.1:{PORT}{PREFIX}/")
    server.serve_forever()

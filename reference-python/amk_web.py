#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
amk_web.py — a tiny HTTP server for Aminakawa.
No Flask, no frameworks: only the Python standard library (http.server).

Used by the language via built-ins:  route("/path", func)  and  serve(port).
Each route's func returns a string (the HTML) that gets sent to the browser.
"""
import http.server

_routes = {}


def add_route(path, handler):
    _routes[path] = handler


def _make_handler():
    class H(http.server.BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path != "/" and path.endswith("/"):
                path = path[:-1]
            handler = _routes.get(path)
            if handler is None:
                self._send(404, "<h1>404</h1><p>page not found</p>")
                return
            try:
                text = handler()
            except Exception as e:
                self._send(500, "<h1>500</h1><pre>%s</pre>" % e)
                return
            self._send(200, text if isinstance(text, str) else str(text))

        def log_message(self, fmt, *args):
            pass  # keep the terminal quiet

    return H


def serve(port=8080):
    httpd = http.server.HTTPServer(("", int(port)), _make_handler())
    print("[web] running at http://localhost:%d   (Ctrl+C to stop)" % port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[web] stopping...")
    finally:
        httpd.server_close()

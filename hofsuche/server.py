"""Kleiner lokaler Webserver für das Dashboard. Läuft nur auf deinem Rechner (127.0.0.1)."""
from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import scoring, store, update
from .config import ROOT

WEB = ROOT / "web"
_lock = threading.Lock()   # SQLite-Schreibzugriffe und Suchläufe nacheinander


def _payload(cfg: dict) -> dict:
    con = store.connect()
    try:
        rows = store.alle(con)
    finally:
        con.close()
    for r in rows:
        r["bewertung"] = scoring.bewerte(r, cfg)
    return {
        "inserate": rows,
        "gewichte": cfg["gewichte"],
        "kriterien": cfg["kriterien"],
        "sanierung": cfg["sanierung"],
        "suchquellen": {"mail": bool(cfg["mail"].get("aktiv")), "web": bool(cfg["web"].get("aktiv"))},
    }


def make_handler(cfg: dict):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # ruhigeres Terminal
            pass

        def _json(self, data, status=HTTPStatus.OK):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                body = (WEB / "index.html").read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/inserate":
                self._json(_payload(cfg))
            else:
                self._json({"fehler": "Nicht gefunden"}, HTTPStatus.NOT_FOUND)

        def do_PATCH(self):
            if not self.path.startswith("/api/inserate/"):
                return self._json({"fehler": "Nicht gefunden"}, HTTPStatus.NOT_FOUND)
            lid = self.path.rsplit("/", 1)[1]
            try:
                patch = self._body()
                with _lock:
                    con = store.connect()
                    try:
                        store.aendern(con, lid, patch)
                    finally:
                        con.close()
            except KeyError:
                return self._json({"fehler": "Inserat nicht gefunden"}, HTTPStatus.NOT_FOUND)
            except (ValueError, json.JSONDecodeError) as e:
                return self._json({"fehler": str(e)}, HTTPStatus.BAD_REQUEST)
            self._json({"ok": True})

        def do_POST(self):
            if self.path != "/api/suchlauf":
                return self._json({"fehler": "Nicht gefunden"}, HTTPStatus.NOT_FOUND)
            if not _lock.acquire(blocking=False):
                return self._json({"fehler": "Es läuft schon ein Suchlauf."}, HTTPStatus.CONFLICT)
            protokoll: list[str] = []
            try:
                con = store.connect()
                try:
                    ergebnis = update.lauf(cfg, con, log=protokoll.append)
                finally:
                    con.close()
            except Exception as e:
                return self._json({"fehler": str(e), "protokoll": protokoll}, HTTPStatus.INTERNAL_SERVER_ERROR)
            finally:
                _lock.release()
            self._json({**ergebnis, "protokoll": protokoll})

    return Handler


def starten(cfg: dict, port: int | None = None) -> None:
    port = port or int(cfg["server"]["port"])
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(cfg))
    print(f"Dashboard läuft: http://localhost:{port}  (Beenden mit Strg+C)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")

"""Höflicher Seitenabruf: feste Pause zwischen Anfragen, keine Umgehung von Sperren."""
from __future__ import annotations

import gzip
import time
import urllib.error
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
SPERR_HINWEISE = (
    "ich bin kein roboter", "captcha", "access denied", "zugriff verweigert",
    "unusual traffic", "are you a robot", "bitte bestätigen sie, dass sie ein mensch",
)


class Gesperrt(Exception):
    """Das Portal hat den Abruf blockiert. Nicht wiederholen."""


class Abrufer:
    def __init__(self, pause: float = 8.0) -> None:
        self.pause = max(3.0, float(pause))   # unter 3 Sekunden gehen wir nie
        self._letzter = 0.0
        self.gesperrt: set[str] = set()

    def hole(self, url: str) -> str:
        host = urllib.request.urlparse(url).netloc
        if host in self.gesperrt:
            raise Gesperrt(host)
        warten = self._letzter + self.pause - time.monotonic()
        if warten > 0:
            time.sleep(warten)
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "de-DE,de;q=0.9",
            "Accept-Encoding": "gzip",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                charset = resp.headers.get_content_charset() or "utf-8"
        except urllib.error.HTTPError as e:
            self._letzter = time.monotonic()
            if e.code in (401, 403, 429):
                self.gesperrt.add(host)
                raise Gesperrt(f"{host} antwortet mit {e.code}") from e
            raise
        self._letzter = time.monotonic()
        text = raw.decode(charset, errors="replace")
        kopf = text[:20000].lower()
        # Echte Such- und Exposéseiten sind groß; eine kleine Seite mit Captcha-Text ist eine Sperre
        if len(text) < 60000 and any(h in kopf for h in SPERR_HINWEISE):
            self.gesperrt.add(host)
            raise Gesperrt(f"{host} zeigt eine Bot-Abfrage")
        return text

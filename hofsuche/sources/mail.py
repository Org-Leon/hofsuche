"""E-Mail-Suchaufträge der Portale per IMAP auslesen.

Die Portale verschicken bei neuen Treffern Mails mit Links zu den Exposés. Wir lesen
nur Mails der eingetragenen Absender, suchen darin Exposé-Links und nehmen den
umgebenden Text als erste Beschreibung. Mails werden nicht verändert oder gelöscht.
"""
from __future__ import annotations

import email
import imaplib
import os
import re
from datetime import date, timedelta
from email.header import decode_header, make_header

from .. import parse


def _dekodiere(raw) -> str:
    try:
        return str(make_header(decode_header(raw or "")))
    except Exception:
        return raw or ""


def _teile(msg: email.message.Message) -> tuple[str, str]:
    html_teile, text_teile = [], []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        typ = part.get_content_type()
        if typ not in ("text/html", "text/plain"):
            continue
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        inhalt = payload.decode(charset, errors="replace")
        (html_teile if typ == "text/html" else text_teile).append(inhalt)
    return "\n".join(html_teile), "\n".join(text_teile)


def _umgebung(text: str, schluessel: str, breite: int = 500) -> str:
    """Text rund um die erste Fundstelle eines Exposé-Schlüssels."""
    i = text.find(schluessel)
    if i < 0:
        return ""
    return text[max(0, i - breite): i + breite]


def treffer_aus_mail(roh: bytes) -> list[dict]:
    msg = email.message_from_bytes(roh)
    betreff = _dekodiere(msg.get("Subject"))
    html, plain = _teile(msg)
    gesamt = html + "\n" + plain
    text = parse.html_zu_text(html)[0] if html else plain
    out = []
    for lid, url in parse.finde_exposes(gesamt):
        nummer = lid.split("-", 1)[1]
        # Kontext: im Klartext der Mail rund um den Link (Titel, Preis, Fläche stehen meist daneben)
        kontext = _umgebung(plain, nummer) or _umgebung(text, nummer) or text[:800]
        eintrag = parse.aus_text(url, kontext)
        eintrag["id"] = lid
        eintrag["info"] = f"Aus Suchauftrag-Mail „{betreff[:80]}“. " + re.sub(r"\s+", " ", kontext)[:300]
        out.append(eintrag)
    return out


def hole(cfg: dict, log=print) -> list[dict]:
    m = cfg["mail"]
    passwort = os.environ.get("HOFSUCHE_IMAP_PASSWORT")
    if not m.get("benutzer") or not passwort:
        log("Mail: Benutzer oder HOFSUCHE_IMAP_PASSWORT fehlt, überspringe.")
        return []
    seit = (date.today() - timedelta(days=int(m.get("tage", 14)))).strftime("%d-%b-%Y")
    treffer: dict[str, dict] = {}
    with imaplib.IMAP4_SSL(m["host"], int(m.get("port", 993))) as imap:
        imap.login(m["benutzer"], passwort)
        imap.select(m.get("ordner", "INBOX"), readonly=True)
        for absender in m.get("absender", []):
            status, daten = imap.search(None, "SINCE", seit, "FROM", f'"{absender}"')
            if status != "OK":
                continue
            ids = daten[0].split()
            log(f"Mail: {len(ids)} Nachrichten von {absender}")
            for num in ids:
                status, teile = imap.fetch(num, "(BODY.PEEK[])")
                if status != "OK" or not teile or not isinstance(teile[0], tuple):
                    continue
                for eintrag in treffer_aus_mail(teile[0][1]):
                    treffer.setdefault(eintrag["id"], eintrag)
    log(f"Mail: {len(treffer)} Exposé-Links gefunden")
    return list(treffer.values())

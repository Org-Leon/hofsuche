"""Gespeicherte Suchseiten der Portale abrufen und neue Exposés im Detail lesen.

Achtung: Die Portale untersagen automatisierte Abrufe in ihren Nutzungsbedingungen.
Dieses Modul ist für seltene, private Abfragen gedacht (z. B. einmal am Tag), hält
eine feste Pause ein und hört bei einer Sperre sofort auf. Es versucht nie, eine
Bot-Abfrage oder Sperre zu umgehen. ImmoScout24 blockt solche Abrufe praktisch immer;
dafür sind die E-Mail-Suchaufträge der bessere Weg.
"""
from __future__ import annotations

from .. import parse
from .http import Abrufer, Gesperrt


def links_von_suchseiten(cfg: dict, abrufer: Abrufer, log=print) -> list[tuple[str, str]]:
    gefunden: dict[str, str] = {}
    for url in cfg["web"].get("suchseiten", []):
        try:
            doc = abrufer.hole(url)
        except Gesperrt as e:
            log(f"Web: gesperrt ({e}), lasse diesen Host für diesen Lauf aus.")
            continue
        except Exception as e:   # Netzwerkfehler sollen den Lauf nicht abbrechen
            log(f"Web: Fehler bei {url}: {e}")
            continue
        treffer = parse.finde_exposes(doc)
        log(f"Web: {len(treffer)} Exposés auf {url[:80]}")
        for lid, link in treffer:
            gefunden.setdefault(lid, link)
    return list(gefunden.items())


def details(url: str, abrufer: Abrufer) -> dict | None:
    try:
        doc = abrufer.hole(url)
    except Gesperrt:
        return None
    eintrag = parse.lese_inserat(url, doc)
    eintrag["geprueft"] = True
    return eintrag

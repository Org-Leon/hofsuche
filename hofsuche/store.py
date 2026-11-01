"""SQLite-Speicher. Eine Zeile pro Inserat.

- data:      was aus Inserat, Mail oder Startliste kommt (wird bei neuen Funden ergänzt)
- korrektur: deine Änderungen im Dashboard (z. B. Grundstücksgröße, Bahn). Gewinnt immer.
- status, notiz: deine Markierungen
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from .config import DATA

DB_PATH = DATA / "hofsuche.db"

# Felder, die du im Dashboard korrigieren darfst
EDITIERBAR = {
    "preis", "wf", "grund", "zustand", "bahn", "bahnText", "fahrzeit", "ziel",
    "ruhe", "neben", "ilbOrt", "land", "ort", "gemeinde", "makler",
}
STATUS = {"neu", "merken", "besichtigen", "raus"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
  id         TEXT PRIMARY KEY,
  data       TEXT NOT NULL,
  korrektur  TEXT NOT NULL DEFAULT '{}',
  status     TEXT NOT NULL DEFAULT 'neu',
  notiz      TEXT NOT NULL DEFAULT '',
  erstmals   TEXT NOT NULL,
  zuletzt    TEXT NOT NULL
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def upsert(con: sqlite3.Connection, listing: dict, heute: str | None = None) -> bool:
    """Speichert ein Inserat. Gibt True zurück, wenn es neu ist.

    Bei bekannten Inseraten werden nur Felder ergänzt oder aktualisiert, die jetzt
    einen Wert haben. Leere Werte überschreiben nie bekannte.
    """
    heute = heute or date.today().isoformat()
    lid = listing["id"]
    neu_data = {k: v for k, v in listing.items() if k != "id"}
    row = con.execute("SELECT data FROM listings WHERE id = ?", (lid,)).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO listings (id, data, erstmals, zuletzt) VALUES (?, ?, ?, ?)",
            (lid, json.dumps(neu_data, ensure_ascii=False), heute, heute),
        )
        return True
    alt = json.loads(row["data"])
    for k, v in neu_data.items():
        if v not in (None, "", []):
            alt[k] = v
    con.execute(
        "UPDATE listings SET data = ?, zuletzt = ? WHERE id = ?",
        (json.dumps(alt, ensure_ascii=False), heute, lid),
    )
    return False


def alle(con: sqlite3.Connection) -> list[dict]:
    out = []
    for row in con.execute("SELECT * FROM listings ORDER BY erstmals DESC"):
        d = json.loads(row["data"])
        korr = json.loads(row["korrektur"])
        d.update(korr)
        d.update(
            id=row["id"], status=row["status"], notiz=row["notiz"],
            erstmals=row["erstmals"], zuletzt=row["zuletzt"], korrigiert=sorted(korr),
        )
        out.append(d)
    return out


def ist_bekannt(con: sqlite3.Connection, lid: str) -> bool:
    return con.execute("SELECT 1 FROM listings WHERE id = ?", (lid,)).fetchone() is not None


def aendern(con: sqlite3.Connection, lid: str, patch: dict) -> None:
    """Status, Notiz oder Korrekturen aus dem Dashboard speichern."""
    row = con.execute("SELECT korrektur FROM listings WHERE id = ?", (lid,)).fetchone()
    if row is None:
        raise KeyError(lid)
    if "status" in patch:
        if patch["status"] not in STATUS:
            raise ValueError(f"Unbekannter Status: {patch['status']}")
        con.execute("UPDATE listings SET status = ? WHERE id = ?", (patch["status"], lid))
    if "notiz" in patch:
        con.execute("UPDATE listings SET notiz = ? WHERE id = ?", (str(patch["notiz"])[:5000], lid))
    korr_patch = patch.get("korrektur") or {}
    unbekannt = set(korr_patch) - EDITIERBAR
    if unbekannt:
        raise ValueError(f"Nicht änderbar: {', '.join(sorted(unbekannt))}")
    if korr_patch:
        korr = json.loads(row["korrektur"])
        for k, v in korr_patch.items():
            if v is None or v == "":
                korr.pop(k, None)   # leer = Korrektur zurücknehmen
            else:
                korr[k] = v
        con.execute("UPDATE listings SET korrektur = ? WHERE id = ?",
                    (json.dumps(korr, ensure_ascii=False), lid))
    con.commit()

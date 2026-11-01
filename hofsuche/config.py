"""Konfiguration laden: config.toml (falls vorhanden) über die Standardwerte legen."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

DEFAULTS: dict = {
    "kriterien": {
        "min_grundstueck_m2": 3000,
        "min_wohnflaeche_m2": 120,
        "budget_eur": 400_000,
        "budget_voll_eur": 250_000,
        "budget_null_eur": 450_000,
        "fahrzeit_voll_min": 45,
        "fahrzeit_null_min": 120,
    },
    "gewichte": {
        "budget": 25, "oepnv": 20, "fahrzeit": 15, "neben": 10,
        "ruhe": 10, "zustand": 10, "ilb": 10, "region": 10,
    },
    "sanierung": {
        "saniert": 150, "gepflegt": 350, "renov": 700,
        "saniebed": 1200, "rohbau": 1500, "unbekannt": 800,
    },
    "mail": {
        "aktiv": False, "host": "imap.gmail.com", "port": 993, "benutzer": "",
        "ordner": "INBOX", "tage": 14,
        "absender": ["immobilienscout24.de", "immowelt.de", "kleinanzeigen.de", "ohne-makler.net"],
    },
    "web": {"aktiv": False, "pause_sekunden": 8, "max_details": 25, "suchseiten": []},
    "server": {"port": 8765},
}


def _merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for key, val in extra.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], val)
        else:
            out[key] = val
    return out


def load_env(path: Path | None = None) -> None:
    """Liest eine einfache .env-Datei (KEY=wert) in os.environ, ohne Vorhandenes zu überschreiben."""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def load(path: Path | None = None) -> dict:
    load_env()
    path = path or ROOT / "config.toml"
    if path.exists():
        with path.open("rb") as fh:
            return _merge(DEFAULTS, tomllib.load(fh))
    return _merge(DEFAULTS, {})

"""Befehle: python -m hofsuche <befehl>

  start     Startliste (die 34 Inserate vom 01.11.2026) in die Datenbank laden
  suche     Einen Suchlauf machen (Mails und, falls eingeschaltet, Suchseiten)
  liste     Rangliste im Terminal anzeigen
  dashboard Dashboard im Browser starten (http://localhost:8765)
"""
from __future__ import annotations

import argparse
import json
import sys

from . import config, scoring, store, update
from .config import DATA
from .parse import id_aus_url


def cmd_start(cfg, args):
    con = store.connect()
    liste = json.loads((DATA / "startliste.json").read_text(encoding="utf-8"))
    neu = 0
    for eintrag in liste:
        eintrag = dict(eintrag)
        # gleiche ID wie bei späteren Funden aus Mail oder Suchseite, damit nichts doppelt erscheint
        eintrag["id"] = id_aus_url(eintrag["url"])
        neu += store.upsert(con, eintrag, eintrag.get("gefunden"))
    con.commit()
    print(f"Startliste geladen: {neu} neu, {len(liste) - neu} schon vorhanden.")


def cmd_suche(cfg, args):
    update.lauf(cfg)


def cmd_liste(cfg, args):
    con = store.connect()
    rows = store.alle(con)
    if not rows:
        print("Noch keine Inserate. Erst `python -m hofsuche start` oder `suche` ausführen.")
        return
    bewertet = []
    for r in rows:
        b = scoring.bewerte(r, cfg)
        bewertet.append((scoring.punkte(b["komponenten"], cfg["gewichte"]), r, b))
    bewertet.sort(key=lambda t: (bool(t[2]["muss"]), t[1].get("status") == "raus", -t[0]))
    print(f"{'#':>3}  {'Pkt':>3}  {'Preis+San.':>11}  {'Grund':>8}  Ort / Titel")
    def tsd(n: float) -> str:
        return f"{n:,.0f}".replace(",", ".")

    for i, (p, r, b) in enumerate(bewertet[: args.anzahl], 1):
        grund = tsd(r["grund"]) if r.get("grund") else "?"
        flag = " RAUS" if b["muss"] else (" >Budget" if b["ueber_budget"] else "")
        print(f"{i:>3}  {p:>3.0f}  {tsd(b['basis']):>11}  {grund:>8}  {r.get('ort') or '?'}: {(r.get('titel') or '')[:50]}{flag}")


def cmd_dashboard(cfg, args):
    from . import server
    server.starten(cfg, args.port)


def main(argv=None):
    p = argparse.ArgumentParser(prog="hofsuche", description="Häuser und Höfe finden und ranken.")
    sub = p.add_subparsers(dest="befehl", required=True)
    sub.add_parser("start", help="Startliste in die Datenbank laden")
    sub.add_parser("suche", help="Suchlauf: Mails und Suchseiten auswerten")
    pl = sub.add_parser("liste", help="Rangliste im Terminal")
    pl.add_argument("-n", "--anzahl", type=int, default=20)
    pd = sub.add_parser("dashboard", help="Dashboard im Browser starten")
    pd.add_argument("--port", type=int)
    args = p.parse_args(argv)
    cfg = config.load()
    {"start": cmd_start, "suche": cmd_suche, "liste": cmd_liste, "dashboard": cmd_dashboard}[args.befehl](cfg, args)


if __name__ == "__main__":
    sys.exit(main())

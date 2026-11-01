"""Ein Suchlauf: Mails und (falls eingeschaltet) Suchseiten auswerten, Neues speichern."""
from __future__ import annotations

from datetime import date

from . import store
from .sources import mail, web
from .sources.http import Abrufer


def lauf(cfg: dict, con=None, log=print) -> dict:
    con = con or store.connect()
    heute = date.today().isoformat()
    neu, bekannt = [], 0
    abrufer = Abrufer(cfg["web"].get("pause_sekunden", 8)) if cfg["web"].get("aktiv") else None
    detail_budget = int(cfg["web"].get("max_details", 25))

    def anreichern(eintrag: dict) -> dict:
        nonlocal detail_budget
        # ImmoScout blockt automatisierte Abrufe; dort bleibt es bei den Mail-Angaben.
        if abrufer and detail_budget > 0 and not eintrag["id"].startswith("immoscout-"):
            detail_budget -= 1
            voll = web.details(eintrag["url"], abrufer)
            if voll:
                voll["id"] = eintrag["id"]
                return voll
        return eintrag

    def speichern(eintrag: dict) -> None:
        nonlocal bekannt
        eintrag.setdefault("gefunden", heute)
        if store.upsert(con, eintrag, heute):
            neu.append(eintrag)
            log(f"  neu: {eintrag.get('titel', '')[:60]} ({eintrag.get('ort') or '?'})")
        else:
            bekannt += 1

    if cfg["mail"].get("aktiv"):
        try:
            for eintrag in mail.hole(cfg, log=log):
                if not store.ist_bekannt(con, eintrag["id"]):
                    eintrag = anreichern(eintrag)
                speichern(eintrag)
        except Exception as e:
            log(f"Mail: Abruf fehlgeschlagen: {e}")

    if abrufer:
        for lid, url in web.links_von_suchseiten(cfg, abrufer, log=log):
            if store.ist_bekannt(con, lid):
                store.upsert(con, {"id": lid, "url": url}, heute)   # nur „zuletzt gesehen“ aktualisieren
                bekannt += 1
                continue
            eintrag = anreichern({"id": lid, "url": url, "titel": "Inserat", "geprueft": False})
            speichern(eintrag)

    con.commit()
    log(f"Fertig: {len(neu)} neue Inserate, {bekannt} bekannte aktualisiert.")
    return {"neu": len(neu), "bekannt": bekannt}

"""Bewertung eines Inserats.

Liefert für jedes Kriterium einen Wert zwischen 0 und 1. Das Dashboard gewichtet
diese Werte mit den Reglern; so bleibt die Rechenlogik an einer Stelle.
"""
from __future__ import annotations

from .ilb import ILB_MIN_SANIERUNG_QM, ILB_WF_MAX, ILB_WF_MAX_ELW

KRITERIEN = ["budget", "oepnv", "fahrzeit", "neben", "ruhe", "zustand", "ilb", "region"]

GRUNDERWERBSTEUER = {"BB": 0.065, "SN": 0.055}
NOTAR_GRUNDBUCH = 0.02
MAKLER = 0.0357
WF_ANNAHME = 150  # wenn die Wohnfläche fehlt


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _linear(wert: float, voll: float, null: float) -> float:
    """1 bei `voll`, 0 bei `null`, dazwischen linear."""
    if voll == null:
        return 1.0 if wert <= voll else 0.0
    return _clamp((null - wert) / (null - voll))


def bewerte(r: dict, cfg: dict) -> dict:
    k = cfg["kriterien"]
    raten = cfg["sanierung"]
    zustand = r.get("zustand") or "unbekannt"
    rate = raten.get(zustand, raten["unbekannt"])
    wf = r.get("wf")
    grund = r.get("grund")
    preis = r.get("preis")

    sanierung = (wf or WF_ANNAHME) * rate
    basis = (preis or 0) + sanierung
    nk = (preis or 0) * (GRUNDERWERBSTEUER.get(r.get("land"), 0.065) + NOTAR_GRUNDBUCH
                         + (MAKLER if r.get("makler", True) else 0))

    c: dict[str, float] = {}
    c["budget"] = _linear(basis, k["budget_voll_eur"], k["budget_null_eur"]) if preis else 0.3
    bahn = r.get("bahn")
    c["oepnv"] = _clamp(bahn / 3) if bahn is not None else 0.3
    fz = r.get("fahrzeit")
    c["fahrzeit"] = _linear(fz, k["fahrzeit_voll_min"], k["fahrzeit_null_min"]) if fz else 0.3
    neben = r.get("neben")
    c["neben"] = _clamp(neben / 2) if neben is not None else 0.25
    ruhe = r.get("ruhe")
    c["ruhe"] = _clamp(ruhe / 3) if ruhe is not None else 0.5
    if zustand == "unbekannt":
        c["zustand"] = 0.4
    else:
        lo, hi = min(raten.values()), max(raten.values())
        c["zustand"] = _clamp(1 - (rate - lo) / ((hi - lo) or 1))

    ilb, ilb_text = 0.0, ""
    if r.get("land") == "BB" and r.get("ilbOrt") != "nein":
        genug = rate >= ILB_MIN_SANIERUNG_QM
        wf_cmp = wf if wf is not None else 10_000
        if genug and wf_cmp <= ILB_WF_MAX:
            ilb, ilb_text = 1.0, "ILB passt"
        elif genug and wf_cmp <= ILB_WF_MAX_ELW:
            ilb, ilb_text = 0.6, "ILB nur mit Einliegerwohnung"
        elif not genug:
            ilb, ilb_text = 0.2, "ILB: zu wenig Sanierung"
        else:
            ilb, ilb_text = 0.2, "ILB: Wohnfläche zu groß"
        if r.get("ilbOrt") == "prüfen":
            ilb *= 0.5
            ilb_text += " (Ort prüfen)"
        if wf is None:
            ilb_text = "ILB-Ort, Wohnfläche unbekannt"
    c["ilb"] = ilb
    c["region"] = 1.0 if r.get("land") == "BB" else 0.4

    muss: list[str] = []
    if wf is not None and wf < k["min_wohnflaeche_m2"]:
        muss.append(f"Wohnfläche unter {k['min_wohnflaeche_m2']} m²")
    if grund is not None and grund < k["min_grundstueck_m2"]:
        muss.append(f"Grundstück unter {k['min_grundstueck_m2']:,} m²".replace(",", "."))

    return {
        "komponenten": c,
        "sanierung": round(sanierung),
        "basis": round(basis),
        "nebenkosten": round(nk),
        "gesamt": round(basis + nk),
        "ueber_budget": basis > k["budget_eur"],
        "ilb_text": ilb_text,
        "muss": muss,
    }


def punkte(komponenten: dict[str, float], gewichte: dict[str, float]) -> float:
    summe = sum(gewichte.get(k, 0) for k in KRITERIEN) or 1
    return sum(komponenten[k] * gewichte.get(k, 0) for k in KRITERIEN) / summe * 100

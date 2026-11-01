"""ILB-Wohneigentumsförderung: Liegt ein Ort in einer Gemeinde mit Gebietskulisse?

Grundlage: LBV-Karte „Gebietskulissen der Städtebau- und Wohnraumförderung“,
Stichtag 30.06.2026 (166 Gemeinden). Die Karte unterscheidet nicht zwischen
Gemeinden, die nur Städtebauförderung haben (27), und solchen mit Wohnraumförderung.
Ob ein Ortsteil zählt, bestätigt die Gemeinde mit der städtebaulichen Stellungnahme.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from .config import DATA

# Richtlinie vom 13.02.2026: Wohnflächengrenzen beim Bestandserwerb (+20 %)
ILB_WF_MAX = 168          # 140 m² + 20 %
ILB_WF_MAX_ELW = 240      # 200 m² mit Einliegerwohnung + 20 %
ILB_MIN_SANIERUNG_QM = 500


def _norm(name: str) -> str:
    name = unicodedata.normalize("NFKC", name).lower()
    name = re.sub(r"\(.*?\)", " ", name)          # „Lindow (Mark)“ -> „lindow“
    name = name.replace("/", " ")
    name = re.sub(r"\b(stadt|gemeinde|ot|ortsteil)\b", " ", name)
    return re.sub(r"[^a-zäöüß]+", " ", name).strip()


@lru_cache(maxsize=1)
def orte() -> dict[str, str]:
    """Normalisierter Name -> Originalname aller Gemeinden mit Kulisse."""
    out: dict[str, str] = {}
    for line in (DATA / "ilb_orte.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out[_norm(line)] = line
            # „Wiesenburg/Mark“ oder „Lindow (Mark)“ auch über den Teil davor finden
            kurz = re.split(r"[/(]", line)[0]
            out.setdefault(_norm(kurz), line)
    return out


def status(*namen: str | None) -> str:
    """'ja', 'nein' oder 'prüfen' (kein Ortsname bekannt)."""
    kandidaten = [n for n in namen if n]
    if not kandidaten:
        return "prüfen"
    table = orte()
    for name in kandidaten:
        if _norm(name) in table or _norm(re.split(r"[/(,]", name)[0]) in table:
            return "ja"
    return "nein"

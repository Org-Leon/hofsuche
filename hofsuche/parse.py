"""Inserate erkennen und Angaben aus dem Text herauslesen.

Der Parser arbeitet bewusst mit dem sichtbaren Text („Wohnfläche 120 m²“) statt mit
dem HTML-Aufbau der Portale. Der ändert sich oft, die Beschriftungen kaum.
"""
from __future__ import annotations

import hashlib
import html
import re
from html.parser import HTMLParser
from urllib.parse import unquote

# --- Exposé-Links erkennen -------------------------------------------------------

PORTALE = [
    ("immoscout", re.compile(r"immobilienscout24\.de/expose/(\d{6,})")),
    ("kleinanzeigen", re.compile(r"kleinanzeigen\.de/s-anzeige/[^\s\"'<>?#]*?/(\d{8,})-\d+-\d+")),
    ("immowelt", re.compile(r"immowelt\.de/expose/([A-Za-z0-9-]{6,})")),
    ("ohnemakler", re.compile(r"ohne-makler\.net/immobilie/(\d{4,})")),
]
KANONISCH = {
    "immoscout": "https://www.immobilienscout24.de/expose/{}",
    "immowelt": "https://www.immowelt.de/expose/{}",
    "ohnemakler": "https://www.ohne-makler.net/immobilie/{}/",
}
QUELLE = {
    "immoscout": "ImmoScout24", "kleinanzeigen": "Kleinanzeigen",
    "immowelt": "Immowelt", "ohnemakler": "ohne-makler.net",
}


def finde_exposes(text: str) -> list[tuple[str, str]]:
    """Liefert [(id, url)] für alle Exposé-Links, auch hinter Tracking-Weiterleitungen."""
    # Tracking-Links enthalten das Ziel oft URL-kodiert, teils doppelt
    roh = html.unescape(text)
    kandidaten = roh + "\n" + unquote(roh) + "\n" + unquote(unquote(roh))
    gefunden: dict[str, str] = {}
    for portal, rx in PORTALE:
        for m in rx.finditer(kandidaten):
            lid = f"{portal}-{m.group(1)}"
            if lid in gefunden:
                continue
            if portal in KANONISCH:
                url = KANONISCH[portal].format(m.group(1))
            else:
                url = "https://www." + m.group(0)
            gefunden[lid] = url
    return list(gefunden.items())


def id_aus_url(url: str) -> str:
    treffer = finde_exposes(url)
    if treffer:
        return treffer[0][0]
    return "url-" + hashlib.sha1(url.encode()).hexdigest()[:12]


# --- HTML zu Text ----------------------------------------------------------------

class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "dt", "dd", "td", "th", "section"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.title = ""
        self._in_title = False
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "meta" and a.get("content"):
            key = a.get("property") or a.get("name") or ""
            if key:
                self.meta[key.lower()] = a["content"]
        if tag in self.SKIP:
            self.skip += 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.out.append(data)


def html_zu_text(doc: str) -> tuple[str, str, dict[str, str]]:
    """Gibt (Text, Seitentitel, Meta-Tags) zurück."""
    p = _Text()
    p.feed(doc)
    text = "".join(p.out)
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip(), p.title.strip(), p.meta


# --- Zahlen und Angaben ----------------------------------------------------------

def _zahl(s: str) -> float | None:
    s = s.strip().replace(" ", "")
    if not s:
        return None
    # deutsche Schreibweise: 1.234,5 -> 1234.5
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


NUM = r"(\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?|\d+(?:,\d+)?)"
RX_PREIS = re.compile(r"(?:Kaufpreis|Preis)\s*:?\s*(?:ca\.\s*)?" + NUM + r"\s*(?:€|EUR|Euro)", re.I)
RX_PREIS_LOSE = re.compile(NUM + r"\s*(?:€|EUR)\b(?:\s*VB)?")
RX_WF = re.compile(r"Wohnfl(?:ä|ae)che\s*(?:\(ca\.\))?\s*:?\s*(?:ca\.\s*|rund\s*)?" + NUM + r"\s*(?:m²|m2|qm)", re.I)
RX_WF_ALT = re.compile(NUM + r"\s*(?:m²|m2|qm)\s*Wohnfl", re.I)
RX_GRUND = re.compile(r"Grundst(?:ü|ue)ck(?:sfl(?:ä|ae)che|sgr(?:ö|oe)(?:ß|ss)e)?\s*(?:\(ca\.\))?\s*:?\s*(?:ca\.\s*|rund\s*|von\s*)?" + NUM + r"\s*(?:m²|m2|qm)", re.I)
RX_GRUND_ALT = re.compile(NUM + r"\s*(?:m²|m2|qm)\s*(?:Grundst|Land\b|Fläche\b)", re.I)
RX_HA = re.compile(NUM + r"\s*(?:ha|Hektar)\b", re.I)
RX_ZIMMER = re.compile(r"Zimmer\s*:?\s*(\d+(?:,5)?)|(\d+(?:,5)?)\s*Zimmer", re.I)
RX_BAUJAHR = re.compile(r"Baujahr\s*:?\s*(?:ca\.\s*|um\s*)?(1[6-9]\d\d|20[0-2]\d)", re.I)
RX_PLZ_ORT = re.compile(r"\b(0[1-9]\d{3}|1[4-9]\d{3})\s+([A-ZÄÖÜ][\wäöüß.\-]+(?:[ /\-][A-ZÄÖÜ(][\wäöüß.()\-]+){0,3})")


def _erste(rx: re.Pattern, text: str) -> float | None:
    for m in rx.finditer(text):
        for g in m.groups():
            if g:
                v = _zahl(g)
                if v:
                    return v
    return None


def land_aus_plz(plz: str | None) -> str | None:
    """Grobe Zuordnung der Postleitzahl zu Brandenburg (BB) oder Sachsen (SN)."""
    if not plz or len(plz) != 5:
        return None
    p = int(plz)
    if 1000 <= p <= 2999 or 4000 <= p <= 4899 or 8000 <= p <= 9999:
        return "SN"
    if 3000 <= p <= 3999 or 4900 <= p <= 4999 or 14400 <= p <= 16999 or 17200 <= p <= 17399 or 19300 <= p <= 19399:
        return "BB"
    return None


ZUSTAND_REGELN = [
    ("rohbau", r"entkernt|rohbau|ruine|abrissreif"),
    ("saniebed", r"sanierungsbed(ü|ue)rftig|handwerkerobjekt|bastlerobjekt|liebhaberobjekt|kernsanierung (erforderlich|notwendig)|leerstand|steht seit .* leer"),
    ("renov", r"renovierungsbed(ü|ue)rftig|modernisierungsbed(ü|ue)rftig|teilsaniert|teilmodernisiert|renovierungsstau"),
    ("saniert", r"kernsaniert|vollsaniert|komplett saniert|neuwertig|erstbezug nach sanierung|hochwertig saniert"),
    ("gepflegt", r"gepflegt|modernisiert|saniert|bezugsfertig|einzugsbereit"),
]


def zustand_aus_text(text: str) -> str:
    t = text.lower()
    for code, rx in ZUSTAND_REGELN:
        if re.search(rx, t):
            return code
    return "unbekannt"


def nebengelass_aus_text(text: str) -> float | None:
    t = text.lower()
    treffer = len(set(re.findall(r"scheune|stallung|stall\b|nebengelass|nebengebäude|remise|werkstatt|schuppen", t)))
    if re.search(r"(drei|vier)[- ]?seit(en)?hof|dreiseithof|vierseithof|resthof|gehöft", t):
        treffer += 2
    return min(2.0, float(treffer)) if treffer else None


def ruhe_aus_text(text: str) -> float | None:
    t = text.lower()
    if re.search(r"alleinlage|einzellage|außenbereich|aussenbereich|sackgasse|am waldrand|absolut ruhig|sehr ruhig", t):
        return 3.0
    if re.search(r"bundesstraße|hauptstraße|durchgangsstraße|\bb ?\d{1,3}\b führt", t):
        return 1.0
    if re.search(r"ruhig|ländlich|idyllisch|dorflage", t):
        return 2.0
    return None


def bahn_aus_text(text: str) -> tuple[float | None, str]:
    """Sehr grob: sucht nach Bahnhof mit Entfernung. Das Ergebnis bitte im Dashboard prüfen."""
    t = text.replace("\n", " ")
    t = re.sub(r"\b(ca|rd|etwa|nur)\.\s*", r"\1 ", t, flags=re.I)   # „ca. 15 km“ nicht am Punkt abbrechen
    m = re.search(r"(Bahnhof|Bahnhaltepunkt|Haltepunkt|S-Bahn|Regionalbahn|RE ?\d+|RB ?\d+)[^.]{0,80}?(\d+(?:,\d+)?)\s*(km|m\b|Minuten|min)", t, re.I)
    if m:
        wert = _zahl(m.group(2)) or 0
        einheit = m.group(3).lower()
        km = wert / 1000 if einheit == "m" else (wert if einheit == "km" else wert / 12)  # Minuten zu Fuß
        stufe = 3.0 if km <= 2 else 2.0 if km <= 6 else 1.0
        return stufe, f"Laut Inserat: {m.group(0).strip()[:120]}"
    if re.search(r"bahnhof|s-bahn|regionalbahn", t, re.I):
        return 2.0, "Bahnhof wird im Inserat erwähnt, Entfernung prüfen"
    if re.search(r"bushaltestelle|buslinie|\bbus\b", t, re.I):
        return 1.0, "Laut Inserat Busanbindung, Bahn prüfen"
    return None, "ÖPNV nicht angegeben, prüfen"


def ist_privat(text: str) -> bool | None:
    t = text.lower()
    if re.search(r"provisionsfrei|keine käuferprovision|von privat|privatverkauf|ohne makler", t):
        return False
    if re.search(r"käuferprovision|maklercourtage|provision", t):
        return True
    return None


def lese_inserat(url: str, doc_html: str, quelle: str | None = None) -> dict:
    """Wertet eine Exposé-Seite aus. Felder, die nicht gefunden werden, bleiben None."""
    text, titel, meta = html_zu_text(doc_html)
    titel = meta.get("og:title") or titel
    titel = re.sub(r"\s*[|–-]\s*(Kleinanzeigen|immowelt|ImmoScout24|Immobilienscout24).*$", "", titel, flags=re.I).strip()
    return aus_text(url, text, titel=titel, quelle=quelle)


def aus_text(url: str, text: str, titel: str = "", quelle: str | None = None) -> dict:
    lid = id_aus_url(url)
    portal = lid.split("-")[0]
    plz = ort = None
    m = RX_PLZ_ORT.search(text)
    if m:
        plz, ort = m.group(1), m.group(2).strip()
    preis = _erste(RX_PREIS, text) or _erste(RX_PREIS_LOSE, text)
    wf = _erste(RX_WF, text) or _erste(RX_WF_ALT, text)
    grund = _erste(RX_GRUND, text) or _erste(RX_GRUND_ALT, text)
    if grund is None:
        ha = _erste(RX_HA, text)
        if ha and ha < 100:
            grund = ha * 10_000
    zimmer = _erste(RX_ZIMMER, text)
    bj = RX_BAUJAHR.search(text)
    bahn, bahn_text = bahn_aus_text(text)
    makler = ist_privat(text)
    beschreibung = re.sub(r"\s+", " ", text)[:600]

    from . import ilb  # spät importieren, damit parse ohne Daten testbar bleibt
    land = land_aus_plz(plz)
    return {
        "id": lid,
        "titel": titel or "Inserat",
        "ort": ort,
        "gemeinde": ort,
        "plz": plz,
        "land": land,
        "preis": round(preis) if preis and preis > 5_000 else None,
        "makler": True if makler is None else makler,
        "wf": wf if wf and 20 <= wf <= 2000 else None,
        "grund": grund if grund and grund >= 100 else None,
        "zimmer": zimmer,
        "baujahr": bj.group(1) if bj else "",
        "zustand": zustand_aus_text(text),
        "bahn": bahn,
        "bahnText": bahn_text,
        "fahrzeit": None,
        "ziel": "Berlin" if land == "BB" else ("Dresden/Leipzig" if land == "SN" else ""),
        "ruhe": ruhe_aus_text(text),
        "neben": nebengelass_aus_text(text),
        "ilbOrt": ilb.status(ort) if land == "BB" else "nein",
        "geprueft": False,
        "quelle": quelle or QUELLE.get(portal, "Web"),
        "url": url,
        "info": beschreibung,
    }

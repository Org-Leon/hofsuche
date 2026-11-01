# Hofsuche

Findet Häuser und Höfe in Brandenburg und Sachsen und rankt sie nach deinen Kriterien:
mindestens 3.000 m² Grundstück und 120 m² Wohnfläche, Kaufpreis plus geschätzter
Sanierungsstau bis rund 400.000 €, Bahnanbindung, Fahrzeit, Nebengelass, ruhige Lage
und ILB-Förderung.

Alles läuft lokal auf deinem Rechner. Es braucht nur Python 3.11 oder neuer, keine
weiteren Pakete.

## Einrichten in VS Code

1. Repository klonen: `Strg+Umschalt+P` → **Git: Clone** → dieses Repository.
2. Python-Erweiterung installieren (VS Code schlägt sie beim Öffnen vor).
3. Im Terminal (`Strg+ö`):
   ```bash
   cp config.example.toml config.toml
   cp .env.example .env
   python -m hofsuche start
   ```
   `start` lädt die 34 Inserate aus der ersten Suche vom 01.11.2026.
4. **Dashboard starten**: Links auf „Ausführen und Debuggen“ → **Dashboard starten** → F5.
   Dann im Browser <http://localhost:8765> öffnen.

## Neue Inserate holen

Im Dashboard oben auf **Suchlauf starten** klicken, oder in VS Code die Startkonfiguration
**Suchlauf** wählen, oder im Terminal `python -m hofsuche suche`.

Es gibt zwei Quellen. Beide schaltest du in `config.toml` ein oder aus.

### 1. E-Mail-Suchaufträge (empfohlen)

Lege auf ImmoScout24, Immowelt, Kleinanzeigen und ohne-makler.net je einen Suchauftrag
mit E-Mail-Benachrichtigung an (Haus kaufen, Region, Grundstück ab 3.000 m²,
Wohnfläche ab 120 m², Preis bis 400.000 €). Das Programm liest diese Mails per IMAP,
findet die Exposé-Links und übernimmt, was in der Mail steht.

- In `config.toml` unter `[mail]`: `aktiv = true`, Server und Benutzer eintragen.
- In `.env`: `HOFSUCHE_IMAP_PASSWORT=...`
- Gmail: IMAP in den Gmail-Einstellungen aktivieren, dann im Google-Konto ein
  **App-Passwort** anlegen. Das normale Passwort funktioniert nicht.
- Das Postfach wird nur gelesen, nichts wird verschoben oder gelöscht.

### 2. Suchseiten direkt abrufen

Unter `[web]` trägst du die Adressen deiner Suchen auf den Portalen ein (im Browser
suchen, Filter setzen, Adresse kopieren) und setzt `aktiv = true`. Neue Treffer werden
dann auch im Detail geöffnet, damit Grundstück, Baujahr und Zustand drinstehen.

Bitte beachten:
- Die Portale verbieten automatisierte Abrufe in ihren Nutzungsbedingungen. Nutze das
  nur privat und selten (z. B. einmal am Tag).
- Zwischen zwei Abrufen liegen mindestens 8 Sekunden. Zeigt ein Portal eine Sperre oder
  ein Captcha, hört das Programm für dieses Portal sofort auf und versucht nichts weiter.
- ImmoScout24 blockt solche Abrufe praktisch immer. Für ImmoScout nimm die Mails.
- Wenn ein Portal sein Seitenlayout ändert, kann das Auslesen schlechter werden. Die
  Links werden trotzdem gefunden.

## Was das Dashboard kann

- Rangliste mit Punkten pro Kriterium (farbiger Balken), Regler für die Gewichte.
- Status pro Inserat (Gemerkt, Besichtigung, Kein Interesse) und eine Notiz.
- **Angaben korrigieren**: Grundstück, Bahn, Fahrzeit, Zustand usw. selbst eintragen.
  Deine Korrekturen gewinnen immer gegen spätere Suchläufe.
- Filter: Brandenburg, Sachsen, nur ILB-Orte, Gemerkt, neu seit letztem Besuch.
- Inserate, die ein Muss-Kriterium verfehlen, stehen unten unter „Fällt raus“.

## Wie gerechnet wird

| Teil | Woher |
|---|---|
| Sanierungsstau | € pro m² Wohnfläche nach Zustand, einstellbar in `config.toml` → `[sanierung]` |
| Nebenkosten | Grunderwerbsteuer (BB 6,5 %, SN 5,5 %), 2 % Notar/Grundbuch, 3,57 % Makler |
| ILB-Förderung | Richtlinie WohneigentumförderR vom 13.02.2026; Ortsliste `data/ilb_orte.txt` |
| Bahn, Ruhe, Nebengelass | aus dem Inseratstext erraten, bitte im Dashboard prüfen |
| Fahrzeit | bei neuen Inseraten leer, bitte selbst eintragen |

Die ILB-Ortsliste stammt von der LBV-Karte „Gebietskulissen der Städtebau- und
Wohnraumförderung“ mit Stichtag 30.06.2026. Ob ein Ortsteil zählt, bestätigt die
Gemeinde mit der städtebaulichen Stellungnahme.

## Aufbau

```
hofsuche/
  cli.py        Befehle: start, suche, liste, dashboard
  config.py     config.toml und .env laden
  scoring.py    Bewertung (eine Stelle für alle Regeln)
  ilb.py        ILB-Ortsliste und Förderregeln
  parse.py      Exposé-Links finden, Angaben aus Text lesen
  store.py      SQLite-Datenbank data/hofsuche.db
  update.py     ein Suchlauf
  server.py     lokaler Webserver für das Dashboard
  sources/
    mail.py     IMAP-Suchaufträge
    web.py      Suchseiten und Exposés
    http.py     Abruf mit Pause und Sperr-Erkennung
web/index.html  Dashboard
data/           Startliste, ILB-Orte, deine Datenbank (nicht im Repo)
tests/          python -m unittest
```

Tests laufen mit `python -m unittest -v` oder über das Test-Symbol in VS Code.

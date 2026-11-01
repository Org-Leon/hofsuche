import json
import tempfile
import unittest
from pathlib import Path

from hofsuche import config, ilb, parse, scoring, store

CFG = config.load(Path("/nicht/vorhanden.toml"))


class TestParse(unittest.TestCase):
    def test_exposes_in_tracking_links(self):
        mail = (
            '<a href="https://click.example.de/r?u=https%3A%2F%2Fwww.immobilienscout24.de%2Fexpose%2F171316080%3Fref%3Dmail">X</a>'
            '<a href="https://www.kleinanzeigen.de/s-anzeige/hof-mit-scheune/3478186960-208-26604?utm=1">Y</a>'
            '<a href="https://www.immowelt.de/expose/9d61d99a-35e9-423d-9e0e-282f0fa9f6be">Z</a>'
        )
        ids = dict(parse.finde_exposes(mail))
        self.assertIn("immoscout-171316080", ids)
        self.assertIn("kleinanzeigen-3478186960", ids)
        self.assertIn("immowelt-9d61d99a-35e9-423d-9e0e-282f0fa9f6be", ids)
        self.assertEqual(ids["immoscout-171316080"], "https://www.immobilienscout24.de/expose/171316080")

    def test_angaben_aus_text(self):
        text = """Vierseitenhof mit Scheune und Stallungen
        14913 Niederer Fläming
        Kaufpreis: 249.999 €
        Wohnfläche ca. 183 m²
        Grundstücksfläche: 8.000 m²
        Baujahr 1936
        Renovierungsbedürftig. Ruhige Sackgassenlage am Waldrand. Provisionsfrei.
        Bahnhof Jüterbog ca. 15 km entfernt."""
        r = parse.aus_text("https://www.kleinanzeigen.de/s-anzeige/x/3478186960-208-26604", text)
        self.assertEqual(r["preis"], 249999)
        self.assertEqual(r["wf"], 183)
        self.assertEqual(r["grund"], 8000)
        self.assertEqual(r["baujahr"], "1936")
        self.assertEqual(r["zustand"], "renov")
        self.assertEqual(r["land"], "BB")
        self.assertEqual(r["ruhe"], 3.0)
        self.assertEqual(r["neben"], 2.0)
        self.assertFalse(r["makler"])
        self.assertEqual(r["bahn"], 1.0)
        self.assertEqual(r["ilbOrt"], "ja")

    def test_hektar(self):
        r = parse.aus_text("https://example.org/x", "Hof auf 1,7 ha Land, Preis 245.000 €")
        self.assertEqual(r["grund"], 17000)

    def test_land_aus_plz(self):
        self.assertEqual(parse.land_aus_plz("01844"), "SN")
        self.assertEqual(parse.land_aus_plz("04758"), "SN")
        self.assertEqual(parse.land_aus_plz("04916"), "BB")
        self.assertEqual(parse.land_aus_plz("16866"), "BB")
        self.assertIsNone(parse.land_aus_plz("80331"))


class TestMail(unittest.TestCase):
    def test_suchauftrag_mail(self):
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from hofsuche.sources import mail

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "2 neue Angebote für Ihre Suche"
        msg["From"] = "noreply@immobilienscout24.de"
        msg.attach(MIMEText(
            "Bauernhaus mit Scheune\n16866 Kyritz\nKaufpreis 279.000 €\nWohnfläche 140 m²\n"
            "Grundstück 4.000 m²\nhttps://www.immobilienscout24.de/expose/111222333\n", "plain", "utf-8"))
        msg.attach(MIMEText('<a href="https://www.immobilienscout24.de/expose/111222333">Ansehen</a>', "html", "utf-8"))
        treffer = mail.treffer_aus_mail(msg.as_bytes())
        self.assertEqual(len(treffer), 1)
        t = treffer[0]
        self.assertEqual(t["id"], "immoscout-111222333")
        self.assertEqual(t["preis"], 279000)
        self.assertEqual(t["grund"], 4000)
        self.assertEqual(t["ilbOrt"], "ja")


class TestIlb(unittest.TestCase):
    def test_orte(self):
        self.assertEqual(ilb.status("Wiesenburg"), "ja")
        self.assertEqual(ilb.status("Wiesenburg/Mark"), "ja")
        self.assertEqual(ilb.status("Lindow"), "ja")
        self.assertEqual(ilb.status("Casekow"), "nein")
        self.assertEqual(ilb.status("Bad Saarow"), "nein")   # „Bad …“ darf nicht über Bad Belzig passen
        self.assertEqual(ilb.status(None), "prüfen")


class TestScoring(unittest.TestCase):
    def test_ilb_und_muss(self):
        r = {"land": "BB", "ilbOrt": "ja", "preis": 145000, "wf": 120, "grund": 3406,
             "zustand": "renov", "bahn": 1, "fahrzeit": 120, "ruhe": 2, "neben": 2, "makler": True}
        b = scoring.bewerte(r, CFG)
        self.assertEqual(b["komponenten"]["ilb"], 1.0)
        self.assertEqual(b["sanierung"], 120 * 700)
        self.assertEqual(b["muss"], [])
        r["grund"] = 2993
        self.assertTrue(scoring.bewerte(r, CFG)["muss"])

    def test_zu_wenig_sanierung(self):
        r = {"land": "BB", "ilbOrt": "ja", "preis": 300000, "wf": 150, "zustand": "saniert"}
        self.assertEqual(scoring.bewerte(r, CFG)["ilb_text"], "ILB: zu wenig Sanierung")

    def test_punkte_bereich(self):
        k = {x: 1.0 for x in scoring.KRITERIEN}
        self.assertAlmostEqual(scoring.punkte(k, CFG["gewichte"]), 100.0)


class TestStore(unittest.TestCase):
    def test_korrektur_gewinnt(self):
        with tempfile.TemporaryDirectory() as d:
            con = store.connect(Path(d) / "t.db")
            self.assertTrue(store.upsert(con, {"id": "a", "grund": None, "preis": 100}))
            store.aendern(con, "a", {"korrektur": {"grund": 5000}, "status": "merken"})
            self.assertFalse(store.upsert(con, {"id": "a", "grund": 1200, "preis": 90}))
            row = store.alle(con)[0]
            self.assertEqual(row["grund"], 5000)     # Korrektur bleibt
            self.assertEqual(row["preis"], 90)       # neuer Preis aus dem Inserat
            self.assertEqual(row["status"], "merken")
            with self.assertRaises(ValueError):
                store.aendern(con, "a", {"korrektur": {"url": "x"}})

    def test_startliste_gueltig(self):
        liste = json.loads((config.DATA / "startliste.json").read_text(encoding="utf-8"))
        self.assertEqual(len(liste), 34)
        for r in liste:
            scoring.bewerte(r, CFG)


if __name__ == "__main__":
    unittest.main()

"""Bilan dans le navigateur : copie du lecteur + CSV converti en script (ADR 003)."""

import json

import pytest

from pointeuse import settings
from pointeuse.bilan import DOSSIER_LECTEUR, CsvAbsent, preparer_bilan, script_donnees

PREFIXE = "window.POINTEUSE_CSV = "


def relire_donnees(script: str) -> dict:
    ligne = next(l for l in script.splitlines() if l.startswith(PREFIXE))
    return json.loads(ligne[len(PREFIXE):].rstrip(";"))


def test_marqueur_present_une_fois_dans_le_lecteur():
    page = (DOSSIER_LECTEUR / "index.html").read_text(encoding="utf-8")
    assert page.count(settings.MARQUEUR_DONNEES_BILAN) == 1


def test_version_identique_cote_js():
    js = (DOSSIER_LECTEUR / "pointeuse.js").read_text(encoding="utf-8")
    assert f"const DONNEES_LOCALES_VERSION = {settings.VERSION_DONNEES_BILAN};" in js


def test_script_donnees_echappe_tout():
    texte = 'a;"b";</script>\n é\\'
    script = script_donnees("pointeuse.csv", texte)
    assert " " not in script   # fichier .js séparé : « </script> » y est sans effet
    assert relire_donnees(script) == {"version": settings.VERSION_DONNEES_BILAN,
                                      "nom": "pointeuse.csv", "texte": texte, "suivi": None}
    script = script_donnees("pointeuse.csv", "", (settings.NOM_FICHIER_SUIVI, texte))
    assert relire_donnees(script)["suivi"] == {"nom": settings.NOM_FICHIER_SUIVI, "texte": texte}


def test_preparer_bilan(tmp_path):
    csv = tmp_path / "pointeuse.csv"
    contenu = "date_in;date_out;client;projet;tache;description;duree_min\n" \
              "2026-11-17 08:00;2026-11-17 09:00;exemple-client;p;t;;60\n"
    csv.write_text("﻿" + contenu, encoding="utf-8")

    page = preparer_bilan(csv, tmp_path)

    dossier = tmp_path / settings.NOM_DOSSIER_BILAN
    assert page == dossier / "index.html"
    html = page.read_text(encoding="utf-8")
    assert settings.MARQUEUR_DONNEES_BILAN not in html
    # Ordre : données, puis suivi.js, puis pointeuse.js.
    assert (html.index(f'<script src="{settings.NOM_FICHIER_DONNEES_BILAN}?v=') < html.index('<script src="suivi.js?v=')
            < html.index('<script src="pointeuse.js?v='))
    assert 'href="pointeuse.css?v=' in html
    for nom in ("pointeuse.css", "fusion.js", "suivi.js", "pointeuse.js", "logo.png"):
        assert (dossier / nom).exists()
    donnees = relire_donnees((dossier / settings.NOM_FICHIER_DONNEES_BILAN).read_text(encoding="utf-8"))
    assert donnees["texte"] == contenu   # BOM retiré
    assert donnees["suivi"] is None       # pas de chemin de suivi donné

    # Deuxième ouverture : tout est réécrit avec le CSV à jour.
    csv.write_text(contenu + "2026-11-17 09:00;2026-11-17 10:00;client-b;p;t;;60\n", encoding="utf-8")
    preparer_bilan(csv, tmp_path)
    # Jeton « ?v= » différent : le navigateur ne ressert pas d'anciennes données de son cache.
    assert page.read_text(encoding="utf-8") != html
    donnees = relire_donnees((dossier / settings.NOM_FICHIER_DONNEES_BILAN).read_text(encoding="utf-8"))
    assert "client-b" in donnees["texte"]


def test_csv_absent(tmp_path):
    with pytest.raises(CsvAbsent):
        preparer_bilan(tmp_path / "pointeuse.csv", tmp_path)
    assert not (tmp_path / settings.NOM_DOSSIER_BILAN).exists()


def test_preparer_bilan_avec_suivi(tmp_path):
    csv = tmp_path / "pointeuse.csv"
    csv.write_text("date_in;date_out;client;projet;tache;description;duree_min\n", encoding="utf-8")
    suivi = tmp_path / settings.NOM_FICHIER_SUIVI

    # Pas encore de note : suivi = null.
    preparer_bilan(csv, tmp_path, suivi)
    script = (tmp_path / settings.NOM_DOSSIER_BILAN / settings.NOM_FICHIER_DONNEES_BILAN).read_text(encoding="utf-8")
    assert relire_donnees(script)["suivi"] is None

    # Contenu brut transmis (les règles de lecture sont appliquées par la page) ; octet illisible → U+FFFD.
    suivi.write_bytes('{"v": 1, "texte": "Câblage"}\n'.encode("utf-8") + b"\xff\n")
    preparer_bilan(csv, tmp_path, suivi)
    script = (tmp_path / settings.NOM_DOSSIER_BILAN / settings.NOM_FICHIER_DONNEES_BILAN).read_text(encoding="utf-8")
    assert relire_donnees(script)["suivi"] == {"nom": settings.NOM_FICHIER_SUIVI,
                                               "texte": '{"v": 1, "texte": "Câblage"}\n\ufffd\n'}

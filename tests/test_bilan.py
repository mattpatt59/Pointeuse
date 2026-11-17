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
                                      "nom": "pointeuse.csv", "texte": texte}


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
    balise = f'<script src="{settings.NOM_FICHIER_DONNEES_BILAN}"></script>'
    assert html.index(balise) < html.index('<script src="pointeuse.js">')   # données d'abord
    for nom in ("pointeuse.css", "pointeuse.js", "logo.png"):
        assert (dossier / nom).exists()
    donnees = relire_donnees((dossier / settings.NOM_FICHIER_DONNEES_BILAN).read_text(encoding="utf-8"))
    assert donnees["texte"] == contenu   # BOM retiré

    # Deuxième ouverture : tout est réécrit avec le CSV à jour.
    csv.write_text(contenu + "2026-11-17 09:00;2026-11-17 10:00;client-b;p;t;;60\n", encoding="utf-8")
    preparer_bilan(csv, tmp_path)
    donnees = relire_donnees((dossier / settings.NOM_FICHIER_DONNEES_BILAN).read_text(encoding="utf-8"))
    assert "client-b" in donnees["texte"]


def test_csv_absent(tmp_path):
    with pytest.raises(CsvAbsent):
        preparer_bilan(tmp_path / "pointeuse.csv", tmp_path)
    assert not (tmp_path / settings.NOM_DOSSIER_BILAN).exists()

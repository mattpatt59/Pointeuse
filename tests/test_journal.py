"""Tests du fichier pointeuse.csv (CDC étape 2)."""

from datetime import date, datetime

import pytest

from pointeuse.journal import Journal, JournalBloque, Ligne

EN_TETE = "date_in;date_out;client;projet;tache;description;duree_min"


def h(texte: str) -> datetime:
    return datetime.strptime(texte, "%Y-%m-%d %H:%M")


LIGNE_A = Ligne(h("2026-11-17 10:12"), h("2026-11-17 10:30"), "Alpha Industrie", "Armoire ligne 2", "câblage", "bornier X1")
LIGNE_B = Ligne(h("2026-11-17 10:30"), h("2026-11-17 10:45"), "PAUSE")


@pytest.fixture
def journal(tmp_path):
    return Journal(tmp_path / "pointeuse.csv")


def test_creation_avec_en_tete_et_bom(journal):
    journal.ajouter([LIGNE_A])
    brut = journal.chemin.read_bytes()
    assert brut.startswith(b"\xef\xbb\xbf")
    texte = brut.decode("utf-8-sig").splitlines()
    assert texte == [EN_TETE, "2026-11-17 10:12;2026-11-17 10:30;Alpha Industrie;Armoire ligne 2;câblage;bornier X1;18"]


def test_ajout_ne_duplique_ni_bom_ni_en_tete(journal):
    journal.ajouter([LIGNE_A])
    journal.ajouter([LIGNE_B])
    brut = journal.chemin.read_bytes()
    assert brut.count(b"\xef\xbb\xbf") == 1
    assert brut.decode("utf-8-sig").count("date_in") == 1
    assert journal.lire() == [LIGNE_A, LIGNE_B]


def test_pause_et_colonnes_vides(journal):
    journal.ajouter([LIGNE_B])
    assert journal.chemin.read_text(encoding="utf-8-sig").splitlines()[1] == "2026-11-17 10:30;2026-11-17 10:45;PAUSE;;;;15"
    assert journal.lire()[0].est_pause


def test_point_virgule_dans_la_description(journal):
    ligne = Ligne(LIGNE_A.debut, LIGNE_A.fin, "a", "p", "", 'appel ; "urgent"')
    journal.ajouter([ligne])
    assert journal.lire() == [ligne]


def test_fichier_absent(journal):
    assert journal.lire() == []


def test_fichier_vide_recoit_l_en_tete(journal):
    journal.chemin.write_bytes(b"")
    journal.ajouter([LIGNE_A])
    assert journal.chemin.read_text(encoding="utf-8-sig").splitlines()[0] == EN_TETE


def test_ligne_abimee_ignoree_et_comptee(journal):
    journal.ajouter([LIGNE_A])
    with open(journal.chemin, "a", encoding="utf-8") as f:
        f.write("pas une date;x;y\n\n2026-13-45 10:00;2026-11-17 11:00;a;p;;;60\n")
    journal.ajouter([LIGNE_B])
    assert journal.lire() == [LIGNE_A, LIGNE_B]
    assert journal.lignes_ignorees == 2


def test_duree_recalculee_pas_relue(journal):
    journal.chemin.write_text(EN_TETE + "\n2026-11-17 08:00;2026-11-17 09:30;a;p;;;999\n", encoding="utf-8-sig")
    assert journal.lire()[0].duree_min == 90


def test_lignes_du_jour_avec_passage_de_minuit(journal):
    veille = Ligne(h("2026-11-16 09:00"), h("2026-11-16 10:00"), "a", "p")
    minuit = Ligne(h("2026-11-16 23:30"), h("2026-11-17 00:30"), "a", "p")
    lendemain = Ligne(h("2026-11-18 09:00"), h("2026-11-18 10:00"), "a", "p")
    journal.ajouter([veille, minuit, LIGNE_A, lendemain])
    assert journal.lignes_du_jour(date(2026, 11, 17)) == [minuit, LIGNE_A]
    assert journal.lignes_du_jour(date(2026, 11, 16)) == [veille, minuit]


def test_ecriture_impossible(tmp_path):
    dossier = tmp_path / "pointeuse.csv"
    dossier.mkdir()   # un dossier à la place du fichier : open() échoue comme un fichier verrouillé
    with pytest.raises(JournalBloque):
        Journal(dossier).ajouter([LIGNE_A])


def test_liste_vide_ne_cree_rien(journal):
    journal.ajouter([])
    assert not journal.chemin.exists()

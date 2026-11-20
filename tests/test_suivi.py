"""Journal de suivi des projets pointeuse_suivi.jsonl (CDC suivi_projets.md, ADR 004)."""

import json
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest

from pointeuse import settings
from pointeuse.journal import Ligne
from pointeuse.suivi import (JournalSuivi, NoteSuivi, dernier_pointage, est_masque, est_periode_semaine,
                             etats_actuels, extrait, historique, jours_de_periode, libelle_statut, lire_contenu,
                             ligne_json, minutes_par_jour, note_de_periode, note_precedente, notes_retenues,
                             nouvelle_note, periode_de, projets_suivis, statut_affiche)

EXEMPLE = Path(__file__).parent / "donnees" / "suivi_exemple.jsonl"   # jeu commun Python / JS


def a(texte: str) -> datetime:
    return datetime.strptime(texte, "%Y-%m-%d %H:%M")


def note(horodatage: str, periode: str = "2026-11-14", statut: str = "en_cours", texte: str = "",
         projet: str = "Armoire ligne 2", poste: str = "", priorite: int = 0) -> NoteSuivi:
    return NoteSuivi(a(horodatage), periode, "Alpha Industrie", projet, statut, priorite, texte, poste)


@pytest.fixture
def journal(tmp_path):
    return JournalSuivi(tmp_path / settings.NOM_FICHIER_SUIVI)


# ─── Périodes ────────────────────────────────────────────────────────────────

def test_periode_jour_et_semaine_iso():
    assert periode_de(date(2026, 11, 14), settings.PERIODE_JOUR) == "2026-11-14"
    assert periode_de(date(2026, 11, 14), settings.PERIODE_SEMAINE) == "2026-W46"
    # Semaine ISO à cheval sur deux années : le 1er janvier 2027 (vendredi) est en 2026-W53.
    assert periode_de(date(2027, 1, 1), settings.PERIODE_SEMAINE) == "2026-W53"


def test_periode_inconnue_refusee():
    with pytest.raises(ValueError):
        periode_de(date(2026, 11, 14), "mois")


def test_jours_de_periode():
    assert jours_de_periode("2026-11-14") == (date(2026, 11, 14), date(2026, 11, 14))
    assert jours_de_periode("2026-W46") == (date(2026, 11, 9), date(2026, 11, 15))
    assert est_periode_semaine("2026-W46")
    assert not est_periode_semaine("2026-11-14")
    for mauvaise in ("2026-1-5", "2026-13-01", "2026-W60", "hier"):
        with pytest.raises(ValueError):
            jours_de_periode(mauvaise)


# ─── Écriture / relecture ────────────────────────────────────────────────────

def test_ajout_puis_relecture_texte_multiligne(journal):
    texte = 'Ligne 1 ; "guillemets"\nLigne 2 — accents éàù\n\nLigne 4'
    journal.ajouter(note("2026-11-14 18:02", texte=texte))
    notes, avertissements = journal.lire()
    assert avertissements == []
    assert len(notes) == 1
    assert notes[0].texte == texte
    # Une note = une ligne de fichier, quel que soit le texte ; UTF-8 sans BOM, accents lisibles.
    brut = journal.chemin.read_bytes()
    assert brut.count(b"\n") == 1
    assert not brut.startswith(b"\xef\xbb\xbf")
    assert "éàù" in brut.decode("utf-8")


def test_ligne_json_ordre_des_champs_et_retours_windows():
    ligne = ligne_json(note("2026-11-14 18:02", texte="a\r\nb\rc"))
    objet = json.loads(ligne)
    assert list(objet) == ["v", "horodatage", "periode", "client", "projet", "statut", "priorite", "texte"]
    assert objet["v"] == 1
    assert objet["horodatage"] == "2026-11-14 18:02:00"
    assert objet["texte"] == "a\nb\nc"


def test_ajout_seul_ne_reecrit_pas(journal):
    journal.ajouter(note("2026-11-14 09:00", texte="9 h"))
    avant = journal.chemin.read_bytes()
    journal.ajouter(note("2026-11-14 16:00", texte="16 h"))
    assert journal.chemin.read_bytes().startswith(avant)


def test_ajout_apres_edition_sans_retour_final(journal):
    journal.ajouter(note("2026-11-14 09:00", texte="9 h"))
    journal.chemin.write_bytes(journal.chemin.read_bytes().rstrip(b"\n"))   # édité à la main
    journal.ajouter(note("2026-11-14 16:00", texte="16 h"))
    notes, avertissements = journal.lire()
    assert avertissements == []
    assert [n.texte for n in notes] == ["9 h", "16 h"]


@pytest.mark.parametrize("modification", [
    {"statut": "termine_a_confirmer"},   # statut calculé : jamais écrit
    {"statut": "fini"},
    {"priorite": 100},
    {"priorite": -100},
    {"projet": " "},
    {"client": ""},
    {"periode": "2026-1-5"},
])
def test_note_invalide_non_ecrite(journal, modification):
    with pytest.raises(ValueError):
        journal.ajouter(replace(note("2026-11-14 09:00"), **modification))
    assert not journal.chemin.exists()


def test_fichier_absent(journal):
    assert journal.lire() == ([], [])


def test_echec_ecriture_leve_oserror(tmp_path):
    dossier = tmp_path / "pas_un_fichier"
    dossier.mkdir()
    with pytest.raises(OSError):
        JournalSuivi(dossier).ajouter(note("2026-11-14 09:00"))


def test_nouvelle_note_periode_et_jour_passe():
    moment = datetime(2026, 11, 20, 17, 30, 12, 345678)
    n = nouvelle_note(moment, settings.PERIODE_JOUR, "Alpha Industrie", "Armoire ligne 2", "en_cours", 0, "x")
    assert n.periode == "2026-11-20"
    assert n.horodatage == datetime(2026, 11, 20, 17, 30, 12)
    passe = nouvelle_note(moment, settings.PERIODE_JOUR, "Alpha Industrie", "Armoire ligne 2", "en_cours", 0, "x",
                          jour=date(2026, 11, 18))
    assert passe.periode == "2026-11-18"
    assert passe.horodatage == datetime(2026, 11, 20, 17, 30, 12)   # moment réel de l'écriture
    semaine = nouvelle_note(moment, settings.PERIODE_SEMAINE, "Alpha Industrie", "Armoire ligne 2", "en_cours", 0, "x")
    assert semaine.periode == "2026-W47"


# ─── Lecture du jeu d'exemple commun ─────────────────────────────────────────

def test_lecture_exemple():
    notes, avertissements = lire_contenu(EXEMPLE.read_bytes(), poste="bureau")
    assert [n.texte for n in notes] == [
        "",                                                     # 12/11, ligne en \r\n
        "Livré.",                                               # 13/11
        "Version de 9 h",
        "Câblage OK.\nDéfaut sur la sortie 3, à reprendre.",
        'Attente retour client sur le schéma ; "urgent".',
    ]
    assert all(n.poste == "bureau" for n in notes)
    assert avertissements == [
        "ligne 4 : JSON invalide, ignorée",
        "ligne 5 : version de format inconnue : 2, ignorée",
        "ligne 6 : statut inconnu : 'fini', ignorée",
        "ligne 8 : priorité 150 ramenée à 99",
    ]
    livre = next(n for n in notes if n.projet == "Firmware passerelle")
    assert livre.priorite == 99
    assert livre.periode == "2026-W46"


def test_bom_tolere_et_encodage_illisible_isole():
    bonne = ligne_json(note("2026-11-14 09:00", texte="ok")).encode("utf-8")
    contenu = b"\xef\xbb\xbf" + bonne + b"\n" + b'{"texte": "\xe9"}\n' + bonne + b"\n"
    notes, avertissements = lire_contenu(contenu)
    assert len(notes) == 2
    assert avertissements == ["ligne 2 : encodage illisible (UTF-8 attendu), ignorée"]


def test_ligne_qui_n_est_pas_un_objet():
    _, avertissements = lire_contenu(b"[1, 2]\n")
    assert avertissements == ["ligne 1 : ce n'est pas un objet JSON, ignorée"]


@pytest.mark.parametrize("modification, raison", [
    ({"horodatage": None}, "champ « horodatage » manquant ou non textuel"),
    ({"texte": 3}, "champ « texte » manquant ou non textuel"),
    ({"priorite": "0"}, "champ « priorite » manquant ou non entier"),
    ({"priorite": True}, "champ « priorite » manquant ou non entier"),
    ({"horodatage": "2026-11-14 09:00"}, "horodatage illisible : '2026-11-14 09:00'"),
    ({"projet": ""}, "client ou projet vide"),
    ({"periode": "2026-W60"}, "période mal formée : '2026-W60'"),
    ({"periode": "2026-1-5"}, "période mal formée : '2026-1-5'"),
])
def test_lignes_refusees(modification, raison):
    objet = json.loads(ligne_json(note("2026-11-14 09:00")))
    objet.update(modification)
    _, avertissements = lire_contenu(json.dumps(objet).encode("utf-8"))
    assert len(avertissements) == 1
    assert avertissements[0].startswith("ligne 1 : ")
    assert raison in avertissements[0]
    assert avertissements[0].endswith(", ignorée")


# ─── Règles de lecture ───────────────────────────────────────────────────────

def test_derniere_version_de_la_periode():
    notes = [note("2026-11-14 16:00", texte="16 h"), note("2026-11-14 09:00", texte="9 h"),
             note("2026-11-14 12:00", texte="12 h"), note("2026-11-15 10:00", "2026-11-15", texte="15/11")]
    assert [n.texte for n in notes_retenues(notes)] == ["16 h", "15/11"]


def test_semaine_lundi_puis_vendredi():
    notes = [note("2026-11-09 10:00", "2026-W46", texte="lundi"),
             note("2026-11-13 17:00", "2026-W46", texte="vendredi")]
    retenues = notes_retenues(notes)
    assert [(n.texte, n.horodatage) for n in retenues] == [("vendredi", a("2026-11-13 17:00"))]


def test_note_jour_et_note_semaine_coexistent():
    notes = [note("2026-11-12 10:00", "2026-11-12", texte="jour"),
             note("2026-11-13 17:00", "2026-W46", texte="semaine")]
    assert [n.texte for n in notes_retenues(notes)] == ["jour", "semaine"]


def test_deux_postes_meme_periode_les_deux_gardees():
    notes = [note("2026-11-14 10:00", texte="bureau", poste="bureau"),
             note("2026-11-14 11:00", texte="client-a", poste="client-a"),
             note("2026-11-14 12:00", texte="bureau v2", poste="bureau")]
    assert [(n.poste, n.texte) for n in notes_retenues(notes)] == [("client-a", "client-a"), ("bureau", "bureau v2")]


def test_etat_actuel_note_la_plus_recente_tous_postes():
    notes = [note("2026-11-15 10:00", "2026-11-15", statut="bloque", priorite=-10, poste="client-a"),
             note("2026-11-14 18:00", statut="en_cours", poste="bureau"),
             note("2026-11-14 09:00", statut="a_faire", projet="Autre")]
    etats = etats_actuels(notes)
    assert etats[("Alpha Industrie", "Armoire ligne 2")].statut == "bloque"
    assert etats[("Alpha Industrie", "Armoire ligne 2")].priorite == -10
    assert etats[("Alpha Industrie", "Autre")].statut == "a_faire"


def test_termine_a_confirmer_calcule():
    termine = note("2026-11-14 18:00", statut="termine")
    assert statut_affiche(termine, None) == "termine"
    assert statut_affiche(termine, a("2026-11-14 17:00")) == "termine"
    assert statut_affiche(termine, a("2026-11-17 10:00")) == settings.STATUT_TERMINE_A_CONFIRMER
    assert statut_affiche(note("2026-11-14 18:00", statut="bloque"), a("2026-11-17 10:00")) == "bloque"
    assert statut_affiche(None, a("2026-11-17 10:00")) is None


def test_masquage_et_libelles():
    assert est_masque("termine")
    assert not est_masque(settings.STATUT_TERMINE_A_CONFIRMER)
    assert not est_masque("en_cours")
    assert not est_masque(None)
    assert libelle_statut(settings.STATUT_TERMINE_A_CONFIRMER) == "terminé ?"
    assert libelle_statut("attente_client") == "en attente client"
    assert libelle_statut(None) == ""


# ─── Fenêtre Suivi : note de la période, message précédent ───────────────────

def test_note_de_periode_et_precedente():
    notes = [note("2026-11-12 18:00", "2026-11-12", texte="12/11"),
             note("2026-11-13 09:00", "2026-11-13", texte="13/11 9 h"),
             note("2026-11-13 17:00", "2026-11-13", texte="13/11 17 h"),
             note("2026-11-14 10:00", texte="14/11"),
             note("2026-11-13 12:00", "2026-11-13", texte="autre projet", projet="Autre")]
    assert note_de_periode(notes, "Alpha Industrie", "Armoire ligne 2", "2026-11-13").texte == "13/11 17 h"
    assert note_de_periode(notes, "Alpha Industrie", "Armoire ligne 2", "2026-11-15") is None
    assert note_precedente(notes, "Alpha Industrie", "Armoire ligne 2", "2026-11-14").texte == "13/11 17 h"
    assert note_precedente(notes, "Alpha Industrie", "Armoire ligne 2", "2026-11-12") is None
    # Une note de semaine écrite après coup : la précédente de la semaine 47 est la dernière de la 46.
    assert note_precedente(notes, "Alpha Industrie", "Armoire ligne 2", "2026-W47").texte == "14/11"
    # Autre poste : pas pris pour « Message du … » de ce poste.
    assert note_precedente(notes, "Alpha Industrie", "Armoire ligne 2", "2026-11-14", poste="bureau") is None


# ─── Temps pointé ────────────────────────────────────────────────────────────

def ligne(debut: str, fin: str, projet: str = "Armoire ligne 2") -> Ligne:
    return Ligne(a(debut), a(fin), "Alpha Industrie", projet, "cdc", "")


def test_minutes_par_jour_coupe_a_minuit():
    lignes = [ligne("2026-11-13 09:00", "2026-11-13 10:30"), ligne("2026-11-13 14:00", "2026-11-13 14:15"),
              ligne("2026-11-13 23:00", "2026-11-14 01:00"), ligne("2026-11-13 08:00", "2026-11-13 18:00", "Autre")]
    assert minutes_par_jour(lignes, "Alpha Industrie", "Armoire ligne 2") == {
        date(2026, 11, 13): 90 + 15 + 60, date(2026, 11, 14): 60}
    assert dernier_pointage(lignes, "Alpha Industrie", "Armoire ligne 2") == a("2026-11-14 01:00")
    assert dernier_pointage(lignes, "Alpha Industrie", "Inconnu") is None


# ─── Liste des projets ───────────────────────────────────────────────────────

def test_projets_suivis_tri_masquage_et_projets_hors_config():
    config = [("Alpha Industrie", "Armoire ligne 2", True), ("Alpha Industrie", "Rétrofit presse", False),
              ("Bêta Automatismes", "Carte capteur v2", True), ("Bêta Automatismes", "Firmware passerelle", True)]
    notes = [note("2026-11-14 10:00", priorite=-5),
             NoteSuivi(a("2026-11-14 11:00"), "2026-11-14", "Bêta Automatismes", "Firmware passerelle",
                       "termine", 3, ""),
             NoteSuivi(a("2026-11-14 12:00"), "2026-11-14", "Bêta Automatismes", "Carte capteur v2",
                       "termine", 2, ""),
             NoteSuivi(a("2026-11-14 12:00"), "2026-11-14", "Delta", "Hors config", "a_faire", 1, "")]
    lignes = [Ligne(a("2026-11-17 09:00"), a("2026-11-17 10:00"), "Bêta Automatismes", "Carte capteur v2", "", "")]
    projets = projets_suivis(config, notes, lignes)
    assert [(p.projet, p.priorite, p.statut, p.masque) for p in projets] == [
        ("Armoire ligne 2", -5, "en_cours", False),
        ("Rétrofit presse", 0, None, True),                          # masqué dans la config
        ("Hors config", 1, "a_faire", False),                        # n'existe que dans les notes
        ("Carte capteur v2", 2, settings.STATUT_TERMINE_A_CONFIRMER, False),   # pointé après « terminé »
        ("Firmware passerelle", 3, "termine", True),
    ]


# ─── Historique ──────────────────────────────────────────────────────────────

def test_historique_jours_et_semaine_en_tete():
    notes = [note("2026-11-13 17:00", "2026-W46", texte="bilan semaine"),
             note("2026-11-12 18:00", "2026-11-12", texte="12/11"),
             note("2026-11-17 18:00", "2026-11-17", texte="autre", projet="Autre")]
    minutes = {date(2026, 11, 12): 60, date(2026, 11, 13): 30, date(2026, 11, 17): 45, date(2026, 11, 16): 0}
    entrees = historique(notes, minutes, "Alpha Industrie", "Armoire ligne 2")
    assert [(e.periode, e.minutes, [n.texte for n in e.notes]) for e in entrees] == [
        ("2026-11-17", 45, []),
        ("2026-W46", 90, ["bilan semaine"]),                         # somme des jours, avant ses jours
        ("2026-11-13", 30, []),
        ("2026-11-12", 60, ["12/11"]),
    ]
    assert entrees[1].est_semaine


def test_extrait():
    assert extrait("Ligne 1\n\n  Ligne 2  ") == "Ligne 1 / Ligne 2"
    assert extrait("abcdefghij", longueur=5) == "abcd…"
    assert extrait("") == ""

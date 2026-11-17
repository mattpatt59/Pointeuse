"""Pause automatique : détecteur (veille, verrouillage) et moteur (CDC étape 6)."""

import json
import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from pointeuse.absence import (PBT_APMRESUMEAUTOMATIC, PBT_APMSUSPEND, RAISON_VEILLE, RAISON_VERROU,  # noqa: E402
                               WM_POWERBROADCAST, WM_WTSSESSION_CHANGE, WTS_SESSION_LOCK,
                               WTS_SESSION_UNLOCK, DetecteurAbsence, traduire_message_windows)
from test_moteur import Horloge, dossier, nouveau_moteur, resume  # noqa: E402,F401


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class Temps:
    """Horloge locale + époque, avancées ensemble."""

    def __init__(self):
        self.local = datetime(2026, 11, 17, 10, 0)
        self.epoque = 1_000_000.0

    def avancer(self, minutes: float) -> None:
        self.local += timedelta(minutes=minutes)
        self.epoque += minutes * 60


@pytest.fixture
def temps():
    return Temps()


@pytest.fixture
def detecteur(qapp, temps):
    d = DetecteurAbsence(lambda: 2, lambda: temps.local, lambda: temps.epoque)
    d.evenements = []
    d.absence_commencee.connect(lambda t: d.evenements.append(("debut", t.strftime("%H:%M"))))
    d.absence_terminee.connect(lambda t: d.evenements.append(("fin", t.strftime("%H:%M"))))
    d.relever()
    return d


# ─── Détecteur ───────────────────────────────────────────────────────────────

def test_releves_reguliers_rien(detecteur, temps):
    for _ in range(10):
        temps.avancer(0.5)
        detecteur.relever()
    assert detecteur.evenements == []


def test_saut_d_horloge_veille(detecteur, temps):
    temps.avancer(0.5)
    detecteur.relever()                 # 10:00:30
    temps.avancer(45)
    detecteur.relever()                 # réveil
    assert detecteur.evenements == [("debut", "10:00"), ("fin", "10:45")]


def test_petit_retard_du_minuteur_ignore(detecteur, temps):
    temps.avancer(1.5)
    detecteur.relever()
    assert detecteur.evenements == []


def test_verrouillage_puis_deverrouillage(detecteur, temps):
    temps.avancer(5)
    detecteur.signaler(RAISON_VERROU, True)
    temps.avancer(30)
    detecteur.relever()
    detecteur.signaler(RAISON_VERROU, False)
    assert detecteur.evenements == [("debut", "10:05"), ("fin", "10:35")]


def test_veille_pendant_le_verrouillage_une_seule_absence(detecteur, temps):
    detecteur.signaler(RAISON_VERROU, True)
    detecteur.signaler(RAISON_VEILLE, True)
    temps.avancer(60)
    detecteur.relever()                     # saut ignoré : absence déjà en cours
    detecteur.signaler(RAISON_VEILLE, False)
    temps.avancer(1)
    detecteur.signaler(RAISON_VERROU, False)
    assert detecteur.evenements == [("debut", "10:00"), ("fin", "11:01")]


def test_deverrouillage_sans_verrouillage_ignore(detecteur):
    detecteur.signaler(RAISON_VERROU, False)
    assert detecteur.evenements == []


def test_suspendu_pendant_la_fenetre_d_absence(detecteur, temps):
    detecteur.suspendre(True)
    temps.avancer(20)                       # la fenêtre reste ouverte 20 min
    detecteur.relever()
    detecteur.signaler(RAISON_VERROU, True)
    detecteur.suspendre(False)
    temps.avancer(0.5)
    detecteur.relever()
    assert detecteur.evenements == []
    assert not detecteur.en_absence



def suivre_journal(detecteur) -> list:
    notes = []
    detecteur.evenement.connect(lambda nature, moment: notes.append((nature, moment.strftime("%H:%M"))))
    return notes


def test_evenements_du_poste_notes(detecteur, temps):
    notes = suivre_journal(detecteur)
    detecteur.signaler(RAISON_VERROU, True)
    temps.avancer(30)
    detecteur.relever()
    detecteur.signaler(RAISON_VERROU, False)
    detecteur.signaler(RAISON_VEILLE, True)
    detecteur.signaler(RAISON_VEILLE, False)
    assert notes == [("verrouillage", "10:00"), ("deverrouillage", "10:30"),
                     ("veille", "10:30"), ("reveil", "10:30")]


def test_evenements_notes_meme_suspendu(detecteur, temps):
    """Fenêtre d'absence ouverte : pas de nouvelle question, mais le journal suit."""
    notes = suivre_journal(detecteur)
    detecteur.suspendre(True)
    detecteur.signaler(RAISON_VERROU, True)
    assert notes == [("verrouillage", "10:00")]


def test_saut_d_horloge_note_veille_et_reveil(detecteur, temps):
    notes = suivre_journal(detecteur)
    temps.avancer(0.5)
    detecteur.relever()
    temps.avancer(45)
    detecteur.relever()
    assert notes == [("veille", "10:00"), ("reveil", "10:45")]

@pytest.mark.parametrize("message, wparam, attendu", [
    (WM_WTSSESSION_CHANGE, WTS_SESSION_LOCK, (RAISON_VERROU, True)),
    (WM_WTSSESSION_CHANGE, WTS_SESSION_UNLOCK, (RAISON_VERROU, False)),
    (WM_WTSSESSION_CHANGE, 0x5, None),      # ouverture de session : ignorée
    (WM_POWERBROADCAST, PBT_APMSUSPEND, (RAISON_VEILLE, True)),
    (WM_POWERBROADCAST, PBT_APMRESUMEAUTOMATIC, (RAISON_VEILLE, False)),
    (0x0010, 0, None),
])
def test_messages_windows(message, wparam, attendu):
    assert traduire_message_windows(message, wparam) == attendu


# ─── Moteur ──────────────────────────────────────────────────────────────────

@pytest.fixture
def horloge():
    return Horloge()


@pytest.fixture
def moteur(dossier, horloge):  # noqa: F811
    return nouveau_moteur(dossier, horloge)


def a(heure: str) -> datetime:
    h, m = heure.split(":")
    return datetime(2026, 11, 17, int(h), int(m))


def test_verrouillage_coupe_la_tache(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2", "câblage")
    moteur.absence_commencee(a("10:30"))
    horloge.regler("11:15")
    absence = moteur.absence_terminee(a("11:15"))
    assert (absence.debut, absence.fin, absence.duree_min) == (a("10:30"), a("11:15"), 45)
    assert absence.tache_precedente.projet == "Armoire ligne 2"
    assert resume(moteur) == [("08:00", "10:30", "Alpha Industrie", "Armoire ligne 2", "câblage", "")]
    assert moteur.ligne_ouverte is None
    moteur.enregistrer_absence(absence)
    assert resume(moteur)[-1][:3] == ("10:30", "11:15", "PAUSE")


def test_absence_courte_la_tache_continue(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    moteur.absence_commencee(a("10:30"))
    assert moteur.absence_terminee(a("10:31")) is None
    assert moteur.ligne_ouverte.debut == a("08:00")
    assert resume(moteur) == []


@pytest.mark.parametrize("etat", ["rien", "pause"])
def test_absence_sans_tache_rien_a_demander(moteur, horloge, etat):
    if etat == "pause":
        moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
        horloge.regler("10:00")
        moteur.pause()
    moteur.absence_commencee(a("10:30"))
    assert moteur.absence_terminee(a("12:00")) is None
    assert moteur.en_pause == (etat == "pause")


def test_plantage_pendant_le_verrouillage(dossier, horloge):  # noqa: F811
    moteur = nouveau_moteur(dossier, horloge)
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("10:30")
    moteur.absence_commencee(a("10:30"))
    horloge.regler("11:00")
    moteur.signe_de_vie()                   # sauvegardes pendant le verrouillage
    etat = json.loads(moteur.chemin_en_cours.read_text(encoding="utf-8"))
    assert etat["absence_debut"] == "2026-11-17T10:30:00"
    horloge.regler("14:00")                 # coupure de courant, redémarrage
    reprise = nouveau_moteur(dossier, horloge)
    absence = reprise.reprendre_apres_arret()
    assert resume(reprise) == [("08:00", "10:30", "Alpha Industrie", "Armoire ligne 2", "", "")]
    assert (absence.debut, absence.fin) == (a("10:30"), a("14:00"))


def test_arret_du_pc_depuis_l_ecran_verrouille(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    moteur.absence_commencee(a("17:00"))
    horloge.regler("18:30")
    moteur.arreter()
    assert resume(moteur) == [("08:00", "17:00", "Alpha Industrie", "Armoire ligne 2", "", "")]


# ─── Absence longue : pas de question (CDC « Pause automatique ») ────────────

def test_nuit_tache_close_au_verrouillage(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    moteur.absence_commencee(a("18:00"))
    lendemain = datetime(2026, 11, 18, 8, 30)
    horloge.moment = lendemain
    assert moteur.absence_terminee(lendemain) is None
    assert resume(moteur) == [("08:00", "18:00", "Alpha Industrie", "Armoire ligne 2", "", "")]
    assert moteur.ligne_ouverte is None
    assert moteur.absence_debut is None


def test_absence_de_4_h_meme_jour_sans_question(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    moteur.absence_commencee(a("10:00"))
    horloge.regler("14:00")
    assert moteur.absence_terminee(a("14:00")) is None
    assert resume(moteur) == [("08:00", "10:00", "Alpha Industrie", "Armoire ligne 2", "", "")]
    assert moteur.ligne_ouverte is None


def test_absence_de_moins_de_4_h_question(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    moteur.absence_commencee(a("10:00"))
    horloge.regler("13:59")
    assert moteur.absence_terminee(a("13:59")) is not None


def test_pause_close_au_verrouillage_le_soir(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("17:00")
    moteur.pause()
    moteur.absence_commencee(a("17:30"))
    lendemain = datetime(2026, 11, 18, 8, 30)
    horloge.moment = lendemain
    assert moteur.absence_terminee(lendemain) is None
    assert resume(moteur)[-1] == ("17:00", "17:30", "PAUSE", "", "", "")
    assert not moteur.en_pause
    assert moteur.ligne_ouverte is None


def test_plantage_puis_redemarrage_le_lendemain(dossier, horloge):  # noqa: F811
    moteur = nouveau_moteur(dossier, horloge)
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("17:55")
    moteur.signe_de_vie()
    # plantage dans la soirée, PC rallumé le lendemain
    horloge.moment = datetime(2026, 11, 18, 8, 30)
    reprise = nouveau_moteur(dossier, horloge)
    assert reprise.reprendre_apres_arret() is None
    assert resume(reprise) == [("08:00", "17:55", "Alpha Industrie", "Armoire ligne 2", "", "")]
    assert reprise.ligne_ouverte is None

"""Fenêtre « Suivi des projets » (CDC suivi_projets.md, étape 3), sans écran : plateforme Qt « offscreen »."""

import os
import shutil
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from pointeuse import settings  # noqa: E402
from pointeuse.application import Application  # noqa: E402
from pointeuse.config import Config  # noqa: E402
from pointeuse.fenetre_suivi import FenetreSuivi, libelle_periode  # noqa: E402
from pointeuse.journal import Journal, Ligne  # noqa: E402
from pointeuse.moteur import Moteur  # noqa: E402
from pointeuse.panneau import Panneau  # noqa: E402
from pointeuse.suivi import JournalSuivi, NoteSuivi  # noqa: E402

EXEMPLE = Path(__file__).resolve().parents[1] / "docs" / "exemples" / "pointeuse_config.toml"
ALPHA = ("Alpha Industrie", "Armoire ligne 2")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def horloge():
    return {"t": datetime(2026, 11, 17, 17, 0)}


@pytest.fixture
def moteur(tmp_path, horloge):
    shutil.copy(EXEMPLE, tmp_path / "pointeuse_config.toml")
    return Moteur(Config(tmp_path / "pointeuse_config.toml"), Journal(tmp_path / "pointeuse.csv"),
                  tmp_path / "pointeuse_en_cours.json", lambda: horloge["t"])


@pytest.fixture
def journal_suivi(tmp_path):
    return JournalSuivi(tmp_path / settings.NOM_FICHIER_SUIVI)


@pytest.fixture
def fenetre(qapp, moteur, journal_suivi, horloge):
    f = FenetreSuivi(moteur, journal_suivi, horloge=lambda: horloge["t"])
    yield f
    f.modifie = False
    f.deleteLater()


@pytest.fixture
def pointer(qapp, moteur, fenetre, horloge):
    """Onglet Pointer relié à la fenêtre Suivi, comme dans application.py."""
    panneau = Panneau(moteur, horloge=lambda: horloge["t"])
    formulaire = panneau.pointer.formulaire
    formulaire.source_termines = fenetre.projets_termines
    fenetre.note_enregistree.connect(formulaire.recharger)
    formulaire.recharger()
    yield panneau.pointer
    panneau.deleteLater()


def elements(liste):
    return [liste.itemText(i) for i in range(liste.count())]


def ecrire(journal_suivi, horodatage, periode, statut="en_cours", priorite=0, texte="", cle=ALPHA):
    journal_suivi.ajouter(NoteSuivi(datetime.strptime(horodatage, "%Y-%m-%d %H:%M"), periode, *cle,
                                    statut, priorite, texte))


def projets_listes(fenetre):
    return [fenetre.liste.topLevelItem(i).text(2) for i in range(fenetre.liste.topLevelItemCount())]


def test_libelle_periode():
    assert libelle_periode("2026-11-14") == "14/11/2026"
    assert libelle_periode("2026-W46") == "semaine 46 (09/11 → 15/11)"


def test_liste_triee_par_priorite_masques_caches(fenetre, journal_suivi):
    ecrire(journal_suivi, "2026-11-16 18:00", "2026-11-16", priorite=-10, cle=("Gamma Énergie", "Supervision serres"))
    ecrire(journal_suivi, "2026-11-16 18:00", "2026-11-16", statut="termine",
           cle=("Bêta Automatismes", "Firmware passerelle"))
    fenetre.recharger()
    # « Rétrofit presse » (visible = false) et le projet terminé sont cachés ; le projet choisi reste choisi.
    assert projets_listes(fenetre) == ["Supervision serres", "Armoire ligne 2", "Carte capteur v2"]
    assert fenetre.liste.topLevelItem(0).text(1) == "Gamma Énergie"   # colonne Client
    assert fenetre.selection == ALPHA
    fenetre.afficher_masques.setChecked(True)
    assert projets_listes(fenetre) == ["Supervision serres", "Armoire ligne 2", "Rétrofit presse",
                                       "Carte capteur v2", "Firmware passerelle"]


def test_enregistrer_puis_remplacer_dans_la_periode(fenetre, journal_suivi, horloge):
    fenetre.ouvrir(*ALPHA)
    assert fenetre.selection == ALPHA
    assert fenetre.statut.currentData() == settings.STATUT_NOUVELLE_NOTE
    fenetre.texte.setPlainText("Câblage OK.\nSortie 3 à reprendre.")
    fenetre.priorite.setValue(-3)
    assert fenetre.modifie
    assert fenetre.enregistrer()
    assert not fenetre.modifie

    horloge["t"] = datetime(2026, 11, 17, 18, 0)
    fenetre.statut.setCurrentIndex(fenetre.statut.findData("bloque"))
    fenetre.texte.setPlainText("Version de 18 h")
    assert fenetre.enregistrer()

    notes, avertissements = journal_suivi.lire()
    assert avertissements == []
    assert [(n.periode, n.statut, n.priorite) for n in notes] == [("2026-11-17", "en_cours", -3),
                                                                 ("2026-11-17", "bloque", -3)]
    # Seule la dernière version de la journée est affichée.
    assert fenetre.texte.toPlainText() == "Version de 18 h"
    assert fenetre.historique.topLevelItemCount() == 1
    assert fenetre.historique.topLevelItem(0).text(3) == "Version de 18 h"
    assert fenetre.liste.currentItem().text(3) == "bloqué"
    assert fenetre.liste.currentItem().text(0) == "-3"


def test_message_precedent_et_etat_repris(fenetre, journal_suivi):
    ecrire(journal_suivi, "2026-11-13 17:00", "2026-11-13", statut="attente_client", priorite=-5,
           texte="Attente du schéma.")
    fenetre.ouvrir(*ALPHA)
    assert fenetre.titre_precedent.text().startswith("Message du 13/11/2026")
    assert fenetre.texte_precedent.text() == "Attente du schéma."
    # Pas encore de note aujourd'hui : statut et priorité repris, texte vide.
    assert fenetre.statut.currentData() == "attente_client"
    assert fenetre.priorite.value() == -5
    assert fenetre.texte.toPlainText() == ""
    assert not fenetre.modifie


def test_note_d_un_jour_passe(fenetre, journal_suivi):
    fenetre.ouvrir(*ALPHA)
    fenetre.date.setDate(QDate(2026, 11, 16))
    fenetre.texte.setPlainText("Oubli d'hier")
    assert fenetre.enregistrer()
    notes, _ = journal_suivi.lire()
    assert notes[0].periode == "2026-11-16"
    assert fenetre.date.date() == QDate(2026, 11, 16)   # la date choisie est gardée
    assert fenetre.date.maximumDate() == QDate(2026, 11, 17)   # pas de note dans le futur


def test_projet_termine_reste_affiche_tant_qu_il_est_ouvert(fenetre):
    fenetre.ouvrir(*ALPHA)
    fenetre.statut.setCurrentIndex(fenetre.statut.findData("termine"))
    assert fenetre.enregistrer()
    assert "Armoire ligne 2" in projets_listes(fenetre)
    fenetre.ouvrir("Bêta Automatismes", "Carte capteur v2")
    assert "Armoire ligne 2" not in projets_listes(fenetre)


def test_termine_a_confirmer_si_pointe_apres(fenetre, journal_suivi, moteur):
    ecrire(journal_suivi, "2026-11-13 17:00", "2026-11-13", statut="termine")
    moteur.journal.ajouter([Ligne(datetime(2026, 11, 16, 9, 0), datetime(2026, 11, 16, 10, 0), *ALPHA, "cdc", "")])
    fenetre.ouvrir(*ALPHA)
    assert "Armoire ligne 2" in projets_listes(fenetre)
    assert fenetre.liste.currentItem().text(3) == "terminé ?"
    # Le temps du 16/11 apparaît dans l'historique, sous la date du jour où il a été pointé.
    periodes = [fenetre.historique.topLevelItem(i).text(0) for i in range(fenetre.historique.topLevelItemCount())]
    assert periodes == ["16/11/2026", "13/11/2026"]
    assert fenetre.historique.topLevelItem(0).text(1) == "1 h 00"


def test_tache_en_cours_comptee(fenetre, moteur, horloge):
    horloge["t"] = datetime(2026, 11, 17, 9, 0)
    moteur.demarrer(*ALPHA, "cdc")
    horloge["t"] = datetime(2026, 11, 17, 10, 30)
    fenetre.ouvrir(*ALPHA)
    assert fenetre.historique.topLevelItem(0).text(1) == "1 h 30"


def test_echec_d_ecriture_garde_le_texte(fenetre, journal_suivi, monkeypatch):
    avertissements = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: avertissements.append(args[2]))
    fenetre.ouvrir(*ALPHA)
    journal_suivi.chemin.mkdir()   # un dossier à la place du fichier : écriture impossible
    fenetre.texte.setPlainText("À ne pas perdre")
    assert not fenetre.enregistrer()
    assert fenetre.texte.toPlainText() == "À ne pas perdre"
    assert fenetre.modifie
    assert len(avertissements) == 1
    assert avertissements[0].startswith("Note non enregistrée")


def test_saisie_non_enregistree_confirmation(fenetre, monkeypatch):
    reponses = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: reponses.pop(0))
    fenetre.ouvrir(*ALPHA)
    fenetre.texte.setPlainText("Brouillon")
    # Refus : on reste sur le projet, avec le brouillon.
    reponses.append(QMessageBox.No)
    fenetre.ouvrir("Bêta Automatismes", "Carte capteur v2")
    assert fenetre.selection == ALPHA
    assert fenetre.texte.toPlainText() == "Brouillon"
    # Cocher la case recharge la liste sans perdre le brouillon.
    fenetre.afficher_masques.setChecked(True)
    assert fenetre.texte.toPlainText() == "Brouillon"
    # Acceptation : le brouillon est abandonné.
    reponses.append(QMessageBox.Yes)
    fenetre.ouvrir("Bêta Automatismes", "Carte capteur v2")
    assert fenetre.selection == ("Bêta Automatismes", "Carte capteur v2")
    assert fenetre.texte.toPlainText() == ""
    assert not fenetre.modifie


def test_mode_semaine(fenetre, moteur, journal_suivi):
    moteur.config.reglage_suivi = lambda nom: settings.PERIODE_SEMAINE
    fenetre.ouvrir(*ALPHA)
    assert fenetre.periode.text() == "semaine 47 (16/11 → 22/11)"
    fenetre.texte.setPlainText("Bilan de la semaine")
    assert fenetre.enregistrer()
    notes, _ = journal_suivi.lire()
    assert notes[0].periode == "2026-W47"


# ─── Étape 4 : projets terminés cachés dans l'onglet Pointer ─────────────────

def test_pointer_cache_les_projets_termines(pointer, fenetre, journal_suivi, moteur, horloge):
    formulaire = pointer.formulaire
    assert "Alpha Industrie" in elements(formulaire.client)
    # Note « terminé » enregistrée depuis la fenêtre : les listes se mettent à jour tout de suite.
    fenetre.ouvrir(*ALPHA)
    fenetre.statut.setCurrentIndex(fenetre.statut.findData("termine"))
    assert fenetre.enregistrer()
    # Seul projet visible d'Alpha Industrie terminé : le client disparaît aussi.
    assert "Alpha Industrie" not in elements(formulaire.client)
    formulaire.client.setCurrentText("Bêta Automatismes")
    ecrire(journal_suivi, "2026-11-17 17:30", "2026-11-17", statut="termine",
           cle=("Bêta Automatismes", "Firmware passerelle"))
    formulaire.recharger()
    assert elements(formulaire.projet) == ["Carte capteur v2"]
    # « Afficher les projets masqués » : tout revient.
    pointer.masques.setChecked(True)
    assert "Alpha Industrie" in elements(formulaire.client)
    assert elements(formulaire.projet) == ["Carte capteur v2", "Firmware passerelle"]
    pointer.masques.setChecked(False)
    # Du temps pointé après la note : « terminé ? », le projet revient dans les listes.
    moteur.journal.ajouter([Ligne(datetime(2026, 11, 17, 18, 0), datetime(2026, 11, 17, 18, 30),
                                  "Bêta Automatismes", "Firmware passerelle", "", "")])
    formulaire.recharger()
    assert elements(formulaire.projet) == ["Carte capteur v2", "Firmware passerelle"]


def test_pointer_projet_termine_tape_a_la_main(pointer, journal_suivi, moteur):
    ecrire(journal_suivi, "2026-11-16 17:00", "2026-11-16", statut="termine")
    pointer.formulaire.recharger()
    pointer.formulaire.remplir(*ALPHA)
    pointer.demarrer()
    assert moteur.ligne_ouverte.projet == ALPHA[1]
    assert pointer.formulaire.projet.currentText() == ALPHA[1]   # gardé, comme un projet masqué


# ─── Étape 5 : rappel au Stop ────────────────────────────────────────────────

def test_stop_signale_le_projet_arrete(pointer, moteur, horloge):
    arretes = []
    pointer.projet_arrete.connect(lambda client, projet: arretes.append((client, projet)))
    pointer.formulaire.remplir(*ALPHA)
    pointer.demarrer()
    horloge["t"] = datetime(2026, 11, 17, 18, 0)
    pointer.pause_ou_reprendre()
    pointer.stop()                      # arrêt pendant une pause : pas de rappel
    assert arretes == []
    pointer.formulaire.remplir(*ALPHA)
    pointer.demarrer()
    horloge["t"] = datetime(2026, 11, 17, 18, 30)
    pointer.stop()
    assert arretes == [ALPHA]


def test_rappel_au_stop(fenetre, journal_suivi, moteur, monkeypatch):
    ouverts = []
    monkeypatch.setattr(fenetre, "ouvrir", lambda *cle: ouverts.append(cle))
    application = SimpleNamespace(moteur=moteur, suivi=fenetre)
    Application.rappel_au_stop(application, *ALPHA)
    assert ouverts == [ALPHA]           # pas encore de note aujourd'hui : la fenêtre s'ouvre
    ecrire(journal_suivi, "2026-11-17 16:00", "2026-11-17")
    Application.rappel_au_stop(application, *ALPHA)
    assert ouverts == [ALPHA]           # note du jour déjà écrite : rien
    moteur.config.reglage_suivi = lambda nom: False
    Application.rappel_au_stop(application, "Bêta Automatismes", "Carte capteur v2")
    assert ouverts == [ALPHA]           # rappel désactivé ([suivi] rappel_au_stop = false)


def test_rappel_au_stop_mode_semaine(fenetre, journal_suivi, moteur, monkeypatch):
    ouverts = []
    monkeypatch.setattr(fenetre, "ouvrir", lambda *cle: ouverts.append(cle))
    reglages = {"periode_note": settings.PERIODE_SEMAINE, "rappel_au_stop": True}
    moteur.config.reglage_suivi = reglages.get
    ecrire(journal_suivi, "2026-11-16 18:00", "2026-W47")   # note de la semaine, écrite lundi
    Application.rappel_au_stop(SimpleNamespace(moteur=moteur, suivi=fenetre), *ALPHA)
    assert ouverts == []

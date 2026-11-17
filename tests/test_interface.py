"""Tests de l'interface (CDC étape 4), sans écran : plateforme Qt « offscreen »."""

import os
import shutil
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from pointeuse.affichage import duree_texte, texte_info_bulle, texte_statut, version_courte  # noqa: E402
from pointeuse.config import Config  # noqa: E402
from pointeuse.dialogue_absence import DialogueAbsence  # noqa: E402
from pointeuse.journal import Journal  # noqa: E402
from pointeuse.moteur import Absence, LigneOuverte, Moteur  # noqa: E402
from pointeuse.panneau import Panneau  # noqa: E402

EXEMPLE = Path(__file__).resolve().parents[1] / "docs" / "exemples" / "pointeuse_config.toml"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def horloge():
    return {"t": datetime(2026, 11, 17, 9, 0)}


@pytest.fixture
def moteur(tmp_path, horloge):
    shutil.copy(EXEMPLE, tmp_path / "pointeuse_config.toml")
    return Moteur(Config(tmp_path / "pointeuse_config.toml"), Journal(tmp_path / "pointeuse.csv"),
                  tmp_path / "pointeuse_en_cours.json", lambda: horloge["t"])


@pytest.fixture
def pointer(qapp, moteur, horloge):
    panneau = Panneau(moteur, horloge=lambda: horloge["t"])
    yield panneau.pointer   # garder le panneau vivant : sinon Qt détruit l'onglet
    panneau.deleteLater()


# ─── Textes ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("minutes, texte", [(0, "0 h 00"), (5, "0 h 05"), (65, "1 h 05"), (-3, "0 h 00")])
def test_duree_texte(minutes, texte):
    assert duree_texte(minutes) == texte


def test_textes_statut_et_info_bulle():
    maintenant = datetime(2026, 11, 17, 11, 17)
    tache = LigneOuverte(datetime(2026, 11, 17, 10, 12), "A", "X", "cdc")
    pause = LigneOuverte(datetime(2026, 11, 17, 11, 0), "PAUSE")
    assert texte_statut(None, maintenant) == "Aucune tâche en cours"
    assert texte_statut(tache, maintenant) == "En cours depuis 10:12"
    assert texte_info_bulle(tache, maintenant) == "A / X / cdc — depuis 10:12 (1 h 05)"
    assert texte_info_bulle(pause, maintenant) == "En pause depuis 11:00 (0 h 17)"
    assert "2 ligne(s) en attente" in texte_info_bulle(None, maintenant, 2)


# ─── Formulaire ──────────────────────────────────────────────────────────────

def test_projets_filtres_par_client(pointer):
    formulaire = pointer.formulaire
    formulaire.client.setCurrentText("Bêta Automatismes")
    projets = [formulaire.projet.itemText(i) for i in range(formulaire.projet.count())]
    assert projets == ["Carte capteur v2", "Firmware passerelle"]
    assert formulaire.projet.currentText() == "Carte capteur v2"


def test_taches_du_projet_puis_communes(pointer):
    formulaire = pointer.formulaire
    formulaire.client.setCurrentText("Gamma Énergie")
    taches = [formulaire.tache.itemText(i) for i in range(formulaire.tache.count())]
    assert taches == ["interface web", "base de données", "déploiement", "",
                      "réunion", "administratif", "support téléphone"]
    assert formulaire.tache.currentText() == ""   # la tâche reste facultative


def test_projets_masques_sur_demande(pointer):
    formulaire = pointer.formulaire
    formulaire.client.setCurrentText("Alpha Industrie")
    assert formulaire.projet.count() == 1
    pointer.masques.setChecked(True)
    assert formulaire.projet.count() == 2


# ─── Onglet « Pointer » ──────────────────────────────────────────────────────

def test_pointer_un_projet_masque(pointer, moteur):
    """Projet masqué tapé à la main : le temps est imputé, il reste hors de la liste et affiché."""
    pointer.formulaire.remplir("Alpha Industrie", "Rétrofit presse", "doc")
    pointer.demarrer()
    assert moteur.ligne_ouverte.projet == "Rétrofit presse"
    formulaire = pointer.formulaire
    projets = [formulaire.projet.itemText(i) for i in range(formulaire.projet.count())]
    assert projets == ["Armoire ligne 2"]
    assert formulaire.projet.currentText() == "Rétrofit presse"
    formulaire.recharger()   # rechargement périodique de la config
    assert formulaire.projet.currentText() == "Rétrofit presse"


def test_demarrer_pause_reprendre(pointer, moteur, horloge):
    pointer.formulaire.remplir("Alpha Industrie", "Armoire ligne 2", "câblage", "bornier")
    pointer.demarrer()
    assert moteur.ligne_ouverte.tache == "câblage"
    assert pointer.bouton_pause.text().endswith("Pause")

    horloge["t"] = datetime(2026, 11, 17, 10, 0)
    pointer.pause_ou_reprendre()
    assert moteur.en_pause
    assert pointer.bouton_pause.text().endswith("Reprendre")

    horloge["t"] = datetime(2026, 11, 17, 10, 10)
    pointer.pause_ou_reprendre()
    assert moteur.ligne_ouverte.client == "Alpha Industrie"
    assert len(moteur.journal.lire()) == 2


def test_nouveau_client_saisi_ajoute_aux_listes(pointer, moteur):
    pointer.formulaire.remplir("Delta Services", "Audit", "visite")
    pointer.demarrer()
    clients = [pointer.formulaire.client.itemText(i) for i in range(pointer.formulaire.client.count())]
    assert "Delta Services" in clients


def test_modifier_la_description_en_cours(pointer, moteur):
    pointer.formulaire.remplir("Alpha Industrie", "Armoire ligne 2")
    pointer.demarrer()
    pointer.formulaire.description.setText("nouvelle")
    pointer._description_modifiee()
    assert moteur.ligne_ouverte.description == "nouvelle"


def test_alerte_si_csv_bloque(pointer, moteur, horloge, tmp_path):
    pointer.formulaire.remplir("Alpha Industrie", "Armoire ligne 2")
    pointer.demarrer()
    moteur.journal.chemin.unlink(missing_ok=True)
    moteur.journal.chemin.mkdir()   # un dossier à la place du CSV : écriture impossible
    horloge["t"] = datetime(2026, 11, 17, 10, 0)
    pointer.pause_ou_reprendre()
    assert moteur.ecriture_bloquee
    assert not pointer.alerte.isHidden()
    assert "1 ligne(s) en attente" in pointer.alerte.text()


# ─── Retour d'absence ────────────────────────────────────────────────────────

def test_dialogue_absence_valeurs(qapp, moteur):
    precedente = LigneOuverte(datetime(2026, 11, 17, 14, 0), "Alpha Industrie", "Armoire ligne 2", "cdc")
    dialogue = DialogueAbsence(moteur.config, Absence(datetime(2026, 11, 17, 16, 55),
                                                      datetime(2026, 11, 17, 17, 10), precedente))
    dialogue.choix_travail.setChecked(True)
    dialogue._valider()
    assert dialogue.result() == QDialog.Accepted
    assert dialogue.travail
    assert dialogue.reprendre   # case cochée par défaut, lue après fermeture
    assert dialogue.formulaire.valeurs()[:2] == ("Alpha Industrie", "Armoire ligne 2")


def test_dialogue_absence_ferme_sans_valider_vaut_pause(qapp, moteur):
    dialogue = DialogueAbsence(moteur.config, Absence(datetime(2026, 11, 17, 16, 55),
                                                      datetime(2026, 11, 17, 17, 10), None))
    dialogue.choix_travail.setChecked(True)
    dialogue.reject()
    assert not dialogue.travail
    assert not dialogue.reprendre


# ─── Onglet « Insérer / Journée » (étape 5) ──────────────────────────────────

from datetime import date  # noqa: E402

from PySide6.QtCore import QTime  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402

from pointeuse.affichage import minutes_dans_le_jour, texte_plage, totaux_du_jour  # noqa: E402
from pointeuse.journal import Ligne  # noqa: E402

JOUR = date(2026, 11, 17)


def test_texte_plage_et_minuit():
    assert texte_plage(datetime(2026, 11, 17, 8, 30), datetime(2026, 11, 17, 10, 12), JOUR) == "08:30–10:12"
    assert texte_plage(datetime(2026, 11, 17, 13, 30), None, JOUR) == "13:30– …"
    assert texte_plage(datetime(2026, 11, 16, 23, 0), datetime(2026, 11, 17, 1, 0), JOUR) == "16/11 23:00–01:00"
    assert minutes_dans_le_jour(datetime(2026, 11, 16, 23, 0), datetime(2026, 11, 17, 1, 0), JOUR) == 60


def test_totaux_du_jour_ligne_en_cours_comprise():
    lignes = [Ligne(datetime(2026, 11, 16, 23, 30), datetime(2026, 11, 17, 0, 30), "A", "X"),
              Ligne(datetime(2026, 11, 17, 8, 0), datetime(2026, 11, 17, 9, 0), "A", "X"),
              Ligne(datetime(2026, 11, 17, 9, 0), datetime(2026, 11, 17, 9, 15), "PAUSE")]
    ouverte = LigneOuverte(datetime(2026, 11, 17, 9, 15), "A", "X")
    assert totaux_du_jour(lignes, ouverte, datetime(2026, 11, 17, 10, 0, 40), JOUR) == (30 + 60 + 45, 15)


@pytest.fixture
def panneau(qapp, moteur, horloge):
    panneau = Panneau(moteur, horloge=lambda: horloge["t"])
    yield panneau
    panneau.deleteLater()


def test_journee_plage_par_defaut(panneau):
    journee = panneau.journee
    assert journee.jour() == JOUR
    assert journee.plage() == (datetime(2026, 11, 17, 8, 45), datetime(2026, 11, 17, 9, 0))
    assert journee.date.maximumDate().toPython() == JOUR
    assert journee.titre.text() == "Journée du 17/11/2026"


def test_journee_affiche_lignes_et_totaux(panneau, moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2", "câblage", "bornier X1")
    horloge["t"] = datetime(2026, 11, 17, 10, 0)
    moteur.pause()
    horloge["t"] = datetime(2026, 11, 17, 10, 20)
    panneau.journee.rafraichir()
    arbre = panneau.journee.lignes
    assert arbre.topLevelItemCount() == 2
    premiere = arbre.topLevelItem(0)
    assert [premiere.text(c) for c in range(3)] == ["09:00–10:00", "Alpha Industrie / Armoire ligne 2 / câblage",
                                                    "1 h 00"]
    assert premiere.toolTip(1) == "Alpha Industrie / Armoire ligne 2 / câblage\nbornier X1"
    assert arbre.topLevelItem(1).text(1) == "Pause  (en cours)"
    assert panneau.journee.totaux.text() == "Travaillé : 1 h 00      Pause : 0 h 20"


def test_inserer_depuis_l_onglet(panneau, moteur, horloge, monkeypatch):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge["t"] = datetime(2026, 11, 17, 11, 0)
    journee = panneau.journee
    journee.reinitialiser_plage()
    journee.debut.setTime(QTime(10, 0))
    journee.fin.setTime(QTime(10, 30))
    journee.formulaire.remplir("Gamma Énergie", "Supervision serres", "réunion", "point hebdo")
    signaux = []
    journee.etat_change.connect(lambda: signaux.append(1))
    journee.inserer()
    lignes = moteur.journal.lire()
    assert [(l.debut.hour, l.debut.minute, l.client) for l in lignes] == [
        (9, 0, "Alpha Industrie"), (10, 0, "Gamma Énergie")]
    assert moteur.ligne_ouverte.debut == datetime(2026, 11, 17, 10, 30)
    assert signaux == [1]
    assert journee.formulaire.description.text() == ""
    assert journee.lignes.topLevelItemCount() == 3


def test_inserer_demande_confirmation_si_ligne_remplacee(panneau, moteur, horloge, monkeypatch):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge["t"] = datetime(2026, 11, 17, 9, 30)
    moteur.pause()
    horloge["t"] = datetime(2026, 11, 17, 11, 0)
    journee = panneau.journee
    journee.reinitialiser_plage()
    journee.debut.setTime(QTime(9, 0))
    journee.fin.setTime(QTime(9, 30))
    journee.formulaire.remplir("Gamma Énergie", "Supervision serres")
    questions = []

    def repondre(parent, titre, texte):
        questions.append(texte)
        return QMessageBox.No
    monkeypatch.setattr(QMessageBox, "question", repondre)
    journee.inserer()
    assert "Alpha Industrie / Armoire ligne 2 09:00 → 09:30" in questions[0]
    assert moteur.journal.lire()[0].client == "Alpha Industrie"   # refusé : rien n'a changé

    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.Yes)
    journee.inserer()
    assert moteur.journal.lire()[0].client == "Gamma Énergie"


def test_inserer_plage_invalide_message(panneau, moteur, monkeypatch):
    journee = panneau.journee
    journee.debut.setTime(QTime(8, 50))
    journee.fin.setTime(QTime(8, 40))
    journee.formulaire.remplir("Gamma Énergie", "Supervision serres")
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, titre, texte: messages.append(texte))
    journee.inserer()
    assert messages == ["L'heure de fin doit être après l'heure de début."]
    assert moteur.journal.lire() == []


@pytest.mark.parametrize("version, texte", [("0.1.0", "V0.1"), ("1.0.0", "V1.0"), ("0.1.2", "V0.1.2")])
def test_version_courte(version, texte):
    assert version_courte(version) == texte

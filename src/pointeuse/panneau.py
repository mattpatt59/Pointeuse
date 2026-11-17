"""Panneau ouvert au clic sur l'icône : onglets « Pointer » et « Insérer / Journée » (onglet_journee.py)."""

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QTabWidget, QVBoxLayout, QWidget)

from pointeuse import settings
from pointeuse.affichage import duree_texte, minutes_ecoulees, texte_statut
from pointeuse.config import ConfigInvalide
from pointeuse.formulaire import FormulaireTache
from pointeuse.moteur import Moteur
from pointeuse.onglet_journee import OngletJournee


class OngletPointer(QWidget):
    """Onglet 1 : démarrer une tâche, pause / reprendre."""

    etat_change = Signal()

    def __init__(self, moteur: Moteur, horloge=datetime.now, parent=None):
        super().__init__(parent)
        self.moteur = moteur
        self.horloge = horloge

        self.statut = QFrame(objectName="statut")
        self.statut_texte = QLabel()
        self.chrono = QLabel(objectName="chrono")
        ligne_statut = QHBoxLayout(self.statut)
        ligne_statut.addWidget(self.statut_texte, 1)
        ligne_statut.addWidget(self.chrono)

        self.alerte = QLabel(objectName="alerte", wordWrap=True)
        self.alerte.hide()

        self.formulaire = FormulaireTache(moteur.config)
        self.formulaire.description.editingFinished.connect(self._description_modifiee)

        self.bouton_demarrer = QPushButton("▶  Démarrer", objectName="primaire")
        self.bouton_pause = QPushButton()
        self.bouton_demarrer.clicked.connect(self.demarrer)
        self.bouton_pause.clicked.connect(self.pause_ou_reprendre)
        boutons = QHBoxLayout()
        boutons.addWidget(self.bouton_demarrer)
        boutons.addWidget(self.bouton_pause)

        self.masques = QCheckBox("Afficher les projets masqués")
        self.masques.toggled.connect(self.formulaire.changer_affichage_masques)

        disposition = QVBoxLayout(self)
        disposition.setContentsMargins(16, 16, 16, 16)
        disposition.setSpacing(12)
        disposition.addWidget(self.statut)
        disposition.addWidget(self.alerte)
        disposition.addWidget(self.formulaire)
        disposition.addLayout(boutons)
        disposition.addWidget(self.masques)
        disposition.addStretch()

        self.preremplir()
        self.rafraichir()

    # ─── Affichage ───────────────────────────────────────────────────────────

    def preremplir(self) -> None:
        """Le formulaire montre la tâche en cours, sinon la dernière tâche."""
        ligne = self.moteur.ligne_ouverte
        if ligne is None or ligne.est_pause:
            ligne = self.moteur.derniere_tache
        if ligne is not None:
            self.formulaire.remplir(ligne.client, ligne.projet, ligne.tache, ligne.description)

    def rafraichir(self) -> None:
        ligne = self.moteur.ligne_ouverte
        maintenant = self.horloge()
        if ligne is None or ligne.est_pause:
            couleur_point = settings.COULEUR_GRIS
        else:
            couleur_point = settings.COULEUR_VERT_FONCE
        self.statut_texte.setText(f'<span style="color:{couleur_point}">●</span>&nbsp; '
                                  + texte_statut(ligne, maintenant))
        if ligne is None:
            self.chrono.setText("")
        else:
            self.chrono.setText(duree_texte(minutes_ecoulees(ligne, maintenant)))
        self.statut.setProperty("pause", ligne is None or ligne.est_pause)
        self.statut.style().unpolish(self.statut)
        self.statut.style().polish(self.statut)

        if self.moteur.en_pause and self.moteur.derniere_tache is not None:
            self.bouton_pause.setText("▶  Reprendre")
            self.bouton_pause.setObjectName("reprendre")
            self.bouton_pause.setEnabled(True)
        else:
            self.bouton_pause.setText("❚❚  Pause")
            self.bouton_pause.setObjectName("pause")
            self.bouton_pause.setEnabled(not self.moteur.en_pause)
        self.bouton_pause.style().unpolish(self.bouton_pause)
        self.bouton_pause.style().polish(self.bouton_pause)

        if self.moteur.derniere_erreur:
            message = self.moteur.derniere_erreur
            if self.moteur.ecriture_bloquee:
                message = (f"{len(self.moteur.en_attente)} ligne(s) en attente : fermez pointeuse.csv "
                           f"(nouvel essai chaque minute, rien n'est perdu).\n{message}")
            self.alerte.setText(message)
            self.alerte.show()
        else:
            self.alerte.hide()

    # ─── Actions ─────────────────────────────────────────────────────────────

    def demarrer(self) -> None:
        client, projet, tache, description = self.formulaire.valeurs()
        if not client or not projet:
            QMessageBox.warning(self, settings.NOM_APPLICATION, "Le client et le projet sont obligatoires.")
            return
        try:
            self.moteur.demarrer(client, projet, tache, description)
        except (ValueError, ConfigInvalide) as erreur:   # ValueError couvre NomReserve
            QMessageBox.warning(self, settings.NOM_APPLICATION, str(erreur))
            return
        self.formulaire.recharger()
        self.preremplir()
        self._apres_action()

    def pause_ou_reprendre(self) -> None:
        if self.moteur.en_pause:
            self.moteur.reprendre()
            self.preremplir()
        else:
            self.moteur.pause()
        self._apres_action()

    def _description_modifiee(self) -> None:
        """La description reste modifiable pendant la tâche (si le formulaire montre la tâche en cours)."""
        ligne = self.moteur.ligne_ouverte
        if ligne is None or ligne.est_pause:
            return
        client, projet, tache, description = self.formulaire.valeurs()
        if tache is None:
            tache = ""
        affiche = (client.casefold(), projet.casefold(), tache.casefold())
        if affiche == (ligne.client.casefold(), ligne.projet.casefold(), ligne.tache.casefold()):
            if description != ligne.description:
                self.moteur.modifier_description(description)
                self._apres_action()

    def _apres_action(self) -> None:
        self.rafraichir()
        self.etat_change.emit()


class Panneau(QWidget):
    """Fenêtre principale. Fermer la fenêtre la masque : l'appli reste dans la zone de notification."""

    def __init__(self, moteur: Moteur, horloge=datetime.now, parent=None):
        super().__init__(parent, Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setObjectName("panneau")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle(settings.NOM_APPLICATION)
        self.setFixedWidth(settings.LARGEUR_PANNEAU_PX)
        self.quitter_a_la_fermeture = False

        entete = QLabel(settings.NOM_APPLICATION, objectName="entete")
        self.onglets = QTabWidget()
        self.pointer = OngletPointer(moteur, horloge)
        self.onglets.addTab(self.pointer, "Pointer")
        self.journee = OngletJournee(moteur, horloge)
        self.onglets.addTab(self.journee, "Insérer / Journée")
        # Une action dans un onglet se voit tout de suite dans l'autre.
        self.pointer.etat_change.connect(self.journee.rafraichir)
        self.journee.etat_change.connect(self.pointer.rafraichir)

        disposition = QVBoxLayout(self)
        disposition.setContentsMargins(0, 0, 0, 0)
        disposition.setSpacing(0)
        disposition.addWidget(entete)
        disposition.addWidget(self.onglets)

    def closeEvent(self, evenement) -> None:
        if self.quitter_a_la_fermeture:
            evenement.accept()
            return
        evenement.ignore()
        self.hide()

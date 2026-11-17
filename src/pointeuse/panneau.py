"""Panneau ouvert au clic sur l'icône : onglets « Pointer », « Insérer / Journée » (onglet_journee.py)
et « À propos » (onglet_a_propos.py)."""

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QTabWidget, QVBoxLayout, QWidget)

from pointeuse import settings
from pointeuse.affichage import duree_texte, minutes_ecoulees, texte_statut, titre_application
from pointeuse.config import ConfigInvalide, Raccourci
from pointeuse.formulaire import FormulaireTache
from pointeuse.moteur import Moteur
from pointeuse.onglet_a_propos import OngletAPropos
from pointeuse.onglet_journee import OngletJournee


class OngletPointer(QWidget):
    """Onglet 1 : démarrer / modifier une tâche, pause / reprendre, stop, repas, boutons rapides."""

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

        # Ligne 1 : la tâche (Modifier garde l'heure de début, Démarrer coupe et en ouvre une autre).
        self.bouton_modifier = QPushButton("✎  Modifier")
        self.bouton_modifier.setToolTip("Corrige la tâche en cours avec le formulaire, sans la couper")
        self.bouton_demarrer = QPushButton("▶  Démarrer", objectName="primaire")
        self.bouton_demarrer.setToolTip("Termine la ligne en cours et démarre la tâche du formulaire")
        self.bouton_modifier.clicked.connect(self.modifier)
        self.bouton_demarrer.clicked.connect(self.demarrer)
        ligne_tache = QHBoxLayout()
        ligne_tache.addWidget(self.bouton_modifier)
        ligne_tache.addWidget(self.bouton_demarrer)

        # Ligne 2 : s'arrêter.
        self.bouton_pause = QPushButton()
        self.bouton_stop = QPushButton("■  Stop", objectName="stop")
        self.bouton_stop.setToolTip("Termine la ligne en cours, sans pause (fin de journée)")
        self.bouton_repas = QPushButton(settings.DESCRIPTION_REPAS, objectName="pause")
        self.bouton_repas.setToolTip(f"Pause « {settings.DESCRIPTION_REPAS} »")
        self.bouton_pause.clicked.connect(self.pause_ou_reprendre)
        self.bouton_stop.clicked.connect(self.stop)
        self.bouton_repas.clicked.connect(self.repas)
        ligne_arret = QHBoxLayout()
        ligne_arret.addWidget(self.bouton_pause)
        ligne_arret.addWidget(self.bouton_stop)
        ligne_arret.addWidget(self.bouton_repas)

        # Boutons rapides [[raccourcis]] du fichier de config (reconstruits s'il change).
        self.titre_raccourcis = QLabel("Boutons rapides", objectName="titre_raccourcis")
        self.zone_raccourcis = QGridLayout()
        self.zone_raccourcis.setSpacing(8)
        self.boutons_raccourcis: list[QPushButton] = []
        self._raccourcis_affiches: list[Raccourci] | None = None

        self.masques = QCheckBox("Afficher les projets masqués")
        self.masques.toggled.connect(self.formulaire.changer_affichage_masques)

        disposition = QVBoxLayout(self)
        disposition.setContentsMargins(16, 16, 16, 16)
        disposition.setSpacing(12)
        disposition.addWidget(self.statut)
        disposition.addWidget(self.alerte)
        disposition.addWidget(self.formulaire)
        disposition.addLayout(ligne_tache)
        disposition.addLayout(ligne_arret)
        disposition.addWidget(self.titre_raccourcis)
        disposition.addLayout(self.zone_raccourcis)
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

        en_tache = ligne is not None and not ligne.est_pause
        self.bouton_modifier.setEnabled(en_tache)
        self.bouton_stop.setEnabled(ligne is not None)
        en_repas = (ligne is not None and ligne.est_pause
                    and ligne.description == settings.DESCRIPTION_REPAS)
        self.bouton_repas.setEnabled(not en_repas)

        # Tâche lancée sans projet (bouton rapide « client seul ») : le champ Projet est en rouge.
        projet = self.formulaire.projet
        projet.setProperty("a_completer", en_tache and ligne.projet == "")
        projet.style().unpolish(projet)
        projet.style().polish(projet)

        self.afficher_raccourcis()

        if self.moteur.derniere_erreur:
            message = self.moteur.derniere_erreur
            if self.moteur.ecriture_bloquee:
                message = (f"{len(self.moteur.en_attente)} ligne(s) en attente : fermez pointeuse.csv "
                           f"(nouvel essai chaque minute, rien n'est perdu).\n{message}")
            self.alerte.setText(message)
            self.alerte.show()
        else:
            self.alerte.hide()

    def afficher_raccourcis(self) -> None:
        """(Re)construit les boutons rapides si la liste du fichier de config a changé."""
        raccourcis = self.moteur.config.raccourcis()
        if raccourcis == self._raccourcis_affiches:
            return
        self._raccourcis_affiches = raccourcis
        for bouton in self.boutons_raccourcis:
            self.zone_raccourcis.removeWidget(bouton)
            bouton.deleteLater()
        self.boutons_raccourcis = []
        colonnes = settings.COLONNES_RACCOURCIS
        marges = 2 * 16 + (colonnes - 1) * 8          # marges de l'onglet, espace entre colonnes
        largeur_texte = (settings.LARGEUR_PANNEAU_PX - marges) // colonnes - 2 * 14   # padding du bouton
        for rang, raccourci in enumerate(raccourcis):
            bouton = QPushButton(objectName="raccourci")
            bouton.ensurePolished()   # police de la feuille de style (gras) pour mesurer le texte
            bouton.setText(bouton.fontMetrics().elidedText(raccourci.libelle, Qt.ElideRight, largeur_texte))
            bouton.setToolTip(self._info_raccourci(raccourci))
            bouton.clicked.connect(lambda _=False, r=raccourci: self.lancer_raccourci(r))
            self.zone_raccourcis.addWidget(bouton, rang // colonnes, rang % colonnes)
            self.boutons_raccourcis.append(bouton)
        self.titre_raccourcis.setVisible(len(raccourcis) > 0)

    @staticmethod
    def _info_raccourci(raccourci: Raccourci) -> str:
        lignes = [f"Client : {raccourci.client}"]
        if raccourci.projet:
            lignes.append(f"Projet : {raccourci.projet}")
        else:
            lignes.append("Projet : à compléter (bouton Modifier)")
        if raccourci.tache:
            lignes.append(f"Tâche : {raccourci.tache}")
        if raccourci.description:
            lignes.append(f"Description : {raccourci.description}")
        return "\n".join(lignes)

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

    def modifier(self) -> None:
        """Applique le formulaire à la tâche en cours, sans la couper."""
        client, projet, tache, description = self.formulaire.valeurs()
        if not client:
            QMessageBox.warning(self, settings.NOM_APPLICATION, "Le client est obligatoire.")
            return
        try:
            self.moteur.modifier(client, projet, tache, description)
        except (ValueError, ConfigInvalide) as erreur:   # ValueError couvre NomReserve
            QMessageBox.warning(self, settings.NOM_APPLICATION, str(erreur))
            return
        self.formulaire.recharger()
        self.preremplir()
        self._apres_action()

    def lancer_raccourci(self, raccourci: Raccourci) -> None:
        """Bouton rapide : démarre tout de suite, même sans projet (à compléter avec Modifier)."""
        ouverte = self.moteur.ligne_ouverte
        if (ouverte is not None and not ouverte.est_pause and not raccourci.description
                and ouverte.meme_tache(raccourci.client, raccourci.projet, raccourci.tache)):
            return   # déjà en cours : ne pas effacer la description saisie
        tache = raccourci.tache
        if not tache:
            tache = None
        try:
            self.moteur.demarrer(raccourci.client, raccourci.projet, tache, raccourci.description,
                                 projet_obligatoire=False)
        except (ValueError, ConfigInvalide) as erreur:
            QMessageBox.warning(self, settings.NOM_APPLICATION, str(erreur))
            return
        self.formulaire.recharger()
        self.preremplir()
        self._apres_action()

    def stop(self) -> None:
        self.moteur.arreter()
        self._apres_action()

    def repas(self) -> None:
        self.moteur.pause(settings.DESCRIPTION_REPAS)
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
        self.setWindowTitle(titre_application())
        self.setFixedWidth(settings.LARGEUR_PANNEAU_PX)
        self.quitter_a_la_fermeture = False

        entete = QLabel(titre_application(), objectName="entete")
        self.onglets = QTabWidget()
        self.pointer = OngletPointer(moteur, horloge)
        self.onglets.addTab(self.pointer, "Pointer")
        self.journee = OngletJournee(moteur, horloge)
        self.onglets.addTab(self.journee, "Insérer / Journée")
        self.a_propos = OngletAPropos()
        self.onglets.addTab(self.a_propos, "À propos")
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

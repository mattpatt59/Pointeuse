"""Onglet « Insérer / Journée » (CDC étape 5).

En haut : insérer une tâche à heures fixes (oubli de pointage, réunion notée après coup).
En bas : les lignes du jour choisi et ses totaux, ligne en cours comprise.
"""

from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QDate, QTime, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDateEdit, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
                               QTimeEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from pointeuse import settings
from pointeuse.affichage import (duree_texte, libelle_ligne, minutes_dans_le_jour, texte_plage,
                                 totaux_du_jour)
from pointeuse.config import ConfigInvalide
from pointeuse.formulaire import FormulaireTache, _etiquette
from pointeuse.journal import JournalBloque, a_la_minute
from pointeuse.moteur import Moteur


class OngletJournee(QWidget):

    etat_change = Signal()

    def __init__(self, moteur: Moteur, horloge=datetime.now, parent=None):
        super().__init__(parent)
        self.moteur = moteur
        self.horloge = horloge

        # ─── Insérer un temps ────────────────────────────────────────────────
        self.date = QDateEdit(calendarPopup=True, displayFormat=settings.FORMAT_DATE_QT)
        self.debut = QTimeEdit(displayFormat=settings.FORMAT_HEURE_QT)
        self.fin = QTimeEdit(displayFormat=settings.FORMAT_HEURE_QT)
        for heure in (self.debut, self.fin):
            heure.setAlignment(Qt.AlignCenter)
            heure.setMinimumWidth(settings.LARGEUR_CHAMP_HEURE_PX)
        plage = QHBoxLayout()
        plage.setSpacing(8)
        plage.addWidget(_etiquette("Le"))
        plage.addWidget(self.date, 1)
        plage.addWidget(_etiquette("de"))
        plage.addWidget(self.debut)
        plage.addWidget(_etiquette("à"))
        plage.addWidget(self.fin)

        self.formulaire = FormulaireTache(moteur.config)
        self.bouton_inserer = QPushButton("＋  Insérer", objectName="primaire")
        self.bouton_inserer.clicked.connect(self.inserer)

        # ─── Journée ─────────────────────────────────────────────────────────
        self.titre = QLabel(objectName="titre_journee")
        self.lignes = QTreeWidget(rootIsDecorated=False, uniformRowHeights=True)
        self.lignes.setHeaderLabels(["Heures", "Tâche", "Durée"])
        self.lignes.setMinimumHeight(settings.HAUTEUR_JOURNEE_PX)
        entete = self.lignes.header()
        entete.setStretchLastSection(False)
        entete.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        entete.setSectionResizeMode(1, QHeaderView.Stretch)
        entete.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.totaux = QLabel(objectName="totaux")

        disposition = QVBoxLayout(self)
        disposition.setContentsMargins(16, 16, 16, 16)
        disposition.setSpacing(12)
        disposition.addLayout(plage)
        disposition.addWidget(self.formulaire)
        disposition.addWidget(self.bouton_inserer)
        disposition.addWidget(self.titre)
        disposition.addWidget(self.lignes, 1)
        disposition.addWidget(self.totaux)

        self.date.dateChanged.connect(self.rafraichir)
        self.reinitialiser_plage()

    # ─── Affichage ───────────────────────────────────────────────────────────

    def jour(self) -> date:
        return self.date.date().toPython()

    def reinitialiser_plage(self) -> None:
        """Plage proposée : les DUREE_INSERTION_DEFAUT_MIN dernières minutes, aujourd'hui."""
        maintenant = a_la_minute(self.horloge())
        debut = maintenant - timedelta(minutes=settings.DUREE_INSERTION_DEFAUT_MIN)
        if debut.date() != maintenant.date():
            debut = datetime.combine(maintenant.date(), time.min)
        aujourdhui = QDate(maintenant.year, maintenant.month, maintenant.day)
        self.date.blockSignals(True)
        self.date.setMaximumDate(aujourdhui)
        self.date.setDate(aujourdhui)
        self.date.blockSignals(False)
        self.debut.setTime(QTime(debut.hour, debut.minute))
        self.fin.setTime(QTime(maintenant.hour, maintenant.minute))
        self.rafraichir()

    def rafraichir(self, *_) -> None:
        jour = self.jour()
        maintenant = self.horloge()
        self.titre.setText(f"Journée du {jour:%d/%m/%Y}")
        lignes = self.moteur.lignes_du_jour(jour)

        self.lignes.clear()
        for ligne in lignes:
            minutes = minutes_dans_le_jour(ligne.debut, ligne.fin, jour)
            element = QTreeWidgetItem([texte_plage(ligne.debut, ligne.fin, jour),
                                       libelle_ligne(ligne.client, ligne.projet, ligne.tache),
                                       duree_texte(minutes)])
            self._mettre_en_forme(element, ligne.est_pause, ligne.description)
            self.lignes.addTopLevelItem(element)

        ouverte = self.moteur.ligne_ouverte
        if ouverte is not None and ouverte.debut.date() <= jour <= maintenant.date():
            minutes = minutes_dans_le_jour(ouverte.debut, a_la_minute(maintenant), jour)
            libelle = libelle_ligne(ouverte.client, ouverte.projet, ouverte.tache) + "  (en cours)"
            element = QTreeWidgetItem([texte_plage(ouverte.debut, None, jour), libelle, duree_texte(minutes)])
            self._mettre_en_forme(element, ouverte.est_pause, ouverte.description)
            police = element.font(1)
            police.setItalic(True)
            for colonne in range(3):
                element.setFont(colonne, police)
            self.lignes.addTopLevelItem(element)
        else:
            ouverte = None

        travail, pause = totaux_du_jour(lignes, ouverte, maintenant, jour)
        self.totaux.setText(f"Travaillé : {duree_texte(travail)}      Pause : {duree_texte(pause)}")

    @staticmethod
    def _mettre_en_forme(element: QTreeWidgetItem, est_pause: bool, description: str) -> None:
        element.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
        # Le libellé peut être tronqué : l'info-bulle le donne en entier, avec la description.
        info = element.text(1)
        if description:
            info += "\n" + description
        element.setToolTip(1, info)
        if est_pause:
            for colonne in range(3):
                element.setForeground(colonne, QColor(settings.COULEUR_GRIS))

    # ─── Action ──────────────────────────────────────────────────────────────

    def plage(self) -> tuple[datetime, datetime]:
        jour = self.jour()
        return (datetime.combine(jour, self.debut.time().toPython()),
                datetime.combine(jour, self.fin.time().toPython()))

    def inserer(self) -> None:
        client, projet, tache, description = self.formulaire.valeurs()
        if not client or not projet:
            QMessageBox.warning(self, settings.NOM_APPLICATION, "Le client et le projet sont obligatoires.")
            return
        debut, fin = self.plage()
        try:
            remplacees = self.moteur.verifier_insertion(debut, fin)
            if remplacees and not self.confirmer(remplacees):
                return
            self.moteur.inserer(debut, fin, client, projet, tache, description)
        except (ValueError, ConfigInvalide, JournalBloque) as erreur:   # ValueError couvre InsertionImpossible
            QMessageBox.warning(self, settings.NOM_APPLICATION, str(erreur))
            return
        self.formulaire.recharger()
        self.formulaire.description.clear()
        self.rafraichir()
        self.etat_change.emit()

    def confirmer(self, remplacees) -> bool:
        """CDC : « Cette plage remplace : A 10:00 → 10:30. Continuer ? »"""
        details = []
        for ligne in remplacees:
            details.append(f"• {libelle_ligne(ligne.client, ligne.projet, ligne.tache)} "
                           f"{ligne.debut:%H:%M} → {ligne.fin:%H:%M}")
        texte = "Cette plage remplace :\n" + "\n".join(details) + "\n\nContinuer ?"
        reponse = QMessageBox.question(self, settings.NOM_APPLICATION, texte)
        return reponse == QMessageBox.Yes

"""Fenêtre « Suivi des projets » : statut, priorité et note par période (CDC suivi_projets.md).

À gauche, les projets triés par priorité ; à droite, le projet choisi :
- « Message du … » : la note de la période précédente, en lecture seule ;
- « Travail en cours » : la note de la période choisie, avec statut et priorité.
  Enregistrer ajoute une version dans pointeuse_suivi.jsonl (ADR 004) ;
- l'historique : temps pointé et notes, du plus récent au plus ancien.
"""

from datetime import date, datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
                               QPlainTextEdit, QPushButton, QSpinBox, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from pointeuse import settings
from pointeuse.affichage import duree_texte, titre_application
from pointeuse.journal import Ligne
from pointeuse.moteur import Moteur
from pointeuse.suivi import (JournalSuivi, NoteSuivi, ProjetSuivi, etats_actuels, extrait, historique,
                             jours_de_periode, libelle_statut, minutes_par_jour, note_de_periode, note_precedente,
                             nouvelle_note, periode_de, projets_suivis)

ROLE_CLE = Qt.UserRole


def libelle_periode(periode: str) -> str:
    """« 14/11/2026 » ou « semaine 46 (09/11 → 15/11) »."""
    debut, fin = jours_de_periode(periode)
    if debut == fin:
        return debut.strftime("%d/%m/%Y")
    return f"semaine {debut.isocalendar()[1]} ({debut:%d/%m} → {fin:%d/%m})"


def _titre_section(texte: str) -> QLabel:
    return QLabel(texte, objectName="titre_section")


class FenetreSuivi(QWidget):

    def __init__(self, moteur: Moteur, journal_suivi: JournalSuivi, horloge=datetime.now, parent=None):
        super().__init__(parent, Qt.Window)
        self.moteur = moteur
        self.journal_suivi = journal_suivi
        self.horloge = horloge
        self.notes: list[NoteSuivi] = []
        self.lignes: list[Ligne] = []
        self.selection: tuple[str, str] | None = None
        self.modifie = False          # note saisie et pas encore enregistrée
        self._chargement = False      # remplissage par le programme : ne compte pas comme une saisie
        self._date_affichee: date | None = None

        self.setObjectName("fenetre_suivi")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle(f"Suivi des projets — {titre_application()}")
        self.resize(settings.LARGEUR_FENETRE_SUIVI_PX, settings.HAUTEUR_FENETRE_SUIVI_PX)

        # ─── Gauche : projets ────────────────────────────────────────────────
        self.afficher_masques = QCheckBox("Afficher les projets terminés ou masqués")
        self.afficher_masques.toggled.connect(self.remplir_liste)
        self.liste = QTreeWidget(rootIsDecorated=False, alternatingRowColors=True)
        self.liste.setHeaderLabels(["Prio.", "Client", "Projet", "Statut"])
        self.liste.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.liste.header().setStretchLastSection(False)
        self.liste.currentItemChanged.connect(self._selection_changee)
        gauche = QVBoxLayout()
        gauche.addWidget(self.afficher_masques)
        gauche.addWidget(self.liste, 1)
        conteneur_gauche = QWidget()
        conteneur_gauche.setLayout(gauche)
        conteneur_gauche.setFixedWidth(settings.LARGEUR_LISTE_SUIVI_PX)

        # ─── Droite : projet choisi ──────────────────────────────────────────
        self.titre = QLabel(objectName="titre_suivi", wordWrap=True)
        self.alerte = QLabel(objectName="alerte", wordWrap=True)
        self.alerte.hide()

        self.titre_precedent = _titre_section("")
        self.texte_precedent = QLabel(objectName="note_precedente", wordWrap=True)
        self.texte_precedent.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.texte_precedent.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.date = QDateEdit(calendarPopup=True, displayFormat=settings.FORMAT_DATE_QT)
        self.date.dateChanged.connect(self._date_changee)
        self.periode = QLabel()
        self.periode.setProperty("etiquette", True)
        self.statut = QComboBox()
        for code, libelle in settings.STATUTS_SUIVI.items():
            self.statut.addItem(libelle, code)
        self.priorite = QSpinBox(minimum=settings.PRIORITE_MIN, maximum=settings.PRIORITE_MAX)
        self.priorite.setToolTip(f"{settings.PRIORITE_MIN} = urgent … {settings.PRIORITE_MAX} = peut attendre")
        ligne_note = QHBoxLayout()
        for widget in (QLabel("Note du"), self.date, self.periode):
            ligne_note.addWidget(widget)
        ligne_note.addStretch()
        for widget in (QLabel("Statut"), self.statut, QLabel("Priorité"), self.priorite):
            ligne_note.addWidget(widget)

        self.texte = QPlainTextEdit()
        self.texte.setPlaceholderText("Ce qui fonctionne, ce qui ne fonctionne pas, la suite…")
        self.bouton_enregistrer = QPushButton("Enregistrer", objectName="primaire")
        self.bouton_enregistrer.clicked.connect(self.enregistrer)
        ligne_bouton = QHBoxLayout()
        ligne_bouton.addStretch()
        ligne_bouton.addWidget(self.bouton_enregistrer)

        self.historique = QTreeWidget(rootIsDecorated=False, alternatingRowColors=True)
        self.historique.setHeaderLabels(["Période", "Temps", "Statut", "Note"])
        self.historique.header().setStretchLastSection(True)

        for signal in (self.texte.textChanged, self.statut.currentIndexChanged, self.priorite.valueChanged):
            signal.connect(self._saisie)

        droite = QVBoxLayout()
        droite.addWidget(self.titre)
        droite.addWidget(self.alerte)
        droite.addWidget(self.titre_precedent)
        droite.addWidget(self.texte_precedent)
        droite.addWidget(_titre_section("Travail en cours"))
        droite.addLayout(ligne_note)
        droite.addWidget(self.texte, 2)
        droite.addLayout(ligne_bouton)
        droite.addWidget(_titre_section("Historique"))
        droite.addWidget(self.historique, 2)
        self.zone_projet = QWidget()
        self.zone_projet.setLayout(droite)

        disposition = QHBoxLayout(self)
        disposition.setContentsMargins(16, 16, 16, 16)
        disposition.setSpacing(16)
        disposition.addWidget(conteneur_gauche)
        disposition.addWidget(self.zone_projet, 1)

        self.recharger()

    # ─── Données ─────────────────────────────────────────────────────────────

    @property
    def mode_periode(self) -> str:
        return self.moteur.config.reglage_suivi("periode_note")

    def _lignes_pointees(self) -> list[Ligne]:
        """Lignes du CSV + la tâche en cours jusqu'à maintenant (pour « terminé ? » et le temps du jour)."""
        lignes = self.moteur.journal.lire() + list(self.moteur.en_attente)
        ouverte = self.moteur.ligne_ouverte
        maintenant = self.horloge().replace(second=0, microsecond=0)
        if ouverte is not None and not ouverte.est_pause and maintenant > ouverte.debut:
            lignes.append(ouverte.fermer(maintenant))
        return lignes

    def _projets_config(self) -> list[tuple[str, str, bool]]:
        config = self.moteur.config
        projets = []
        clients_visibles = config.clients()
        for client in config.clients(inclure_masques=True):
            projets_visibles = config.projets(client)
            for projet in config.projets(client, inclure_masques=True):
                projets.append((client, projet, client in clients_visibles and projet in projets_visibles))
        return projets

    def recharger(self) -> None:
        """Relit le journal de suivi et le CSV, puis réaffiche tout."""
        self.notes, avertissements = self.journal_suivi.lire()
        self.lignes = self._lignes_pointees()
        if avertissements:
            self.alerte.setText(f"{len(avertissements)} remarque(s) sur {self.journal_suivi.chemin.name} "
                                f"(survoler pour le détail).")
            self.alerte.setToolTip("\n".join(avertissements))
            self.alerte.show()
        else:
            self.alerte.hide()
        self.remplir_liste()

    # ─── Liste des projets ───────────────────────────────────────────────────

    def remplir_liste(self, *_) -> None:
        ancienne_selection = self.selection
        tous = projets_suivis(self._projets_config(), self.notes, self.lignes)
        self.liste.blockSignals(True)
        self.liste.clear()
        a_selectionner = None
        for projet in tous:
            # Le projet ouvert reste affiché, même s'il vient de passer « terminé ».
            if projet.masque and not self.afficher_masques.isChecked() and projet.cle != self.selection:
                continue
            element = self._element_projet(projet)
            self.liste.addTopLevelItem(element)
            if projet.cle == self.selection:
                a_selectionner = element
        for colonne in (0, 1, 3):
            self.liste.resizeColumnToContents(colonne)
        if a_selectionner is None and self.liste.topLevelItemCount() > 0:
            a_selectionner = self.liste.topLevelItem(0)
        if a_selectionner is not None:
            self.liste.setCurrentItem(a_selectionner)
        self.liste.blockSignals(False)
        if a_selectionner is None:
            self.selection = None
        else:
            self.selection = a_selectionner.data(0, ROLE_CLE)
        if self.selection is None or self.selection != ancienne_selection or self._date_affichee is None:
            self.charger_projet()
            return
        # Même projet : garder la date choisie et, si elle n'est pas enregistrée, la saisie en cours.
        if not self.modifie:
            self._charger_note()
        self._remplir_historique()

    @staticmethod
    def _element_projet(projet: ProjetSuivi) -> QTreeWidgetItem:
        element = QTreeWidgetItem([str(projet.priorite), projet.client, projet.projet, libelle_statut(projet.statut)])
        element.setData(0, ROLE_CLE, projet.cle)
        for colonne in (1, 2):   # texte complet si la colonne est trop étroite
            element.setToolTip(colonne, f"{projet.client} — {projet.projet}")
        element.setTextAlignment(0, Qt.AlignRight | Qt.AlignVCenter)
        if projet.masque:
            for colonne in range(4):
                element.setForeground(colonne, Qt.gray)
        return element

    def _selection_changee(self, element, precedent) -> None:
        if element is None:
            return
        cle = element.data(0, ROLE_CLE)
        if cle == self.selection:
            return
        if not self._abandon_accepte():
            self.liste.blockSignals(True)
            self.liste.setCurrentItem(precedent)
            self.liste.blockSignals(False)
            return
        self.selection = cle
        self.charger_projet()

    def ouvrir(self, client: str | None = None, projet: str | None = None) -> None:
        """Affiche la fenêtre, sur le projet demandé s'il est donné (rappel au Stop, onglet Pointer)."""
        if client and projet and (client, projet) != self.selection and self._abandon_accepte():
            self.selection = (client, projet)
            self.modifie = False
            self._date_affichee = None   # autre projet : repartir de la date du jour
        self.recharger()
        self.show()
        self.raise_()
        self.activateWindow()

    # ─── Projet choisi ───────────────────────────────────────────────────────

    def charger_projet(self) -> None:
        self.zone_projet.setEnabled(self.selection is not None)
        if self.selection is None:
            self.titre.setText("Aucun projet : ils apparaissent ici dès qu'ils sont dans la config.")
            self.historique.clear()
            return
        client, projet = self.selection
        self.titre.setText(f"{client} — {projet}")
        self._chargement = True
        self.date.setMaximumDate(QDate(self.horloge().date()))
        self.date.setDate(QDate(self.horloge().date()))
        self._chargement = False
        self._date_affichee = self.date.date().toPython()
        self._charger_note()
        self._remplir_historique()

    def _periode_affichee(self) -> str:
        return periode_de(self.date.date().toPython(), self.mode_periode)

    def _charger_note(self) -> None:
        """Remplit « Travail en cours » (et « Message du … ») pour la période de la date choisie."""
        client, projet = self.selection
        periode = self._periode_affichee()
        note = note_de_periode(self.notes, client, projet, periode)
        etat = etats_actuels(self.notes).get((client, projet))
        statut = settings.STATUT_NOUVELLE_NOTE
        priorite = settings.PRIORITE_DEFAUT
        texte = ""
        if note is not None:
            statut, priorite, texte = note.statut, note.priorite, note.texte
        elif etat is not None:
            statut, priorite = etat.statut, etat.priorite
        self._chargement = True
        self.statut.setCurrentIndex(self.statut.findData(statut))
        self.priorite.setValue(priorite)
        self.texte.setPlainText(texte)
        self._chargement = False
        self.modifie = False
        if self.mode_periode == settings.PERIODE_SEMAINE:
            self.periode.setText(libelle_periode(periode))
        else:
            self.periode.setText("")

        precedente = note_precedente(self.notes, client, projet, periode)
        if precedente is None:
            self.titre_precedent.setText("Message précédent")
            self.texte_precedent.setText("(aucune note avant cette période)")
            return
        self.titre_precedent.setText(f"Message du {precedente.horodatage:%d/%m/%Y}  "
                                     f"({libelle_statut(precedente.statut)}, priorité {precedente.priorite})")
        self.texte_precedent.setText(precedente.texte or "(note vide)")

    def _remplir_historique(self) -> None:
        client, projet = self.selection
        minutes = minutes_par_jour(self.lignes, client, projet)
        self.historique.clear()
        for entree in historique(self.notes, minutes, client, projet):
            temps = ""
            if entree.minutes > 0:
                temps = duree_texte(entree.minutes)
            notes = entree.notes or (None,)
            for numero, note in enumerate(notes):
                colonnes = [libelle_periode(entree.periode), temps, "", ""]
                if numero > 0:
                    colonnes[0], colonnes[1] = "", ""
                if note is not None:
                    prefixe = ""
                    if note.poste:
                        prefixe = f"[{note.poste}] "
                    colonnes[2] = libelle_statut(note.statut)
                    colonnes[3] = prefixe + extrait(note.texte)
                element = QTreeWidgetItem(colonnes)
                if note is not None and note.texte:
                    element.setToolTip(3, note.texte)
                if entree.est_semaine:
                    police = element.font(0)
                    police.setBold(True)
                    element.setFont(0, police)
                self.historique.addTopLevelItem(element)
        for colonne in range(3):
            self.historique.resizeColumnToContents(colonne)

    # ─── Saisie ──────────────────────────────────────────────────────────────

    def _saisie(self, *_) -> None:
        if not self._chargement:
            self.modifie = True

    def _date_changee(self, nouvelle: QDate) -> None:
        if self._chargement or self.selection is None:
            return
        ancienne = self._date_affichee
        meme_periode = ancienne is not None and \
            periode_de(ancienne, self.mode_periode) == periode_de(nouvelle.toPython(), self.mode_periode)
        if meme_periode:
            self._date_affichee = nouvelle.toPython()
            return
        if not self._abandon_accepte():
            self._chargement = True
            self.date.setDate(QDate(ancienne))
            self._chargement = False
            return
        self._date_affichee = nouvelle.toPython()
        self._charger_note()

    def _abandon_accepte(self) -> bool:
        """Vrai s'il n'y a rien à perdre, ou si l'utilisateur accepte d'abandonner sa saisie."""
        if not self.modifie:
            return True
        reponse = QMessageBox.question(self, settings.NOM_APPLICATION,
                                       "La note n'est pas enregistrée. L'abandonner ?")
        return reponse == QMessageBox.Yes

    def enregistrer(self) -> bool:
        """Ajoute la note dans le journal. En cas d'échec, le texte reste dans la fenêtre."""
        if self.selection is None:
            return False
        client, projet = self.selection
        note = nouvelle_note(self.horloge(), self.mode_periode, client, projet, self.statut.currentData(),
                             self.priorite.value(), self.texte.toPlainText(), jour=self.date.date().toPython())
        try:
            self.journal_suivi.ajouter(note)
        except (OSError, ValueError) as erreur:
            QMessageBox.warning(self, settings.NOM_APPLICATION,
                                f"Note non enregistrée : {erreur}\nLe texte reste dans la fenêtre : réessayez.")
            return False
        self.modifie = False
        self.recharger()   # même projet : la date choisie est gardée
        return True

    def closeEvent(self, evenement) -> None:
        if not self._abandon_accepte():
            evenement.ignore()
            return
        self.modifie = False
        evenement.ignore()   # la fenêtre est seulement masquée : elle garde son état
        self.hide()


"""Formulaire Client / Projet / Tâche / Description, commun aux deux onglets et
à la fenêtre « retour d'absence » (CDC « Commun aux deux onglets »)."""

from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QLineEdit, QWidget

from pointeuse.config import Config


def _index_sans_casse(liste: list[str], texte: str) -> int:
    cle = texte.strip().casefold()
    for index, element in enumerate(liste):
        if element.casefold() == cle:
            return index
    return -1


def _etiquette(texte: str, facultatif: bool = False) -> QLabel:
    if facultatif:
        texte += '<br><span style="font-size:8pt">(facultatif)</span>'
    label = QLabel(texte)
    label.setProperty("etiquette", True)
    return label


class FormulaireTache(QWidget):

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.afficher_masques = False

        self.client = QComboBox(editable=True)
        self.projet = QComboBox(editable=True)
        self.tache = QComboBox(editable=True)
        self.description = QLineEdit()
        for liste in (self.client, self.projet, self.tache):
            liste.setInsertPolicy(QComboBox.NoInsert)   # l'ajout passe par Config.ajouter
            liste.lineEdit().setClearButtonEnabled(False)
        self.tache.lineEdit().setPlaceholderText("—")

        disposition = QFormLayout(self)
        disposition.setContentsMargins(0, 0, 0, 0)
        disposition.setHorizontalSpacing(14)
        disposition.addRow(_etiquette("Client"), self.client)
        disposition.addRow(_etiquette("Projet"), self.projet)
        disposition.addRow(_etiquette("Tâche", facultatif=True), self.tache)
        disposition.addRow(_etiquette("Description", facultatif=True), self.description)

        self.client.currentTextChanged.connect(self._remplir_projets)
        self.projet.currentTextChanged.connect(self._remplir_taches)
        self.recharger()

    # ─── Lecture / écriture ──────────────────────────────────────────────────

    def valeurs(self) -> tuple[str, str, str | None, str]:
        """(client, projet, tâche ou None, description), espaces retirés."""
        tache = self.tache.currentText().strip()
        if not tache:
            tache = None
        return (self.client.currentText().strip(), self.projet.currentText().strip(),
                tache, self.description.text().strip())

    def remplir(self, client: str, projet: str, tache: str = "", description: str = "") -> None:
        self.client.setCurrentText(client)
        self.projet.setCurrentText(projet)
        self.tache.setCurrentText(tache)
        self.description.setText(description)

    def recharger(self) -> None:
        """Relit les listes depuis la config, sans perdre ce qui est saisi."""
        client = self.client.currentText()
        self._remplacer_elements(self.client, self.config.clients(self.afficher_masques), client)
        self._remplir_projets()

    def changer_affichage_masques(self, afficher: bool) -> None:
        self.afficher_masques = afficher
        self.recharger()

    # ─── Listes dépendantes ──────────────────────────────────────────────────

    def _remplir_projets(self, *_) -> None:
        """La liste Projet ne montre que les projets du client choisi.

        Le projet affiché est gardé s'il appartient au client, même masqué : on peut
        pointer exceptionnellement sur un projet masqué sans qu'il réapparaisse dans la liste.
        """
        client = self.client.currentText()
        ancien = self.projet.currentText()
        projets = self.config.projets(client, self.afficher_masques)
        tous = self.config.projets(client, inclure_masques=True)
        if _index_sans_casse(tous, ancien) < 0 and projets:
            ancien = projets[0]   # projet d'un autre client : on propose le premier de celui-ci
        self._remplacer_elements(self.projet, projets, ancien)
        self._remplir_taches()

    def _remplir_taches(self, *_) -> None:
        """Tâches du projet, puis tâches communes sous un séparateur."""
        ancienne = self.tache.currentText()
        du_projet = self.config.taches_projet(self.client.currentText(), self.projet.currentText())
        communes = []
        for tache in self.config.taches_communes():
            if _index_sans_casse(du_projet, tache) < 0:
                communes.append(tache)
        if _index_sans_casse(du_projet + communes, ancienne) < 0:
            ancienne = ""
        self.tache.blockSignals(True)
        self.tache.clear()
        self.tache.addItems(du_projet)
        if du_projet and communes:
            self.tache.insertSeparator(len(du_projet))
        self.tache.addItems(communes)
        self.tache.setCurrentText(ancienne)
        self.tache.blockSignals(False)

    @staticmethod
    def _remplacer_elements(liste: QComboBox, elements: list[str], texte: str) -> None:
        liste.blockSignals(True)
        liste.clear()
        liste.addItems(elements)
        index = _index_sans_casse(elements, texte)
        if index >= 0:
            liste.setCurrentIndex(index)
        else:
            liste.setCurrentText(texte)
        liste.blockSignals(False)

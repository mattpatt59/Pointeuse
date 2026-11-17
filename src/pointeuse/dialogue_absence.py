"""Fenêtre « retour d'absence » : après un plantage (et à l'étape 6, après une veille)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QRadioButton, QVBoxLayout)

from pointeuse import settings
from pointeuse.affichage import libelle_tache, texte_absence
from pointeuse.config import Config
from pointeuse.formulaire import FormulaireTache
from pointeuse.moteur import Absence


class DialogueAbsence(QDialog):
    """Résultat lu après exec() : travail (bool), valeurs() du formulaire, reprendre (bool).

    Fermer la fenêtre sans valider revient à répondre « Pause » : rien n'est perdu,
    la plage peut être corrigée ensuite avec « Insérer ».
    """

    def __init__(self, config: Config, absence: Absence, parent=None):
        super().__init__(parent, Qt.WindowStaysOnTopHint)
        self.setWindowTitle(f"{settings.NOM_APPLICATION} — retour d'absence")
        self.setMinimumWidth(settings.LARGEUR_PANNEAU_PX + 40)

        message = QLabel(texte_absence(absence.debut, absence.fin), objectName="alerte")
        self.choix_pause = QRadioButton("Pause", checked=True)
        self.choix_travail = QRadioButton("J'ai travaillé sur…")
        self.formulaire = FormulaireTache(config)
        self.formulaire.setEnabled(False)
        self.choix_travail.toggled.connect(self.formulaire.setEnabled)

        precedente = absence.tache_precedente
        self.case_reprendre = QCheckBox()
        if precedente is None:
            self.case_reprendre.hide()
        elif precedente.est_pause:
            self.case_reprendre.setText("Rester en pause ensuite")
            self.case_reprendre.setChecked(True)
        else:
            self.case_reprendre.setText("Reprendre ensuite : "
                                        + libelle_tache(precedente.client, precedente.projet, precedente.tache))
            self.case_reprendre.setChecked(True)
            self.formulaire.remplir(precedente.client, precedente.projet, precedente.tache)

        valider = QPushButton("Valider", objectName="primaire")
        valider.clicked.connect(self._valider)
        bas = QHBoxLayout()
        bas.addStretch()
        bas.addWidget(valider)

        disposition = QVBoxLayout(self)
        disposition.setContentsMargins(16, 16, 16, 16)
        disposition.setSpacing(10)
        disposition.addWidget(message)
        disposition.addWidget(self.choix_pause)
        disposition.addWidget(self.choix_travail)
        disposition.addWidget(self.formulaire)
        disposition.addWidget(self.case_reprendre)
        disposition.addLayout(bas)

    @property
    def travail(self) -> bool:
        return self.result() == QDialog.Accepted and self.choix_travail.isChecked()

    @property
    def reprendre(self) -> bool:
        # isHidden() et non isVisible() : la fenêtre est déjà fermée quand on lit le résultat.
        return not self.case_reprendre.isHidden() and self.case_reprendre.isChecked()

    def _valider(self) -> None:
        if self.choix_travail.isChecked():
            client, projet, _, _ = self.formulaire.valeurs()
            if not client or not projet:
                QMessageBox.warning(self, settings.NOM_APPLICATION, "Le client et le projet sont obligatoires.")
                return
        self.accept()

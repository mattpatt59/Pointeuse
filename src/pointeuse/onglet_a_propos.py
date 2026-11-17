"""Onglet « À propos » : version, code source (dépôt GitHub), licences, société."""

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from pointeuse import __version__, settings
from pointeuse.bilan import DOSSIER_LECTEUR

FICHIER_LOGO = DOSSIER_LECTEUR / "logo.png"   # logo T-Elec déjà livré avec le lecteur de bilan


def lien(url: str, texte: str = "") -> str:
    if not texte:
        texte = url.removeprefix("https://").rstrip("/")
    return f'<a href="{escape(url)}" style="color:{settings.COULEUR_VERT_PROFOND}">{escape(texte)}</a>'


def texte_application() -> str:
    return (f"<b>{settings.NOM_APPLICATION}</b> — version {__version__}<br>"
            "Pointage du temps par client, projet et tâche, depuis la zone de notification. "
            f"Les données restent sur ce poste (fichiers <code>{settings.NOM_FICHIER_CSV}</code> "
            f"et <code>{settings.NOM_FICHIER_CONFIG}</code>) : rien n'est envoyé.")


def texte_source() -> str:
    return (f"<b>Code source</b><br>{lien(settings.URL_DEPOT)}<br>"
            f"Licence {settings.LICENCE_APPLICATION}. Interface Qt / PySide6 sous licence LGPL v3 : "
            "voir le dossier <code>licences/</code> livré avec l'appli.")


def texte_societe() -> str:
    return (f"<b>{settings.NOM_SOCIETE}</b><br>{escape(settings.PRESENTATION_SOCIETE)}<br>"
            f"{lien(settings.URL_SITE_SOCIETE)}")


class OngletAPropos(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logo = QLabel(alignment=Qt.AlignCenter)
        image = QPixmap(str(FICHIER_LOGO))
        if not image.isNull():
            self.logo.setPixmap(image.scaledToHeight(settings.HAUTEUR_LOGO_A_PROPOS_PX, Qt.SmoothTransformation))
        else:
            self.logo.hide()

        self.blocs = []
        for texte in (texte_application(), texte_source(), texte_societe()):
            bloc = QLabel(texte, objectName="a_propos", wordWrap=True, textFormat=Qt.RichText)
            bloc.setOpenExternalLinks(True)   # ouvre le lien dans le navigateur
            bloc.setTextInteractionFlags(Qt.TextBrowserInteraction)
            self.blocs.append(bloc)

        disposition = QVBoxLayout(self)
        disposition.setContentsMargins(16, 16, 16, 16)
        disposition.setSpacing(14)
        disposition.addWidget(self.logo)
        for bloc in self.blocs:
            disposition.addWidget(bloc)
        disposition.addStretch()

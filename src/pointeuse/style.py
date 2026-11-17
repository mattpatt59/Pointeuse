"""Feuille de style Qt, d'après la charte T-Elec (couleurs dans settings.py)."""

import tempfile
from pathlib import Path

from pointeuse import settings as s

# Chevron « ⌄ » des listes déroulantes. Qt ne dessine plus sa flèche dès que la zone
# ::drop-down est personnalisée : il faut lui donner une image, par un chemin de fichier
# (pas d'image en ligne dans une feuille de style Qt).
_CHEVRON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="12" height="8" viewBox="0 0 12 8">
<path d="M1 1.5 L6 6.5 L11 1.5" fill="none" stroke="{couleur}" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round"/></svg>"""


def _image_chevron(couleur: str) -> str:
    """Écrit le chevron dans le dossier temporaire et retourne son chemin, au format attendu par Qt."""
    dossier = Path(tempfile.gettempdir()) / s.DOSSIER_TEMP_STYLE
    dossier.mkdir(exist_ok=True)
    chemin = dossier / f"chevron_{couleur.lstrip('#')}.svg"
    chemin.write_text(_CHEVRON_SVG.format(couleur=couleur), encoding="utf-8")
    return chemin.as_posix()


def feuille_de_style() -> str:
    chevron = _image_chevron(s.COULEUR_VERT_PROFOND)
    chevron_survol = _image_chevron(s.COULEUR_VERT_FONCE)
    return f"""
    QWidget {{ font-family: "{s.POLICE}"; font-size: {s.TAILLE_POLICE_PT}pt; color: {s.COULEUR_NOIR}; }}
    QWidget#panneau, QDialog {{ background: {s.COULEUR_BLANC}; }}

    QLabel#entete {{
        color: {s.COULEUR_BLANC}; font-weight: bold; font-size: {s.TAILLE_POLICE_PT + 2}pt;
        padding: 10px 14px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {s.COULEUR_VERT_PROFOND}, stop:0.55 {s.COULEUR_VERT_FONCE}, stop:1 {s.COULEUR_VERT});
    }}

    QTabWidget::pane {{ border: none; border-top: 1px solid {s.COULEUR_BORDURE}; }}
    QTabBar::tab {{ padding: 8px 16px; color: {s.COULEUR_GRIS}; font-weight: bold;
                    border: none; border-bottom: 3px solid transparent; background: transparent; }}
    QTabBar::tab:selected {{ color: {s.COULEUR_VERT_PROFOND}; border-bottom: 3px solid {s.COULEUR_VERT_FONCE}; }}

    QFrame#statut {{ background: {s.COULEUR_VERT_CLAIR}; border-left: 4px solid {s.COULEUR_VERT_FONCE};
                     padding: 4px 6px; border-radius: 4px; }}
    QFrame#statut QLabel {{ background: transparent; }}
    QFrame#statut[pause="true"] {{ background: #f5f5f5; border-left-color: {s.COULEUR_GRIS}; }}
    QLabel#chrono {{ font-family: monospace; font-size: {s.TAILLE_POLICE_PT + 3}pt; color: {s.COULEUR_VERT_PROFOND};
                     background: transparent; }}
    QLabel#alerte {{ background: {s.COULEUR_ORANGE_CLAIR}; border-left: 4px solid {s.COULEUR_ORANGE};
                     padding: 8px 12px; border-radius: 4px; }}
    QLabel[etiquette="true"] {{ color: {s.COULEUR_GRIS}; }}

    QComboBox, QLineEdit, QDateEdit, QTimeEdit {{ border: 1px solid {s.COULEUR_BORDURE}; border-radius: 6px;
                            padding: 5px 8px; background: {s.COULEUR_BLANC}; min-height: 20px; }}
    QComboBox, QDateEdit {{ padding-right: {s.LARGEUR_FLECHE_LISTE_PX + 4}px; }}
    /* Heures : saisie au clavier ou à la molette, sans les petites flèches.
       (setButtonSymbols(NoButtons) réduit le texte à 1 px avec une feuille de style.) */
    QTimeEdit::up-button, QTimeEdit::down-button {{ width: 0px; border: none; }}
    QComboBox:focus, QLineEdit:focus, QDateEdit:focus, QTimeEdit:focus {{ border-color: {s.COULEUR_VERT_FONCE}; }}
    QComboBox:hover {{ border-color: {s.COULEUR_VERT}; }}

    /* Zone de la flèche : bien visible, comme un <select> web */
    QComboBox::drop-down, QDateEdit::drop-down {{
        subcontrol-origin: padding; subcontrol-position: center right;
        width: {s.LARGEUR_FLECHE_LISTE_PX}px; border: none;
        border-left: 1px solid {s.COULEUR_BORDURE};
        border-top-right-radius: 6px; border-bottom-right-radius: 6px;
        background: {s.COULEUR_VERT_CLAIR};
    }}
    QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url("{chevron}"); width: 12px; height: 8px; }}
    QComboBox::down-arrow:hover, QComboBox::down-arrow:on, QDateEdit::down-arrow:hover {{ image: url("{chevron_survol}"); }}

    /* Liste dépliée */
    QComboBox QAbstractItemView {{
        border: 1px solid {s.COULEUR_VERT_FONCE}; background: {s.COULEUR_BLANC}; outline: none;
        selection-background-color: {s.COULEUR_VERT_CLAIR}; selection-color: {s.COULEUR_VERT_PROFOND};
    }}

    QPushButton {{ border: none; border-radius: 6px; padding: 9px 14px; font-weight: bold;
                   color: {s.COULEUR_BLANC}; background: {s.COULEUR_BOUTON_SECONDAIRE}; }}
    QPushButton#primaire {{ background: {s.COULEUR_VERT}; }}
    QPushButton#primaire:hover {{ background: {s.COULEUR_VERT_FONCE}; }}
    QPushButton#pause {{ background: {s.COULEUR_ORANGE}; }}
    QPushButton#reprendre {{ background: {s.COULEUR_VERT_FONCE}; }}
    QPushButton#stop {{ background: {s.COULEUR_BOUTON_SUPPRIMER}; }}
    /* Boutons rapides [[raccourcis]] : discrets, vert clair (charte §E Tags) */
    QPushButton#raccourci {{ background: {s.COULEUR_VERT_CLAIR}; color: {s.COULEUR_VERT_PROFOND};
                             border: 1px solid {s.COULEUR_VERT_FONCE}; padding: 7px 14px; text-align: left; }}
    QPushButton#raccourci:hover {{ background: {s.COULEUR_VERT}; color: {s.COULEUR_BLANC}; }}
    QLabel#titre_raccourcis {{ color: {s.COULEUR_VERT_PROFOND}; font-weight: bold; padding-top: 6px;
                               border-top: 1px solid {s.COULEUR_BORDURE}; }}
    QPushButton:disabled {{ background: {s.COULEUR_BORDURE}; color: {s.COULEUR_GRIS}; border: none; }}

    /* Tâche lancée sans projet (bouton rapide « client seul ») : projet à compléter */
    QComboBox[a_completer="true"] {{ border: 2px solid {s.COULEUR_ROUGE}; background: {s.COULEUR_ROUGE_CLAIR}; }}

    QCheckBox, QRadioButton {{ color: {s.COULEUR_GRIS}; }}

    /* Onglet « Insérer / Journée » : tableau selon la charte (§E Tables) */
    QLabel#titre_journee {{ color: {s.COULEUR_VERT_PROFOND}; font-weight: bold; padding-top: 6px;
                            border-top: 1px solid {s.COULEUR_BORDURE}; }}
    QTreeWidget {{ border: 1px solid {s.COULEUR_BORDURE_TABLE}; border-radius: 6px; }}
    QHeaderView::section {{ background: {s.COULEUR_ENTETE_TABLE}; color: {s.COULEUR_VERT_PROFOND};
                            font-weight: bold; border: none; padding: 4px 6px; }}
    QLabel#a_propos {{ color: {s.COULEUR_NOIR}; padding-top: 10px; border-top: 1px solid {s.COULEUR_BORDURE}; }}
    QLabel#totaux {{ font-weight: bold; color: {s.COULEUR_VERT_PROFOND}; }}
    QRadioButton {{ font-weight: bold; color: {s.COULEUR_NOIR}; }}
    """

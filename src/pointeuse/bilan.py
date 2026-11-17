"""Bilan dans le navigateur (menu de l'icône « Bilan », ADR 003).

Le lecteur HTML/JS (dossier lecteur/, hors ligne) est copié
dans <dossier du programme>/bilan/, avec le CSV converti en script :
pointeuse_donnees_tmp.js → window.POINTEUSE_CSV = {version, nom, texte}.
Une page ouverte en file:// ne peut pas lire un fichier par elle-même, mais peut charger
un <script> voisin : c'est ce qui fait passer les données, sans réseau.
"""

import json
import shutil
from pathlib import Path

from pointeuse import settings

DOSSIER_LECTEUR = Path(__file__).resolve().parent / "lecteur"
FICHIERS_LECTEUR = ("pointeuse.css", "fusion.js", "pointeuse.js", "logo.png")


class CsvAbsent(Exception):
    """Le CSV n'existe pas encore (aucune tâche terminée)."""


def script_donnees(nom: str, texte: str) -> str:
    """Contenu de pointeuse_donnees_tmp.js. json.dumps échappe tout (guillemets, retours,
    U+2028…) : le texte du CSV ne peut pas sortir de la chaîne."""
    donnees = {"version": settings.VERSION_DONNEES_BILAN, "nom": nom, "texte": texte}
    return ("// Généré par la Pointeuse (menu « Bilan ») — copie du CSV, réécrite à chaque ouverture.\n"
            f"window.POINTEUSE_CSV = {json.dumps(donnees, ensure_ascii=True)};\n")


def preparer_bilan(chemin_csv: Path, dossier_programme: Path) -> Path:
    """Écrit le dossier bilan/ et renvoie le chemin de sa page index.html.

    Lève CsvAbsent si le CSV n'existe pas, OSError si l'écriture échoue."""
    if not chemin_csv.exists():
        raise CsvAbsent(chemin_csv)
    texte = chemin_csv.read_text(encoding="utf-8-sig", errors="replace")

    dossier = dossier_programme / settings.NOM_DOSSIER_BILAN
    dossier.mkdir(parents=True, exist_ok=True)
    for nom in FICHIERS_LECTEUR:
        shutil.copyfile(DOSSIER_LECTEUR / nom, dossier / nom)
    (dossier / settings.NOM_FICHIER_DONNEES_BILAN).write_text(
        script_donnees(chemin_csv.name, texte), encoding="utf-8")

    page = (DOSSIER_LECTEUR / "index.html").read_text(encoding="utf-8")
    balise = f'<script src="{settings.NOM_FICHIER_DONNEES_BILAN}"></script>'
    page = page.replace(settings.MARQUEUR_DONNEES_BILAN, balise)
    chemin_page = dossier / "index.html"
    chemin_page.write_text(page, encoding="utf-8")
    return chemin_page

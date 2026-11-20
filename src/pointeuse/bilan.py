"""Bilan dans le navigateur (menu de l'icône « Bilan », ADR 003).

Le lecteur HTML/JS (dossier lecteur/, hors ligne) est copié
dans <dossier du programme>/bilan/, avec le CSV converti en script :
pointeuse_donnees_tmp.js → window.POINTEUSE_CSV = {version, nom, texte, suivi}, où suivi
vaut {nom, texte} (contenu brut du pointeuse_suivi.jsonl, lu par lecteur/suivi.js, ADR 004)
ou null s'il n'y a pas encore de note.
Une page ouverte en file:// ne peut pas lire un fichier par elle-même, mais peut charger
un <script> voisin : c'est ce qui fait passer les données, sans réseau.
"""

import json
import shutil
import time
from pathlib import Path

from pointeuse import settings

DOSSIER_LECTEUR = Path(__file__).resolve().parent / "lecteur"
FICHIERS_LECTEUR = ("pointeuse.css", "fusion.js", "suivi.js", "pointeuse.js", "logo.png")


class CsvAbsent(Exception):
    """Le CSV n'existe pas encore (aucune tâche terminée)."""


def script_donnees(nom: str, texte: str, suivi: tuple[str, str] | None = None) -> str:
    """Contenu de pointeuse_donnees_tmp.js. json.dumps échappe tout (guillemets, retours,
    U+2028…) : le texte du CSV ne peut pas sortir de la chaîne. suivi = (nom, texte) du jsonl."""
    donnees_suivi = None
    if suivi is not None:
        donnees_suivi = {"nom": suivi[0], "texte": suivi[1]}
    donnees = {"version": settings.VERSION_DONNEES_BILAN, "nom": nom, "texte": texte, "suivi": donnees_suivi}
    return ("// Généré par la Pointeuse (menu « Bilan ») — copie du CSV, réécrite à chaque ouverture.\n"
            f"window.POINTEUSE_CSV = {json.dumps(donnees, ensure_ascii=True)};\n")


def preparer_bilan(chemin_csv: Path, dossier_programme: Path, chemin_suivi: Path | None = None) -> Path:
    """Écrit le dossier bilan/ et renvoie le chemin de sa page index.html.

    chemin_suivi : pointeuse_suivi.jsonl, transmis brut s'il existe (les règles de lecture sont
    appliquées par la page : lignes abîmées signalées là-bas, pas ici).
    Lève CsvAbsent si le CSV n'existe pas, OSError si l'écriture échoue."""
    if not chemin_csv.exists():
        raise CsvAbsent(chemin_csv)
    texte = chemin_csv.read_text(encoding="utf-8-sig", errors="replace")
    suivi = None
    if chemin_suivi is not None and chemin_suivi.exists():
        # errors="replace" : un octet illisible devient U+FFFD, que la page signale (« encodage illisible »).
        suivi = (chemin_suivi.name, chemin_suivi.read_text(encoding="utf-8-sig", errors="replace"))

    dossier = dossier_programme / settings.NOM_DOSSIER_BILAN
    dossier.mkdir(parents=True, exist_ok=True)
    for nom in FICHIERS_LECTEUR:
        shutil.copyfile(DOSSIER_LECTEUR / nom, dossier / nom)
    (dossier / settings.NOM_FICHIER_DONNEES_BILAN).write_text(
        script_donnees(chemin_csv.name, texte, suivi), encoding="utf-8")

    page = (DOSSIER_LECTEUR / "index.html").read_text(encoding="utf-8")
    balise = f'<script src="{settings.NOM_FICHIER_DONNEES_BILAN}"></script>'
    page = page.replace(settings.MARQUEUR_DONNEES_BILAN, balise)
    # « ?v=… » change à chaque clic sur « Bilan » : le navigateur ne peut pas resservir de son cache
    # des données ou un script d'une génération précédente (vu sous Firefox : ancienne priorité affichée).
    jeton = time.time_ns()
    for nom in (*FICHIERS_LECTEUR, settings.NOM_FICHIER_DONNEES_BILAN):
        if nom.endswith((".js", ".css")):
            page = page.replace(f'"{nom}"', f'"{nom}?v={jeton}"')
    chemin_page = dossier / "index.html"
    chemin_page.write_text(page, encoding="utf-8")
    return chemin_page

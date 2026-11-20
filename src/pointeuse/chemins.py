"""Emplacement des fichiers de l'application (CDC multi_postes.md, ADR 005).

- Dossier du logiciel : celui de l'exécutable PyInstaller (sys.executable ; en mode
  « onefile », __file__ pointe vers un dossier temporaire : ne pas l'utiliser), ou la
  racine du dépôt en développement (python -m pointeuse). Il contient le verrou.
- data/ : données de travail de ce poste (config, CSV, journaux), toujours en local.
- Dossier de sauvegarde (facultatif) : copie de data/ ; son nom est le nom du poste.
- Dossier externe : lu par le bilan, un sous-dossier par PC (les sauvegardes des autres postes).
"""

import os
import sys
from pathlib import Path

from pointeuse import settings


class DossierNonInscriptible(Exception):
    """Le dossier des données n'est pas accessible en écriture."""


def est_executable() -> bool:
    """Vrai si l'appli tourne depuis un exécutable PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def dossier_logiciel() -> Path:
    """Dossier de l'exécutable, ou racine du dépôt en développement."""
    if est_executable():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def dossier_donnees(logiciel: Path | None = None) -> Path:
    """data/ : où sont lus et écrits les fichiers de travail de ce poste."""
    if logiciel is None:
        logiciel = dossier_logiciel()
    return logiciel / settings.NOM_DOSSIER_DONNEES


def _chemin_reglage(reglage: str, logiciel: Path | None) -> Path:
    """Chemin d'un réglage de [donnees] : absolu, ou relatif au dossier du logiciel."""
    chemin = Path(reglage.strip()).expanduser()
    if chemin.is_absolute():
        return chemin
    if logiciel is None:
        logiciel = dossier_logiciel()
    return logiciel / chemin


def dossier_sauvegarde(reglage: str, logiciel: Path | None = None) -> Path | None:
    """[donnees] dossier_de_sauvegarde : où data/ est recopié, None si vide (pas de sauvegarde).
    Le nom de ce dossier est le nom du poste dans le bilan des autres PC."""
    if not reglage.strip():
        return None
    return _chemin_reglage(reglage, logiciel)


def dossier_externe(reglage: str, logiciel: Path | None = None) -> Path:
    """[donnees] dossier_externe : lu par le bilan, un sous-dossier par PC. Vide : data_extern."""
    if not reglage.strip():
        reglage = settings.DONNEES_DEFAUT["dossier_externe"]
    return _chemin_reglage(reglage, logiciel)


def verifier_inscriptible(dossier: Path) -> None:
    """Lève DossierNonInscriptible si on ne peut pas écrire dans le dossier."""
    try:
        dossier.mkdir(parents=True, exist_ok=True)
    except OSError as erreur:
        raise DossierNonInscriptible(f"Impossible de créer « {dossier} » : {erreur}") from erreur
    if not os.access(dossier, os.W_OK):
        raise DossierNonInscriptible(
            f"Impossible d'écrire dans « {dossier} ». "
            "Déplacez le programme dans un dossier personnel (ex. Documents ou C:\\pointeuse)."
        )


def chemin_config(dossier: Path) -> Path:
    return dossier / settings.NOM_FICHIER_CONFIG

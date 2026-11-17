"""Emplacement des fichiers de l'application.

Les fichiers (config, CSV, sauvegarde) sont créés dans le dossier du programme :
- exécutable PyInstaller : dossier qui contient l'exécutable (sys.executable).
  En mode « onefile », __file__ pointe vers un dossier temporaire : ne pas l'utiliser.
- développement (python -m pointeuse) : dossier data/ à la racine du dépôt.
"""

import os
import sys
from pathlib import Path

from pointeuse import settings


class DossierNonInscriptible(Exception):
    """Le dossier du programme n'est pas accessible en écriture."""


def est_executable() -> bool:
    """Vrai si l'appli tourne depuis un exécutable PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def dossier_programme() -> Path:
    """Dossier où sont lus et écrits les fichiers de l'application."""
    if est_executable():
        return Path(sys.executable).resolve().parent
    racine_depot = Path(__file__).resolve().parents[2]
    return racine_depot / settings.DOSSIER_DATA_DEV


def verifier_inscriptible(dossier: Path) -> None:
    """Lève DossierNonInscriptible si on ne peut pas écrire dans le dossier."""
    dossier.mkdir(parents=True, exist_ok=True)
    if not os.access(dossier, os.W_OK):
        raise DossierNonInscriptible(
            f"Impossible d'écrire dans « {dossier} ». "
            "Déplacez le programme dans un dossier personnel (ex. Documents ou C:\\pointeuse)."
        )


def chemin_config(dossier: Path) -> Path:
    return dossier / settings.NOM_FICHIER_CONFIG

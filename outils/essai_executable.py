# Nom : essai_executable.py
# Usage : python outils/essai_executable.py — après outils/construire.py.
#         Lance l'exécutable hors écran 5 s : il doit tenir et créer sa config à côté de lui.
#         Utilisé par GitHub Actions ; marche aussi en local.
# Date : 2026-11-17
"""Essai de fumée de l'exécutable construit (CDC étape 7)."""

import os
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

from pointeuse import settings  # noqa: E402

DUREE_ESSAI_S = 5
FICHIERS_CREES = [settings.NOM_FICHIER_CONFIG, settings.NOM_FICHIER_EN_COURS, settings.NOM_FICHIER_VERROU,
                  settings.NOM_FICHIER_CSV]


def main() -> int:
    dossier = RACINE / "dist" / settings.NOM_APPLICATION
    nom = settings.NOM_APPLICATION
    if sys.platform == "win32":
        nom += ".exe"
    executable = dossier / nom
    if not executable.exists():
        print(f"Introuvable : {executable}")
        return 1

    environnement = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    processus = subprocess.Popen([str(executable)], cwd=dossier, env=environnement)
    time.sleep(DUREE_ESSAI_S)
    code = processus.poll()
    if code is None:
        processus.kill()
        processus.wait()
    config_creee = (dossier / settings.NOM_FICHIER_CONFIG).exists()
    for nom_fichier in FICHIERS_CREES:   # ne pas laisser de données d'essai dans dist/
        (dossier / nom_fichier).unlink(missing_ok=True)

    if code is not None:
        print(f"L'exécutable s'est arrêté au bout de moins de {DUREE_ESSAI_S} s (code {code}).")
        return 1
    if not config_creee:
        print(f"{settings.NOM_FICHIER_CONFIG} n'a pas été créé à côté de l'exécutable.")
        return 1
    print(f"OK : l'exécutable tourne et a créé {settings.NOM_FICHIER_CONFIG}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

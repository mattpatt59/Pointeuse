# Nom : construire.py
# Usage : .venv/bin/python outils/construire.py  (Windows : .venv\Scripts\python outils\construire.py)
#         Construit l'exécutable portable de l'OS courant (PyInstaller, mode dossier)
#         et l'archive dist/Pointeuse-<version>-<os>.zip. Même commande en local et dans GitHub Actions.
# Date : 2026-11-17
"""Construction de l'exécutable portable (CDC étape 7, ADR 002).

Mode « dossier » (onedir) et non « fichier unique » : démarrage immédiat (rien à
décompresser à chaque lancement) et bibliothèques Qt remplaçables, comme le demande
la LGPL v3 de PySide6 / Qt.
"""

import os
import platform
import shutil
import sys
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

from pointeuse import settings  # noqa: E402

DIST = RACINE / "dist"
TRAVAIL = RACINE / "build"
NOM = settings.NOM_APPLICATION
FICHIERS_LIVRES = [   # copiés à côté de l'exécutable
    (RACINE / "LICENSE", "LICENSE.txt"),
    (RACINE / "licences" / "LICENCES_TIERS.md", "LICENCES_TIERS.md"),
    (RACINE / "licences" / "LGPL-3.0.txt", "licences/LGPL-3.0.txt"),
    (RACINE / "licences" / "GPL-3.0.txt", "licences/GPL-3.0.txt"),
    (RACINE / "docs" / "exemples" / "pointeuse_config.toml", "pointeuse_config.exemple.toml"),
]
# Modules Qt jamais utilisés : allège l'archive si PySide6 « complet » est installé (poste de dev).
MODULES_EXCLUS = ["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml",
                  "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtPdf",
                  "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtNetwork", "tkinter"]


def version() -> str:
    with open(RACINE / "pyproject.toml", "rb") as fichier:
        return tomllib.load(fichier)["project"]["version"]


def nom_os() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return sys.platform


def generer_icone() -> Path:
    """Icône de l'exécutable : la même horloge verte que dans la zone de notification."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    from pointeuse.icone import icone_horloge

    application = QGuiApplication.instance() or QGuiApplication([])
    chemin = TRAVAIL / "pointeuse.ico"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    image = icone_horloge(settings.COULEUR_VERT_FONCE).pixmap(256, 256)
    if not image.save(str(chemin), "ICO"):
        raise SystemExit("Impossible de générer l'icône (greffon Qt « ico » absent ?)")
    del application
    return chemin


def construire() -> Path:
    import PyInstaller.__main__

    arguments = [
        str(RACINE / "src" / "pointeuse" / "__main__.py"),
        "--name", NOM,
        "--onedir", "--windowed", "--noconfirm", "--clean",
        "--paths", str(RACINE / "src"),
        "--icon", str(generer_icone()),
        "--distpath", str(DIST),
        "--workpath", str(TRAVAIL / "pyinstaller"),
        "--specpath", str(TRAVAIL),
    ]
    for module in MODULES_EXCLUS:
        arguments += ["--exclude-module", module]
    PyInstaller.__main__.run(arguments)

    dossier = DIST / NOM
    for source, destination in FICHIERS_LIVRES:
        cible = dossier / destination
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, cible)
    return dossier


def archiver(dossier: Path) -> Path:
    base = DIST / f"{NOM}-{version()}-{nom_os()}-{platform.machine().lower()}"
    archive = shutil.make_archive(str(base), "zip", root_dir=DIST, base_dir=dossier.name)
    return Path(archive)


def main() -> None:
    dossier = construire()
    archive = archiver(dossier)
    print(f"Exécutable : {dossier}")
    print(f"Archive    : {archive}")


if __name__ == "__main__":
    main()

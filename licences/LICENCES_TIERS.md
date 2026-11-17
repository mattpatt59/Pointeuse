# Licences des composants tiers

La Pointeuse est sous licence MIT (`LICENSE.txt`). L'exécutable distribué contient
aussi les composants suivants, chacun sous sa propre licence.

| Composant | Rôle | Licence | Source |
|-----------|------|---------|--------|
| Qt 6 | Interface graphique | LGPL v3 | https://www.qt.io/download-open-source — code source : https://code.qt.io |
| PySide6 / shiboken6 | Liaison Python ↔ Qt | LGPL v3 | https://code.qt.io/cgit/pyside/pyside-setup.git |
| tomlkit | Lecture / écriture de la config | MIT | https://github.com/python-poetry/tomlkit |
| Python | Interpréteur embarqué | PSF License | https://www.python.org/ |
| PyInstaller (chargeur) | Lancement de l'exécutable | GPL v2 avec exception pour les programmes livrés | https://pyinstaller.org/ |

## Qt et PySide6 — LGPL v3

Texte de la licence : `licences/LGPL-3.0.txt` (elle complète la GPL v3, `licences/GPL-3.0.txt`).

Qt et PySide6 sont utilisés sans modification. Ils sont livrés sous forme de
bibliothèques séparées, dans le sous-dossier `_internal/` (`_internal/PySide6/`,
`_internal/shiboken6/`). Vous pouvez les remplacer par une autre version compatible
(par exemple recompilée à partir du code source indiqué ci-dessus) : la Pointeuse
utilisera les fichiers présents dans ce dossier au prochain lancement.

Le code source de la Pointeuse est libre (licence MIT) : https://github.com/mattpatt59/Pointeuse

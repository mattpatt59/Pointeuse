# ADR — Exécutable portable, licence LGPL et construction GitHub Actions

**Date :** 2026-11-17
**Statut :** PROPOSÉ

---

## Contexte

La pointeuse doit être livrée en exécutable portable, un par OS (Windows 10/11, Linux),
sans installateur : les fichiers (CSV, config) sont créés à côté de l'exécutable (CDC,
« Emplacement »). Elle embarque PySide6 / Qt, sous **LGPL v3** : la licence impose que
l'utilisateur puisse remplacer les bibliothèques Qt par une autre version, et que le texte
de la licence soit fourni.

Les deux exécutables doivent être construits sans dépendre d'un poste Windows : MP
demande que la construction passe par GitHub Actions.

---

## Options envisagées

| Option | Avantages | Inconvénients |
|--------|-----------|---------------|
| PyInstaller « onefile » (un seul `.exe`) | Un seul fichier à poser | Décompression dans un dossier temporaire à chaque lancement (2–5 s, antivirus plus méfiants) ; bibliothèques Qt enfermées dans l'exécutable → remplacement LGPL difficile à démontrer |
| **PyInstaller « onedir » (dossier zippé)** | Lancement immédiat ; Qt livré en fichiers séparés dans `_internal/`, remplaçables (LGPL) ; même commande en local et en CI | Un dossier au lieu d'un fichier ; ~100 Mo zippé |
| Nuitka | Exécutable plus rapide | Compilation C longue, chaîne d'outils plus lourde en CI, sans gain utile ici |

Construction :

| Option | Avantages | Inconvénients |
|--------|-----------|---------------|
| **GitHub Actions, un job par OS** | Windows construit sans poste Windows ; tests lancés sur les deux OS ; archives attachées aux releases | Dépôt sur GitHub, minutes Actions |
| Construction locale sur chaque OS | Aucun service externe | Il faut un poste Windows à chaque version |

---

## Décision

**Choix : PyInstaller « onedir » + GitHub Actions**

Raisons :
- « onedir » respecte la LGPL sans effort : `_internal/PySide6/` et `_internal/shiboken6/`
  sont des fichiers séparés, remplaçables. Le dossier reste portable : on dézippe
  `Pointeuse/` où l'on veut (`Documents/`, `C:\pointeuse\`) et les fichiers de données sont
  créés à côté de `Pointeuse.exe` ;
- `outils/construire.py` est la seule commande de construction, en local comme en CI ;
- dépendance `PySide6-Essentials` plutôt que `PySide6` (complet) : seuls QtCore / QtGui /
  QtWidgets / QtDBus sont utilisés, l'archive est nettement plus légère.

Workflow `.github/workflows/ci.yml` :
1. **tests** : pytest sur `ubuntu-latest` et `windows-latest` (Qt hors écran), à chaque push
   sur `main`, chaque pull request, chaque tag `v*` ;
2. **construire** (hors pull request) : `construire.py`, puis `essai_executable.py`, qui lance
   l'exécutable 5 s et vérifie qu'il crée sa config. Linux construit sur `ubuntu-22.04`
   (glibc plus ancienne, donc compatible avec plus de distributions). Les archives sont
   publiées comme artefacts du run ;
3. **publier** (tag `vX.Y.Z` seulement) : vérifie que le tag correspond à la version du
   `pyproject.toml`, puis crée la release GitHub avec les deux zip, et `VERSION.md` comme
   notes de version.

---

## Conséquences

- Livraison = un zip par OS : `Pointeuse-<version>-<os>-<machine>.zip`, qui contient
  `Pointeuse/` avec l'exécutable, `_internal/`, `LICENSE.txt`, `LICENCES_TIERS.md`,
  `licences/` (LGPL v3 + GPL v3) et `pointeuse_config.exemple.toml`.
- Le CDC (« un seul fichier ») est amendé : un seul **dossier**.
- Linux : sur certaines distributions, Qt demande le paquet système `libxcb-cursor0`
  (Ubuntu : `sudo apt install libxcb-cursor0`).
- Pas de signature de code : Windows SmartScreen peut avertir au premier lancement
  (« Informations complémentaires » → « Exécuter quand même »).
- Faire une release : mettre la version à jour dans `pyproject.toml` et `VERSION.md`, commiter,
  `git tag v0.1.0 && git push --tags`.

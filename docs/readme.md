# Pointeuse

_Dernière mise à jour : 2026-11-17_

## Présentation

Petit utilitaire de pointage : une icône horloge dans la zone de notification
ouvre un panneau pour choisir le client et le projet, mettre en pause ou
insérer une plage horaire passée sur un autre projet. Tout est consigné en CSV.

## Stack technique

- Python 3.12+ (venv `.venv/`)
- UI + icône de notification : PySide6 (Qt 6) — voir `docs/adr/001-toolkit-ui.md`
- Stockage : fichier CSV local
- Packaging : PyInstaller, dossier portable zippé (« onedir ») par OS, pas d'installateur — voir `docs/adr/002-executable-et-ci.md`
- Intégration continue : GitHub Actions (`.github/workflows/ci.yml`) — tests Linux + Windows, construction des deux exécutables, release sur tag `v*`

## Développement

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/python -m pointeuse      # lance l'appli (fichiers dans data/)

# exécutable de l'OS courant → dist/Pointeuse/ + dist/Pointeuse-<version>-<os>-<machine>.zip
.venv/bin/python -m pip install -e ".[build]"
.venv/bin/python outils/construire.py
.venv/bin/python outils/essai_executable.py   # lance l'exécutable 5 s, vérifie qu'il démarre
```

## Structure des dossiers

| Dossier | Contenu |
|---------|---------|
| `src/pointeuse/` | Code de l'application |
| `tests/` | Tests unitaires (pytest) |
| `outils/` | Construction de l'exécutable, essai de lancement |
| `licences/` | Licences livrées avec l'exécutable (LGPL / GPL v3, composants tiers) |
| `.github/workflows/` | GitHub Actions : tests, construction, release |
| `assets/` | Icônes (horloge), ressources UI |
| `data/` | CSV de pointage en dev (non commité) |
| `docs/cdc/` | Cahiers des charges et spécifications |
| `docs/adr/` | Décisions d'architecture |
| `docs/user/` | Doc utilisateur (modules IMPLÉMENTÉ uniquement) |
| `docs/reviews/` | Relectures de code |
| `docs/veille_dependances.md` | Libs / projets de référence repris + veille amont |
| `.claude/` | `settings.json`, `checklist.md` ; règles importées en copie locale, hors dépôt |

## État d'avancement

- [x] Initialisation du projet
- [x] CDC principal (`docs/cdc/pointeuse.md`, statut PARTIELLEMENT IMPLÉMENTÉ)
- [x] ADR 001 — choix du toolkit UI (PySide6)
- [x] ADR 002 — exécutable « onedir » + GitHub Actions
- [x] Étape 1 — config TOML au format compact (`config.py`, 42 tests)
- [x] Étapes 2 et 3 — moteur, CSV, sauvegarde et reprise (`journal.py`, `moteur.py`)
- [~] Étape 4 — icône + onglet « Pointer » + fenêtre d'absence (15 tests hors écran) ; validé sous Ubuntu/GNOME, reste Windows
- [~] Étape 5 — onglet « Insérer / Journée » (`onglet_journee.py`) : insertion avec découpage, journée et totaux ; reste à valider sur poste réel
- [~] Étape 6 — pause automatique (`absence.py`) : relevé d'horloge de secours, D-Bus sous Linux, messages de session sous Windows ; reste à valider sur poste réel
- [~] Étape 7 — exécutable portable (`outils/construire.py`), lancement à l'ouverture de session (`demarrage_auto.py`), CI GitHub Actions ; exécutable Linux vérifié en local, reste Windows et le premier passage de la CI — 135 tests au total

## Déploiement

Télécharger le zip de l'OS dans les releases GitHub (ou les artefacts d'un run Actions), le dézipper où l'on veut (`Documents/`, `C:\pointeuse\`) et lancer `Pointeuse` (`Pointeuse.exe`) dans le dossier `Pointeuse/` : le CSV et la config sont créés à côté.
Menu de l'icône → « Lancer à l'ouverture de session » pour le démarrage automatique.
Linux : si Qt réclame `libxcb-cursor0`, l'installer (`sudo apt install libxcb-cursor0`).
Windows : exécutable non signé, SmartScreen peut avertir au premier lancement.

Publier une version : version dans `src/pointeuse/__init__.py` (`__version__`, seule source, affichée « Pointeuse V0.1 » dans le panneau) + `VERSION.md`, commit, puis `git tag vX.Y.Z && git push --tags`.
Ne jamais livrer `data/`.

## Règles de travail

Ce projet suit les règles définies dans `pilot/IA/` :
- `regles_tout_projet_dev.md`
- `regles_charte_graphique.md`

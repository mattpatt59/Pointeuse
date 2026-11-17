# Pointeuse — CLAUDE.md

Logiciel de pointage du temps par client / projet, résidant dans la zone de
notification (Windows + Linux), avec export CSV.

## Règles applicables

@.claude/regles_tout_projet_dev.md
@.claude/regles_charte_graphique.md

> Ces fichiers sont des copies locales de `pilot/IA/`, **hors dépôt** (`.gitignore`) :
> ne pas les commiter. Sur un nouveau poste, les recopier depuis `pilot/IA/`.
>
> Pas de `regles_projet_dev_python.md` dans `pilot/IA/` au 2026-11-17.
> Si le fichier est créé, l'ajouter ici et dans `.claude/`.

## Spécifique au projet

- **Stack** : Python 3.12+, venv obligatoire (`.venv/`), pas de `pip install` global.
  Dépendances dans `pyproject.toml` ; install dev : `.venv/bin/python -m pip install -e ".[dev]"`.
  Tests : `.venv/bin/python -m pytest`.
- **Cibles** : Windows 10/11 et Linux (Ubuntu GNOME, Wayland + extension AppIndicator).
- **Stockage** : CSV, pas de base de données → pas de dossier `migrations/`.
  Un changement de format du CSV = ADR + note dans `VERSION.md`.
- **Charte** : T-Elec (app Python → police Arial/système, palette verte §C).
- **Constantes** (chemins, durées, colonnes CSV) : `src/pointeuse/settings.py`.
- **Données** : `data/` n'est jamais commité (pointages réels).
- **Version** : projet simple → `VERSION.md`, section `[Non publié]`.
- **Dépendances reprises** : voir `docs/veille_dependances.md`.
- **Checklist** : `.claude/checklist.md`.

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
- Packaging : PyInstaller, exécutable portable « onefile » par OS (pas d'installateur)

## Développement

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/python -m pointeuse      # lance l'appli (fichiers dans data/)
```

## Structure des dossiers

| Dossier | Contenu |
|---------|---------|
| `src/pointeuse/` | Code de l'application |
| `tests/` | Tests unitaires (pytest) |
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
- [x] Étape 1 — config TOML au format compact (`config.py`, 40 tests)
- [x] Étapes 2 et 3 — moteur, CSV, sauvegarde et reprise (`journal.py`, `moteur.py`, 33 tests)
- [~] Étape 4 — icône + onglet « Pointer » + fenêtre d'absence (15 tests hors écran) ; validé sous Ubuntu/GNOME, reste Windows

## Déploiement

Exécutable portable posé où l'on veut (`Documents/`, `C:\pointeuse\`) : le CSV et la config sont créés dans le même dossier.
Ne jamais livrer `data/`.

## Règles de travail

Ce projet suit les règles définies dans `pilot/IA/` :
- `regles_tout_projet_dev.md`
- `regles_charte_graphique.md`

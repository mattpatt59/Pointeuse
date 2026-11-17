# Checklist de vérification — pointeuse
Généré le 2026-11-17 depuis pilot/IA @ cd20ea6 + CLAUDE.md du projet.

## 1. À chaque commit
### 1.1 Commandes
grep -rn "<ancien terme>" README.md docs/readme.md docs/user/      # §H doc-rename — vide
grep -rnE "=.* if .* else " src/                                    # §F ternaires interdits — vide
grep -rnE "https?://" src/ | grep -v settings.py                    # §F URL hors config — vide
git diff --cached --name-only | grep -E "^data/|\.csv$"             # §E données non commitées — vide
### 1.2 Revue (à lire et trancher)
- [ ] Valeurs avec unité / chemins / colonnes CSV dans `settings.py`, pas inline   → §F
- [ ] Pas de nom réel de client dans le code, tests ou exemples                  → §F
- [ ] Reformatage ≥ 30 % d'un fichier → commit `style:` séparé                   → §E
- [ ] Pas de ligne `Co-Authored-By:`                                              → §E
- [ ] `VERSION.md` `[Non publié]` à jour                                          → §E

## 2. Avant merge vers main
Rejouer toute la partie 1, puis :
### 2.1 Commandes
.venv/bin/python -m py_compile $(find src -name "*.py")             # compile — aucune erreur
.venv/bin/python -m pytest -q                                       # tests — tous verts
### 2.2 Revue (à lire et trancher)
- [ ] Testé sur Windows ET Linux (icône, panneau, écriture CSV)                  → CLAUDE.md
- [ ] Format du CSV inchangé, ou ADR + note `VERSION.md`                          → CLAUDE.md
- [ ] Charte T-Elec respectée (palette §C, police système)                       → charte
- [ ] `docs/readme.md`, statuts CDC, `docs/user/` à jour                          → §D / §E

## 3. Première session du mois
- [ ] Sync `.claude/` ← `pilot/IA/` : copies identiques, nouveaux `regles_*.md` applicables présents (surveiller un futur `regles_projet_dev_python.md`), divergence `CLAUDE.md` ↔ règles → prévenir   → §D
- [ ] Régénérer cette checklist si des règles vérifiables ont changé   → §D
- [ ] Veille dépendances : aucune ligne dans `docs/veille_dependances.md` pour l'instant   → §B

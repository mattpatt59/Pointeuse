# Version

## [Non publié]

### Ajouté
- Initialisation du projet (arborescence, règles, templates) — 2026-11-17
- Licence MIT — 2026-11-17
- Lecture / écriture de `pointeuse_config.toml` : création par défaut, ajout automatique des saisies, relecture à chaud (CDC étape 1)
- Moteur de pointage sans interface : démarrer / pause / reprendre, écriture de `pointeuse.csv`, file d'attente si le fichier est bloqué (CDC étape 2)
- Sauvegarde de sécurité `pointeuse_en_cours.json` et reprise après plantage (CDC étape 3)
- Interface : icône horloge dans la zone de notification, onglet « Pointer », fenêtre « retour d'absence » après plantage, alerte si le CSV est bloqué (CDC étape 4)

### Modifié
- `pointeuse_config.toml` : format compact `[clients."Nom"]` + un projet par ligne `"Projet" = { taches = [...] }` (remplace `[[clients]]` / `[[clients.projets]]`). La clé `actif` devient `visible` (true par défaut) ; case « Afficher les projets masqués ». Un projet masqué reste utilisable en tapant son nom, sans réapparaître. Fichier existant à convertir une fois à la main — voir `docs/exemples/pointeuse_config.toml`

### Corrigé
- Listes Client / Projet / Tâche : flèche « ⌄ » invisible (masquée par la feuille de style) → chevron vert sur fond vert clair, liste dépliée aux couleurs de la charte
- Linux : plantage au lancement sous Ubuntu 24.04 / GNOME 46 (thème Qt « gtk3 ») → thème Qt « gnome » forcé

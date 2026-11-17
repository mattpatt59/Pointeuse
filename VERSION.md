# Version

## [Non publié]

### Ajouté
- Initialisation du projet (arborescence, règles, templates) — 2026-11-17
- Licence MIT — 2026-11-17
- Lecture / écriture de `pointeuse_config.toml` : création par défaut, ajout automatique des saisies, relecture à chaud (CDC étape 1)
- Moteur de pointage sans interface : démarrer / pause / reprendre, écriture de `pointeuse.csv`, file d'attente si le fichier est bloqué (CDC étape 2)
- Sauvegarde de sécurité `pointeuse_en_cours.json` et reprise après plantage (CDC étape 3)
- Interface : icône horloge dans la zone de notification, onglet « Pointer », fenêtre « retour d'absence » après plantage, alerte si le CSV est bloqué (CDC étape 4)
- Onglet « Insérer / Journée » : insertion d'une tâche à heures fixes qui découpe ce qu'elle recouvre (CSV et tâche en cours, confirmation si une ligne est remplacée) ; lignes du jour choisi et totaux travaillé / pause (CDC étape 5)
- Pause automatique en cas de veille ou de session verrouillée : la tâche est coupée à l'heure du départ, puis la fenêtre « retour d'absence » demande ce qu'on a fait. Détection par D-Bus (Linux), messages de session (Windows) et, en secours, relevé d'horloge toutes les 30 s (CDC étape 6)
- Exécutable portable Windows et Linux (dossier zippé, PyInstaller), avec les licences LGPL de Qt / PySide6 ; option « Lancer à l'ouverture de session » dans le menu de l'icône (CDC étape 7, ADR 002)
- Version affichée dans l'en-tête et le titre du panneau : « Pointeuse V0.1 » (le numéro de correctif n'apparaît que s'il n'est pas nul) ; version définie à un seul endroit, `src/pointeuse/__init__.py`
- GitHub Actions : tests Linux + Windows, construction des deux exécutables, release automatique sur tag `v*`
- Menu de l'icône « Bilan » : ouvre dans le navigateur le bilan du CSV (temps par client / projet / tâche, graphe, export), fichier déjà chargé. Le lecteur HTML/JS est livré avec l'appli (`src/pointeuse/lecteur/`, licence MIT) et copié dans `bilan/` à côté du CSV avec les données en `pointeuse_donnees_tmp.js` : rien n'est envoyé, fonctionne hors connexion (ADR 003)

### Modifié
- Dépendance `PySide6` remplacée par `PySide6-Essentials` (modules utilisés seulement : exécutable plus léger)
- `pointeuse_config.toml` : format compact `[clients."Nom"]` + un projet par ligne `"Projet" = { taches = [...] }` (remplace `[[clients]]` / `[[clients.projets]]`). La clé `actif` devient `visible` (true par défaut) ; case « Afficher les projets masqués ». Un projet masqué reste utilisable en tapant son nom, sans réapparaître. Fichier existant à convertir une fois à la main — voir `docs/exemples/pointeuse_config.toml`

### Corrigé
- Listes Client / Projet / Tâche : flèche « ⌄ » invisible (masquée par la feuille de style) → chevron vert sur fond vert clair, liste dépliée aux couleurs de la charte
- Linux : plantage au lancement sous Ubuntu 24.04 / GNOME 46 (thème Qt « gtk3 ») → thème Qt « gnome » forcé

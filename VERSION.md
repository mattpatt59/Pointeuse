# Version

## [Non publié]

### Ajouté
- Journal de suivi des projets `pointeuse_suivi.jsonl` (statut, priorité, note par jour ou par semaine) : lecture / écriture et règles de lecture (`suivi.py`), Nouveau fichier de données, `pointeuse.csv` inchangé (CDC suivi_projets.md étapes 1-2, ADR 004)
- Fenêtre « Suivi des projets » (menu de l'icône, bouton « Suivi… » de l'onglet Pointer) : projets triés par priorité, message précédent, note de la période avec statut et priorité, historique temps + notes ; section `[suivi]` dans `pointeuse_config.toml` (`periode_note` = jour / semaine, `rappel_au_stop`) (CDC suivi_projets.md étape 3)
- Bilan : vue « Suivi des projets » : par projet (trié par priorité) le statut en cours puis l'historique jour par jour (temps + notes, note de semaine en tête de sa semaine), sur la période du bilan ou « depuis le … », onglets « Temps | Suivi des projets » en tête du bilan, priorité et statut aussi dans la Répartition de la vue Temps ; bouton « Imprimer », un projet par page. Le bilan reçoit `pointeuse_suivi.jsonl` (données du bilan en version 2) ; dans le lecteur seul, le jsonl se lit avec « Lire un CSV » (CDC suivi_projets.md étape 6)
- Doc utilisateur `docs/user/` : guide général (`pointeuse.md`), onglet Pointer, fusion des CSV de plusieurs PC

### Modifié
- GitHub Actions : actions passées en Node.js 24 (`checkout@v7`, `setup-python@v7`, `upload-artifact@v7`, `download-artifact@v8`), Node.js 20 étant déprécié sur les runners
- Bilan, période « Tout le fichier » : inclut aussi les jours des notes de suivi (une note écrite après le dernier pointage était ignorée : priorité et statut à 0 / sans note)
- Bilan : les scripts et la feuille de style de la page sont appelés avec un jeton `?v=…` renouvelé à chaque clic sur « Bilan », pour que le navigateur ne ressorte pas d'anciennes données de son cache

## [0.1.0] - 2026-11-17

Première version diffusée (les tags `v0.1.0` et `V0.1.1` précédents n'ont été distribués à personne et sont remplacés).

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
- Journal des événements du poste `pointeuse_journal.csv` (démarrage / arrêt de la Pointeuse, verrouillage / déverrouillage, veille / réveil), conservé `retention_journal_jours` jours (90 par défaut, 0 = pas de journal), purgé au démarrage. Fichier à part : `pointeuse.csv` et le bilan ne changent pas (CDC étape 8)
- Onglet « Pointer » sur deux lignes : **Modifier** (corrige la tâche en cours sans la couper) / Démarrer, puis Pause / **Stop** (fin de journée, sans pause) / **Repas** (pause décrite « Repas ») ; **boutons rapides** `[[raccourcis]]` déclarés dans `pointeuse_config.toml` — un clic démarre, client seul accepté (projet en rouge, à compléter avec Modifier) (CDC onglet_pointer.md)
- Vue Journée : événements du poste en gris et moments « non pointés » (PC utilisé, rien de pointé) en orange ; un clic remplit la plage à insérer. Case « Masquer le journal », mémorisée dans la config (`afficher_journal`) (CDC étape 8)
- Onglet « À propos » : version, lien du dépôt https://github.com/mattpatt59/Pointeuse, licence MIT et mention Qt / PySide6 LGPL, présentation de T-Elec et lien vers t-elec.fr
- Fichier de config créé au premier lancement : deux boutons rapides d'exemple, « Administratif » (Perso / administratif) et « 26-01_routage » (Client A / 26-01-Projet / Routage)
- `README.md` de présentation avec captures d'écran (`docs/images/`)

### Modifié
- Dépendance `PySide6` remplacée par `PySide6-Essentials` (modules utilisés seulement : exécutable plus léger)
- `pointeuse_config.toml` : format compact `[clients."Nom"]` + un projet par ligne `"Projet" = { taches = [...] }` (remplace `[[clients]]` / `[[clients.projets]]`). La clé `actif` devient `visible` (true par défaut) ; case « Afficher les projets masqués ». Un projet masqué reste utilisable en tapant son nom, sans réapparaître. Fichier existant à convertir une fois à la main — voir `docs/exemples/pointeuse_config.toml`
- `LICENCES_TIERS.md` : le code source n'est plus « disponible sur demande » mais public, lien vers https://github.com/mattpatt59/Pointeuse
- Absence longue (changement de jour, ou au moins `absence_longue_h` = 4 h) : plus de question au retour, la tâche ou la pause en cours est clôturée à l'heure du départ et rien ne redémarre ; même règle après un plantage (CDC étape 8)
- Bilan avec plusieurs fichiers (plusieurs PC) : ils ne sont plus additionnés mais **fusionnés** autour d'un PC principal (choisi d'un clic) — un temps du secondaire qui chevauche le principal est retiré, une pause du principal laisse la place au travail du secondaire. Bandeau « temps retirés du PC secondaire » avec le détail et l'export `fusion_rapport.csv` ; bouton « Ajouter un autre PC » ; téléchargement de `pointeuse_fusion.csv` (format de `pointeuse.csv`, fichiers d'origine non modifiés) (CDC fusion.md)

### Corrigé
- Listes Client / Projet / Tâche : flèche « ⌄ » invisible (masquée par la feuille de style) → chevron vert sur fond vert clair, liste dépliée aux couleurs de la charte
- Linux : plantage au lancement sous Ubuntu 24.04 / GNOME 46 (thème Qt « gtk3 ») → thème Qt « gnome » forcé

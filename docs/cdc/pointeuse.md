# CDC — Pointeuse

**Date demande :** 2026-11-17
**Date création :** 2026-11-17
**Statut :** IMPLÉMENTÉ

---

## Contexte

Besoin d'un outil de pointage simple, sous Windows et Linux, pour savoir combien
de temps a été passé par client, projet et tâche. L'appli montre la journée en
cours. Le bilan sur une plus longue période s'ouvre dans le navigateur, hors ligne,
par le menu « Bilan » (ADR 003, voir « Bilan »).

Principe de base : **une personne, une chose à la fois**. À tout instant, il y a
soit une seule tâche en cours, soit une pause. Le CSV est une suite continue de
lignes qui ne se chevauchent jamais.

---

## Questions ouvertes

_Aucune — toutes tranchées le 2026-11-17._

---

## Fonctionnement

### Icône dans la zone de notification

- Windows : en bas à droite, à côté de l'icône réseau. Linux : barre du haut (extension AppIndicator).
- Icône horloge **verte** quand une tâche est en cours, **grise** en pause.
- Info-bulle : `Client / Projet / Tâche — depuis 10:12 (1 h 05)` ou `En pause depuis 12:00`.
- Clic gauche : ouvre ou ferme le panneau (Windows). Sous Ubuntu/GNOME, l'extension AppIndicator n'ouvre que le menu : accepté, le menu donne accès à tout (MP 2026-11-17).
- Clic droit : menu `Ouvrir` · `Ouvrir le CSV` · `Ouvrir la config` · `Bilan` (ouvre dans le navigateur le bilan du CSV, page locale générée à côté du CSV — ADR 003) · `Quitter`.

### Panneau — trois onglets

Sous Windows, le panneau s'ouvre juste au-dessus de l'icône. Sous Linux/Wayland,
c'est le système qui le place (accepté, MP 2026-11-17).

**Onglet 1 — « Pointer »** (affiché par défaut) : on démarre une tâche.

```
┌─[ Pointer ]─[ Insérer / Journée ]───┐
│  ● En cours depuis 10:12  (1 h 05)  │
│                                     │
│  Client      [ exemple-client   ▾]  │
│  Projet      [ projet-x         ▾]  │
│  Tâche       [ routage          ▾]  │  ← facultatif
│  Description [ ...                ] │  ← facultatif
│                                     │
│  [ ✎ Modifier ]   [ ▶ Démarrer ]    │
│  [ ❚❚ Pause ] [ ■ Stop ] [ Repas ]  │
│  ─── Boutons rapides ───            │  ← [[raccourcis]] de la config
│  □ Afficher les projets masqués     │
└─────────────────────────────────────┘
```

Boutons Modifier, Stop, Repas et boutons rapides : voir `docs/cdc/onglet_pointer.md`.

**Onglet 2 — « Insérer / Journée »** : on insère une tâche à des heures fixes, et on voit la journée.

```
┌─[ Pointer ]─[ Insérer / Journée ]─────────────────────┐
│  Le [ 17/11/2026 ]  de [ 10:12 ]  à [ 10:30 ]         │
│  Client      [ autre-client     ▾]                    │
│  Projet      [ projet-b         ▾]                    │
│  Tâche       [                  ▾]                    │
│  Description [ questions au téléphone   ]             │
│                                   [ Insérer ]         │
│  ─── Journée du 17/11/2026 ──────────────────────     │
│  08:30–10:12  exemple-client / projet-x / routage  1 h 42 │
│  10:12–10:30  autre-client / projet-b              0 h 18 │
│  10:30–12:00  exemple-client / projet-x / routage  1 h 30 │
│  12:00–13:30  PAUSE                                1 h 30 │
│  13:30– …     exemple-client / projet-x   (en cours)      │
│  ────────────────────────────────────────────────     │
│  Travaillé : 4 h 05        Pause : 1 h 30             │
└───────────────────────────────────────────────────────┘
```

- La journée affichée est celle de la date choisie dans le formulaire (aujourd'hui par défaut). Si on insère un temps sur la veille, on voit donc la veille.
- Elle est lue directement dans le CSV, et la ligne en cours y apparaît aussi.
- Elle est en lecture seule : pour corriger une plage, on insère par-dessus (voir « Insérer un temps défini »).

**Onglet 3 — « À propos »** : version, lien du dépôt (`settings.URL_DEPOT`, https://github.com/mattpatt59/Pointeuse), licence MIT et mention Qt / PySide6 LGPL, présentation de T-Elec et lien vers t-elec.fr, logo. Liens ouverts dans le navigateur ; aucune donnée envoyée.

**Commun aux onglets « Pointer » et « Insérer / Journée » :**

- **Hiérarchie** :
  - un client contient des projets ; la liste Projet n'affiche que ceux du client choisi ;
  - la tâche est **facultative** : on peut pointer « client + projet » seulement, ou « client + projet + tâche » ;
  - la liste Tâche montre d'abord les tâches **du projet choisi**, puis, sous un séparateur, les **tâches communes** s'il y en a dans la config ;
  - une tâche saisie librement est ajoutée **au projet choisi** ;
  - la description est libre et facultative.
- Client, Projet et Tâche sont des listes déroulantes **modifiables** : on choisit dans la liste ou on tape un nouveau nom.
- Client et Projet sont obligatoires pour démarrer (exception : bouton rapide « client seul », voir `onglet_pointer.md`).
- Le changement n'est pris en compte qu'au clic sur **Démarrer**. Sinon, on couperait la tâche en cours au moindre caractère tapé.

### Démarrer / changer de tâche

- Au clic sur **Démarrer** :
  - la ligne en cours (tâche ou pause) est clôturée à l'heure actuelle et écrite dans le CSV ;
  - la nouvelle tâche démarre aussitôt.
- Si le client, le projet ou la tâche saisi n'existe pas encore, il est ajouté au fichier de config (voir plus bas).
- La description reste modifiable pendant la tâche. Elle est écrite dans le CSV au moment où la tâche est clôturée.

### Pause

- Une pause est **écrite comme une ligne du CSV**, avec le client `PAUSE` (MP 2026-11-17).
  - Le nom `PAUSE` est réservé : impossible de créer un client qui porte ce nom.
- **Pause** : clôture la tâche en cours et ouvre une ligne de pause.
- **Reprendre** (le bouton Pause change de libellé) :
  - clôture la pause ;
  - redémarre la dernière tâche (même client, même projet, même tâche, description vide).
- **Stop** : clôture la ligne en cours sans ouvrir de pause ; **Repas** : une pause décrite « Repas » (voir `onglet_pointer.md`).
- Quitter l'appli clôture la ligne en cours, qu'il s'agisse d'une tâche ou d'une pause.

### Pause automatique (veille, session verrouillée)

- Si la session est verrouillée ou le PC mis en veille : la tâche en cours est clôturée à l'heure du verrouillage.
- Au retour, une fenêtre s'ouvre :
  `Absent de 10:30 à 11:15 (45 min). Qu'avez-vous fait ?`
  - `Pause` : une ligne `PAUSE 10:30 → 11:15` est écrite ;
  - `J'ai travaillé sur…` : on choisit client, projet, tâche et description ; une ligne `10:30 → 11:15` est écrite ;
  - option « reprendre la tâche précédente » ensuite (cochée par défaut).
- Comment c'est détecté :
  - Windows : notifications de session et de veille (via `ctypes`, aucune dépendance supplémentaire) ;
  - Linux : D-Bus `org.freedesktop.login1` (veille) et `org.gnome.ScreenSaver` (verrouillage), via QtDBus ;
  - **solution de secours sur les deux OS** : un minuteur vérifie toutes les 30 s l'heure réelle. Un saut de plus de 2 min veut dire que le PC dormait, et on applique alors la même procédure.
- **Absence longue : pas de question** (MP 2026-11-17). Une absence est longue si elle passe un changement de jour (parti à 18:00, revenu le lendemain à 08:30) ou dure au moins `absence_longue_h` heures (4 h par défaut). Dans ce cas :
  - la tâche est clôturée à l'heure du verrouillage, comme pour une absence courte ;
  - une pause en cours est clôturée aussi à l'heure du verrouillage (sinon elle durerait toute la nuit) ;
  - aucune fenêtre ne s'ouvre et rien ne redémarre : on choisit sa tâche en arrivant ;
  - l'heure d'arrivée est notée dans le journal des événements ; un oubli se rattrape depuis la vue Journée (voir « Journal des événements »).
- La même règle s'applique au trou laissé par un plantage (« Sauvegarde de la tâche en cours et redémarrage après plantage », étape 2) : un trou long ne déclenche pas de question.

### Insérer un temps défini

Exemple : on travaille sur le projet A depuis 10:00 ; entre 10:12 et 10:30, on a traité des questions du projet B.

- Se fait dans l'onglet 2 : date (aujourd'hui par défaut), heure de début, heure de fin, client, projet, tâche, description.
- Comme il n'y a qu'une chose à la fois, la plage insérée **découpe** ce qu'elle recouvre (tâche ou pause) :

  | Avant | Après |
  |---|---|
  | A 10:00 → (en cours) | A 10:00 → 10:12 · **B 10:12 → 10:30** · A 10:30 → (en cours) |

- Si la plage recouvre des lignes déjà écrites dans le CSV, celles-ci sont découpées de la même façon. Une ligne entièrement recouverte est remplacée, après confirmation (`Cette plage remplace : A 10:00 → 10:30. Continuer ?`).
- Une plage dans le futur ou avec une fin avant le début est refusée.
- Plage proposée par défaut : les 15 dernières minutes d'aujourd'hui (réglage `DUREE_INSERTION_DEFAUT_MIN`), remise à jour à chaque ouverture du panneau.
- L'insertion est refusée tant que des lignes attendent d'être écrites (CSV ouvert dans Excel) ou si le CSV contient des lignes illisibles (modifiées à la main) : la réécriture les ferait disparaître. Le message dit quoi corriger.
- **Ordre d'écriture** : le CSV est réécrit d'un bloc (fichier temporaire `pointeuse.csv.tmp`, puis remplacement), ensuite la sauvegarde `pointeuse_en_cours.json` est mise à jour (ligne en cours découpée). Un plantage pendant la réécriture laisse l'ancien CSV intact. Un plantage entre les deux peut, au pire, laisser un chevauchement à la reprise (la ligne en cours repart de son ancien début) — rien n'est perdu, une nouvelle insertion le corrige.

### Sauvegarde de la tâche en cours et redémarrage après plantage

- **Toutes les 5 min**, la ligne en cours (tâche ou pause : client, projet, tâche, description, heure de début) est sauvegardée, avec l'heure de la sauvegarde, dans `pointeuse_en_cours.json`.
- Au lancement, si ce fichier contient une ligne ouverte :
  1. la ligne est **écrite automatiquement** dans le CSV jusqu'à la dernière sauvegarde (exemple : démarrée à 14:00, plantage à 17:00, dernière sauvegarde à 16:55 → ligne `14:00 → 16:55` écrite sans rien demander) ;
  2. la fenêtre « retour d'absence » s'ouvre pour le trou entre la dernière sauvegarde et le redémarrage (`Absent de 16:55 à 17:20…`) : on répond pause, ou « j'ai travaillé sur… », comme après une veille ;
  3. on choisit ensuite la tâche suivante (reprendre la même tâche est proposé par défaut).
- On perd au plus 5 min, et elles sont rattrapables par la fenêtre de l'étape 2.

### Journal des événements (rattraper les oublis)

But : savoir quand le PC était réellement utilisé, pour **compléter les plages oubliées** (arrivé à 08:12, première tâche pointée à 08:30). Le journal n'est pas un pointage : il ne sert qu'à aider la saisie (MP 2026-11-17).

- Fichier séparé `pointeuse_journal.csv`, à côté du CSV. **`pointeuse.csv` ne change pas**, le lecteur de bilan (ADR 003) non plus : il ne lit que `pointeuse.csv`.
- Tous les événements sont notés, un par ligne :

  | `evenement` | Quand |
  |---|---|
  | `demarrage` | lancement de l'appli (le matin si le PC était éteint : il n'y a pas de déverrouillage) |
  | `arret` | « Quitter » (absent après un plantage) |
  | `verrouillage` / `deverrouillage` | session verrouillée / déverrouillée |
  | `veille` / `reveil` | mise en veille / réveil ; aussi la solution de secours sur l'horloge (saut détecté) |

- **Vue Journée** (onglet « Insérer / Journée ») :
  - les événements du jour s'affichent entre les lignes, en gris, pour ne pas être confondus avec des pointages ;
  - les **trous** sont mis en évidence : moments où le PC était actif (entre `demarrage` / `deverrouillage` / `reveil` et l'événement de départ suivant) sans aucune ligne, tâche ou pause. Seuls les trous d'au moins `TROU_MIN_AFFICHE_MIN` minutes sont montrés ;
  - un clic sur un trou remplit date, début et fin du formulaire « Insérer » : on choisit le client, le projet, et on insère ;
  - case **« Masquer le journal »** : la vue ne montre plus que les pointages ; le choix est retenu (`afficher_journal` dans `[reglages]`).

  ```
  │  ─── Journée du 17/11/2026 ──────────────────────     │
  │  08:12        ◦ déverrouillage                        │
  │  08:12–08:30  ▒ non pointé                     0 h 18 │  ← clic : remplit l'insertion
  │  08:30–10:00  exemple-client / projet-x / routage  1 h 30 │
  │  10:00        ◦ verrouillage                          │
  │  10:45        ◦ déverrouillage                        │
  │  10:45–11:00  ▒ non pointé                     0 h 15 │
  │  11:00– …     autre-client / projet-b   (en cours)    │
  │  ☐ Masquer le journal                                 │
  ```

- **Rétention** : réglage `retention_journal_jours` (90 jours par défaut). Au démarrage, les lignes plus anciennes sont retirées (réécriture via `pointeuse_journal.csv.tmp`, puis remplacement). `0` = pas de journal : rien n'est écrit, la vue Journée n'affiche ni événements ni trous.
- Ce journal est une donnée de présence : il reste local, lisible par l'utilisateur, et limité dans le temps par la rétention. Si l'outil est un jour déployé chez des salariés, l'information des salariés (voire du CSE) est à prévoir.
- Si l'écriture échoue (fichier ouvert dans un tableur), l'événement est perdu, sans alerte : le journal est une aide, pas une donnée de référence.

---

## Fichiers

### Emplacement : le dossier du programme

- Les fichiers sont créés **dans le même dossier que l'exécutable** (MP 2026-11-17) : on pose `pointeuse.exe` dans `Documents/`, les fichiers apparaissent dans `Documents/`. Si OneDrive pose problème, on le place dans `C:\pointeuse\`.
- L'exécutable est **portable**, sans installateur : un dossier `Pointeuse/` livré en zip (PyInstaller « onedir », ADR 002), à dézipper où l'on veut. Un installateur placerait le programme dans `C:\Program Files\`, où l'on ne peut pas écrire.
- Ce qu'il faut savoir pour l'implémentation :
  - dans l'exécutable, `__file__` pointe vers `_internal/` : le dossier du programme se calcule depuis `sys.executable` ;
  - en développement (`python -m pointeuse`), les fichiers vont dans `data/` du dépôt ;
  - si le dossier n'est pas accessible en écriture, un message demande de déplacer le programme.

| Fichier | Rôle |
|---|---|
| `pointeuse.csv` | Journal des temps |
| `pointeuse_config.toml` | Clients, projets, tâches, réglages — modifiable à la main |
| `pointeuse_journal.csv` | Événements du poste (démarrage, verrouillage…) pour rattraper les oublis — géré par l'appli, purgé selon `retention_journal_jours` |
| `pointeuse_en_cours.json` | Sauvegarde de la ligne en cours, toutes les 5 min — géré par l'appli |
| `pointeuse.lock` | Empêche de lancer deux fois la pointeuse sur les mêmes fichiers — géré par l'appli |

### pointeuse.csv

- Encodage UTF-8 avec BOM, séparateur `;` : un tableur l'ouvre directement, accents compris.
- Une ligne = une tâche ou une pause terminée. Les lignes sont triées par `date_in`.
- La durée est en **minutes entières** (validé, MP 2026-11-17).

```csv
date_in;date_out;client;projet;tache;description;duree_min
2026-11-17 10:00;2026-11-17 10:12;exemple-client;projet-x;routage;carte principale;12
2026-11-17 10:12;2026-11-17 10:30;autre-client;projet-b;;questions au téléphone;18
2026-11-17 10:30;2026-11-17 12:00;exemple-client;projet-x;routage;;90
2026-11-17 12:00;2026-11-17 13:30;PAUSE;;;;90
```

- `date_in` / `date_out` contiennent la date **et** l'heure (`AAAA-MM-JJ HH:MM`), pour gérer les tâches qui passent minuit et pour le bilan.
- `duree_min` est calculée par l'appli et redondante, mais elle évite de recalculer dans le bilan.
- **Ordre d'écriture** : une ligne terminée est d'abord sauvegardée dans `pointeuse_en_cours.json` (avec les lignes encore en attente), puis ajoutée au CSV ; une fois le CSV écrit, elle est retirée du JSON. Un plantage entre les deux ne perd rien ; le doublon éventuel est écarté au redémarrage (MP 2026-11-17).
- Si l'écriture échoue (fichier ouvert dans Excel, par exemple), la ligne reste dans `pointeuse_en_cours.json` et l'appli réessaie toutes les minutes. Une notification prévient l'utilisateur. Aucune ligne n'est perdue. Un seul CSV : pas de fichier de secours `pointeuse_2.csv` (MP 2026-11-17).

### pointeuse_journal.csv

Même conventions que `pointeuse.csv` (UTF-8 avec BOM, `;`), trié par horodatage, ajout en fin de fichier.

```csv
horodatage;evenement
2026-11-17 08:12:40;deverrouillage
2026-11-17 10:00:05;verrouillage
2026-11-17 10:45:31;deverrouillage
2026-11-17 18:02:10;arret
```

- Horodatage à la seconde ; affiché à la minute dans la vue Journée.
- Ce n'est pas un contrat avec le bilan : son format peut évoluer sans ADR (note dans `VERSION.md`).

### pointeuse_config.toml

Format compact : un client = une section, un projet = une ligne (MP 2026-11-17).

```toml
[reglages]
sauvegarde_min = 5          # fréquence de sauvegarde de la ligne en cours
detection_absence_min = 2   # saut d'horloge considéré comme une veille
absence_longue_h = 4        # au-delà (ou si le jour change) : pas de question au retour
retention_journal_jours = 90  # durée de conservation du journal des événements (0 = pas de journal)
afficher_journal = true     # vue Journée : événements et trous visibles (case « Masquer le journal »)

[clients."exemple-client"]
"projet-x" = { taches = ["cdc", "routage", "tests"] }   # tâches propres au projet
"projet-fini" = { taches = [], visible = false }       # n'apparaît plus dans la liste par défaut

[clients."client-fini"]
visible = false             # client masqué par défaut, avec tous ses projets
"projet-y" = { taches = [] }

[taches_communes]           # proposées dans tous les projets — facultatif, peut rester vide
liste = ["réunion", "administratif"]
```

- `[[client:NOM]]` n'est pas du TOML valide : le nom du client va dans l'en-tête sous forme de clé entre guillemets, `[clients."NOM"]`.
- Dans un client, `visible` est le seul réglage ; toute autre clé est un projet. « visible » ne peut donc pas être un nom de projet (refusé à la saisie).
- Un projet n'accepte que `taches` (liste de textes) et `visible` (true / false, true par défaut), tous deux facultatifs. Une autre clé (faute de frappe, `tache` au lieu de `taches`) est signalée.
- L'écriture TOML équivalente `[clients."NOM"."projet"]` est acceptée à la lecture, mais l'appli écrit toujours le format compact.
- Les tâches sont de simples listes de noms : pas de champ `visible`, une tâche se masque avec son projet.

- Si le fichier n'existe pas au premier lancement, il est créé avec un exemple.
- Toute saisie libre d'un client, d'un projet ou d'une tâche nouvelle l'ajoute au fichier : nouveau projet sous le dernier projet du client, nouveau client après le dernier client. Visible par défaut, donc sans `visible`.
- `visible = false` : masqué des listes (projet fini). La case « Afficher les projets masqués » le fait réapparaître.
- Le fichier est relu automatiquement s'il est modifié à la main pendant que l'appli tourne.
- Si une modification manuelle rend le fichier illisible (erreur de syntaxe, clé inconnue…), l'appli garde la dernière config valide et affiche l'erreur une seule fois, jusqu'à la prochaine modification.
- Les noms sont comparés sans tenir compte des majuscules ni des espaces autour : taper « alpha industrie » sélectionne « Alpha Industrie », sans créer de doublon.
- Un client ou un projet masqué reste utilisable exceptionnellement : taper son nom impute le temps dessus, **sans** le faire réapparaître dans les listes (`visible = false` est conservé). Pour le réafficher durablement, retirer `visible = false` à la main — MP 2026-11-17.
- Une tâche qui existe déjà dans les tâches communes n'est pas recopiée dans le projet.
- L'écriture utilise `tomlkit`, qui **conserve les commentaires** et la mise en forme. La lib standard `tomllib` ne sait que lire.
- La sauvegarde toutes les 5 min va dans `pointeuse_en_cours.json`, **pas** dans le TOML : réécrire le TOML en permanence risquerait d'écraser une modification faite à la main.

### Bilan

- Dans l'appli, seule la journée est visible (onglet 2).
- Pour un bilan plus long (semaine, mois, par client) : menu de l'icône « Bilan », lecteur HTML livré avec l'appli, hors ligne (ADR 003). Il ne lit que `pointeuse.csv`, pas le journal des événements.
- Le format du CSV décrit ici sert de contrat avec ce lecteur : toute modification de colonne passe par un ADR (voir `CLAUDE.md`).

---

## Planning

- [x] Step 1 — Config TOML : lecture, création par défaut, ajout d'entrées, relecture à chaud
- [x] Step 2 — Moteur de pointage : démarrer / pause / clôture, écriture CSV, mise en attente si le fichier est bloqué
- [x] Step 3 — Sauvegarde toutes les 5 min + reprise au démarrage
- [x] Step 4 — Icône dans la zone de notification + onglet « Pointer » (Windows + Linux) — validé sur poste réel Linux et Windows (MP 2026-11-18)
- [x] Step 5 — Onglet « Insérer / Journée » : insertion avec découpage (tests unitaires sur les cas de recouvrement) + vue de la journée — validé sur poste réel Linux et Windows (MP 2026-11-18)
- [x] Step 6 — Pause automatique : solution de secours sur l'horloge, puis détection propre à chaque OS (veille / verrouillage) — validé sur poste réel Linux et Windows (MP 2026-11-18)
- [x] Step 7 — Exécutable portable Windows + Linux (ADR 002, construit par GitHub Actions, release v0.1.0) ; lancement à l'ouverture de session (option du menu) — validé sur poste réel Linux et Windows (MP 2026-11-18)
- [x] Step 8 — Absence longue sans question (tâche et pause clôturées au départ, même règle après plantage) + journal des événements (écriture, rétention, purge au démarrage) + vue Journée (événements, trous cliquables, « Masquer le journal ») — validé sur poste réel Linux et Windows (MP 2026-11-18)

---

## Présentation technique

### Fichiers impactés

| Fichier | Action | Note |
|---------|--------|------|
| `src/pointeuse/settings.py` | modifier | Noms de fichiers, colonnes CSV, `PAUSE`, intervalles des minuteurs |
| `src/pointeuse/chemins.py` | créé | Dossier du programme (exécutable ou dev), vérification de l'écriture |
| `src/pointeuse/config.py` | créé | Lecture et écriture du TOML (tomlkit) |
| `src/pointeuse/journal.py` | créé | Lecture / écriture du CSV, lignes d'une journée, découpage d'une plage (`decouper`), réécriture atomique (`reecrire`) |
| `src/pointeuse/moteur.py` | créé | États tâche / pause, file d'attente si CSV bloqué, sauvegarde `pointeuse_en_cours.json`, reprise. L'interface appelle `signe_de_vie()` toutes les 5 min, et toutes les minutes tant que `ecriture_bloquee` |
| `src/pointeuse/absence.py` | créé | Détection veille / verrouillage : relevé d'horloge toutes les 30 s (secours), D-Bus sous Linux, messages de session Windows ; émet chaque événement pour le journal |
| `src/pointeuse/evenements.py` | créé | Journal des événements `pointeuse_journal.csv` (écriture, lecture, purge) ; plages où le PC était utilisé et moments non pointés |
| `src/pointeuse/demarrage_auto.py` | créé | Lancement à l'ouverture de session : registre `HKCU\…\Run` (Windows), `~/.config/autostart/pointeuse.desktop` (Linux) |
| `src/pointeuse/application.py` | créé | Assemblage : icône de notification, menu, minuteurs, verrou une seule instance, reprise au démarrage |
| `src/pointeuse/panneau.py` | créé | Panneau à trois onglets, onglet « Pointer » |
| `src/pointeuse/onglet_a_propos.py` | créé | Onglet « À propos » : version, dépôt, licences, présentation T-Elec |
| `src/pointeuse/onglet_journee.py` | créé | Onglet « Insérer / Journée » : plage date / début / fin, insertion avec confirmation, lignes et totaux du jour |
| `src/pointeuse/formulaire.py` | créé | Client / Projet / Tâche / Description, commun aux onglets et à la fenêtre d'absence |
| `src/pointeuse/dialogue_absence.py` | créé | Fenêtre « retour d'absence » (plantage, veille, verrouillage) |
| `src/pointeuse/affichage.py`, `icone.py`, `style.py` | créés | Textes affichés, icône dessinée (verte / grise / orange si CSV bloqué), feuille de style charte |
| `src/pointeuse/__main__.py` | créé | Point d'entrée (`python -m pointeuse`) |
| `outils/construire.py`, `outils/essai_executable.py` | créés | Construction de l'exécutable + archive zip ; essai de lancement (ADR 002) |
| `.github/workflows/ci.yml` | créé | Tests Linux + Windows, construction des deux exécutables, release sur tag `v*` |
| `licences/` | créé | LGPL v3, GPL v3, `LICENCES_TIERS.md` — livrés avec l'exécutable |
| `tests/` | créé | `test_config.py`, `test_journal.py`, `test_moteur.py`, `test_interface.py` (Qt hors écran), `test_absence.py`, `test_demarrage_auto.py`, dont les cas de recouvrement de l'insertion |

### Dépendances

- `PySide6-Essentials` — UI, icône dans la zone de notification, D-Bus (ADR 001) ; modules complémentaires inutiles
- `tomlkit` — écriture du TOML en conservant les commentaires
- `pyinstaller` (extra `build`) — exécutable portable (ADR 002)

---

## Décisions prises

- [x] **Toolkit** : PySide6 — ADR 001
- [x] **Position du panneau sous Wayland** : placé par le système, accepté — MP 2026-11-17
- [x] **Icône sous Ubuntu/GNOME** : un clic ouvre le menu (Ouvrir, Ouvrir le CSV, Ouvrir la config, Quitter), pas directement le panneau ; conservé tel quel — MP 2026-11-17
- [x] **Format de `pointeuse_config.toml`** : compact, `[clients."NOM"]` + un projet par ligne (inline table), plutôt que `[[clients]]` / `[[clients.projets]]` (verbeux) ou JSON (pas de commentaires, virgules piégeuses à la main) — MP 2026-11-17
- [x] **Distribution** : exécutable portable PyInstaller, un par OS — MP 2026-11-17
- [x] **Format de l'exécutable** : dossier zippé (« onedir ») au lieu d'un fichier unique, pour la LGPL de Qt et un lancement immédiat ; construit par GitHub Actions — ADR 002, MP 2026-11-17
- [x] **Lancement à l'ouverture de session** : case à cocher dans le menu de l'icône (exécutable seulement), désactivée par défaut — MP 2026-11-17
- [x] **Code source** : ~~disponible sur demande auprès de T-Elec~~ → code libre, dépôt public https://github.com/mattpatt59/Pointeuse, lien dans `LICENCES_TIERS.md` et l'onglet « À propos » — MP 2026-11-17
- [x] **Emplacement des fichiers** : dossier de l'exécutable (`Documents/` ou `C:\pointeuse\`) — MP 2026-11-17
- [x] **Une chose à la fois** : jamais de chevauchement, l'insertion découpe ce qu'elle recouvre — MP 2026-11-17
- [x] **Pause** : écrite comme une ligne, client `PAUSE` (nom réservé) — MP 2026-11-17
- [x] **Veille / verrouillage** : pause automatique, puis question « qu'avez-vous fait ? » au retour — MP 2026-11-17 ; **sauf absence longue** (changement de jour ou ≥ `absence_longue_h`, 4 h par défaut) : pas de question, tâche et pause clôturées au départ, rien ne redémarre — MP 2026-11-17
- [x] **Journal des événements** : fichier séparé `pointeuse_journal.csv` (tous les événements : démarrage, arrêt, verrouillage, déverrouillage, veille, réveil), affiché dans la vue Journée pour rattraper les oublis (trous cliquables), case « Masquer le journal » ; `pointeuse.csv` et le lecteur de bilan inchangés ; rétention configurable (`retention_journal_jours`, 90 j par défaut) — MP 2026-11-17
- [x] **Plantage** : sauvegarde toutes les 5 min, ligne écrite automatiquement jusqu'à la dernière sauvegarde au redémarrage — MP 2026-11-17
- [x] **Hiérarchie** : Client → Projet (obligatoires, projet lié au client) → Tâche (facultative) + description libre — MP 2026-11-17
- [x] **Tâches** : rattachées au projet ; liste commune facultative en complément — MP 2026-11-17
- [x] **Listes** : `pointeuse_config.toml`, enrichi par les saisies libres, `visible = false` pour masquer (nommé `actif` à l'origine, renommé — MP 2026-11-17)
- [x] **Durée** : `duree_min`, minutes entières — MP 2026-11-17
- [x] **Interface** : deux onglets — « Pointer » (par défaut) et « Insérer / Journée » — MP 2026-11-17 ; + onglet « À propos » (lien du dépôt https://github.com/mattpatt59/Pointeuse, infos T-Elec) — MP 2026-11-17
- [x] **CSV bloqué** : lignes en attente dans `pointeuse_en_cours.json` (sauvegardé avant le CSV), pas de second CSV — MP 2026-11-17
- [x] **Stockage** : CSV seul ; ~~pas de lecteur HTML local~~ → lecteur de bilan livré avec l'appli, ouvert par le menu « Bilan » (ADR 003, remplace « bilan via t-elec.fr ») — MP 2026-11-17

---

## Notes

- Ne jamais mettre de vrais noms de clients dans les exemples ni dans les tests (règle commune §F).
- Exemple de config (3 clients, 3 tâches par projet) : `docs/exemples/pointeuse_config.toml`.
- Maquettes de l'interface : `docs/maquettes/` — `maquettes.html` (source) et PNG générés par `generer_png.sh` (`pointer`, `liste`, `inserer`, `absence`). Rendu indicatif : l'appli réelle sera en Qt.

# Pointeuse — guide d'utilisation

La Pointeuse note le temps passé par client, projet et tâche. Elle vit dans la zone
de notification (Windows et Linux) et écrit tout dans un fichier CSV, sur votre poste.

Règle de base : **une chose à la fois**. À tout instant, il y a une seule tâche en
cours, ou une pause, ou rien.

---

## Installation

1. Télécharger le zip de votre système dans les
   [Releases](https://github.com/mattpatt59/Pointeuse/releases).
2. Le dézipper où vous voulez : `Documents/`, ou `C:\pointeuse\` si OneDrive gêne.
3. Lancer `Pointeuse.exe` (Windows) ou `Pointeuse` (Linux) dans le dossier `Pointeuse/`.

Pas d'installateur ni de droits administrateur. Les fichiers de données sont créés
dans le dossier **`data/`, à côté de l'exécutable** : le dossier doit être accessible en écriture.
Depuis une V0.1 : déplacer à la main `pointeuse.csv`, `pointeuse_config.toml` et les autres
fichiers `pointeuse_*` dans `data/` avant de lancer la nouvelle version.

- **Windows** : l'exécutable n'est pas signé, SmartScreen peut avertir au premier
  lancement (« Informations complémentaires » → « Exécuter quand même »).
- **Linux (Ubuntu GNOME)** : l'icône demande l'extension AppIndicator. Si Qt réclame
  `libxcb-cursor0` : `sudo apt install libxcb-cursor0`.

Une seule Pointeuse peut tourner sur un même dossier de fichiers.

---

## L'icône

- **Verte** : une tâche est en cours. **Grise** : pause ou rien en cours.
- Info-bulle : la tâche en cours et depuis quand (`Client / Projet / Tâche — depuis 10:12 (1 h 05)`).
- Clic gauche (Windows) : ouvre ou ferme le panneau. Sous Ubuntu GNOME, le clic ouvre
  le menu, qui donne accès à tout.
- Menu :

  | Entrée | Effet |
  |---|---|
  | Ouvrir | Ouvre le panneau |
  | Ouvrir le CSV | Ouvre `pointeuse.csv` dans le tableur |
  | Ouvrir la config | Ouvre `pointeuse_config.toml` dans l'éditeur de texte |
  | Bilan | Ouvre le bilan dans le navigateur (voir plus bas) |
  | Lancer à l'ouverture de session | Case à cocher : la Pointeuse démarre avec la session |
  | Quitter | Clôture la ligne en cours et ferme la Pointeuse |

Le panneau a trois onglets :

- **Pointer** : démarrer, modifier, mettre en pause, arrêter
  (voir [onglet_pointer.md](onglet_pointer.md)) ;
- **Insérer / Journée** : ajouter une plage après coup, voir la journée ;
- **À propos** : version, lien du code source, licences.

---

## Client, projet, tâche

- Un client contient des projets ; la liste Projet ne montre que ceux du client choisi.
- La **tâche est facultative**. La liste Tâche montre d'abord les tâches du projet,
  puis les tâches communes à tous les projets.
- La description est libre et facultative.
- On choisit dans la liste ou on **tape un nouveau nom** : il est ajouté au fichier
  de config. Majuscules et espaces autour ne comptent pas (« alpha industrie »
  retrouve « Alpha Industrie »).
- `PAUSE` est un nom réservé : il ne peut pas servir de client.
- Les projets terminés peuvent être masqués (voir « Configuration »). La case
  **Afficher les projets masqués** les fait réapparaître. Taper le nom d'un projet
  masqué permet quand même de pointer dessus, sans le réafficher.

---

## Onglet « Insérer / Journée »

### Insérer une plage après coup

Exemple : vous travaillez sur le projet A depuis 10:00 ; de 10:12 à 10:30, vous avez
répondu au téléphone pour le projet B.

1. Choisir la date (aujourd'hui par défaut), l'heure de début et l'heure de fin.
   Par défaut, la plage proposée est celle des 15 dernières minutes.
2. Choisir client, projet, tâche, description.
3. **＋ Insérer**.

La plage insérée **découpe** ce qu'elle recouvre :

| Avant | Après |
|---|---|
| A 10:00 → (en cours) | A 10:00 → 10:12 · **B 10:12 → 10:30** · A 10:30 → (en cours) |

- Si une ligne est entièrement recouverte, elle est remplacée après confirmation.
- Une plage dans le futur, ou qui finit avant de commencer, est refusée.
- L'insertion est refusée si le CSV est ouvert dans un tableur, ou s'il contient des
  lignes modifiées à la main devenues illisibles : le message dit quoi corriger.

Pour corriger une plage existante, on insère simplement la bonne par-dessus.

### La journée

Sous le formulaire : les lignes de la journée choisie (tâche en cours comprise), puis
le total travaillé et le total des pauses. La vue est en lecture seule.

Le **journal du poste** s'y affiche aussi, en gris : démarrage, verrouillage,
déverrouillage, veille, réveil. Les moments où le PC était utilisé sans rien de pointé
apparaissent en **orange** (« non pointé ») : **un clic dessus remplit la date et les
heures du formulaire**, il ne reste qu'à choisir le client et le projet.

La case **Masquer le journal** n'affiche plus que les pointages (le choix est retenu).

---

## Absences

### Veille ou session verrouillée

La tâche est arrêtée à l'heure du départ. Au retour, une fenêtre demande :

`Absent de 10:30 à 11:15 (45 min). Qu'avez-vous fait ?`

- **Pause** : la plage est notée en pause ;
- **J'ai travaillé sur…** : on choisit client, projet, tâche, et la plage leur est imputée.

La case « reprendre la tâche précédente » (cochée par défaut) relance ensuite la tâche
d'avant.

### Absence longue

Si l'absence passe la nuit (changement de jour) ou dure au moins 4 h (réglage
`absence_longue_h`) : **aucune question**. La tâche, ou la pause, est clôturée à
l'heure du départ et rien ne redémarre : vous choisissez votre tâche en arrivant.
Un oubli se rattrape dans la vue Journée (clic sur le « non pointé » orange).

### Plantage ou coupure de courant

La ligne en cours est sauvegardée toutes les 5 minutes. Au redémarrage, elle est
écrite jusqu'à la dernière sauvegarde, puis la fenêtre d'absence s'ouvre pour les
minutes manquantes (sauf absence longue). On perd au plus 5 minutes, rattrapables.

---

## Bilan

Menu de l'icône → **Bilan** : le CSV s'ouvre dans le navigateur, déjà chargé. Tout
reste en local, rien n'est envoyé.

- **Période** : cette semaine, semaine dernière, ce mois-ci, mois dernier, cette année,
  tout le fichier, ou dates choisies.
- **Graphe par** jour, semaine ou mois (Auto choisit selon la période).
- **Répartition** par client, projet ou tâche, en heures décimales pour la facturation.
- **Filtres** : recherche texte, choix des clients, affichage des pauses.
- **Exporter** : CSV de la répartition affichée.

Plusieurs postes ? Le bilan sait fusionner les CSV de plusieurs PC sans compter deux
fois le même moment : voir [fusion.md](fusion.md).

---

## Les fichiers

Tous dans le dossier de l'exécutable.

| Fichier | Rôle |
|---|---|
| `pointeuse.csv` | Les pointages. À sauvegarder. |
| `pointeuse_config.toml` | Clients, projets, tâches, boutons rapides, réglages. Modifiable à la main. |
| `pointeuse_journal.csv` | Événements du poste, gardés 90 jours. |
| `pointeuse_en_cours.json` | Sauvegarde de la ligne en cours. Ne pas modifier. |
| `pointeuse.lock` | Empêche un deuxième lancement. Ne pas modifier. |

### pointeuse.csv

Une ligne par tâche ou pause terminée, séparateur `;`, UTF-8 : il s'ouvre directement
dans un tableur.

```csv
date_in;date_out;client;projet;tache;description;duree_min
2026-11-17 10:00;2026-11-17 10:12;exemple-client;projet-x;routage;carte principale;12
2026-11-17 12:00;2026-11-17 13:30;PAUSE;;;Repas;90
```

Une ligne est écrite **à sa clôture** (nouvelle tâche, pause, Stop, Quitter). Si le
fichier est ouvert dans un tableur au même moment, rien n'est perdu : la ligne attend,
une notification prévient, et l'écriture se refait toute seule une fois le fichier fermé.

### Configuration — pointeuse_config.toml

Créé au premier lancement avec un exemple. Il est relu automatiquement quand on le
modifie, et les commentaires sont conservés quand la Pointeuse y ajoute un nom.

```toml
[reglages]
sauvegarde_min = 5            # sauvegarde de la ligne en cours
detection_absence_min = 2     # saut d'horloge considéré comme une veille
absence_longue_h = 4          # au-delà, ou si le jour change : pas de question au retour
retention_journal_jours = 90  # conservation du journal (0 = pas de journal)
afficher_journal = true       # vue Journée : journal visible

[clients."exemple-client"]
"projet-x" = { taches = ["cdc", "routage", "tests"] }
"projet-fini" = { taches = [], visible = false }   # masqué des listes

[clients."client-fini"]
visible = false               # client masqué, avec tous ses projets
"projet-y" = { taches = [] }

[taches_communes]             # proposées dans tous les projets
liste = ["réunion", "administratif"]
```

- « visible » ne peut pas être un nom de projet.
- Les boutons rapides `[[raccourcis]]` sont décrits dans [onglet_pointer.md](onglet_pointer.md).
- Si une modification rend le fichier illisible, la Pointeuse garde la dernière
  version valide et affiche l'erreur une fois.

Exemple commenté complet : [docs/exemples/pointeuse_config.toml](../exemples/pointeuse_config.toml).

### Le journal du poste

`pointeuse_journal.csv` note les démarrages, arrêts, verrouillages et mises en veille.
Il ne sert qu'à repérer les oublis dans la vue Journée ; le bilan ne le lit pas. Il reste
local et les lignes de plus de 90 jours sont effacées au démarrage
(`retention_journal_jours = 0` : pas de journal du tout).

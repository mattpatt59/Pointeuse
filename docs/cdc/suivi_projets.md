# CDC — Suivi des projets : statut, priorité, notes datées

**Date demande :** 2026-11-20
**Date création :** 2026-11-20
**Statut :** PARTIELLEMENT IMPLÉMENTÉ

---

## Contexte

MP fait un **bilan de la semaine**. Aujourd'hui la Pointeuse dit *combien de temps* a été
passé par projet, mais pas *où en est* le projet : ce qui fonctionne, ce qui bloque, ce qui
est prioritaire.

Besoin :
- une fenêtre « Suivi » avec la liste des projets ;
- pour chacun : un **statut**, une **priorité**, une **note** par période (ce qui marche /
  ce qui ne marche pas) ;
- dans le **bilan** : par projet, le statut en cours et l'historique (notes + temps passé).

Le temps vient du CSV des pointages : il n'est **jamais ressaisi**.

---

## Décisions de cadrage (MP 2026-11-20)

- **Niveau** : statut, priorité et notes au niveau du **projet**. Les tâches restent de
  simples libellés.
- **Tout le suivi est dans `pointeuse_suivi.jsonl`** : statut, priorité, notes. Rien n'est
  écrit dans `pointeuse_config.toml` (pas de `visible = false` posé par le suivi).
- **Statuts** : `à faire`, `en cours`, `bloqué`, `en attente client`, `terminé`.
  `terminé` masque le projet (fenêtre Suivi et listes de l'onglet Pointer). Le relancer
  est simple : choisir un autre statut le ré-affiche.
- **Statut calculé `terminé ?`** : si du temps est pointé sur un projet `terminé` après la
  note qui l'a terminé, il s'affiche `terminé ?` et redevient visible. Ce n'est pas
  forcément une réouverture (une question du client) : c'est à MP de trancher en écrivant
  une note. Rien n'est écrit automatiquement dans le journal. C'est un statut à part
  entière à l'affichage (badge, tri, filtre) ; on en sort en écrivant une note :
  `terminé` (confirmé) ou un statut ouvert (`en cours`, `bloqué`…) si le projet est rouvert.
- **Priorité** : un entier de **-99 (urgent) à +99**, 0 par défaut. Tri croissant : le plus
  petit nombre passe en premier. Libre à l'usage de n'en utiliser que 2 ou 3 valeurs.
- **Notes** : **une note par période et par projet**. Période réglable : `jour` (défaut)
  ou `semaine`. La note est **la dernière version enregistrée** dans la période : les
  versions précédentes ne sont plus affichées nulle part.
  - Mode jour : notes écrites à 9 h, 12 h puis 16 h → seule celle de 16 h reste.
  - Mode semaine : note écrite lundi, modifiée vendredi → seule celle de vendredi reste,
    datée du vendredi.
- **Plusieurs PC** : chaque PC a en général ses propres projets ; le même projet sur deux
  PC est rare. Si deux postes ont une note sur la même période pour le même projet, **les
  deux sont affichées**, chacune avec le nom de son poste. Statut et priorité actuels :
  ceux de la note la plus récente, tous postes confondus.
- **Bilan par jour, toujours** : même en mode `semaine`, l'historique du bilan garde une
  ligne par jour avec son temps pointé. La note de la semaine s'affiche en tête de la
  semaine, au-dessus de ses jours. Un total sur la semaine entière masquerait la
  répartition réelle du travail.
- **Saisie** : dans une **fenêtre séparée**, redimensionnable (voir maquette ci-dessous).
- **Rappel** : proposer d'écrire la note au **Stop**, pour le projet arrêté, s'il n'a pas
  encore de note sur la période. Désactivable.
- **Bilan** : par projet, le **statut en cours** (dernière note) puis l'**historique** sur la
  plage de dates du bilan (défaut) ou depuis une date choisie. Peut tenir sur plusieurs
  pages (un projet par page à l'impression).

---

## Fichier `pointeuse_suivi.jsonl`

### Pourquoi pas un CSV

Une note fait plusieurs lignes. En CSV, c'est permis (champ entre guillemets) mais
fragile : une ligne de fichier ≠ un enregistrement, un guillemet mal fermé décale tout ce
qui suit, une édition à la main ou un `grep` cassent facilement le fichier.

### Format retenu (proposé) : JSON Lines

Un enregistrement = **une ligne** du fichier, au format JSON. Les retours à la ligne de la
note sont écrits `\n` par la bibliothèque JSON : le fichier reste strictement « une ligne
par note », quel que soit le texte.

```
{"horodatage": "2026-11-14 18:02", "periode": "2026-11-14", "client": "Alpha Industrie", "projet": "Armoire ligne 2", "statut": "en cours", "priorite": -10, "texte": "Câblage OK.\nDéfaut sur la sortie 3, à reprendre."}
{"horodatage": "2026-11-15 17:40", "periode": "2026-11-15", "client": "Alpha Industrie", "projet": "Armoire ligne 2", "statut": "bloqué", "priorite": -10, "texte": "Attente retour client sur le schéma."}
```

- Encodage UTF-8, lisible dans n'importe quel éditeur. Pas fait pour Excel (ce n'est pas
  son rôle : l'export Excel reste `pointeuse.csv`).
- Lecture native côté Python (`json`) et côté lecteur JS (`JSON.parse` ligne à ligne).
- Une ligne illisible (édition à la main ratée) est ignorée avec un avertissement, sans
  perdre les autres.
- `periode` : la date (`2026-11-14`) en mode jour, la semaine ISO (`2026-W46`) en mode
  semaine.

### Ajout seul

On **ajoute** une ligne à chaque enregistrement, on ne réécrit jamais le fichier :
- pas de perte de données si l'appli plante pendant une écriture ;
- la note d'une période **est la dernière ligne** pour ce projet et cette période :
  rouvrir et corriger la note du jour ajoute une ligne qui remplace l'ancienne à
  l'affichage ;
- statut et priorité actuels = ceux de la dernière ligne du projet, toutes périodes
  confondues ;
- volume négligeable (quelques Ko par mois).

### Plusieurs PC (CDC `multi_postes.md`)

Fichier dans `data/`, copié dans le dossier externe comme les autres. Le bilan concatène
les journaux des postes et trie par horodatage. La règle « dernière version de la
période » s'applique **par poste** : deux postes → deux notes affichées, avec le nom du
poste. Le statut et la priorité actuels sont ceux de la note la plus récente, tous postes
confondus.

### Réglages : section `[suivi]` de `pointeuse_config.toml`

```toml
[suivi]
periode_note = "jour"    # "jour" ou "semaine"
rappel_au_stop = true    # proposer la note au Stop si la période n'en a pas
```

---

## Fenêtre « Suivi » (proposition)

Ouverture : menu de l'icône « Suivi… », bouton dans l'onglet Pointer, rappel au Stop
(ouvre directement sur le projet arrêté).

```
┌─ Suivi des projets ──────────────────────────────────────────────────────────────┐
│ ☐ Afficher les projets terminés                                                  │
│ ┌──────────────────────────────┐  Alpha Industrie — Armoire ligne 2              │
│ │ -10  Armoire ligne 2  BLOQUÉ │                                                 │
│ │   0  Carte capteur v2 EN C.  │  ──── Message du 14/11/2026  (en cours, -10) ── │
│ │   0  Firmware passer. À FAIRE│  Câblage OK.                                    │
│ │  20  Supervision s.  ATT. CL.│  Défaut sur la sortie 3, à reprendre.           │
│ │   5  Rétrofit presse TERMINÉ?│                                                 │
│ │                              │  ──── Travail en cours  [15/11/2026]            │
│ │                              │       Statut [bloqué        ⌄]  Priorité [-10]  │
│ │                              │  ┌───────────────────────────────────────────┐  │
│ │                              │  │ Attente retour client sur le schéma,      │  │
│ │                              │  │ en fait je pense que…                     │  │
│ │                              │  └───────────────────────────────────────────┘  │
│ │                              │                            [Enregistrer]        │
│ │                              │  ──── Historique ───────────────────────────    │
│ │                              │  13/11  2 h 10  (pas de note)                   │
│ │                              │  12/11  0 h 45  en cours — Schéma validé…       │
│ └──────────────────────────────┘                                                 │
└──────────────────────────────────────────────────────────────────────────────────┘
```

- À gauche : les projets, triés par priorité puis par nom, avec un badge de statut.
- À droite, de haut en bas :
  - **Message du …** : la note de la période précédente, en lecture seule, pour
    écrire la suite sans la chercher ;
  - **Travail en cours** : la note de la période choisie (aujourd'hui par défaut, ou la
    semaine en cours), avec statut et priorité. S'il y a déjà une version sur la période,
    elle est chargée et l'enregistrement la remplace. Changer la date permet d'écrire la
    note d'un jour passé ;
  - **Historique** en lecture seule : période, temps pointé, statut, début de la note.

---

## Bilan : page « Suivi »

```
Alpha Industrie — Armoire ligne 2           Priorité -10      Statut : BLOQUÉ
  Statut en cours (15/11) : Attente retour client sur le schéma.

  15/11/2026   3 h 20   Attente retour client sur le schéma.
  14/11/2026   1 h 05   Câblage OK.
                        Défaut sur la sortie 3, à reprendre.
  13/11/2026   2 h 10
  12/11/2026   0 h 45
```

- Projets triés par priorité. Un projet apparaît s'il a du temps **ou** une note sur la
  plage.
- Plage : celle du bilan par défaut, ou « depuis le … ».
- Une ligne **par jour**, du plus récent au plus ancien, quel que soit le réglage de
  période. En mode semaine, la note de la semaine s'affiche en tête de la semaine :

```
  ──── Semaine 46 (10/11 → 16/11) — note du 14/11 ────
  Câblage OK. Défaut sur la sortie 3, à reprendre.
  14/11/2026   1 h 05
  13/11/2026   2 h 10
  12/11/2026   0 h 45
```

- Note du même projet sur deux postes pour la même période : les deux, chacune précédée
  du nom du poste.
- Impression : saut de page entre projets.

Réalisé (étape 6) :

- Onglets « Temps | Suivi des projets » en tête du bilan, visibles dès qu'un
  `pointeuse_suivi.jsonl` est chargé avec des pointages (seule vue possible s'il n'y
  a que lui). Premier essai : le choix était dans les réglages, à droite — passé
  inaperçu à l'usage, déplacé en onglets.
- Vue Temps, tableau Répartition : priorité et statut (fin de période) à côté de
  chaque projet qui a une note.
- Période « Tout le fichier » : va du premier au dernier jour qui a un pointage **ou une
  note de suivi**. Avant, elle s'arrêtait au dernier pointage : une note écrite ensuite
  sortait de la plage et le projet s'affichait « Priorité 0, sans note » (vu à l'usage).
- En-tête de chaque projet : priorité et statut **à la fin de la période** (dernière
  note écrite avant), `terminé ?` si du temps a été pointé ensuite ; puis
  « Statut en cours (date) » avec le texte de cette note, même si elle est antérieure à
  la plage.
- Filtres clients du bilan appliqués ; recherche, pauses, graphe et répartition masqués
  dans cette vue ; « Exporter » désactivé (l'export reste celui des temps).
- Lignes abîmées du jsonl : listées sous le fichier dans « Fichiers lus », avec les
  mêmes messages que la fenêtre Suivi.
- Plusieurs jsonl chargés : le nom du fichier sert de nom de poste.

---

## Questions ouvertes

- [x] Format JSON Lines — validé MP 2026-11-20
- [x] Priorité / statut : journal seul — validé MP 2026-11-20 (« 100 % dans le jsonl »)
- [x] Pointer sur un projet `terminé` → statut calculé `terminé ?` — MP 2026-11-20
- [x] Bilan en mode semaine : temps affiché jour par jour — MP 2026-11-20
- [x] Même projet sur deux postes : les deux notes affichées — MP 2026-11-20

---

## Planning

- [x] Step 1 — Valider le format, ADR `docs/adr/004-journal-suivi.md` (ACCEPTÉ 2026-11-20)
- [x] Step 2 — `suivi.py` : lecture / ajout dans `pointeuse_suivi.jsonl` (+ tests)
- [x] Step 3 — Fenêtre « Suivi » (saisie + historique) : menu de l'icône « Suivi des projets… » et bouton « Suivi… » de l'onglet Pointer ; section `[suivi]` de la config (`periode_note`, `rappel_au_stop`) (+ tests)
- [x] Step 4 — Masquage des projets `terminé` / statut calculé `terminé ?` (Suivi + onglet Pointer) (+ tests)
- [x] Step 5 — Rappel au Stop (+ tests)
- [x] Step 6 — Bilan : page « Suivi » — vue « Suivi des projets » du lecteur (`lecteur/suivi.js` + `pointeuse.js`), réglage « Historique : période du bilan / depuis le … », bouton « Imprimer » (un projet par page) ; `pointeuse_suivi.jsonl` transmis brut par `bilan.py` (`VERSION_DONNEES_BILAN` = 2) ou lu avec « Lire un CSV » / « Ajouter un autre PC » (+ tests JS sur le jeu d'exemple commun)
- [x] Step 7 — Fusion multi-postes du journal de suivi, dans le bilan (`suiviNomsPostes`, `suiviFusionner` de `lecteur/suivi.js`) (+ tests JS). La collecte automatique des journaux des autres postes viendra avec le CDC `multi_postes.md` (PLAN) ; d'ici là, « Ajouter un autre PC »

Réalisé (étape 7, 2026-11-20) :

- Problème corrigé : le nom du fichier servait de nom de poste. Deux PC ont le même
  `pointeuse_suivi.jsonl`, donc le même « poste » : la note du jour de l'un cachait
  celle de l'autre (règle « dernière version par poste et par période »).
- Nom de poste de chaque journal chargé :
  - `local` pour celui de la Pointeuse qui ouvre le bilan (même mot que `multi_postes.md`) ;
  - sinon le nom du fichier sans extension s'il est parlant (`portable.jsonl` →
    `portable`), ou celui du CSV ajouté avec lui (`atelier.csv` → `atelier`) ;
  - sinon `PC 2`, `PC 3`… dans l'ordre de chargement (noms `pointeuse…` jugés génériques) ;
  - jamais deux postes du même nom (`portable (2)`).
  Pour nommer un PC dans le bilan : renommer son jsonl avant de l'ajouter.
- Une note identique (même horodatage, période, projet, statut, priorité, texte) lue dans
  deux journaux n'est gardée qu'une fois, sous le premier chargé : même fichier ajouté
  deux fois, copie du journal local. « Fichiers lus » l'indique (« n déjà lue(s) dans un
  autre fichier »), comme la règle 5 de `fusion.md` pour les pointages.
- Pas de PC principal pour le suivi : les notes ne se chevauchent pas, elles s'ajoutent.
  Statut et priorité : note la plus récente tous postes confondus (inchangé).
- La fenêtre Suivi de la Pointeuse reste locale (notes de ce PC seulement).
- Quand `multi_postes.md` sera fait, `bilan.py` transmettra les journaux du dossier
  externe avec le nom du dossier comme poste (champ `poste` de l'entrée, prioritaire sur
  le nom calculé).

Réalisé (étapes 4 et 5, 2026-11-20) :

- Onglet Pointer : un projet `terminé` disparaît des listes Projet, comme un projet
  masqué ; un client dont tous les projets visibles sont terminés disparaît aussi. La
  case « Afficher les projets masqués » les ré-affiche. Un projet `terminé ?` (temps
  pointé après la note) reste visible. Les listes sont recalculées à l'ouverture du
  panneau et à chaque note enregistrée, pas à chaque frappe. Taper le nom d'un projet
  terminé reste possible (même règle que les projets masqués).
- Seul l'onglet Pointer filtre : l'onglet Journée et la fenêtre « retour d'absence »
  gardent toutes les listes (on corrige le passé, où le projet était encore ouvert).
- Rappel au Stop : sur Stop d'une tâche (pas d'une pause), si `rappel_au_stop` est vrai et
  que le projet n'a pas de note sur la période en cours (jour ou semaine selon
  `periode_note`), la fenêtre Suivi s'ouvre directement sur ce projet. Pas de question
  intermédiaire : fermer la fenêtre suffit pour ne rien écrire.

---

## Présentation technique

### Fichiers impactés (estimation)

| Fichier | Action | Note |
|---------|--------|------|
| `src/pointeuse/settings.py` | modifier | nom du fichier, statuts, bornes de priorité, réglages `[suivi]` |
| `src/pointeuse/suivi.py` | créer | lecture / ajout dans `pointeuse_suivi.jsonl` |
| `src/pointeuse/fenetre_suivi.py` | créer | saisie + historique |
| `src/pointeuse/config.py` | modifier | section `[suivi]` (réglages seulement) |
| `src/pointeuse/formulaire.py` | modifier | listes de l'onglet Pointer : masquer les projets `terminé` |
| `src/pointeuse/panneau.py`, `icone.py` | modifier | accès à la fenêtre ; signal `projet_arrete` émis au Stop d'une tâche |
| `src/pointeuse/application.py` | modifier | branchements : projets terminés → formulaire, note enregistrée → rechargement des listes, `rappel_au_stop` |
| `src/pointeuse/bilan.py` | modifier | injecter le suivi (`VERSION_DONNEES_BILAN` + 1) |
| `src/pointeuse/lecteur/*` | modifier | page « Suivi » : `suivi.js` (lecture + blocs par projet, sans page), `pointeuse.js`, `pointeuse.css`, `index.html` |
| `docs/adr/004-journal-suivi.md` | créer | format du nouveau fichier |

---

## Décisions prises

Voir « Décisions de cadrage » ci-dessus.

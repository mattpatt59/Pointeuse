# CDC — Plusieurs PC : données locales + dossier externe

**Date demande :** 2026-11-20
**Date création :** 2026-11-20
**Statut :** IMPLÉMENTÉ (validé sur poste réel par MP le 2026-11-20, mergé en 1.1.0)

---

## Contexte

MP pointe sur plusieurs PC : le sien et des PC chez des clients. Il est le **seul
utilisateur** (une seule personne, plusieurs machines) et les PC ne sont pas en réseau
entre eux. Aujourd'hui, chaque Pointeuse écrit ses fichiers à côté de son exécutable.
Les `pointeuse.csv` sont donc éparpillés : pour un bilan, il faut les récupérer à la main
puis les fusionner dans le lecteur (CDC `fusion.md`).

Objectif :
- chaque poste continue à **travailler en local**, sans dépendre d'un réseau ;
- chaque poste peut **sauvegarder** `data/` dans un dossier (drive, NAS, `Z:/`, ou
  simple dossier), dont le nom est celui du poste ;
- un **dossier externe** regroupe ces sauvegardes, un sous-dossier par poste ;
- le **bilan** lit tout d'un coup.

---

## Décisions de cadrage (MP 2026-11-20)

- **Un seul utilisateur** : pas de notion de personne, la fusion se fait entre tous les postes.
- **Chaque PC a sa propre config** : pas de config partagée, donc pas de conflit d'écriture.
  La liste des clients n'est pas diffusée sur les PC des autres clients.
- **La Pointeuse ne synchronise rien** : elle recopie les fichiers dans un dossier. Si ce
  dossier est un drive ou un NAS, la sauvegarde distante vient de là.
- **Pas de détection du double pointage** : les PC ne sont pas en réseau. Les
  chevauchements se voient au bilan, dans le bandeau « temps retirés du PC secondaire »
  de la fusion (CDC `fusion.md`).

---

## Arborescence

```
<dossier du logiciel>/                   ← là où est l'exécutable
  pointeuse(.exe)
  pointeuse.lock                         ← verrou « appli déjà lancée » (local, jamais copié)
  data/                                  ← DONNÉES DE TRAVAIL de ce poste (toujours local)
    pointeuse_config.toml                ← config de ce poste (contient [donnees], voir plus bas)
    pointeuse.csv                        ← pointages (format inchangé)
    pointeuse_journal.csv
    pointeuse_suivi.jsonl                ← notes de suivi (CDC suivi_projets.md)
    pointeuse_en_cours.json              ← local, jamais copié
  data_extern/                           ← dossier externe PAR DÉFAUT (réglable : Z:/…, NAS, drive)

<dossier externe>/                       ← lu par le bilan, uniquement des données externes
  bureau/                                ← dossier de sauvegarde d'un poste, nommé comme le poste
    pointeuse_config.toml
    pointeuse.csv
    pointeuse_journal.csv
  client-a/
    ...
```

- La Pointeuse lit et écrit **uniquement dans `data/`**. Elle **écrit** une copie dans le
  dossier de sauvegarde et **lit** le dossier externe pour le bilan, rien d'autre.
- Le **nom du poste est le nom de son dossier de sauvegarde** (pas de réglage `poste`,
  MP 2026-11-20).
- Les noms et formats de fichiers ne changent pas : seul leur emplacement change
  (`data/` au lieu de la racine du logiciel).
- En développement (`python -m pointeuse`), le dossier du logiciel est la racine du dépôt.
  `data/` reste le même, et `data_extern/` doit être ajouté au `.gitignore`.

### Réglages : section `[donnees]` de `pointeuse_config.toml`

Format retenu par MP (2026-11-20) :

```toml
# Sauvegarde des données
[donnees]
dossier_de_sauvegarde = ""        # vide = fonctionnement sans sauvegarde automatique (ex. "Z:/pointeuse/bureau")
dossier_externe = "data_extern"   # bilan : un sous-dossier par autre PC (ex. "Z:/pointeuse")
```

- **`dossier_de_sauvegarde` = cible de la copie.** Chemin absolu, ou relatif au dossier
  du logiciel. Les fichiers y sont copiés directement (pas de sous-dossier). **Vide (défaut) :
  pas de sauvegarde.** Son nom est le nom du poste : `Z:/pointeuse/bureau` → poste
  « bureau ». Un dossier dans `data/` est refusé (notification, info-bulle).
- **`dossier_externe` = lu par le bilan seulement.** Un sous-dossier par autre PC. Chemin
  absolu, ou relatif au dossier du logiciel ; par défaut `data_extern`. Le drive / NAS est
  **optionnel** : un réglage vide vaut aussi `data_extern` (MP 2026-11-20).
- Usage normal : `dossier_de_sauvegarde` est un sous-dossier de `dossier_externe`
  (`Z:/pointeuse/bureau` et `Z:/pointeuse`) ; le bilan reconnaît alors la sauvegarde de ce
  poste et ne la relit pas.
- Ces réglages se modifient **à la main dans le fichier** (relu à chaud), comme les
  clients et projets. Il n'y a pas de menu dans le logiciel (MP 2026-11-20).

> ⚠ Un dossier de sauvegarde sur le même disque que `data/` (`data_extern/bureau`)
> **ne protège pas d'une panne du disque**. Pour une vraie sauvegarde, viser un drive ou
> un NAS.

---

## Sauvegarde (copie vers le dossier de sauvegarde)

### Quand

Après **chaque enregistrement** dans `data/` : ligne écrite dans le CSV, config modifiée,
événement du journal.

Si la copie échoue (drive déconnecté, NAS éteint, `Z:/` absent), elle est retentée avec
un **délai qui double** à chaque échec (MP 2026-11-20) :

```
échec → 1 min → 2 min → 4 min → 8 min → 16 min → 32 min → 1 h → 1 h → …
```

- Le délai est plafonné à **1 h** (`COPIE_DELAI_MAX_MIN`). Il démarre à 1 min
  (`COPIE_DELAI_INITIAL_MIN`).
- **Un nouvel enregistrement relance une copie tout de suite**, sans attendre la fin du
  délai en cours. Si cette copie échoue aussi, le délai continue de monter là où il en
  était : il ne repart pas à 1 min, sinon un drive absent pendant une journée de pointage
  serait retenté sans cesse.
- **Une copie réussie** remet le délai à 1 min et efface l'état « copie en attente ».
- L'échec est signalé **une seule fois** par une notification, puis par l'info-bulle de
  l'icône (« Sauvegarde en attente depuis 10:42 »). Le pointage n'est jamais bloqué.
- Un minuteur à part (pas le tick de `VERIFICATION_MIN`) programme le prochain essai.

### Quoi

`pointeuse.csv`, `pointeuse_config.toml`, `pointeuse_journal.csv` et
`pointeuse_suivi.jsonl` (CDC `suivi_projets.md`), copiés dans `dossier_de_sauvegarde`.
Un dossier relatif est créé s'il n'existe pas ; un dossier absolu est créé seulement si son
parent existe (un `Z:/` déconnecté ne devient pas un dossier vide sur le disque local).

Ne sont pas copiés : `pointeuse_en_cours.json` (état de travail, remplacé toutes les
5 min) et le verrou.

### Garde-fou : ne pas écraser une sauvegarde plus complète (MP 2026-11-20)

Avant de copier, on compare la taille du `pointeuse.csv` local à celle du
`pointeuse.csv` sauvegardé :

- **local ≥ sauvegarde** (ou pas de fichier sauvegardé) : on écrase les fichiers copiés ;
- **local < sauvegarde** : **aucune copie**, et une notification : « Le CSV sauvegardé dans
  … est plus grand que le CSV local : sauvegarde suspendue ». Ce cas couvre une
  réinstallation ou un `data/` vidé par erreur, qui écraseraient la sauvegarde avec un
  fichier vide.

Pour restaurer, on recopie à la main le dossier de sauvegarde dans `data/`. Il n'y a
pas de restauration automatique.

Cas limite connu : une correction qui raccourcit le CSV (ligne supprimée ou remplacée
dans « Insérer / Journée », description raccourcie) suspend aussi la copie. La copie
reprend dès que le CSV local redevient au moins aussi grand, en pratique à la prochaine
ligne pointée. La notification le dit.

### Écriture sûre

On copie d'abord vers un fichier temporaire dans le dossier de destination, puis on le
renomme. Le client du drive n'envoie ainsi jamais un fichier à moitié écrit.

### Même dossier de sauvegarde sur deux PC

Ce n'est pas protégé : deux PC qui visent le même dossier de sauvegarde s'écrasent l'un
l'autre. C'est une erreur de configuration, à signaler
dans la doc utilisateur (MP 2026-11-20).

---

## Renommer un poste

**À la main, ce n'est pas une fonction du logiciel** (MP 2026-11-20). Le logiciel ne
renomme ni ne supprime jamais un dossier.

Le nom d'un poste, c'est :
- **« local »** pour les données de `data/` du PC sur lequel on est ;
- **le nom de son dossier** dans le dossier externe pour tous les autres postes (= nom
  de leur dossier de sauvegarde).

Procédure (doc utilisateur) :
1. renommer le dossier de sauvegarde (`Z:/pointeuse/<ancien nom>/` → `<nouveau nom>/`) ;
2. mettre le nouveau chemin dans `[donnees] dossier_de_sauvegarde` du PC concerné.

`data/` n'est pas touché : le nom du poste n'apparaît ni dans les fichiers locaux ni
dans le CSV.

Si on change seulement `dossier_de_sauvegarde` dans la config, la prochaine copie crée un nouveau
dossier et l'ancien reste. Les lignes identiques ne sont pas comptées deux fois au bilan
(règle 5 de `fusion.md`), mais il faut supprimer l'ancien dossier à la main. C'est la
même chose pour un PC client renommé après avoir déjà été recopié à la main (voir plus
bas).

---

## Bilan

« Bilan » lit et fusionne (règle existante, CDC `fusion.md`) :

- le `pointeuse.csv` **local** du poste courant (`data/`) ;
- **plus** tous les `<dossier externe>/*/pointeuse.csv`, **sauf** le dossier du poste
  courant (même nom que son dossier de sauvegarde, sans tenir compte de la casse) :
  c'est une copie du local, peut-être en retard.

Si le dossier externe n'existe pas ou est injoignable, le bilan porte sur le seul CSV
local, avec un message qui le précise. La sauvegarde n'est jamais modifiée par le bilan.

- **PC principal = « local »**, modifiable d'un clic comme aujourd'hui.
- Chaque fichier est présenté sous le **nom de son poste** : « local » pour le CSV de
  `data/`, et le nom du dossier pour les autres (`client-a`, `portable`).
- Plus de deux postes : fusion à la chaîne, déjà prévue (règle 8 de `fusion.md`).

## Cas d'un PC client sans accès au drive / NAS

Ce PC sauvegarde dans un dossier local, par exemple `dossier_de_sauvegarde =
"data_extern/client-a"`. Pour le bilan, on copie ce dossier dans le dossier externe du PC
principal (clé USB, mail). Le
bilan le prend en compte sans autre action.

---

## Passage depuis la V0.1

Les fichiers sont aujourd'hui à la racine du dossier du logiciel. Il faut les déplacer
**à la main** dans `data/` (MP est le seul utilisateur). Pas de code de migration, mais
une note dans `VERSION.md`.

---

## Planning

- [x] Step 1 — ADR 005 « données locales dans `data/`, copie vers un dossier externe par poste »
- [x] Step 2 — `chemins.py` : `dossier_logiciel()`, `dossier_donnees()` (= `data/`), `dossier_externe()`, `dossier_poste_externe()` ; verrou dans le dossier du logiciel ; `data_extern/` au `.gitignore`
- [x] Step 3 — Config : section `[donnees]` (`dossier_de_sauvegarde`, `dossier_externe`), lecture et validation
- [x] Step 4 — Copie après chaque enregistrement : garde-fou de taille, écriture sûre (temporaire + renommage), nouvel essai avec délai doublé (1 min → 1 h max, essai immédiat à chaque enregistrement), notification unique en cas d'échec
- [x] Step 5 — Bilan : CSV local (« local ») + `<dossier externe>/*/` sauf le dossier de sauvegarde du poste courant, nom du dossier affiché, principal = local
- [x] Step 6 — `VERSION.md` (fichiers à déplacer dans `data/`) ; doc utilisateur `docs/user/multi_postes.md` (réglage `[donnees]`, drive / NAS, sauvegarde sur le même disque, PC client hors réseau, même dossier de sauvegarde sur deux PC, renommage et restauration à la main)

---

## Présentation technique

### Fichiers impactés (estimation)

| Fichier | Action | Note |
|---------|--------|------|
| `src/pointeuse/settings.py` | modifier | `NOM_DOSSIER_DONNEES = "data"`, `DOSSIER_EXTERNE_DEFAUT = "data_extern"`, liste des fichiers copiés, `COPIE_DELAI_INITIAL_MIN = 1`, `COPIE_DELAI_MAX_MIN = 60` |
| `src/pointeuse/chemins.py` | modifier | Séparer dossier du logiciel / `data/` / dossier externe |
| `src/pointeuse/config.py` | modifier | Section `[donnees]` |
| `src/pointeuse/copie_externe.py` | créer | Copie avec garde-fou de taille, écriture sûre, état « copie en attente » |
| `src/pointeuse/application.py` | modifier | Appel de la copie après chaque enregistrement, minuteur des nouveaux essais, notification et info-bulle |
| `src/pointeuse/bilan.py` | modifier | CSV local + postes externes, noms de postes, principal |
| `src/pointeuse/lecteur/pointeuse.js` | modifier | Plusieurs fichiers préchargés, nom du poste, principal désigné |
| `docs/adr/005-donnees-locales-et-externe.md` | créer | Emplacement des données (004 était déjà pris par le journal de suivi) |
| `.gitignore` | modifier | `data_extern/`, `pointeuse.lock` |

### Impact sur l'existant

- Format de `pointeuse.csv`, du journal et du JSON en cours : **inchangés**.
- `pointeuse_config.toml` : nouvelle section `[donnees]`, facultative (valeurs par défaut
  si elle est absente).
- Emplacement des fichiers : de la racine du logiciel vers `data/` (déplacement manuel).
- Fusion (`fusion.js`) : réutilisée telle quelle.

---

## Décisions prises

- [x] **Un seul utilisateur, plusieurs postes** — MP 2026-11-20
- [x] **Une config par poste, pas de config partagée** — MP 2026-11-20
- [x] **Travail toujours en local dans `data/`**, copie dans un dossier de sauvegarde ; le bilan lit un dossier externe (un sous-dossier par poste) — MP 2026-11-20
- [x] **Rôles séparés** : `dossier_de_sauvegarde` = cible de la copie (vide = pas de sauvegarde), `dossier_externe` = lu par le bilan seulement — MP 2026-11-20
- [x] **Dossier externe par défaut `data_extern/`** dans le dossier du logiciel, réglable (drive, NAS, `Z:/`) — MP 2026-11-20
- [x] **Sauvegarde optionnelle**, après chaque enregistrement — MP 2026-11-20
- [x] **Nouvel essai avec délai doublé** (1, 2, 4, 8… min, plafonné à 1 h), essai immédiat à chaque enregistrement ; s'il échoue, le délai continue de monter (l'essai vient de montrer que le dossier est injoignable) ; délai remis à 1 min après une réussite — MP 2026-11-20
- [x] **Garde-fou** : copie seulement si le CSV local est au moins aussi grand que le CSV sauvegardé — MP 2026-11-20
- [x] **Même dossier de sauvegarde sur deux PC** : non protégé, erreur de config documentée — MP 2026-11-20
- [x] **Bilan = CSV local + postes du dossier externe** (sauf la copie du poste courant) — MP 2026-11-20
- [x] **Pas de détection du double pointage** : les PC ne sont pas en réseau, les chevauchements se voient au bilan — MP 2026-11-20
- [x] **Nom du poste** = « local » pour `data/`, nom du dossier pour les postes externes ; pas de réglage `poste` : c'est le nom du dossier de sauvegarde ; pas de menu — MP 2026-11-20
- [x] **Renommage d'un poste à la main** (dossier + config) : le logiciel ne renomme ni ne supprime jamais de dossier — MP 2026-11-20
- [x] **Passage depuis la V0.1 à la main**, pas de code de migration — MP 2026-11-20

---

## Réalisé (2026-11-20, branche `feature/multi-postes`)

- Étapes 1 à 5 et `VERSION.md` : ADR 005, `chemins.py`, `[donnees]` dans `config.py`,
  `copie_externe.py` branché dans `application.py`, `bilan.py` + lecteur (données du bilan
  en version 3). Tests : `tests/test_multi_postes.py`.
- Ajouts par rapport au plan :
  - `pointeuse_suivi.jsonl` copié avec les autres fichiers, et lu par le bilan pour chaque
    poste (notes nommées par le dossier du poste) ;
  - dossier externe **absolu** absent (`Z:/` déconnecté) : échec et nouvel essai, sans
    créer le dossier sur le disque local ; le dossier relatif par défaut, lui, est créé ;
  - dossier de sauvegarde dans `data/` : refusé, pas de nouvel essai au minuteur (il faut
    corriger la config), info-bulle « dossier de sauvegarde à corriger » ;
  - sauvegarde suspendue (garde-fou) : signalée dans l'info-bulle comme une sauvegarde en
    attente ;
  - pas de fonction `dossier_poste_externe()` dans `chemins.py` : `dossier_sauvegarde()`
    et `dossier_externe()` ;
  - `dossier_externe` vide accepté = `data_extern` (drive / NAS optionnel, MP 2026-11-20) ;
  - **révision MP 2026-11-20** : réglages `dossier_externe` + `poste` remplacés par
    `dossier_de_sauvegarde` (cible, nom = poste) + `dossier_externe` (bilan) ; l'ancienne
    clé `poste` est refusée par la validation de la config.
- Validé sur poste réel par MP (2026-11-20) ; doc utilisateur `docs/user/multi_postes.md`
  écrite au merge (1.1.0).

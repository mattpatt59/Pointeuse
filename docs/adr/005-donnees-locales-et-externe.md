# ADR — Données locales dans `data/`, sauvegarde par poste, bilan sur un dossier externe

**Date :** 2026-11-20
**Statut :** ACCEPTÉ (MP 2026-11-20, décisions du CDC `multi_postes.md`)

---

## Contexte

MP pointe seul sur plusieurs PC (le sien, des PC chez des clients), sans réseau entre eux.
Jusqu'à la V0.1, chaque Pointeuse écrit ses fichiers à côté de son exécutable : pour un
bilan, il faut récupérer les `pointeuse.csv` à la main et les fusionner dans le lecteur
(CDC `fusion.md`).

Contraintes :
- le pointage ne doit **jamais dépendre d'un réseau** (drive déconnecté, NAS éteint) ;
- pas de base de données, formats de fichiers inchangés ;
- une config par poste (la liste des clients ne circule pas sur les PC des clients) ;
- une réinstallation ou un `data/` vidé ne doit pas écraser la sauvegarde.

---

## Options envisagées

| Option | Avantages | Inconvénients |
|--------|-----------|---------------|
| Travailler directement dans le dossier partagé (drive / NAS) | Rien à copier | Pointage bloqué si le dossier est injoignable ; conflits du client de synchro sur un fichier ouvert en continu |
| Synchronisation bidirectionnelle par la Pointeuse | Restauration automatique | Gestion des conflits, des suppressions : beaucoup de code pour un seul utilisateur |
| **Travail en local dans `data/`, copie à sens unique vers un dossier de sauvegarde ; bilan sur un dossier externe** | Le pointage ne dépend de rien ; la Pointeuse ne fait que recopier ; le transport est confié au drive / NAS | Restauration à la main ; un dossier de sauvegarde partagé par deux PC n'est pas détecté |

---

## Décision

**Choix : travail en local dans `data/`, copie à sens unique.**

### Emplacements (`chemins.py`)

- **Dossier du logiciel** : celui de l'exécutable (racine du dépôt en développement). Il
  contient le verrou `pointeuse.lock` (jamais copié) et, par défaut, `data_extern/`.
- **`data/`** : config, CSV, journal des événements, journal de suivi, JSON en cours,
  dossier `bilan/`. Seul endroit lu et écrit pour travailler.
- **Dossier de sauvegarde** : réglage `[donnees] dossier_de_sauvegarde` (absolu, ou
  relatif au dossier du logiciel). Cible de la copie ; **son nom est le nom du poste**.
- **Dossier externe** : réglage `[donnees] dossier_externe` (absolu, ou relatif au dossier
  du logiciel ; `data_extern` par défaut). **Lu par le bilan seulement** : un sous-dossier
  par poste. En usage normal, le dossier de sauvegarde en est un sous-dossier.

### Réglage `[donnees]` de `pointeuse_config.toml`

Format retenu (MP 2026-11-20) :

```toml
# Sauvegarde des données
[donnees]
dossier_de_sauvegarde = ""        # vide = fonctionnement sans sauvegarde automatique
dossier_externe = "data_extern"
```

- `dossier_de_sauvegarde` (texte ; vide = pas de sauvegarde, défaut).
- `dossier_externe` (texte ; vide = `data_extern`, le drive / NAS étant optionnel).
- Section et clés facultatives, autre clé refusée (dont l'ancienne `poste`, d'une première
  version de la branche : le nom du poste n'est plus un réglage).
- Un dossier de sauvegarde dans `data/` n'est **pas** une erreur de config : le pointage
  continue, seule la sauvegarde s'arrête, avec une notification.

### Sauvegarde (`copie_externe.py`)

- **Fichiers** : `settings.FICHIERS_COPIES` = `pointeuse.csv`, `pointeuse_config.toml`,
  `pointeuse_journal.csv`, `pointeuse_suivi.jsonl` (ceux qui existent). Pas le JSON en
  cours ni le verrou.
- **Déclenchement** : à chaque rafraîchissement de l'icône (changement d'état, et toutes
  les `RAFRAICHISSEMENT_AFFICHAGE_S` secondes), si la signature (date de modif + taille)
  des fichiers a changé depuis le dernier essai ; et au démarrage.
- **Garde-fou** : si le `pointeuse.csv` sauvegardé est plus grand que le local, rien n'est
  copié (état « suspendue »). Reprise automatique quand le local redevient au moins
  aussi grand.
- **Écriture sûre** : fichier `*.copie_tmp` dans le dossier de destination, puis
  `os.replace`.
- **Dossier de sauvegarde absolu dont le parent est absent** (lecteur réseau, point de
  montage) : échec, sans le créer (sinon un `Z:/` absent deviendrait un dossier vide sur
  le disque local). Un dossier relatif, lui, est créé avec ses parents.
- **Échec** : nouvel essai par un minuteur à part après 1, 2, 4… min, plafonné à
  `COPIE_DELAI_MAX_MIN` (60). Un nouvel enregistrement relance un essai tout de suite,
  le délai continue de monter ; une réussite le remet à 1 min.
- **Signalement** : une notification à l'entrée dans un état à problème (échec,
  suspendue, dossier dans `data/`), pas une par essai ; l'info-bulle de l'icône indique
  « Sauvegarde en attente depuis HH:MM » tant que le problème dure.

### Bilan (`bilan.py`, lecteur)

- Données du bilan **version 3** (`VERSION_DONNEES_BILAN`, Python et JS) :
  `window.POINTEUSE_CSV = {version, nom, texte, suivi, postes, note}` avec
  `postes = [{poste, csv, suivi}]` (`csv` / `suivi` : `{nom, texte}` ou `null`) et
  `note` = texte à afficher si le dossier externe est introuvable ou illisible.
- Postes lus : chaque sous-dossier du dossier externe contenant un `pointeuse.csv` ou un
  `pointeuse_suivi.jsonl`, **sauf celui qui porte le nom du poste courant** (nom du dossier
  de sauvegarde, comparaison sans casse : c'est une copie, peut-être en retard, de `data/`). Ordre alphabétique.
- Le CSV de `data/` s'appelle **« local »** et reste le PC principal (modifiable d'un clic) ;
  les autres sont nommés par leur dossier, CSV et notes de suivi.

---

## Conséquences

- Passage depuis la V0.1 : fichiers à déplacer **à la main** dans `data/` (note dans
  `VERSION.md`), pas de code de migration.
- Sans réglage, pas de sauvegarde. Une sauvegarde sur le même disque (`data_extern/…`)
  ne protège pas d'une panne du disque : viser un drive / NAS.
- Restauration et renommage d'un poste : à la main (le logiciel ne renomme ni ne
  supprime jamais un dossier).
- Deux PC avec le même dossier de sauvegarde s'écrasent : erreur de config, documentée,
  non détectée.
- `pointeuse.lock` et `data_extern/` ajoutés au `.gitignore`.

# ADR — Journal de suivi des projets : `pointeuse_suivi.jsonl`

**Date :** 2026-11-20
**Statut :** ACCEPTÉ (MP 2026-11-20)

---

## Contexte

Le CDC `suivi_projets.md` ajoute, par projet, un **statut**, une **priorité** et une
**note par période** (jour ou semaine). Ces données sont lues par le bilan : c'est un
nouveau contrat de fichier, d'où cet ADR.

Contraintes :
- une note est un texte **sur plusieurs lignes**, tapé librement (guillemets, `;`…) ;
- pas de base de données (CLAUDE.md) ;
- plusieurs PC non reliés (CDC `multi_postes.md`) : chaque poste écrit son fichier, le
  bilan les réunit ;
- une note se corrige dans la période (la dernière version remplace la précédente) ;
- un plantage pendant l'écriture ne doit pas détruire les notes déjà écrites ;
- `pointeuse.csv` ne change pas.

---

## Options envisagées

| Option | Avantages | Inconvénients |
|--------|-----------|---------------|
| CSV, texte entre guillemets | Même famille que `pointeuse.csv` ; s'ouvre dans Excel | Une ligne de fichier ≠ une note ; un guillemet mal fermé (édition à la main) décale tout ce qui suit |
| CSV, retours à la ligne écrits `\n` | Une ligne = une note | Échappement maison (`\n`, `\\`, `;`) à coder et tester des deux côtés (Python, JS) |
| Un seul fichier JSON (liste), réécrit à chaque note | Format standard | Réécriture complète : un plantage au mauvais moment perd tout ; pas d'ajout simple |
| Un fichier Markdown par projet | Très lisible à la main | Statut / priorité / période à parser dans du texte libre ; fusion multi-postes délicate |
| **JSON Lines : un objet JSON par ligne, ajout en fin de fichier** | Une ligne = une note, quel que soit le texte ; échappement fait par la bibliothèque standard (Python `json`, JS `JSON.parse`) ; ajout seul, rien n'est réécrit ; une ligne abîmée n'affecte qu'elle-même | Ne s'ouvre pas proprement dans Excel (pas son rôle : l'export tableur reste `pointeuse.csv`) |

---

## Décision

**Choix : JSON Lines, ajout seul.** (validé sur le principe, MP 2026-11-20)

### Fichier

- Nom : `pointeuse_suivi.jsonl`, rangé avec `pointeuse.csv` (dossier des données du poste).
- Encodage **UTF-8 sans BOM** (un BOM rendrait la première ligne illisible pour `JSON.parse`).
  Accents écrits tels quels (`ensure_ascii=False`) pour rester lisible dans un éditeur.
- Une ligne = un objet JSON, terminée par `\n`. À la lecture, `\r\n` est accepté et les
  lignes vides sont ignorées.

### Une ligne

```json
{"v": 1, "horodatage": "2026-11-14 18:02:31", "periode": "2026-11-14", "client": "Alpha Industrie", "projet": "Armoire ligne 2", "statut": "en_cours", "priorite": -10, "texte": "Câblage OK.\nDéfaut sur la sortie 3, à reprendre."}
```

| Champ | Type | Contenu |
|-------|------|---------|
| `v` | entier | Version du format de la ligne : `1` |
| `horodatage` | texte | Heure de l'enregistrement, `AAAA-MM-JJ HH:MM:SS` (heure locale). À la seconde : deux versions dans la même minute restent ordonnées |
| `periode` | texte | Période de la note : `AAAA-MM-JJ` (jour) ou `AAAA-Www` (semaine ISO, ex. `2026-W46`) |
| `client` | texte | Nom du client, comme dans `pointeuse.csv` |
| `projet` | texte | Nom du projet, comme dans `pointeuse.csv` (non vide) |
| `statut` | texte | Code : `a_faire`, `en_cours`, `bloque`, `attente_client`, `termine` |
| `priorite` | entier | De `-99` (urgent) à `99` ; `0` par défaut |
| `texte` | texte | Note, retours à la ligne compris ; peut être vide (changement de statut seul) |

- Le statut est stocké par **code** stable ; les libellés affichés (« en attente client »…)
  sont dans `settings.py` et peuvent changer sans toucher au format.
- `terminé ?` n'est **jamais écrit** : il est calculé (projet `termine` avec du temps
  pointé après la note qui l'a terminé).
- Le **poste** n'est pas dans la ligne : c'est le nom du dossier du poste dans le dossier
  externe (CDC `multi_postes.md`), ajouté par le bilan à la lecture.
- Projet **renommé** dans la config : les anciennes notes gardent l'ancien nom, comme les
  lignes de `pointeuse.csv`. Pas de reprise automatique.

### Règles de lecture

1. Lire toutes les lignes valides, trier par `horodatage` (ordre stable).
2. **Note d'une période** = la dernière ligne pour (poste, client, projet, période). Les
   versions précédentes restent dans le fichier mais ne sont plus affichées.
3. **Statut et priorité actuels** d'un projet = ceux de la ligne la plus récente, tous
   postes et toutes périodes confondus.
4. Ligne illisible (JSON invalide, champ manquant, `v` inconnu, statut inconnu) :
   **ignorée**, avec un avertissement (journal de l'appli / bandeau du bilan) ; les autres
   lignes sont lues normalement.
5. `priorite` hors bornes : ramenée dans `[-99, 99]`, avec un avertissement.
6. Changement de réglage jour ↔ semaine : les notes déjà écrites gardent leur `periode`.
   Le bilan affiche une note-jour sur son jour, une note-semaine en tête de sa semaine,
   les deux pouvant coexister.

### Règles d'écriture

- **Ajout seul** : ouverture en mode ajout, la ligne complète (`\n` compris) en un seul
  `write`, puis `flush` + `fsync`. Le fichier n'est jamais réécrit par l'appli.
- Si le fichier ne se termine pas par `\n` (édition à la main), un `\n` est ajouté avant
  la nouvelle ligne.
- Échec d'écriture (fichier verrouillé, disque plein) : message dans la fenêtre Suivi, qui
  **reste ouverte avec le texte saisi** ; rien n'est perdu, l'utilisateur réessaie.
- Pas de suppression ni de purge par l'appli : corriger = écrire une nouvelle version ;
  supprimer = éditer le fichier à la main.

### Transmission au bilan

- `bilan.py` ajoute le contenu brut de chaque `pointeuse_suivi.jsonl` aux données
  locales (`pointeuse_donnees_tmp.js`, ADR 003) ; le lecteur JS applique les règles de
  lecture ci-dessus.
- Changement de structure de `window.POINTEUSE_CSV` → `VERSION_DONNEES_BILAN` passe à `2`
  (Python et JS, vérifié par le test existant).

---

## Conséquences

- Nouveau fichier par poste, copié dans le dossier externe comme les autres (CDC
  `multi_postes.md`).
- `pointeuse.csv` et `pointeuse_config.toml` inchangés : le suivi n'écrit rien dans la
  config (le masquage des projets `termine` est calculé depuis ce fichier).
- Le fichier ne fait que grossir (chaque correction ajoute une ligne) : quelques Ko par
  mois, pas de purge prévue.
- Constantes (nom du fichier, codes et libellés des statuts, bornes de priorité, format
  d'horodatage, version `v`) dans `settings.py`.
- Les mêmes règles de lecture sont codées deux fois (Python pour la fenêtre Suivi, JS pour
  le bilan) : un jeu de lignes d'exemple commun sert aux tests des deux côtés.
- Évolution du format : nouveau champ facultatif → `v` inchangé, lu avec une valeur par
  défaut ; changement de sens d'un champ → `v` incrémenté + mise à jour de cet ADR.
- À l'implémentation : note dans `VERSION.md` (nouveau fichier de données).

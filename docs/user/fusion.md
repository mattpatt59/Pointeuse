# Bilan sur plusieurs PC — fusion des CSV

Chaque poste qui fait tourner la Pointeuse écrit son propre `pointeuse.csv`. Le bilan
peut les réunir **sans compter deux fois le même moment** : on ne travaille pas à deux
endroits à la fois. Ce qui compte, c'est votre temps, pas celui d'un outil qui tourne
seul sur un autre poste.

---

## Charger les fichiers

1. Ouvrir le bilan : menu de l'icône → **Bilan** (ou ouvrir la page et **Lire un CSV**).
2. Dans **Fichiers lus** (à droite), cliquer **＋ Ajouter un autre PC** et choisir le
   `pointeuse.csv` de l'autre poste (copié sur une clé, un partage…). On peut aussi
   glisser le fichier sur la page.
3. Choisir le **PC principal** (bouton radio en face du fichier). Par défaut, c'est le
   CSV ouvert depuis la Pointeuse, sinon le premier fichier chargé.

« Lire un CSV » remplace les fichiers déjà lus ; « ＋ Ajouter un autre PC » en ajoute un.

---

## La règle

- Toutes les lignes du **PC principal** sont gardées telles quelles.
- Celles des autres PC remplissent les trous. La partie qui chevauche une **tâche** du
  principal est retirée :

  ```
  Principal  : A 08:30 → 10:00
  Secondaire : B 09:30 → 11:00
  Fusion     : A 08:30 → 10:00 · B 10:00 → 11:00   (B perd 09:30 → 10:00)
  ```

- Une **pause du principal laisse la place** au travail des autres PC : « pause » sur
  un poste veut souvent dire « je travaillais sur l'autre ». La pause est raccourcie
  d'autant.
- Une ligne présente à l'identique dans les deux fichiers n'est comptée qu'une fois.
  Fusionner deux fois le même fichier ne crée donc pas de doublon.
- Plus de deux fichiers : ils sont fusionnés à la suite, le principal d'abord.

---

## Ce qui a été retiré

Dès qu'un temps d'un autre PC est retiré, un bandeau ⚠ l'indique avec le total, et le
détail se déplie : date, plage, client / projet, durée, et ce qui la recouvre.

**Exporter le rapport** télécharge `fusion_rapport.csv` : les plages retirées, avec le
fichier d'origine (`fichier`) et la ligne qui les recouvre (`recouvert_par`).

---

## Garder le résultat

Le bilan affiché est celui de la fusion. **Télécharger le CSV fusionné** donne
`pointeuse_fusion.csv`, au format exact de `pointeuse.csv`.

Les fichiers d'origine ne sont jamais modifiés. Pour adopter la fusion sur un poste :
fermer la Pointeuse, remplacer `pointeuse.csv` par `pointeuse_fusion.csv` (renommé),
relancer.

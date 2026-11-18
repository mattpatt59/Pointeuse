# CDC — Fusion de deux CSV (PC principal + PC secondaire)

**Date demande :** 2026-11-17
**Date création :** 2026-11-17
**Statut :** IMPLÉMENTÉ

---

## Contexte

On peut pointer sur deux PC (bureau + portable, ou deux postes qui font tourner chacun
un agent IA). Chaque Pointeuse écrit son propre `pointeuse.csv`. Pour un bilan juste, il
faut réunir les deux fichiers **sans compter deux fois le même moment** : on ne peut pas
être à deux endroits en même temps.

Avant ce CDC, le lecteur de bilan acceptait plusieurs fichiers mais les **additionnait**
(seuls les doublons exacts étaient retirés) : deux plages qui se chevauchent étaient
comptées deux fois.

Ce qu'on compte, c'est le **temps d'attention** de la personne, pas le travail réalisé
en parallèle par des outils (agents IA) : le temps où un agent tourne seul est un coût
machine, pas des heures (MP 2026-11-17).

---

## Questions ouvertes

- [x] **Pauses du PC principal** : une `PAUSE` du principal veut surtout dire « je ne
  travaillais pas sur ce PC ». Proposition : une pause du principal **laisse la place** au
  travail du secondaire ; seules les tâches du principal gagnent. Sinon, règle stricte :
  la pause du principal efface aussi le travail du secondaire.
  **Implémenté selon la proposition** (`CFG.fusionPauseCede = true` dans `lecteur/pointeuse.js`) ;
  la règle stricte = passer la constante à `false` (les deux cas sont testés). La pause du
  principal est alors raccourcie du travail gardé du secondaire, pour ne pas compter le même
  moment en pause et en travail.

> 💬 MP (2026-11-17) : validé — les pauses comptent moins que le travail à facturer, et on peut
> très bien avoir mis « pause » sur A pour aller travailler sur B. La fusion se fait entre
> deux CSV de créneaux de temps.

---

## Règle de fusion

1. On charge deux fichiers et on désigne le **PC principal**. Par défaut, c'est le CSV
   ouvert depuis la Pointeuse (menu « Bilan ») ; sinon, le premier fichier chargé. Le
   choix se change d'un clic (bouton radio « PC principal » dans « Fichiers lus »).
   « Lire un CSV » remplace les données comme avant ; « ＋ Ajouter un autre PC » ajoute un
   fichier à ceux déjà lus.
2. Toutes les lignes du principal sont gardées telles quelles.
3. Les lignes du secondaire sont **découpées** par les lignes du principal : la partie qui
   chevauche est retirée, le reste est gardé (même logique que l'insertion de la Pointeuse).

   ```
   Principal  : A 08:30 → 10:00
   Secondaire : B 09:30 → 11:00
   Fusion     : A 08:30 → 10:00 · B 10:00 → 11:00   (B perd 09:30 → 10:00)
   ```

4. Le secondaire remplit les trous du principal (matin sur un PC, après-midi sur l'autre).
5. Une ligne identique dans les deux fichiers est entièrement recouverte : elle disparaît
   du secondaire, sans être signalée comme temps retiré (« N ligne(s) déjà dans le
   principal »). Refusionner le même fichier ne crée donc pas de doublon.
6. Une **pause** du secondaire est découpée par toutes les lignes du principal ; une
   pause retirée n'est pas signalée (ce n'est pas du temps travaillé).
7. `duree_min` des lignes découpées est recalculée.
8. Plus de deux fichiers : fusion à la chaîne, (principal + B) puis + C.

## Avertissement : temps retirés du PC secondaire

Dès qu'un temps du secondaire est retiré, le lecteur **prévient** (MP 2026-11-17) :

```
⚠ 3 plages du PC secondaire (pointeuse_portable.csv) recouvertes par le PC principal — 1 h 05 retirées
  17/11  09:30 → 10:00  client-b / projet-b          0 h 30   (recouvert par exemple-client / projet-x)
  17/11  14:10 → 14:25  client-b / projet-b / tests  0 h 15
  18/11  08:00 → 08:20  autre-client / projet-c      0 h 20
                                              [ Exporter le rapport ]
```

- Le bandeau reste visible tant que les deux fichiers sont chargés ; le détail se déplie.
- « Exporter le rapport » → `fusion_rapport.csv` (mêmes colonnes que le CSV + colonnes
  `fichier` — d'où le temps est retiré, utile au-delà de deux fichiers — et `recouvert_par`).
  C'est un fichier à part : `pointeuse.csv` ne change pas de format.

## Résultat

- Le bilan affiché est celui de la fusion.
- Bouton « Télécharger le CSV fusionné » → `pointeuse_fusion.csv`, au format exact de
  `pointeuse.csv` (UTF-8 avec BOM, `;`).
- Les fichiers d'origine ne sont **jamais modifiés** (le navigateur ne peut pas écrire sur
  le disque). Pour adopter la fusion : fermer la Pointeuse, remplacer `pointeuse.csv` par
  `pointeuse_fusion.csv`, relancer.

---

## Planning

- [x] Step 1 — Pauses du principal : elles cèdent au travail du secondaire (MP 2026-11-17)
- [x] Step 2 — Algorithme de fusion en JS (`lecteur/fusion.js`, fonctions pures : principal, secondaire → lignes gardées + lignes retirées), testé sur les cas de recouvrement par `tests/test_fusion.py` avec le moteur JS de Qt (`QJSEngine`, déjà dans PySide6 : pas de `node`)
- [x] Step 3 — Lecteur (validé sur poste réel, MP 2026-11-18) : choix du PC principal, bandeau d'avertissement + rapport, export du CSV fusionné ; texte « Plusieurs fichiers sont additionnés » remplacé
- [x] Step 4 — Doc utilisateur : `docs/user/fusion.md`

---

## Présentation technique

### Fichiers impactés

| Fichier | Action | Note |
|---------|--------|------|
| `src/pointeuse/lecteur/fusion.js` | créé | Algorithme pur (`fusionner`, `fusionnerFichiers`), sans page web |
| `src/pointeuse/lecteur/pointeuse.js` | modifié | `chargerTextes(entrees, ajouter)` + `fusionnerFichiersCharges()` ; bandeau `htmlFusion()` ; choix du principal et « Ajouter un autre PC » ; exports `pointeuse_fusion.csv` et `fusion_rapport.csv` |
| `src/pointeuse/lecteur/index.html` | modifié | Charge `fusion.js` avant `pointeuse.js` |
| `src/pointeuse/lecteur/pointeuse.css` | modifié | Bandeau (alerte `al-warn` de la charte), choix du principal |
| `src/pointeuse/bilan.py` | modifié | `fusion.js` copié avec le lecteur |
| `tests/test_fusion.py` | créé | Tests de l'algorithme (QJSEngine) |

---

## Intégration

### Point d'appel

Lecteur de bilan (menu « Bilan » de la Pointeuse, ADR 003), quand un second fichier est
ajouté (bouton ou glisser-déposer).

### Dépendances

- Format de `pointeuse.csv` (contrat, CDC `pointeuse.md`) : lu et écrit sans changement.
- ADR 003 : le lecteur reste hors ligne, dans ce dépôt.

### Impact sur l'existant

- Le chargement de plusieurs fichiers ne les additionne plus : le chevauchement est retiré
  du secondaire. Changement de comportement visible → note dans `VERSION.md`.

---

## Décisions prises

- [x] **Principe** : un PC principal ; tout temps du secondaire qui chevauche le principal est retiré (on ne peut pas être à deux endroits à la fois) — MP 2026-11-17
- [x] **On compte l'attention**, pas le travail parallèle des agents IA ; pas de lignes simultanées dans le CSV — MP 2026-11-17
- [x] **Avertissement** : le lecteur prévient que des temps ont été retirés du PC secondaire, avec le détail — MP 2026-11-17
- [x] **Où** : dans le lecteur de bilan (hors ligne), fichiers d'origine jamais modifiés, export du CSV fusionné — MP 2026-11-17
- [x] **Découpage** plutôt que suppression de la ligne entière : seule la partie recouverte est retirée — proposé, cohérent avec « une chose à la fois »
- [x] **Pauses du principal** : elles laissent la place au travail du secondaire (`CFG.fusionPauseCede = true`) — le travail à facturer prime ; « pause » sur A peut vouloir dire « je bosse sur B » — MP 2026-11-17
- [x] **Tests sans `node`** : le moteur JS de Qt (`QJSEngine`, dans PySide6) exécute `fusion.js` depuis pytest — aucune dépendance ajoutée

---

## Notes

- Si les allers-retours entre projets deviennent trop fréquents pour pointer à la main, piste
  écartée pour l'instant : une option « partager » dans Insérer (une plage répartie entre
  deux projets, en lignes successives — sans changer le CSV).
- Pour savoir quelle part du travail est faite avec l'IA : une tâche ou un mot `IA` dans la
  description suffit, filtrable dans le bilan.

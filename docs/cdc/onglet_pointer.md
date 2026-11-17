# CDC — Onglet « Pointer » : Modifier, Stop, Repas, boutons rapides

**Date demande :** 2026-11-17
**Date création :** 2026-11-17
**Statut :** PARTIELLEMENT IMPLÉMENTÉ

---

## Contexte

L'onglet « Pointer » n'avait que deux boutons, « Démarrer » et « Pause » / « Reprendre ».
Il manquait trois choses :

- un moyen de **corriger la tâche en cours** sans la couper (on lance « Client A », puis
  on précise le projet ou la description) ;
- un **Stop** (« j'ai fini ») qui n'écrive pas de pause, et un **Repas** distinct d'une
  pause ordinaire ;
- des **boutons rapides** pour les clients et tâches réguliers : un clic et c'est parti.

---

## Disposition

```
┌─[ Pointer ]─[ Insérer / Journée ]─[ À propos ]─┐
│  ● En cours depuis 09:00   0 h 25   │
│  Client      [ Delta Services   ▾]  │
│  Projet      [                  ▾]  │  ← en rouge : projet à compléter
│  Tâche       [ —                ▾]  │
│  Description [                    ] │
│  [ ✎ Modifier ]   [ ▶ Démarrer ]    │
│  [ ❚❚ Pause ] [ ■ Stop ] [ Repas ]  │
│  ─── Boutons rapides ───            │
│  [ Alpha – Armoire ] [ Bêta – rout… ]│
│  [ Gamma Énergie – … ] [ Delta Serv… ]│
│  □ Afficher les projets masqués     │
└─────────────────────────────────────┘
```

---

## Règles

### Ligne 1 — la tâche

- **Modifier** : applique le formulaire (client, projet, tâche, description) à la tâche
  en cours **sans la couper** : l'heure de début est gardée.
  - Client obligatoire ; le projet peut rester vide (il reste alors en rouge).
  - Un nom nouveau est ajouté à la config, comme avec Démarrer.
  - Grisé quand aucune tâche n'est en cours (rien, ou pause).
- **Démarrer** : inchangé — clôture la ligne en cours et démarre la tâche du formulaire
  (client et projet obligatoires).

### Ligne 2 — s'arrêter

- **Pause** / **Reprendre** : inchangé.
- **Stop** : clôture la ligne en cours, **sans ouvrir de pause** (fin de journée). Grisé
  quand rien n'est en cours.
- **Repas** : une pause avec la description « Repas » (`settings.DESCRIPTION_REPAS`).
  - Ligne CSV : client `PAUSE`, description `Repas` — format inchangé.
  - Déjà en pause : la pause continue et prend la description « Repas » (pas de coupure).
  - Reprendre après un repas relance la dernière tâche, comme après une pause.
  - Le bandeau affiche « En pause (Repas) depuis 12:00 ».

### Boutons rapides `[[raccourcis]]`

Déclarés dans `pointeuse_config.toml`, un bloc par bouton, dans l'ordre d'affichage :

```toml
# client obligatoire ; projet, tache, description facultatifs (pas de tâche sans projet) ;
# nom = texte du bouton (par défaut « client – projet – tâche »).
[[raccourcis]]
nom = "Alpha – Armoire"
client = "Alpha Industrie"
projet = "Armoire ligne 2"

[[raccourcis]]
client = "Delta Services"          # client seul
```

- **Un clic démarre tout de suite**, même avec le client seul (MP 2026-11-17).
- **Client seul** : la ligne démarre avec un projet vide ; le champ Projet est **en
  rouge** tant que la tâche tourne sans projet. On le complète avec **Modifier**. Si on
  ne le complète pas, la ligne est écrite sans projet (le bilan l'affiche « sans projet »).
- **Client ou projet inconnu** : créé dans la config comme une saisie libre ; on corrige
  ensuite le fichier si besoin (MP 2026-11-17). Pas de contrôle « doit exister ».
- Le bouton de la **tâche déjà en cours** ne fait rien (la description saisie n'est pas
  effacée), sauf si le raccourci porte sa propre description.
- 2 colonnes (`settings.COLONNES_RACCOURCIS`), 8 boutons au plus
  (`settings.NOMBRE_MAX_RACCOURCIS`, au-delà la config est signalée en erreur). Un texte
  trop long est coupé « … » ; l'info-bulle donne le détail. `nom` sert à donner un texte court.
- Sans `[[raccourcis]]`, la zone « Boutons rapides » n'apparaît pas.
- Le fichier créé au premier lancement contient deux boutons d'exemple, actifs :
  « Administratif » (Perso / administratif) et « 26-01_routage »
  (Client A / 26-01-Projet / Routage) — MP 2026-11-17.
- La liste est relue avec la config (à l'ouverture du panneau).

**Erreurs de config signalées** (message clair, la dernière config valide est gardée) :
`[raccourcis]` à un seul crochet, client absent, client `PAUSE`, projet `visible`, tâche
sans projet, clé inconnue, valeur qui n'est pas un texte, plus de 8 boutons.

---

## Planning

- [x] Step 1 — Moteur : `modifier()`, `pause(description)`, `demarrer(..., projet_obligatoire=False)` ; Stop = `arreter()`
- [x] Step 2 — Config : `[[raccourcis]]` (lecture, contrôles), `ajouter(..., projet_obligatoire=False)`, deux boutons d'exemple dans le fichier par défaut
- [x] Step 3 — Interface : deux lignes de boutons, boutons rapides, projet en rouge — vérifié par capture hors écran
- [ ] Step 4 — Validation sur poste réel (Linux, Windows)
- [ ] Step 5 — Doc utilisateur (`docs/user/`) une fois implémenté

---

## Présentation technique

### Fichiers impactés

| Fichier | Action | Note |
|---------|--------|------|
| `src/pointeuse/settings.py` | modifier | `NOMBRE_MAX_RACCOURCIS`, `COLONNES_RACCOURCIS`, `DESCRIPTION_REPAS`, couleurs rouge et bouton Stop (charte §C, §E) |
| `src/pointeuse/config.py` | modifier | `Raccourci`, `raccourcis()`, contrôle de `[[raccourcis]]`, projet facultatif dans `ajouter()` |
| `src/pointeuse/moteur.py` | modifier | `modifier()`, description de pause, projet facultatif au démarrage |
| `src/pointeuse/affichage.py` | modifier | « En pause (Repas) » ; libellé sans les parties vides |
| `src/pointeuse/panneau.py` | modifier | Boutons Modifier / Stop / Repas, zone des boutons rapides, projet en rouge |
| `src/pointeuse/style.py` | modifier | `#stop`, `#raccourci`, `[a_completer="true"]` |
| `tests/test_config.py`, `test_moteur.py`, `test_interface.py` | modifier | Raccourcis, Modifier, Stop, Repas, client seul |

### Format du CSV

Inchangé (pas d'ADR) : un repas est une ligne `PAUSE` avec une description, un raccourci
« client seul » non complété donne une ligne au projet vide — deux cas que le format et
le lecteur de bilan acceptaient déjà.

---

## Décisions prises

- [x] **Disposition** : deux lignes — Modifier / Démarrer, puis Pause / Stop / Repas — MP 2026-11-17
- [x] **Pause et Stop séparés** : on a la place, et c'est plus simple à expliquer — MP 2026-11-17
- [x] **Repas** : juste une pause avec le mot « Repas » (pas de réglage dans le TOML) — MP 2026-11-17
- [x] **Format** : liste `[[raccourcis]]` (ordre et libellé libres) plutôt qu'un drapeau sur les projets — MP 2026-11-17
- [x] **Client seul** : un clic démarre, le projet vide est signalé en rouge, à compléter avec Modifier — MP 2026-11-17
- [x] **Boutons d'exemple** dans le fichier par défaut : « Administratif » et « 26-01_routage » — MP 2026-11-17
- [x] **Noms inconnus** dans un raccourci : créés comme une saisie, l'utilisateur corrige — MP 2026-11-17

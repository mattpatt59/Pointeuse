# Onglet « Pointer »

L'onglet affiché à l'ouverture du panneau. En haut, l'état : « En cours depuis 09:00 »,
« En pause depuis 12:00 » ou « En pause (Repas) depuis 12:00 », avec la durée.

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
│  □ Afficher les projets masqués     │
└─────────────────────────────────────┘
```

Rien ne change tant qu'on ne clique pas sur un bouton : on peut remplir le formulaire
sans couper la tâche en cours.

---

## Les boutons

| Bouton | Effet |
|---|---|
| **▶ Démarrer** | Clôture la ligne en cours et démarre la tâche du formulaire. Client et projet obligatoires. |
| **✎ Modifier** | Applique le formulaire à la tâche en cours **sans la couper** : l'heure de début est gardée. Le projet peut rester vide. Grisé si aucune tâche n'est en cours. |
| **❚❚ Pause** / **Reprendre** | Clôture la tâche et ouvre une pause. Reprendre clôture la pause et relance la dernière tâche (description vide). |
| **■ Stop** | Clôture la ligne en cours, sans ouvrir de pause : fin de journée. Grisé si rien n'est en cours. |
| **Repas** | Une pause notée « Repas ». Déjà en pause : la pause devient « Repas », sans coupure. |

Un client, un projet ou une tâche tapé pour la première fois est ajouté à la config,
avec Démarrer comme avec Modifier.

---

## Boutons rapides

Pour les tâches régulières : **un clic démarre la tâche tout de suite**.

Ils se déclarent dans `pointeuse_config.toml` (menu de l'icône → Ouvrir la config), un
bloc `[[raccourcis]]` par bouton, dans l'ordre d'affichage :

```toml
[[raccourcis]]
nom = "Alpha – Armoire"        # texte du bouton (facultatif)
client = "Alpha Industrie"     # obligatoire
projet = "Armoire ligne 2"     # facultatif
tache = "Câblage"              # facultatif, demande un projet
description = "Lot 3"          # facultatif

[[raccourcis]]
client = "Delta Services"      # client seul
```

- Sans `nom`, le bouton affiche « client – projet – tâche ». Un texte trop long est
  coupé par « … » ; l'info-bulle donne le détail.
- **8 boutons au plus**, sur deux colonnes. Sans `[[raccourcis]]`, la zone n'apparaît pas.
- **Client seul** : la tâche démarre sans projet et le champ Projet passe **en rouge**.
  Choisir le projet puis **Modifier** : l'heure de début est conservée. Sans
  correction, la ligne est écrite sans projet (le bilan l'affiche « sans projet »).
- Un client ou projet inconnu est ajouté à la config, comme une saisie libre.
- Cliquer le bouton de la tâche déjà en cours ne fait rien (sauf si le raccourci porte
  sa propre description).
- La liste est relue à chaque ouverture du panneau.

Le fichier créé au premier lancement contient deux exemples : « Administratif »
(Perso / administratif) et « 26-01_routage » (Client A / 26-01-Projet / Routage).
À adapter ou supprimer.

En cas d'erreur dans les raccourcis (`[raccourcis]` à un seul crochet, client absent ou
`PAUSE`, tâche sans projet, clé inconnue, plus de 8 boutons…), un message l'explique
et la dernière configuration valide reste utilisée.

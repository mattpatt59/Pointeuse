# Suivi des projets — statut, priorité, notes

Le CSV dit **combien de temps** a été passé sur un projet. Le suivi dit **où il en est** :
un statut, une priorité et une note par période (ce qui marche, ce qui bloque). Le temps
n'est jamais ressaisi, il vient des pointages.

---

## Ouvrir la fenêtre Suivi

- menu de l'icône → **Suivi des projets…** ;
- onglet Pointer → bouton **Suivi…** ;
- au **Stop** d'une tâche, si le projet n'a pas encore de note sur la période : la
  fenêtre s'ouvre directement sur ce projet. La fermer suffit pour ne rien écrire.

---

## La fenêtre

À gauche, la liste des projets, **triés par priorité**. La case **Afficher les projets
terminés ou masqués** fait réapparaître ceux qui sont cachés.

À droite, pour le projet choisi :

- **Message du …** : la note de la période précédente, en lecture seule, pour écrire
  la suite sans la chercher ;
- **Travail en cours** : la note de la période choisie (aujourd'hui par défaut), avec
  **Statut** et **Priorité**, puis **Enregistrer**. Changer la date permet d'écrire la
  note d'un jour passé ;
- **Historique** : période, temps pointé, statut, début de la note.

### Une note par période

Il y a **une note par projet et par période** : la dernière enregistrée. Écrire à 9 h,
puis corriger à 16 h : seule la version de 16 h reste.

La période est le **jour** par défaut, ou la **semaine** (réglage `periode_note`, voir
plus bas).

### Statut et priorité

| Statut | Effet |
|---|---|
| à faire, en cours, bloqué, en attente client | Projet affiché normalement |
| terminé | Projet caché dans la fenêtre Suivi **et** dans les listes de l'onglet Pointer |
| terminé ? | Calculé, jamais choisi : du temps a été pointé sur un projet terminé après la note qui l'a terminé. Le projet réapparaît |

`terminé ?` n'est pas forcément une réouverture (une question du client, par exemple).
Pour trancher, écrire une note : `terminé` le confirme, un autre statut le rouvre.

**Priorité** : un nombre de **-99 (le plus urgent) à +99**, 0 par défaut. Le plus petit
passe en premier. On peut très bien n'utiliser que deux ou trois valeurs.

Un projet terminé reste utilisable : taper son nom dans l'onglet Pointer permet de
pointer dessus. L'onglet Journée et la fenêtre de retour d'absence gardent tous les
projets.

---

## Dans le bilan

Menu de l'icône → **Bilan**, puis l'onglet **Suivi des projets** en tête de page.

```
Alpha Industrie — Armoire ligne 2           Priorité -10      Statut : BLOQUÉ
  Statut en cours (15/11) : Attente retour client sur le schéma.

  15/11/2026   3 h 20   Attente retour client sur le schéma.
  14/11/2026   1 h 05   Câblage OK.
                        Défaut sur la sortie 3, à reprendre.
  13/11/2026   2 h 10
```

- Un projet apparaît s'il a du temps **ou** une note sur la période.
- Historique sur la **période du bilan**, ou **depuis le …** une date choisie.
- Toujours **une ligne par jour**. En mode semaine, la note de la semaine s'affiche en
  tête de ses jours.
- Les filtres clients du bilan s'appliquent.
- **Imprimer** : un projet par page.

Dans l'onglet **Temps**, le tableau Répartition montre aussi la priorité et le statut
des projets qui ont une note.

### Plusieurs PC

Les notes des autres postes sont lues avec leurs pointages (voir
[multi_postes.md](multi_postes.md)), ou ajoutées à la main avec **＋ Ajouter un autre PC**.

- Deux postes ont une note sur la même période pour le même projet : **les deux** sont
  affichées, chacune avec le nom de son poste.
- Statut et priorité : ceux de la note la plus récente, tous postes confondus.
- Une note identique lue deux fois n'est comptée qu'une fois.

La fenêtre Suivi, elle, ne montre que les notes du PC sur lequel on est.

---

## Réglages — section `[suivi]` de `pointeuse_config.toml`

```toml
[suivi]
periode_note = "jour"     # "jour" ou "semaine" : une note par jour ou par semaine
rappel_au_stop = true     # au Stop, proposer la note du projet arrêté s'il n'en a pas
```

---

## Le fichier `pointeuse_suivi.jsonl`

Dans `data/`. Une ligne par note enregistrée, au format JSON. Chaque enregistrement
**ajoute** une ligne, le fichier n'est jamais réécrit. Il se lit dans n'importe quel
éditeur, mais il n'est pas fait pour un tableur.

Une ligne abîmée par une modification à la main est ignorée, avec un avertissement, sans
perdre les autres.

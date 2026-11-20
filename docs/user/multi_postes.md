# Plusieurs PC — sauvegarde et bilan commun

Chaque PC pointe **en local**, dans son dossier `data/`, sans jamais dépendre d'un réseau.
Deux réglages permettent en plus :

- de **sauvegarder** `data/` dans un dossier (drive, NAS, `Z:/`…) ;
- de faire un **bilan commun** avec les sauvegardes des autres PC.

La Pointeuse ne synchronise rien : elle recopie des fichiers dans un dossier. Si ce
dossier est sur un drive ou un NAS, c'est lui qui les transporte.

---

## Réglage — section `[donnees]` de `pointeuse_config.toml`

```toml
# Sauvegarde des données
[donnees]
dossier_de_sauvegarde = ""        # vide = fonctionnement sans sauvegarde automatique
dossier_externe = "data_extern"   # bilan : un sous-dossier par autre PC
```

Chemins absolus (`Z:/pointeuse/bureau`, `//nas/pointeuse/bureau`), ou relatifs au
dossier de la Pointeuse. Le fichier est relu dès qu'on l'enregistre.

| Réglage | Rôle | Vide |
|---|---|---|
| `dossier_de_sauvegarde` | Dossier où `data/` est recopié. **Son nom est le nom du poste** | Pas de sauvegarde (défaut) |
| `dossier_externe` | Lu par le bilan : un sous-dossier par PC | `data_extern`, dans le dossier de la Pointeuse |

### Exemple : trois PC et un drive monté en `Z:`

```
Z:/pointeuse/
  bureau/      ← sauvegarde du PC « bureau »
  atelier/     ← sauvegarde du PC « atelier »
  portable/    ← sauvegarde du PC « portable »
```

Sur le PC du bureau :

```toml
[donnees]
dossier_de_sauvegarde = "Z:/pointeuse/bureau"
dossier_externe = "Z:/pointeuse"
```

Sur les autres, seul le dernier dossier change (`atelier`, `portable`).

---

## La sauvegarde

Après chaque enregistrement (ligne pointée, config modifiée, note de suivi…), ces
fichiers sont recopiés dans le dossier de sauvegarde :

`pointeuse.csv`, `pointeuse_config.toml`, `pointeuse_journal.csv`,
`pointeuse_suivi.jsonl`.

- **Le pointage n'est jamais bloqué**, même si le dossier est injoignable.
- **Drive déconnecté, `Z:` absent** : une notification, une seule. L'info-bulle de
  l'icône affiche ensuite « Sauvegarde en attente depuis 10:42 ». La copie est retentée
  après 1, 2, 4, 8… minutes, puis toutes les heures, et à chaque nouvel enregistrement.
  Dès qu'elle réussit, l'avertissement disparaît.
- Un dossier relatif est créé s'il n'existe pas. Pour un chemin absolu, le dossier
  parent doit exister (`Z:/pointeuse`) : un lecteur absent ne devient pas un dossier
  vide sur le disque local.
- Un dossier de sauvegarde placé dans `data/` est refusé : notification, et « dossier
  de sauvegarde à corriger » dans l'info-bulle.

### Protection contre l'écrasement

Si le `pointeuse.csv` sauvegardé est **plus grand** que celui de `data/`, rien n'est
copié : c'est le signe d'une réinstallation ou d'un `data/` vidé par erreur, qui
écraserait une sauvegarde plus complète. Une notification le signale.

Après une correction qui raccourcit le CSV (ligne supprimée ou remplacée dans
« Insérer / Journée »), la sauvegarde attend aussi. Elle reprend toute seule dès que le
CSV redevient au moins aussi grand, en pratique à la ligne pointée suivante.

> ⚠ Une sauvegarde sur le même disque que `data/` (`data_extern/bureau`) ne protège pas
> d'une panne du disque. Pour une vraie sauvegarde, viser un drive ou un NAS.

---

## Le bilan commun

Menu de l'icône → **Bilan** lit :

- les fichiers de `data/` de ce PC, sous le nom **« local »** ;
- chaque sous-dossier de `dossier_externe`, sous **le nom du dossier** (`atelier`,
  `portable`) : pointages et notes de suivi.

Le dossier qui porte le nom de ce poste (sa propre sauvegarde) n'est pas relu : c'est
une copie de `data/`, peut-être en retard.

Les pointages sont fusionnés autour du **PC principal**, « local » par défaut et
modifiable d'un clic dans **Fichiers lus**. La règle de fusion est décrite dans
[fusion.md](fusion.md) ; celle des notes dans [suivi_projets.md](suivi_projets.md).

Si `dossier_externe` est introuvable, le bilan porte sur ce PC seul et le dit dans
**Fichiers lus**. Le bilan ne modifie jamais les sauvegardes.

---

## Cas particuliers

### PC client sans accès au drive

Lui donner une sauvegarde locale, par exemple
`dossier_de_sauvegarde = "data_extern/client-a"`. Pour le bilan, copier ce dossier
`client-a/` dans le dossier externe du PC principal (clé USB, mail…) : il est pris en
compte sans autre action.

### Deux PC sur le même dossier de sauvegarde

Ils s'écrasent l'un l'autre, sans avertissement. Chaque PC doit avoir **son** dossier.

### Renommer un poste

À la main :

1. renommer le dossier de sauvegarde (`Z:/pointeuse/bureau` → `Z:/pointeuse/maison`) ;
2. mettre le nouveau chemin dans `dossier_de_sauvegarde` de ce PC.

Si l'on change seulement le réglage, une nouvelle sauvegarde est créée et l'ancienne
reste : la supprimer à la main. Ses lignes ne sont de toute façon pas comptées deux fois
au bilan.

### Restaurer

Pointeuse fermée, recopier le contenu du dossier de sauvegarde dans `data/`, puis
relancer.

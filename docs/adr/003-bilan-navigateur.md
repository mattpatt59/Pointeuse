# ADR — Bilan dans le navigateur : lecteur livré avec l'appli, données en script local

**Date :** 2026-11-17
**Statut :** ACCEPTÉ (MP 2026-11-17 : page locale générée par la Pointeuse, CSV converti en `.js`, un seul dépôt, tout hors ligne, licence MIT)

---

## Contexte

Le lecteur de bilan du CSV (graphe, répartition client / projet / tâche, export) existe
en page HTML/JS, publiée sur `t-elec.fr/outils/pointeuse/`. Le menu de l'icône doit
l'ouvrir **avec le fichier déjà chargé**, sans que l'utilisateur ait à le chercher.

Contraintes : une page web ne peut pas lire un fichier du disque sans action de
l'utilisateur ; la promesse affichée est « aucune donnée envoyée » ; MP veut **un seul
dépôt** pour le lecteur (pas de contrat à tenir entre deux dépôts).

---

## Options envisagées

| Option | Avantages | Inconvénients |
|--------|-----------|---------------|
| Données dans l'adresse (`t-elec.fr/…#d=<CSV compressé>`) | Rien à livrer avec l'appli ; le `#` n'est pas envoyé au serveur | Taille limitée (Windows peut tronquer une adresse longue) ; demande internet |
| Petit serveur local dans l'appli, lu par la page du site | Pas de limite de taille | Chrome demande une autorisation « réseau local » ; un serveur de plus |
| Page locale qui charge le code depuis t-elec.fr + données en `.js` local | Lecteur à jour sans release | Contrat entre deux dépôts (squelette HTML ↔ JS du site) ; demande internet |
| **Lecteur livré avec l'appli, copié à côté du CSV + données en `.js` local** | Un seul dépôt ; aucun réseau, hors connexion ; pas de limite de taille ; tous navigateurs | Le site publie une copie à resynchroniser |

---

## Décision

**Choix : lecteur livré avec l'appli, données en `.js` local.**

- **Source unique** du lecteur : `src/pointeuse/lecteur/` (`index.html`, `pointeuse.css`,
  `fusion.js`, `pointeuse.js`, `logo.png`), utilisé hors ligne : liens vers le
  site en adresses absolues, logo dans le dossier.
- Menu de l'icône « **Bilan** » (`bilan.py`) : copie le lecteur dans
  `<dossier du programme>/bilan/`, convertit le CSV en
  `pointeuse_donnees_tmp.js` → `window.POINTEUSE_CSV = {version, nom, texte, suivi}`
  (`suivi` = `{nom, texte}` du journal de suivi, ou `null` : ajouté en version 2, ADR 004)
  (`json.dumps`, tout est échappé), remplace le marqueur `<!-- POINTEUSE:DONNEES -->` de
  la page par la balise `<script>` correspondante, puis ouvre la page (`file://`).
  Une page locale ne peut pas *lire* un fichier voisin, mais peut *charger un script*
  voisin : c'est ce qui fait passer les données.
- `pointeuse.js` charge `window.POINTEUSE_CSV` au démarrage s'il existe et si sa
  `version` est connue (`DONNEES_LOCALES_VERSION` = `settings.VERSION_DONNEES_BILAN`,
  vérifié par un test).
- Tout est réécrit à chaque clic : le bilan reflète le CSV du moment.

---

## Conséquences

- Remplace la décision du CDC « pas de lecteur HTML local, bilan via t-elec.fr ».
- La tâche en cours n'apparaît pas dans le bilan (elle n'est écrite dans le CSV qu'à sa fin).
- `pointeuse_donnees_tmp.js` contient les mêmes données que le CSV, au même endroit :
  pas de nouvelle exposition. Il n'est pas effacé après ouverture (le navigateur le
  charge de façon asynchrone).
- Exécutable : `construire.py` ajoute `lecteur/` (`--add-data`) ; paquet Python :
  `package-data` dans `pyproject.toml`.
- **Tout hors ligne** : le lecteur ne vit que dans ce dépôt. La version mise en ligne sur
  `t-elec.fr/outils/pointeuse/` (projet site_web, avant cet ADR) est retirée du site
  (MP 2026-11-17).
- Un changement de `window.POINTEUSE_CSV` = incrémenter la version des deux côtés.
- **Licence** : le lecteur suit la licence du projet, **MIT** (`LICENSE`) — MP 2026-11-17.
  Le logo T-Elec (`lecteur/logo.png`) reste la marque de T-Elec : la licence MIT couvre le code,
  pas le logo.

"""Fichier de configuration pointeuse_config.toml (CDC « pointeuse_config.toml »).

- Lecture, avec création d'un fichier par défaut au premier lancement.
- Ajout automatique des clients / projets / tâches saisis librement.
- Relecture à chaud quand le fichier est modifié à la main.

L'écriture passe par tomlkit, qui conserve les commentaires et la mise en forme
de l'utilisateur. Les noms sont comparés sans tenir compte de la casse ni des
espaces autour (« alpha » = « Alpha ») pour ne pas créer de doublons.
"""

import os
from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError
from tomlkit.items import Comment, InlineTable, KeyType, SingleKey, Whitespace

from pointeuse import settings

CONFIG_DEFAUT = """\
# pointeuse_config.toml
#
# Ce fichier se modifie à la main, l'appli le relit automatiquement.
# - Un client, un projet ou une tâche tapé dans l'appli est ajouté ici tout seul.
# - Un client = une section [clients."Nom du client"],
#   un projet = une ligne "Nom du projet" = { taches = [...] }.
# - visible = false : masque un client ou un projet fini (visible par défaut).
#   Case « Afficher les projets masqués » pour le revoir. On peut toujours
#   pointer dessus en tapant son nom : il reste masqué.
# - La tâche est facultative au pointage.

[reglages]
sauvegarde_min = 5          # fréquence de sauvegarde de la ligne en cours
detection_absence_min = 2   # saut d'horloge considéré comme une veille

[clients."exemple-client"]
"exemple-projet" = { taches = ["cdc", "dev", "tests"] }

# Tâches proposées dans tous les projets (facultatif, peut rester vide).
[taches_communes]
liste = ["réunion", "administratif"]
"""

# Clé qui masque un client ou un projet (true par défaut). Dans un client, elle côtoie
# les projets : « visible » ne peut donc pas servir de nom de projet.
CLE_VISIBLE = "visible"
CLES_PROJET = ("taches", CLE_VISIBLE)


class ConfigInvalide(Exception):
    """Le fichier de config ne peut pas être lu (syntaxe ou structure)."""


class NomReserve(ValueError):
    """Nom réservé : client PAUSE, projet « visible »."""


def _cle(nom: str) -> str:
    """Clé de comparaison d'un nom : sans espaces autour, sans casse."""
    return nom.strip().casefold()


def _trouver(table, nom: str):
    """Nom exact (tel qu'écrit dans le fichier) de l'entrée client / projet correspondante, sinon None.

    La clé « visible » d'un client n'est pas un projet : seules les valeurs de type table comptent.
    """
    for cle, valeur in table.items():
        if isinstance(valeur, dict) and _cle(str(cle)) == _cle(nom):
            return str(cle)
    return None


def _deplacer_commentaires_finaux(source, cible) -> None:
    """Déplace les commentaires et lignes vides de fin de `source` à la fin de `cible`.

    tomlkit rattache les commentaires placés avant une section (ex. « # Tâches
    proposées… » au-dessus de [taches_communes]) à la fin de la table précédente.
    Sans ce déplacement, un bloc ajouté s'intercalerait entre le commentaire et la
    section qu'il décrit.
    """
    for element in _retirer_fin(source):
        cible.value.append(None, element)


def _retirer_fin(table) -> list:
    """Retire et retourne les commentaires / lignes vides de fin de la table."""
    corps = table.value.body
    fin = []
    while corps and corps[-1][0] is None and isinstance(corps[-1][1], (Whitespace, Comment)):
        fin.insert(0, corps.pop()[1])
    return fin


def _ligne_projet(taches: list[str], visible: bool) -> InlineTable:
    """Valeur d'un projet sur une ligne : { taches = ["a", "b"] }, avec visible = false si masqué.

    Construite en texte puis relue, pour obtenir la même mise en forme qu'à la main
    (espaces dans les accolades, guillemets doubles).
    """
    parties = ["taches = [" + ", ".join(tomlkit.string(t).as_string() for t in taches) + "]"]
    if not visible:
        parties.append(f"{CLE_VISIBLE} = false")
    return tomlkit.parse("x = { " + ", ".join(parties) + " }\n")["x"]


def _verifier_structure(donnees: dict) -> None:
    """Lève ConfigInvalide avec un message lisible si la structure est incorrecte."""
    reglages = donnees.get("reglages", {})
    if not isinstance(reglages, dict):
        raise ConfigInvalide("[reglages] doit être une section.")
    for nom in settings.REGLAGES_DEFAUT:
        if nom in reglages:
            valeur = reglages[nom]
            if isinstance(valeur, bool) or not isinstance(valeur, int) or valeur <= 0:
                raise ConfigInvalide(f"[reglages] {nom} doit être un nombre entier positif.")

    clients = donnees.get("clients", {})
    if not isinstance(clients, dict):
        raise ConfigInvalide('Les clients doivent être déclarés avec [clients."Nom du client"].')
    for nom_client, client in clients.items():
        if not isinstance(client, dict):
            raise ConfigInvalide(f"Client « {nom_client} » : à déclarer avec [clients.\"{nom_client}\"].")
        if not nom_client.strip():
            raise ConfigInvalide("Un client a un nom vide.")
        if _cle(nom_client) == _cle(settings.CLIENT_PAUSE):
            raise ConfigInvalide(f"« {settings.CLIENT_PAUSE} » est réservé aux pauses : renommez ce client.")
        for nom_projet, projet in client.items():
            if nom_projet == CLE_VISIBLE:
                if not isinstance(projet, bool):
                    raise ConfigInvalide(f"Client « {nom_client} » : visible doit valoir true ou false "
                                         f"(« visible » ne peut pas être un nom de projet).")
                continue
            if not isinstance(projet, dict):
                raise ConfigInvalide(f"Client « {nom_client} », projet « {nom_projet} » : écrire "
                                     f"\"{nom_projet}\" = {{ taches = [...] }}.")
            if not nom_projet.strip():
                raise ConfigInvalide(f"Client « {nom_client} » : un projet a un nom vide.")
            inconnues = [cle for cle in projet if cle not in CLES_PROJET]
            if inconnues:
                raise ConfigInvalide(f"Projet « {nom_projet} » : clé inconnue « {inconnues[0]} » "
                                     f"(autorisées : taches, visible).")
            if not isinstance(projet.get(CLE_VISIBLE, True), bool):
                raise ConfigInvalide(f"Projet « {nom_projet} » : visible doit valoir true ou false.")
            taches = projet.get("taches", [])
            if not isinstance(taches, list) or not all(isinstance(t, str) for t in taches):
                raise ConfigInvalide(f"Projet « {nom_projet} » : taches doit être une liste de textes.")

    communes = donnees.get("taches_communes", {})
    if not isinstance(communes, dict):
        raise ConfigInvalide("[taches_communes] doit être une section.")
    liste = communes.get("liste", [])
    if not isinstance(liste, list) or not all(isinstance(t, str) for t in liste):
        raise ConfigInvalide("[taches_communes] liste doit être une liste de textes.")


class Config:
    """Accès au fichier pointeuse_config.toml."""

    def __init__(self, chemin: Path):
        self.chemin = Path(chemin)
        self._doc = None          # document tomlkit (conserve commentaires et mise en forme)
        self._donnees = {}        # copie en types Python simples, pour la lecture
        self._signature = None    # (date de modif, taille) du fichier au dernier chargement
        self.charger()

    # ─── Chargement ──────────────────────────────────────────────────────────

    def charger(self) -> None:
        """Lit le fichier (le crée s'il n'existe pas). Lève ConfigInvalide si illisible."""
        if not self.chemin.exists():
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            self._ecrire_texte(CONFIG_DEFAUT)

        signature = self._lire_signature()
        # Signature mémorisée même en cas d'erreur : on ne re-signale pas la même
        # erreur à chaque vérification, seulement à la prochaine modification.
        self._signature = signature

        # utf-8-sig : tolère le BOM ajouté par certains éditeurs Windows.
        texte = self.chemin.read_text(encoding="utf-8-sig")
        try:
            doc = tomlkit.parse(texte)
        except TOMLKitError as erreur:
            raise ConfigInvalide(f"Erreur de syntaxe dans {self.chemin.name} : {erreur}") from erreur
        donnees = doc.unwrap()
        _verifier_structure(donnees)

        self._doc = doc
        self._donnees = donnees

    def recharger_si_modifie(self) -> bool:
        """Relit le fichier s'il a changé depuis le dernier chargement.

        Retourne True si la config a été rechargée. En cas d'erreur, lève
        ConfigInvalide et garde la dernière config valide en mémoire.
        """
        if not self.chemin.exists():
            # Fichier supprimé pendant que l'appli tourne : on le réécrit.
            self._sauvegarder()
            return False
        if self._lire_signature() == self._signature:
            return False
        self.charger()
        return True

    # ─── Lecture ─────────────────────────────────────────────────────────────

    def reglage(self, nom: str) -> int:
        """Valeur d'un réglage de [reglages], ou sa valeur par défaut."""
        reglages = self._donnees.get("reglages", {})
        if nom in reglages:
            return reglages[nom]
        return settings.REGLAGES_DEFAUT[nom]

    def clients(self, inclure_masques: bool = False) -> list[str]:
        """Noms des clients, dans l'ordre du fichier."""
        noms = []
        for nom, client in self._donnees.get("clients", {}).items():
            if inclure_masques or client.get(CLE_VISIBLE, True):
                noms.append(nom)
        return noms

    def projets(self, client: str, inclure_masques: bool = False) -> list[str]:
        """Noms des projets d'un client, dans l'ordre du fichier."""
        clients = self._donnees.get("clients", {})
        nom_client = _trouver(clients, client)
        if nom_client is None:
            return []
        noms = []
        for nom, projet in clients[nom_client].items():
            if isinstance(projet, dict) and (inclure_masques or projet.get(CLE_VISIBLE, True)):
                noms.append(nom)
        return noms

    def taches_projet(self, client: str, projet: str) -> list[str]:
        """Tâches propres au projet."""
        clients = self._donnees.get("clients", {})
        nom_client = _trouver(clients, client)
        if nom_client is None:
            return []
        nom_projet = _trouver(clients[nom_client], projet)
        if nom_projet is None:
            return []
        return list(clients[nom_client][nom_projet].get("taches", []))

    def taches_communes(self) -> list[str]:
        """Tâches proposées dans tous les projets."""
        return list(self._donnees.get("taches_communes", {}).get("liste", []))

    # ─── Écriture ────────────────────────────────────────────────────────────

    def ajouter(self, client: str, projet: str, tache: str | None = None) -> tuple[str, str, str | None]:
        """Enregistre client / projet / tâche s'ils n'existent pas encore.

        - Un client ou un projet masqué (visible = false) reste masqué : on peut
          pointer dessus exceptionnellement sans le faire réapparaître (MP 2026-11-17).
        - Une tâche déjà présente dans le projet ou dans les tâches communes
          n'est pas recopiée ; une tâche nouvelle est ajoutée au projet.

        Retourne les noms tels qu'écrits dans le fichier (casse existante conservée),
        avec tache = None si aucune tâche n'est donnée.
        """
        client = client.strip()
        projet = projet.strip()
        if tache is not None:
            tache = tache.strip()
        if tache == "":
            tache = None
        if not client or not projet:
            raise ValueError("Le client et le projet sont obligatoires.")
        if _cle(client) == _cle(settings.CLIENT_PAUSE):
            raise NomReserve(f"« {settings.CLIENT_PAUSE} » est réservé aux pauses.")
        if _cle(projet) == CLE_VISIBLE:
            raise NomReserve(f"« {CLE_VISIBLE} » ne peut pas être un nom de projet.")

        # Prendre en compte une modification manuelle récente avant d'écrire,
        # pour ne pas l'écraser avec l'ancienne version en mémoire.
        self.recharger_si_modifie()

        modifie = False
        if "clients" not in self._doc:
            self._doc.append("clients", tomlkit.table(is_super_table=True))
        clients = self._doc["clients"]

        nom_client = _trouver(clients, client)
        if nom_client is None:
            table_client = tomlkit.table()
            table_client.trivia.indent = "\n"   # ligne vide avant [clients."..."]
            precedent = None
            for valeur in clients.values():
                precedent = valeur
            clients.append(SingleKey(client, KeyType.Basic), table_client)
            if precedent is not None:
                _deplacer_commentaires_finaux(precedent, table_client)
            nom_client = client
            modifie = True
        table_client = clients[nom_client]

        nom_projet = _trouver(table_client, projet)
        if nom_projet is None:
            # Nouvelle ligne après le dernier projet, avant les commentaires de fin du client.
            fin = _retirer_fin(table_client)
            table_client.append(SingleKey(projet, KeyType.Basic), _ligne_projet([], True))
            for element in fin:
                table_client.value.append(None, element)
            nom_projet = projet
            modifie = True
        valeur_projet = table_client[nom_projet]
        taches = [str(t) for t in valeur_projet.get("taches", [])]
        visible = bool(valeur_projet.get(CLE_VISIBLE, True))

        nom_tache = None
        if tache is not None:
            for existante in taches + self.taches_communes():
                if nom_tache is None and _cle(existante) == _cle(tache):
                    nom_tache = existante
            if nom_tache is None:
                nom_tache = tache
                taches.append(tache)
                modifie = True

        if taches != [str(t) for t in valeur_projet.get("taches", [])]:
            self._reecrire_projet(table_client, nom_projet, taches, visible)
            modifie = True

        if modifie:
            self._sauvegarder()
        return nom_client, nom_projet, nom_tache

    @staticmethod
    def _reecrire_projet(table_client, nom_projet: str, taches: list[str], visible: bool) -> None:
        """Remplace la ligne du projet (tâches à jour) en gardant visible et le commentaire de fin de ligne."""
        ancienne = table_client[nom_projet]
        if not isinstance(ancienne, InlineTable):
            # Projet écrit à la main en section [clients."A"."P"] : modification sur place.
            ancienne["taches"] = taches
            return
        nouvelle = _ligne_projet(taches, visible)
        nouvelle.trivia.comment_ws = ancienne.trivia.comment_ws
        nouvelle.trivia.comment = ancienne.trivia.comment
        nouvelle.trivia.trail = ancienne.trivia.trail
        table_client[nom_projet] = nouvelle

    # ─── Interne ─────────────────────────────────────────────────────────────

    def _lire_signature(self):
        try:
            etat = self.chemin.stat()
        except FileNotFoundError:
            return None
        return (etat.st_mtime_ns, etat.st_size)

    def _sauvegarder(self) -> None:
        self._ecrire_texte(tomlkit.dumps(self._doc))
        self._donnees = self._doc.unwrap()
        self._signature = self._lire_signature()

    def _ecrire_texte(self, texte: str) -> None:
        """Écriture atomique : fichier temporaire puis remplacement."""
        temporaire = self.chemin.with_name(self.chemin.name + ".tmp")
        temporaire.write_text(texte, encoding="utf-8")
        os.replace(temporaire, self.chemin)

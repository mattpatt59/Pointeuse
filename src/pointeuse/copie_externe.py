"""Sauvegarde automatique de data/ (CDC multi_postes.md, ADR 005).

data/ reste la seule source de travail. Après chaque enregistrement, les fichiers de
settings.FICHIERS_COPIES sont recopiés dans [donnees] dossier_de_sauvegarde (vide : pas de
sauvegarde). Le nom de ce dossier est le nom du poste : rangé dans le dossier externe d'un
autre PC (Z:/pointeuse/bureau/…), il est lu par son bilan. La Pointeuse ne synchronise
rien : si le dossier est sur un drive ou un NAS, c'est lui qui transporte les fichiers.

- Garde-fou : pas de copie si le pointeuse.csv sauvegardé est plus grand que le local
  (data/ vidé, réinstallation : on n'écrase pas une sauvegarde plus complète).
- Écriture sûre : fichier temporaire dans le dossier de destination, puis renommage.
- Échec (drive absent…) : nouvel essai après 1, 2, 4… min, plafonné à 1 h ; un nouvel
  enregistrement relance un essai tout de suite, sans remettre le délai à 1 min.
- Le pointage n'est jamais bloqué : tout se passe ici, les erreurs deviennent un état.
"""

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from pointeuse import settings
from pointeuse.chemins import dossier_externe, dossier_sauvegarde


class Etat(Enum):
    DESACTIVEE = "desactivee"               # dossier_de_sauvegarde vide : pas de sauvegarde
    FAITE = "faite"
    DOSSIER_INVALIDE = "dossier_invalide"   # sauvegarde dans data/ : refusée
    SUSPENDUE = "suspendue"                 # garde-fou : CSV sauvegardé plus grand que le local
    ECHEC = "echec"                         # dossier injoignable, disque plein…


ETATS_A_SIGNALER = (Etat.DOSSIER_INVALIDE, Etat.SUSPENDUE, Etat.ECHEC)


@dataclass
class Resultat:
    etat: Etat
    detail: str = ""


def _taille(chemin: Path) -> int:
    """Taille du fichier, -1 s'il n'existe pas."""
    try:
        return chemin.stat().st_size
    except FileNotFoundError:
        return -1


def _dans(chemin: Path, dossier: Path) -> bool:
    """Vrai si chemin est dossier ou l'un de ses sous-dossiers."""
    chemin = chemin.resolve()
    dossier = dossier.resolve()
    return chemin == dossier or dossier in chemin.parents


def copier_donnees(donnees: Path, destination: Path, creer_parent: bool) -> Resultat:
    """Recopie les fichiers de data/ dans le dossier de sauvegarde.

    creer_parent : le dossier peut être créé avec ses parents (chemin relatif, dans le dossier
    du logiciel). Sinon son parent doit exister : un lecteur réseau ou un point de montage
    absent ne doit pas devenir un dossier vide sur le disque local."""
    try:
        taille_locale = max(_taille(donnees / settings.NOM_FICHIER_CSV), 0)
        taille_sauvegarde = _taille(destination / settings.NOM_FICHIER_CSV)
        if taille_locale < taille_sauvegarde:
            return Resultat(Etat.SUSPENDUE)
        if not creer_parent and not destination.parent.is_dir():
            return Resultat(Etat.ECHEC, f"dossier introuvable : {destination.parent}")
        destination.mkdir(parents=True, exist_ok=True)
        for nom in settings.FICHIERS_COPIES:
            source = donnees / nom
            if not source.exists():
                continue
            temporaire = destination / (nom + settings.SUFFIXE_COPIE_TEMPORAIRE)
            try:
                shutil.copyfile(source, temporaire)
                os.replace(temporaire, destination / nom)
            finally:
                temporaire.unlink(missing_ok=True)
    except OSError as erreur:
        return Resultat(Etat.ECHEC, str(erreur))
    return Resultat(Etat.FAITE)


class CopieExterne:
    """État de la sauvegarde : dernier résultat, délai avant le prochain essai, attente en cours.

    reglage(nom) : valeur de [donnees] (Config.reglage_donnees), relue à chaque essai."""

    def __init__(self, donnees: Path, logiciel: Path, reglage: Callable[[str], str],
                 horloge: Callable[[], datetime] = datetime.now):
        self.donnees = donnees
        self.logiciel = logiciel
        self.reglage = reglage
        self.horloge = horloge
        self.delai_min = settings.COPIE_DELAI_INITIAL_MIN   # délai appliqué au prochain échec
        self.prochain_essai_min: int | None = None          # à programmer après cet essai
        self.en_attente_depuis: datetime | None = None
        self.dernier: Resultat | None = None
        self._signature_essai = None

    # ─── Emplacements ────────────────────────────────────────────────────────

    def dossier_sauvegarde(self) -> Path | None:
        return dossier_sauvegarde(self.reglage("dossier_de_sauvegarde"), self.logiciel)

    def poste(self) -> str:
        """Nom de ce poste = nom du dossier de sauvegarde ("" sans sauvegarde)."""
        dossier = self.dossier_sauvegarde()
        if dossier is None:
            return ""
        return dossier.name

    def dossier_externe(self) -> Path:
        return dossier_externe(self.reglage("dossier_externe"), self.logiciel)

    # ─── Essais ──────────────────────────────────────────────────────────────

    def signature(self) -> tuple:
        """(nom, date de modif, taille) des fichiers copiés : change à chaque enregistrement."""
        resultat = []
        for nom in settings.FICHIERS_COPIES:
            try:
                infos = (self.donnees / nom).stat()
                resultat.append((nom, infos.st_mtime_ns, infos.st_size))
            except OSError:
                resultat.append((nom, None, None))
        return tuple(resultat)

    def a_change(self) -> bool:
        """Vrai si un fichier a été enregistré depuis le dernier essai (ou s'il n'y en a pas eu)."""
        return self.signature() != self._signature_essai

    def essayer(self) -> bool:
        """Un essai de sauvegarde. Renvoie True si le résultat est à signaler (notification unique)."""
        self._signature_essai = self.signature()
        destination = self.dossier_sauvegarde()
        if destination is None:
            resultat = Resultat(Etat.DESACTIVEE)
        elif _dans(destination, self.donnees):
            resultat = Resultat(Etat.DOSSIER_INVALIDE)
        else:
            # Chemin relatif : dans le dossier du logiciel, créé si besoin. Absolu : le parent doit exister.
            reglage = self.reglage("dossier_de_sauvegarde").strip()
            relatif = not Path(reglage).expanduser().is_absolute()
            resultat = copier_donnees(self.donnees, destination, creer_parent=relatif)

        self.prochain_essai_min = None
        if resultat.etat == Etat.ECHEC:
            self.prochain_essai_min = self.delai_min
            self.delai_min = min(self.delai_min * 2, settings.COPIE_DELAI_MAX_MIN)
        if resultat.etat in (Etat.ECHEC, Etat.SUSPENDUE):
            if self.en_attente_depuis is None:
                self.en_attente_depuis = self.horloge()
        else:
            self.en_attente_depuis = None
        if resultat.etat in (Etat.FAITE, Etat.DESACTIVEE):
            self.delai_min = settings.COPIE_DELAI_INITIAL_MIN

        etat_precedent = None
        if self.dernier is not None:
            etat_precedent = self.dernier.etat
        self.dernier = resultat
        return resultat.etat in ETATS_A_SIGNALER and resultat.etat != etat_precedent

    # ─── Textes ──────────────────────────────────────────────────────────────

    def message(self) -> str:
        """Notification du dernier résultat (vide si rien à dire)."""
        if self.dernier is None:
            return ""
        etat = self.dernier.etat
        if etat == Etat.DOSSIER_INVALIDE:
            return (f"[donnees] dossier_de_sauvegarde ({self.dossier_sauvegarde()}) est dans data/ : "
                    "pas de sauvegarde tant qu'il n'est pas corrigé.")
        if etat == Etat.SUSPENDUE:
            return (f"Le CSV sauvegardé dans {self.dossier_sauvegarde()} est plus grand que le CSV local : "
                    "sauvegarde suspendue, pour ne pas écraser une sauvegarde plus complète. Elle reprend "
                    "quand le CSV local redevient au moins aussi grand (en général à la prochaine ligne "
                    "pointée). Pour restaurer : recopier ce dossier dans data/.")
        if etat == Etat.ECHEC:
            return (f"Sauvegarde impossible ({self.dernier.detail}). "
                    f"Nouvel essai dans {self.prochain_essai_min} min ; le pointage continue normalement.")
        return ""

    def texte_info_bulle(self) -> str:
        """Ligne ajoutée à l'info-bulle de l'icône, vide si tout va bien."""
        if self.dernier is not None and self.dernier.etat == Etat.DOSSIER_INVALIDE:
            return "Sauvegarde impossible : dossier de sauvegarde à corriger"
        if self.en_attente_depuis is not None:
            return f"Sauvegarde en attente depuis {self.en_attente_depuis:%H:%M}"
        return ""

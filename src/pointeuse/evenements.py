"""Journal des événements du poste : pointeuse_journal.csv (CDC « Journal des événements »).

Démarrage / arrêt de l'appli, verrouillage / déverrouillage, veille / réveil. Ce n'est
pas un pointage : il sert à repérer, dans la vue Journée, les moments où le PC était
utilisé sans que rien ne soit pointé (oubli à rattraper).

Le journal est une aide : un événement qui ne peut pas être écrit (fichier ouvert dans
un tableur) est perdu sans alerte. pointeuse.csv et le lecteur de bilan n'en dépendent pas.
"""

import csv
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from pointeuse import settings

DEMARRAGE = "demarrage"
ARRET = "arret"
VERROUILLAGE = "verrouillage"
DEVERROUILLAGE = "deverrouillage"
VEILLE = "veille"
REVEIL = "reveil"

LIBELLES = {
    DEMARRAGE: "démarrage de la pointeuse",
    ARRET: "arrêt de la pointeuse",
    VERROUILLAGE: "verrouillage",
    DEVERROUILLAGE: "déverrouillage",
    VEILLE: "mise en veille",
    REVEIL: "réveil",
}

Plage = tuple[datetime, datetime]


@dataclass(frozen=True)
class Evenement:
    moment: datetime
    nature: str

    @property
    def libelle(self) -> str:
        return LIBELLES.get(self.nature, self.nature)


class JournalEvenements:
    """Accès au fichier pointeuse_journal.csv."""

    def __init__(self, chemin: Path, retention_jours: Callable[[], int]):
        self.chemin = Path(chemin)
        self.retention_jours = retention_jours   # fonction : le réglage peut changer à chaud

    @property
    def actif(self) -> bool:
        """retention_journal_jours = 0 : pas de journal (rien n'est écrit ni affiché)."""
        return self.retention_jours() > 0

    def noter(self, nature: str, moment: datetime) -> bool:
        """Ajoute un événement en fin de fichier. Faux s'il n'a pas pu être écrit."""
        if not self.actif:
            return False
        nouveau = not self.chemin.exists() or self.chemin.stat().st_size == 0
        try:
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            with open(self.chemin, "a", newline="", encoding=settings.ENCODAGE_CSV) as fichier:
                ecrivain = csv.writer(fichier, delimiter=settings.SEPARATEUR_CSV)
                if nouveau:
                    ecrivain.writerow(settings.COLONNES_EVENEMENTS)
                ecrivain.writerow([moment.strftime(settings.FORMAT_HORODATAGE_EVENEMENT), nature])
        except OSError:
            return False
        return True

    def lire(self) -> list[Evenement]:
        """Événements lisibles, triés par heure. Une ligne abîmée est ignorée."""
        if not self.chemin.exists():
            return []
        evenements = []
        try:
            with open(self.chemin, newline="", encoding=settings.ENCODAGE_CSV) as fichier:
                for valeurs in csv.reader(fichier, delimiter=settings.SEPARATEUR_CSV):
                    if len(valeurs) < 2 or valeurs[0] == settings.COLONNES_EVENEMENTS[0]:
                        continue
                    try:
                        moment = datetime.strptime(valeurs[0].strip(), settings.FORMAT_HORODATAGE_EVENEMENT)
                    except ValueError:
                        continue
                    evenements.append(Evenement(moment, valeurs[1].strip()))
        except OSError:
            return []
        return sorted(evenements, key=lambda e: e.moment)

    def purger(self, maintenant: datetime) -> None:
        """Retire les événements plus vieux que la rétention (au démarrage de l'appli).

        Réécriture atomique (fichier temporaire puis remplacement) ; en cas d'échec,
        le fichier reste tel quel.
        """
        if not self.actif or not self.chemin.exists():
            return
        limite = maintenant - timedelta(days=self.retention_jours())
        tous = self.lire()
        gardes = [e for e in tous if e.moment >= limite]
        if len(gardes) == len(tous):
            return
        temporaire = self.chemin.with_name(self.chemin.name + ".tmp")
        try:
            with open(temporaire, "w", newline="", encoding=settings.ENCODAGE_CSV) as fichier:
                ecrivain = csv.writer(fichier, delimiter=settings.SEPARATEUR_CSV)
                ecrivain.writerow(settings.COLONNES_EVENEMENTS)
                for evenement in gardes:
                    ecrivain.writerow([evenement.moment.strftime(settings.FORMAT_HORODATAGE_EVENEMENT),
                                       evenement.nature])
            os.replace(temporaire, self.chemin)
        except OSError:
            temporaire.unlink(missing_ok=True)

    def du_jour(self, jour: date) -> list[Evenement]:
        debut_jour = datetime.combine(jour, datetime.min.time())
        fin_jour = debut_jour + timedelta(days=1)
        return [e for e in self.lire() if debut_jour <= e.moment < fin_jour]


# ─── Moments où le PC était utilisé, et moments non pointés ──────────────────

def plages_actives(evenements: list[Evenement], maintenant: datetime) -> list[Plage]:
    """Plages où l'appli tournait, session déverrouillée et PC réveillé.

    Un démarrage alors que l'appli tournait déjà (plantage, coupure : pas d'« arret »)
    abandonne la plage précédente, dont on ne connaît pas la fin. Une plage encore
    ouverte se termine à maintenant.
    """
    plages = []
    en_marche = False
    verrouille = False
    en_veille = False
    debut = None
    for evenement in sorted(evenements, key=lambda e: e.moment):
        nature = evenement.nature
        if nature == DEMARRAGE:
            en_marche, verrouille, en_veille = True, False, False
            debut = evenement.moment
            continue
        if nature == ARRET:
            en_marche = False
        elif nature == VERROUILLAGE:
            verrouille = True
        elif nature == DEVERROUILLAGE:
            verrouille = False
        elif nature == VEILLE:
            en_veille = True
        elif nature == REVEIL:
            en_veille = False
        else:
            continue
        actif = en_marche and not verrouille and not en_veille
        if actif and debut is None:
            debut = evenement.moment
        elif not actif and debut is not None:
            if evenement.moment > debut:
                plages.append((debut, evenement.moment))
            debut = None
    if debut is not None and maintenant > debut:
        plages.append((debut, maintenant))
    return plages


def soustraire(plages: list[Plage], occupees: list[Plage]) -> list[Plage]:
    """Parties des plages qui ne sont couvertes par aucune plage occupée."""
    resultat = []
    for debut, fin in plages:
        morceaux = [(debut, fin)]
        for o_debut, o_fin in occupees:
            suivants = []
            for m_debut, m_fin in morceaux:
                if o_fin <= m_debut or o_debut >= m_fin:
                    suivants.append((m_debut, m_fin))
                    continue
                if m_debut < o_debut:
                    suivants.append((m_debut, o_debut))
                if o_fin < m_fin:
                    suivants.append((o_fin, m_fin))
            morceaux = suivants
        resultat.extend(morceaux)
    return sorted(resultat)


def trous_du_jour(evenements: list[Evenement], occupees: list[Plage], jour: date,
                  maintenant: datetime, minimum_min: int) -> list[Plage]:
    """Moments non pointés du jour : PC actif, aucune tâche ni pause. Seuls ceux d'au moins
    minimum_min minutes sont rendus, à la minute (comme le CSV)."""
    debut_jour = datetime.combine(jour, datetime.min.time())
    fin_jour = debut_jour + timedelta(days=1)
    dans_le_jour = []
    for debut, fin in plages_actives(evenements, maintenant):
        debut, fin = max(debut, debut_jour), min(fin, fin_jour)
        if fin > debut:
            dans_le_jour.append((debut, fin))
    trous = []
    for debut, fin in soustraire(dans_le_jour, occupees):
        debut = debut.replace(second=0, microsecond=0)
        fin = fin.replace(second=0, microsecond=0)
        if (fin - debut) >= timedelta(minutes=minimum_min):
            trous.append((debut, fin))
    return trous

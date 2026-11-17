"""Journal des temps : fichier pointeuse.csv (CDC « pointeuse.csv »).

Une ligne = une tâche ou une pause terminée. Les heures sont à la minute.
"""

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from pointeuse import settings


class JournalBloque(Exception):
    """Écriture impossible (fichier ouvert dans Excel, disque plein, droits…)."""


def a_la_minute(moment: datetime) -> datetime:
    """Tronque à la minute : le CSV ne stocke pas les secondes."""
    return moment.replace(second=0, microsecond=0)


@dataclass(frozen=True)
class Ligne:
    debut: datetime
    fin: datetime
    client: str
    projet: str = ""
    tache: str = ""
    description: str = ""

    @property
    def duree_min(self) -> int:
        return int((self.fin - self.debut).total_seconds() // 60)

    @property
    def est_pause(self) -> bool:
        return self.client == settings.CLIENT_PAUSE

    def vers_csv(self) -> list[str]:
        return [
            self.debut.strftime(settings.FORMAT_DATE_CSV),
            self.fin.strftime(settings.FORMAT_DATE_CSV),
            self.client,
            self.projet,
            self.tache,
            self.description,
            str(self.duree_min),
        ]

    @classmethod
    def depuis_csv(cls, valeurs: list[str]) -> "Ligne":
        """Lève ValueError si la ligne est mal formée. duree_min est recalculée, pas relue."""
        if len(valeurs) < len(settings.COLONNES_CSV):
            raise ValueError("colonnes manquantes")
        return cls(
            debut=datetime.strptime(valeurs[0].strip(), settings.FORMAT_DATE_CSV),
            fin=datetime.strptime(valeurs[1].strip(), settings.FORMAT_DATE_CSV),
            client=valeurs[2],
            projet=valeurs[3],
            tache=valeurs[4],
            description=valeurs[5],
        )

    def vers_dict(self) -> dict:
        return {
            "debut": self.debut.isoformat(),
            "fin": self.fin.isoformat(),
            "client": self.client,
            "projet": self.projet,
            "tache": self.tache,
            "description": self.description,
        }

    @classmethod
    def depuis_dict(cls, d: dict) -> "Ligne":
        return cls(
            debut=datetime.fromisoformat(d["debut"]),
            fin=datetime.fromisoformat(d["fin"]),
            client=d["client"],
            projet=d.get("projet", ""),
            tache=d.get("tache", ""),
            description=d.get("description", ""),
        )


class Journal:
    """Accès au fichier pointeuse.csv."""

    def __init__(self, chemin: Path):
        self.chemin = Path(chemin)
        self.lignes_ignorees = 0   # lignes illisibles rencontrées à la dernière lecture

    def lire(self) -> list[Ligne]:
        """Toutes les lignes lisibles, dans l'ordre du fichier.

        Une ligne abîmée (modifiée à la main) est ignorée et comptée dans
        lignes_ignorees, pour ne pas bloquer l'affichage de la journée.
        """
        self.lignes_ignorees = 0
        if not self.chemin.exists():
            return []
        lignes = []
        with open(self.chemin, newline="", encoding=settings.ENCODAGE_CSV) as fichier:
            lecteur = csv.reader(fichier, delimiter=settings.SEPARATEUR_CSV)
            for numero, valeurs in enumerate(lecteur):
                if numero == 0 and valeurs[:1] == settings.COLONNES_CSV[:1]:
                    continue  # en-tête
                if not valeurs:
                    continue  # ligne vide
                try:
                    lignes.append(Ligne.depuis_csv(valeurs))
                except ValueError:
                    self.lignes_ignorees += 1
        return lignes

    def lignes_du_jour(self, jour: date) -> list[Ligne]:
        """Lignes qui touchent ce jour (une ligne qui passe minuit apparaît les deux jours)."""
        debut_jour = datetime.combine(jour, datetime.min.time())
        resultat = []
        for ligne in self.lire():
            if ligne.debut.date() <= jour and ligne.fin > debut_jour:
                resultat.append(ligne)
        return resultat

    def ajouter(self, lignes: list[Ligne]) -> None:
        """Ajoute des lignes en fin de fichier (crée le fichier avec son en-tête au besoin).

        Lève JournalBloque si le fichier ne peut pas être écrit.
        """
        if not lignes:
            return
        nouveau = not self.chemin.exists() or self.chemin.stat().st_size == 0
        try:
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            # En mode ajout, Python n'écrit le BOM que si le fichier est vide.
            with open(self.chemin, "a", newline="", encoding=settings.ENCODAGE_CSV) as fichier:
                ecrivain = csv.writer(fichier, delimiter=settings.SEPARATEUR_CSV)
                if nouveau:
                    ecrivain.writerow(settings.COLONNES_CSV)
                for ligne in lignes:
                    ecrivain.writerow(ligne.vers_csv())
        except OSError as erreur:
            raise JournalBloque(f"Impossible d'écrire dans {self.chemin.name} : {erreur}") from erreur

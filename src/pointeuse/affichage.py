"""Textes affichés (statut, info-bulle) : fonctions pures, testables sans Qt."""

from datetime import datetime

from pointeuse.journal import a_la_minute
from pointeuse.moteur import LigneOuverte


def duree_texte(minutes: int) -> str:
    """75 → « 1 h 15 » ; 5 → « 0 h 05 »."""
    if minutes < 0:
        minutes = 0
    return f"{minutes // 60} h {minutes % 60:02d}"


def libelle_tache(client: str, projet: str, tache: str = "") -> str:
    morceaux = [client, projet]
    if tache:
        morceaux.append(tache)
    return " / ".join(morceaux)


def minutes_ecoulees(ligne: LigneOuverte, maintenant: datetime) -> int:
    return int((a_la_minute(maintenant) - ligne.debut).total_seconds() // 60)


def texte_statut(ligne: LigneOuverte | None, maintenant: datetime) -> str:
    """Bandeau de l'onglet « Pointer »."""
    if ligne is None:
        return "Aucune tâche en cours"
    heure = ligne.debut.strftime("%H:%M")
    if ligne.est_pause:
        return f"En pause depuis {heure}"
    return f"En cours depuis {heure}"


def texte_info_bulle(ligne: LigneOuverte | None, maintenant: datetime, nb_en_attente: int = 0) -> str:
    """Info-bulle de l'icône (CDC « Icône dans la zone de notification »)."""
    if ligne is None:
        texte = "Pointeuse — aucune tâche en cours"
    else:
        duree = duree_texte(minutes_ecoulees(ligne, maintenant))
        heure = ligne.debut.strftime("%H:%M")
        if ligne.est_pause:
            texte = f"En pause depuis {heure} ({duree})"
        else:
            texte = f"{libelle_tache(ligne.client, ligne.projet, ligne.tache)} — depuis {heure} ({duree})"
    if nb_en_attente > 0:
        texte += f"\n⚠ {nb_en_attente} ligne(s) en attente : fermez pointeuse.csv"
    return texte


def texte_absence(debut: datetime, fin: datetime) -> str:
    minutes = int((fin - debut).total_seconds() // 60)
    return f"Absent de {debut:%H:%M} à {fin:%H:%M} ({duree_texte(minutes)}).\nQu'avez-vous fait ?"

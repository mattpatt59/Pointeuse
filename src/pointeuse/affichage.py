"""Textes affichés (statut, info-bulle) : fonctions pures, testables sans Qt."""

from datetime import date, datetime, timedelta

from pointeuse import __version__, settings
from pointeuse.journal import Ligne, a_la_minute
from pointeuse.moteur import LigneOuverte


def version_courte(version: str = __version__) -> str:
    """« 0.1.0 » → « V0.1 » ; « 0.1.2 » → « V0.1.2 » (le correctif n'est montré que s'il existe)."""
    morceaux = version.split(".")
    while len(morceaux) > 2 and morceaux[-1] == "0":
        morceaux.pop()
    return "V" + ".".join(morceaux)


def titre_application() -> str:
    """En-tête et titre du panneau : « Pointeuse V0.1 »."""
    return f"{settings.NOM_APPLICATION} {version_courte()}"


def duree_texte(minutes: int) -> str:
    """75 → « 1 h 15 » ; 5 → « 0 h 05 »."""
    if minutes < 0:
        minutes = 0
    return f"{minutes // 60} h {minutes % 60:02d}"


def libelle_tache(client: str, projet: str, tache: str = "") -> str:
    """« client / projet / tâche », sans les parties vides (projet vide : bouton rapide « client seul »)."""
    return " / ".join(t for t in (client, projet, tache) if t)


def nom_pause(ligne: LigneOuverte) -> str:
    """« pause », ou « pause (Repas) » si la pause a une description."""
    if ligne.description:
        return f"pause ({ligne.description})"
    return "pause"


def minutes_ecoulees(ligne: LigneOuverte, maintenant: datetime) -> int:
    return int((a_la_minute(maintenant) - ligne.debut).total_seconds() // 60)


def texte_statut(ligne: LigneOuverte | None, maintenant: datetime) -> str:
    """Bandeau de l'onglet « Pointer »."""
    if ligne is None:
        return "Aucune tâche en cours"
    heure = ligne.debut.strftime("%H:%M")
    if ligne.est_pause:
        return f"En {nom_pause(ligne)} depuis {heure}"
    return f"En cours depuis {heure}"


def texte_info_bulle(ligne: LigneOuverte | None, maintenant: datetime, nb_en_attente: int = 0) -> str:
    """Info-bulle de l'icône (CDC « Icône dans la zone de notification »)."""
    if ligne is None:
        texte = "Pointeuse — aucune tâche en cours"
    else:
        duree = duree_texte(minutes_ecoulees(ligne, maintenant))
        heure = ligne.debut.strftime("%H:%M")
        if ligne.est_pause:
            texte = f"En {nom_pause(ligne)} depuis {heure} ({duree})"
        else:
            texte = f"{libelle_tache(ligne.client, ligne.projet, ligne.tache)} — depuis {heure} ({duree})"
    if nb_en_attente > 0:
        texte += f"\n⚠ {nb_en_attente} ligne(s) en attente : fermez pointeuse.csv"
    return texte


def texte_absence(debut: datetime, fin: datetime) -> str:
    minutes = int((fin - debut).total_seconds() // 60)
    return f"Absent de {debut:%H:%M} à {fin:%H:%M} ({duree_texte(minutes)}).\nQu'avez-vous fait ?"


# ─── Onglet « Insérer / Journée » ────────────────────────────────────────────

def texte_plage(debut: datetime, fin: datetime | None, jour: date) -> str:
    """« 08:30–10:12 » ; « 13:30– … » pour la ligne en cours ; date ajoutée si hors du jour affiché."""
    morceaux = [_heure(debut, jour) + "–"]
    if fin is None:
        morceaux.append(" …")
    else:
        morceaux.append(_heure(fin, jour))
    return "".join(morceaux)


def libelle_ligne(client: str, projet: str, tache: str = "") -> str:
    if client == settings.CLIENT_PAUSE:
        return "Pause"
    return libelle_tache(client, projet, tache)


def minutes_dans_le_jour(debut: datetime, fin: datetime, jour: date) -> int:
    """Durée de [debut, fin] comptée dans ce jour seulement (une ligne peut passer minuit)."""
    debut_jour = datetime.combine(jour, datetime.min.time())
    fin_jour = debut_jour + timedelta(days=1)
    debut = max(debut, debut_jour)
    fin = min(fin, fin_jour)
    if fin <= debut:
        return 0
    return int((fin - debut).total_seconds() // 60)


def totaux_du_jour(lignes: list[Ligne], ouverte: LigneOuverte | None, maintenant: datetime,
                   jour: date) -> tuple[int, int]:
    """(minutes travaillées, minutes de pause) du jour, ligne en cours comprise."""
    plages = [(l.debut, l.fin, l.est_pause) for l in lignes]
    if ouverte is not None:
        plages.append((ouverte.debut, a_la_minute(maintenant), ouverte.est_pause))
    travail = 0
    pause = 0
    for debut, fin, est_pause in plages:
        minutes = minutes_dans_le_jour(debut, fin, jour)
        if est_pause:
            pause += minutes
        else:
            travail += minutes
    return travail, pause


def _heure(moment: datetime, jour: date) -> str:
    if moment.date() == jour:
        return moment.strftime("%H:%M")
    return moment.strftime("%d/%m %H:%M")

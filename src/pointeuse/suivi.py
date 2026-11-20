"""Journal de suivi des projets : pointeuse_suivi.jsonl (CDC suivi_projets.md, ADR 004).

Une ligne = une note JSON (statut, priorité, texte) d'un projet pour une période (jour ou
semaine). Le fichier est en ajout seul : corriger une note ajoute une nouvelle version, la
plus récente de la période est celle qui compte. Les règles de lecture sont aussi codées
dans le lecteur de bilan (JS) : les garder alignées avec l'ADR 004.
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from pointeuse import settings
from pointeuse.journal import Ligne

CHAMPS_TEXTE = ("horodatage", "periode", "client", "projet", "statut", "texte")
MOTIF_PERIODE_SEMAINE = re.compile(r"^(\d{4})-W(\d{2})$")


@dataclass(frozen=True)
class NoteSuivi:
    horodatage: datetime
    periode: str
    client: str
    projet: str
    statut: str
    priorite: int
    texte: str
    poste: str = ""          # nom du poste (dossier externe), rempli par le bilan ; vide en local

    @property
    def cle_projet(self) -> tuple[str, str]:
        return (self.client, self.projet)


# ─── Périodes ────────────────────────────────────────────────────────────────

def periode_de(jour: date, mode: str) -> str:
    """Période qui contient le jour : « 2026-11-14 » (jour) ou « 2026-W46 » (semaine ISO)."""
    if mode == settings.PERIODE_SEMAINE:
        annee, semaine, _ = jour.isocalendar()
        return settings.FORMAT_PERIODE_SEMAINE.format(annee=annee, semaine=semaine)
    if mode == settings.PERIODE_JOUR:
        return jour.strftime(settings.FORMAT_PERIODE_JOUR)
    raise ValueError(f"période inconnue : {mode!r}")


def jours_de_periode(periode: str) -> tuple[date, date]:
    """Premier et dernier jour (inclus) d'une période. ValueError si elle est mal formée."""
    erreur = ValueError(f"période mal formée : {periode!r}")
    semaine = MOTIF_PERIODE_SEMAINE.match(periode)
    if semaine:
        try:
            lundi = date.fromisocalendar(int(semaine.group(1)), int(semaine.group(2)), 1)
        except ValueError:
            raise erreur from None
        return lundi, lundi + timedelta(days=6)
    try:
        jour = datetime.strptime(periode, settings.FORMAT_PERIODE_JOUR).date()
    except ValueError:
        raise erreur from None
    if jour.strftime(settings.FORMAT_PERIODE_JOUR) != periode:   # refuse « 2026-1-5 »
        raise erreur
    return jour, jour


def est_periode_semaine(periode: str) -> bool:
    return MOTIF_PERIODE_SEMAINE.match(periode) is not None


# ─── Lecture ─────────────────────────────────────────────────────────────────

def _note_depuis_objet(objet, poste: str) -> tuple[NoteSuivi, list[str]]:
    """Convertit un objet JSON en note. ValueError (raison lisible) si la ligne est refusée ;
    les avertissements non bloquants (priorité ramenée dans les bornes) sont rendus."""
    if not isinstance(objet, dict):
        raise ValueError("ce n'est pas un objet JSON")
    if objet.get("v") != settings.VERSION_LIGNE_SUIVI:
        raise ValueError(f"version de format inconnue : {objet.get('v')!r}")
    for champ in CHAMPS_TEXTE:
        if not isinstance(objet.get(champ), str):
            raise ValueError(f"champ « {champ} » manquant ou non textuel")
    priorite = objet.get("priorite")
    if isinstance(priorite, bool) or not isinstance(priorite, int):
        raise ValueError("champ « priorite » manquant ou non entier")
    if objet["statut"] not in settings.STATUTS_SUIVI:
        raise ValueError(f"statut inconnu : {objet['statut']!r}")
    if not objet["client"].strip() or not objet["projet"].strip():
        raise ValueError("client ou projet vide")
    try:
        horodatage = datetime.strptime(objet["horodatage"], settings.FORMAT_HORODATAGE_SUIVI)
    except ValueError:
        raise ValueError(f"horodatage illisible : {objet['horodatage']!r}") from None
    jours_de_periode(objet["periode"])   # lève ValueError si la période est mal formée
    avertissements = []
    bornee = min(max(priorite, settings.PRIORITE_MIN), settings.PRIORITE_MAX)
    if bornee != priorite:
        avertissements.append(f"priorité {priorite} ramenée à {bornee}")
    note = NoteSuivi(horodatage=horodatage, periode=objet["periode"], client=objet["client"],
                     projet=objet["projet"], statut=objet["statut"], priorite=bornee,
                     texte=objet["texte"], poste=poste)
    return note, avertissements


def lire_contenu(contenu: bytes, poste: str = "") -> tuple[list[NoteSuivi], list[str]]:
    """Notes lisibles du contenu d'un fichier, triées par horodatage (ordre du fichier en
    cas d'égalité), et avertissements « ligne N : raison » pour les lignes écartées ou
    corrigées. Une ligne abîmée n'empêche pas de lire les autres."""
    notes = []
    avertissements = []
    if contenu.startswith(b"\xef\xbb\xbf"):   # BOM ajouté par un éditeur : toléré
        contenu = contenu[3:]
    for numero, brute in enumerate(contenu.split(b"\n"), start=1):
        brute = brute.rstrip(b"\r")
        if not brute.strip():
            continue
        try:
            objet = json.loads(brute.decode(settings.ENCODAGE_SUIVI))
            note, remarques = _note_depuis_objet(objet, poste)
        except UnicodeDecodeError:
            avertissements.append(f"ligne {numero} : encodage illisible (UTF-8 attendu), ignorée")
            continue
        except json.JSONDecodeError:
            avertissements.append(f"ligne {numero} : JSON invalide, ignorée")
            continue
        except ValueError as erreur:
            avertissements.append(f"ligne {numero} : {erreur}, ignorée")
            continue
        for remarque in remarques:
            avertissements.append(f"ligne {numero} : {remarque}")
        notes.append(note)
    notes.sort(key=lambda n: n.horodatage)   # tri stable : l'ordre du fichier départage
    return notes, avertissements


# ─── Écriture ────────────────────────────────────────────────────────────────

def ligne_json(note: NoteSuivi) -> str:
    """Ligne JSON d'une note (sans le \\n final), champs dans l'ordre de l'ADR 004."""
    objet = {
        "v": settings.VERSION_LIGNE_SUIVI,
        "horodatage": note.horodatage.strftime(settings.FORMAT_HORODATAGE_SUIVI),
        "periode": note.periode,
        "client": note.client,
        "projet": note.projet,
        "statut": note.statut,
        "priorite": note.priorite,
        "texte": note.texte.replace("\r\n", "\n").replace("\r", "\n"),
    }
    return json.dumps(objet, ensure_ascii=False)


def verifier_note(note: NoteSuivi) -> None:
    """ValueError si la note ne peut pas être écrite (elle serait refusée à la relecture)."""
    if note.statut not in settings.STATUTS_SUIVI:
        raise ValueError(f"statut inconnu : {note.statut!r}")
    if isinstance(note.priorite, bool) or not isinstance(note.priorite, int):
        raise ValueError("la priorité doit être un entier")
    if not settings.PRIORITE_MIN <= note.priorite <= settings.PRIORITE_MAX:
        raise ValueError(f"priorité hors bornes [{settings.PRIORITE_MIN}, {settings.PRIORITE_MAX}]")
    if not note.client.strip() or not note.projet.strip():
        raise ValueError("client et projet obligatoires")
    jours_de_periode(note.periode)


class JournalSuivi:
    """Accès au fichier pointeuse_suivi.jsonl d'un poste."""

    def __init__(self, chemin: Path):
        self.chemin = Path(chemin)

    def lire(self) -> tuple[list[NoteSuivi], list[str]]:
        """Notes et avertissements. Fichier absent : aucune note. Fichier illisible
        (verrouillé…) : aucune note et un avertissement."""
        if not self.chemin.exists():
            return [], []
        try:
            contenu = self.chemin.read_bytes()
        except OSError as erreur:
            return [], [f"lecture impossible de {self.chemin.name} : {erreur}"]
        return lire_contenu(contenu)

    def ajouter(self, note: NoteSuivi) -> None:
        """Ajoute la note en fin de fichier, sans jamais réécrire l'existant.

        ValueError si la note est invalide ; OSError si l'écriture échoue (fichier
        verrouillé, disque plein) : l'appelant garde le texte saisi et prévient.
        """
        verifier_note(note)
        donnees = (ligne_json(note) + "\n").encode(settings.ENCODAGE_SUIVI)
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        with open(self.chemin, "ab+") as fichier:
            fichier.seek(0, os.SEEK_END)
            if fichier.tell() > 0:
                fichier.seek(-1, os.SEEK_END)
                if fichier.read(1) != b"\n":       # fin de fichier éditée à la main
                    donnees = b"\n" + donnees
            fichier.write(donnees)
            fichier.flush()
            os.fsync(fichier.fileno())


def nouvelle_note(moment: datetime, mode_periode: str, client: str, projet: str, statut: str,
                  priorite: int, texte: str, jour: date | None = None) -> NoteSuivi:
    """Note enregistrée à `moment` pour la période qui contient `jour` (par défaut le jour
    de `moment` : on peut écrire la note d'un jour passé)."""
    if jour is None:
        jour = moment.date()
    return NoteSuivi(horodatage=moment.replace(microsecond=0), periode=periode_de(jour, mode_periode),
                     client=client, projet=projet, statut=statut, priorite=priorite, texte=texte)


# ─── Règles de lecture (ADR 004) ─────────────────────────────────────────────

def notes_retenues(notes: list[NoteSuivi]) -> list[NoteSuivi]:
    """Dernière version de chaque note par (poste, client, projet, période), triées par
    horodatage. Deux postes sur la même période : les deux sont gardées."""
    dernieres: dict[tuple[str, str, str, str], NoteSuivi] = {}
    for note in sorted(notes, key=lambda n: n.horodatage):
        dernieres[(note.poste, note.client, note.projet, note.periode)] = note
    return sorted(dernieres.values(), key=lambda n: n.horodatage)


def etats_actuels(notes: list[NoteSuivi]) -> dict[tuple[str, str], NoteSuivi]:
    """Note la plus récente de chaque projet (client, projet), tous postes et toutes
    périodes confondus : elle donne le statut et la priorité actuels."""
    etats: dict[tuple[str, str], NoteSuivi] = {}
    for note in sorted(notes, key=lambda n: n.horodatage):
        etats[note.cle_projet] = note
    return etats


def statut_affiche(etat: NoteSuivi | None, dernier_pointage: datetime | None) -> str | None:
    """Statut à afficher : celui de la note la plus récente, sauf un projet terminé sur
    lequel du temps a été pointé après la note → « terminé ? » (calculé, jamais écrit).
    None si le projet n'a aucune note."""
    if etat is None:
        return None
    if etat.statut == settings.STATUT_TERMINE and dernier_pointage is not None \
            and dernier_pointage > etat.horodatage:
        return settings.STATUT_TERMINE_A_CONFIRMER
    return etat.statut


def libelle_statut(statut: str | None) -> str:
    if statut is None:
        return ""
    if statut == settings.STATUT_TERMINE_A_CONFIRMER:
        return settings.LIBELLE_TERMINE_A_CONFIRMER
    return settings.STATUTS_SUIVI.get(statut, statut)


def est_masque(statut: str | None) -> bool:
    """Projet masqué des listes : terminé et confirmé (« terminé ? » reste visible)."""
    return statut == settings.STATUT_TERMINE


def note_de_periode(notes: list[NoteSuivi], client: str, projet: str, periode: str,
                    poste: str = "") -> NoteSuivi | None:
    """Version actuelle de la note d'une période (la plus récente), pour un poste."""
    trouvee = None
    for note in sorted(notes, key=lambda n: n.horodatage):
        if (note.poste, note.client, note.projet, note.periode) == (poste, client, projet, periode):
            trouvee = note
    return trouvee


def note_precedente(notes: list[NoteSuivi], client: str, projet: str, periode: str,
                    poste: str = "") -> NoteSuivi | None:
    """Note retenue de la dernière période qui commence avant `periode` (« Message du … »)."""
    debut, _ = jours_de_periode(periode)
    candidates = [n for n in notes_retenues(notes)
                  if (n.poste, n.client, n.projet) == (poste, client, projet)
                  and jours_de_periode(n.periode)[0] < debut]
    if not candidates:
        return None
    return max(candidates, key=lambda n: (jours_de_periode(n.periode)[0], n.horodatage))


# ─── Temps pointé (depuis pointeuse.csv) ─────────────────────────────────────

def minutes_par_jour(lignes: list[Ligne], client: str, projet: str) -> dict[date, int]:
    """Minutes pointées sur un projet, par jour (une ligne qui passe minuit est partagée)."""
    temps: dict[date, int] = {}
    for ligne in lignes:
        if (ligne.client, ligne.projet) != (client, projet):
            continue
        debut = ligne.debut
        while debut < ligne.fin:
            minuit = datetime.combine(debut.date() + timedelta(days=1), time.min)
            fin = min(ligne.fin, minuit)
            temps[debut.date()] = temps.get(debut.date(), 0) + int((fin - debut).total_seconds() // 60)
            debut = fin
    return temps


def dernier_pointage(lignes: list[Ligne], client: str, projet: str) -> datetime | None:
    """Fin du dernier temps pointé sur le projet (sert au statut calculé « terminé ? »)."""
    fins = [ligne.fin for ligne in lignes if (ligne.client, ligne.projet) == (client, projet)]
    if not fins:
        return None
    return max(fins)


# ─── Liste des projets et historique (fenêtre Suivi) ─────────────────────────

@dataclass(frozen=True)
class ProjetSuivi:
    client: str
    projet: str
    statut: str | None         # statut affiché (peut être « terminé ? ») ; None : aucune note
    priorite: int
    visible_config: bool       # False : client ou projet masqué dans la config (visible = false)

    @property
    def cle(self) -> tuple[str, str]:
        return (self.client, self.projet)

    @property
    def masque(self) -> bool:
        return not self.visible_config or est_masque(self.statut)


def projets_suivis(projets_config: list[tuple[str, str, bool]], notes: list[NoteSuivi],
                   lignes: list[Ligne]) -> list[ProjetSuivi]:
    """Projets de la config (client, projet, visible) et projets qui n'ont que des notes,
    triés par priorité, puis client, puis projet."""
    etats = etats_actuels(notes)
    visibles: dict[tuple[str, str], bool] = {}
    for client, projet, visible in projets_config:
        visibles[(client, projet)] = visible
    for cle in etats:
        visibles.setdefault(cle, True)
    resultat = []
    for (client, projet), visible in visibles.items():
        etat = etats.get((client, projet))
        priorite = settings.PRIORITE_DEFAUT
        if etat is not None:
            priorite = etat.priorite
        statut = statut_affiche(etat, dernier_pointage(lignes, client, projet))
        resultat.append(ProjetSuivi(client, projet, statut, priorite, visible))
    return sorted(resultat, key=lambda p: (p.priorite, p.client.casefold(), p.projet.casefold()))


@dataclass(frozen=True)
class EntreeHistorique:
    periode: str               # « 2026-11-14 » ou « 2026-W46 »
    debut: date
    fin: date
    minutes: int               # temps pointé sur la période (somme des jours pour une semaine)
    notes: tuple[NoteSuivi, ...]   # versions retenues (une par poste), souvent 0 ou 1

    @property
    def est_semaine(self) -> bool:
        return est_periode_semaine(self.periode)


def historique(notes: list[NoteSuivi], minutes: dict[date, int], client: str,
               projet: str) -> list[EntreeHistorique]:
    """Historique d'un projet, du plus récent au plus ancien : chaque jour pointé ou noté,
    et chaque semaine notée (placée avant ses jours)."""
    par_periode: dict[str, list[NoteSuivi]] = {}
    for note in notes_retenues(notes):
        if note.cle_projet == (client, projet):
            par_periode.setdefault(note.periode, []).append(note)
    for jour, duree in minutes.items():
        if duree > 0:
            par_periode.setdefault(jour.strftime(settings.FORMAT_PERIODE_JOUR), [])
    entrees = []
    for periode, notes_periode in par_periode.items():
        debut, fin = jours_de_periode(periode)
        total = sum(duree for jour, duree in minutes.items() if debut <= jour <= fin)
        entrees.append(EntreeHistorique(periode, debut, fin, total, tuple(notes_periode)))
    return sorted(entrees, key=lambda e: (e.fin, e.est_semaine), reverse=True)


def extrait(texte: str, longueur: int = settings.LONGUEUR_EXTRAIT_NOTE) -> str:
    """Début d'une note sur une ligne (retours à la ligne remplacés par « / »)."""
    morceaux = [ligne.strip() for ligne in texte.splitlines() if ligne.strip()]
    resume = " / ".join(morceaux)
    if len(resume) > longueur:
        return resume[:longueur - 1].rstrip() + "…"
    return resume

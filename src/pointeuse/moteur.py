"""Moteur de pointage, sans interface (CDC étapes 2, 3, 5 et 6).

Une seule chose à la fois : une tâche ou une pause est « ouverte » ; la démarrer
ferme la précédente, qui part dans le CSV. L'heure est injectée (horloge) pour
que les tests puissent simuler une journée.

Sauvegarde de sécurité : l'état est écrit dans pointeuse_en_cours.json à chaque
changement et à chaque signe_de_vie() (toutes les 5 min côté interface). Après
un plantage, reprendre_apres_arret() écrit la ligne ouverte jusqu'à la dernière
sauvegarde et rend l'Absence à faire qualifier par l'utilisateur.
"""

import json
import os
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from pointeuse import settings
from pointeuse.config import Config
from pointeuse.evenements import JournalEvenements
from pointeuse.journal import Journal, JournalBloque, Ligne, a_la_minute, decouper

VERSION_EN_COURS = 1


@dataclass(frozen=True)
class LigneOuverte:
    """Tâche ou pause commencée, pas encore terminée."""
    debut: datetime
    client: str
    projet: str = ""
    tache: str = ""
    description: str = ""

    @property
    def est_pause(self) -> bool:
        return self.client == settings.CLIENT_PAUSE

    def meme_tache(self, client: str, projet: str, tache: str) -> bool:
        return (self.client, self.projet, self.tache) == (client, projet, tache)

    def fermer(self, fin: datetime) -> Ligne:
        return Ligne(self.debut, fin, self.client, self.projet, self.tache, self.description)

    def vers_dict(self) -> dict:
        return {
            "debut": self.debut.isoformat(),
            "client": self.client,
            "projet": self.projet,
            "tache": self.tache,
            "description": self.description,
        }

    @classmethod
    def depuis_dict(cls, d: dict) -> "LigneOuverte":
        return cls(
            debut=datetime.fromisoformat(d["debut"]),
            client=d["client"],
            projet=d.get("projet", ""),
            tache=d.get("tache", ""),
            description=d.get("description", ""),
        )


class InsertionImpossible(ValueError):
    """Plage refusée (dans le futur, fin avant début) ou CSV pas en état d'être réécrit."""


@dataclass(frozen=True)
class Absence:
    """Trou à faire qualifier par l'utilisateur (« retour d'absence »)."""
    debut: datetime
    fin: datetime
    tache_precedente: LigneOuverte | None

    @property
    def duree_min(self) -> int:
        return int((self.fin - self.debut).total_seconds() // 60)


class Moteur:

    def __init__(self, config: Config, journal: Journal, chemin_en_cours: Path,
                 horloge: Callable[[], datetime] = datetime.now,
                 evenements: JournalEvenements | None = None):
        self.config = config
        self.journal = journal
        self.evenements = evenements   # journal des événements du poste (vue Journée), facultatif
        self.chemin_en_cours = Path(chemin_en_cours)
        self.horloge = horloge
        self.ligne_ouverte: LigneOuverte | None = None
        self.derniere_tache: LigneOuverte | None = None   # pour « Reprendre » après une pause
        self.en_attente: list[Ligne] = []                 # lignes pas encore écrites (CSV bloqué)
        self.derniere_sauvegarde: datetime | None = None
        self.derniere_erreur: str = ""
        self.absence_debut: datetime | None = None        # veille / verrouillage en cours (étape 6)

    # ─── État ────────────────────────────────────────────────────────────────

    @property
    def en_pause(self) -> bool:
        return self.ligne_ouverte is not None and self.ligne_ouverte.est_pause

    @property
    def ecriture_bloquee(self) -> bool:
        """Vrai tant que des lignes attendent de pouvoir être écrites dans le CSV."""
        return len(self.en_attente) > 0

    # ─── Actions de l'utilisateur ────────────────────────────────────────────

    def demarrer(self, client: str, projet: str, tache: str | None = None, description: str = "",
                 projet_obligatoire: bool = True) -> None:
        """Démarre (ou change de) tâche. Les noms libres sont ajoutés à la config.

        projet_obligatoire = False : bouton rapide « client seul », le projet se complète
        ensuite avec Modifier (le champ Projet est en rouge tant qu'il est vide).
        """
        client, projet, tache = self.config.ajouter(client, projet, tache, projet_obligatoire)
        if tache is None:
            tache = ""
        description = description.strip()
        ouverte = self.ligne_ouverte
        if ouverte is not None and not ouverte.est_pause and ouverte.meme_tache(client, projet, tache):
            self.modifier_description(description)
            return
        maintenant = self._maintenant()
        self._clore(maintenant)
        self.ligne_ouverte = LigneOuverte(maintenant, client, projet, tache, description)
        self.derniere_tache = self.ligne_ouverte
        self._ecrire_et_sauvegarder()

    def pause(self, description: str = "") -> None:
        """Ouvre une pause (description : « Repas » pour le bouton Repas).

        Déjà en pause : la pause continue ; une description donnée la remplace (Pause puis Repas).
        """
        description = description.strip()
        if self.en_pause:
            if description and description != self.ligne_ouverte.description:
                self.ligne_ouverte = replace(self.ligne_ouverte, description=description)
                self.sauvegarder()
            return
        maintenant = self._maintenant()
        self._clore(maintenant)
        self.ligne_ouverte = LigneOuverte(maintenant, settings.CLIENT_PAUSE, description=description)
        self._ecrire_et_sauvegarder()

    def reprendre(self) -> bool:
        """Ferme la pause et relance la dernière tâche (description vidée). Faux si rien à reprendre."""
        if not self.en_pause or self.derniere_tache is None:
            return False
        maintenant = self._maintenant()
        self._clore(maintenant)
        self.ligne_ouverte = replace(self.derniere_tache, debut=maintenant, description="")
        self.derniere_tache = self.ligne_ouverte
        self._ecrire_et_sauvegarder()
        return True

    def modifier_description(self, description: str) -> None:
        if self.ligne_ouverte is None or self.ligne_ouverte.est_pause:
            return
        self.ligne_ouverte = replace(self.ligne_ouverte, description=description.strip())
        self.derniere_tache = self.ligne_ouverte
        self.sauvegarder()

    def modifier(self, client: str, projet: str, tache: str | None = None, description: str = "") -> bool:
        """Bouton Modifier : corrige la tâche en cours sans la couper (l'heure de début est gardée).

        Projet vide accepté (il reste à compléter). Faux si aucune tâche n'est en cours.
        Les noms libres sont ajoutés à la config, comme pour Démarrer.
        """
        if self.ligne_ouverte is None or self.ligne_ouverte.est_pause:
            return False
        client, projet, tache = self.config.ajouter(client, projet, tache, projet_obligatoire=False)
        if tache is None:
            tache = ""
        self.ligne_ouverte = replace(self.ligne_ouverte, client=client, projet=projet, tache=tache,
                                     description=description.strip())
        self.derniere_tache = self.ligne_ouverte
        self.sauvegarder()
        return True

    def arreter(self) -> None:
        """Bouton Stop, ou fermeture du programme : la ligne en cours part dans le CSV, rien ne suit.

        Arrêt du PC depuis l'écran de verrouillage : la ligne s'arrête au verrouillage.
        """
        fin = self._maintenant()
        if self.absence_debut is not None and self.ligne_ouverte is not None:
            fin = max(self.ligne_ouverte.debut, min(fin, self.absence_debut))
        self.absence_debut = None
        self._clore(fin)
        self._ecrire_et_sauvegarder()

    def enregistrer_absence(self, absence: Absence, client: str | None = None, projet: str = "",
                            tache: str | None = None, description: str = "") -> None:
        """Qualifie une absence : sans client → ligne PAUSE, sinon la tâche déclarée."""
        if client is None:
            ligne = Ligne(absence.debut, absence.fin, settings.CLIENT_PAUSE)
        else:
            client, projet, tache = self.config.ajouter(client, projet, tache)
            if tache is None:
                tache = ""
            ligne = Ligne(absence.debut, absence.fin, client, projet, tache, description.strip())
        if ligne.duree_min > 0:
            self.en_attente.append(ligne)
        self._ecrire_et_sauvegarder()

    # ─── Pause automatique : veille, session verrouillée (étape 6) ───────────

    def absence_commencee(self, debut: datetime) -> None:
        """Le PC se verrouille ou s'endort : on note l'heure, la ligne reste ouverte.

        Elle n'est coupée qu'au retour, si l'absence a duré (voir absence_terminee). L'heure
        est sauvegardée : après une coupure pendant l'absence, la reprise coupe la ligne ici.
        """
        if self.absence_debut is not None:
            return
        self.absence_debut = a_la_minute(debut)
        self.sauvegarder()

    def absence_longue(self, debut: datetime, fin: datetime) -> bool:
        """Absence qui passe un changement de jour ou dure au moins absence_longue_h : pas de question."""
        if fin.date() != debut.date():
            return True
        return fin - debut >= timedelta(hours=self.config.reglage("absence_longue_h"))

    def absence_terminee(self, fin: datetime) -> Absence | None:
        """Retour : rend l'Absence à faire qualifier, ou None si rien à demander.

        Rien à demander si l'absence est plus courte que detection_absence_min (la tâche
        continue sans coupure), ou s'il n'y avait pas de tâche en cours (rien, ou pause :
        la pause continue).

        Absence longue (nuit, ou au moins absence_longue_h) : rien à demander non plus, mais
        la tâche ou la pause en cours est clôturée à l'heure du départ et rien ne redémarre.
        """
        debut = self.absence_debut
        if debut is None:
            return None
        self.absence_debut = None
        fin = a_la_minute(fin)
        ouverte = self.ligne_ouverte
        trop_court = (fin - debut).total_seconds() < self.config.reglage("detection_absence_min") * 60
        if trop_court or ouverte is None or fin <= ouverte.debut:
            self.sauvegarder()
            return None
        if self.absence_longue(debut, fin):
            self._clore(max(debut, ouverte.debut))
            self._ecrire_et_sauvegarder()
            return None
        if ouverte.est_pause:
            self.sauvegarder()
            return None
        debut = max(debut, ouverte.debut)
        self._clore(debut)
        self._ecrire_et_sauvegarder()
        return Absence(debut, fin, ouverte)

    # ─── Insertion d'un temps défini (onglet « Insérer / Journée ») ──────────

    def verifier_insertion(self, debut: datetime, fin: datetime) -> list[Ligne]:
        """Contrôle la plage et retourne les lignes du CSV qu'elle remplacerait entièrement.

        L'interface demande confirmation si la liste n'est pas vide. Lève InsertionImpossible.
        """
        debut, fin = a_la_minute(debut), a_la_minute(fin)
        _, recouvertes = decouper(self._lignes_pour_insertion(debut, fin), debut, fin)
        return recouvertes

    def inserer(self, debut: datetime, fin: datetime, client: str, projet: str,
                tache: str | None = None, description: str = "") -> None:
        """Insère une tâche de debut à fin : elle découpe ce qu'elle recouvre (CSV et ligne en cours).

        Le CSV est réécrit d'un bloc (écriture atomique), puis l'état est sauvegardé.
        Lève InsertionImpossible, ValueError (noms) ou JournalBloque : rien n'est alors modifié
        dans le CSV ni dans la ligne en cours.
        """
        debut, fin = a_la_minute(debut), a_la_minute(fin)
        lignes = self._lignes_pour_insertion(debut, fin)
        client, projet, tache = self.config.ajouter(client, projet, tache)
        if tache is None:
            tache = ""
        restantes, _ = decouper(lignes, debut, fin)
        a_ajouter = [Ligne(debut, fin, client, projet, tache, description.strip())]

        # La ligne en cours est découpée aussi : sa partie avant la plage est clôturée,
        # elle reprend à la fin de la plage.
        ouverte = self.ligne_ouverte
        if ouverte is not None and ouverte.debut < fin:
            if ouverte.debut < debut:
                a_ajouter.append(ouverte.fermer(debut))
            ouverte = replace(ouverte, debut=fin)

        self.journal.reecrire(restantes + a_ajouter)
        self.ligne_ouverte = ouverte
        self.derniere_erreur = ""
        self.sauvegarder()

    def lignes_du_jour(self, jour: date) -> list[Ligne]:
        """Lignes terminées qui touchent ce jour : CSV + lignes en attente, triées."""
        debut_jour = datetime.combine(jour, datetime.min.time())
        fin_jour = debut_jour + timedelta(days=1)
        lignes = self.journal.lignes_du_jour(jour)
        for ligne in self.en_attente:
            if ligne.debut < fin_jour and ligne.fin > debut_jour:
                lignes.append(ligne)
        return sorted(lignes, key=lambda l: l.debut)

    def _lignes_pour_insertion(self, debut: datetime, fin: datetime) -> list[Ligne]:
        """Valide la plage et l'état du CSV ; retourne les lignes actuelles du CSV."""
        if fin <= debut:
            raise InsertionImpossible("L'heure de fin doit être après l'heure de début.")
        if fin > self._maintenant():
            raise InsertionImpossible("Impossible d'insérer un temps dans le futur.")
        if self.en_attente:
            raise InsertionImpossible(f"{len(self.en_attente)} ligne(s) attendent d'être écrites : "
                                      f"fermez {self.journal.chemin.name} puis réessayez.")
        lignes = self.journal.lire()
        if self.journal.lignes_ignorees > 0:
            # Réécrire le fichier ferait disparaître ces lignes : on laisse l'utilisateur corriger.
            raise InsertionImpossible(f"{self.journal.lignes_ignorees} ligne(s) illisible(s) dans "
                                      f"{self.journal.chemin.name} : corrigez-les avant d'insérer.")
        return lignes

    # ─── Sauvegarde de sécurité et reprise ───────────────────────────────────

    def signe_de_vie(self) -> None:
        """Appel périodique (réglage sauvegarde_min) : réessaie le CSV, sauvegarde l'état."""
        self._ecrire_et_sauvegarder()

    def sauvegarder(self) -> None:
        maintenant = self._maintenant()
        etat = {
            "version": VERSION_EN_COURS,
            "derniere_sauvegarde": maintenant.isoformat(),
            "ligne_ouverte": None,
            "derniere_tache": None,
            "en_attente": [ligne.vers_dict() for ligne in self.en_attente],
            "absence_debut": None,
        }
        if self.absence_debut is not None:
            etat["absence_debut"] = self.absence_debut.isoformat()
        if self.ligne_ouverte is not None:
            etat["ligne_ouverte"] = self.ligne_ouverte.vers_dict()
        if self.derniere_tache is not None:
            etat["derniere_tache"] = self.derniere_tache.vers_dict()
        temporaire = self.chemin_en_cours.with_suffix(".tmp")
        try:
            self.chemin_en_cours.parent.mkdir(parents=True, exist_ok=True)
            temporaire.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporaire, self.chemin_en_cours)
        except OSError as erreur:
            self.derniere_erreur = f"Sauvegarde de sécurité impossible : {erreur}"
            return
        self.derniere_sauvegarde = maintenant

    def reprendre_apres_arret(self) -> Absence | None:
        """Au démarrage : récupère l'état laissé par la session précédente.

        Si une ligne était ouverte (plantage, coupure), elle est écrite jusqu'à
        la dernière sauvegarde et l'Absence qui suit est rendue à l'interface
        (sauf absence longue : rien à demander).
        """
        etat = self._lire_etat()
        absence = None
        if etat is not None:
            sauvees = [Ligne.depuis_dict(d) for d in etat.get("en_attente", [])]
            self.en_attente = self._pas_encore_dans_le_csv(sauvees) + self.en_attente
            if etat.get("derniere_tache"):
                self.derniere_tache = LigneOuverte.depuis_dict(etat["derniere_tache"])
            if etat.get("ligne_ouverte"):
                ouverte = LigneOuverte.depuis_dict(etat["ligne_ouverte"])
                arret = datetime.fromisoformat(etat["derniere_sauvegarde"])
                if etat.get("absence_debut"):
                    # Coupure pendant une veille / un verrouillage : la tâche s'est arrêtée là.
                    arret = min(arret, datetime.fromisoformat(etat["absence_debut"]))
                arret = max(arret, ouverte.debut)
                ligne = ouverte.fermer(arret)
                if ligne.duree_min > 0:
                    self.en_attente.append(ligne)
                maintenant = self._maintenant()
                # Trou long (nuit, ou au moins absence_longue_h) : pas de question, comme après une veille.
                if maintenant > arret and not self.absence_longue(arret, maintenant):
                    absence = Absence(arret, maintenant, ouverte)
        self.ligne_ouverte = None
        self.absence_debut = None
        self._ecrire_et_sauvegarder()
        return absence

    # ─── Interne ─────────────────────────────────────────────────────────────

    def _maintenant(self) -> datetime:
        return a_la_minute(self.horloge())

    def _clore(self, fin: datetime) -> None:
        """Ferme la ligne ouverte et la met en file d'écriture (sauf durée nulle)."""
        if self.ligne_ouverte is None:
            return
        ligne = self.ligne_ouverte.fermer(fin)
        if ligne.duree_min > 0:
            self.en_attente.append(ligne)
        self.ligne_ouverte = None

    def _ecrire_et_sauvegarder(self) -> None:
        """Règle (MP 2026-11-17) : d'abord la sauvegarde JSON, ensuite le CSV.

        Une ligne terminée est donc toujours dans pointeuse_en_cours.json avant
        d'être ajoutée au CSV : un plantage entre les deux ne perd rien (et le
        doublon éventuel est écarté à la reprise, voir _deja_dans_le_csv).
        """
        self.sauvegarder()
        if self.en_attente:
            self._vider_file()
            self.sauvegarder()

    def _vider_file(self) -> None:
        """Écrit les lignes en attente, dans l'ordre. En cas d'échec, elles restent en file."""
        if not self.en_attente:
            return
        try:
            self.journal.ajouter(self.en_attente)
        except JournalBloque as erreur:
            self.derniere_erreur = str(erreur)
            return
        self.en_attente = []
        self.derniere_erreur = ""

    def _pas_encore_dans_le_csv(self, lignes: list[Ligne]) -> list[Ligne]:
        """Écarte les lignes déjà écrites (plantage juste après l'écriture du CSV)."""
        if not lignes:
            return []
        try:
            deja_ecrites = set(self.journal.lire())
        except OSError:
            return lignes   # CSV illisible pour l'instant : on garde tout en attente
        resultat = []
        for ligne in lignes:
            if ligne not in deja_ecrites:
                resultat.append(ligne)
        return resultat

    def _lire_etat(self) -> dict | None:
        """Lit pointeuse_en_cours.json. Un fichier illisible est mis de côté, pas effacé."""
        if not self.chemin_en_cours.exists():
            return None
        try:
            etat = json.loads(self.chemin_en_cours.read_text(encoding="utf-8"))
            if etat.get("version") != VERSION_EN_COURS:
                raise ValueError("version inconnue")
            # Valide tout de suite les champs, pour ne pas planter à mi-reprise.
            for d in etat.get("en_attente", []):
                Ligne.depuis_dict(d)
            for cle in ("ligne_ouverte", "derniere_tache"):
                if etat.get(cle):
                    LigneOuverte.depuis_dict(etat[cle])
            datetime.fromisoformat(etat["derniere_sauvegarde"])
            if etat.get("absence_debut"):
                datetime.fromisoformat(etat["absence_debut"])
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as erreur:
            illisible = self.chemin_en_cours.with_suffix(".illisible.json")
            os.replace(self.chemin_en_cours, illisible)
            self.derniere_erreur = f"Sauvegarde de sécurité illisible, mise de côté dans {illisible.name} : {erreur}"
            return None
        return etat

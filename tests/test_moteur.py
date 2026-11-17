"""Tests du moteur de pointage (CDC étapes 2 et 3)."""

import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from pointeuse.config import Config
from pointeuse.journal import Journal, JournalBloque
from pointeuse.moteur import Moteur

EXEMPLE = Path(__file__).resolve().parents[1] / "docs" / "exemples" / "pointeuse_config.toml"


class Horloge:
    """Horloge réglable à la main : h.regler("14:00")."""

    def __init__(self):
        self.moment = datetime(2026, 11, 17, 8, 0, 0)

    def regler(self, heure: str, secondes: int = 0) -> None:
        heures, minutes = heure.split(":")
        self.moment = self.moment.replace(hour=int(heures), minute=int(minutes), second=secondes)

    def __call__(self) -> datetime:
        return self.moment


class JournalVerrouillable(Journal):
    """Simule pointeuse.csv ouvert dans Excel."""
    verrouille = False

    def ajouter(self, lignes):
        if self.verrouille:
            raise JournalBloque("fichier verrouillé")
        super().ajouter(lignes)


@pytest.fixture
def dossier(tmp_path):
    shutil.copy(EXEMPLE, tmp_path / "pointeuse_config.toml")
    return tmp_path


@pytest.fixture
def horloge():
    return Horloge()


def nouveau_moteur(dossier, horloge):
    return Moteur(
        Config(dossier / "pointeuse_config.toml"),
        JournalVerrouillable(dossier / "pointeuse.csv"),
        dossier / "pointeuse_en_cours.json",
        horloge,
    )


@pytest.fixture
def moteur(dossier, horloge):
    return nouveau_moteur(dossier, horloge)


def resume(moteur):
    """Lignes du CSV sous forme courte : (début, fin, client, projet, tâche, description)."""
    return [
        (l.debut.strftime("%H:%M"), l.fin.strftime("%H:%M"), l.client, l.projet, l.tache, l.description)
        for l in moteur.journal.lire()
    ]


# ─── Démarrer / changer ──────────────────────────────────────────────────────

def test_changer_de_tache_ecrit_la_precedente(moteur, horloge):
    horloge.regler("10:12")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2", "câblage", "bornier")
    horloge.regler("10:30", secondes=45)
    moteur.demarrer("Gamma Énergie", "Supervision serres")
    assert resume(moteur) == [("10:12", "10:30", "Alpha Industrie", "Armoire ligne 2", "câblage", "bornier")]
    assert moteur.ligne_ouverte.client == "Gamma Énergie"
    assert moteur.ligne_ouverte.tache == ""


def test_noms_ramenes_a_la_config(moteur, horloge):
    moteur.demarrer(" alpha industrie", "ARMOIRE LIGNE 2", "Câblage")
    assert (moteur.ligne_ouverte.client, moteur.ligne_ouverte.projet) == ("Alpha Industrie", "Armoire ligne 2")
    assert moteur.ligne_ouverte.tache == "câblage"


def test_texte_libre_ajoute_a_la_config(moteur):
    moteur.demarrer("Delta Services", "Audit", "visite")
    assert Config(moteur.config.chemin).taches_projet("Delta Services", "Audit") == ["visite"]


def test_meme_tache_ne_coupe_pas_la_ligne(moteur, horloge):
    horloge.regler("09:00")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2", "câblage")
    horloge.regler("09:20")
    moteur.demarrer("alpha industrie", "armoire ligne 2", "câblage", "nouvelle description")
    assert moteur.journal.lire() == []
    assert moteur.ligne_ouverte.debut.strftime("%H:%M") == "09:00"
    assert moteur.ligne_ouverte.description == "nouvelle description"


def test_ligne_de_moins_d_une_minute_ignoree(moteur, horloge):
    horloge.regler("09:00", secondes=5)
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("09:00", secondes=50)
    moteur.demarrer("Gamma Énergie", "Supervision serres")
    assert moteur.journal.lire() == []


def test_journee_type(moteur, horloge):
    horloge.regler("08:30")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2", "cdc")
    horloge.regler("10:00")
    moteur.pause()
    horloge.regler("10:15")
    assert moteur.reprendre() is True
    horloge.regler("12:00")
    moteur.arreter()
    assert resume(moteur) == [
        ("08:30", "10:00", "Alpha Industrie", "Armoire ligne 2", "cdc", ""),
        ("10:00", "10:15", "PAUSE", "", "", ""),
        ("10:15", "12:00", "Alpha Industrie", "Armoire ligne 2", "cdc", ""),
    ]
    assert moteur.ligne_ouverte is None


# ─── Pause ───────────────────────────────────────────────────────────────────

def test_double_pause_sans_effet(moteur, horloge):
    horloge.regler("09:00")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("10:00")
    moteur.pause()
    horloge.regler("10:05")
    moteur.pause()
    assert moteur.ligne_ouverte.debut.strftime("%H:%M") == "10:00"


def test_reprendre_vide_la_description(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2", "cdc", "relecture")
    horloge.regler("09:00")
    moteur.pause()
    horloge.regler("09:10")
    moteur.reprendre()
    assert moteur.ligne_ouverte.description == ""


def test_reprendre_sans_pause_ou_sans_tache(moteur, horloge):
    assert moteur.reprendre() is False
    moteur.pause()
    assert moteur.reprendre() is False   # pause avant toute tâche : rien à reprendre
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    assert moteur.reprendre() is False   # pas en pause


def test_demarrer_pendant_la_pause_la_ferme(moteur, horloge):
    horloge.regler("09:00")
    moteur.pause()
    horloge.regler("09:30")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    assert resume(moteur) == [("09:00", "09:30", "PAUSE", "", "", "")]


def test_modifier_description_ignoree_en_pause(moteur):
    moteur.pause()
    moteur.modifier_description("x")
    assert moteur.ligne_ouverte.description == ""


# ─── CSV verrouillé ──────────────────────────────────────────────────────────

def test_csv_verrouille_lignes_mises_en_attente(moteur, horloge):
    horloge.regler("09:00")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    moteur.journal.verrouille = True
    horloge.regler("10:00")
    moteur.demarrer("Gamma Énergie", "Supervision serres")
    horloge.regler("11:00")
    moteur.pause()
    assert moteur.ecriture_bloquee
    assert "verrouillé" in moteur.derniere_erreur
    assert moteur.journal.lire() == []

    moteur.journal.verrouille = False
    moteur.signe_de_vie()
    assert not moteur.ecriture_bloquee
    assert moteur.derniere_erreur == ""
    assert [l[2] for l in resume(moteur)] == ["Alpha Industrie", "Gamma Énergie"]


def test_lignes_en_attente_survivent_a_un_plantage(dossier, horloge):
    moteur = nouveau_moteur(dossier, horloge)
    horloge.regler("09:00")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    moteur.journal.verrouille = True
    horloge.regler("10:00")
    moteur.demarrer("Gamma Énergie", "Supervision serres")
    # plantage : le moteur disparaît sans arreter()

    horloge.regler("10:30")
    relance = nouveau_moteur(dossier, horloge)
    relance.reprendre_apres_arret()
    assert resume(relance) == [
        ("09:00", "10:00", "Alpha Industrie", "Armoire ligne 2", "", ""),
    ]


# ─── Sauvegarde de sécurité et reprise ───────────────────────────────────────

def test_plantage_14h_17h_exemple_du_cdc(dossier, horloge):
    moteur = nouveau_moteur(dossier, horloge)
    horloge.regler("14:00")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2", "câblage")
    for heure in ("14:05", "15:00", "16:55"):
        horloge.regler(heure)
        moteur.signe_de_vie()
    # plantage à 16:58, redémarrage à 17:10

    horloge.regler("17:10")
    relance = nouveau_moteur(dossier, horloge)
    absence = relance.reprendre_apres_arret()
    assert resume(relance) == [("14:00", "16:55", "Alpha Industrie", "Armoire ligne 2", "câblage", "")]
    assert (absence.debut.strftime("%H:%M"), absence.fin.strftime("%H:%M")) == ("16:55", "17:10")
    assert absence.duree_min == 15
    assert absence.tache_precedente.projet == "Armoire ligne 2"
    assert relance.ligne_ouverte is None

    relance.enregistrer_absence(absence)
    assert resume(relance)[-1] == ("16:55", "17:10", "PAUSE", "", "", "")


def test_absence_declaree_sur_une_tache(dossier, horloge):
    moteur = nouveau_moteur(dossier, horloge)
    horloge.regler("14:00")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("17:00")
    relance = nouveau_moteur(dossier, horloge)
    absence = relance.reprendre_apres_arret()
    relance.enregistrer_absence(absence, "Bêta Automatismes", "Carte capteur v2", "prototype", "essai chez le client")
    assert resume(relance)[-1] == ("14:00", "17:00", "Bêta Automatismes", "Carte capteur v2", "prototype", "essai chez le client")


def test_arret_normal_pas_d_absence(dossier, horloge):
    moteur = nouveau_moteur(dossier, horloge)
    horloge.regler("09:00")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("12:00")
    moteur.arreter()
    horloge.regler("14:00")
    relance = nouveau_moteur(dossier, horloge)
    assert relance.reprendre_apres_arret() is None
    assert len(relance.journal.lire()) == 1


def test_reprise_garde_la_derniere_tache(dossier, horloge):
    moteur = nouveau_moteur(dossier, horloge)
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2", "cdc")
    horloge.regler("09:00")
    moteur.pause()
    horloge.regler("10:00")
    relance = nouveau_moteur(dossier, horloge)
    absence = relance.reprendre_apres_arret()
    assert absence.tache_precedente.est_pause
    assert relance.derniere_tache.tache == "cdc"


def test_premier_lancement(moteur):
    assert moteur.reprendre_apres_arret() is None
    assert moteur.chemin_en_cours.exists()


def test_fichier_de_reprise_contenu(moteur, horloge):
    horloge.regler("09:00")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2", "cdc", "relecture")
    etat = json.loads(moteur.chemin_en_cours.read_text(encoding="utf-8"))
    assert etat["version"] == 1
    assert etat["ligne_ouverte"]["description"] == "relecture"
    assert etat["derniere_sauvegarde"] == "2026-11-17T09:00:00"


def test_fichier_de_reprise_illisible_mis_de_cote(moteur):
    moteur.chemin_en_cours.write_text("{pas du json", encoding="utf-8")
    assert moteur.reprendre_apres_arret() is None
    assert (moteur.chemin_en_cours.parent / "pointeuse_en_cours.illisible.json").exists()
    assert "illisible" in moteur.derniere_erreur


# ─── Ordre d'écriture : JSON d'abord, CSV ensuite (règle MP 2026-11-17) ──────

class JournalEspion(Journal):
    """Relève le contenu de pointeuse_en_cours.json au moment où le CSV est écrit."""
    vu_dans_le_json = None

    def ajouter(self, lignes):
        chemin_json = self.chemin.parent / "pointeuse_en_cours.json"
        self.vu_dans_le_json = json.loads(chemin_json.read_text(encoding="utf-8"))["en_attente"]
        super().ajouter(lignes)


def test_point_sauvegarde_dans_le_json_avant_le_csv(dossier, horloge):
    moteur = Moteur(Config(dossier / "pointeuse_config.toml"), JournalEspion(dossier / "pointeuse.csv"),
                    dossier / "pointeuse_en_cours.json", horloge)
    horloge.regler("09:00")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("10:00")
    moteur.demarrer("Gamma Énergie", "Supervision serres")
    assert [d["client"] for d in moteur.journal.vu_dans_le_json] == ["Alpha Industrie"]
    # une fois le CSV écrit, le JSON est vidé
    etat = json.loads(moteur.chemin_en_cours.read_text(encoding="utf-8"))
    assert etat["en_attente"] == []


def test_plantage_entre_csv_et_json_pas_de_doublon(dossier, horloge):
    moteur = nouveau_moteur(dossier, horloge)
    horloge.regler("09:00")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("10:00")
    # simule le plantage : CSV écrit, mais le JSON garde encore la ligne en attente
    moteur.sauvegarder = lambda: None
    moteur._clore(horloge())
    Moteur.sauvegarder(moteur)
    moteur._vider_file()

    horloge.regler("10:30")
    relance = nouveau_moteur(dossier, horloge)
    relance.reprendre_apres_arret()
    assert resume(relance) == [("09:00", "10:00", "Alpha Industrie", "Armoire ligne 2", "", "")]


# ─── Insérer un temps défini (étape 5) ───────────────────────────────────────

from pointeuse.moteur import InsertionImpossible  # noqa: E402


def a(heure: str) -> datetime:
    heures, minutes = heure.split(":")
    return datetime(2026, 11, 17, int(heures), int(minutes))


def test_inserer_dans_une_ligne_terminee(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2", "câblage")
    horloge.regler("12:00")
    moteur.pause()
    moteur.inserer(a("10:00"), a("10:30"), "Bêta Automatismes", "Carte capteur v2", "schéma", "appel")
    assert resume(moteur) == [
        ("08:00", "10:00", "Alpha Industrie", "Armoire ligne 2", "câblage", ""),
        ("10:00", "10:30", "Bêta Automatismes", "Carte capteur v2", "schéma", "appel"),
        ("10:30", "12:00", "Alpha Industrie", "Armoire ligne 2", "câblage", ""),
    ]
    assert moteur.en_pause


def test_inserer_decoupe_la_ligne_en_cours(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("09:00")
    moteur.inserer(a("08:45"), a("09:00"), "Gamma Énergie", "Supervision serres", "réunion")
    assert resume(moteur) == [
        ("08:00", "08:45", "Alpha Industrie", "Armoire ligne 2", "", ""),
        ("08:45", "09:00", "Gamma Énergie", "Supervision serres", "réunion", ""),
    ]
    assert moteur.ligne_ouverte.debut == a("09:00")
    assert moteur.ligne_ouverte.projet == "Armoire ligne 2"
    # l'état sauvegardé suit : un plantage ne réécrirait pas 08:00 → …
    etat = json.loads(moteur.chemin_en_cours.read_text(encoding="utf-8"))
    assert etat["ligne_ouverte"]["debut"] == "2026-11-17T09:00:00"


def test_inserer_avant_la_ligne_en_cours_ne_la_touche_pas(moteur, horloge):
    horloge.regler("10:00")
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("11:00")
    moteur.inserer(a("08:00"), a("09:00"), "Gamma Énergie", "Supervision serres")
    assert len(resume(moteur)) == 1
    assert moteur.ligne_ouverte.debut == a("10:00")


def test_inserer_remplace_et_verifier_le_signale(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("08:30")
    moteur.demarrer("Gamma Énergie", "Supervision serres")
    horloge.regler("09:00")
    moteur.pause()
    remplacees = moteur.verifier_insertion(a("08:00"), a("08:30"))
    assert [(l.client, l.debut) for l in remplacees] == [("Alpha Industrie", a("08:00"))]
    moteur.inserer(a("08:00"), a("08:30"), "Bêta Automatismes", "Firmware passerelle")
    assert [l[2] for l in resume(moteur)] == ["Bêta Automatismes", "Gamma Énergie"]


def test_inserer_nouveau_nom_ajoute_a_la_config(moteur, horloge):
    horloge.regler("10:00")
    moteur.inserer(a("09:00"), a("09:30"), "alpha industrie", "Nouveau projet", "essai")
    assert resume(moteur)[0][2:5] == ("Alpha Industrie", "Nouveau projet", "essai")
    assert "Nouveau projet" in moteur.config.projets("Alpha Industrie")


@pytest.mark.parametrize("debut, fin, message", [
    ("09:30", "09:30", "après"),
    ("09:30", "09:00", "après"),
    ("09:30", "10:30", "futur"),
])
def test_inserer_plage_refusee(moteur, horloge, debut, fin, message):
    horloge.regler("10:00")
    with pytest.raises(InsertionImpossible, match=message):
        moteur.inserer(a(debut), a(fin), "Alpha Industrie", "Armoire ligne 2")
    assert resume(moteur) == []


def test_inserer_refuse_si_lignes_en_attente(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    moteur.journal.verrouille = True
    horloge.regler("09:00")
    moteur.pause()
    with pytest.raises(InsertionImpossible, match="attendent"):
        moteur.inserer(a("08:00"), a("08:30"), "Gamma Énergie", "Supervision serres")
    assert len(moteur.en_attente) == 1


def test_inserer_refuse_si_lignes_illisibles(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("09:00")
    moteur.pause()
    with open(moteur.journal.chemin, "a", encoding="utf-8") as f:
        f.write("ligne abîmée à la main\n")
    avant = moteur.journal.chemin.read_bytes()
    with pytest.raises(InsertionImpossible, match="illisible"):
        moteur.inserer(a("08:00"), a("08:30"), "Gamma Énergie", "Supervision serres")
    assert moteur.journal.chemin.read_bytes() == avant


def test_inserer_csv_bloque_rien_ne_change(moteur, horloge, monkeypatch):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("09:00")
    ouverte = moteur.ligne_ouverte

    def bloque(lignes):
        raise JournalBloque("fichier verrouillé")
    monkeypatch.setattr(moteur.journal, "reecrire", bloque)
    with pytest.raises(JournalBloque):
        moteur.inserer(a("08:30"), a("08:45"), "Gamma Énergie", "Supervision serres")
    assert moteur.ligne_ouverte == ouverte


def test_lignes_du_jour_inclut_les_lignes_en_attente(moteur, horloge):
    moteur.demarrer("Alpha Industrie", "Armoire ligne 2")
    horloge.regler("09:00")
    moteur.demarrer("Gamma Énergie", "Supervision serres")
    moteur.journal.verrouille = True
    horloge.regler("10:00")
    moteur.pause()
    assert [l.client for l in moteur.lignes_du_jour(a("00:00").date())] == ["Alpha Industrie", "Gamma Énergie"]

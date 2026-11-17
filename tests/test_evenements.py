"""Journal des événements du poste et moments non pointés (CDC étape 8)."""

from datetime import date, datetime

import pytest

from pointeuse import settings
from pointeuse.evenements import (ARRET, DEMARRAGE, DEVERROUILLAGE, REVEIL, VEILLE, VERROUILLAGE, Evenement,
                                  JournalEvenements, plages_actives, soustraire, trous_du_jour)

JOUR = date(2026, 11, 17)


def a(heure: str, jour: int = 17) -> datetime:
    h, m = heure.split(":")
    return datetime(2026, 11, jour, int(h), int(m))


def ev(heure: str, nature: str, jour: int = 17) -> Evenement:
    return Evenement(a(heure, jour), nature)


def texte(plages) -> list[tuple[str, str]]:
    return [(d.strftime("%d %H:%M"), f.strftime("%d %H:%M")) for d, f in plages]


@pytest.fixture
def retention():
    return {"jours": 90}


@pytest.fixture
def journal(tmp_path, retention):
    return JournalEvenements(tmp_path / settings.NOM_FICHIER_EVENEMENTS, lambda: retention["jours"])


# ─── Fichier ─────────────────────────────────────────────────────────────────

def test_noter_puis_lire(journal):
    assert journal.noter(DEMARRAGE, a("08:00"))
    assert journal.noter(VERROUILLAGE, a("12:00"))
    contenu = journal.chemin.read_text(encoding=settings.ENCODAGE_CSV).splitlines()
    assert contenu == ["horodatage;evenement", "2026-11-17 08:00:00;demarrage", "2026-11-17 12:00:00;verrouillage"]
    assert journal.lire() == [ev("08:00", DEMARRAGE), ev("12:00", VERROUILLAGE)]
    assert journal.lire()[1].libelle == "verrouillage"


def test_lignes_abimees_ignorees_et_tri(journal):
    journal.chemin.write_text("horodatage;evenement\n2026-11-17 12:00:00;arret\nn'importe quoi\n"
                              "2026-13-45 99:00:00;veille\n2026-11-17 08:00:00;demarrage\n",
                              encoding=settings.ENCODAGE_CSV)
    assert journal.lire() == [ev("08:00", DEMARRAGE), ev("12:00", ARRET)]


def test_fichier_absent(journal):
    assert journal.lire() == []


def test_retention_zero_pas_de_journal(journal, retention):
    retention["jours"] = 0
    assert not journal.actif
    assert not journal.noter(DEMARRAGE, a("08:00"))
    assert not journal.chemin.exists()


def test_ecriture_impossible_perdue_sans_erreur(tmp_path):
    bloque = JournalEvenements(tmp_path / "dossier_fichier", lambda: 90)
    bloque.chemin.mkdir()                       # un dossier à la place du fichier
    assert not bloque.noter(DEMARRAGE, a("08:00"))


def test_purger_garde_la_retention(journal, retention):
    retention["jours"] = 10
    journal.noter(DEMARRAGE, datetime(2026, 11, 1, 8, 0))
    journal.noter(ARRET, datetime(2026, 11, 8, 18, 0))
    journal.noter(DEMARRAGE, a("08:00"))
    journal.purger(a("09:00"))
    assert [e.moment.day for e in journal.lire()] == [8, 17]
    assert not journal.chemin.with_name(journal.chemin.name + ".tmp").exists()


def test_du_jour(journal):
    journal.noter(ARRET, a("18:00", 16))
    journal.noter(DEMARRAGE, a("08:00"))
    assert journal.du_jour(JOUR) == [ev("08:00", DEMARRAGE)]


# ─── Plages actives ──────────────────────────────────────────────────────────

def test_plages_actives_journee_type():
    evenements = [ev("08:00", DEMARRAGE), ev("12:00", VERROUILLAGE), ev("13:30", DEVERROUILLAGE),
                  ev("15:00", VEILLE), ev("15:20", REVEIL), ev("18:00", ARRET)]
    assert texte(plages_actives(evenements, a("20:00"))) == [
        ("17 08:00", "17 12:00"), ("17 13:30", "17 15:00"), ("17 15:20", "17 18:00")]


def test_plage_ouverte_finit_maintenant():
    assert texte(plages_actives([ev("08:00", DEMARRAGE)], a("09:30"))) == [("17 08:00", "17 09:30")]


def test_plantage_plage_abandonnee():
    """Pas d'« arret » : on ne sait pas quand le PC s'est arrêté, la plage est abandonnée."""
    evenements = [ev("08:00", DEMARRAGE), ev("10:00", VERROUILLAGE), ev("10:30", DEVERROUILLAGE),
                  ev("14:00", DEMARRAGE)]
    assert texte(plages_actives(evenements, a("15:00"))) == [("17 08:00", "17 10:00"), ("17 14:00", "17 15:00")]


def test_verrouille_pendant_la_veille():
    evenements = [ev("08:00", DEMARRAGE), ev("12:00", VERROUILLAGE), ev("12:01", VEILLE),
                  ev("13:00", REVEIL), ev("13:05", DEVERROUILLAGE)]
    assert texte(plages_actives(evenements, a("14:00"))) == [("17 08:00", "17 12:00"), ("17 13:05", "17 14:00")]


def test_soustraire():
    plages = [(a("08:00"), a("12:00"))]
    occupees = [(a("09:00"), a("10:00")), (a("11:30"), a("13:00"))]
    assert texte(soustraire(plages, occupees)) == [("17 08:00", "17 09:00"), ("17 10:00", "17 11:30")]
    assert soustraire(plages, [(a("07:00"), a("13:00"))]) == []


# ─── Moments non pointés ─────────────────────────────────────────────────────

def test_trous_du_jour_seuil_et_minute():
    evenements = [ev("08:00", DEMARRAGE), ev("18:00", ARRET)]
    occupees = [(a("08:03"), a("12:00")), (datetime(2026, 11, 17, 13, 0, 40), a("18:00"))]
    # 08:00 → 08:03 : sous le seuil ; 12:00 → 13:00:40 rendu à la minute
    assert texte(trous_du_jour(evenements, occupees, JOUR, a("19:00"), 5)) == [("17 12:00", "17 13:00")]


def test_trou_depuis_la_veille_coupe_a_minuit():
    """Déverrouillé la veille au soir, jamais reverrouillé : le jour commence à minuit."""
    evenements = [ev("20:00", DEMARRAGE, 16)]
    assert texte(trous_du_jour(evenements, [(a("00:30"), a("09:00"))], JOUR, a("09:10"), 5)) == [
        ("17 00:00", "17 00:30"), ("17 09:00", "17 09:10")]


def test_trou_jusqu_a_minuit_un_jour_passe():
    evenements = [ev("22:00", DEMARRAGE, 16)]
    assert texte(trous_du_jour(evenements, [], date(2026, 11, 16), a("09:00"), 5)) == [("16 22:00", "17 00:00")]

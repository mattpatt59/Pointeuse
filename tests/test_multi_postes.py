"""Plusieurs PC (CDC multi_postes.md, ADR 005) : emplacements, réglage [donnees], sauvegarde
de data/, lecture des autres postes par le bilan."""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine

from pointeuse import settings
from pointeuse.bilan import DOSSIER_LECTEUR, lire_postes, preparer_bilan
from pointeuse.chemins import dossier_donnees, dossier_externe, dossier_sauvegarde
from pointeuse.config import Config, ConfigInvalide
from pointeuse.copie_externe import CopieExterne, Etat, copier_donnees

from test_bilan import relire_donnees

CSV = "date_in;date_out;client;projet;tache;description;duree_min\n"


def ecrire(chemin: Path, texte: str) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")
    return chemin


# ─── Emplacements ────────────────────────────────────────────────────────────

def test_dossiers(tmp_path):
    assert dossier_donnees(tmp_path) == tmp_path / settings.NOM_DOSSIER_DONNEES
    assert dossier_externe("data_extern", tmp_path) == tmp_path / "data_extern"
    absolu = tmp_path / "ailleurs"
    assert dossier_externe(str(absolu), tmp_path / "logiciel") == absolu
    assert dossier_sauvegarde("", tmp_path) is None
    assert dossier_sauvegarde("  ", tmp_path) is None
    assert dossier_sauvegarde("sauvegarde/bureau", tmp_path) == tmp_path / "sauvegarde" / "bureau"
    assert dossier_sauvegarde(str(absolu / "bureau"), tmp_path) == absolu / "bureau"


# ─── Réglage [donnees] ───────────────────────────────────────────────────────

def test_config_donnees_par_defaut(tmp_path):
    config = Config(tmp_path / "pointeuse_config.toml")
    assert config.reglage_donnees("dossier_de_sauvegarde") == ""
    assert config.reglage_donnees("dossier_externe") == settings.DONNEES_DEFAUT["dossier_externe"]


def test_config_donnees_lues(tmp_path):
    chemin = ecrire(tmp_path / "pointeuse_config.toml",
                    '[donnees]\ndossier_de_sauvegarde = "Z:/pointeuse/bureau"\n'
                    'dossier_externe = "Z:/pointeuse"\n')
    config = Config(chemin)
    assert config.reglage_donnees("dossier_de_sauvegarde") == "Z:/pointeuse/bureau"
    assert config.reglage_donnees("dossier_externe") == "Z:/pointeuse"


@pytest.mark.parametrize("section", ['[donnees]\nautre = "x"\n',
                                     '[donnees]\nposte = "bureau"\n',       # ancienne clé : refusée
                                     "[donnees]\ndossier_de_sauvegarde = 3\n"])
def test_config_donnees_invalides(tmp_path, section):
    with pytest.raises(ConfigInvalide):
        Config(ecrire(tmp_path / "pointeuse_config.toml", section))


@pytest.mark.parametrize("vide", ["", "  "])
def test_dossier_externe_vide_vaut_defaut(tmp_path, vide):
    """Drive / NAS optionnel : réglage vide = data_extern/ du logiciel."""
    config = Config(ecrire(tmp_path / "pointeuse_config.toml", f'[donnees]\ndossier_externe = "{vide}"\n'))
    assert dossier_externe(config.reglage_donnees("dossier_externe"), tmp_path) == tmp_path / "data_extern"


# ─── Copie ───────────────────────────────────────────────────────────────────

@pytest.fixture
def donnees(tmp_path):
    dossier = tmp_path / "logiciel" / "data"
    ecrire(dossier / settings.NOM_FICHIER_CSV, CSV + "2026-11-17 08:00;2026-11-17 09:00;c;p;;;60\n")
    ecrire(dossier / settings.NOM_FICHIER_CONFIG, "[reglages]\n")
    ecrire(dossier / settings.NOM_FICHIER_EN_COURS, "{}")   # pas copié
    return dossier


def test_copie_faite(donnees, tmp_path):
    cible = tmp_path / "sauvegarde" / "bureau"
    assert copier_donnees(donnees, cible, creer_parent=True).etat == Etat.FAITE
    assert (cible / settings.NOM_FICHIER_CSV).read_bytes() == (donnees / settings.NOM_FICHIER_CSV).read_bytes()
    assert (cible / settings.NOM_FICHIER_CONFIG).exists()
    assert not (cible / settings.NOM_FICHIER_SUIVI).exists()      # absent en local : rien
    assert not (cible / settings.NOM_FICHIER_EN_COURS).exists()   # hors FICHIERS_COPIES
    assert not list(cible.glob("*" + settings.SUFFIXE_COPIE_TEMPORAIRE))


def test_copie_suspendue_si_sauvegarde_plus_grande(donnees, tmp_path):
    cible = tmp_path / "sauvegarde" / "bureau"
    sauvegarde = CSV + "ligne\n" * 50
    ecrire(cible / settings.NOM_FICHIER_CSV, sauvegarde)
    assert copier_donnees(donnees, cible, creer_parent=True).etat == Etat.SUSPENDUE
    assert (cible / settings.NOM_FICHIER_CSV).read_text(encoding="utf-8") == sauvegarde
    assert not (cible / settings.NOM_FICHIER_CONFIG).exists()   # rien n'est copié


def test_copie_suspendue_si_data_vide(tmp_path):
    cible = ecrire(tmp_path / "sauvegarde" / "bureau" / settings.NOM_FICHIER_CSV, CSV).parent
    vide = tmp_path / "data"
    vide.mkdir()
    assert copier_donnees(vide, cible, creer_parent=True).etat == Etat.SUSPENDUE


def test_copie_dossier_absolu_absent(donnees, tmp_path):
    """Lecteur réseau absent : échec, et surtout pas de dossier créé sur le disque local."""
    lecteur = tmp_path / "Z"
    resultat = copier_donnees(donnees, lecteur / "bureau", creer_parent=False)
    assert resultat.etat == Etat.ECHEC
    assert not lecteur.exists()


class Horloge:
    def __init__(self):
        self.moment = datetime(2026, 11, 20, 10, 42)

    def __call__(self):
        return self.moment


def creer_copie(donnees, sauvegarde, externe="data_extern"):
    reglages = {"dossier_de_sauvegarde": sauvegarde, "dossier_externe": externe}
    return CopieExterne(donnees, donnees.parent, lambda nom: reglages[nom], Horloge())


@pytest.mark.parametrize("vide", ["", "  "])
def test_sauvegarde_desactivee(donnees, vide):
    copie = creer_copie(donnees, vide)
    assert copie.essayer() is False
    assert copie.dernier.etat == Etat.DESACTIVEE
    assert copie.poste() == ""
    assert copie.prochain_essai_min is None
    assert copie.texte_info_bulle() == ""
    assert sorted(p.name for p in donnees.parent.iterdir()) == ["data"]   # rien de créé


def test_poste_est_le_nom_du_dossier(donnees, tmp_path):
    assert creer_copie(donnees, "sauvegarde/bureau").poste() == "bureau"
    assert creer_copie(donnees, str(tmp_path / "Z" / "PC atelier")).poste() == "PC atelier"


@pytest.mark.parametrize("cible", ["data", "data/sauvegarde"])
def test_sauvegarde_dans_data_refusee(donnees, cible):
    copie = creer_copie(donnees, cible)
    assert copie.essayer() is True
    assert copie.dernier.etat == Etat.DOSSIER_INVALIDE
    assert copie.prochain_essai_min is None   # pas de réessai : il faut corriger la config
    assert "dans data/" in copie.message()
    assert copie.essayer() is False           # même problème : pas de seconde notification
    assert "à corriger" in copie.texte_info_bulle()
    assert not (donnees / "sauvegarde").exists()


def test_sauvegarde_relative_creee_dans_le_logiciel(donnees):
    copie = creer_copie(donnees, "data_extern/bureau")
    assert copie.a_change()
    assert copie.essayer() is False
    assert copie.dernier.etat == Etat.FAITE
    assert (donnees.parent / "data_extern" / "bureau" / settings.NOM_FICHIER_CSV).exists()
    assert not copie.a_change()
    ecrire(donnees / settings.NOM_FICHIER_CSV, CSV + "x\n" * 10)   # nouvel enregistrement
    assert copie.a_change()


def test_sauvegarde_delai_double_et_repart(donnees, tmp_path):
    copie = creer_copie(donnees, str(tmp_path / "Z" / "bureau"))
    delais = []
    signalements = []
    for _ in range(9):
        signalements.append(copie.essayer())
        delais.append(copie.prochain_essai_min)
    assert delais == [1, 2, 4, 8, 16, 32, 60, 60, 60]
    assert signalements == [True] + [False] * 8   # une notification par panne, pas par essai
    assert "Nouvel essai dans 60 min" in copie.message()
    assert copie.texte_info_bulle() == "Sauvegarde en attente depuis 10:42"

    (tmp_path / "Z").mkdir()                       # le lecteur revient
    assert copie.essayer() is False
    assert copie.dernier.etat == Etat.FAITE
    assert (tmp_path / "Z" / "bureau" / settings.NOM_FICHIER_CSV).exists()
    assert copie.prochain_essai_min is None
    assert copie.delai_min == settings.COPIE_DELAI_INITIAL_MIN
    assert copie.texte_info_bulle() == ""
    shutil.rmtree(tmp_path / "Z")                  # nouvelle panne
    assert copie.essayer() is True                 # nouvelle panne : nouvelle notification
    assert copie.prochain_essai_min == 1


def test_dossier_externe_independant_de_la_sauvegarde(donnees, tmp_path):
    """Le bilan lit dossier_externe, même sans sauvegarde ; la sauvegarde n'écrit pas dedans."""
    copie = creer_copie(donnees, "", "")
    assert copie.dossier_externe() == donnees.parent / "data_extern"
    copie = creer_copie(donnees, "", str(tmp_path / "Z"))
    assert copie.dossier_externe() == tmp_path / "Z"


# ─── Bilan : autres postes ───────────────────────────────────────────────────

def test_lire_postes(tmp_path):
    externe = tmp_path / "externe"
    ecrire(externe / "Bureau" / settings.NOM_FICHIER_CSV, CSV)               # ce poste (casse ignorée)
    ecrire(externe / "atelier" / settings.NOM_FICHIER_CSV, CSV + "a\n")
    ecrire(externe / "atelier" / settings.NOM_FICHIER_SUIVI, "{}\n")
    ecrire(externe / "portable" / settings.NOM_FICHIER_SUIVI, "{}\n")       # suivi seul
    (externe / "vide").mkdir()                                              # ignoré
    ecrire(externe / "orphelin.csv", CSV)                                   # fichier : ignoré

    postes, note = lire_postes(externe, "bureau")
    assert note == ""
    assert [p["poste"] for p in postes] == ["atelier", "portable"]
    assert postes[0]["csv"] == {"nom": settings.NOM_FICHIER_CSV, "texte": CSV + "a\n"}
    assert postes[0]["suivi"]["texte"] == "{}\n"
    assert postes[1]["csv"] is None


def test_lire_postes_dossier_absent(tmp_path):
    postes, note = lire_postes(tmp_path / "Z", "bureau")
    assert postes == []
    assert "introuvable" in note
    assert lire_postes(None, "bureau") == ([], "")


def test_preparer_bilan_avec_postes(tmp_path):
    data = tmp_path / "data"
    csv = ecrire(data / settings.NOM_FICHIER_CSV, CSV)
    externe = tmp_path / "externe"
    ecrire(externe / "atelier" / settings.NOM_FICHIER_CSV, CSV + "b\n")
    preparer_bilan(csv, data, None, externe, "bureau")
    donnees = relire_donnees((data / settings.NOM_DOSSIER_BILAN / settings.NOM_FICHIER_DONNEES_BILAN)
                             .read_text(encoding="utf-8"))
    assert donnees["version"] == 3
    assert [p["poste"] for p in donnees["postes"]] == ["atelier"]
    assert donnees["note"] == ""


# ─── Lecteur JS : entrées construites depuis les données transmises ──────────

def extraire_fonction(source: str, nom: str) -> str:
    debut = source.index(f"function {nom}(")
    fin = re.compile(r"^}\s*$", re.M).search(source, debut).end()
    return source[debut:fin]


def test_entrees_donnees_locales_js():
    app = QCoreApplication.instance() or QCoreApplication([])   # noqa: F841 — requis par QJSEngine
    moteur = QJSEngine()
    suivi_js = (DOSSIER_LECTEUR / "suivi.js").read_text(encoding="utf-8")
    page_js = (DOSSIER_LECTEUR / "pointeuse.js").read_text(encoding="utf-8")
    donnees = {"version": 3, "nom": "pointeuse.csv", "texte": "L", "suivi": {"nom": "s.jsonl", "texte": "S"},
               "postes": [{"poste": "atelier", "csv": {"nom": "pointeuse.csv", "texte": "A"}, "suivi": None},
                          {"poste": "portable", "csv": None, "suivi": {"nom": "s.jsonl", "texte": "P"}}],
               "note": ""}
    source = (suivi_js + "\n" + extraire_fonction(page_js, "entreesDonneesLocales")
              + f"\nJSON.stringify([SUIVI.posteLocal, entreesDonneesLocales({json.dumps(donnees)})])")
    resultat = moteur.evaluate(source)
    assert not resultat.isError(), resultat.toString()
    poste_local, entrees = json.loads(resultat.toString())
    assert poste_local == settings.POSTE_LOCAL
    assert [(e["poste"], e["texte"]) for e in entrees["csv"]] == [("local", "L"), ("atelier", "A")]
    assert [(e["poste"], e["texte"]) for e in entrees["suivi"]] == [("local", "S"), ("portable", "P")]


# ─── Câblage dans l'application ──────────────────────────────────────────────

def test_application_copie_et_info_bulle(tmp_path, monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from pointeuse.application import Application
    from pointeuse.journal import Journal
    from pointeuse.moteur import Moteur

    qapp = QApplication.instance() or QApplication([])
    logiciel = tmp_path / "logiciel"
    data = logiciel / "data"
    ecrire(data / settings.NOM_FICHIER_CONFIG,
           f'[donnees]\ndossier_de_sauvegarde = "{(tmp_path / "Z" / "bureau").as_posix()}"\n')
    ecrire(data / settings.NOM_FICHIER_CSV, CSV)
    config = Config(data / settings.NOM_FICHIER_CONFIG)
    moteur = Moteur(config, Journal(data / settings.NOM_FICHIER_CSV), data / settings.NOM_FICHIER_EN_COURS)
    copie = CopieExterne(data, logiciel, config.reglage_donnees, Horloge())
    application = Application(qapp, moteur, copie)
    messages = []
    monkeypatch.setattr(application.icone, "showMessage", lambda *args: messages.append(args[1]))

    application.mettre_a_jour()                      # Z absent : échec, une notification, réessai programmé
    assert len(messages) == 1
    assert application.minuteur_copie.isActive()
    assert application.minuteur_copie.interval() == 60 * 1000
    assert "Sauvegarde en attente depuis 10:42" in application.icone.toolTip()
    application.mettre_a_jour()                      # rien d'enregistré : pas de nouvel essai
    assert copie.delai_min == 2

    (tmp_path / "Z").mkdir()
    application.essayer_copie()                      # le minuteur tombe
    assert (tmp_path / "Z" / "bureau" / settings.NOM_FICHIER_CSV).exists()
    assert not application.minuteur_copie.isActive()
    application.mettre_a_jour()
    assert "Sauvegarde" not in application.icone.toolTip()
    assert len(messages) == 1
    application.panneau.deleteLater()
    application.suivi.deleteLater()

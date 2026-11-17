"""Tests du fichier de configuration (CDC étape 1)."""

import os
import shutil
from pathlib import Path

import pytest
import tomllib

from pointeuse.config import Config, ConfigInvalide, NomReserve, Raccourci

EXEMPLE = Path(__file__).resolve().parents[1] / "docs" / "exemples" / "pointeuse_config.toml"


@pytest.fixture
def chemin(tmp_path):
    """Copie de l'exemple de la doc (3 clients) dans un dossier temporaire."""
    destination = tmp_path / "pointeuse_config.toml"
    shutil.copy(EXEMPLE, destination)
    return destination


def modifier_a_la_main(chemin: Path, texte: str) -> None:
    """Écrit le fichier comme un utilisateur, en forçant une date de modif différente."""
    chemin.write_text(texte, encoding="utf-8")
    etat = chemin.stat()
    os.utime(chemin, ns=(etat.st_atime_ns, etat.st_mtime_ns + 1_000_000_000))


# ─── Création et lecture ─────────────────────────────────────────────────────

def test_cree_fichier_par_defaut(tmp_path):
    chemin = tmp_path / "sous_dossier" / "pointeuse_config.toml"
    config = Config(chemin)
    assert chemin.exists()
    assert config.clients() == ["Perso", "Client A"]
    assert config.projets("Client A") == ["26-01-Projet"]
    assert config.reglage("sauvegarde_min") == 5


def test_lecture_exemple_de_la_doc(chemin):
    config = Config(chemin)
    assert config.clients() == ["Alpha Industrie", "Bêta Automatismes", "Gamma Énergie"]
    assert config.projets("Bêta Automatismes") == ["Carte capteur v2", "Firmware passerelle"]
    assert config.taches_projet("Bêta Automatismes", "Carte capteur v2") == ["schéma", "routage", "prototype"]
    assert config.taches_communes() == ["réunion", "administratif", "support téléphone"]


def test_projet_masque_par_defaut(chemin):
    config = Config(chemin)
    assert config.projets("Alpha Industrie") == ["Armoire ligne 2"]
    assert config.projets("Alpha Industrie", inclure_masques=True) == ["Armoire ligne 2", "Rétrofit presse"]


def test_noms_compares_sans_casse_ni_espaces(chemin):
    config = Config(chemin)
    assert config.projets("  alpha industrie ") == ["Armoire ligne 2"]


def test_client_inconnu(chemin):
    config = Config(chemin)
    assert config.projets("inconnu") == []
    assert config.taches_projet("inconnu", "x") == []


def test_reglage_absent_prend_la_valeur_par_defaut(tmp_path):
    chemin = tmp_path / "c.toml"
    chemin.write_text('[clients.a]\n', encoding="utf-8")
    assert Config(chemin).reglage("detection_absence_min") == 2


def test_fichier_avec_bom_windows(tmp_path):
    chemin = tmp_path / "c.toml"
    chemin.write_text('[clients.a]\n', encoding="utf-8-sig")
    assert Config(chemin).clients() == ["a"]
    assert "visible" not in chemin.read_text(encoding="utf-8")


def test_fichier_vide_accepte(tmp_path):
    chemin = tmp_path / "c.toml"
    chemin.write_text("", encoding="utf-8")
    config = Config(chemin)
    assert config.clients() == []
    assert config.taches_communes() == []


# ─── Erreurs ─────────────────────────────────────────────────────────────────

def test_erreur_de_syntaxe(tmp_path):
    chemin = tmp_path / "c.toml"
    chemin.write_text('[clients."a]\n', encoding="utf-8")
    with pytest.raises(ConfigInvalide, match="syntaxe"):
        Config(chemin)


@pytest.mark.parametrize("texte, message", [
    ('[[clients]]\nnom = "a"\n', "Nom du client"),             # ancien format
    ('clients = ["a"]\n', "Nom du client"),
    ('[clients]\na = 1\n', "à déclarer"),
    ('[clients.Pause]\n', "réservé"),
    ('[clients.a]\nvisible = "oui"\n', "visible"),
    ('[clients.a]\nvisible = { taches = [] }\n', "nom de projet"),
    ('[clients.a]\np = ["cdc"]\n', "taches = "),
    ('[clients.a]\np = { taches = "cdc" }\n', "liste"),
    ('[clients.a]\np = { visible = "non" }\n', "visible"),
    ('[clients.a]\np = { actif = false }\n', "clé inconnue « actif »"),        # ancien nom
    ('[clients.a]\np = { tache = ["cdc"] }\n', "clé inconnue « tache »"),
    ('[reglages]\nsauvegarde_min = 0\n', "positif"),
    ('[taches_communes]\nliste = [1, 2]\n', "liste"),
    ('[reglages]\nafficher_journal = 1\n', "true ou false"),
    ('[reglages]\nretention_journal_jours = -1\n', "0 ou plus"),
    ('[reglages]\nabsence_longue_h = true\n', "positif"),
])
def test_erreur_de_structure(tmp_path, texte, message):
    chemin = tmp_path / "c.toml"
    chemin.write_text(texte, encoding="utf-8")
    with pytest.raises(ConfigInvalide, match=message):
        Config(chemin)


# ─── Ajout d'entrées ─────────────────────────────────────────────────────────

def test_ajout_client_projet_tache(chemin):
    config = Config(chemin)
    assert config.ajouter("Delta Services", "Audit", "visite") == ("Delta Services", "Audit", "visite")
    relu = Config(chemin)
    assert "Delta Services" in relu.clients()
    assert relu.projets("Delta Services") == ["Audit"]
    assert relu.taches_projet("Delta Services", "Audit") == ["visite"]


def test_ajout_conserve_les_commentaires(chemin):
    Config(chemin).ajouter("Delta Services", "Audit")
    texte = chemin.read_text(encoding="utf-8")
    assert "# projet fini" in texte
    assert "# Tâches proposées dans tous les projets" in texte
    tomllib.loads(texte)  # reste un TOML valide


def test_ajout_garde_les_commentaires_au_dessus_de_leur_section(chemin):
    config = Config(chemin)
    config.ajouter("Delta Services", "Audit")
    config.ajouter("Bêta Automatismes", "Banc test")
    lignes = chemin.read_text(encoding="utf-8").splitlines()

    commentaire = lignes.index("# Tâches proposées dans tous les projets (facultatif, peut rester vide).")
    assert lignes[commentaire + 1] == "[taches_communes]"
    delta = lignes.index('[clients."Delta Services"]')
    assert lignes[delta - 1] == ""                       # ligne vide avant le nouveau client
    assert lignes[delta + 1] == '"Audit" = { taches = [] }'
    assert delta < commentaire

    # Le nouveau projet de Bêta est rangé sous son dernier projet, avant la ligne vide.
    banc = lignes.index('"Banc test" = { taches = [] }')
    assert lignes[banc - 1].startswith('"Firmware passerelle"')
    assert lignes[banc + 1] == ""
    assert lignes[banc + 2] == '[clients."Gamma Énergie"]'


def test_ajout_existant_ne_modifie_pas_le_fichier(chemin):
    avant = chemin.read_text(encoding="utf-8")
    resultat = Config(chemin).ajouter("bêta automatismes", "carte capteur V2", "ROUTAGE")
    assert resultat == ("Bêta Automatismes", "Carte capteur v2", "routage")
    assert chemin.read_text(encoding="utf-8") == avant


def test_tache_commune_non_recopiee_dans_le_projet(chemin):
    config = Config(chemin)
    assert config.ajouter("Gamma Énergie", "Supervision serres", "Réunion")[2] == "réunion"
    assert "réunion" not in config.taches_projet("Gamma Énergie", "Supervision serres")


def test_nouvelle_tache_ajoutee_au_projet(chemin):
    config = Config(chemin)
    config.ajouter("Gamma Énergie", "Supervision serres", "recette")
    assert config.taches_projet("Gamma Énergie", "Supervision serres")[-1] == "recette"
    assert ('"Supervision serres" = { taches = ["interface web", "base de données", "déploiement", "recette"] }'
            in chemin.read_text(encoding="utf-8"))


def test_projet_masque_utilisable_sans_reapparaitre(chemin):
    avant = chemin.read_text(encoding="utf-8")
    config = Config(chemin)
    assert config.ajouter("alpha industrie", "rétrofit PRESSE", "doc") == ("Alpha Industrie", "Rétrofit presse", "doc")
    assert chemin.read_text(encoding="utf-8") == avant   # rien à écrire : tâche connue, projet laissé masqué
    assert "Rétrofit presse" not in Config(chemin).projets("Alpha Industrie")


def test_nouvelle_tache_sur_projet_masque(chemin):
    config = Config(chemin)
    config.ajouter("Alpha Industrie", "Rétrofit presse", "dépannage")
    assert "Rétrofit presse" not in Config(chemin).projets("Alpha Industrie")
    # Une seule ligne, visible = false et commentaire de fin de ligne conservés.
    assert ('"Rétrofit presse" = { taches = ["étude", "mise en service", "doc", "dépannage"], visible = false }'
            '   # projet fini' in chemin.read_text(encoding="utf-8"))


def test_client_masque_utilisable_sans_reapparaitre(tmp_path):
    chemin = tmp_path / "c.toml"
    chemin.write_text('[clients.a]\nvisible = false   # client fini\np = { taches = [] }\n', encoding="utf-8")
    config = Config(chemin)
    assert config.clients() == []
    assert config.clients(inclure_masques=True) == ["a"]
    assert config.ajouter("A", "p", "t")[:2] == ("a", "p")
    assert Config(chemin).clients() == []
    assert "visible = false   # client fini" in chemin.read_text(encoding="utf-8")


def test_projet_ecrit_en_section(tmp_path):
    """Écriture TOML équivalente acceptée : [clients."a"."p"] au lieu d'une ligne."""
    chemin = tmp_path / "c.toml"
    chemin.write_text('[clients.a.p]\ntaches = ["x"]\nvisible = false\n', encoding="utf-8")
    config = Config(chemin)
    assert config.projets("a", inclure_masques=True) == ["p"]
    config.ajouter("a", "p", "y")
    assert Config(chemin).projets("a") == []
    assert Config(chemin).taches_projet("a", "p") == ["x", "y"]


def test_tache_vide_ignoree(chemin):
    assert Config(chemin).ajouter("Alpha Industrie", "Armoire ligne 2", "  ")[2] is None


def test_ajout_dans_fichier_vide(tmp_path):
    chemin = tmp_path / "c.toml"
    chemin.write_text("", encoding="utf-8")
    Config(chemin).ajouter("a", "p", "t")
    relu = Config(chemin)
    assert relu.clients() == ["a"]
    assert relu.taches_projet("a", "p") == ["t"]


def test_client_pause_refuse(chemin):
    with pytest.raises(NomReserve):
        Config(chemin).ajouter(" pause ", "x")


def test_projet_nomme_visible_refuse(chemin):
    with pytest.raises(NomReserve):
        Config(chemin).ajouter("Alpha Industrie", "Visible")


def test_client_ou_projet_vide_refuse(chemin):
    with pytest.raises(ValueError):
        Config(chemin).ajouter("Alpha Industrie", "  ")


# ─── Relecture à chaud ───────────────────────────────────────────────────────

def test_relecture_apres_modification_manuelle(chemin):
    config = Config(chemin)
    assert config.recharger_si_modifie() is False
    modifier_a_la_main(chemin, '[clients.Nouveau]\n')
    assert config.recharger_si_modifie() is True
    assert config.clients() == ["Nouveau"]


def test_propre_ecriture_ne_declenche_pas_de_relecture(chemin):
    config = Config(chemin)
    config.ajouter("Delta Services", "Audit")
    assert config.recharger_si_modifie() is False


def test_modification_invalide_garde_la_derniere_config(chemin):
    config = Config(chemin)
    modifier_a_la_main(chemin, '[clients.\n')
    with pytest.raises(ConfigInvalide):
        config.recharger_si_modifie()
    assert "Alpha Industrie" in config.clients()
    # L'erreur n'est signalée qu'une fois, pas à chaque vérification.
    assert config.recharger_si_modifie() is False


def test_ajout_prend_en_compte_une_modification_manuelle(chemin):
    config = Config(chemin)
    modifier_a_la_main(chemin, '[clients.Manuel]\n')
    config.ajouter("Delta Services", "Audit")
    assert Config(chemin).clients() == ["Manuel", "Delta Services"]


def test_fichier_supprime_est_reecrit(chemin):
    config = Config(chemin)
    chemin.unlink()
    config.recharger_si_modifie()
    assert Config(chemin).clients() == config.clients()


# ─── Réglage modifié par l'appli (case « Masquer le journal ») ───────────────

def test_retention_zero_acceptee(tmp_path):
    chemin = tmp_path / "c.toml"
    chemin.write_text("[reglages]\nretention_journal_jours = 0\n", encoding="utf-8")
    assert Config(chemin).reglage("retention_journal_jours") == 0


def test_modifier_reglage_garde_les_commentaires(chemin):
    config = Config(chemin)
    assert config.reglage("afficher_journal") is True
    config.modifier_reglage("afficher_journal", False)
    texte = chemin.read_text(encoding="utf-8")
    assert "afficher_journal = false" in texte
    assert "# vue Journée : événements et moments non pointés" in texte
    assert tomllib.loads(texte)["reglages"]["afficher_journal"] is False
    assert Config(chemin).reglage("afficher_journal") is False


def test_modifier_reglage_absent_ajoute_dans_la_section(tmp_path):
    chemin = tmp_path / "c.toml"
    chemin.write_text("[reglages]\nsauvegarde_min = 1\n\n[clients.a]\n", encoding="utf-8")
    Config(chemin).modifier_reglage("afficher_journal", False)
    donnees = tomllib.loads(chemin.read_text(encoding="utf-8"))
    assert donnees["reglages"] == {"sauvegarde_min": 1, "afficher_journal": False}
    assert "a" in donnees["clients"]


def test_modifier_reglage_sans_section(tmp_path):
    chemin = tmp_path / "c.toml"
    chemin.write_text("[clients.a]\n", encoding="utf-8")
    Config(chemin).modifier_reglage("afficher_journal", False)
    assert tomllib.loads(chemin.read_text(encoding="utf-8"))["reglages"] == {"afficher_journal": False}


def test_modifier_reglage_inconnu(chemin):
    with pytest.raises(KeyError):
        Config(chemin).modifier_reglage("inconnu", 1)


def test_modifier_reglage_identique_ne_reecrit_pas(chemin):
    config = Config(chemin)
    avant = chemin.stat().st_mtime_ns
    config.modifier_reglage("afficher_journal", True)
    assert chemin.stat().st_mtime_ns == avant


# ─── Boutons rapides [[raccourcis]] (CDC onglet_pointer.md) ──────────────────

RACCOURCIS = '''
[[raccourcis]]
client = "Alpha Industrie"
projet = "Armoire ligne 2"

[[raccourcis]]
nom = "Bêta"
client = "Bêta Automatismes"

[[raccourcis]]
client = "Gamma Énergie"
projet = "Supervision serres"
tache = "déploiement"
description = "sur site"
'''


def test_raccourcis_lus_dans_l_ordre(chemin):
    modifier_a_la_main(chemin, chemin.read_text(encoding="utf-8") + RACCOURCIS)
    raccourcis = Config(chemin).raccourcis()
    assert [r.libelle for r in raccourcis] == ["Alpha Industrie – Armoire ligne 2", "Bêta",
                                               "Gamma Énergie – Supervision serres – déploiement"]
    assert raccourcis[1].projet == ""
    assert raccourcis[2].description == "sur site"


def test_sans_raccourcis(chemin):
    assert Config(chemin).raccourcis() == []


def test_raccourcis_du_fichier_par_defaut(tmp_path):
    raccourcis = Config(tmp_path / "pointeuse_config.toml").raccourcis()
    assert raccourcis == [
        Raccourci(nom="Administratif", client="Perso", projet="administratif"),
        Raccourci(nom="26-01_routage", client="Client A", projet="26-01-Projet", tache="Routage"),
    ]


@pytest.mark.parametrize("texte, message", [
    ('[raccourcis]\nclient = "A"\n', "deux crochets"),
    ('[[raccourcis]]\nprojet = "P"\n', "client obligatoire"),
    ('[[raccourcis]]\nclient = "PAUSE"\n', "réservé"),
    ('[[raccourcis]]\nclient = "A"\ntache = "t"\n', "une tâche demande un projet"),
    ('[[raccourcis]]\nclient = "A"\ncouleur = "rouge"\n', "clé inconnue « couleur »"),
    ('[[raccourcis]]\nclient = "A"\nprojet = 3\n', "projet doit être un texte"),
    ('[[raccourcis]]\nclient = "A"\nprojet = "visible"\n', "nom de projet"),
    ('[[raccourcis]]\nclient = "A"\n' * 9, r"8 \[\[raccourcis\]\] au maximum"),
])
def test_raccourcis_invalides(tmp_path, texte, message):
    chemin = tmp_path / "pointeuse_config.toml"
    chemin.write_text(texte, encoding="utf-8")
    with pytest.raises(ConfigInvalide, match=message):
        Config(chemin)


def test_ajouter_client_sans_projet(chemin):
    config = Config(chemin)
    assert config.ajouter("Delta Services", "", projet_obligatoire=False) == ("Delta Services", "", None)
    assert "Delta Services" in config.clients()
    assert config.projets("Delta Services") == []
    assert config.ajouter("alpha industrie", " ", projet_obligatoire=False) == ("Alpha Industrie", "", None)
    with pytest.raises(ValueError, match="client est obligatoire"):
        config.ajouter(" ", "", projet_obligatoire=False)

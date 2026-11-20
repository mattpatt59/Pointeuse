"""Page « Suivi » du bilan (CDC suivi_projets.md, étape 6) : lecture du pointeuse_suivi.jsonl et
construction des blocs par projet dans lecteur/suivi.js, exécuté par le moteur JavaScript de Qt.

Le jeu d'exemple est le même que pour suivi.py (tests/test_suivi.py) : les deux lectures
doivent rester identiques (ADR 004)."""

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine

from pointeuse import settings
from pointeuse.bilan import DOSSIER_LECTEUR

EXEMPLE = Path(__file__).parent / "donnees" / "suivi_exemple.jsonl"

AIDES = r"""
function D(texte) {          // « 2026-11-14 09:30 » ou « 2026-11-14 »
    const [jour, heure] = texte.split(' ');
    const [a, m, j] = jour.split('-').map(Number);
    let hh = 0;
    let mm = 0;
    if (heure) [hh, mm] = heure.split(':').map(Number);
    return new Date(a, m - 1, j, hh, mm);
}
function P(debut, fin, client, projet) { return { debut: D(debut), fin: D(fin), client, projet }; }
function N(horodatage, periode, projet, statut, priorite, texte, poste) {
    return { horodatage: D(horodatage), periode, client: 'Alpha Industrie', projet, statut,
             priorite: priorite || 0, texte: texte || '', poste: poste || '' };
}
function resumeBilan(blocs) {
    return JSON.stringify(blocs.map(b => ({
        projet: b.client + ' / ' + b.projet, statut: b.statut, priorite: b.priorite, minutes: b.minutes,
        lignes: b.lignes.map(l => {
            let tete = suiviCleJour(l.jour || l.debut);
            if (l.type === 'semaine') tete = l.periode;
            return tete + ' ' + l.minutes + ' ' + l.notes.map(n => n.texte + (n.poste ? '@' + n.poste : '')).join('|');
        }),
    })));
}
"""


@pytest.fixture(scope="module")
def moteur_js():
    app = QCoreApplication.instance() or QCoreApplication([])   # noqa: F841 — requis par QJSEngine
    moteur = QJSEngine()
    for source in ((DOSSIER_LECTEUR / "suivi.js").read_text(encoding="utf-8"), AIDES):
        resultat = moteur.evaluate(source)
        assert not resultat.isError(), resultat.toString()
    return moteur


def evaluer(moteur_js, expression: str):
    resultat = moteur_js.evaluate(expression)
    assert not resultat.isError(), resultat.toString()
    return json.loads(resultat.toString())


def test_constantes_alignees(moteur_js):
    # Un « const » de premier niveau n'est visible que dans le même evaluate() (dans la page, si).
    source = (DOSSIER_LECTEUR / "suivi.js").read_text(encoding="utf-8")
    assert evaluer(moteur_js, source + "\nJSON.stringify(SUIVI.statuts)") == settings.STATUTS_SUIVI
    assert evaluer(moteur_js, source + "\nJSON.stringify([SUIVI.versionLigne, SUIVI.prioriteMin, SUIVI.prioriteMax, "
                              "SUIVI.prioriteDefaut, SUIVI.termine, SUIVI.termineAConfirmer, "
                              "SUIVI.libelleTermineAConfirmer])") == [
        settings.VERSION_LIGNE_SUIVI, settings.PRIORITE_MIN, settings.PRIORITE_MAX, settings.PRIORITE_DEFAUT,
        settings.STATUT_TERMINE, settings.STATUT_TERMINE_A_CONFIRMER, settings.LIBELLE_TERMINE_A_CONFIRMER]


def test_lecture_exemple_identique_a_python(moteur_js):
    texte = EXEMPLE.read_text(encoding="utf-8")
    lu = evaluer(moteur_js, f"(() => {{ const r = suiviLire({json.dumps(texte)}, 'bureau'); return JSON.stringify("
                            "{ notes: r.notes.map(n => [n.texte, n.poste, n.priorite, n.periode]), "
                            "avertissements: r.avertissements }); })()")
    # Mêmes attentes que tests/test_suivi.py::test_lecture_exemple.
    assert [n[0] for n in lu["notes"]] == [
        "",
        "Livré.",
        "Version de 9 h",
        "Câblage OK.\nDéfaut sur la sortie 3, à reprendre.",
        'Attente retour client sur le schéma ; "urgent".',
    ]
    assert all(n[1] == "bureau" for n in lu["notes"])
    assert lu["avertissements"] == [
        "ligne 4 : JSON invalide, ignorée",
        "ligne 5 : version de format inconnue : 2, ignorée",
        "ligne 6 : statut inconnu : 'fini', ignorée",
        "ligne 8 : priorité 150 ramenée à 99",
    ]
    assert lu["notes"][1][2:] == [99, "2026-W46"]


@pytest.mark.parametrize("ligne, raison", [
    ('[1]', "ce n'est pas un objet JSON"),
    ('{"v": 1, "texte": "\ufffd"}', "encodage illisible (UTF-8 attendu)"),   # octet illisible remplacé par bilan.py
    ('{"v": null}', "version de format inconnue : None"),
    ('{"v": 1, "horodatage": 5}', "champ « horodatage » manquant ou non textuel"),
    ('{"v":1,"horodatage":"2026-11-14 09:00:00","periode":"2026-11-14","client":"A","projet":"B",'
     '"statut":"en_cours","priorite":true,"texte":""}', "champ « priorite » manquant ou non entier"),
    ('{"v":1,"horodatage":"2026-11-14 09:00:00","periode":"2026-11-14","client":" ","projet":"B",'
     '"statut":"en_cours","priorite":0,"texte":""}', "client ou projet vide"),
    ('{"v":1,"horodatage":"14/11/2026","periode":"2026-11-14","client":"A","projet":"B",'
     '"statut":"en_cours","priorite":0,"texte":""}', "horodatage illisible : '14/11/2026'"),
    ('{"v":1,"horodatage":"2026-11-14 09:00:00","periode":"2026-02-30","client":"A","projet":"B",'
     '"statut":"en_cours","priorite":0,"texte":""}', "période mal formée : '2026-02-30'"),
    ('{"v":1,"horodatage":"2026-11-14 09:00:00","periode":"2025-W53","client":"A","projet":"B",'
     '"statut":"en_cours","priorite":0,"texte":""}', "période mal formée : '2025-W53'"),
])
def test_lignes_refusees(moteur_js, ligne, raison):
    lu = evaluer(moteur_js, f"JSON.stringify(suiviLire({json.dumps(ligne)}, '').avertissements)")
    assert lu == [f"ligne 1 : {raison}, ignorée"]


def test_semaine_53_valide(moteur_js):
    # 2026 a 53 semaines ISO (le 1er janvier 2027, vendredi, est en 2026-W53).
    assert evaluer(moteur_js, "JSON.stringify(suiviCleJour(suiviJoursDePeriode('2026-W53').debut))") == "2026-12-28"
    assert evaluer(moteur_js, "JSON.stringify(suiviCleJour(suiviJoursDePeriode('2026-W46').fin))") == "2026-11-15"


def bilan(moteur_js, notes: str, pointages: str, du: str, au: str) -> list:
    return evaluer(moteur_js, f"resumeBilan(suiviBilan([{notes}], [{pointages}], D('{du}'), D('{au}'), "
                              "{ clientPause: 'PAUSE' }))")


def test_un_bloc_par_projet_jours_et_semaine(moteur_js):
    r = bilan(moteur_js,
              "N('2026-11-14 16:00','2026-11-14','Armoire',  'bloque', -10, 'Défaut sortie 3'),"
              "N('2026-11-14 09:00','2026-11-14','Armoire',  'en_cours', 0, 'Version de 9 h'),"
              "N('2026-11-13 18:00','2026-W46',  'Armoire',  'en_cours', -10, 'Bilan semaine'),"
              "N('2026-11-12 08:00','2026-11-12','Carte',    'a_faire', 5, '')",
              "P('2026-11-13 09:00','2026-11-13 10:30','Alpha Industrie','Armoire'),"
              "P('2026-11-14 23:00','2026-11-15 01:00','Alpha Industrie','Armoire'),"   # passe minuit
              "P('2026-11-13 12:00','2026-11-13 13:00','PAUSE',''),"
              "P('2026-11-16 09:00','2026-11-16 10:00','Alpha Industrie','Armoire')",  # semaine suivante
              "2026-11-09", "2026-11-16")
    assert r == [
        {"projet": "Alpha Industrie / Armoire", "statut": "bloque", "priorite": -10, "minutes": 270,
         "lignes": ["2026-11-16 60 ",
                    "2026-W46 210 Bilan semaine",          # en tête de sa semaine, temps des jours de la semaine
                    "2026-11-15 60 ",
                    "2026-11-14 60 Défaut sortie 3",       # seule la dernière version du jour
                    "2026-11-13 90 "]},
        {"projet": "Alpha Industrie / Carte", "statut": "a_faire", "priorite": 5, "minutes": 0,
         "lignes": ["2026-11-12 0 "]},
    ]


def test_plage_etat_a_la_fin_et_termine_a_confirmer(moteur_js):
    notes = ("N('2026-11-10 17:00','2026-11-10','Armoire','termine', 0, 'Livré'),"
             "N('2026-11-20 17:00','2026-11-20','Armoire','en_cours', 0, 'Reprise')")
    pointages = "P('2026-11-12 09:00','2026-11-12 10:00','Alpha Industrie','Armoire')"
    # Plage 11/11 → 13/11 : pas de note dedans, mais du temps ; l'état est celui du 10/11 (terminé),
    # du temps pointé après → « terminé ? ». La note du 20/11, postérieure, est ignorée.
    r = bilan(moteur_js, notes, pointages, "2026-11-11", "2026-11-13")
    assert [(b["statut"], b["lignes"]) for b in r] == [("termine_a_confirmer", ["2026-11-12 60 "])]
    # Plage sans temps ni note : rien.
    assert bilan(moteur_js, notes, pointages, "2026-11-14", "2026-11-15") == []
    # Semaine ISO qui dépasse la fin de plage : placée au dernier jour de la plage, après les jours.
    r = bilan(moteur_js, "N('2026-11-11 17:00','2026-W46','Armoire','en_cours', 0, 'S46')", pointages,
              "2026-11-10", "2026-11-12")
    assert r[0]["lignes"] == ["2026-W46 60 S46", "2026-11-12 60 "]


def test_deux_postes_et_tri(moteur_js):
    r = bilan(moteur_js,
              "N('2026-11-14 17:00','2026-11-14','zeta', 'en_cours', 0, 'du bureau', 'bureau'),"
              "N('2026-11-14 18:00','2026-11-14','zeta', 'bloque', 0, 'du portable', 'portable'),"
              "N('2026-11-14 10:00','2026-11-14','Alpha','en_cours', 0, 'a', ''),"
              "N('2026-11-14 10:00','2026-11-14','beta', 'en_cours', -1, 'b', '')",
              "", "2026-11-14", "2026-11-14")
    assert [b["projet"] for b in r] == ["Alpha Industrie / beta", "Alpha Industrie / Alpha",
                                        "Alpha Industrie / zeta"]
    assert r[2]["lignes"] == ["2026-11-14 0 du bureau@bureau|du portable@portable"]
    assert r[2]["statut"] == "bloque"   # la note la plus récente, tous postes confondus


def test_filtre_garder(moteur_js):
    r = evaluer(moteur_js, "resumeBilan(suiviBilan([N('2026-11-14 10:00','2026-11-14','Armoire','en_cours')], "
                           "[P('2026-11-14 09:00','2026-11-14 10:00','Bêta','Carte')], D('2026-11-14'), "
                           "D('2026-11-14'), { clientPause: 'PAUSE', garder: c => c === 'Bêta' }))")
    assert [b["projet"] for b in r] == ["Bêta / Carte"]

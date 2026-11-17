"""Fusion de deux CSV dans le lecteur de bilan (CDC fusion.md) : algorithme JS de lecteur/fusion.js,
exécuté par le moteur JavaScript de Qt (pas besoin de node)."""

import json

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine

from pointeuse.bilan import DOSSIER_LECTEUR

AIDES = r"""
function L(debut, fin, client, projet, tache) {
    const date = h => {
        let jour = '17';
        let heure = h;
        if (h.includes(' ')) [jour, heure] = h.split(' ');
        const [hh, mm] = heure.split(':');
        return new Date(2026, 10, +jour, +hh, +mm);
    };
    return { debut: date(debut), fin: date(fin), client, projet: projet || '', tache: tache || '', description: '' };
}
function hm(d) { return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); }
function court(p) { return hm(p.debut) + '-' + hm(p.fin) + ' ' + p.client; }
function resume(r) {
    return JSON.stringify({
        pointages: r.pointages.map(court),
        retires: r.retires.map(x => {
            let texte = court(x.ligne) + ' < ' + x.recouvertPar;
            if (x.fichier !== undefined) texte += ' #' + x.fichier;
            return texte;
        }),
        doublons: r.doublons,
    });
}
"""


@pytest.fixture(scope="module")
def moteur_js():
    app = QCoreApplication.instance() or QCoreApplication([])   # noqa: F841 — requis par QJSEngine
    moteur = QJSEngine()
    for source in ((DOSSIER_LECTEUR / "fusion.js").read_text(encoding="utf-8"), AIDES):
        resultat = moteur.evaluate(source)
        assert not resultat.isError(), resultat.toString()
    return moteur


def fusion(moteur_js, principal: str, secondaire: str, pause_cede: bool = True) -> dict:
    options = json.dumps({"clientPause": "PAUSE", "pauseCede": pause_cede})
    resultat = moteur_js.evaluate(f"resume(fusionner([{principal}], [{secondaire}], {options}))")
    assert not resultat.isError(), resultat.toString()
    return json.loads(resultat.toString())


def test_exemple_du_cdc(moteur_js):
    r = fusion(moteur_js, "L('08:30','10:00','A','x')", "L('09:30','11:00','B','y')")
    assert r == {"pointages": ["08:30-10:00 A", "10:00-11:00 B"],
                 "retires": ["09:30-10:00 B < A / x"], "doublons": 0}


def test_le_secondaire_comble_les_trous(moteur_js):
    r = fusion(moteur_js, "L('08:00','12:00','A')", "L('13:30','17:00','B')")
    assert r["pointages"] == ["08:00-12:00 A", "13:30-17:00 B"]
    assert r["retires"] == []


def test_secondaire_coupe_en_deux(moteur_js):
    r = fusion(moteur_js, "L('10:00','10:30','A')", "L('09:00','12:00','B')")
    assert r["pointages"] == ["09:00-10:00 B", "10:00-10:30 A", "10:30-12:00 B"]
    assert r["retires"] == ["10:00-10:30 B < A"]


def test_secondaire_entierement_recouvert(moteur_js):
    r = fusion(moteur_js, "L('09:00','10:00','A'), L('10:00','12:00','C')", "L('09:30','11:00','B')")
    assert r["pointages"] == ["09:00-10:00 A", "10:00-12:00 C"]
    assert r["retires"] == ["09:30-10:00 B < A", "10:00-11:00 B < C"]


def test_refusionner_le_meme_fichier_ne_change_rien(moteur_js):
    lignes = "L('08:00','09:00','A'), L('09:00','09:15','PAUSE'), L('09:15','10:00','B')"
    r = fusion(moteur_js, lignes, lignes)
    assert r == {"pointages": ["08:00-09:00 A", "09:00-09:15 PAUSE", "09:15-10:00 B"],
                 "retires": [], "doublons": 3}


def test_pause_du_principal_cede_au_travail_du_secondaire(moteur_js):
    r = fusion(moteur_js, "L('12:00','13:30','PAUSE')", "L('12:30','13:00','B')")
    assert r["pointages"] == ["12:00-12:30 PAUSE", "12:30-13:00 B", "13:00-13:30 PAUSE"]
    assert r["retires"] == []


def test_regle_stricte_la_pause_du_principal_l_emporte(moteur_js):
    r = fusion(moteur_js, "L('12:00','13:30','PAUSE')", "L('12:30','13:00','B')", pause_cede=False)
    assert r["pointages"] == ["12:00-13:30 PAUSE"]
    assert r["retires"] == ["12:30-13:00 B < PAUSE"]


def test_pause_du_secondaire_ne_compte_pas_double_et_n_est_pas_signalee(moteur_js):
    r = fusion(moteur_js, "L('08:00','10:00','A'), L('12:00','13:00','PAUSE')",
               "L('09:00','09:30','PAUSE'), L('12:30','13:30','PAUSE')")
    assert r["pointages"] == ["08:00-10:00 A", "12:00-13:00 PAUSE", "13:00-13:30 PAUSE"]
    assert r["retires"] == []


def test_ligne_sur_minuit(moteur_js):
    r = fusion(moteur_js, "L('17 23:00','18 01:00','A')", "L('18 00:30','18 02:00','B')")
    assert r["pointages"] == ["23:00-01:00 A", "01:00-02:00 B"]


def test_fusion_a_la_chaine(moteur_js):
    script = """resume(fusionnerFichiers([
        [L('09:00','10:00','A')],
        [L('08:00','09:30','B')],
        [L('08:30','11:00','C')],
    ], 0, {clientPause: 'PAUSE', pauseCede: true}))"""
    r = json.loads(moteur_js.evaluate(script).toString())
    assert r["pointages"] == ["08:00-09:00 B", "09:00-10:00 A", "10:00-11:00 C"]
    assert r["retires"] == ["08:30-09:00 C < B #2", "09:00-09:30 B < A #1", "09:00-10:00 C < A #2"]
    assert r["doublons"] == [0, 0, 0]


def test_principal_au_choix(moteur_js):
    script = """resume(fusionnerFichiers([[L('08:30','10:00','A')], [L('09:30','11:00','B')]], 1,
                                         {clientPause: 'PAUSE', pauseCede: true}))"""
    r = json.loads(moteur_js.evaluate(script).toString())
    assert r["pointages"] == ["08:30-09:30 A", "09:30-11:00 B"]
    assert r["retires"] == ["09:30-10:00 A < B #0"]


def test_lecteur_charge_fusion_avant_pointeuse():
    page = (DOSSIER_LECTEUR / "index.html").read_text(encoding="utf-8")
    assert page.index('<script src="fusion.js">') < page.index('<script src="pointeuse.js">')

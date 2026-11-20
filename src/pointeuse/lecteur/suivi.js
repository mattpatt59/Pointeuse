/* ═══════════════════════════════════════
   SUIVI DES PROJETS (pointeuse_suivi.jsonl) — CDC docs/cdc/suivi_projets.md, ADR 004
   Une ligne = une note JSON (statut, priorité, texte) d'un projet pour une période
   (jour « 2026-11-14 » ou semaine ISO « 2026-W46 »). Fichier en ajout seul : la
   dernière version de la période est celle qui compte.
   Mêmes règles de lecture que src/pointeuse/suivi.py : les garder alignées avec l'ADR 004
   (jeu d'exemple commun tests/donnees/suivi_exemple.jsonl).
   Fonctions pures, sans page web : testées par tests/test_bilan_suivi.py (moteur JS de Qt).
   Licence MIT (voir LICENSE du dépôt pointeuse).
═══════════════════════════════════════ */
'use strict';

const SUIVI = {
    versionLigne:     1,                      // champ « v » (settings.VERSION_LIGNE_SUIVI)
    statuts: {                                // code → libellé (settings.STATUTS_SUIVI)
        a_faire:        'à faire',
        en_cours:       'en cours',
        bloque:         'bloqué',
        attente_client: 'en attente client',
        termine:        'terminé',
    },
    termine:          'termine',
    termineAConfirmer: 'termine_a_confirmer', // calculé, jamais écrit
    libelleTermineAConfirmer: 'terminé ?',
    prioriteMin:      -99,
    prioriteMax:      99,
    prioriteDefaut:   0,
    champsTexte:      ['horodatage', 'periode', 'client', 'projet', 'statut', 'texte'],
    posteLocal:       'local',                // journal du PC qui ouvre le bilan (CDC multi_postes.md)
    prefixePoste:     'PC ',                  // poste sans nom parlant : « PC 2 », « PC 3 »…
    nomGenerique:     /^pointeuse/i,          // pointeuse_suivi.jsonl, pointeuse.csv, « pointeuse_suivi (1).jsonl »…
};

/* ─── Dates (jours civils, heure locale) ─── */

function suiviDeux(n) {
    return String(n).padStart(2, '0');
}

function suiviJour(d) {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function suiviAjouterJours(d, n) {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

function suiviCleJour(d) {
    return d.getFullYear() + '-' + suiviDeux(d.getMonth() + 1) + '-' + suiviDeux(d.getDate());
}

/** Lundi de la semaine ISO n de l'année (la semaine 1 contient le 4 janvier). */
function suiviLundiIso(annee, semaine) {
    const quatreJanvier = new Date(annee, 0, 4);
    const lundiS1 = suiviAjouterJours(quatreJanvier, -((quatreJanvier.getDay() + 6) % 7));
    return suiviAjouterJours(lundiS1, (semaine - 1) * 7);
}

/** Nombre de semaines ISO de l'année (52 ou 53 : le 28 décembre est toujours dans la dernière). */
function suiviSemainesDansAnnee(annee) {
    const d = new Date(annee, 11, 28);
    const jeudi = suiviAjouterJours(d, 3 - ((d.getDay() + 6) % 7));
    const debut = new Date(jeudi.getFullYear(), 0, 1);
    return 1 + Math.floor(Math.round((jeudi - debut) / 86400000) / 7);
}

/** { debut, fin } (jours inclus) d'une période ; null si elle est mal formée. */
function suiviJoursDePeriode(periode) {
    let m = /^(\d{4})-W(\d{2})$/.exec(periode);
    if (m) {
        const annee = +m[1];
        const semaine = +m[2];
        if (semaine < 1 || semaine > suiviSemainesDansAnnee(annee)) return null;
        const lundi = suiviLundiIso(annee, semaine);
        return { debut: lundi, fin: suiviAjouterJours(lundi, 6) };
    }
    m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(periode);
    if (!m) return null;
    const jour = new Date(+m[1], +m[2] - 1, +m[3]);
    if (suiviCleJour(jour) !== periode) return null;   // refuse le 31 février
    return { debut: jour, fin: jour };
}

function suiviEstSemaine(periode) {
    return /^\d{4}-W\d{2}$/.test(periode);
}

/** « 2026-11-14 18:02:00 » → Date ; null si illisible. */
function suiviLireHorodatage(texte) {
    const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/.exec(texte);
    if (!m) return null;
    const d = new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
    if (d.getMonth() !== +m[2] - 1 || d.getDate() !== +m[3] || d.getHours() !== +m[4]) return null;
    return d;
}

/** Valeur citée comme Python le fait (repr) : messages identiques à suivi.py. */
function suiviCite(v) {
    if (typeof v === 'string') return "'" + v + "'";
    if (v === null || v === undefined) return 'None';
    if (v === true) return 'True';
    if (v === false) return 'False';
    return String(v);
}

/* ─── Lecture ─── */

/** Objet JSON → { note, remarques } ; lève Error(raison) si la ligne est refusée. */
function suiviNoteDepuisObjet(objet, poste) {
    if (objet === null || typeof objet !== 'object' || Array.isArray(objet)) {
        throw new Error("ce n'est pas un objet JSON");
    }
    if (objet.v !== SUIVI.versionLigne) throw new Error('version de format inconnue : ' + suiviCite(objet.v));
    for (const champ of SUIVI.champsTexte) {
        if (typeof objet[champ] !== 'string') throw new Error('champ « ' + champ + ' » manquant ou non textuel');
    }
    const priorite = objet.priorite;
    if (typeof priorite !== 'number' || !Number.isInteger(priorite)) {
        throw new Error('champ « priorite » manquant ou non entier');
    }
    if (!Object.prototype.hasOwnProperty.call(SUIVI.statuts, objet.statut)) {
        throw new Error('statut inconnu : ' + suiviCite(objet.statut));
    }
    if (!objet.client.trim() || !objet.projet.trim()) throw new Error('client ou projet vide');
    const horodatage = suiviLireHorodatage(objet.horodatage);
    if (!horodatage) throw new Error('horodatage illisible : ' + suiviCite(objet.horodatage));
    if (!suiviJoursDePeriode(objet.periode)) throw new Error('période mal formée : ' + suiviCite(objet.periode));
    const remarques = [];
    const bornee = Math.min(Math.max(priorite, SUIVI.prioriteMin), SUIVI.prioriteMax);
    if (bornee !== priorite) remarques.push('priorité ' + priorite + ' ramenée à ' + bornee);
    const note = {
        horodatage, periode: objet.periode, client: objet.client, projet: objet.projet,
        statut: objet.statut, priorite: bornee, texte: objet.texte, poste: poste || '',
    };
    return { note, remarques };
}

/**
 * Contenu texte d'un pointeuse_suivi.jsonl → { notes, avertissements }.
 * Notes triées par horodatage (ordre du fichier en cas d'égalité) ; une ligne abîmée est
 * ignorée avec « ligne N : raison, ignorée », les autres sont lues normalement.
 */
function suiviLire(texte, poste) {
    const notes = [];
    const avertissements = [];
    let contenu = String(texte);
    if (contenu.charCodeAt(0) === 0xFEFF) contenu = contenu.slice(1);   // BOM toléré
    contenu.split('\n').forEach((brute, i) => {
        const numero = i + 1;
        const ligne = brute.replace(/\r+$/, '');
        if (!ligne.trim()) return;
        if (ligne.includes('�')) {
            avertissements.push('ligne ' + numero + ' : encodage illisible (UTF-8 attendu), ignorée');
            return;
        }
        let objet;
        try {
            objet = JSON.parse(ligne);
        } catch (e) {
            avertissements.push('ligne ' + numero + ' : JSON invalide, ignorée');
            return;
        }
        let lu;
        try {
            lu = suiviNoteDepuisObjet(objet, poste);
        } catch (e) {
            avertissements.push('ligne ' + numero + ' : ' + e.message + ', ignorée');
            return;
        }
        for (const remarque of lu.remarques) avertissements.push('ligne ' + numero + ' : ' + remarque);
        notes.push(lu.note);
    });
    return { notes: suiviTrier(notes), avertissements };
}

/** Tri stable par horodatage. */
function suiviTrier(notes) {
    return notes.map((n, i) => [n, i])
        .sort((a, b) => (a[0].horodatage - b[0].horodatage) || (a[1] - b[1]))
        .map(x => x[0]);
}

/* ─── Plusieurs postes (CDC suivi_projets.md étape 7) ─── */

/** Nom de poste tiré d'un nom de fichier (sans extension), ou '' s'il est générique. */
function suiviNomDepuisFichier(nom) {
    const texte = String(nom || '').trim();
    if (!texte || SUIVI.nomGenerique.test(texte)) return '';
    return texte.replace(/\.[^.]*$/, '').trim();
}

/**
 * Noms de poste des jsonl lus ensemble (un même « Ajouter un autre PC »).
 * Un seul jsonl : nom tiré du jsonl, sinon du CSV lu avec lui (s'il est seul), sinon « PC n ».
 * Plusieurs jsonl : un poste chacun. Un nom déjà pris reçoit « (2) », « (3) »… :
 * deux PC ne se partagent jamais un nom, sinon la note de l'un cacherait celle de l'autre.
 */
function suiviNomsPostes(nomsJsonl, nomsCsv, dejaPris) {
    const pris = new Set(dejaPris || []);
    return nomsJsonl.map(nom => {
        let base = suiviNomDepuisFichier(nom);
        if (!base && nomsJsonl.length === 1 && nomsCsv.length === 1) base = suiviNomDepuisFichier(nomsCsv[0]);
        let choisi = base;
        if (!base) {
            let numero = pris.size + 1;
            while (pris.has(SUIVI.prefixePoste + numero)) numero++;
            choisi = SUIVI.prefixePoste + numero;
        } else {
            let numero = 2;
            while (pris.has(choisi)) {
                choisi = base + ' (' + numero + ')';
                numero++;
            }
        }
        pris.add(choisi);
        return choisi;
    });
}

/** Contenu d'une note, sans le poste. */
function suiviCleNote(n) {
    return [n.horodatage.getTime(), n.periode, n.client, n.projet, n.statut, n.priorite, n.texte].join('\u0001');
}

/**
 * Journaux de plusieurs postes (listes de notes, dans l'ordre de chargement) → une seule liste.
 * { notes : toutes les notes triées par horodatage, doublons : nb de notes ignorées par liste }.
 * Une note identique à une note d'une liste précédente (même fichier lu deux fois, copie du
 * journal local dans le dossier externe) n'est gardée qu'une fois, sous le premier poste.
 */
function suiviFusionner(listes) {
    const vues = new Set();
    const notes = [];
    const doublons = listes.map(liste => {
        let ignorees = 0;
        for (const n of liste) {
            const cle = suiviCleNote(n);
            if (vues.has(cle)) {
                ignorees++;
                continue;
            }
            vues.add(cle);
            notes.push(n);
        }
        return ignorees;
    });
    return { notes: suiviTrier(notes), doublons };
}

/* ─── Règles de lecture (ADR 004) ─── */

function suiviCleProjet(client, projet) {
    return client + '\u0001' + projet;
}

/** Dernière version par (poste, client, projet, période) ; deux postes → deux notes. */
function suiviNotesRetenues(notes) {
    const dernieres = new Map();
    for (const n of suiviTrier(notes)) {
        dernieres.set([n.poste, n.client, n.projet, n.periode].join('\u0001'), n);
    }
    return suiviTrier(Array.from(dernieres.values()));
}

/** Note la plus récente de chaque projet (tous postes, toutes périodes) écrite avant `avant` (Date, exclue) ou sans limite. */
function suiviEtatsActuels(notes, avant) {
    const etats = new Map();
    for (const n of suiviTrier(notes)) {
        if (avant && n.horodatage >= avant) continue;
        etats.set(suiviCleProjet(n.client, n.projet), n);
    }
    return etats;
}

/** Statut affiché : « terminé ? » si du temps a été pointé après la note qui a terminé le projet. */
function suiviStatutAffiche(etat, dernierPointage) {
    if (!etat) return null;
    if (etat.statut === SUIVI.termine && dernierPointage && dernierPointage > etat.horodatage) {
        return SUIVI.termineAConfirmer;
    }
    return etat.statut;
}

function suiviLibelleStatut(statut) {
    if (!statut) return '';
    if (statut === SUIVI.termineAConfirmer) return SUIVI.libelleTermineAConfirmer;
    return SUIVI.statuts[statut] || statut;
}

/* ─── Bilan : un bloc par projet ─── */

/** Minutes d'un pointage par jour (une tâche qui passe minuit compte sur les deux jours) → [{ jour, minutes }]. */
function suiviMorceaux(p) {
    const morceaux = [];
    let d = p.debut;
    while (d < p.fin) {
        const minuit = suiviAjouterJours(suiviJour(d), 1);
        let f = p.fin;
        if (minuit < f) f = minuit;
        morceaux.push({ jour: suiviJour(d), minutes: (f - d) / 60000 });
        d = f;
    }
    return morceaux;
}

function suiviComparerNoms(a, b) {
    return a.localeCompare(b, 'fr', { sensitivity: 'base' });
}

/**
 * Blocs du bilan « Suivi », triés par priorité puis client puis projet.
 *   notes     : toutes les notes lues (tous postes)
 *   pointages : [{ debut, fin, client, projet }] (pauses comprises : elles sont écartées)
 *   du, au    : jours inclus de la plage
 *   options   : { clientPause, garder(client, projet) → bool (filtres de la page) }
 * Un projet apparaît s'il a du temps ou une note sur la plage. Pour chacun :
 *   { client, projet, statut, priorite, etat (note la plus récente à la fin de la plage),
 *     minutes, lignes: [{ type: 'semaine', periode, debut, fin, minutes, notes }
 *                       | { type: 'jour', jour, minutes, notes }] }
 * Lignes du plus récent au plus ancien : une par jour (temps ou note), la note d'une
 * semaine en tête de sa semaine, quel que soit le réglage de période de la Pointeuse.
 */
function suiviBilan(notes, pointages, du, au, options) {
    const opts = options || {};
    const garder = opts.garder || (() => true);
    const finPlage = suiviAjouterJours(au, 1);
    const projets = new Map();
    const projet = (client, nom) => {
        const cle = suiviCleProjet(client, nom);
        if (!projets.has(cle)) {
            projets.set(cle, { client, projet: nom, minutes: 0, jours: new Map(), periodes: new Map(), dernierPointage: null });
        }
        return projets.get(cle);
    };
    const dernierPointage = new Map();   // pointé jusqu'à la fin de la plage : pour « terminé ? »

    for (const p of pointages) {
        if (p.client === opts.clientPause) continue;
        const cle = suiviCleProjet(p.client, p.projet);
        let fin = p.fin;
        if (fin > finPlage) fin = finPlage;
        if (p.debut < finPlage && (!dernierPointage.has(cle) || fin > dernierPointage.get(cle))) dernierPointage.set(cle, fin);
        if (p.fin <= du || p.debut >= finPlage || !garder(p.client, p.projet)) continue;
        for (const m of suiviMorceaux(p)) {
            if (m.jour < du || m.jour >= finPlage || m.minutes <= 0) continue;
            const bloc = projet(p.client, p.projet);
            const cleJour = suiviCleJour(m.jour);
            bloc.jours.set(cleJour, (bloc.jours.get(cleJour) || 0) + m.minutes);
            bloc.minutes += m.minutes;
        }
    }

    const visibles = notes.filter(n => n.horodatage < finPlage);
    for (const n of suiviNotesRetenues(visibles)) {
        const jours = suiviJoursDePeriode(n.periode);
        if (jours.fin < du || jours.debut > au || !garder(n.client, n.projet)) continue;
        const bloc = projet(n.client, n.projet);
        if (!bloc.periodes.has(n.periode)) bloc.periodes.set(n.periode, []);
        bloc.periodes.get(n.periode).push(n);
    }

    const etats = suiviEtatsActuels(notes, finPlage);
    const resultat = [];
    for (const [cle, bloc] of projets) {
        const etat = etats.get(cle) || null;
        let priorite = SUIVI.prioriteDefaut;
        if (etat) priorite = etat.priorite;
        resultat.push({
            client: bloc.client,
            projet: bloc.projet,
            etat,
            statut: suiviStatutAffiche(etat, dernierPointage.get(cle) || null),
            priorite,
            minutes: bloc.minutes,
            lignes: suiviLignes(bloc, du, au),
        });
    }
    return resultat.sort((a, b) => (a.priorite - b.priorite)
        || suiviComparerNoms(a.client, b.client) || suiviComparerNoms(a.projet, b.projet));
}

/** Lignes d'un projet : jours (temps ou note-jour) et en-têtes de semaine (note-semaine). */
function suiviLignes(bloc, du, au) {
    const entrees = [];
    const jours = new Set(bloc.jours.keys());
    for (const periode of bloc.periodes.keys()) {
        if (!suiviEstSemaine(periode)) jours.add(periode);
    }
    for (const cle of jours) {
        const jour = suiviJoursDePeriode(cle).debut;
        entrees.push({ cle: jour, rang: 0, ligne: {
            type: 'jour', jour, minutes: bloc.jours.get(cle) || 0, notes: bloc.periodes.get(cle) || [] } });
    }
    for (const [periode, notes] of bloc.periodes) {
        if (!suiviEstSemaine(periode)) continue;
        const { debut, fin } = suiviJoursDePeriode(periode);
        let minutes = 0;
        for (const [cle, m] of bloc.jours) {
            const jour = suiviJoursDePeriode(cle).debut;
            if (jour >= debut && jour <= fin) minutes += m;
        }
        let place = fin;            // en tête de la semaine, à l'intérieur de la plage
        if (place > au) place = au;
        entrees.push({ cle: place, rang: 1, ligne: { type: 'semaine', periode, debut, fin, minutes, notes } });
    }
    entrees.sort((a, b) => (b.cle - a.cle) || (b.rang - a.rang));
    return entrees.map(e => e.ligne);
}

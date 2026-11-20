/* ═══════════════════════════════════════
   POINTEUSE (lecteur de bilan) — outil gratuit T-Elec
   Lit le fichier pointeuse.csv écrit par le logiciel Pointeuse et en fait
   le bilan : temps par client / projet / tâche, par jour, semaine ou mois.
   100 % navigateur, sans dépendance : le fichier n'est jamais envoyé.
   Licence MIT (voir LICENSE du dépôt pointeuse) — dépôt pointeuse, src/pointeuse/lecteur/.
═══════════════════════════════════════ */
'use strict';

/* ═══════════════════════════════════════
   CONSTANTES
═══════════════════════════════════════ */
const CFG = {
    clientPause:      'PAUSE',          // nom réservé par la Pointeuse pour les pauses
    colonnesRequises: ['date_in', 'date_out', 'client'],
    cleReglages:      't-elec-pointeuse-reglages',   // localStorage : réglages seulement, jamais les pointages
    toastMs:          3500,

    // Fusion de plusieurs fichiers (CDC fusion.md) — format de sortie = pointeuse.csv (settings.py)
    colonnesCsv:      ['date_in', 'date_out', 'client', 'projet', 'tache', 'description', 'duree_min'],
    fusionPauseCede:  true,      // une pause du PC principal laisse la place au travail du secondaire
    nomFusion:        'pointeuse_fusion.csv',
    nomRapport:       'fusion_rapport.csv',

    // Couleurs des clients — ordre fixe validé daltonisme (écart voisins ≥ 10, vision normale ≥ 19,6).
    // Attribuées par temps total sur tout le fichier : un client garde sa couleur quand on filtre.
    palette:          ['#70AD47', '#e87ba4', '#eda100', '#e34948', '#2a78d6', '#eb6834', '#6250d6', '#1baf7a'],
    couleurAutres:    '#9ca3af',

    // Graphe
    hauteurGraphe:    260,       // px — zone de tracé
    marge:            { gauche: 44, droite: 8, haut: 18, bas: 30 },
    ecartSegments:    2,         // px — liseré blanc entre deux clients d'une même barre
    rayonBarre:       4,         // px — arrondi du haut de la barre
    largeurBarreMax:  48,        // px
    pxParEtiquette:   46,        // px — espacement minimal entre deux étiquettes de l'axe X
    totauxSiBarresMax: 16,       // total écrit au-dessus des barres s'il y en a au plus autant
    graduationsVisees: 5,

    // Regroupement automatique selon la longueur de la période (jours)
    autoJourMax:      31,
    autoSemaineMax:   184,

    lignesAffichees:  500,
    erreursAffichees: 5,
    exempleSemaines:  6,
};

const MOIS_COURTS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const MOIS_LONGS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const JOURS_COURTS = ['dim.', 'lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.'];

const PERIODES = [
    ['semaine',      'Cette semaine'],
    ['semainePrec',  'Semaine dernière'],
    ['mois',         'Ce mois-ci'],
    ['moisPrec',     'Mois dernier'],
    ['annee',        'Cette année'],
    ['tout',         'Tout le fichier'],
    ['perso',        'Dates choisies'],
];

/* ═══════════════════════════════════════
   ÉTAT
═══════════════════════════════════════ */
let pointages = [];      // { debut, fin, client, projet, tache, description, recherche }
let fichiers = [];       // { nom, lignes, erreurs: [], pointages } — dans l'ordre de chargement
let principal = 0;       // index du PC principal dans fichiers (plusieurs fichiers : fusion)
let fusion = null;       // { retires: [{ ligne, recouvertPar, fichier }], doublons: [] } si plusieurs fichiers
let couleurs = new Map();  // client → couleur ; absent = « Autres »
const masques = new Set(); // clients décochés
let recherche = '';
let resultat = null;     // dernier calcul (pour l'export et l'info-bulle)
let noteDonnees = '';    // dossier externe injoignable (bilan.py, ADR 005) : affiché dans « Fichiers lus »
let suivis = [];         // pointeuse_suivi.jsonl lus : { nom, poste, notes, avertissements } (suivi.js, ADR 004)
let suiviFusion = { notes: [], doublons: [] };   // journaux de tous les postes réunis (suiviFusionner)

const reglages = {
    periode:      'mois',
    du:           null,   // 'AAAA-MM-JJ' si periode = 'perso'
    au:           null,
    regroupement: 'auto', // auto | jour | semaine | mois
    detail:       'projet', // client | projet | tache
    pauses:       false,  // pauses visibles dans la liste des lignes
    vue:          'temps', // temps | suivi (page « Suivi » : statut et notes par projet)
    historique:   'periode', // suivi : notes de la période du bilan | depuis le …
    depuis:       null,   // 'AAAA-MM-JJ' si historique = 'depuis'
};

const $ = sel => document.querySelector(sel);

/* ═══════════════════════════════════════
   UTILITAIRES
═══════════════════════════════════════ */
function esc(s) {
    const table = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return String(s).replace(/[&<>"']/g, c => table[c]);
}

function deux(n) {
    return String(n).padStart(2, '0');
}

function sansAccents(s) {
    return String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

/** 95 → « 1 h 35 » */
function hmin(minutes) {
    let m = Math.round(minutes);
    if (m < 0) m = 0;
    return Math.floor(m / 60) + ' h ' + deux(m % 60);
}

/** 95 → « 1,58 » */
function heuresDecimales(minutes) {
    return (minutes / 60).toFixed(2).replace('.', ',');
}

function toast(msg, erreur) {
    const t = $('#toast');
    t.textContent = msg;
    t.classList.toggle('toast--erreur', Boolean(erreur));
    t.hidden = false;
    clearTimeout(toast.minuteur);
    toast.minuteur = setTimeout(() => { t.hidden = true; }, CFG.toastMs);
}

function telecharger(contenu, nom, type) {
    const url = URL.createObjectURL(new Blob([contenu], { type }));
    const a = document.createElement('a');
    a.href = url;
    a.download = nom;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ═══════════════════════════════════════
   DATES (heure locale, jours civils)
═══════════════════════════════════════ */
function jourDe(d) {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function ajouterJours(d, n) {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

function ajouterMois(d, n) {
    return new Date(d.getFullYear(), d.getMonth() + n, 1);
}

function cleJour(d) {
    return d.getFullYear() + '-' + deux(d.getMonth() + 1) + '-' + deux(d.getDate());
}

function depuisCle(cle) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(cle || '');
    if (!m) return null;
    return new Date(+m[1], +m[2] - 1, +m[3]);
}

function texteJour(d) {
    return deux(d.getDate()) + '/' + deux(d.getMonth() + 1) + '/' + d.getFullYear();
}

function texteHeure(d) {
    return deux(d.getHours()) + ':' + deux(d.getMinutes());
}

function lundiDe(d) {
    return ajouterJours(jourDe(d), -((d.getDay() + 6) % 7));
}

function dernierJourDuMois(d) {
    return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

/** Numéro de semaine ISO 8601 (la semaine 1 contient le premier jeudi de l'année). */
function semaineIso(d) {
    const jeudi = ajouterJours(jourDe(d), 3 - ((d.getDay() + 6) % 7));
    const debutAnnee = new Date(jeudi.getFullYear(), 0, 1);
    return 1 + Math.floor(Math.round((jeudi - debutAnnee) / 86400000) / 7);
}

function nbJours(du, au) {
    return Math.round((au - du) / 86400000) + 1;
}

/** « 2026-11-17 08:33 », « 2026-11-17T08:33:00 » ou « 17/11/2026 08:33 » (fichier repassé par Excel). */
function lireDate(texte) {
    const s = String(texte).trim();
    let m = /^(\d{4})-(\d{1,2})-(\d{1,2})[ T](\d{1,2}):(\d{2})(?::\d{2})?$/.exec(s);
    if (m) return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
    m = /^(\d{1,2})\/(\d{1,2})\/(\d{4}) (\d{1,2}):(\d{2})(?::\d{2})?$/.exec(s);
    if (m) return new Date(+m[3], +m[2] - 1, +m[1], +m[4], +m[5]);
    return null;
}

/* ═══════════════════════════════════════
   LECTURE DU CSV
═══════════════════════════════════════ */
/** Découpe un CSV (guillemets « à la Excel » : "a;b", "" pour un guillemet). */
function decouperCsv(texte, separateur) {
    const rangs = [];
    let rang = [];
    let champ = '';
    let entreGuillemets = false;
    for (let i = 0; i < texte.length; i++) {
        const c = texte[i];
        if (entreGuillemets) {
            if (c === '"' && texte[i + 1] === '"') {
                champ += '"';
                i++;
            } else if (c === '"') {
                entreGuillemets = false;
            } else {
                champ += c;
            }
        } else if (c === '"') {
            entreGuillemets = true;
        } else if (c === separateur) {
            rang.push(champ);
            champ = '';
        } else if (c === '\n' || c === '\r') {
            if (c === '\r' && texte[i + 1] === '\n') i++;
            rang.push(champ);
            rangs.push(rang);
            rang = [];
            champ = '';
        } else {
            champ += c;
        }
    }
    if (champ !== '' || rang.length > 0) {
        rang.push(champ);
        rangs.push(rang);
    }
    return rangs;
}

/** → { pointages: [...], erreurs: ['Ligne 3 : …'] } ; lève une Error si le fichier n'est pas un CSV de la Pointeuse. */
function analyserCsv(texte) {
    const propre = texte.replace(/^﻿/, '');
    const premiereLigne = propre.split(/\r?\n/, 1)[0];
    let separateur = ';';
    if (!premiereLigne.includes(';') && premiereLigne.includes(',')) separateur = ',';

    const rangs = decouperCsv(propre, separateur);
    if (rangs.length === 0) throw new Error('fichier vide');
    const entete = rangs[0].map(c => c.trim().toLowerCase());
    const index = {};
    entete.forEach((nom, i) => { index[nom] = i; });
    const manquantes = CFG.colonnesRequises.filter(c => !(c in index));
    if (manquantes.length > 0) {
        throw new Error('colonne(s) ' + manquantes.join(', ') + ' absente(s) — est-ce bien le pointeuse.csv ?');
    }

    const champ = (rang, nom) => {
        if (!(nom in index)) return '';
        return (rang[index[nom]] || '').trim();
    };
    const resultat = { pointages: [], erreurs: [] };
    for (let i = 1; i < rangs.length; i++) {
        const rang = rangs[i];
        if (rang.every(c => c.trim() === '')) continue;
        const numero = i + 1;
        const debut = lireDate(champ(rang, 'date_in'));
        const fin = lireDate(champ(rang, 'date_out'));
        if (debut === null) { resultat.erreurs.push('Ligne ' + numero + ' : date de début illisible'); continue; }
        if (fin === null) { resultat.erreurs.push('Ligne ' + numero + ' : date de fin illisible'); continue; }
        if (fin < debut) { resultat.erreurs.push('Ligne ' + numero + ' : fin avant le début'); continue; }
        const p = {
            debut, fin,
            client: champ(rang, 'client'),
            projet: champ(rang, 'projet'),
            tache: champ(rang, 'tache'),
            description: champ(rang, 'description'),
        };
        p.recherche = sansAccents([p.client, p.projet, p.tache, p.description].join(' '));
        resultat.pointages.push(p);
    }
    return resultat;
}

/**
 * Lit les fichiers donnés (doublons exacts d'un même fichier retirés).
 * ajouter = false : ils remplacent les données ; true : ils s'ajoutent (« Ajouter un autre PC »).
 * Plusieurs fichiers : fusion, le PC principal l'emporte (fusion.js, CDC fusion.md).
 */
function chargerTextes(entrees, ajouter, entreesSuivi) {
    const lus = [];
    for (const { nom, texte, poste } of entrees) {
        let res;
        try {
            res = analyserCsv(texte);
        } catch (e) {
            toast(nom + ' : ' + e.message, true);
            continue;
        }
        const vus = new Set();
        const lignes = [];
        for (const p of res.pointages) {
            const cle = fusionCle(p);
            if (vus.has(cle)) continue;
            vus.add(cle);
            lignes.push(p);
        }
        lus.push({ nom, poste: poste || '', lignes: lignes.length, erreurs: res.erreurs, pointages: lignes });
    }
    // Notes de suivi : un nom de poste par journal (plusieurs postes : notes côte à côte, étape 7).
    const listeSuivi = entreesSuivi || [];
    let dejaPris = [];
    if (ajouter) dejaPris = suivis.map(f => f.poste);
    const postes = suiviNomsPostes(listeSuivi.map(e => e.nom), entrees.map(e => e.nom), dejaPris);
    const suivisLus = listeSuivi.map(({ nom, texte, poste }, i) => {
        const nomPoste = poste || postes[i];
        return Object.assign({ nom, poste: nomPoste }, suiviLire(texte, nomPoste));
    });
    if (lus.length === 0 && suivisLus.length === 0) return;

    if (ajouter) {
        fichiers = fichiers.concat(lus);
        suivis = suivis.concat(suivisLus);
    } else {
        fichiers = lus;
        principal = 0;   // ouvert depuis la Pointeuse : son CSV est chargé en premier
        suivis = suivisLus;
        noteDonnees = '';
    }
    fusionnerFichiersCharges();
    suiviFusion = suiviFusionner(suivis.map(f => f.notes));
    masques.clear();
    recherche = '';
    attribuerCouleurs();

    // Rien sur la période choisie (vieux fichier) : on montre tout le fichier.
    if (pointages.length > 0 && calculer().nbLignes === 0) {
        reglages.periode = 'tout';
        toast('Aucun pointage sur la période choisie : affichage de tout le fichier.');
    }
    toutAfficher();
}

/** Nom affiché d'un CSV : son poste (dossier externe, ADR 005), sinon son nom de fichier. */
function libelleFichier(f) {
    if (f.poste) return f.poste;
    return f.nom;
}

/** pointages ← fichier unique, ou fusion des fichiers chargés autour du PC principal. */
function fusionnerFichiersCharges() {
    fusion = null;
    if (fichiers.length === 0) {
        pointages = [];
        return;
    }
    if (fichiers.length === 1) {
        pointages = fichiers[0].pointages.slice().sort((a, b) => a.debut - b.debut);
        return;
    }
    const r = fusionnerFichiers(fichiers.map(f => f.pointages), principal,
                                { clientPause: CFG.clientPause, pauseCede: CFG.fusionPauseCede });
    pointages = r.pointages;
    fusion = { retires: r.retires, doublons: r.doublons };
}

function lireFichiers(liste, ajouter) {
    const tous = Array.from(liste);
    const jsonl = tous.filter(f => /\.jsonl$/i.test(f.name));
    const csv = tous.filter(f => !jsonl.includes(f) && (/\.(csv|txt)$/i.test(f.name) || f.type === 'text/csv'));
    if (csv.length === 0 && jsonl.length === 0) {
        toast('Choisissez un fichier .csv (pointeuse.csv), et si besoin pointeuse_suivi.jsonl.', true);
        return;
    }
    const lire = f => f.text().then(texte => ({ nom: f.name, texte }));
    Promise.all([Promise.all(csv.map(lire)), Promise.all(jsonl.map(lire))])
        .then(([entrees, entreesSuivi]) => chargerTextes(entrees, ajouter, entreesSuivi))
        .catch(() => toast('Lecture du fichier impossible.', true));
}

/** Toutes les notes de suivi lues (tous postes, notes en double ignorées). */
function notesSuivi() {
    return suiviFusion.notes;
}

function avecDonnees() {
    return pointages.length > 0 || suivis.length > 0;
}

/** Vue affichée : « suivi » seulement s'il y a des notes à montrer, toujours s'il n'y a qu'elles. */
function vueEffective() {
    if (suivis.length === 0) return 'temps';
    if (pointages.length === 0) return 'suivi';
    return reglages.vue;
}

function attribuerCouleurs() {
    const totaux = new Map();
    for (const p of pointages) {
        if (p.client === CFG.clientPause) continue;
        totaux.set(p.client, (totaux.get(p.client) || 0) + (p.fin - p.debut));
    }
    couleurs = new Map();
    Array.from(totaux.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, CFG.palette.length)
        .forEach(([client], i) => couleurs.set(client, CFG.palette[i]));
}

function couleurClient(client) {
    if (couleurs.has(client)) return couleurs.get(client);
    return CFG.couleurAutres;
}

/** Série du graphe : le client lui-même, ou « Autres » au-delà des 8 couleurs. */
function serieClient(client) {
    if (couleurs.has(client)) return client;
    return null;
}

/* ═══════════════════════════════════════
   PÉRIODE ET REGROUPEMENT
═══════════════════════════════════════ */
/** « Tout le fichier » : du premier au dernier jour qui a un pointage ou une note de suivi
 *  (une note écrite après le dernier pointage doit rester dans la plage, sinon son statut et sa priorité sont perdus). */
function bornesFichier() {
    let du = null;
    let au = null;
    const etendre = (debut, fin) => {
        if (du === null || debut < du) du = debut;
        if (au === null || fin > au) au = fin;
    };
    for (const p of pointages) {
        // Une ligne qui finit pile à minuit n'a rien sur le jour suivant.
        etendre(jourDe(p.debut), jourDe(new Date(p.fin.getTime() - 1)));
    }
    for (const n of notesSuivi()) {
        const jours = suiviJoursDePeriode(n.periode);
        etendre(jours.debut, jourDe(n.horodatage));
    }
    if (du === null) {
        const auj = jourDe(new Date());
        return { du: auj, au: auj };
    }
    return { du, au };
}

/** { du, au } : jours inclus. */
function periodeCourante() {
    const auj = jourDe(new Date());
    switch (reglages.periode) {
        case 'semaine':     return { du: lundiDe(auj), au: ajouterJours(lundiDe(auj), 6) };
        case 'semainePrec': return { du: ajouterJours(lundiDe(auj), -7), au: ajouterJours(lundiDe(auj), -1) };
        case 'moisPrec': {
            const debut = ajouterMois(auj, -1);
            return { du: debut, au: dernierJourDuMois(debut) };
        }
        case 'annee':       return { du: new Date(auj.getFullYear(), 0, 1), au: new Date(auj.getFullYear(), 11, 31) };
        case 'tout':        return bornesFichier();
        case 'perso': {
            const du = depuisCle(reglages.du);
            const au = depuisCle(reglages.au);
            if (du && au && du <= au) return { du, au };
            return bornesFichier();
        }
        default:            return { du: ajouterMois(auj, 0), au: dernierJourDuMois(auj) };
    }
}

function estMoisComplet(du, au) {
    return du.getDate() === 1 && au.getTime() === dernierJourDuMois(du).getTime();
}

/** ◀ ▶ : période précédente / suivante, de même longueur (ou mois entier). */
function decaler(sens) {
    const { du, au } = periodeCourante();
    let nouveauDu;
    let nouveauAu;
    if (estMoisComplet(du, au)) {
        const nbMois = (au.getFullYear() - du.getFullYear()) * 12 + au.getMonth() - du.getMonth() + 1;
        nouveauDu = ajouterMois(du, sens * nbMois);
        nouveauAu = dernierJourDuMois(ajouterMois(nouveauDu, nbMois - 1));
    } else {
        const n = nbJours(du, au);
        nouveauDu = ajouterJours(du, sens * n);
        nouveauAu = ajouterJours(au, sens * n);
    }
    reglages.periode = 'perso';
    reglages.du = cleJour(nouveauDu);
    reglages.au = cleJour(nouveauAu);
    toutAfficher();
}

function regroupementEffectif(du, au) {
    if (reglages.regroupement !== 'auto') return reglages.regroupement;
    const n = nbJours(du, au);
    if (n <= CFG.autoJourMax) return 'jour';
    if (n <= CFG.autoSemaineMax) return 'semaine';
    return 'mois';
}

function cleSeau(jour, mode) {
    if (mode === 'semaine') return cleJour(lundiDe(jour));
    if (mode === 'mois') return jour.getFullYear() + '-' + deux(jour.getMonth() + 1);
    return cleJour(jour);
}

/** Barres du graphe, de du à au : { cle, court, long, weekend }. */
function seaux(du, au, mode) {
    const liste = [];
    if (mode === 'jour') {
        for (let d = du; d <= au; d = ajouterJours(d, 1)) {
            liste.push({
                cle: cleJour(d),
                court: deux(d.getDate()) + '/' + deux(d.getMonth() + 1),
                long: JOURS_COURTS[d.getDay()] + ' ' + texteJour(d),
                weekend: d.getDay() === 0 || d.getDay() === 6,
            });
        }
    } else if (mode === 'semaine') {
        for (let d = lundiDe(du); d <= au; d = ajouterJours(d, 7)) {
            liste.push({
                cle: cleJour(d),
                court: 'S' + semaineIso(d),
                long: 'Semaine ' + semaineIso(d) + ' — du ' + texteJour(d) + ' au ' + texteJour(ajouterJours(d, 6)),
                weekend: false,
            });
        }
    } else {
        for (let d = ajouterMois(du, 0); d <= au; d = ajouterMois(d, 1)) {
            liste.push({
                cle: d.getFullYear() + '-' + deux(d.getMonth() + 1),
                court: MOIS_COURTS[d.getMonth()] + ' ' + String(d.getFullYear()).slice(2),
                long: MOIS_LONGS[d.getMonth()] + ' ' + d.getFullYear(),
                weekend: false,
            });
        }
    }
    return liste;
}

/** Morceaux d'un pointage jour par jour (une tâche qui passe minuit compte sur les deux jours). */
function morceauxParJour(p) {
    const morceaux = [];
    let d = p.debut;
    while (d < p.fin) {
        const minuit = ajouterJours(jourDe(d), 1);
        let f = p.fin;
        if (minuit < f) f = minuit;
        morceaux.push({ jour: jourDe(d), minutes: (f - d) / 60000 });
        d = f;
    }
    return morceaux;
}

/* ═══════════════════════════════════════
   CALCUL DU BILAN
═══════════════════════════════════════ */
function calculer() {
    const { du, au } = periodeCourante();
    const finPeriode = ajouterJours(au, 1);
    const mode = regroupementEffectif(du, au);
    const filtre = sansAccents(recherche.trim());
    const r = {
        du, au, mode,
        travail: 0, pause: 0, nbLignes: 0,
        joursPointes: new Set(),
        clientsPeriode: new Map(),   // tous les clients de la période (avant filtres) → minutes
        parSeau: new Map(),          // cle seau → Map(série → minutes)
        series: new Map(),           // série → minutes (filtres appliqués)
        arbre: new Map(),            // client → { minutes, projets: Map(projet → { minutes, taches: Map }) }
        lignes: [],                  // pointages à lister
    };

    for (const p of pointages) {
        if (p.fin <= du || p.debut >= finPeriode) continue;
        const morceaux = morceauxParJour(p).filter(m => m.jour >= du && m.jour < finPeriode);
        const minutes = morceaux.reduce((s, m) => s + m.minutes, 0);
        if (minutes <= 0) continue;
        r.nbLignes++;

        if (p.client === CFG.clientPause) {
            r.pause += minutes;
            if (reglages.pauses) r.lignes.push({ p, minutes });
            continue;
        }
        r.clientsPeriode.set(p.client, (r.clientsPeriode.get(p.client) || 0) + minutes);
        if (masques.has(p.client)) continue;
        if (filtre && !p.recherche.includes(filtre)) continue;

        r.travail += minutes;
        r.lignes.push({ p, minutes });
        const serie = serieClient(p.client);
        r.series.set(serie, (r.series.get(serie) || 0) + minutes);
        for (const m of morceaux) {
            r.joursPointes.add(cleJour(m.jour));
            const cle = cleSeau(m.jour, mode);
            if (!r.parSeau.has(cle)) r.parSeau.set(cle, new Map());
            const seau = r.parSeau.get(cle);
            seau.set(serie, (seau.get(serie) || 0) + m.minutes);
        }

        if (!r.arbre.has(p.client)) r.arbre.set(p.client, { minutes: 0, projets: new Map() });
        const noeudClient = r.arbre.get(p.client);
        noeudClient.minutes += minutes;
        if (!noeudClient.projets.has(p.projet)) noeudClient.projets.set(p.projet, { minutes: 0, taches: new Map() });
        const noeudProjet = noeudClient.projets.get(p.projet);
        noeudProjet.minutes += minutes;
        noeudProjet.taches.set(p.tache, (noeudProjet.taches.get(p.tache) || 0) + minutes);
    }
    return r;
}

/** Séries dans l'ordre des couleurs (fixe), « Autres » en dernier. */
function seriesOrdonnees(r) {
    const liste = [];
    for (const client of couleurs.keys()) {
        if (r.series.has(client)) liste.push(client);
    }
    if (r.series.has(null)) liste.push(null);
    return liste;
}

function nomSerie(serie) {
    if (serie === null) return 'Autres clients';
    return serie;
}

function couleurSerie(serie) {
    if (serie === null) return CFG.couleurAutres;
    return couleurClient(serie);
}

function trierParTemps(map, valeur) {
    return Array.from(map.entries()).sort((a, b) => valeur(b[1]) - valeur(a[1]));
}

/* ═══════════════════════════════════════
   GRAPHE (SVG)
═══════════════════════════════════════ */
function pasRond(brut) {
    const puissance = Math.pow(10, Math.floor(Math.log10(brut)));
    for (const k of [1, 2, 2.5, 5, 10]) {
        if (k * puissance >= brut) return k * puissance;
    }
    return 10 * puissance;
}

/** Rectangle dont seul le haut est arrondi (la base reste posée sur l'axe). */
function cheminBarre(x, y, l, h, rayon) {
    const r = Math.min(rayon, l / 2, h);
    return 'M' + x + ',' + (y + h) + 'V' + (y + r) + 'Q' + x + ',' + y + ' ' + (x + r) + ',' + y +
        'H' + (x + l - r) + 'Q' + (x + l) + ',' + y + ' ' + (x + l) + ',' + (y + r) + 'V' + (y + h) + 'Z';
}

function svgGraphe(r, liste, W) {
    const mg = CFG.marge;
    const H = CFG.hauteurGraphe;
    const largeurTrace = W - mg.gauche - mg.droite;
    const pas = largeurTrace / liste.length;
    const largeurBarre = Math.max(2, Math.min(CFG.largeurBarreMax, pas * 0.7));
    const series = seriesOrdonnees(r);

    let maxMin = 0;
    for (const s of liste) {
        const seau = r.parSeau.get(s.cle);
        if (!seau) continue;
        let total = 0;
        for (const v of seau.values()) total += v;
        if (total > maxMin) maxMin = total;
    }
    let pasHeures = pasRond(Math.max(maxMin / 60, 1) / CFG.graduationsVisees);
    if (pasHeures < 0.5) pasHeures = 0.5;
    const maxHeures = Math.max(pasHeures, Math.ceil(maxMin / 60 / pasHeures) * pasHeures);
    const y = minutes => mg.haut + H - (minutes / 60 / maxHeures) * H;

    const parties = [];
    parties.push(`<svg width="${W}" height="${mg.haut + H + mg.bas}" viewBox="0 0 ${W} ${mg.haut + H + mg.bas}" role="img" aria-label="Temps travaillé par ${r.mode}, empilé par client">`);
    parties.push(`<rect id="survol" x="0" y="${mg.haut}" width="${pas}" height="${H}" fill="#f2f9e5" visibility="hidden"/>`);

    // Week-ends grisés
    liste.forEach((s, i) => {
        if (s.weekend) parties.push(`<rect x="${mg.gauche + i * pas}" y="${mg.haut}" width="${pas}" height="${H}" fill="#f5f5f5"/>`);
    });

    // Graduations horizontales
    for (let h = 0; h <= maxHeures + 1e-9; h += pasHeures) {
        const yy = y(h * 60);
        let couleurTrait = '#eef0f2';
        if (h === 0) couleurTrait = '#c9d3c0';
        parties.push(`<line x1="${mg.gauche}" x2="${W - mg.droite}" y1="${yy}" y2="${yy}" stroke="${couleurTrait}" stroke-width="1"/>`);
        parties.push(`<text x="${mg.gauche - 6}" y="${yy + 4}" text-anchor="end" font-size="11" fill="#6b7280">${String(h).replace('.', ',')} h</text>`);
    }

    // Barres empilées
    liste.forEach((s, i) => {
        const seau = r.parSeau.get(s.cle);
        if (!seau) return;
        const x = mg.gauche + i * pas + (pas - largeurBarre) / 2;
        const presentes = series.filter(serie => (seau.get(serie) || 0) > 0);
        let cumul = 0;
        presentes.forEach((serie, k) => {
            const minutes = seau.get(serie);
            const haut = y(cumul + minutes);
            const bas = y(cumul);
            cumul += minutes;
            let hauteur = bas - haut;
            if (k > 0) hauteur -= CFG.ecartSegments;   // liseré blanc avec le segment du dessous
            if (hauteur <= 0) return;
            let rayon = 0;
            if (k === presentes.length - 1) rayon = CFG.rayonBarre;
            parties.push(`<path d="${cheminBarre(x, haut, largeurBarre, hauteur, rayon)}" fill="${couleurSerie(serie)}"/>`);
        });
        if (liste.length <= CFG.totauxSiBarresMax && cumul > 0) {
            parties.push(`<text x="${x + largeurBarre / 2}" y="${y(cumul) - 5}" text-anchor="middle" font-size="11" fill="#6b7280">${hmin(cumul)}</text>`);
        }
    });

    // Étiquettes de l'axe X (une sur k si elles se chevauchent)
    const k = Math.max(1, Math.ceil(CFG.pxParEtiquette / pas));
    liste.forEach((s, i) => {
        if (i % k !== 0) return;
        parties.push(`<text x="${mg.gauche + i * pas + pas / 2}" y="${mg.haut + H + 18}" text-anchor="middle" font-size="11" fill="#6b7280">${esc(s.court)}</text>`);
    });

    // Zone de survol (cible plus large que les barres)
    parties.push(`<rect id="zone-survol" x="${mg.gauche}" y="${mg.haut}" width="${largeurTrace}" height="${H}" fill="transparent"/>`);
    parties.push('</svg>');
    return parties.join('');
}

function brancherSurvol(r, liste, W) {
    const zone = $('#graphe');
    const bulle = $('#infobulle');
    const survol = zone.querySelector('#survol');
    const cible = zone.querySelector('#zone-survol');
    const pas = (W - CFG.marge.gauche - CFG.marge.droite) / liste.length;
    const series = seriesOrdonnees(r);

    cible.addEventListener('mousemove', ev => {
        const boite = zone.getBoundingClientRect();
        const x = ev.clientX - boite.left;
        const i = Math.floor((x - CFG.marge.gauche) / pas);
        if (i < 0 || i >= liste.length) return;
        const s = liste[i];
        survol.setAttribute('x', CFG.marge.gauche + i * pas);
        survol.setAttribute('visibility', 'visible');

        const seau = r.parSeau.get(s.cle) || new Map();
        let total = 0;
        const lignes = [];
        for (const serie of series) {
            const minutes = seau.get(serie) || 0;
            if (minutes <= 0) continue;
            total += minutes;
            lignes.push(`<div class="infobulle__ligne"><span class="pastille" style="background:${couleurSerie(serie)}"></span><span>${esc(nomSerie(serie))}</span><span>${hmin(minutes)}</span></div>`);
        }
        let corps = lignes.reverse().join('');   // même ordre que l'empilement (haut en premier)
        if (total === 0) corps = '<div class="infobulle__ligne"><span></span><span>Aucun pointage</span><span></span></div>';
        bulle.innerHTML = `<div class="infobulle__titre">${esc(s.long)}</div>${corps}` +
            `<div class="infobulle__total"><span>Total</span><span>${hmin(total)}</span></div>`;
        bulle.hidden = false;
        let gauche = x + 14;
        if (gauche + bulle.offsetWidth > boite.width) gauche = x - bulle.offsetWidth - 14;
        bulle.style.left = Math.max(0, gauche) + 'px';
        bulle.style.top = (CFG.marge.haut + 4) + 'px';
    });
    cible.addEventListener('mouseleave', () => {
        bulle.hidden = true;
        survol.setAttribute('visibility', 'hidden');
    });
}

function renderGraphe(r) {
    const zone = $('#graphe');
    if (!zone) return;
    const liste = seaux(r.du, r.au, r.mode);
    const W = Math.max(320, Math.floor(zone.clientWidth));
    zone.innerHTML = svgGraphe(r, liste, W) + '<div class="infobulle" id="infobulle" hidden></div>';
    brancherSurvol(r, liste, W);
}

/* ═══════════════════════════════════════
   RENDU — BILAN (gauche)
═══════════════════════════════════════ */
function nomOuVide(texte, vide) {
    if (texte) return esc(texte);
    return `<span class="sans-nom">${vide}</span>`;
}

function barrePart(minutes, total) {
    let pct = 0;
    if (total > 0) pct = (minutes / total) * 100;
    return `<span class="part"><i style="width:${pct.toFixed(1)}%"></i></span>${pct.toFixed(1).replace('.', ',')} %`;
}

function ligneRepartition(classe, libelle, minutes, total) {
    return `<tr class="${classe}"><td>${libelle}</td><td class="nb">${hmin(minutes)}</td>` +
        `<td class="nb">${heuresDecimales(minutes)}</td><td class="nb">${barrePart(minutes, total)}</td></tr>`;
}

function htmlRepartition(r) {
    if (r.arbre.size === 0) {
        return '<tr><td class="vide" colspan="4">Aucun temps travaillé sur cette période (ou tout est filtré).</td></tr>';
    }
    const rangs = [];
    const suiviParProjet = suiviDesProjets(r);
    for (const [client, noeud] of trierParTemps(r.arbre, n => n.minutes)) {
        const libelle = `<span class="nom-client"><span class="pastille" style="background:${couleurClient(client)}"></span>${nomOuVide(client, 'sans client')}</span>`;
        rangs.push(ligneRepartition('niv-client', libelle, noeud.minutes, r.travail));
        if (reglages.detail === 'client') continue;
        for (const [projet, np] of trierParTemps(noeud.projets, n => n.minutes)) {
            let libelleProjet = nomOuVide(projet, 'sans projet');
            if (suiviParProjet) libelleProjet += htmlSuiviCourt(suiviParProjet.get(suiviCleProjet(client, projet)));
            rangs.push(ligneRepartition('niv-projet', libelleProjet, np.minutes, r.travail));
            if (reglages.detail !== 'tache') continue;
            for (const [tache, minutes] of trierParTemps(np.taches, n => n)) {
                rangs.push(ligneRepartition('niv-tache', nomOuVide(tache, 'sans tâche'), minutes, r.travail));
            }
        }
    }
    rangs.push(`<tr class="total"><td>Total travaillé</td><td class="nb">${hmin(r.travail)}</td><td class="nb">${heuresDecimales(r.travail)}</td><td class="nb">100 %</td></tr>`);
    return rangs.join('');
}

function htmlLignes(r) {
    if (r.lignes.length === 0) {
        return '<tr><td class="vide" colspan="7">Aucune ligne.</td></tr>';
    }
    return r.lignes.slice(0, CFG.lignesAffichees).map(({ p, minutes }) => {
        let classe = '';
        if (p.client === CFG.clientPause) classe = ' class="pause"';
        let jourFin = '';
        if (cleJour(p.debut) !== cleJour(p.fin)) jourFin = ' (+1 j)';
        return `<tr${classe}><td>${JOURS_COURTS[p.debut.getDay()]} ${texteJour(p.debut)}</td>` +
            `<td>${texteHeure(p.debut)} → ${texteHeure(p.fin)}${jourFin}</td>` +
            `<td><span class="nom-client"><span class="pastille" style="background:${couleurClient(p.client)}"></span>${nomOuVide(p.client, '—')}</span></td>` +
            `<td>${nomOuVide(p.projet, '—')}</td><td>${nomOuVide(p.tache, '—')}</td>` +
            `<td class="texte">${esc(p.description)}</td><td class="nb">${hmin(minutes)}</td></tr>`;
    }).join('');
}

function htmlLegende(r) {
    return seriesOrdonnees(r).map(serie =>
        `<span class="legende__item"><span class="pastille" style="background:${couleurSerie(serie)}"></span>` +
        `<b>${esc(nomSerie(serie))}</b><span class="legende__temps">${hmin(r.series.get(serie))}</span></span>`
    ).join('');
}

function tuile(label, valeur, detail) {
    return `<div class="tuile"><div class="tuile__label">${label}</div><div class="tuile__valeur">${valeur}</div><div class="tuile__detail">${detail}</div></div>`;
}

function titrePeriode(r) {
    if (r.du.getTime() === r.au.getTime()) return 'Bilan du ' + texteJour(r.du);
    if (estMoisComplet(r.du, r.au) && r.du.getMonth() === r.au.getMonth()) {
        return 'Bilan de ' + MOIS_LONGS[r.du.getMonth()] + ' ' + r.du.getFullYear();
    }
    return 'Bilan du ' + texteJour(r.du) + ' au ' + texteJour(r.au);
}

function renderVide() {
    $('#bilan').innerHTML = `<div class="bilan-vide">
        <p class="bilan-vide__titre">Bilan de la Pointeuse</p>
        <p class="bilan-vide__presentation">Ouvrez le fichier <code>pointeuse.csv</code> de la <strong>Pointeuse</strong> pour voir
            le temps passé <strong>par client, projet et tâche</strong>, jour par jour, semaine par semaine ou mois par mois,
            et exporter la répartition pour la facturation.</p>
        <div class="bilan-vide__atouts">
            <span class="tag">Gratuit</span>
            <span class="tag">Aucune donnée envoyée sur nos serveurs</span>
            <span class="tag">Fonctionne dans votre navigateur</span>
        </div>
        <div class="bilan-vide__actions">
            <label class="btn btn--primary">Lire mon pointeuse.csv
                <input type="file" accept=".csv,text/csv,.jsonl" multiple hidden data-fichier></label>
            <button type="button" class="btn btn--sec" data-action="exemple">Voir un exemple</button>
        </div>
        <p class="bilan-vide__note">Le fichier se trouve dans le dossier data/ du programme Pointeuse (menu de l'icône → « Ouvrir le CSV »).
            Vous pouvez aussi le glisser sur cette page. Plusieurs fichiers (plusieurs postes) sont fusionnés :
            le PC principal l'emporte, on ne compte pas deux fois le même moment.</p>
    </div>`;
}

function renderBilan(r) {
    if (!avecDonnees()) {
        renderVide();
        return;
    }
    if (vueEffective() === 'suivi') {
        renderSuivi(r);
        return;
    }
    let moyenne = 0;
    if (r.joursPointes.size > 0) moyenne = r.travail / r.joursPointes.size;
    let noteLignes = r.lignes.length + ' ligne(s)';
    if (r.lignes.length > CFG.lignesAffichees) noteLignes = CFG.lignesAffichees + ' premières lignes sur ' + r.lignes.length;
    let filtreActif = '';
    if (masques.size > 0 || recherche.trim()) filtreActif = ' · filtres actifs';

    $('#bilan').innerHTML = `
        ${htmlOngletsVue()}
        ${htmlFusion()}
        <div class="bilan-entete">
            <h2>${titrePeriode(r)}</h2>
            <span class="bilan-entete__info">${pointages.length} pointage(s) lu(s)${filtreActif}</span>
        </div>
        <div class="tuiles">
            ${tuile('Travaillé', hmin(r.travail), heuresDecimales(r.travail) + ' h')}
            ${tuile('Pauses', hmin(r.pause), 'non comptées')}
            ${tuile('Jours pointés', r.joursPointes.size, 'sur ' + nbJours(r.du, r.au) + ' jour(s)')}
            ${tuile('Moyenne', hmin(moyenne), 'par jour pointé')}
        </div>
        <div class="carte">
            <div class="carte__entete"><h3>Temps travaillé par ${r.mode}</h3><span class="carte__note">Survolez une barre pour le détail</span></div>
            <div class="legende">${htmlLegende(r)}</div>
            <div class="graphe" id="graphe"></div>
        </div>
        <div class="carte">
            <div class="carte__entete"><h3>Répartition</h3><span class="carte__note">Heures décimales : pour la facturation</span></div>
            <div class="table-defile"><table class="table">
                <thead><tr><th>Client / projet / tâche</th><th class="nb">Durée</th><th class="nb">Heures</th><th class="nb">Part</th></tr></thead>
                <tbody>${htmlRepartition(r)}</tbody>
            </table></div>
        </div>
        <div class="carte">
            <div class="carte__entete"><h3>Lignes</h3><span class="carte__note">${noteLignes}</span></div>
            <div class="table-defile"><table class="table">
                <thead><tr><th>Date</th><th>Heures</th><th>Client</th><th>Projet</th><th>Tâche</th><th>Description</th><th class="nb">Durée</th></tr></thead>
                <tbody>${htmlLignes(r)}</tbody>
            </table></div>
        </div>`;
    renderGraphe(r);
}

/* ═══════════════════════════════════════
   RENDU — SUIVI DES PROJETS (CDC suivi_projets.md, étape 6)
   Un bloc par projet (statut actuel puis historique jour par jour), une page par projet à l'impression.
═══════════════════════════════════════ */
/** Plage de l'historique : la période du bilan, ou « depuis le … » jusqu'à la fin de la période. */
function plageSuivi(r) {
    let du = r.du;
    const depuis = depuisCle(reglages.depuis);
    if (reglages.historique === 'depuis' && depuis && depuis <= r.au) du = depuis;
    return { du, au: r.au };
}

function calculerSuivi(r) {
    const { du, au } = plageSuivi(r);
    const blocs = suiviBilan(notesSuivi(), pointages, du, au, {
        clientPause: CFG.clientPause,
        garder: client => !masques.has(client),
    });
    return { du, au, blocs };
}

/** Vue Temps : statut et priorité de chaque projet à la fin de la période (null sans journal de suivi). */
function suiviDesProjets(r) {
    if (suivis.length === 0) return null;
    const blocs = suiviBilan(notesSuivi(), pointages, r.du, r.au, { clientPause: CFG.clientPause });
    return new Map(blocs.map(b => [suiviCleProjet(b.client, b.projet), b]));
}

/** « Priorité 10 · terminé » à côté du nom du projet, s'il a une note. */
function htmlSuiviCourt(bloc) {
    if (!bloc || !bloc.etat) return '';
    return ` <span class="suivi-court"><span class="tag">Priorité ${bloc.priorite}</span> ${badgeStatut(bloc.statut)}</span>`;
}

/** Onglets « Temps | Suivi des projets » en tête du bilan, quand les deux vues ont des données. */
function htmlOngletsVue() {
    if (suivis.length === 0 || pointages.length === 0) return '';
    const vue = vueEffective();
    const onglet = (valeur, libelle) => {
        let classe = 'onglet';
        if (valeur === vue) classe += ' onglet--actif';
        return `<button type="button" class="${classe}" data-reglage="vue" data-valeur="${valeur}">${libelle}</button>`;
    };
    return `<nav class="onglets-vue sans-impression">${onglet('temps', 'Temps')}${onglet('suivi', 'Suivi des projets')}</nav>`;
}

function texteJourCourt(d) {
    return deux(d.getDate()) + '/' + deux(d.getMonth() + 1);
}

function libellePeriodeSuivi(periode) {
    const { debut, fin } = suiviJoursDePeriode(periode);
    if (suiviEstSemaine(periode)) {
        return 'semaine ' + Number(periode.slice(-2)) + ' (' + texteJourCourt(debut) + ' → ' + texteJourCourt(fin) + ')';
    }
    return texteJour(debut);
}

function badgeStatut(statut) {
    if (!statut) return '<span class="statut statut--aucun">sans note</span>';
    return `<span class="statut statut--${statut}">${esc(suiviLibelleStatut(statut))}</span>`;
}

function texteNote(texte) {
    if (!texte.trim()) return '<span class="sans-nom">(pas de texte)</span>';
    return esc(texte);
}

/** Notes d'une période : une seule en général, une par poste si deux postes ont écrit. */
function htmlNotes(notes) {
    const plusieursPostes = new Set(suivis.map(f => f.poste)).size > 1;
    return notes.map(n => {
        let poste = '';
        if (plusieursPostes) poste = `<b class="note__poste">${esc(n.poste)}</b> `;
        return `<div class="note">${poste}${badgeStatut(n.statut)} <span class="note__texte">${texteNote(n.texte)}</span></div>`;
    }).join('');
}

function htmlLignesSuivi(bloc) {
    return bloc.lignes.map(l => {
        let temps = '—';
        if (l.minutes > 0) temps = hmin(l.minutes);
        if (l.type === 'semaine') {
            const ecrite = l.notes[l.notes.length - 1].horodatage;
            return `<tr class="suivi-semaine"><td colspan="3">
                <div class="suivi-semaine__titre">${esc(libellePeriodeSuivi(l.periode))} — note du ${texteJourCourt(ecrite)}
                    <span class="suivi-semaine__temps">${temps}</span></div>
                ${htmlNotes(l.notes)}</td></tr>`;
        }
        return `<tr><td>${texteJour(l.jour)}</td><td class="nb">${temps}</td><td class="texte">${htmlNotes(l.notes)}</td></tr>`;
    }).join('');
}

function htmlBlocSuivi(bloc) {
    let etat = '<p class="suivi-etat sans-nom">Aucune note pour ce projet.</p>';
    if (bloc.etat) {
        etat = `<p class="suivi-etat"><b>Statut en cours (${esc(libellePeriodeSuivi(bloc.etat.periode))}) :</b>
            ${badgeStatut(bloc.statut)} <span class="note__texte">${texteNote(bloc.etat.texte)}</span></p>`;
    }
    let lignes = '<p class="cfg-note">Ni temps ni note sur la plage.</p>';
    if (bloc.lignes.length > 0) {
        lignes = `<div class="table-defile"><table class="table suivi-table">
            <thead><tr><th>Date</th><th class="nb">Temps</th><th>Note</th></tr></thead>
            <tbody>${htmlLignesSuivi(bloc)}</tbody></table></div>`;
    }
    return `<section class="carte suivi-projet">
        <div class="carte__entete">
            <h3><span class="nom-client"><span class="pastille" style="background:${couleurClient(bloc.client)}"></span>${nomOuVide(bloc.client, 'sans client')}</span>
                — ${nomOuVide(bloc.projet, 'sans projet')}</h3>
            <span class="suivi-projet__infos"><span class="tag">Priorité ${bloc.priorite}</span> ${badgeStatut(bloc.statut)}
                <span class="carte__note">${hmin(bloc.minutes)} sur la plage</span></span>
        </div>
        ${etat}
        ${lignes}
    </section>`;
}

function renderSuivi(r) {
    const s = calculerSuivi(r);
    let titre = 'Suivi des projets du ' + texteJour(s.du) + ' au ' + texteJour(s.au);
    if (s.du.getTime() === s.au.getTime()) titre = 'Suivi des projets du ' + texteJour(s.du);
    let filtreActif = '';
    if (masques.size > 0) filtreActif = ' · filtres actifs';
    let corps = s.blocs.map(htmlBlocSuivi).join('');
    if (s.blocs.length === 0) {
        corps = '<div class="carte"><p class="cfg-note">Aucun projet avec du temps ou une note sur cette plage.</p></div>';
    }
    $('#bilan').innerHTML = `
        ${htmlOngletsVue()}
        ${htmlFusion()}
        <div class="bilan-entete">
            <h2>${titre}</h2>
            <span class="bilan-entete__info">${s.blocs.length} projet(s)${filtreActif}
                <button type="button" class="btn btn--sec sans-impression" data-action="imprimer"
                    title="Une page par projet">Imprimer</button></span>
        </div>
        ${corps}`;
}

/* ═══════════════════════════════════════
   RENDU — RÉGLAGES (droite)
═══════════════════════════════════════ */
function segmente(nom, options, courant) {
    return '<div class="segmente">' + options.map(([valeur, libelle]) => {
        let classe = '';
        if (valeur === courant) classe = ' class="actif"';
        return `<button type="button"${classe} data-reglage="${nom}" data-valeur="${valeur}">${libelle}</button>`;
    }).join('') + '</div>';
}

function htmlClients(r) {
    if (r.clientsPeriode.size === 0) return '<p class="cfg-note">Aucun client sur cette période.</p>';
    return '<div class="clients">' + trierParTemps(r.clientsPeriode, v => v).map(([client, minutes]) => {
        let coche = ' checked';
        if (masques.has(client)) coche = '';
        return `<label class="client-filtre"><input type="checkbox" data-client="${esc(client)}"${coche}>` +
            `<span class="pastille" style="background:${couleurClient(client)}"></span>` +
            `<span class="nom">${nomOuVide(client, 'sans client')}</span><span class="temps">${hmin(minutes)}</span></label>`;
    }).join('') + '</div>';
}

/** Minutes de travail retirées à chaque fichier par la fusion. */
function minutesRetirees() {
    const parFichier = fichiers.map(() => 0);
    if (!fusion) return parFichier;
    for (const x of fusion.retires) parFichier[x.fichier] += (x.ligne.fin - x.ligne.debut) / 60000;
    return parFichier;
}

/** Bandeau : temps retirés du (des) PC secondaire(s), avec le détail (CDC fusion.md). */
function htmlFusion() {
    if (!fusion || fusion.retires.length === 0) return '';
    const parFichier = minutesRetirees();
    const total = parFichier.reduce((a, b) => a + b, 0);
    const secondaires = [];
    parFichier.forEach((minutes, i) => {
        if (minutes > 0) secondaires.push(esc(libelleFichier(fichiers[i])));
    });
    let colonneFichier = '';
    if (fichiers.length > 2) colonneFichier = '<th>Fichier</th>';
    const rangs = fusion.retires.slice(0, CFG.lignesAffichees).map(x => {
        const p = x.ligne;
        let celluleFichier = '';
        if (fichiers.length > 2) celluleFichier = `<td>${esc(libelleFichier(fichiers[x.fichier]))}</td>`;
        return `<tr><td>${texteJour(p.debut)}</td><td>${texteHeure(p.debut)} → ${texteHeure(p.fin)}</td>` +
            `${celluleFichier}<td>${nomOuVide(fusionLibelle(p), 'sans client')}</td>` +
            `<td class="nb">${hmin((p.fin - p.debut) / 60000)}</td><td>${esc(x.recouvertPar)}</td></tr>`;
    }).join('');
    let suite = '';
    if (fusion.retires.length > CFG.lignesAffichees) {
        suite = `<p class="cfg-note">${CFG.lignesAffichees} premières plages sur ${fusion.retires.length} : le rapport les contient toutes.</p>`;
    }
    return `<div class="al-warn fusion" role="alert">
        <details>
            <summary><b>⚠ Temps retirés du PC secondaire (${secondaires.join(', ')}) : ${hmin(total)}</b>
                — ${fusion.retires.length} plage(s) déjà pointée(s) sur le PC principal (${esc(libelleFichier(fichiers[principal]))}).
                On ne peut pas être à deux endroits à la fois.</summary>
            <div class="table-defile"><table class="table">
                <thead><tr><th>Date</th><th>Heures</th>${colonneFichier}<th>Retiré</th><th class="nb">Durée</th><th>Recouvert par</th></tr></thead>
                <tbody>${rangs}</tbody>
            </table></div>
            ${suite}
        </details>
        <button type="button" class="btn btn--sec" data-action="rapport">Exporter le rapport</button>
    </div>`;
}

function htmlFichiers() {
    let note = '';
    if (noteDonnees) note = `<div class="al-warn fichier" role="alert">⚠ ${esc(noteDonnees)}</div>`;
    return note + htmlFichiersLus();
}

function htmlFichiersLus() {
    const plusieurs = fichiers.length > 1;
    const retirees = minutesRetirees();
    return fichiers.map((f, i) => {
        const erreurs = listeErreurs(f.erreurs);
        let fusionTexte = '';
        if (retirees[i] > 0) fusionTexte += ` · <span class="fichier__retire">${hmin(retirees[i])} retirées</span>`;
        if (fusion && fusion.doublons[i] > 0) fusionTexte += ` · ${fusion.doublons[i]} ligne(s) déjà dans le principal`;
        let choix = '';
        if (plusieurs) {
            let coche = '';
            if (i === principal) coche = ' checked';
            choix = `<label class="fichier__principal"><input type="radio" name="principal" value="${i}"${coche}> PC principal</label>`;
        }
        let nom = `<b>${esc(f.nom)}</b>`;
        if (f.poste) nom = `<b>${esc(f.poste)}</b> (${esc(f.nom)})`;
        return `<div class="fichier">${nom} — ${f.lignes} ligne(s)${fusionTexte}${choix}${erreurs}</div>`;
    }).join('') + suivis.map((f, i) => {
        let doublons = '';
        if (suiviFusion.doublons[i] > 0) doublons = ` · ${suiviFusion.doublons[i]} déjà lue(s) dans un autre fichier`;
        // Lignes abîmées : mêmes messages que la Pointeuse (fenêtre « Suivi »).
        return `<div class="fichier"><b>${esc(f.nom)}</b> — poste « ${esc(f.poste)} » — ` +
            `${f.notes.length} note(s) de suivi${doublons}${listeErreurs(f.avertissements)}</div>`;
    }).join('');
}

function listeErreurs(erreurs) {
    if (erreurs.length === 0) return '';
    const visibles = erreurs.slice(0, CFG.erreursAffichees).map(e => `<li>${esc(e)}</li>`).join('');
    let suite = '';
    if (erreurs.length > CFG.erreursAffichees) suite = `<li>… et ${erreurs.length - CFG.erreursAffichees} autre(s)</li>`;
    return `<ul class="fichier__erreurs">${visibles}${suite}</ul>`;
}

function htmlActionsFichiers() {
    let fusionner = '';
    if (fichiers.length > 1) {
        fusionner = `<button type="button" class="btn-lien" data-action="csv-fusion">Télécharger le CSV fusionné</button>
            <p class="cfg-note">Fichiers d'origine non modifiés. Pour garder la fusion : fermer la Pointeuse,
                remplacer <code>pointeuse.csv</code> par <code>${CFG.nomFusion}</code>, relancer.</p>`;
    }
    return `<div class="fichiers__actions">
            <label class="btn-lien" title="pointeuse.csv (et pointeuse_suivi.jsonl) d'un autre poste : fusionné avec le PC principal">＋ Ajouter un autre PC
                <input type="file" accept=".csv,text/csv,.jsonl" multiple hidden data-ajout></label>
            ${fusionner}
        </div>`;
}

function noteFichiers() {
    if (window.POINTEUSE_CSV) return 'Ouvert depuis la Pointeuse : cliquez à nouveau sur « Bilan » dans son menu pour actualiser.';
    return 'Pointages non conservés : relisez le fichier à la prochaine visite.';
}

function renderConfig(r) {
    const config = $('#config');
    if (!avecDonnees()) {
        config.innerHTML = `<section class="cfg-section"><h2>Mode d'emploi</h2>
            <p class="cfg-note">1. Dans la Pointeuse : menu de l'icône → « Ouvrir le CSV » pour retrouver le fichier.</p>
            <p class="cfg-note">2. Ici : « Lire un CSV », ou glissez le fichier sur la page.
                Ajoutez <code>pointeuse_suivi.jsonl</code> pour la page « Suivi » des projets.</p>
            <p class="cfg-note">Le fichier est lu par votre navigateur : il n'est ni envoyé, ni conservé.</p></section>`;
        return;
    }
    const options = PERIODES.map(([valeur, libelle]) => {
        let choisi = '';
        if (valeur === reglages.periode) choisi = ' selected';
        return `<option value="${valeur}"${choisi}>${libelle}</option>`;
    }).join('');
    let pausesCochees = '';
    if (reglages.pauses) pausesCochees = ' checked';
    const suivi = vueEffective() === 'suivi';

    let sectionsVue = '';
    if (suivi) {
        let depuis = '';
        if (reglages.historique === 'depuis') {
            let valeur = cleJour(r.du);
            if (depuisCle(reglages.depuis)) valeur = reglages.depuis;
            depuis = `<label class="champ" style="margin-top:8px"><span class="champ__label">Depuis le</span>
                <input type="date" id="depuis" value="${valeur}" max="${cleJour(r.au)}"></label>`;
        }
        sectionsVue = `<section class="cfg-section"><h2>Historique</h2>
            ${segmente('historique', [['periode', 'Période du bilan'], ['depuis', 'Depuis le…']], reglages.historique)}
            ${depuis}
            <p class="cfg-note" style="margin-top:8px">Projets avec du temps ou une note sur la plage, par priorité
                (la plus urgente d'abord). Statut : dernière note écrite avant la fin de la période.</p>
        </section>`;
    } else {
        sectionsVue = `<section class="cfg-section"><h2>Graphe par</h2>
            ${segmente('regroupement', [['auto', 'Auto'], ['jour', 'Jour'], ['semaine', 'Semaine'], ['mois', 'Mois']], reglages.regroupement)}
        </section>
        <section class="cfg-section"><h2>Répartition</h2>
            ${segmente('detail', [['client', 'Client'], ['projet', 'Projet'], ['tache', 'Tâche']], reglages.detail)}
        </section>`;
    }
    let recherchePauses = '';
    if (!suivi) {
        recherchePauses = `<label class="champ"><input type="search" id="recherche" placeholder="Rechercher (projet, tâche, description…)" value="${esc(recherche)}"></label>`;
    }
    let casePauses = '';
    if (!suivi) {
        casePauses = `<label class="case" style="margin-top:10px"><input type="checkbox" id="pauses"${pausesCochees}> Afficher les pauses dans les lignes</label>`;
    }

    config.innerHTML = `
        <section class="cfg-section"><h2>Période</h2>
            <div class="cfg-ligne">
                <button type="button" class="btn-nav" data-action="precedent" title="Période précédente">◀</button>
                <label class="champ"><select id="periode" aria-label="Période">${options}</select></label>
                <button type="button" class="btn-nav" data-action="suivant" title="Période suivante">▶</button>
            </div>
            <div class="cfg-ligne">
                <label class="champ"><span class="champ__label">Du</span><input type="date" id="du" value="${cleJour(r.du)}"></label>
                <label class="champ"><span class="champ__label">Au</span><input type="date" id="au" value="${cleJour(r.au)}"></label>
            </div>
        </section>
        ${sectionsVue}
        <section class="cfg-section"><h2>Filtres</h2>
            ${recherchePauses}
            <h2 style="margin-top:4px">Clients <span><button type="button" class="btn-lien" data-action="tous">Tous</button> · <button type="button" class="btn-lien" data-action="aucun">Aucun</button></span></h2>
            ${htmlClients(r)}
            ${casePauses}
        </section>
        <section class="cfg-section"><h2>Fichiers lus <button type="button" class="btn-lien" data-action="fermer">Fermer</button></h2>
            ${htmlFichiers()}
            ${htmlActionsFichiers()}
            <p class="cfg-note">${noteFichiers()}</p>
        </section>`;
}

function toutAfficher() {
    resultat = calculer();
    renderBilan(resultat);
    renderConfig(resultat);
    $('#btn-exporter').disabled = pointages.length === 0 || vueEffective() === 'suivi';
    sauverReglages();
}

/** Recherche : on ne reconstruit pas les réglages (garde le focus dans le champ). */
function afficherBilanSeul() {
    resultat = calculer();
    renderBilan(resultat);
}

/* ═══════════════════════════════════════
   EXPORT CSV
═══════════════════════════════════════ */
function champCsv(v) {
    const s = String(v);
    if (/[;"\r\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
    return s;
}

function exporter() {
    if (!resultat || pointages.length === 0) return;
    const r = resultat;
    const rangs = [['client', 'projet', 'tache', 'duree_min', 'heures']];
    for (const [client, noeud] of trierParTemps(r.arbre, n => n.minutes)) {
        if (reglages.detail === 'client') {
            rangs.push([client, '', '', Math.round(noeud.minutes), heuresDecimales(noeud.minutes)]);
            continue;
        }
        for (const [projet, np] of trierParTemps(noeud.projets, n => n.minutes)) {
            if (reglages.detail === 'projet') {
                rangs.push([client, projet, '', Math.round(np.minutes), heuresDecimales(np.minutes)]);
                continue;
            }
            for (const [tache, minutes] of trierParTemps(np.taches, n => n)) {
                rangs.push([client, projet, tache, Math.round(minutes), heuresDecimales(minutes)]);
            }
        }
    }
    rangs.push(['Total', '', '', Math.round(r.travail), heuresDecimales(r.travail)]);
    const texte = '﻿' + rangs.map(rang => rang.map(champCsv).join(';')).join('\r\n') + '\r\n';
    telecharger(texte, 'pointeuse_bilan_' + cleJour(r.du) + '_' + cleJour(r.au) + '.csv', 'text/csv;charset=utf-8');
}

/** Ligne au format exact de pointeuse.csv. */
function texteDateCsv(d) {
    return d.getFullYear() + '-' + deux(d.getMonth() + 1) + '-' + deux(d.getDate()) + ' ' + texteHeure(d);
}

function rangPointage(p) {
    return [texteDateCsv(p.debut), texteDateCsv(p.fin), p.client, p.projet, p.tache, p.description,
            Math.round((p.fin - p.debut) / 60000)];
}

/** UTF-8 avec BOM, « ; », fins de ligne CRLF : comme la Pointeuse. */
function texteCsv(rangs) {
    return '\uFEFF' + rangs.map(rang => rang.map(champCsv).join(';')).join('\r\n') + '\r\n';
}

function exporterFusion() {
    if (fichiers.length < 2) return;
    const rangs = [CFG.colonnesCsv].concat(pointages.map(rangPointage));
    telecharger(texteCsv(rangs), CFG.nomFusion, 'text/csv;charset=utf-8');
}

/** fusion_rapport.csv : colonnes du CSV + fichier d'où le temps est retiré + ce qui le recouvre. */
function exporterRapport() {
    if (!fusion) return;
    const rangs = [CFG.colonnesCsv.concat(['fichier', 'recouvert_par'])];
    for (const x of fusion.retires) {
        rangs.push(rangPointage(x.ligne).concat([libelleFichier(fichiers[x.fichier]), x.recouvertPar]));
    }
    telecharger(texteCsv(rangs), CFG.nomRapport, 'text/csv;charset=utf-8');
}

/* ═══════════════════════════════════════
   EXEMPLE (pointages fictifs, noms génériques)
═══════════════════════════════════════ */
function hasard(graine) {
    let s = graine;
    return () => {
        s = (s * 1664525 + 1013904223) % 4294967296;
        return s / 4294967296;
    };
}

function csvExemple() {
    const clients = [
        ['exemple-client', ['carte-principale', 'banc-de-test'], ['schéma', 'routage', 'essais', 'revue']],
        ['client-b', ['capteur-ble', 'firmware'], ['développement', 'mise au point', 'documentation']],
        ['client-c', ['audit-cem'], ['mesures', 'rapport']],
        ['Interne', ['commercial', 'administratif'], ['devis', 'salon', '']],
    ];
    const poids = [0.42, 0.28, 0.12, 0.18];
    const alea = hasard(20261117);
    const choisir = liste => liste[Math.floor(alea() * liste.length)];
    const choisirClient = () => {
        let x = alea();
        for (let i = 0; i < poids.length; i++) {
            x -= poids[i];
            if (x <= 0) return clients[i];
        }
        return clients[0];
    };
    const ligne = (debut, fin, client, projet, tache, description) => {
        const d = debut.getFullYear() + '-' + deux(debut.getMonth() + 1) + '-' + deux(debut.getDate()) + ' ' + texteHeure(debut);
        const f = fin.getFullYear() + '-' + deux(fin.getMonth() + 1) + '-' + deux(fin.getDate()) + ' ' + texteHeure(fin);
        return [d, f, client, projet, tache, description, Math.round((fin - debut) / 60000)].map(champCsv).join(';');
    };

    const rangs = ['date_in;date_out;client;projet;tache;description;duree_min'];
    const fin = jourDe(new Date());
    for (let jour = ajouterJours(lundiDe(fin), -7 * (CFG.exempleSemaines - 1)); jour <= fin; jour = ajouterJours(jour, 1)) {
        if (jour.getDay() === 0 || jour.getDay() === 6) continue;
        for (const [debutDemi, finDemi] of [[8 * 60 + 15 + Math.floor(alea() * 45), 12 * 60 + Math.floor(alea() * 30)],
                                             [13 * 60 + 15 + Math.floor(alea() * 30), 17 * 60 + Math.floor(alea() * 75)]]) {
            let t = debutDemi;
            while (t < finDemi - 10) {
                const duree = Math.min(finDemi - t, 20 + Math.floor(alea() * 140));
                const [client, projets, taches] = choisirClient();
                const debut = new Date(jour.getFullYear(), jour.getMonth(), jour.getDate(), 0, t);
                const finLigne = new Date(jour.getFullYear(), jour.getMonth(), jour.getDate(), 0, t + duree);
                let description = '';
                if (alea() < 0.25) description = 'appel ; suivi';
                rangs.push(ligne(debut, finLigne, client, choisir(projets), choisir(taches), description));
                t += duree;
            }
            if (finDemi < 13 * 60) {
                const debut = new Date(jour.getFullYear(), jour.getMonth(), jour.getDate(), 0, finDemi);
                const reprise = new Date(jour.getFullYear(), jour.getMonth(), jour.getDate(), 13, 15);
                rangs.push(ligne(debut, reprise, CFG.clientPause, '', '', ''));
            }
        }
    }
    return rangs.join('\r\n');
}

/* ═══════════════════════════════════════
   RÉGLAGES MÉMORISÉS (confort, jamais les pointages)
═══════════════════════════════════════ */
function sauverReglages() {
    try {
        localStorage.setItem(CFG.cleReglages, JSON.stringify(reglages));
    } catch (e) {
        /* navigation privée ou stockage bloqué : sans conséquence */
    }
}

function chargerReglages() {
    try {
        const brut = JSON.parse(localStorage.getItem(CFG.cleReglages) || 'null');
        if (!brut || typeof brut !== 'object') return;
        if (PERIODES.some(([v]) => v === brut.periode)) reglages.periode = brut.periode;
        if (['auto', 'jour', 'semaine', 'mois'].includes(brut.regroupement)) reglages.regroupement = brut.regroupement;
        if (['client', 'projet', 'tache'].includes(brut.detail)) reglages.detail = brut.detail;
        reglages.pauses = brut.pauses === true;
        if (depuisCle(brut.du)) reglages.du = brut.du;
        if (depuisCle(brut.au)) reglages.au = brut.au;
        if (['temps', 'suivi'].includes(brut.vue)) reglages.vue = brut.vue;
        if (['periode', 'depuis'].includes(brut.historique)) reglages.historique = brut.historique;
        if (depuisCle(brut.depuis)) reglages.depuis = brut.depuis;
    } catch (e) {
        /* réglages illisibles : valeurs par défaut */
    }
}

/* ═══════════════════════════════════════
   ÉVÉNEMENTS
═══════════════════════════════════════ */
function surAction(action) {
    if (action === 'exemple') {
        chargerTextes([{ nom: 'exemple (pointages fictifs)', texte: csvExemple() }], false);
        return;
    }
    if (action === 'rapport') exporterRapport();
    if (action === 'imprimer') window.print();
    if (action === 'csv-fusion') exporterFusion();
    if (action === 'precedent') decaler(-1);
    if (action === 'suivant') decaler(1);
    if (action === 'tous') {
        masques.clear();
        toutAfficher();
    }
    if (action === 'aucun') {
        for (const client of resultat.clientsPeriode.keys()) masques.add(client);
        toutAfficher();
    }
    if (action === 'fermer') {
        pointages = [];
        fichiers = [];
        principal = 0;
        fusion = null;
        suivis = [];
        suiviFusion = { notes: [], doublons: [] };
        masques.clear();
        recherche = '';
        toutAfficher();
    }
}

function brancher() {
    document.addEventListener('click', ev => {
        const bouton = ev.target.closest('[data-action]');
        if (bouton) {
            surAction(bouton.dataset.action);
            return;
        }
        const reglage = ev.target.closest('[data-reglage]');
        if (reglage) {
            reglages[reglage.dataset.reglage] = reglage.dataset.valeur;
            toutAfficher();
        }
    });

    document.addEventListener('change', ev => {
        const cible = ev.target;
        if (cible.id === 'fichier' || cible.hasAttribute('data-fichier')) {
            lireFichiers(cible.files, false);
            cible.value = '';
        } else if (cible.hasAttribute('data-ajout')) {
            lireFichiers(cible.files, true);
            cible.value = '';
        } else if (cible.name === 'principal') {
            principal = Number(cible.value);
            fusionnerFichiersCharges();
            toutAfficher();
        } else if (cible.id === 'periode') {
            reglages.periode = cible.value;
            if (cible.value === 'perso') {
                const { du, au } = periodeCourante();
                reglages.du = cleJour(du);
                reglages.au = cleJour(au);
            }
            toutAfficher();
        } else if (cible.id === 'du' || cible.id === 'au') {
            if (!depuisCle(cible.value)) return;
            const { du, au } = periodeCourante();
            reglages.du = cleJour(du);
            reglages.au = cleJour(au);
            reglages[cible.id] = cible.value;
            if (depuisCle(reglages.du) > depuisCle(reglages.au)) {
                // Bornes croisées : l'autre borne suit.
                if (cible.id === 'du') reglages.au = reglages.du;
                else reglages.du = reglages.au;
            }
            reglages.periode = 'perso';
            toutAfficher();
        } else if (cible.dataset.client !== undefined) {
            if (cible.checked) masques.delete(cible.dataset.client);
            else masques.add(cible.dataset.client);
            toutAfficher();
        } else if (cible.id === 'depuis') {
            if (!depuisCle(cible.value)) return;
            reglages.depuis = cible.value;
            toutAfficher();
        } else if (cible.id === 'pauses') {
            reglages.pauses = cible.checked;
            toutAfficher();
        }
    });

    document.addEventListener('input', ev => {
        if (ev.target.id !== 'recherche') return;
        recherche = ev.target.value;
        afficherBilanSeul();
    });

    $('#btn-exporter').addEventListener('click', exporter);

    // Glisser-déposer sur toute la page
    let profondeur = 0;
    const avecFichiers = ev => ev.dataTransfer && Array.from(ev.dataTransfer.types).includes('Files');
    document.addEventListener('dragenter', ev => {
        if (!avecFichiers(ev)) return;
        ev.preventDefault();
        profondeur++;
        $('#depot').hidden = false;
    });
    document.addEventListener('dragover', ev => {
        if (avecFichiers(ev)) ev.preventDefault();
    });
    document.addEventListener('dragleave', ev => {
        if (!avecFichiers(ev)) return;
        profondeur--;
        if (profondeur <= 0) {
            profondeur = 0;
            $('#depot').hidden = true;
        }
    });
    document.addEventListener('drop', ev => {
        if (!avecFichiers(ev)) return;
        ev.preventDefault();
        profondeur = 0;
        $('#depot').hidden = true;
        lireFichiers(ev.dataTransfer.files, false);
    });

    let attente = null;
    window.addEventListener('resize', () => {
        clearTimeout(attente);
        attente = setTimeout(() => { if (resultat) renderGraphe(resultat); }, 150);
    });
}

chargerReglages();
brancher();
toutAfficher();

/* Ouverture depuis la Pointeuse (menu « Bilan ») : la page locale charge d'abord
   pointeuse_donnees_tmp.js, qui définit window.POINTEUSE_CSV = { version, nom, texte, suivi, postes, note }
   (suivi : { nom, texte } du pointeuse_suivi.jsonl, ou null ; postes : [{ poste, csv, suivi }] des autres
   PC lus dans le dossier externe, csv et suivi valant { nom, texte } ou null ; note : texte à signaler).
   Ce poste s'appelle « local » et reste le PC principal (ADR 005). */
const DONNEES_LOCALES_VERSION = 3;

/** { csv, suivi } : entrées de chargerTextes pour les données transmises par la Pointeuse. */
function entreesDonneesLocales(donnees) {
    const csv = [{ nom: String(donnees.nom || 'pointeuse.csv'), texte: donnees.texte, poste: SUIVI.posteLocal }];
    const suivi = [];
    const ajouterSuivi = (fichier, poste) => {
        if (fichier && typeof fichier.texte === 'string') {
            suivi.push({ nom: String(fichier.nom || 'pointeuse_suivi.jsonl'), texte: fichier.texte, poste });
        }
    };
    ajouterSuivi(donnees.suivi, SUIVI.posteLocal);
    for (const autre of donnees.postes || []) {
        const poste = String(autre.poste);
        if (autre.csv && typeof autre.csv.texte === 'string') {
            csv.push({ nom: String(autre.csv.nom || 'pointeuse.csv'), texte: autre.csv.texte, poste });
        }
        ajouterSuivi(autre.suivi, poste);
    }
    return { csv, suivi };
}

const donneesLocales = window.POINTEUSE_CSV;
if (donneesLocales && donneesLocales.version === DONNEES_LOCALES_VERSION && typeof donneesLocales.texte === 'string') {
    const entrees = entreesDonneesLocales(donneesLocales);
    chargerTextes(entrees.csv, false, entrees.suivi);
    if (donneesLocales.note) {
        noteDonnees = String(donneesLocales.note);
        toutAfficher();
    }
} else if (donneesLocales) {
    toast('Données de la Pointeuse dans un format inconnu : lisez le CSV avec « Lire un CSV ».', true);
}

// Capture de contrôle : ?exemple charge l'exemple directement.
if (new URLSearchParams(location.search).has('exemple')) surAction('exemple');

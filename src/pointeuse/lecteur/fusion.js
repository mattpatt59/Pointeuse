/* ═══════════════════════════════════════
   FUSION DE PLUSIEURS pointeuse.csv (PC principal + PC secondaires) — CDC docs/cdc/fusion.md
   On compte le temps d'attention : on ne peut pas être à deux endroits à la fois.
   Les lignes du principal sont gardées ; celles d'un secondaire sont découpées là où elles
   chevauchent le principal, le reste comble les trous du principal.
   Fonctions pures, sans page web : testées par tests/test_fusion.py (moteur JS de Qt).
   Licence MIT (voir LICENSE du dépôt pointeuse).
═══════════════════════════════════════ */
'use strict';

/** Clé d'une ligne : deux lignes de même clé sont la même ligne (fichier refusionné). */
function fusionCle(p) {
    return [p.debut.getTime(), p.fin.getTime(), p.client, p.projet, p.tache, p.description].join('\u0001');
}

/** « client / projet / tâche », sans les parties vides. */
function fusionLibelle(p) {
    return [p.client, p.projet, p.tache].filter(t => t).join(' / ');
}

/** Copie d'une ligne avec d'autres heures (les autres champs sont gardés). */
function fusionCopie(p, debut, fin) {
    return Object.assign({}, p, { debut, fin });
}

function fusionChevauche(a, b) {
    return a.debut < b.fin && a.fin > b.debut;
}

/** Parties de [debut, fin] qu'aucune des plages ne couvre → [{ debut, fin }]. */
function fusionSoustraire(debut, fin, plages) {
    let morceaux = [{ debut, fin }];
    for (const o of plages) {
        const suivants = [];
        for (const m of morceaux) {
            if (o.fin <= m.debut || o.debut >= m.fin) {
                suivants.push(m);
                continue;
            }
            if (m.debut < o.debut) suivants.push({ debut: m.debut, fin: o.debut });
            if (o.fin < m.fin) suivants.push({ debut: o.fin, fin: m.fin });
        }
        morceaux = suivants;
    }
    return morceaux;
}

/**
 * Fusionne un fichier secondaire dans le principal.
 *   options.clientPause : nom réservé des lignes de pause ('PAUSE')
 *   options.pauseCede   : true  → une pause du principal laisse la place au travail du secondaire
 *                                  (la pause est raccourcie d'autant) ;
 *                         false → règle stricte, la pause du principal efface aussi ce travail.
 * → { pointages, retires: [{ ligne, recouvertPar }], doublons }
 *   retires : morceaux de TRAVAIL du secondaire retirés (une pause retirée n'est pas signalée).
 *   doublons : lignes du secondaire identiques à une ligne du principal (fichier refusionné).
 */
function fusionner(principal, secondaire, options) {
    const estPause = p => p.client === options.clientPause;
    const clesPrincipal = new Set(principal.map(fusionCle));
    const travailPrincipal = principal.filter(p => !estPause(p));
    const gardes = [];
    const travailSecondaire = [];   // travail du secondaire gardé : raccourcit les pauses du principal
    const retires = [];
    let doublons = 0;

    for (const p of secondaire) {
        if (clesPrincipal.has(fusionCle(p))) {
            doublons++;
            continue;
        }
        let couvrants = principal;
        if (!estPause(p) && options.pauseCede) couvrants = travailPrincipal;
        const chevauchants = couvrants.filter(o => fusionChevauche(o, p));
        for (const morceau of fusionSoustraire(p.debut, p.fin, chevauchants)) {
            const ligne = fusionCopie(p, morceau.debut, morceau.fin);
            gardes.push(ligne);
            if (!estPause(p)) travailSecondaire.push(ligne);
        }
        if (estPause(p)) continue;
        for (const o of chevauchants) {
            let debut = p.debut;
            if (o.debut > debut) debut = o.debut;
            let fin = p.fin;
            if (o.fin < fin) fin = o.fin;
            retires.push({ ligne: fusionCopie(p, debut, fin), recouvertPar: fusionLibelle(o) });
        }
    }

    for (const p of principal) {
        if (!estPause(p) || !options.pauseCede) {
            gardes.push(p);
            continue;
        }
        const chevauchants = travailSecondaire.filter(o => fusionChevauche(o, p));
        for (const morceau of fusionSoustraire(p.debut, p.fin, chevauchants)) {
            gardes.push(fusionCopie(p, morceau.debut, morceau.fin));
        }
    }

    gardes.sort((a, b) => a.debut - b.debut);
    retires.sort((a, b) => a.ligne.debut - b.ligne.debut);
    return { pointages: gardes, retires, doublons };
}

/**
 * Fusion à la chaîne : (principal + B) puis + C…, dans l'ordre des fichiers.
 *   listes : un tableau de lignes par fichier ; indexPrincipal : le PC principal.
 * → { pointages, retires: [{ ligne, recouvertPar, fichier }], doublons: [par fichier] }
 */
function fusionnerFichiers(listes, indexPrincipal, options) {
    let pointages = listes[indexPrincipal].slice().sort((a, b) => a.debut - b.debut);
    const retires = [];
    const doublons = listes.map(() => 0);
    listes.forEach((liste, i) => {
        if (i === indexPrincipal) return;
        const r = fusionner(pointages, liste, options);
        pointages = r.pointages;
        doublons[i] = r.doublons;
        for (const retire of r.retires) {
            retire.fichier = i;
            retires.push(retire);
        }
    });
    retires.sort((a, b) => a.ligne.debut - b.ligne.debut);
    return { pointages, retires, doublons };
}

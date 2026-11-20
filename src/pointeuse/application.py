"""Assemblage : icône de notification, panneau, minuteurs, reprise au démarrage, pause automatique."""

import os
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QLockFile, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from pointeuse import demarrage_auto, evenements, settings
from pointeuse.bilan import CsvAbsent, preparer_bilan
from pointeuse.absence import DetecteurAbsence, creer_sources
from pointeuse.affichage import texte_info_bulle
from pointeuse.chemins import DossierNonInscriptible, est_executable, chemin_config, dossier_programme, verifier_inscriptible
from pointeuse.config import Config, ConfigInvalide
from pointeuse.dialogue_absence import DialogueAbsence
from pointeuse.evenements import JournalEvenements
from pointeuse.fenetre_suivi import FenetreSuivi
from pointeuse.icone import icone_etat
from pointeuse.journal import Journal, a_la_minute
from pointeuse.moteur import Moteur
from pointeuse.panneau import Panneau
from pointeuse.style import feuille_de_style
from pointeuse.suivi import JournalSuivi


class Application:

    def __init__(self, qapp: QApplication, moteur: Moteur):
        self.qapp = qapp
        self.moteur = moteur
        self.bloque_signale = False
        self.arret_note = False

        self.panneau = Panneau(moteur)
        self.panneau.pointer.etat_change.connect(self.mettre_a_jour)
        self.panneau.journee.etat_change.connect(self.mettre_a_jour)
        self.suivi = FenetreSuivi(moteur, JournalSuivi(moteur.journal.chemin.parent / settings.NOM_FICHIER_SUIVI))
        self.panneau.pointer.suivi_demande.connect(self.suivi.ouvrir)

        self.icone = QSystemTrayIcon()
        self.icone.activated.connect(self._icone_activee)
        menu = QMenu()
        for libelle, action in (("Ouvrir", self.afficher_panneau),
                                ("Ouvrir le CSV", lambda: self._ouvrir_fichier(moteur.journal.chemin)),
                                ("Ouvrir la config", lambda: self._ouvrir_fichier(moteur.config.chemin)),
                                ("Suivi des projets…", lambda: self.suivi.ouvrir()),
                                ("Bilan", self._ouvrir_bilan),
                                (None, None),
                                ("Quitter", self.quitter)):
            if libelle is None:
                menu.addSeparator()
            else:
                element = QAction(libelle, menu)
                element.triggered.connect(action)
                menu.addAction(element)
        if est_executable():
            # Lancement à l'ouverture de session (étape 7) : sans objet en développement.
            self.action_demarrage = QAction("Lancer à l'ouverture de session", menu, checkable=True)
            self.action_demarrage.setChecked(demarrage_auto.est_active())
            self.action_demarrage.toggled.connect(self._changer_demarrage_auto)
            separateur = [a for a in menu.actions() if a.isSeparator()][0]
            menu.insertAction(separateur, self.action_demarrage)
        self.menu = menu   # garder une référence : sinon le menu est détruit
        self.icone.setContextMenu(menu)

        self.minuteur_affichage = QTimer(interval=settings.RAFRAICHISSEMENT_AFFICHAGE_S * 1000)
        self.minuteur_affichage.timeout.connect(self.mettre_a_jour)
        self.minuteur_verification = QTimer(interval=settings.VERIFICATION_MIN * 60 * 1000)
        self.minuteur_verification.timeout.connect(self.verifier)
        qapp.aboutToQuit.connect(self.moteur.arreter)
        qapp.aboutToQuit.connect(self._noter_arret)

        # Pause automatique (étape 6) : veille, session verrouillée.
        self.detecteur = DetecteurAbsence(lambda: moteur.config.reglage("detection_absence_min"))
        self.detecteur.absence_commencee.connect(self.moteur.absence_commencee)
        self.detecteur.absence_terminee.connect(self._retour_absence)
        self.detecteur.evenement.connect(self._noter_evenement)
        self.sources_absence = creer_sources(self.detecteur)   # garder une référence

    def demarrer(self) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.mettre_a_jour()
            self.icone.show()
        else:
            # GNOME sans l'extension AppIndicator : le panneau devient une fenêtre normale.
            self.panneau.quitter_a_la_fermeture = True
            self.qapp.setQuitOnLastWindowClosed(True)
            QMessageBox.information(None, settings.NOM_APPLICATION,
                                    "Zone de notification introuvable (sous GNOME : activer l'extension "
                                    "« AppIndicator »).\nLa pointeuse s'ouvre en fenêtre ; la fermer arrête le pointage.")
        self.minuteur_affichage.start()
        self.minuteur_verification.start()

        if self.moteur.evenements is not None:
            maintenant = datetime.now()
            self.moteur.evenements.purger(maintenant)
            self.moteur.evenements.noter(evenements.DEMARRAGE, maintenant)

        absence = self.moteur.reprendre_apres_arret()
        if absence is not None and absence.duree_min > 0:
            self.traiter_absence(absence)
        self.detecteur.demarrer()
        self.panneau.pointer.preremplir()
        self.afficher_panneau()

    # ─── Mise à jour périodique ──────────────────────────────────────────────

    def mettre_a_jour(self) -> None:
        moteur = self.moteur
        en_cours = moteur.ligne_ouverte is not None and not moteur.en_pause
        self.icone.setIcon(icone_etat(en_cours, moteur.ecriture_bloquee))
        self.icone.setToolTip(texte_info_bulle(moteur.ligne_ouverte, datetime.now(), len(moteur.en_attente)))
        self.panneau.pointer.rafraichir()
        self.panneau.journee.rafraichir()
        if moteur.ecriture_bloquee and not self.bloque_signale:
            self.bloque_signale = True
            self.icone.showMessage(settings.NOM_APPLICATION,
                                   "pointeuse.csv est ouvert dans un autre programme : les lignes sont gardées "
                                   "et seront écrites dès qu'il sera fermé.",
                                   QSystemTrayIcon.Warning, settings.DUREE_NOTIFICATION_MS)
        if not moteur.ecriture_bloquee:
            self.bloque_signale = False

    def verifier(self) -> None:
        """Chaque minute : réessai du CSV bloqué, sauvegarde toutes les sauvegarde_min minutes."""
        moteur = self.moteur
        try:
            moteur.config.recharger_si_modifie()
        except ConfigInvalide as erreur:
            self.icone.showMessage(settings.NOM_APPLICATION, str(erreur), QSystemTrayIcon.Warning,
                                   settings.DUREE_NOTIFICATION_MS)
        intervalle = moteur.config.reglage("sauvegarde_min")
        derniere = moteur.derniere_sauvegarde
        maintenant = a_la_minute(datetime.now())
        en_retard = derniere is None or (maintenant - derniere).total_seconds() >= intervalle * 60
        if moteur.ecriture_bloquee or en_retard:
            moteur.signe_de_vie()
        self.mettre_a_jour()

    # ─── Panneau ─────────────────────────────────────────────────────────────

    def _icone_activee(self, raison) -> None:
        if raison == QSystemTrayIcon.Trigger:
            if self.panneau.isVisible():
                self.panneau.hide()
            else:
                self.afficher_panneau()

    def afficher_panneau(self) -> None:
        try:
            self.moteur.config.recharger_si_modifie()
        except ConfigInvalide as erreur:
            QMessageBox.warning(None, settings.NOM_APPLICATION, str(erreur))
        self.panneau.pointer.formulaire.recharger()
        self.panneau.pointer.rafraichir()
        self.panneau.journee.formulaire.recharger()
        self.panneau.journee.reinitialiser_plage()
        self.panneau.adjustSize()
        self._placer_panneau()
        self.panneau.show()
        self.panneau.raise_()
        self.panneau.activateWindow()

    def _placer_panneau(self) -> None:
        """Windows / X11 : juste au-dessus de l'icône. Wayland : le système décide (accepté)."""
        if QGuiApplication.platformName() == "wayland":
            return
        zone_icone = self.icone.geometry()
        if not zone_icone.isValid() or zone_icone.isEmpty():
            return
        ecran = QGuiApplication.screenAt(zone_icone.center())
        if ecran is None:
            return
        utile = ecran.availableGeometry()
        taille = self.panneau.sizeHint()
        marge = settings.MARGE_PANNEAU_PX
        x = min(zone_icone.right() - taille.width(), utile.right() - taille.width() - marge)
        x = max(x, utile.left() + marge)
        if zone_icone.center().y() > utile.center().y():
            y = zone_icone.top() - taille.height() - marge     # barre en bas (Windows)
        else:
            y = zone_icone.bottom() + marge                     # barre en haut
        y = max(utile.top() + marge, min(y, utile.bottom() - taille.height() - marge))
        self.panneau.move(x, y)

    # ─── Absence et journal des événements ───────────────────────────────────

    def _noter_evenement(self, nature: str, moment) -> None:
        if self.moteur.evenements is not None:
            self.moteur.evenements.noter(nature, moment)

    def _noter_arret(self) -> None:
        """Une seule fois : « Quitter » puis la fin de la boucle Qt appellent tous deux."""
        if self.arret_note:
            return
        self.arret_note = True
        self._noter_evenement(evenements.ARRET, datetime.now())

    def _retour_absence(self, fin) -> None:
        absence = self.moteur.absence_terminee(fin)
        if absence is not None and absence.duree_min > 0:
            self.traiter_absence(absence)
        else:
            self.mettre_a_jour()

    def traiter_absence(self, absence) -> None:
        self.mettre_a_jour()   # l'icône passe au gris pendant la question
        dialogue = DialogueAbsence(self.moteur.config, absence)
        self.detecteur.suspendre(True)
        dialogue.exec()
        self.detecteur.suspendre(False)
        # L'absence court jusqu'à la réponse, pas seulement jusqu'à l'ouverture de la fenêtre.
        absence = replace(absence, fin=max(absence.fin, a_la_minute(datetime.now())))
        try:
            if dialogue.travail:
                client, projet, tache, description = dialogue.formulaire.valeurs()
                self.moteur.enregistrer_absence(absence, client, projet, tache, description)
            else:
                self.moteur.enregistrer_absence(absence)
        except (ValueError, ConfigInvalide) as erreur:
            QMessageBox.warning(None, settings.NOM_APPLICATION, f"{erreur}\nL'absence est notée en pause.")
            self.moteur.enregistrer_absence(absence)

        precedente = absence.tache_precedente
        if dialogue.reprendre and precedente is not None:
            if precedente.est_pause:
                self.moteur.pause()
            else:
                self.moteur.demarrer(precedente.client, precedente.projet, precedente.tache)
        self.mettre_a_jour()

    # ─── Menu ────────────────────────────────────────────────────────────────

    def _ouvrir_fichier(self, chemin) -> None:
        if not chemin.exists():
            QMessageBox.information(None, settings.NOM_APPLICATION,
                                    f"{chemin.name} n'existe pas encore (il est créé à la première tâche terminée).")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(chemin)))

    def _ouvrir_bilan(self) -> None:
        """Ouvre le bilan du CSV dans le navigateur (page locale, rien n'est envoyé — ADR 003).

        La tâche en cours n'y figure pas : elle n'est écrite dans le CSV qu'à sa fin."""
        chemin_csv = self.moteur.journal.chemin
        try:
            page = preparer_bilan(chemin_csv, chemin_csv.parent, self.suivi.journal_suivi.chemin)
        except CsvAbsent:
            QMessageBox.information(None, settings.NOM_APPLICATION,
                                    f"{chemin_csv.name} n'existe pas encore (il est créé à la première tâche terminée).")
            return
        except OSError as erreur:
            QMessageBox.warning(None, settings.NOM_APPLICATION, f"Impossible de préparer le bilan : {erreur}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(page)))

    def _changer_demarrage_auto(self, actif: bool) -> None:
        try:
            if actif:
                demarrage_auto.activer(Path(sys.executable))
            else:
                demarrage_auto.desactiver()
        except OSError as erreur:
            QMessageBox.warning(None, settings.NOM_APPLICATION, f"Réglage du démarrage impossible : {erreur}")
            self.action_demarrage.blockSignals(True)
            self.action_demarrage.setChecked(demarrage_auto.est_active())
            self.action_demarrage.blockSignals(False)

    def quitter(self) -> None:
        self.moteur.arreter()
        self._noter_arret()
        self.icone.hide()
        self.qapp.quit()


def main() -> int:
    if sys.platform.startswith("linux"):
        # Doit être fait avant de créer QApplication ; un réglage de l'utilisateur reste prioritaire.
        os.environ.setdefault("QT_QPA_PLATFORMTHEME", settings.THEME_QT_LINUX)
    qapp = QApplication(sys.argv)
    qapp.setStyle(settings.STYLE_QT)
    qapp.setApplicationName(settings.NOM_APPLICATION)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setStyleSheet(feuille_de_style())

    dossier = dossier_programme()
    try:
        verifier_inscriptible(dossier)
    except DossierNonInscriptible as erreur:
        QMessageBox.critical(None, settings.NOM_APPLICATION, str(erreur))
        return 1

    verrou = QLockFile(str(dossier / settings.NOM_FICHIER_VERROU))
    if not verrou.tryLock(100):
        QMessageBox.information(None, settings.NOM_APPLICATION,
                                "La pointeuse est déjà lancée (voir la zone de notification).")
        return 0

    try:
        config = Config(chemin_config(dossier))
    except ConfigInvalide as erreur:
        QMessageBox.critical(None, settings.NOM_APPLICATION,
                             f"{erreur}\n\nCorrigez {settings.NOM_FICHIER_CONFIG} puis relancez la pointeuse.")
        return 1

    journal_evenements = JournalEvenements(dossier / settings.NOM_FICHIER_EVENEMENTS,
                                           lambda: config.reglage("retention_journal_jours"))
    moteur = Moteur(config, Journal(dossier / settings.NOM_FICHIER_CSV), dossier / settings.NOM_FICHIER_EN_COURS,
                    evenements=journal_evenements)
    application = Application(qapp, moteur)
    application.demarrer()
    code = qapp.exec()
    verrou.unlock()
    return code

"""Détection des absences : veille, session verrouillée (CDC étape 6).

Trois sources, qui alimentent toutes DetecteurAbsence.signaler(raison, actif) :
- secours, sur les deux OS : un relevé d'horloge toutes les 30 s. Un saut de plus
  de detection_absence_min veut dire que le PC dormait (les minuteurs Qt s'arrêtent
  pendant la veille) ;
- Linux : D-Bus — org.freedesktop.login1 (veille), org.gnome.ScreenSaver (verrouillage) ;
- Windows : messages WM_WTSSESSION_CHANGE (verrouillage) et WM_POWERBROADCAST (veille),
  reçus par une fenêtre invisible (ctypes, aucune dépendance).

L'absence commence quand la première raison devient active et se termine quand
toutes sont retombées. Le détecteur ne décide rien : l'Application transmet au moteur.
"""

import sys
import time
from datetime import datetime
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal, Slot, SLOT

from pointeuse import settings

RAISON_VERROU = "verrouillage"
RAISON_VEILLE = "veille"


class DetecteurAbsence(QObject):
    """Émet absence_commencee(debut) puis absence_terminee(fin), en datetime local."""

    absence_commencee = Signal(object)
    absence_terminee = Signal(object)

    def __init__(self, seuil_min: Callable[[], int], horloge: Callable[[], datetime] = datetime.now,
                 epoque: Callable[[], float] = time.time, parent=None):
        super().__init__(parent)
        self.seuil_min = seuil_min      # fonction : le réglage peut changer à chaud
        self.horloge = horloge
        self.epoque = epoque            # secondes UTC : pas de faux saut au changement d'heure
        self.raisons: set[str] = set()
        self.suspendu = False           # vrai pendant la fenêtre « retour d'absence »
        self._dernier_releve: tuple[float, datetime] | None = None
        self.minuteur = QTimer(self, interval=settings.RELEVE_HORLOGE_S * 1000)
        self.minuteur.timeout.connect(self.relever)

    def demarrer(self) -> None:
        self.relever()
        self.minuteur.start()

    @property
    def en_absence(self) -> bool:
        return len(self.raisons) > 0

    # ─── Sources ─────────────────────────────────────────────────────────────

    def signaler(self, raison: str, actif: bool) -> None:
        """Appelé par les sources OS : verrouillage / veille qui commence ou finit."""
        if self.suspendu:
            return
        maintenant = self.horloge()
        if actif:
            deja = self.en_absence
            self.raisons.add(raison)
            if not deja:
                self.absence_commencee.emit(maintenant)
        elif raison in self.raisons:
            self.raisons.discard(raison)
            if not self.en_absence:
                self.absence_terminee.emit(maintenant)
        self._dernier_releve = (self.epoque(), maintenant)

    def relever(self) -> None:
        """Solution de secours : un trou dans les relevés = le PC dormait."""
        epoque, maintenant = self.epoque(), self.horloge()
        precedent = self._dernier_releve
        self._dernier_releve = (epoque, maintenant)
        if precedent is None or self.suspendu or self.en_absence:
            return   # une absence signalée par l'OS est déjà en cours : on attend sa fin
        if epoque - precedent[0] >= self.seuil_min() * 60:
            self.absence_commencee.emit(precedent[1])
            self.absence_terminee.emit(maintenant)

    def suspendre(self, suspendu: bool) -> None:
        """Pendant la fenêtre « retour d'absence », le temps compte déjà dans l'absence."""
        self.suspendu = suspendu
        self.raisons.clear()
        self._dernier_releve = (self.epoque(), self.horloge())


# ─── Linux : D-Bus ───────────────────────────────────────────────────────────

class SourceDBus(QObject):
    """Veille (login1, bus système) et verrouillage (GNOME, bus de session)."""

    def __init__(self, detecteur: DetecteurAbsence, parent=None):
        super().__init__(parent)
        self.detecteur = detecteur
        self.connectee = False
        try:
            from PySide6.QtDBus import QDBusConnection
        except ImportError:
            return
        session = QDBusConnection.sessionBus()
        systeme = QDBusConnection.systemBus()
        verrou = session.isConnected() and session.connect(
            "org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver",
            "ActiveChanged", self, SLOT("verrouillage(bool)"))
        veille = systeme.isConnected() and systeme.connect(
            "org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager",
            "PrepareForSleep", self, SLOT("veille(bool)"))
        self.connectee = bool(verrou or veille)

    @Slot(bool)
    def verrouillage(self, actif: bool) -> None:
        self.detecteur.signaler(RAISON_VERROU, actif)

    @Slot(bool)
    def veille(self, actif: bool) -> None:
        self.detecteur.signaler(RAISON_VEILLE, actif)


# ─── Windows : messages de session et d'alimentation ─────────────────────────

WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
WM_POWERBROADCAST = 0x0218
PBT_APMSUSPEND = 0x4
PBT_APMRESUMESUSPEND = 0x7
PBT_APMRESUMEAUTOMATIC = 0x12
NOTIFY_FOR_THIS_SESSION = 0


def traduire_message_windows(message: int, wparam: int) -> tuple[str, bool] | None:
    """(raison, actif) pour un message Windows qui nous intéresse, sinon None."""
    if message == WM_WTSSESSION_CHANGE:
        if wparam == WTS_SESSION_LOCK:
            return RAISON_VERROU, True
        if wparam == WTS_SESSION_UNLOCK:
            return RAISON_VERROU, False
    if message == WM_POWERBROADCAST:
        if wparam == PBT_APMSUSPEND:
            return RAISON_VEILLE, True
        if wparam in (PBT_APMRESUMESUSPEND, PBT_APMRESUMEAUTOMATIC):
            return RAISON_VEILLE, False
    return None


def creer_source_windows(detecteur: DetecteurAbsence):
    """Fenêtre invisible abonnée aux notifications de session. None si indisponible."""
    import ctypes
    from ctypes import wintypes

    from PySide6.QtWidgets import QWidget

    class FenetreWindows(QWidget):
        def nativeEvent(self, type_evenement, message):
            try:
                msg = wintypes.MSG.from_address(int(message))
                evenement = traduire_message_windows(msg.message, msg.wParam)
                if evenement is not None:
                    detecteur.signaler(*evenement)
            except (ValueError, TypeError, OSError):
                pass   # message illisible : la solution de secours reste active
            return False, 0

    fenetre = FenetreWindows()
    try:
        ok = ctypes.windll.wtsapi32.WTSRegisterSessionNotification(
            wintypes.HWND(int(fenetre.winId())), NOTIFY_FOR_THIS_SESSION)
    except (AttributeError, OSError):
        ok = False
    if not ok:
        fenetre.deleteLater()
        return None
    return fenetre


def creer_sources(detecteur: DetecteurAbsence) -> list:
    """Sources propres à l'OS ; la solution de secours (relever) marche dans tous les cas."""
    sources = []
    if sys.platform.startswith("linux"):
        source = SourceDBus(detecteur)
        if source.connectee:
            sources.append(source)
    elif sys.platform == "win32":
        source = creer_source_windows(detecteur)
        if source is not None:
            sources.append(source)
    return sources

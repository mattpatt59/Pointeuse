"""Icône horloge dessinée à la volée (pas de fichier image à embarquer)."""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from pointeuse import settings


def icone_horloge(couleur: str) -> QIcon:
    taille = settings.TAILLE_ICONE_PX
    image = QPixmap(taille, taille)
    image.fill(Qt.transparent)
    peintre = QPainter(image)
    peintre.setRenderHint(QPainter.Antialiasing)

    centre = QPointF(taille / 2, taille / 2)
    rayon = taille * 0.46
    peintre.setPen(Qt.NoPen)
    peintre.setBrush(QColor(couleur))
    peintre.drawEllipse(centre, rayon, rayon)
    peintre.setBrush(QColor(settings.COULEUR_BLANC))
    peintre.drawEllipse(centre, rayon * 0.74, rayon * 0.74)

    aiguilles = QPen(QColor(couleur), taille * 0.09, Qt.SolidLine, Qt.RoundCap)
    peintre.setPen(aiguilles)
    peintre.drawLine(centre, QPointF(centre.x(), centre.y() - rayon * 0.52))   # minutes : 12 h
    peintre.drawLine(centre, QPointF(centre.x() + rayon * 0.38, centre.y()))   # heures : 3 h
    peintre.end()
    return QIcon(image)


def icone_etat(en_cours: bool, bloque: bool) -> QIcon:
    """Vert : tâche en cours. Gris : pause / rien. Orange : CSV bloqué."""
    if bloque:
        return icone_horloge(settings.COULEUR_ORANGE)
    if en_cours:
        return icone_horloge(settings.COULEUR_VERT_FONCE)
    return icone_horloge(settings.COULEUR_GRIS)

# ADR — Toolkit UI et icône de notification

**Date :** 2026-11-17
**Statut :** ACCEPTÉ (MP 2026-11-17)

---

## Contexte

Il faut une icône horloge dans la zone de notification (Windows : à côté de
l'icône réseau ; Linux : barre du haut sous Ubuntu GNOME), qui ouvre un petit
panneau, le tout avec un seul code pour Windows et Linux.

Poste de dev : Ubuntu 24.04, GNOME sous **Wayland**, extension
`ubuntu-appindicators` active.

## Options envisagées

| Option | Avantages | Inconvénients |
|--------|-----------|---------------|
| **PySide6** (QSystemTrayIcon + QWidget) | Icône de notification et UI dans un seul toolkit ; rendu natif propre ; licence LGPL ; fonctionne en StatusNotifierItem sous GNOME/KDE | Exécutable lourd (~60–80 Mo avec PyInstaller) |
| pystray + tkinter | Léger, tkinter fourni avec Python | Deux boucles d'événements à faire cohabiter (threads) ; tkinter peu esthétique ; sous Linux pystray dépend de GTK/AppIndicator |
| pystray + webview | UI HTML (charte CSS T-Elec réutilisable) | Trois briques, dépendances système plus lourdes |

## Décision

**Choix : PySide6**

Raison : une seule bibliothèque couvre l'icône, le menu, le panneau et les
boîtes de dialogue sur les deux OS, ce qui limite le code propre à chaque plateforme.

## Conséquences

- Windows : on place le panneau juste au-dessus de l'icône avec `QSystemTrayIcon.geometry()`.
- Linux / Wayland : l'application **ne peut pas choisir la position** de sa fenêtre,
  c'est le compositeur qui place le panneau (en général au centre). Solutions :
  forcer XWayland (`QT_QPA_PLATFORM=xcb`) pour retrouver le positionnement en haut à droite,
  ou se contenter d'un menu déroulant sur l'icône. **Retenu : le placement par le système suffit** (MP 2026-11-17).
- GNOME sans extension AppIndicator : l'icône n'apparaît pas → prérequis à documenter.

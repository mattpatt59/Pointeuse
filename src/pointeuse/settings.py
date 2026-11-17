"""Constantes centralisées de l'application (règle commune §F)."""

# ─── Fichiers (créés dans le dossier du programme, voir chemins.py) ──────────
NOM_FICHIER_CONFIG = "pointeuse_config.toml"
NOM_FICHIER_CSV = "pointeuse.csv"
NOM_FICHIER_EN_COURS = "pointeuse_en_cours.json"

# Dossier utilisé en développement (python -m pointeuse), relatif à la racine du dépôt.
DOSSIER_DATA_DEV = "data"

# ─── Format du CSV (contrat avec le futur outil de bilan : modifier = ADR) ───
COLONNES_CSV = ["date_in", "date_out", "client", "projet", "tache", "description", "duree_min"]
SEPARATEUR_CSV = ";"
ENCODAGE_CSV = "utf-8-sig"        # UTF-8 avec BOM : accents corrects dans Excel FR
FORMAT_DATE_CSV = "%Y-%m-%d %H:%M"

# ─── Pointage ────────────────────────────────────────────────────────────────
# Nom de client réservé aux lignes de pause : interdit pour un vrai client.
CLIENT_PAUSE = "PAUSE"

# ─── Interface ───────────────────────────────────────────────────────────────
NOM_APPLICATION = "Pointeuse"
NOM_FICHIER_VERROU = "pointeuse.lock"   # empêche de lancer deux fois l'appli sur les mêmes fichiers
# Linux : le thème Qt « gtk3 » (choisi par défaut sous GNOME) fait planter l'appli sur Ubuntu 24.04
# (GLib : clé xsettings « antialiasing » absente → arrêt brutal). Le thème « gnome » de Qt n'a pas ce souci.
THEME_QT_LINUX = "gnome"
STYLE_QT = "Fusion"                     # même rendu sous Windows et Linux, base de la feuille de style
POLICE = "Arial"                        # charte T-Elec §D : app Python → Arial / police système
TAILLE_POLICE_PT = 10
LARGEUR_PANNEAU_PX = 400
TAILLE_ICONE_PX = 64
LARGEUR_FLECHE_LISTE_PX = 26            # zone cliquable « ⌄ » à droite des listes Client / Projet / Tâche
DOSSIER_TEMP_STYLE = "pointeuse_style"  # images de la feuille de style, dans le dossier temporaire du système
MARGE_PANNEAU_PX = 8                    # écart entre l'icône de notification et le panneau (Windows)
RAFRAICHISSEMENT_AFFICHAGE_S = 30       # mise à jour de l'info-bulle et du chrono
VERIFICATION_MIN = 1                    # tick : sauvegarde périodique, réessai du CSV bloqué
DUREE_NOTIFICATION_MS = 8000

# Charte T-Elec §C
COULEUR_VERT = "#99CB38"
COULEUR_VERT_FONCE = "#70AD47"
COULEUR_VERT_PROFOND = "#4a7a1a"
COULEUR_VERT_CLAIR = "#f2f9e5"
COULEUR_NOIR = "#1a1a1a"
COULEUR_GRIS = "#6b7280"
COULEUR_BORDURE = "#e5e7eb"
COULEUR_BLANC = "#ffffff"
COULEUR_ORANGE = "#fb8c00"
COULEUR_ORANGE_CLAIR = "#fff3e0"
COULEUR_BOUTON_SECONDAIRE = "#546e7a"

# ─── Réglages par défaut (surchargés par [reglages] du fichier de config) ────
REGLAGES_DEFAUT = {
    "sauvegarde_min": 5,          # fréquence de sauvegarde de la ligne en cours (min)
    "detection_absence_min": 2,   # saut d'horloge considéré comme une veille (min)
}

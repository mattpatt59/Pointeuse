"""Lancement automatique à l'ouverture de la session (CDC étape 7).

Coché / décoché depuis le menu de l'icône, seulement pour l'exécutable (pas en dev) :
- Windows : valeur « Pointeuse » dans HKCU\\...\\CurrentVersion\\Run (pas de droits admin) ;
- Linux : fichier ~/.config/autostart/pointeuse.desktop (norme XDG, reconnue par GNOME).
"""

import os
import sys
from pathlib import Path

from pointeuse import settings

CLE_RUN_WINDOWS = r"Software\Microsoft\Windows\CurrentVersion\Run"


def fichier_autostart_linux() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / settings.NOM_FICHIER_AUTOSTART


def contenu_desktop(executable: Path) -> str:
    return ("[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={settings.NOM_APPLICATION}\n"
            "Comment=Pointage du temps par client / projet\n"
            f'Exec="{executable}"\n'
            f"Path={executable.parent}\n"
            "X-GNOME-Autostart-enabled=true\n"
            "Terminal=false\n")


def est_active() -> bool:
    if sys.platform == "win32":
        return _lire_windows() is not None
    return fichier_autostart_linux().exists()


def activer(executable: Path) -> None:
    """Lève OSError si l'écriture échoue."""
    executable = Path(executable).resolve()
    if sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLE_RUN_WINDOWS, 0, winreg.KEY_SET_VALUE) as cle:
            winreg.SetValueEx(cle, settings.NOM_APPLICATION, 0, winreg.REG_SZ, f'"{executable}"')
        return
    fichier = fichier_autostart_linux()
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_text(contenu_desktop(executable), encoding="utf-8")


def desactiver() -> None:
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLE_RUN_WINDOWS, 0, winreg.KEY_SET_VALUE) as cle:
                winreg.DeleteValue(cle, settings.NOM_APPLICATION)
        except FileNotFoundError:
            pass
        return
    fichier_autostart_linux().unlink(missing_ok=True)


def _lire_windows() -> str | None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLE_RUN_WINDOWS) as cle:
            valeur, _ = winreg.QueryValueEx(cle, settings.NOM_APPLICATION)
    except OSError:
        return None
    return valeur

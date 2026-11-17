"""Lancement à l'ouverture de session — partie Linux (XDG autostart). Windows : test sur poste réel."""

import sys
from pathlib import Path

import pytest

from pointeuse import demarrage_auto

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="registre Windows : test sur poste réel")


def test_activer_desactiver(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    executable = tmp_path / "mes outils" / "Pointeuse" / "Pointeuse"
    assert not demarrage_auto.est_active()
    demarrage_auto.activer(executable)
    assert demarrage_auto.est_active()
    contenu = (tmp_path / "autostart" / "pointeuse.desktop").read_text(encoding="utf-8")
    assert f'Exec="{executable}"' in contenu
    assert f"Path={executable.parent}" in contenu
    demarrage_auto.desactiver()
    demarrage_auto.desactiver()     # deux fois : sans erreur
    assert not demarrage_auto.est_active()


def test_sans_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert demarrage_auto.fichier_autostart_linux() == tmp_path / ".config" / "autostart" / "pointeuse.desktop"

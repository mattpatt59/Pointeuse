#!/usr/bin/env bash
# Nom : generer_png.sh
# Usage : exporte chaque vue de maquettes.html en PNG (Firefox headless). ./generer_png.sh
# Date : 2026-11-17
set -euo pipefail
dir="$(cd "$(dirname "$0")" && pwd)"
profil="$dir/profil_tmp"   # pas de /tmp : Firefox snap n'y a pas accès
mkdir -p "$profil"
trap 'rm -rf "$profil"' EXIT

exporter() {  # vue largeur hauteur
    firefox --headless --no-remote --profile "$profil" \
        --window-size="$2,$3" --screenshot "$dir/$1.png" \
        "file://$dir/maquettes.html?vue=$1" >/dev/null 2>&1
    echo "$dir/$1.png"
}

exporter pointer 720 560
exporter liste   620 590
exporter inserer 720 780
exporter absence 600 560

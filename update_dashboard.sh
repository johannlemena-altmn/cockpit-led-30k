#!/usr/bin/env bash
# Rafraîchit public_data.json depuis Pixel CRM ou un export CSV
# puis pousse le résultat sur GitHub pour mettre à jour le dashboard live.
#
# Usage :
#   ./update_dashboard.sh                          → via pixel_api.py (API Pixel directe)
#   ./update_dashboard.sh data/mon.csv             → via export CSV Pixel
#   ./update_dashboard.sh --betool data/betool.xlsx → pipeline BETOOL seulement
#   ./update_dashboard.sh data/mon.csv --betool data/betool.xlsx → les deux
#
# Prérequis : fichier .env dans ce dossier avec :
#   PIXEL_BASE_URL=https://crm.pixel-crm.fr
#   PIXEL_SESSION_COOKIE=<cookie copié depuis DevTools>
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── Charger .env si présent ───────────────────────────────────────────────────
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# ── Vérifier Python ───────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
  echo "[ERREUR] Python introuvable. Installer Python 3.9+."
  exit 1
fi
PYTHON="${PYTHON:-$(command -v python3 2>/dev/null || command -v python)}"

# ── Installer les dépendances si nécessaire ───────────────────────────────────
if ! "$PYTHON" -c "import pandas" 2>/dev/null; then
  echo "Installation des dépendances (pandas, openpyxl)…"
  "$PYTHON" -m pip install pandas openpyxl --quiet
fi

# ── Arguments ────────────────────────────────────────────────────────────────
CSV_ARG=""
BETOOL_ARG=""
ARGS=("$@")
i=0
while [ $i -lt ${#ARGS[@]} ]; do
  if [ "${ARGS[$i]}" = "--betool" ]; then
    i=$((i+1))
    BETOOL_ARG="${ARGS[$i]:-}"
  elif [ -z "$CSV_ARG" ] && [ "${ARGS[$i]:0:1}" != "-" ]; then
    CSV_ARG="${ARGS[$i]}"
  fi
  i=$((i+1))
done

# ── Source de données ─────────────────────────────────────────────────────────

if [ -n "$CSV_ARG" ]; then
  # Mode CSV : copier dans data/ et lancer daily_summary.py
  echo "Mode CSV : $CSV_ARG"
  mkdir -p data
  cp "$CSV_ARG" data/export_crm.csv
  "$PYTHON" daily_summary.py
else
  # Mode API Pixel (doit être lancé depuis ton PC, pas GitHub Actions)
  echo "Mode API Pixel CRM…"
  if [ -z "${PIXEL_BASE_URL:-}" ] || [ -z "${PIXEL_SESSION_COOKIE:-}" ]; then
    echo "[ERREUR] Créer un fichier .env avec :"
    echo "  PIXEL_BASE_URL=https://crm.pixel-crm.fr"
    echo "  PIXEL_SESSION_COOKIE=<valeur du header Cookie depuis DevTools>"
    exit 1
  fi
  "$PYTHON" pixel_api.py
fi

# ── BETOOL pipeline (optionnel) ───────────────────────────────────────────────
if [ -n "$BETOOL_ARG" ]; then
  if [ ! -f "$BETOOL_ARG" ]; then
    echo "[ERREUR] Fichier BETOOL introuvable : $BETOOL_ARG"
    exit 1
  fi
  echo "Pipeline BETOOL : $BETOOL_ARG"
  "$PYTHON" betool_summary.py "$BETOOL_ARG"
fi

# ── Vérifier que public_data.json existe ─────────────────────────────────────
if [ ! -f "public_data.json" ]; then
  echo "[ERREUR] public_data.json non généré."
  exit 1
fi

# ── Git : commit + push ───────────────────────────────────────────────────────
if git diff --quiet public_data.json 2>/dev/null; then
  echo "public_data.json inchangé — aucune mise à jour nécessaire."
else
  TODAY="$(date +%Y-%m-%d)"
  git add public_data.json
  git commit -m "data: public_data.json $TODAY"
  git push origin main
  echo ""
  echo "✅ Dashboard mis à jour : https://johannlemena-altmn.github.io/cockpit-led-30k/"
fi

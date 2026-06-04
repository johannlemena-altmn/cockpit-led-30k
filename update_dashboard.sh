#!/usr/bin/env bash
# Rafraîchit public_data.json depuis Pixel CRM ou un export CSV
# puis pousse le résultat sur GitHub pour mettre à jour le dashboard live.
#
# Usage :
#   ./update_dashboard.sh                          → via pixel_api.py (API Pixel directe)
#   ./update_dashboard.sh data/mon.csv             → via export CSV Pixel
#   ./update_dashboard.sh --betool data/betool.xlsx → pipeline BETOOL seulement
#   ./update_dashboard.sh --confirme "data/LISTE EQ 127 CONFIRME.csv" → confirmés CEE
#   ./update_dashboard.sh --confirme liste.csv --ary "data/TABLEAU ARY.csv" → + autres secteurs
#   ./update_dashboard.sh --betool b.xlsx --confirme liste.csv --ary ary.csv → tout
#   ./update_dashboard.sh --auditeur data/prime_evolution.xlsx              → board auditeur seul
#   ./update_dashboard.sh --betool b.xlsx --confirme liste.csv --ary ary.csv --auditeur pe.xlsx → complet
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
CONFIRME_ARG=""
ARY_ARG=""
AUDITEUR_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --betool)   shift; BETOOL_ARG="${1:-}"   ;;
    --confirme) shift; CONFIRME_ARG="${1:-}" ;;
    --ary)      shift; ARY_ARG="${1:-}"      ;;
    --auditeur) shift; AUDITEUR_ARG="${1:-}" ;;
    -*)         ;;
    *)          [ -z "$CSV_ARG" ] && CSV_ARG="$1" ;;
  esac
  shift
done

# ── Source de données ─────────────────────────────────────────────────────────

if [ -n "$CSV_ARG" ]; then
  # Mode CSV : copier dans data/ et lancer daily_summary.py
  echo "Mode CSV : $CSV_ARG"
  mkdir -p data
  cp "$CSV_ARG" data/export_crm.csv
  "$PYTHON" daily_summary.py
elif [ -n "$BETOOL_ARG" ] || [ -n "$CONFIRME_ARG" ] || [ -n "$AUDITEUR_ARG" ]; then
  # Mode fichiers locaux (BETOOL / LISTE CONFIRME) : pas d'API Pixel.
  echo "Mode fichiers locaux — pas d'appel à l'API Pixel."
elif [ -n "${PIXEL_BASE_URL:-}" ] && [ -n "${PIXEL_SESSION_COOKIE:-}" ]; then
  # Mode API Pixel (doit être lancé depuis ton PC, pas GitHub Actions)
  echo "Mode API Pixel CRM…"
  "$PYTHON" pixel_api.py
else
  echo "[ERREUR] Aucune source de données fournie."
  echo "  • Export BETOOL : ./update_dashboard.sh --betool data/betool.xlsx"
  echo "  • Export CSV     : ./update_dashboard.sh data/export.csv"
  echo "  • API Pixel      : créer un .env avec PIXEL_BASE_URL + PIXEL_SESSION_COOKIE"
  exit 1
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

# ── LISTE CONFIRME CEE (optionnel) ────────────────────────────────────────────
if [ -n "$CONFIRME_ARG" ]; then
  if [ ! -f "$CONFIRME_ARG" ]; then
    echo "[ERREUR] Fichier LISTE CONFIRME introuvable : $CONFIRME_ARG"
    exit 1
  fi
  echo "Confirmés CEE : $CONFIRME_ARG"
  if [ -n "$ARY_ARG" ]; then
    "$PYTHON" confirme_summary.py "$CONFIRME_ARG" --ary "$ARY_ARG"
  else
    "$PYTHON" confirme_summary.py "$CONFIRME_ARG"
  fi
fi

# ── BETOOL auditeur / Prime Evolution (optionnel) ────────────────────────────
if [ -n "$AUDITEUR_ARG" ]; then
  if [ ! -f "$AUDITEUR_ARG" ]; then
    echo "[ERREUR] Fichier auditeur introuvable : $AUDITEUR_ARG"
    exit 1
  fi
  echo "Pipeline auditeur (Prime Evolution) : $AUDITEUR_ARG"
  "$PYTHON" auditeur_summary.py "$AUDITEUR_ARG"
fi

# ── Brief quotidien + delta J-1 (toujours) ────────────────────────────────────
echo "Génération du brief + delta…"
"$PYTHON" daily_brief.py || true

# ── Snapshot historique du jour (toujours) ────────────────────────────────────
echo "Archivage du snapshot historique…"
"$PYTHON" snapshot.py || true

# ── Vérifier que public_data.json existe ─────────────────────────────────────
if [ ! -f "public_data.json" ]; then
  echo "[ERREUR] public_data.json non généré."
  exit 1
fi

# ── Git : commit + push ───────────────────────────────────────────────────────
if git diff --quiet public_data.json history/ 2>/dev/null && \
   [ -z "$(git ls-files --others --exclude-standard history/ 2>/dev/null)" ]; then
  echo "public_data.json + historique inchangés — aucune mise à jour nécessaire."
else
  TODAY="$(date +%Y-%m-%d)"
  git add public_data.json history/
  git commit -m "data: public_data.json + snapshot $TODAY"
  git push origin main
  echo ""
  echo "✅ Dashboard mis à jour : https://johannlemena-altmn.github.io/cockpit-led-30k/"
fi

#!/usr/bin/env bash
# Rafraîchit le cockpit : (1) [option] ré-exporte le CSV depuis Pixel, (2) recharge Postgres.
# Planifier toutes les 15-30 min via cron :  */20 * * * * /chemin/infra/refresh.sh >> /tmp/led_refresh.log 2>&1
set -euo pipefail
cd "$(dirname "$0")"

# --- (1) Récupération du CSV ---
# A) Manuel : déposez l'export Pixel dans ../data/ (le plus récent est pris).
# B) Auto (à implémenter en Sprint) : script Playwright/headless qui rejoue
#    Recherche BAT-EQ-127 -> Export -> "eq 127 pour liste" et dépose le CSV ici.
#    (ou, mieux, appel direct de l'endpoint JSON de recherche une fois reversé.)

# --- (2) Chargement ---
export PG_URL="${PG_URL:-postgresql+psycopg2://led:changeme@localhost:5432/ledcockpit}"
python3 etl.py "${DATA_DIR:-../data}"

# --- (3) Vues (idempotent) ---
PGPASSWORD="${PGPASSWORD:-changeme}" psql -h localhost -U "${PGUSER:-led}" -d ledcockpit -f sql/views.sql || true
echo "Refresh terminé : $(date)"

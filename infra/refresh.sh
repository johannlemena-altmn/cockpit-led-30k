#!/usr/bin/env bash
# Rafraîchit le cockpit complet :
#   1. Recharge Postgres depuis le dernier CSV + optionnel BETOOL
#   2. Met à jour public_data.json (agrégats dashboard)
#   3. Git commit + push (si changement)
#
# Usage :
#   ./infra/refresh.sh                                     → CSV auto + pas de BETOOL
#   ./infra/refresh.sh --betool /chemin/betool.xlsx        → + pipeline BETOOL
#   ./infra/refresh.sh /chemin/data --betool betool.xlsx   → dossier CSV explicite
#
# Planification cron (toutes les 20 min) :
#   */20 * * * * /chemin/cockpit-led-30k/infra/refresh.sh >> /tmp/led_refresh.log 2>&1
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."
cd "$SCRIPT_DIR"

# Charger .env si présent à la racine
if [ -f "$ROOT/.env" ]; then
  set -a; source "$ROOT/.env"; set +a
fi

# Args
DATA_ARG=""
BETOOL_ARG=""
ARGS=("$@")
i=0
while [ $i -lt ${#ARGS[@]} ]; do
  if [ "${ARGS[$i]}" = "--betool" ]; then
    i=$((i+1)); BETOOL_ARG="${ARGS[$i]:-}"
  elif [ -z "$DATA_ARG" ] && [ "${ARGS[$i]:0:1}" != "-" ]; then
    DATA_ARG="${ARGS[$i]}"
  fi
  i=$((i+1))
done
DATA_DIR="${DATA_ARG:-$ROOT/data}"
export PG_URL="${PG_URL:-postgresql+psycopg2://led:changeme@localhost:5432/ledcockpit}"
PYTHON="${PYTHON:-$(command -v python3 2>/dev/null || command -v python)}"

echo "=== Refresh $(date) ==="

# 1. ETL CSV → Postgres
echo "→ ETL CSV : $DATA_DIR"
if [ -n "$BETOOL_ARG" ]; then
  echo "  + BETOOL : $BETOOL_ARG"
  "$PYTHON" "$SCRIPT_DIR/etl.py" "$DATA_DIR" --betool "$BETOOL_ARG"
else
  "$PYTHON" "$SCRIPT_DIR/etl.py" "$DATA_DIR"
fi

# 2. Regénérer public_data.json depuis CSV
echo "→ Génération public_data.json..."
cd "$ROOT"
"$PYTHON" daily_summary.py

# 3. Si BETOOL dispo, enrichir public_data.json avec pipeline
if [ -n "$BETOOL_ARG" ]; then
  echo "→ Pipeline BETOOL..."
  "$PYTHON" betool_summary.py "$BETOOL_ARG"
fi

# 4. Git commit + push si changement
if ! git diff --quiet public_data.json 2>/dev/null; then
  TODAY="$(date +%Y-%m-%d)"
  git add public_data.json
  git commit -m "data: public_data.json $TODAY (refresh auto)"
  git push origin main
  echo "✅ Dashboard mis à jour"
else
  echo "public_data.json inchangé — rien à pousser."
fi

echo "=== Refresh terminé : $(date) ==="

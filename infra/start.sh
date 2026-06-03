#!/usr/bin/env bash
# Usage : ./infra/start.sh [chemin_vers_csv_ou_dossier_data]
# Lance Postgres+Metabase, exécute l'ETL, ouvre Metabase dans le navigateur
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA=${1:-"$SCRIPT_DIR/../data"}

echo "=== Cockpit LED 30k — démarrage ==="
cd "$SCRIPT_DIR"

# 1. Démarrer la stack Docker
echo "→ docker compose up..."
docker compose up -d

# 2. Attendre Postgres
echo "→ Attente Postgres (max 30s)..."
for i in $(seq 1 30); do
  docker compose exec -T db pg_isready -U ${PGUSER:-led} -q && break
  sleep 1
done

# 3. ETL
echo "→ ETL CSV → Postgres..."
pip install -q -r "$SCRIPT_DIR/requirements.txt"
export PG_URL="${PG_URL:-postgresql+psycopg2://led:changeme@localhost:5432/ledcockpit}"
python "$SCRIPT_DIR/etl.py" "$DATA"

# 4. Ouvrir Metabase
echo "=== Metabase dispo sur http://localhost:3000 ==="
echo "    (premier lancement : configurer le compte admin, puis connecter la base 'ledcockpit')"
if command -v open &>/dev/null; then open "http://localhost:3000"
elif command -v xdg-open &>/dev/null; then xdg-open "http://localhost:3000"; fi

#!/usr/bin/env bash
# Lance Postgres+Metabase, exécute l'ETL (CSV + optionnel BETOOL), ouvre Metabase.
#
# Usage :
#   ./infra/start.sh                                          → data/ par défaut
#   ./infra/start.sh /chemin/vers/data                        → dossier CSV
#   ./infra/start.sh /chemin/vers/data --betool betool.xlsx   → CSV + BETOOL
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DATA=""
BETOOL_ARG=""
ARGS=("$@")
i=0
while [ $i -lt ${#ARGS[@]} ]; do
  if [ "${ARGS[$i]}" = "--betool" ]; then
    i=$((i+1)); BETOOL_ARG="${ARGS[$i]:-}"
  elif [ -z "$DATA" ] && [ "${ARGS[$i]:0:1}" != "-" ]; then
    DATA="${ARGS[$i]}"
  fi
  i=$((i+1))
done
DATA="${DATA:-$SCRIPT_DIR/../data}"

echo "=== Cockpit LED 30k — démarrage ==="

# 1. Démarrer la stack Docker
echo "→ docker compose up..."
docker compose up -d

# 2. Attendre Postgres
echo "→ Attente Postgres (max 30s)..."
for i in $(seq 1 30); do
  docker compose exec -T db pg_isready -U "${PGUSER:-led}" -q && break
  sleep 1
done

# 3. Dépendances
pip install -q -r "$SCRIPT_DIR/requirements.txt"

# 4. ETL CSV (+ BETOOL si fourni)
echo "→ ETL CSV → Postgres : $DATA"
export PG_URL="${PG_URL:-postgresql+psycopg2://led:changeme@localhost:5432/ledcockpit}"
if [ -n "$BETOOL_ARG" ]; then
  echo "  + BETOOL : $BETOOL_ARG"
  python "$SCRIPT_DIR/etl.py" "$DATA" --betool "$BETOOL_ARG"
else
  python "$SCRIPT_DIR/etl.py" "$DATA"
fi

# 5. Ouvrir Metabase
echo ""
echo "=== Metabase dispo sur http://localhost:3000 ==="
echo "    (premier lancement : configurer le compte admin, puis connecter la base 'ledcockpit')"
if command -v open &>/dev/null; then open "http://localhost:3000"
elif command -v xdg-open &>/dev/null; then xdg-open "http://localhost:3000"; fi

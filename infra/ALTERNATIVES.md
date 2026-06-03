# Outils de visualisation — options 100 % gratuites / open-source

Tu n'es pas lié à Metabase. Les 3 options ci-dessous sont **libres et gratuites en auto-hébergé**
(aucune licence). Toutes lisent la même base Postgres (`ledcockpit`) alimentée par `etl.py`.

| Outil | Licence | Pour qui / quand |
|---|---|---|
| **Metabase** (Community) | AGPL v3 | **Recommandé** — le plus simple pour des managers, dashboards + filtres + alertes. Gratuit auto-hébergé (seul le cloud/Pro est payant). |
| **Apache Superset** | Apache 2.0 | Licence la plus permissive, très puissant (SQL Lab, graphes avancés), un peu plus technique. |
| **Grafana** | AGPL v3 | Idéal pour le suivi temps réel / burn-up + **alerting** (mail/Slack) si la cadence baisse. |

## Variante Apache Superset (au lieu de Metabase)
Remplacer le service `metabase` du `docker-compose.yml` par :
```yaml
  superset:
    image: apache/superset:latest
    container_name: led_superset
    restart: unless-stopped
    depends_on: [db]
    environment:
      SUPERSET_SECRET_KEY: ${SUPERSET_SECRET_KEY:-change-me-long-random}
    ports: ["8088:8088"]
    command: >
      bash -c "superset db upgrade &&
               superset fab create-admin --username admin --firstname A --lastname B --email a@b.c --password admin &&
               superset init &&
               superset run -h 0.0.0.0 -p 8088 --with-threads"
```
Puis http://localhost:8088 → ajouter la base `postgresql://led:...@db:5432/ledcockpit`.

## Variante Grafana (suivi + alertes)
```yaml
  grafana:
    image: grafana/grafana-oss:latest
    container_name: led_grafana
    restart: unless-stopped
    depends_on: [db]
    ports: ["3001:3000"]
    volumes: [led_grafana:/var/lib/grafana]
# + ajouter   led_grafana:   sous volumes:
```
http://localhost:3001 → data source Postgres (`db:5432`, `ledcockpit`) → panels sur les vues `v_*`.

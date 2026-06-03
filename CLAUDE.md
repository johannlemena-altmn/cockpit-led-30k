# CLAUDE.md — Cockpit LED 30k (contexte agent)

Lis ce fichier en début de session. Il te donne tout le contexte pour reprendre le sprint, y compris depuis Claude Code sur iPhone.

## But
Aider **Énergie Responsable** (intermédiaire CEE) à atteindre **30 000 LED déposées / mois** (fiche **BAT-EQ-127**, secteur entrepôts ; délégataire iSolidarité ; objectif 1 500/j ; prime 200 €/pers).

## Diagnostic clé (déjà établi, données réelles Pixel CRM)
- **~196 177 LED déjà signées** (×6,5 l'objectif) → le frein n'est PAS le stock, mais le **débit de traitement** (contrôle→dépôt) + la **pose** qui traîne (60-75% au lieu de ≥95%).
- ~5 280 dossiers signés, ~37 LED/dossier (méd. 30, max 459), 13,0 M€ prime, secteur quasi 100% « Entrepôts ».

## 🔒 RÈGLE ABSOLUE — PII / données client
- **Ne JAMAIS commiter de données client.** Déjà gitignoré : `data/`, `*.csv`, `*.xlsx`, `*.pdf`, `Dashboard_LED_interactif.html`, `Dashboard_LED_MVP.html`.
- Avant tout commit : scanner les fichiers suivis (SIRET 14 chiffres, noms clients) et bloquer si match.
- Travailler sur des **copies**, jamais sur un document d'origine.

## Structure
- `build_dashboard_interactive.py` / `build_dashboard_mvp.py` : génèrent les dashboards depuis `data/*.csv`.
- `build_xlsx.py` : cockpit Excel (seeds anonymisés).
- `Note_Plan_30k_LED.html` : note de process (diagnostic, leviers, chaîne, conformité, checklist v2).
- `infra/` : stack auto-hébergée Postgres + Metabase (gratuit/OSS) — alternatives Superset/Grafana dans `infra/ALTERNATIVES.md`.

## Régénérer un dashboard (quand un nouvel export CRM est dispo)
1. Mettre l'export Pixel (« eq 127 pour liste ») dans `data/` (ou me l'uploader dans la session).
2. `pip install pandas openpyxl` puis `python build_dashboard_interactive.py` (et/ou `build_dashboard_mvp.py`, `build_xlsx.py`).
3. Ouvrir le HTML généré (local — non commité).

## Limite depuis iPhone
L'extraction depuis le CRM Pixel nécessite une session navigateur + l'extension → **impossible depuis le tél**. Donc : un poste de bureau dépose le CSV, ou tu **uploades le CSV** dans la session Claude Code, puis « régénère ».

## Sprint — prochaines étapes (backlog)
- **S0 (feed enrichi statut/pose/responsable)** : via support Pixel (corriger la persistance du modèle d'export « Dashboard LED (Claude) » qui ne sauve pas les colonnes → export 500), **ou** un script d'agrégats-only sur l'endpoint `Fiche/Recherche?handler=GetBody_ServerSide` (opération BAT-EQ-127 = `Search.BaremeMultiple`) qui ne renvoie que des totaux (pas de PII).
- **S1** : brancher l'ETL (`infra/etl.py`) → Postgres → dashboards Metabase (manager + pôles) ; activer les vues avancées dans `infra/sql/views.sql`.
- **S2** : déployer la stack Docker (auto-hébergé) + refresh 15-30 min (`infra/refresh.sh`).
- **S3 (option)** : routine Claude (résumé quotidien) + MCP (questions en langage naturel).

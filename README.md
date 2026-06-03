# Cockpit LED — Objectif 30 000 (Énergie Responsable)

Outils pour piloter l'objectif **30 000 LED déposées / mois** : dashboard, ETL, infra de visualisation, note de process. Conçu pour être **opérable depuis Claude Code sur iPhone** via ce dépôt Git.

> ⚠️ **RÈGLE PII — aucune donnée client dans Git.** Les exports CRM, CSV, xlsx, PDF et dashboards rendus (qui embarquent SIRET / noms / adresses) sont dans `.gitignore`. Ce dépôt ne contient **que du code et de la doc**. On ne commit jamais le dossier `data/`.

## 📱 Piloter depuis Claude Code sur iPhone
1. Ouvre ce dépôt dans **Claude Code (mobile)** (connecté à ton GitHub).
2. Tu peux alors, depuis le téléphone, demander à Claude de :
   - modifier / améliorer les dashboards et la note (`build_*.py`, `Note_Plan_30k_LED.html`) ;
   - faire évoluer l'infra (`infra/` : Postgres + Metabase/Superset, vues, refresh) ;
   - régénérer les livrables.
3. **Alimenter en données** (la seule étape qui exige le CRM, impossible depuis le tél sans session Pixel) :
   - soit un poste de bureau dépose l'export Pixel dans `data/` (ou via la tâche planifiée `infra/refresh.sh`) ;
   - soit tu **téléverses le CSV** directement dans la session Claude Code, puis : « régénère le dashboard ».
4. **Visualiser** : régénère le HTML et ouvre-le ; ou utilise l'infra Metabase/Superset auto-hébergée.

## Contenu
| Élément | Rôle |
|---|---|
| `build_dashboard_interactive.py` | Génère le dashboard **interactif** (filtres live) depuis l'export `data/*.csv` |
| `build_dashboard_mvp.py` | Génère la vue MVP (KPIs + tendances) |
| `build_xlsx.py` | Génère le **cockpit Excel** (Dashboard/Pipeline/Paramètres) — seeds anonymisés |
| `Note_Plan_30k_LED.html` | Note de process 1 page (diagnostic, leviers, chaîne, conformité, checklist v2) |
| `infra/` | Stack auto-hébergée : Postgres + **Metabase** (ou Superset) + ETL + refresh 15-30 min |
| `README_mode_emploi.md` | Mode d'emploi du cockpit Excel |

## Démarrage rapide (poste de bureau)
```bash
pip install pandas openpyxl
# 1) déposer l'export Pixel "eq 127 pour liste" dans data/
python build_dashboard_interactive.py   # -> Dashboard_LED_interactif.html (local, non commité)
python build_dashboard_mvp.py           # -> Dashboard_LED_MVP.html
python build_xlsx.py                    # -> Plan_30k_LED_Juin.xlsx
# 2) infra dataviz : voir infra/README.md (docker compose up -d)
```

## Outil de visualisation — 100 % gratuit / open-source
- **Metabase** édition *Community* (AGPL) : **gratuit en auto-hébergé** (le payant = cloud/Pro uniquement). Le plus simple pour les managers.
- Alternatives libres : **Apache Superset** (Apache 2.0), **Grafana** (AGPL, alerting), **Redash**.
- `infra/` fournit Metabase par défaut + une variante Superset.

## État (sprints)
- ✅ Données confirmées : **~196 177 LED signées** (×6,5 l'objectif) → le frein = débit + pose, pas le stock.
- ✅ Dashboard interactif + cockpit Excel + note + infra.
- ⏳ S0 : feed enrichi statut/pose/responsable — via support Pixel **ou** reverse de l'endpoint `Fiche/Recherche?handler=GetBody_ServerSide` (op BAT-EQ-127 = `Search.BaremeMultiple`).
- ⏳ S1/S2 : Metabase/Superset + refresh 15-30 min.

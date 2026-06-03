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
4. **Visualiser sans données** : ouvre directement le `demo_dashboard.html` via l'URL githack (agrégats anonymisés, toujours disponible).
5. **Résumé quotidien** : GitHub Actions génère automatiquement `daily_summary.html` chaque matin lun.–ven. à 07h00 Paris. Récupérable dans l'onglet Actions → dernier run → artifact `daily-summary`.
6. **Visualiser avec données** : régénère le HTML et ouvre-le ; ou utilise l'infra Metabase/Superset auto-hébergée.

## Voir sur iPhone (maintenant)

Aucune installation requise — ouvre simplement ce lien :

**https://raw.githack.com/johannlemena-altmn/cockpit-led-30k/main/demo_dashboard.html**

Dashboard mobile-first (agrégats anonymisés, zéro PII). Mis à jour à chaque commit sur `main`.

> Pour activer GitHub Pages en plus : Settings → Pages → Source → GitHub Actions (workflow `pages.yml` déjà en place).

## Contenu
| Élément | Rôle |
|---|---|
| `build_dashboard_interactive.py` | Génère le dashboard **interactif** (filtres live) depuis l'export `data/*.csv` |
| `build_dashboard_mvp.py` | Génère la vue MVP (KPIs + tendances) |
| `build_xlsx.py` | Génère le **cockpit Excel** (Dashboard/Pipeline/Paramètres) — seeds anonymisés |
| `demo_dashboard.html` | Dashboard **mobile-first** (agrégats anonymisés, zéro PII) — commité, URL publique githack |
| `daily_summary.py` | Génère un résumé HTML mobile chaque matin (KPIs + alertes + recommandation) |
| `Note_Plan_30k_LED.html` | Note de process 1 page (diagnostic, leviers, chaîne, conformité, checklist v2) |
| `infra/` | Stack auto-hébergée : Postgres + **Metabase** (ou Superset) + ETL + refresh 15-30 min |
| `README_mode_emploi.md` | Mode d'emploi du cockpit Excel |
| `.github/workflows/pages.yml` | Déploie GitHub Pages à chaque push sur `main` |
| `.github/workflows/daily_summary.yml` | Cron lun.–ven. 07h00 Paris — génère le résumé quotidien (artifact 7 j) |

## Démarrage rapide (poste de bureau)
```bash
pip install pandas openpyxl
# 1) déposer l'export Pixel "eq 127 pour liste" dans data/
python build_dashboard_interactive.py   # -> Dashboard_LED_interactif.html (local, non commité)
python build_dashboard_mvp.py           # -> Dashboard_LED_MVP.html
python build_xlsx.py                    # -> Plan_30k_LED_Juin.xlsx
# 2) résumé quotidien (local)
python daily_summary.py                 # -> daily_summary.html (local, non commité)
# 3) infra dataviz : voir infra/README.md (docker compose up -d)
```

## Outil de visualisation — 100 % gratuit / open-source
- **Metabase** édition *Community* (AGPL) : **gratuit en auto-hébergé** (le payant = cloud/Pro uniquement). Le plus simple pour les managers.
- Alternatives libres : **Apache Superset** (Apache 2.0), **Grafana** (AGPL, alerting), **Redash**.
- `infra/` fournit Metabase par défaut + une variante Superset.

## État (sprints)
- ✅ **S0 partiel** : diagnostic établi — ~196 177 LED signées (×6,5 l'objectif) → frein = débit + pose, pas le stock.
- ✅ Dashboard interactif + cockpit Excel + note + infra.
- ✅ **Mobile** : `demo_dashboard.html` opérationnel, URL githack publique.
- ✅ **S3** : résumé quotidien `daily_summary.py` + workflow GitHub Actions (cron 07h00 Paris lun.–ven.).
- ⏳ **S0 feed live** : nécessite support Pixel (persistance modèle export) **ou** secret `PIXEL_EXPORT_URL` pour l'endpoint `Fiche/Recherche?handler=GetBody_ServerSide` (op BAT-EQ-127 = `Search.BaremeMultiple`).
- ⏳ **S1** : ETL (`infra/etl.py`) → Postgres → Metabase (manager + pôles) ; infra prête, pas encore branchée.
- ⏳ **S2** : Docker stack (code prêt, pas encore déployé) + refresh 15-30 min (`infra/refresh.sh`).

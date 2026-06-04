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
- `betool_summary.py` : lit l'export BETOOL « ENERGIE RESPONSABLE » (CRM, ~16 400 lignes) → pipeline opérationnel (Installation→Audit→Signature→Modif→Déposé) + quickwins. Réf dossier = n° Waresito (non-PII).
- `confirme_summary.py` : lit la **LISTE EQ 127 « CONFIRME »** (fichier dépôt CEE officiel, ~5 440 ops) → bloc `confirmes` (vue centrale : LED confirmées, prime, réfs `ERS-YYYY-XXXX` cherchables, secteurs). Option `--ary` pour le **TABLEAU ARY** (autres secteurs, alerte photos manquantes). **Agrégats anonymisés uniquement** + garde-fou PII intégré.
- `demo_dashboard.html` : dashboard mobile-first (agrégats anonymisés, zéro PII) — **commité**, visible publiquement. Inclut : **barre de navigation sticky** (pills Actions/Confirmés/Audit/Pipeline/Historique + scrollspy), **carte delta colorée** en haut (lit `public_data.json.delta`, tuiles vert/rouge + verdict), légende prios + ligne « impact total débloquable », tour guidé.
- `daily_summary.py` : génère un résumé HTML mobile (KPIs + alertes + recommandation) ; exécuté automatiquement par GitHub Actions.
- `Note_Plan_30k_LED.html` : note de process (diagnostic, leviers, chaîne, conformité, checklist v2).
- `infra/` : stack auto-hébergée Postgres + Metabase (gratuit/OSS) — alternatives Superset/Grafana dans `infra/ALTERNATIVES.md`.
- `snapshot.py` : archive un instantané quotidien léger (~8 Ko, **zéro PII**) depuis `public_data.json` → `history/YYYY-MM-DD.json` (agrégats par statut + **top 30 prios** du jour, réfs Waresito/LE-XXXX, installs internes = `#N · interne`). Régénère aussi `history/timeseries.json` (série compacte 1 ligne/jour pour les graphes) + `history/index.json`. **Calcule un bloc `delta` « depuis la dernière mise à jour »** (intra-jour si ré-export le même jour, sinon J-1) : déposés (n/LED), taux pose, stock actif, modifs audit, confirmés ; réinjecté dans `public_data.json` pour le cockpit. **Idempotent** via signature des métriques (`cur_sig`) → un re-run / le cron quotidien ne remet PAS le delta à zéro. Garde-fou PII intégré. Lancé auto en fin de `update_dashboard.sh` **et** par le workflow `snapshot.yml`.
- `history_dashboard.html` : page dédiée évolution **jour / semaine / mois** — vue macro (KPIs + deltas, taux de pose par période, évolution pipeline par statut avec sparklines) + vue micro (top 20 prios d'une journée sélectionnable). Lit `history/*.json`. Lien depuis `demo_dashboard.html`.
- `history/` : dossier versionné des snapshots (commité, anonymisé). Accumulation naturelle (~1,8 Mo/an).
- `.github/workflows/pages.yml` : déploie GitHub Pages (nécessite 1 config manuelle : Settings → Pages → Source → GitHub Actions).
- `.github/workflows/snapshot.yml` : archive l'historique à chaque push modifiant `public_data.json` + filet de sécurité quotidien 20h00 Paris. Commit auto de `history/`.
- `.github/workflows/daily_summary.yml` : cron lun.–ven. 07h00 Paris, upload artifact 7 jours.

## Sources de données (3 systèmes, vues complémentaires)
La chaîne s'appuie sur 3 sources distinctes — bien les distinguer :

1. **BETOOL CRM — board « ENERGIE RESPONSABLE »** (`application.betool.fr/board/energie-responsable/led`, ~16 400 lignes).
   Base de traitement remplie par les commerciaux puis complétée jusqu'à « Déposé ».
   Export `.xlsx` → `betool_summary.py` → bloc `pipeline` (étapes opérationnelles + quickwins).
2. **LISTE EQ 127 « CONFIRME »** (CSV format dépôt CEE/EMMY, ~5 440 ops). **Vue centrale de suivi.**
   Col 0 = ID interne, **col 5 = réf `ERS-YYYY-XXXX-N`** (identifiant cherchable, non nominatif), col 36 = nb LED, col 7 = prime.
   → `confirme_summary.py` → bloc `confirmes` (158k LED confirmées, ~11,4 M€, couverture ERS ~100 %).
   - **TABLEAU ARY** (`--ary`) : ~1 040 dossiers « Autres secteurs » (animaux, bâtiment ouvert, <15 ans). Alerte = ~90 % sans photos → bloc `autres_secteurs`.
3. **BETOOL auditeur — board « PRIME EVOLUTION »** (`application.betool.fr/board/prime-evolution/led`, ~2 760 lignes). ⏳ pas encore branché.
   Statuts audit : `Étude prête` (~2 400, prêtes à valider/corriger), `Modification à faire` (~190 = vrais blocages audit), `Étude en cours`, `Étude à réaliser`. Clé = ticket `LE-XXXX`.
   **Pour l'intégrer** : exporter ce board en `.xlsx`/CSV (colonnes : `Clé ticket`, `Status LED`, `Jetons`/nb LED, `Last updateTime`), puis créer `auditeur_summary.py` (calque de `betool_summary.py` ; mapper `Status LED`→étapes audit, réf = `LE-XXXX`). Cible : un bloc `audit_pipeline` avec les ~190 « Modification à faire » comme quickwin prioritaire en amont du CRM.

## Régénérer un dashboard (quand un nouvel export CRM est dispo)
1. Mettre l'export Pixel (« eq 127 pour liste ») dans `data/` (ou me l'uploader dans la session).
2. `pip install pandas openpyxl` puis `python build_dashboard_interactive.py` (et/ou `build_dashboard_mvp.py`, `build_xlsx.py`).
3. Ouvrir le HTML généré (local — non commité).
4. Pour le résumé quotidien : `python daily_summary.py` → génère `daily_summary.html` (local). En production, GitHub Actions l'exécute automatiquement lun.–ven. à 07h00 Paris et l'upload comme artifact (7 jours).

## Limite depuis iPhone
L'extraction depuis le CRM Pixel nécessite une session navigateur + l'extension → **impossible depuis le tél**. Donc : un poste de bureau dépose le CSV, ou tu **uploades le CSV** dans la session Claude Code, puis « régénère ».

## URLs publiques
- **Demo dashboard** (agrégats anonymisés, mobile-first) : https://raw.githack.com/johannlemena-altmn/cockpit-led-30k/main/demo_dashboard.html
- **GitHub Pages** (à activer) : Settings → Pages → Source → GitHub Actions → le workflow `pages.yml` se charge du déploiement.

## Sprint — prochaines étapes (backlog)
- **S0 partiel ✅** : diagnostic établi, agrégats connus (196 177 LED signées, 5 280 dossiers, 13 M€).
- **S0 feed live ⏳** : via support Pixel (corriger la persistance du modèle d'export « Dashboard LED (Claude) » qui ne sauve pas les colonnes → export 500), **ou** `pixel_api.py` — script stdlib-only qui interroge `Fiche/Recherche?handler=GetBody_ServerSide` (opération BAT-EQ-127 = `Search.BaremeMultiple`) et écrit `public_data.json` (agrégats, zéro PII).
  - Variables d'env requises (fichier `.env` ou export shell) :
    - `PIXEL_BASE_URL` : URL de base du CRM Pixel (ex: `https://votre-instance.pixel-crm.fr`)
    - `PIXEL_SESSION_COOKIE` : valeur du header `Cookie` copiée depuis DevTools (F12 → Network) après connexion à Pixel
    - `PIXEL_REFERER` : (optionnel) URL de la page de recherche pour le header Referer
  - Usage : `python pixel_api.py` (live) ou `python pixel_api.py --dry-run` (inspecter les requêtes sans les envoyer).
  - Si la réponse est non reconnue, le script affiche les clés JSON reçues + les 500 premiers chars → copier le payload exact depuis DevTools et l'ajouter dans `CANDIDATE_PAYLOADS` dans `pixel_api.py`.
- **S1 ⏳** : brancher l'ETL (`infra/etl.py`) → Postgres → dashboards Metabase (manager + pôles) ; activer les vues avancées dans `infra/sql/views.sql`.
- **S2 ⏳** : déployer la stack Docker (auto-hébergé) + refresh 15-30 min (`infra/refresh.sh`). Code prêt, pas encore déployé.
- **S3 ✅** : résumé quotidien `daily_summary.py` + workflow GitHub Actions (`daily_summary.yml`, cron 07h00 Paris lun.–ven.).
- **Board auditeur ✅** : `auditeur_summary.py` branché sur l'export Prime Evolution (2 764 dossiers — 179 « Modification à faire », 2 408 « Étude prête »). ⚠ Cette source n'a PAS de nb LED (col `Jetons` = emoji ♾️/🪙) → on agrège les dossiers + cellules (zones). Bloc `audit_pipeline` affiché dans `demo_dashboard.html`. Réf = `LE-XXXX`. Lancer via `--auditeur data/export.xlsx` (ou `--inspect` pour vérifier les colonnes).

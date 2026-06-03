# Cockpit LED — infra auto-hébergée (Docker)

Stack open-source, ~0 € de licence : **Postgres** (entrepôt) + **Metabase** (dashboards multi-pôles, filtres, accès par rôle, alertes) + **ETL Python** (Pixel CSV → Postgres) + **refresh planifié** (15-30 min).

## 0. Prérequis (à faire par toi / l'IT)
- Installer **Docker Desktop**.
- Avoir **Python 3.9+** + `pip install -r requirements.txt`.
- (Création de comptes Metabase = action humaine, je ne le fais pas à ta place.)

## 1. Lancer la stack
```bash
cp .env.example .env          # adapter le mot de passe
docker compose up -d          # démarre Postgres + Metabase
```
- Metabase : http://localhost:3000 → créer le compte admin → ajouter une **source de données** Postgres
  (hôte `localhost`, port `5432`, base `ledcockpit`, user/pass du .env).

## 2. Charger les données
Déposer l'export Pixel (« eq 127 pour liste ») dans `../data/`, puis :
```bash
pip install -r requirements.txt
python etl.py ../data          # crée tables `dossier` + `ligne_chantier`
psql -h localhost -U led -d ledcockpit -f sql/views.sql   # crée les vues
```
L'ETL **détecte automatiquement** les colonnes ; il sait déjà mapper statut / dépôt / pose /
responsable s'ils sont présents (cf. `COLMAP` dans `etl.py`).

## 3. Construire les dashboards (dans Metabase)
- **Manager** : `v_kpi` (LED signées / à déposer / déposées), burn-up vs 1500/j, `v_signe_par_mois`.
- **Pôle Contrôle / Valorisation** : funnel par statut, par responsable (vues avancées).
- **Pôle Pose** : `v_pose` (taux de pose réel), liste des dossiers à relancer.
- Filtres par secteur / responsable / période. Accès par rôle = permissions Metabase.

## 4. Rafraîchissement auto (15-30 min)
```bash
chmod +x refresh.sh
crontab -e
# */20 * * * * /CHEMIN/infra/refresh.sh >> /tmp/led_refresh.log 2>&1
```

## État actuel & limite connue
- L'export **« eq 127 pour liste »** alimente déjà : LED, prime, cumac, secteur, signature → KPI + tendances OK.
- **Statut / dépôt / pose / responsable** : pas dans cet export. La création d'un modèle Pixel dédié
  a échoué (bug Pixel : le « format » de colonnes ne se persiste pas → export en erreur 500).
  → **2 voies fiables** : (a) ticket support Pixel pour activer la persistance du modèle ;
  (b) reverse de l'endpoint JSON de recherche (`?handler=Search`) qui expose déjà
  Statut + Intervenants + cumac — c'est aussi la clé du quasi-temps-réel sans ré-export.
- Dès que ce feed enrichi arrive, décommenter les vues avancées dans `sql/views.sql`.

## Couche Claude (option, votre licence)
- **Routine planifiée** : pull + ETL + résumé quotidien auto (mail/Slack).
- **MCP** sur la base : questions en langage naturel (« combien de LED prêtes à déposer ? »).

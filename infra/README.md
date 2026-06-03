# Cockpit LED — infra auto-hébergée (Docker)

Stack open-source, ~0 € de licence : **Postgres** (entrepôt) + **Metabase** (dashboards multi-pôles, filtres, accès par rôle, alertes) + **ETL Python** (Pixel CSV → Postgres) + **refresh planifié** (15-30 min).

## 0. Prérequis (à faire par toi / l'IT)
- Installer **Docker Desktop**.
- Avoir **Python 3.9+** + `pip install -r requirements.txt`.
- (Création de comptes Metabase = action humaine, je ne le fais pas à ta place.)

## 1. Démarrage en une commande (point d'entrée principal)

Déposer l'export Pixel (« eq 127 pour liste ») dans `../data/`, puis :
```bash
cp .env.example .env          # adapter le mot de passe (une seule fois)
./infra/start.sh              # ou : ./infra/start.sh /chemin/vers/dossier_data
```

`start.sh` fait tout en séquence :
1. `docker compose up -d` — démarre Postgres + Metabase.
2. Attend que Postgres soit prêt (max 30 s).
3. `python etl.py <data>` — charge les tables et **applique automatiquement** `sql/views.sql`.
4. Ouvre http://localhost:3000 dans le navigateur (macOS / Linux).

### Connexion Metabase (première fois)

Au premier lancement, l'assistant d'onboarding Metabase s'affiche sur http://localhost:3000 :

1. **Créer un compte admin** — choisir un e-mail + mot de passe (compte local, aucun abonnement requis).
2. **Ajouter une source de données** — choisir « PostgreSQL » et renseigner :
   - Hôte : `db` (si Metabase tourne dans Docker) ou `localhost` (si Metabase est externe)
   - Port : `5432`
   - Base de données : `ledcockpit`
   - Utilisateur : `led` (ou la valeur de `PGUSER` dans `.env`)
   - Mot de passe : `changeme` (ou la valeur de `PGPASSWORD` dans `.env`)
3. Cliquer **Tester la connexion**, puis **Suivant** pour terminer l'onboarding.
4. Les tables `dossier`, `ligne_chantier` et les vues `v_kpi`, `v_signe_par_mois`, etc. sont immédiatement disponibles pour créer des questions / dashboards.

> **Note** : pour les lancements suivants, `start.sh` suffit — l'onboarding ne s'affiche qu'une fois.

## 2. Charger les données manuellement (optionnel)
Si tu veux relancer l'ETL seul sans redémarrer Docker :
```bash
pip install -r requirements.txt
python etl.py ../data          # crée tables `dossier` + `ligne_chantier` + applique les vues
```
L'ETL **détecte automatiquement** les colonnes ; il sait déjà mapper statut / dépôt / pose /
responsable s'ils sont présents (cf. `COLMAP` dans `etl.py`).
Les vues `sql/views.sql` sont appliquées automatiquement à la fin de chaque exécution ETL.

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

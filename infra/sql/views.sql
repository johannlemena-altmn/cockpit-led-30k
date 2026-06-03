-- Vues Metabase — Cockpit LED (à exécuter dans la base ledcockpit après le 1er ETL)
-- Robustes avec le seul export "eq 127 pour liste". Les vues statut/pose/responsable
-- s'activent automatiquement dès que le feed enrichi (statut, dépôt, pose) est branché.

-- KPI globaux
CREATE OR REPLACE VIEW v_kpi AS
SELECT
  COUNT(*)                                   AS nb_dossiers,
  COUNT(*) FILTER (WHERE signe)              AS nb_signes,
  COALESCE(SUM(led) FILTER (WHERE signe),0)  AS led_signees,
  COALESCE(SUM(led) FILTER (WHERE depose),0) AS led_deposees,
  COALESCE(SUM(led) FILTER (WHERE signe AND NOT depose),0) AS led_a_deposer,
  ROUND(AVG(led) FILTER (WHERE signe)::numeric,1) AS led_moy_dossier,
  COALESCE(SUM(prime) FILTER (WHERE signe),0) AS prime_signee
FROM dossier;

-- LED signées par mois
CREATE OR REPLACE VIEW v_signe_par_mois AS
SELECT to_char(date_signature,'YYYY-MM') AS mois, SUM(led) AS led
FROM dossier WHERE signe AND date_signature IS NOT NULL
GROUP BY 1 ORDER BY 1;

-- Par secteur
CREATE OR REPLACE VIEW v_par_secteur AS
SELECT COALESCE(secteur,'(vide)') AS secteur,
       COUNT(*) AS nb, SUM(led) AS led
FROM dossier WHERE signe GROUP BY 1 ORDER BY led DESC;

-- Répartition par taille de dossier
CREATE OR REPLACE VIEW v_taille_dossier AS
SELECT CASE
         WHEN led<10 THEN '1-9' WHEN led<20 THEN '10-19' WHEN led<30 THEN '20-29'
         WHEN led<50 THEN '30-49' WHEN led<100 THEN '50-99' ELSE '100+' END AS tranche,
       COUNT(*) AS nb_dossiers
FROM dossier WHERE signe AND led>0 GROUP BY 1;

-- ============================================================
-- AVANCÉ — nécessite le feed enrichi (statut / catégorie / pose / responsable).
-- Décommenter une fois ces colonnes présentes dans la table dossier.
-- ============================================================
-- CREATE OR REPLACE VIEW v_funnel_statut AS
--   SELECT statut, COUNT(*) nb, SUM(led) led FROM dossier WHERE signe GROUP BY 1 ORDER BY led DESC;
-- CREATE OR REPLACE VIEW v_funnel_categorie AS
--   SELECT categorie_statut, COUNT(*) nb, SUM(led) led FROM dossier WHERE signe GROUP BY 1;
-- CREATE OR REPLACE VIEW v_par_responsable AS
--   SELECT COALESCE(administrateur,'(non affecté)') resp, COUNT(*) nb,
--          SUM(led) FILTER (WHERE NOT depose) led_en_cours FROM dossier WHERE signe GROUP BY 1;
-- CREATE OR REPLACE VIEW v_pose AS
--   SELECT COUNT(*) FILTER (WHERE pose_terminee) poses_finies,
--          COUNT(*) FILTER (WHERE NOT pose_terminee) poses_en_attente,
--          ROUND(100.0*COUNT(*) FILTER (WHERE pose_terminee)/NULLIF(COUNT(*),0),1) taux_pose_pct
--   FROM dossier WHERE signe AND NOT depose;

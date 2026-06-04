-- Vues Metabase — Cockpit LED (appliquées automatiquement par etl.py)
-- Robustes avec l'export "eq 127 pour liste". Les vues statut/pose/responsable
-- s'activent dès que le feed enrichi est présent dans la table dossier.

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

-- Funnel par statut Pixel (nécessite colonne statut dans dossier)
CREATE OR REPLACE VIEW v_funnel_statut AS
SELECT COALESCE(statut,'(vide)') AS statut,
       COUNT(*) nb, SUM(led) led
FROM dossier WHERE signe GROUP BY 1 ORDER BY led DESC;

-- Funnel par catégorie de statut
CREATE OR REPLACE VIEW v_funnel_categorie AS
SELECT COALESCE(categorie_statut,'(vide)') AS categorie_statut,
       COUNT(*) nb, SUM(led) led
FROM dossier WHERE signe GROUP BY 1;

-- Par responsable (administrateur Pixel)
CREATE OR REPLACE VIEW v_par_responsable AS
SELECT COALESCE(administrateur,'(non affecté)') AS resp,
       COUNT(*) nb,
       SUM(led) FILTER (WHERE NOT depose) AS led_en_cours
FROM dossier WHERE signe GROUP BY 1 ORDER BY led_en_cours DESC NULLS LAST;

-- Taux de pose (depuis dates Pixel)
CREATE OR REPLACE VIEW v_pose AS
SELECT COUNT(*) FILTER (WHERE pose_terminee)       AS poses_finies,
       COUNT(*) FILTER (WHERE NOT pose_terminee)   AS poses_en_attente,
       ROUND(100.0 * COUNT(*) FILTER (WHERE pose_terminee)
             / NULLIF(COUNT(*),0), 1)              AS taux_pose_pct
FROM dossier WHERE signe AND NOT depose AND pose_terminee IS NOT NULL;

-- ============================================================
-- BETOOL — pipeline (actif si la table betool_lead existe)
-- ============================================================

-- Pipeline BETOOL par stage
CREATE OR REPLACE VIEW v_betool_pipeline AS
SELECT
  stage_id,
  COUNT(*)                          AS nb_dossiers,
  COALESCE(SUM(led),0)              AS led_total,
  ROUND(AVG(age_days)::numeric,0)   AS age_moy_jours
FROM betool_lead
GROUP BY stage_id;

-- Zone d'action immédiate (tout sauf en_cours et depose)
CREATE OR REPLACE VIEW v_betool_action AS
SELECT
  COUNT(*)             AS nb_action,
  COALESCE(SUM(led),0) AS led_action,
  ROUND(AVG(age_days)::numeric,0) AS age_moy_jours
FROM betool_lead
WHERE stage_id IN ('attente_audit','attente_signature','modif_audit');

-- KPI BETOOL global (taux de pose depuis pipeline)
CREATE OR REPLACE VIEW v_betool_kpi AS
SELECT
  COUNT(*) AS total_pipeline,
  COUNT(*) FILTER (WHERE stage_id = 'depose')    AS nb_depose,
  COALESCE(SUM(led) FILTER (WHERE stage_id = 'depose'),0) AS led_depose,
  COALESCE(SUM(led),0) AS led_total,
  ROUND(100.0 * COUNT(*) FILTER (WHERE stage_id != 'en_cours')
        / NULLIF(COUNT(*),0), 0)                 AS taux_pose_pct
FROM betool_lead

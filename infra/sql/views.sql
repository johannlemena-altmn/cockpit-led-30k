-- Vues Metabase — Cockpit LED (appliquées automatiquement par etl.py)
-- Vues de base : toujours créées.
-- Vues avancées : créées seulement si les colonnes/tables requises existent.

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
-- AVANCÉ — colonnes optionnelles (statut/responsable/pose)
-- Créées seulement si la colonne existe dans la table dossier.
-- ============================================================

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='dossier' AND column_name='statut') THEN
    EXECUTE $v$
      CREATE OR REPLACE VIEW v_funnel_statut AS
      SELECT COALESCE(statut,'(vide)') AS statut,
             COUNT(*) nb, SUM(led) led
      FROM dossier WHERE signe GROUP BY 1 ORDER BY led DESC
    $v$;
  END IF;
END $$;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='dossier' AND column_name='categorie_statut') THEN
    EXECUTE $v$
      CREATE OR REPLACE VIEW v_funnel_categorie AS
      SELECT COALESCE(categorie_statut,'(vide)') AS categorie_statut,
             COUNT(*) nb, SUM(led) led
      FROM dossier WHERE signe GROUP BY 1
    $v$;
  END IF;
END $$;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='dossier' AND column_name='administrateur') THEN
    EXECUTE $v$
      CREATE OR REPLACE VIEW v_par_responsable AS
      SELECT COALESCE(administrateur,'(non affecté)') AS resp,
             COUNT(*) nb,
             SUM(led) FILTER (WHERE NOT depose) AS led_en_cours
      FROM dossier WHERE signe GROUP BY 1 ORDER BY led_en_cours DESC NULLS LAST
    $v$;
  END IF;
END $$;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='dossier' AND column_name='pose_terminee') THEN
    EXECUTE $v$
      CREATE OR REPLACE VIEW v_pose AS
      SELECT
        COUNT(*) FILTER (WHERE pose_terminee = TRUE)  AS poses_finies,
        COUNT(*) FILTER (WHERE pose_terminee = FALSE) AS poses_en_attente,
        ROUND(100.0 * COUNT(*) FILTER (WHERE pose_terminee = TRUE)
              / NULLIF(COUNT(*),0), 1)                AS taux_pose_pct
      FROM dossier WHERE signe AND NOT depose AND pose_terminee IS NOT NULL
    $v$;
  END IF;
END $$;

-- ============================================================
-- BETOOL — créées seulement si la table betool_lead existe
-- ============================================================

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables
             WHERE table_name='betool_lead') THEN
    EXECUTE $v$
      CREATE OR REPLACE VIEW v_betool_pipeline AS
      SELECT stage_id,
             COUNT(*)                        AS nb_dossiers,
             COALESCE(SUM(led),0)            AS led_total,
             ROUND(AVG(age_days)::numeric,0) AS age_moy_jours
      FROM betool_lead GROUP BY stage_id
    $v$;
    EXECUTE $v$
      CREATE OR REPLACE VIEW v_betool_action AS
      SELECT COUNT(*)             AS nb_action,
             COALESCE(SUM(led),0) AS led_action,
             ROUND(AVG(age_days)::numeric,0) AS age_moy_jours
      FROM betool_lead
      WHERE stage_id IN ('attente_audit','attente_signature','modif_audit')
    $v$;
    EXECUTE $v$
      CREATE OR REPLACE VIEW v_betool_kpi AS
      SELECT COUNT(*) AS total_pipeline,
             COUNT(*) FILTER (WHERE stage_id = 'depose')           AS nb_depose,
             COALESCE(SUM(led) FILTER (WHERE stage_id = 'depose'),0) AS led_depose,
             COALESCE(SUM(led),0)                                   AS led_total,
             ROUND(100.0 * COUNT(*) FILTER (WHERE stage_id != 'en_cours')
                   / NULLIF(COUNT(*),0), 0)                        AS taux_pose_pct
      FROM betool_lead
    $v$;
  END IF;
END $$;

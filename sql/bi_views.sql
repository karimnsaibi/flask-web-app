-- Star schema exposed to Power BI (DirectQuery) as views in the `bi` schema.
-- Views read the live operational tables, so every KPI logged in the app
-- is visible in Power BI at the next (auto) page refresh.
--
--   dim_date ─┐
--   dim_site ─┼─< fact_kpi_daily
--             └─< fact_ticket >── dim_user (engineer / technician)

CREATE SCHEMA IF NOT EXISTS bi;

-- Calendar covering all KPI and ticket dates up to today.
CREATE OR REPLACE VIEW bi.dim_date AS
WITH bounds AS (
    SELECT LEAST(
               COALESCE((SELECT MIN(date) FROM kpi_stats), CURRENT_DATE),
               COALESCE((SELECT MIN(created_at)::date FROM tickets), CURRENT_DATE)
           ) AS first_day
)
SELECT d::date                              AS date,
       EXTRACT(YEAR FROM d)::int            AS year,
       EXTRACT(QUARTER FROM d)::int         AS quarter,
       EXTRACT(MONTH FROM d)::int           AS month_number,
       TO_CHAR(d, 'Mon YYYY')               AS month_label,
       TO_CHAR(d, 'YYYY-MM')                AS year_month,
       EXTRACT(ISODOW FROM d)::int          AS weekday_number,   -- 1 = Monday
       TO_CHAR(d, 'Dy')                     AS weekday_label,
       EXTRACT(ISODOW FROM d) IN (6, 7)     AS is_weekend,
       DATE_TRUNC('week', d)::date          AS week_start
FROM bounds, generate_series(bounds.first_day, CURRENT_DATE, INTERVAL '1 day') AS d;

CREATE OR REPLACE VIEW bi.dim_site AS
SELECT id                         AS site_id,
       code                       AS site_code,
       site_name,
       region                     AS governorate,
       delegation,
       supplier,
       access                     AS access_type,
       antenna                    AS antenna_type,
       surface                    AS installation_type,
       NULLIF(hba, '')::numeric   AS antenna_height_m,
       NULLIF(x, '')::numeric     AS latitude,
       NULLIF(y, '')::numeric     AS longitude
FROM site;

CREATE OR REPLACE VIEW bi.dim_user AS
SELECT id AS user_id, name AS user_name, profile
FROM users;

-- Grain: one site, one day.
CREATE OR REPLACE VIEW bi.fact_kpi_daily AS
SELECT k.id                     AS kpi_id,
       k.site_id,
       k.date,
       k.taux_blocage           AS blocking_rate_pct,
       k.taux_coupure           AS drop_rate_pct,
       k.taux_disponibilite     AS availability_pct,
       k.trafic_voix_erlang     AS voice_traffic_erl,
       k.trafic_data_go         AS data_traffic_gb,
       k.trafic_volte_go        AS volte_traffic_gb,
       k.logged_at,
       (k.taux_disponibilite < 99.0)                         AS availability_breach,  -- SLA: 99 %
       (k.taux_blocage > 2.0 OR k.taux_coupure > 1.0)        AS quality_breach
FROM kpi_stats k;

-- Grain: one ticket (with its first intervention, if any).
CREATE OR REPLACE VIEW bi.fact_ticket AS
SELECT t.id                                   AS ticket_id,
       t.site_id,
       t.engineer_id,
       t.technician_id,
       t.title                                AS fault_type,
       t.priority,
       t.status,
       t.created_at,
       t.created_at::date                     AS created_date,
       i.date                                 AS resolved_at,
       ROUND((EXTRACT(EPOCH FROM (i.date - t.created_at)) / 3600.0)::numeric, 1)
                                              AS resolution_hours,
       i.engineer_rating,
       (t.status IN ('Open', 'In Progress'))  AS is_open
FROM tickets t
LEFT JOIN LATERAL (
    SELECT date, engineer_rating
    FROM interventions
    WHERE ticket_id = t.id
    ORDER BY date
    LIMIT 1
) i ON TRUE;

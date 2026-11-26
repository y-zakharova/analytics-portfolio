-- =====================================================================
-- Retention & LTV by acquisition channel: SQL version of the analysis
-- Fictional subscription app "Driftly". All data is simulated.
--
-- Tables
--   users(user_id, install_date, channel, platform, last_active_day, is_censored)
--   transactions(user_id, charge_date, renewal_number, gross_amount_usd)
--   marketing_spend(month, channel, installs, spend_usd)
--
-- Dialect: standard SQL with CTEs and window functions (tested in DuckDB;
-- runs in PostgreSQL / BigQuery / ClickHouse with minor date-function changes).
--
-- To run locally with DuckDB (from this folder):
--   CREATE VIEW users           AS SELECT * FROM 'data/users.csv.gz';
--   CREATE VIEW transactions    AS SELECT * FROM 'data/transactions.csv';
--   CREATE VIEW marketing_spend AS SELECT * FROM 'data/marketing_spend.csv';
--
-- Snapshot date of the data: 2026-03-31. Net revenue = gross × 0.70 (store fee).
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Rolling retention by channel (D1, D7, D30, D90)
--    "Active on day N or later". Only users at least N days old count,
--    otherwise young users would pull retention down.
-- ---------------------------------------------------------------------
WITH u AS (
    SELECT channel, last_active_day,
           DATE '2026-03-31' - install_date AS age_days
    FROM users
)
SELECT
    channel,
    ROUND(AVG(CASE WHEN last_active_day >= 1  THEN 1.0 ELSE 0 END) FILTER (WHERE age_days >= 1),  3) AS d1,
    ROUND(AVG(CASE WHEN last_active_day >= 7  THEN 1.0 ELSE 0 END) FILTER (WHERE age_days >= 7),  3) AS d7,
    ROUND(AVG(CASE WHEN last_active_day >= 30 THEN 1.0 ELSE 0 END) FILTER (WHERE age_days >= 30), 3) AS d30,
    ROUND(AVG(CASE WHEN last_active_day >= 90 THEN 1.0 ELSE 0 END) FILTER (WHERE age_days >= 90), 3) AS d90
FROM u
GROUP BY channel
ORDER BY d90 DESC;


-- ---------------------------------------------------------------------
-- 2. Is retention falling, or is it the channel mix?
--    D30 by install month, next to D30 with January's channel mix held constant.
--    If the two lines diverge, the decline comes from the mix, not the product.
-- ---------------------------------------------------------------------
WITH cohort_channel AS (
    SELECT
        DATE_TRUNC('month', install_date)                               AS cohort,
        channel,
        COUNT(*)                                                        AS installs,
        AVG(CASE WHEN last_active_day >= 30 THEN 1.0 ELSE 0 END)
            FILTER (WHERE DATE '2026-03-31' - install_date >= 30)       AS d30
    FROM users
    GROUP BY 1, 2
),
with_share AS (
    SELECT *, installs * 1.0 / SUM(installs) OVER (PARTITION BY cohort) AS share
    FROM cohort_channel
),
jan_mix AS (
    SELECT channel, share AS jan_share
    FROM with_share
    WHERE cohort = (SELECT MIN(cohort) FROM with_share)
)
SELECT
    w.cohort,
    ROUND(SUM(w.share * w.d30), 4)       AS d30_actual,
    ROUND(SUM(j.jan_share * w.d30), 4)   AS d30_january_mix,
    ROUND(SUM(w.share * w.d30) - SUM(j.jan_share * w.d30), 4) AS mix_effect
FROM with_share w
JOIN jan_mix j USING (channel)
GROUP BY w.cohort
ORDER BY w.cohort;


-- ---------------------------------------------------------------------
-- 3. Monetization drivers by channel (censoring-aware)
--    conv_30d   : share of installs (30+ days old) that paid within 30 days
--    first_renew: share of first charges followed by a second one
--    later_renew: share of later charges followed by another one
--    A charge counts for renewal only if its next billing date has passed.
-- ---------------------------------------------------------------------
WITH charges AS (
    SELECT
        t.user_id, u.channel, t.charge_date, t.renewal_number,
        t.charge_date - u.install_date AS day_since_install,
        LEAD(t.renewal_number) OVER (PARTITION BY t.user_id ORDER BY t.renewal_number) IS NOT NULL AS renewed
    FROM transactions t
    JOIN users u USING (user_id)
),
conv AS (
    SELECT
        u.channel,
        COUNT(*) AS eligible_installs,
        COUNT(DISTINCT c.user_id) AS payers_30d
    FROM users u
    LEFT JOIN charges c
           ON c.user_id = u.user_id AND c.renewal_number = 0 AND c.day_since_install < 30
    WHERE DATE '2026-03-31' - u.install_date >= 30
    GROUP BY u.channel
),
renew AS (
    SELECT
        channel,
        AVG(CASE WHEN renewed THEN 1.0 ELSE 0 END) FILTER (WHERE renewal_number = 0) AS first_renew,
        AVG(CASE WHEN renewed THEN 1.0 ELSE 0 END) FILTER (WHERE renewal_number > 0) AS later_renew
    FROM charges
    WHERE charge_date + INTERVAL '30 days' <= DATE '2026-03-31'
    GROUP BY channel
)
SELECT
    c.channel,
    ROUND(c.payers_30d * 1.0 / c.eligible_installs, 4) AS conv_30d,
    ROUND(r.first_renew, 4)                            AS first_renew,
    ROUND(r.later_renew, 4)                            AS later_renew
FROM conv c
JOIN renew r USING (channel)
ORDER BY conv_30d DESC;


-- ---------------------------------------------------------------------
-- 4. LTV12, CAC, LTV/CAC and payback by channel
--    LTV12 = conv_30d × net price × expected charges in 12 months,
--    expected charges = 1 + s1 × (1 − s^11) / (1 − s)
--    Payback month = first month where cumulative expected net revenue per install ≥ CAC.
-- ---------------------------------------------------------------------
WITH charges AS (
    SELECT
        t.user_id, u.channel, t.charge_date, t.renewal_number,
        t.charge_date - u.install_date AS day_since_install,
        LEAD(t.renewal_number) OVER (PARTITION BY t.user_id ORDER BY t.renewal_number) IS NOT NULL AS renewed
    FROM transactions t
    JOIN users u USING (user_id)
),
drivers AS (
    SELECT
        u.channel,
        COUNT(DISTINCT c.user_id) * 1.0 / COUNT(DISTINCT u.user_id) AS conv_30d
    FROM users u
    LEFT JOIN charges c
           ON c.user_id = u.user_id AND c.renewal_number = 0 AND c.day_since_install < 30
    WHERE DATE '2026-03-31' - u.install_date >= 30
    GROUP BY u.channel
),
renew AS (
    SELECT
        channel,
        AVG(CASE WHEN renewed THEN 1.0 ELSE 0 END) FILTER (WHERE renewal_number = 0) AS s1,
        AVG(CASE WHEN renewed THEN 1.0 ELSE 0 END) FILTER (WHERE renewal_number > 0) AS s
    FROM charges
    WHERE charge_date + INTERVAL '30 days' <= DATE '2026-03-31'
    GROUP BY channel
),
cac AS (
    SELECT channel, SUM(spend_usd) / SUM(installs) AS cac
    FROM marketing_spend
    GROUP BY channel
),
ltv AS (
    SELECT
        d.channel, d.conv_30d, r.s1, r.s,
        d.conv_30d * 29.99 * 0.70 * (1 + r.s1 * (1 - POWER(r.s, 11)) / (1 - r.s)) AS ltv12
    FROM drivers d
    JOIN renew r USING (channel)
),
payback AS (
    -- cumulative expected net revenue per install after month m (m = 1..24)
    SELECT
        l.channel,
        MIN(m.m) FILTER (
            WHERE l.conv_30d * 29.99 * 0.70
                  * (1 + CASE WHEN m.m > 1 THEN l.s1 * (1 - POWER(l.s, m.m - 1)) / (1 - l.s) ELSE 0 END)
                  >= c.cac
        ) AS payback_month
    FROM ltv l
    JOIN cac c USING (channel)
    CROSS JOIN (SELECT UNNEST(RANGE(1, 25)) AS m) m      -- PostgreSQL: generate_series(1, 24)
    GROUP BY l.channel
)
SELECT
    l.channel,
    ROUND(l.ltv12, 2)                 AS ltv12_usd,
    ROUND(c.cac, 2)                   AS cac_usd,
    ROUND(l.ltv12 / c.cac, 2)         AS ltv_to_cac,
    p.payback_month
FROM ltv l
LEFT JOIN cac c USING (channel)
LEFT JOIN payback p USING (channel)
ORDER BY ltv_to_cac DESC NULLS LAST;


-- ---------------------------------------------------------------------
-- 5. Cohort revenue matrix: cumulative net revenue per install
--    by install month × months since install (only fully observed cells).
--    The classic "how fast does each cohort pay back" view.
-- ---------------------------------------------------------------------
WITH cohort_size AS (
    SELECT DATE_TRUNC('month', install_date) AS cohort, COUNT(*) AS installs
    FROM users
    GROUP BY 1
),
rev AS (
    SELECT
        DATE_TRUNC('month', u.install_date)                       AS cohort,
        FLOOR((t.charge_date - u.install_date) / 30.0)::INT        AS month_since_install,
        SUM(t.gross_amount_usd) * 0.70                            AS net_revenue
    FROM transactions t
    JOIN users u USING (user_id)
    GROUP BY 1, 2
),
cum AS (
    SELECT
        r.cohort, r.month_since_install,
        SUM(r.net_revenue) OVER (PARTITION BY r.cohort ORDER BY r.month_since_install) AS cum_net_revenue
    FROM rev r
)
SELECT
    c.cohort,
    c.month_since_install,
    ROUND(c.cum_net_revenue / s.installs, 3) AS cum_net_revenue_per_install
FROM cum c
JOIN cohort_size s USING (cohort)
-- keep only cells where every user in the cohort has been observed this long
WHERE c.cohort + INTERVAL '1 month' + (c.month_since_install + 1) * INTERVAL '30 days' <= DATE '2026-03-31'
ORDER BY c.cohort, c.month_since_install;

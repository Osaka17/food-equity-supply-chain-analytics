-- QUERY 1: Baseline Annual In vs. Out Net Balance
WITH d AS (
    SELECT pantry_id, SUM(weight_distributed_lbs) AS total_out
    FROM distributions 
    GROUP BY pantry_id
),
s AS (
    SELECT pantry_id, SUM(weight_received_lbs) AS total_in
    FROM shipments 
    GROUP BY pantry_id
)
SELECT 
    p.pantry_id,
    p.pantry_name,
    ROUND(((d.total_out * 1.0 / SUM(d.total_out) OVER ()) * 100), 2) AS demand_share_pct,
    ROUND(((s.total_in * 1.0 / SUM(s.total_in) OVER ()) * 100), 2) AS received_share_pct
FROM pantries p
JOIN d ON p.pantry_id = d.pantry_id
JOIN s ON p.pantry_id = s.pantry_id
ORDER BY demand_share_pct DESC;

-- QUERY 2: Baseline Problem Quantification (Stockouts vs Overflows)
WITH 
sdi AS (
    SELECT 
        pantry_id, 
        service_date, 
        SUM(weight_distributed_lbs) AS day_out
    FROM distributions
    GROUP BY pantry_id, service_date
),
sdo AS (
    SELECT 
        pantry_id, 
        arrival_date, 
        SUM(weight_received_lbs) AS day_in
    FROM shipments
    GROUP BY pantry_id, arrival_date
), 
running_tot AS (
    SELECT 
        sdi.pantry_id, 
        sdi.service_date,
        SUM(COALESCE(sdo.day_in, 0) - sdi.day_out) 
            OVER (PARTITION BY sdi.pantry_id ORDER BY sdi.service_date) AS running_total_lbs
    FROM sdi
    LEFT JOIN sdo
        ON sdi.pantry_id = sdo.pantry_id 
        AND sdi.service_date = sdo.arrival_date
), 
pantry_summary AS (
    SELECT 
        rt.pantry_id, 
        COUNT(CASE WHEN running_total_lbs <= 0 THEN 1 END) AS stockout_days, 
        COUNT(CASE WHEN running_total_lbs > p.max_storage_capacity_lbs THEN 1 END) AS overflow_days,
        ROUND(MAX(rt.running_total_lbs), 2) AS peak_inventory_lbs
    FROM running_tot rt
    LEFT JOIN pantries p ON rt.pantry_id = p.pantry_id
    GROUP BY rt.pantry_id
)
SELECT 
    p.pantry_id, 
    p.pantry_name, 
    p.max_storage_capacity_lbs,
    s.stockout_days,
    ROUND(((s.stockout_days * 1.0 / 365.0) * 100), 2) AS stockout_pct,
    ROUND(((s.overflow_days * 1.0 / 365.0) * 100), 2) AS overflow_pct,
    s.peak_inventory_lbs
FROM pantries p 
INNER JOIN pantry_summary s ON p.pantry_id = s.pantry_id
ORDER BY p.pantry_id;
-- QUERY 3: Demand Weight Share per Pantry

WITH d AS (
    SELECT pantry_id, SUM(weight_distributed_lbs) AS total_out
    FROM distributions 
    GROUP BY pantry_id
),
s AS (
    SELECT pantry_id, SUM(weight_received_lbs) AS total_in
    FROM shipments 
    GROUP BY pantry_id
)
SELECT 
    p.pantry_id,
    p.pantry_name,
    ROUND((d.total_out * 100.0) / SUM(d.total_out) OVER (), 2) AS demand_share_pct,
    ROUND((s.total_in * 100.0) / SUM(s.total_in) OVER (), 2) AS received_share_pct
FROM pantries p
JOIN d ON p.pantry_id = d.pantry_id
JOIN s ON p.pantry_id = s.pantry_id
ORDER BY demand_share_pct DESC;

-- QUERY 4: Demand-Weighted Reallocation Simulation
WITH 
demand AS (
    SELECT 
        pantry_id,
        SUM(weight_distributed_lbs) * 1.0 / SUM(SUM(weight_distributed_lbs)) OVER () AS demand_share
    FROM distributions
    GROUP BY pantry_id
),
daily_out AS (
    SELECT 
        pantry_id, 
        service_date, 
        SUM(weight_distributed_lbs) AS day_out
    FROM distributions
    GROUP BY pantry_id, service_date
),
daily_network_shipments AS (
    SELECT 
        arrival_date, 
        SUM(weight_received_lbs) AS total_network_in
    FROM shipments
    GROUP BY arrival_date
),
simulated_running_tot AS (
    SELECT 
        o.pantry_id,
        o.service_date,
        SUM(COALESCE(s.total_network_in * d.demand_share, 0) - o.day_out) 
            OVER (PARTITION BY o.pantry_id ORDER BY o.service_date) AS sim_running_lbs
    FROM daily_out o
    JOIN demand d ON o.pantry_id = d.pantry_id
    LEFT JOIN daily_network_shipments s ON o.service_date = s.arrival_date
),
sim_summary AS (
    SELECT 
        srt.pantry_id,
        COUNT(CASE WHEN srt.sim_running_lbs <= 0 THEN 1 END) AS sim_stockout_days,
        COUNT(CASE WHEN srt.sim_running_lbs > p.max_storage_capacity_lbs THEN 1 END) AS sim_overflow_days,
        ROUND(MAX(srt.sim_running_lbs), 2) AS sim_peak_lbs
    FROM simulated_running_tot srt
    JOIN pantries p ON srt.pantry_id = p.pantry_id
    GROUP BY srt.pantry_id
)
SELECT 
    p.pantry_id,
    p.pantry_name,
    p.max_storage_capacity_lbs,
    ROUND(d.demand_share * 100.0, 2) AS demand_share_pct,
    ss.sim_stockout_days,
    ROUND(((ss.sim_stockout_days * 1.0 / 365.0) * 100.0), 2) AS sim_stockout_pct,
    ss.sim_overflow_days,
    ROUND(((ss.sim_overflow_days * 1.0 / 365.0) * 100.0), 2) AS sim_overflow_pct,
    ss.sim_peak_lbs
FROM pantries p
JOIN demand d ON p.pantry_id = d.pantry_id
JOIN sim_summary ss ON p.pantry_id = ss.pantry_id
ORDER BY p.pantry_id;

-----chart2
WITH 
sdi AS (
    SELECT 
        pantry_id, 
        service_date, 
        SUM(weight_distributed_lbs) AS day_out
    FROM distributions
    GROUP BY pantry_id, service_date
),
sdo AS (
    SELECT 
        pantry_id, 
        arrival_date, 
        SUM(weight_received_lbs) AS day_in
    FROM shipments
    GROUP BY pantry_id, arrival_date
)
SELECT 
    sdi.pantry_id,
    p.pantry_name,
    p.max_storage_capacity_lbs,
    sdi.service_date,
    ROUND(
        SUM(COALESCE(sdo.day_in, 0) - sdi.day_out) 
        OVER (PARTITION BY sdi.pantry_id ORDER BY sdi.service_date), 
        2
    ) AS running_total_lbs
FROM sdi
JOIN pantries p 
    ON sdi.pantry_id = p.pantry_id
LEFT JOIN sdo 
    ON sdi.pantry_id = sdo.pantry_id 
    AND sdi.service_date = sdo.arrival_date
WHERE sdi.pantry_id IN ('P05', 'P02')
ORDER BY sdi.service_date, sdi.pantry_id;
# Food Bank Supply Chain Simulation & Inventory Analysis

A 365-day inventory simulation across an 8-hub municipal food distribution network using SQLite and Python. This project evaluates distribution bottlenecks caused by uniform shipping schedules and tests a dynamic, demand-weighted SQL reallocation policy to eliminate stockouts.

**Tech Stack:** Python, SQLite, SQL (CTEs, Window Functions), Pandas, Matplotlib

---

## Key Results

- **Baseline Failure:** Evenly distributing shipments (12.5% per hub) led to a **93.7% stockout rate** at the central urban hub (P05), leaving over 340,000 lbs of community demand unmet.
- **Policy Fix:** Reallocating daily shipments based on historical demand share reduced the network-wide stockout rate to **0.0%**.
- **Storage Trade-off:** Eliminating stockouts pushed a peak of 1.1M lbs through the urban hub, showing that solving supply equity requires secondary warehouse cross-docking rather than just bulk delivery.

---

## 1. Project Overview & The Problem

A regional food network delivers bulk goods across 8 pantry hubs. Central dispatch previously used an **equal-split shipment rule**, sending 12.5% of total incoming supply to each facility every day regardless of local demand.

In practice, community demand is heavily skewed toward the urban core:

- **Metro Central (P05):** Storage capacity of 35,000 lbs, but handles **23.1%** of total regional demand.
- **East Ward (P02):** Storage capacity of 18,000 lbs, but handles only **10.9%** of regional demand.

Tracking inventory without enforcing physical capacity limits creates two issues in basic spreadsheets:

1. **Unmet Demand:** Running balances drop below zero on paper, hiding prolonged food shortages.
2. **Wasted Overflow:** Suburban hubs accumulate paper inventory that physically exceeds their warehouse capacity.

---

## 2. Core Business Logic

The simulation tracks daily movement for each pantry over 365 operating days:

- **Daily Net Flow:** Daily incoming shipments minus daily distributed food.
- **Running Balance:** Cumulative sum of daily net flows starting from day 1.
- **Stockout Event:** Any day a pantry ends with a running balance of zero or less.
- **Capacity Overflow:** Any inventory volume that exceeds the pantry's maximum storage limit.

---

## 3. SQL Implementation

All data processing runs in SQLite using multi-level Common Table Expressions (CTEs) and window functions to model inventory balances and simulate policies without altering raw records. Source data lives in three tables: `pantries`, `shipments`, and `distributions`.

The two queries below are the core of the analysis — the rest of the query set (demand-share breakdowns and chart-specific data pulls) is available in [`/sql`](./sql).

### Query 1: Baseline Problem Quantification (Stockouts vs. Overflows)

Builds a running inventory ledger per pantry, then counts how many days each pantry spent in a stockout (balance ≤ 0) or overflow (balance > storage capacity) state under the baseline shipping policy. This is the query behind the headline 93.7% stockout figure.

```sql
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
```

### Query 2: Demand-Weighted Reallocation Simulation

Simulates a policy where total daily network shipments are redistributed by each pantry's demand share, then recomputes stockout days, overflow days, and peak inventory under the new policy. This is the fix that drops the network-wide stockout rate to 0.0%.

```sql
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
```

---

## 4. Visual Findings & Analysis

**Chart 1: The Allocation Mismatch**
Under equal dispatch (~12.5% per hub), Metro Central (P05) operates under an immediate -10.6% structural deficit, while suburban pantries receive far more food than their local communities require.

**Chart 2: Inventory Divergence vs. Storage Limits**
Over 365 days, Metro Central runs out of inventory by October and stays in an ongoing deficit, finishing with -340,000 lbs of unfulfilled demand. Meanwhile, suburban East Ward (P02) exceeds its 18,000 lb capacity within weeks, accumulating paper inventory that cannot physically fit on site.

**Chart 3: Policy Comparison & Bottlenecks**
Distributing shipments by demand share completely resolves community shortages, dropping the stockout rate from 93.7% to 0.0% at Metro Central. However, because network-wide supply exceeds demand, routing 23.1% of shipments downtown causes inventory accumulation to exceed local warehouse capacity, indicating that urban centers need frequent, smaller deliveries rather than large bulk drop-offs.

---

## 5. Performance Summary

| Pantry ID | Location Type   | Storage Capacity | Demand Share | Baseline Stockout % | Policy Stockout % | Net Change in Peak Inventory |
|-----------|------------------|-------------------|---------------|-----------------------|---------------------|-------------------------------|
| P05       | Urban Central     | 35,000 lbs        | 23.1%         | 93.7%                 | 0.0%                | +1,095k lbs                   |
| P08       | Urban Satellite   | 15,000 lbs        | 11.2%         | 2.7%                  | 0.0%                | -82k lbs                      |
| P07       | Suburban Hub      | 20,000 lbs        | 11.0%         | 1.4%                  | 0.0%                | -365k lbs                     |
| P04       | Suburban Relief   | 16,000 lbs        | 11.1%         | 1.1%                  | 0.0%                | -188k lbs                     |
| P02       | Suburban Hub      | 18,000 lbs        | 10.9%         | 0.0%                  | 0.0%                | -300k lbs                     |
| P06       | Community Table   | 10,000 lbs        | 11.0%         | 0.0%                  | 0.0%                | -185k lbs                     |
| P03       | Community Table   | 12,000 lbs        | 11.0%         | 0.0%                  | 0.0%                | -157k lbs                     |
| P01       | Community Table   | 12,000 lbs        | 10.8%         | 0.0%                  | 0.0%                | -209k lbs                     |

---

## 6. How to Run

```bash
# 1. Generate 365 days of synthetic network data
python gen_data.py

# 2. Run SQL analysis and export summary tables
# Queries analysis.sql and outputs CSV summaries

# 3. Generate charts
python vis.py
```

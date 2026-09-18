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

All data processing runs in SQLite (`analysis.sql`) using multi-level Common Table Expressions (CTEs) and window functions to model inventory balances and simulate policies without altering raw records.

### Query 1: Tracking Running Balances & Storage Breaches

Calculates cumulative inventory per pantry over time and flags stockouts and physical overflow.

```sql
WITH DailyNet AS (
    SELECT 
        pantry_id,
        service_date,
        daily_shipments,
        daily_distributed,
        (daily_shipments - daily_distributed) AS net_flow
    FROM service_records
),
RunningLedger AS (
    SELECT 
        p.pantry_id,
        p.pantry_name,
        p.capacity_lbs,
        d.service_date,
        SUM(d.net_flow) OVER (
            PARTITION BY p.pantry_id 
            ORDER BY d.service_date 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_balance
    FROM DailyNet d
    JOIN pantries p ON d.pantry_id = p.pantry_id
)
SELECT 
    pantry_id,
    service_date,
    running_balance,
    capacity_lbs,
    CASE WHEN running_balance <= 0 THEN 1 ELSE 0 END AS is_stockout,
    CASE WHEN running_balance > capacity_lbs THEN (running_balance - capacity_lbs) ELSE 0 END AS overflow_lbs
FROM RunningLedger;
```

### Query 2: Demand-Weighted Reallocation Policy

Reallocates total daily network shipments proportionally according to each pantry's share of annual demand.

```sql
WITH PantryDemandTotals AS (
    SELECT 
        pantry_id,
        SUM(daily_distributed) * 1.0 / (SELECT SUM(daily_distributed) FROM service_records) AS demand_weight
    FROM service_records
    GROUP BY pantry_id
),
NetworkDailyShipments AS (
    SELECT 
        service_date,
        SUM(daily_shipments) AS total_network_shipments
    FROM service_records
    GROUP BY service_date
),
SimulatedFlow AS (
    SELECT 
        s.pantry_id,
        s.service_date,
        (nds.total_network_shipments * pdt.demand_weight) AS sim_shipments,
        s.daily_distributed,
        ((nds.total_network_shipments * pdt.demand_weight) - s.daily_distributed) AS sim_net_flow
    FROM service_records s
    JOIN PantryDemandTotals pdt ON s.pantry_id = pdt.pantry_id
    JOIN NetworkDailyShipments nds ON s.service_date = nds.service_date
)
SELECT 
    pantry_id,
    service_date,
    SUM(sim_net_flow) OVER (
        PARTITION BY pantry_id 
        ORDER BY service_date 
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS sim_running_balance
FROM SimulatedFlow;
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

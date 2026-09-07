import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import seaborn as sns

sns.set_theme(style="whitegrid")
plt.rcParams["font.sans-serif"] = "DejaVu Sans"

def find_file(candidates):
    for path in candidates:
        if os.path.exists(path):
            return path
        sub_path = os.path.join("data", path)
        if os.path.exists(sub_path):
            return sub_path
    raise FileNotFoundError(f"Missing file: {candidates}")

def read_clean(filepath):
    df = pd.read_csv(filepath)
    df = df.loc[:, ~df.columns.str.contains(r"^Unnamed", case=False)]
    df.columns = [c.strip().replace("'", "").replace('"', '').lower() for c in df.columns]
    return df

# ==========================================
# CHART 1: Demand Share vs. Received Share
# ==========================================
df1 = read_clean("n_chart1.csv")

id_col_1 = [c for c in df1.columns if "id" in c][0]
name_col_1 = [c for c in df1.columns if "name" in c][0]
demand_col = [c for c in df1.columns if "demand" in c][0]
rec_col = [c for c in df1.columns if "rec" in c][0]

df1[demand_col] = pd.to_numeric(df1[demand_col].astype(str).str.replace("%", ""))
df1[rec_col] = pd.to_numeric(df1[rec_col].astype(str).str.replace("%", ""))
df1 = df1.sort_values(by=demand_col, ascending=False).reset_index(drop=True)

x1 = np.arange(len(df1))
width1 = 0.38

fig1, ax1 = plt.subplots(figsize=(11, 5.5), dpi=150)
bars_demand = ax1.bar(
    x1 - width1 / 2,
    df1[demand_col],
    width1,
    label="Demand Share (%)",
    color="#d9534f",
)
bars_received = ax1.bar(
    x1 + width1 / 2,
    df1[rec_col],
    width1,
    label="Received Share (%)",
    color="#4a90e2",
)

ax1.set_ylabel("Share of Network Total (%)", fontsize=10, fontweight="bold")
ax1.set_title(
    "Structural Allocation Mismatch: Community Demand vs. Central Shipments",
    fontsize=12,
    fontweight="bold",
    pad=15,
)
ax1.set_xticks(x1)

formatted_labels = [f"{name}\n({pid})" for pid, name in zip(df1[id_col_1], df1[name_col_1])]
ax1.set_xticklabels(formatted_labels, fontsize=8, rotation=12, ha="right")

ax1.legend(frameon=True, loc="upper right")
ax1.bar_label(bars_demand, padding=3, fmt="%.1f%%", fontsize=7.5)
ax1.bar_label(bars_received, padding=3, fmt="%.1f%%", fontsize=7.5)
ax1.set_ylim(0, max(df1[demand_col].max(), df1[rec_col].max()) + 4)

metro_rows = df1[df1[id_col_1].astype(str).str.contains("P05", case=False)]
if not metro_rows.empty:
    m_idx = metro_rows.index[0]
    deficit = df1.loc[m_idx, demand_col] - df1.loc[m_idx, rec_col]
    ax1.annotate(
        f"Deficit: -{deficit:.1f}%\nChronic Starvation",
        xy=(m_idx - width1 / 2, df1.loc[m_idx, demand_col]),
        xytext=(m_idx + 0.85, df1.loc[m_idx, demand_col] - 2.5),
        arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=-0.2", color="#333333", lw=1.2),
        fontsize=8.5,
        fontweight="semibold",
        bbox=dict(boxstyle="round,pad=0.4", fc="#fdf6e2", ec="#b58900", lw=1),
    )

plt.tight_layout()
plt.savefig("chart1_allocation_mismatch.png")
plt.close(fig1)

# ==========================================
# CHART 2: Daily Inventory Balance vs. Physical Capacity
# ==========================================
df2 = read_clean("chart2_daily.csv")

id_col_2 = [c for c in df2.columns if "pantry" in c and "id" in c or c == "pantry_id"][0]
date_col = [c for c in df2.columns if "date" in c][0]
run_col = [c for c in df2.columns if "running" in c or "total" in c][0]
cap_col = [c for c in df2.columns if "cap" in c][0]

df2[date_col] = pd.to_datetime(df2[date_col])
df2[run_col] = pd.to_numeric(df2[run_col])
df2[cap_col] = pd.to_numeric(df2[cap_col])

p05 = df2[df2[id_col_2].astype(str).str.contains("P05", case=False)].sort_values(date_col)
p02 = df2[df2[id_col_2].astype(str).str.contains("P02", case=False)].sort_values(date_col)

fig2, (p2_ax1, p2_ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, dpi=150, gridspec_kw={"hspace": 0.25})

p2_ax1.plot(p05[date_col], p05[run_col] / 1000.0, color="#d9534f", lw=2, label="Daily Inventory Balance")
p2_ax1.axhline(0, color="black", linestyle="--", lw=1, alpha=0.8, label="Zero Balance / Stockout Floor")

cap_p05 = p05[cap_col].iloc[0] / 1000.0
p2_ax1.axhline(cap_p05, color="#1b5e20", linestyle="-.", lw=2, label=f"Max Physical Capacity ({cap_p05:.0f}k lbs)")

first_date = p05[date_col].iloc[10]
p2_ax1.text(
    first_date, cap_p05 + 12,
    f"  MAX STORAGE CEILING: {cap_p05:,.0f}k lbs  ",
    fontsize=8, fontweight="bold", color="#1b5e20",
    bbox=dict(boxstyle="round,pad=0.3", fc="#e8f5e9", ec="#1b5e20", lw=1.2)
)

p2_ax1.fill_between(
    p05[date_col],
    p05[run_col] / 1000.0,
    0,
    where=(p05[run_col] <= 0),
    color="#d9534f",
    alpha=0.25,
    rasterized=True,
    label="Chronic Stockout Deficit",
)
p2_ax1.set_ylim(p05[run_col].min() / 1000.0 - 30, cap_p05 + 50)
p2_ax1.set_title("Metro Central (P05): Urban Center Chronically Depleted", fontsize=11, fontweight="bold")
p2_ax1.set_ylabel("Inventory (1,000 lbs)", fontsize=9, fontweight="bold")
p2_ax1.legend(loc="lower left", frameon=True, fontsize=8)

p2_ax2.plot(p02[date_col], p02[run_col] / 1000.0, color="#2980b9", lw=2, label="Virtual Ledger Balance")

cap_p02 = p02[cap_col].iloc[0] / 1000.0
p2_ax2.axhline(cap_p02, color="#b71c1c", linestyle="-.", lw=2, label=f"Physical Capacity Limit ({cap_p02:.0f}k lbs)")

p2_ax2.text(
    first_date, cap_p02 + 45,
    f"  PHYSICAL CAPACITY LIMIT: {cap_p02:,.0f}k lbs (Breached in Oct)  ",
    fontsize=8, fontweight="bold", color="#b71c1c",
    bbox=dict(boxstyle="round,pad=0.3", fc="#ffebee", ec="#b71c1c", lw=1.2)
)

p2_ax2.fill_between(
    p02[date_col],
    p02[run_col] / 1000.0,
    cap_p02,
    where=(p02[run_col] / 1000.0 > cap_p02),
    color="#f39c12",
    alpha=0.3,
    rasterized=True,
    label="Phantom Overflow / Physical Constraint Breach",
)
p2_ax2.set_ylim(-30, p02[run_col].max() / 1000.0 + 60)
p2_ax2.set_title("Suburban Hub (P02): Unconstrained Ledger Overflow", fontsize=11, fontweight="bold")
p2_ax2.set_ylabel("Inventory (1,000 lbs)", fontsize=9, fontweight="bold")
p2_ax2.legend(loc="upper left", frameon=True, fontsize=8)

p2_ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
p2_ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
p2_ax2.set_xlabel("Service Date", fontsize=9, fontweight="bold")

plt.tight_layout()
plt.savefig("chart2_daily_divergence.png")
plt.close(fig2)

# ==========================================
# CHART 3: Policy Shift Impact
# ==========================================
fq2 = find_file(["n_q2.csv", "new_query2.csv", "query2.csv"])
fq4 = find_file(["n_q4.csv", "new_query_4.csv", "query4.csv"])

df_q2 = read_clean(fq2)
df_q4 = read_clean(fq4)

id_col_q2 = [c for c in df_q2.columns if "id" in c][0]
id_col_q4 = [c for c in df_q4.columns if "id" in c][0]

stockout_col_q2 = [c for c in df_q2.columns if "stockout" in c and ("%" in c or "pct" in c or "percent" in c)][0]
stockout_col_q4 = [c for c in df_q4.columns if "stockout" in c and ("%" in c or "pct" in c or "percent" in c)][0]

peak_col_q2 = [c for c in df_q2.columns if "peak" in c][0]
peak_col_q4 = [c for c in df_q4.columns if "peak" in c][0]

df3 = pd.merge(df_q2, df_q4, left_on=id_col_q2, right_on=id_col_q4, suffixes=("_baseline", "_sim"))

df3["base_stockout"] = pd.to_numeric(df3[stockout_col_q2])
df3["sim_stockout"] = pd.to_numeric(df3[stockout_col_q4])
df3["base_peak_k"] = pd.to_numeric(df3[peak_col_q2]) / 1000.0
df3["sim_peak_k"] = pd.to_numeric(df3[peak_col_q4]) / 1000.0
df3["peak_change_k"] = df3["sim_peak_k"] - df3["base_peak_k"]

df3 = df3.sort_values(by="base_stockout", ascending=True).reset_index(drop=True)

fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(10, 6), sharex=False, dpi=150, gridspec_kw={"height_ratios": [1, 1.4], "hspace": 0.4})

y_pos = np.arange(len(df3))
ax_top.hlines(y=y_pos, xmin=df3["sim_stockout"], xmax=df3["base_stockout"], color="#b0bec5", lw=2, zorder=1)
ax_top.scatter(df3["base_stockout"], y_pos, color="#d9534f", s=80, label="Baseline Stockout %", zorder=2)
ax_top.scatter(df3["sim_stockout"], y_pos, color="#2ca02c", s=80, label="Reallocated Stockout %", zorder=2)

ax_top.set_yticks(y_pos)
ax_top.set_yticklabels(df3[id_col_q2], fontsize=9, fontweight="bold")
ax_top.set_xlabel("% of Days Stocked Out", fontsize=9, fontweight="bold")
ax_top.set_title("1. The Win: Stockouts Dropped to 0% Across All Hubs", fontsize=11, fontweight="bold", loc="left")
ax_top.set_xlim(-2, 105)
ax_top.legend(loc="lower right", frameon=True, fontsize=8)

p05_idx = df3[df3[id_col_q2].str.contains("P05", case=False)].index[0]
ax_top.annotate(
    f"Metro Central (P05): {df3.loc[p05_idx, 'base_stockout']:.1f}% → 0%",
    xy=(0, p05_idx),
    xytext=(55, p05_idx + 0.25),
    arrowprops=dict(arrowstyle="->", color="#1b5e20", lw=1.2),
    fontsize=8, fontweight="bold", color="#1b5e20",
    ha="center", va="center",
    bbox=dict(boxstyle="round,pad=0.2", fc="#e8f5e9", ec="#1b5e20", lw=0.8)
)

bar_colors = ["#d9534f" if v > 0 else "#4a90e2" for v in df3["peak_change_k"]]
bars = ax_bot.barh(y_pos, df3["peak_change_k"], color=bar_colors, height=0.55, edgecolor="none")
ax_bot.axvline(0, color="black", linestyle="--", lw=1, alpha=0.7)

ax_bot.set_yticks(y_pos)
ax_bot.set_yticklabels(df3[id_col_q2], fontsize=9, fontweight="bold")
ax_bot.set_xlabel("Net Change in Peak Inventory Accumulation (1,000 lbs)", fontsize=9, fontweight="bold")
ax_bot.set_title("2. The Trade-Off: Suburban Surplus Transferred Directly to Urban Hub", fontsize=11, fontweight="bold", loc="left")

for bar, val in zip(bars, df3["peak_change_k"]):
    align = "left" if val >= 0 else "right"
    offset = 25 if val >= 0 else -25
    ax_bot.text(val + offset, bar.get_y() + bar.get_height() / 2, f"{val:+,.0f}k lbs", 
                va="center", ha=align, fontsize=7.5, fontweight="semibold")

ax_bot.set_xlim(df3["peak_change_k"].min() - 170, df3["peak_change_k"].max() + 180)

fig.suptitle("Policy Trade-Off: Solving Service Equity Without Capacity Constraints", fontsize=12, fontweight="bold", y=0.98)
plt.tight_layout()
plt.savefig("chart3_policy_comparison.png")
plt.close(fig)
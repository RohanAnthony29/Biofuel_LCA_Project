"""
03_visualizations.py
Biofuel LCA — Publication-Quality Plots

Figures produced:
  1. Stacked bar: Stage-by-stage CI for all central-scenario pathways
  2. Grouped bar: CI by fuel type (SAF vs Ethanol) vs fossil baselines
  3. Horizontal bar: GHG reduction % ranked by pathway
  4. Sensitivity: transport distance impact on CI (line chart)
  5. Heat map: CI matrix (feedstock × pathway, central scenario)
  6. Scenario comparison: current grid vs renewable grid
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mtick
import seaborn as sns
import os

DB_PATH  = "data/biofuel_lca.db"
CSV_PATH = "data/scenario_results.csv"
PLOT_DIR = "plots"
os.makedirs(PLOT_DIR, exist_ok=True)

df = pd.read_csv(CSV_PATH)

# ── Shared style ──────────────────────────────────────────────────────────────
NAVY   = "#1B3A5C"
TEAL   = "#2A9D8F"
AMBER  = "#E9C46A"
CORAL  = "#E76F51"
SAGE   = "#6DA67A"
SLATE  = "#8D99AE"
PURPLE = "#7B5EA7"
BG     = "#F8F9FA"

STAGE_COLS = [
    "ci_cultivation_kg_per_mj",
    "ci_harvest_kg_per_mj",
    "ci_transport_kg_per_mj",
    "ci_preprocessing_kg_per_mj",
    "ci_conversion_kg_per_mj",
    "ci_combustion_kg_per_mj",
]
STAGE_LABELS = ["Cultivation", "Harvesting", "Transport",
                "Preprocessing", "Conversion", "Combustion"]
STAGE_COLORS = [CORAL, AMBER, SLATE, SAGE, TEAL, NAVY]

plt.rcParams.update({
    "font.family":      "DejaVu Sans",
    "axes.facecolor":   BG,
    "figure.facecolor": "white",
    "axes.spines.top":  False,
    "axes.spines.right":False,
    "axes.grid":        True,
    "grid.color":       "#E0E0E0",
    "grid.linewidth":   0.7,
    "axes.labelsize":   11,
    "axes.titlesize":   13,
    "axes.titleweight": "bold",
    "xtick.labelsize":  9,
    "ytick.labelsize":  9,
    "legend.fontsize":  9,
})

central = df[df["scenario_name"].str.startswith("Central")].copy()
central = central.sort_values("ci_total_kg_per_mj")

# Short pathway label
def short_label(row):
    fs = row["feedstock_name"].replace(" (Raceway)","").replace(" (Dry Mill, NG)","")
    pw = row["pathway_name"].split("→")[-1].strip().replace("(","").replace(")","").strip()
    pw = pw.replace("Cellulosic Ethanol","CE").replace("HEFA-SAF","HEFA")
    pw = pw.replace("FT-SAF","FT-SAF").replace("Ethanol","EtOH")
    return f"{fs}\n{pw}"

central["label"] = central.apply(short_label, axis=1)

# =============================================================================
# FIGURE 1 — Stacked bar: stage-by-stage CI
# =============================================================================
fig, ax = plt.subplots(figsize=(14, 7))

bottoms = np.zeros(len(central))
for col, label, color in zip(STAGE_COLS, STAGE_LABELS, STAGE_COLORS):
    vals = central[col].values
    ax.bar(range(len(central)), vals, bottom=bottoms,
           label=label, color=color, alpha=0.92, width=0.7, edgecolor="white", linewidth=0.4)
    bottoms += vals

# Fossil baseline lines
saf_bl   = central[central["fuel_product"]=="SAF"]["fossil_baseline_kg_per_mj"].iloc[0]
etoh_bl  = central[central["fuel_product"]=="Ethanol"]["fossil_baseline_kg_per_mj"].iloc[0]

for i, (_, row) in enumerate(central.iterrows()):
    bl = row["fossil_baseline_kg_per_mj"]
    ax.hlines(bl, i - 0.42, i + 0.42, colors="black", linewidths=1.6,
              linestyles="--", zorder=5)

ax.set_xticks(range(len(central)))
ax.set_xticklabels(central["label"], rotation=35, ha="right", fontsize=7.5)
ax.set_ylabel("Carbon Intensity (kg CO₂e / MJ fuel)", fontsize=11)
ax.set_title("Stage-by-Stage Carbon Intensity — Central Scenario\nAll Pathways vs. Fossil Baseline (dashed)", pad=14)
ax.legend(loc="upper right", framealpha=0.9, ncol=2)

# Fuel type annotation
for i, (_, row) in enumerate(central.iterrows()):
    ax.text(i, -0.0035, row["fuel_product"][:3],
            ha="center", va="top", fontsize=7, color=NAVY, style="italic")

fig.tight_layout()
fig.savefig(f"{PLOT_DIR}/01_stacked_stage_ci.png", dpi=150, bbox_inches="tight")
plt.close()
print("Plot 1 saved: stacked stage CI")

# =============================================================================
# FIGURE 2 — Grouped bar: SAF vs Ethanol vs fossil baselines
# =============================================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=False)

for ax, fuel, color, fossil_label, fossil_bl in [
    (axes[0], "SAF",     TEAL,  "Fossil Jet-A WTW",     0.0880),
    (axes[1], "Ethanol", CORAL, "Fossil Gasoline WTW",   0.0906),
]:
    sub = central[central["fuel_product"] == fuel].copy()
    sub = sub.sort_values("ci_total_kg_per_mj")
    labels = [s.split("\n")[0] for s in sub["label"]]

    bars = ax.bar(range(len(sub)), sub["ci_total_kg_per_mj"],
                  color=color, alpha=0.85, width=0.6, edgecolor="white")

    ax.axhline(fossil_bl, color="black", linestyle="--", linewidth=1.8,
               label=fossil_label, zorder=5)

    # Reduction % labels
    for i, (_, row) in enumerate(sub.iterrows()):
        ax.text(i, row["ci_total_kg_per_mj"] + 0.0008,
                f"{row['reduction_pct']:.0f}%",
                ha="center", va="bottom", fontsize=8, color=NAVY, fontweight="bold")

    ax.set_xticks(range(len(sub)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("CI (kg CO₂e / MJ)", fontsize=10)
    ax.set_title(f"{fuel} Pathways — Total Carbon Intensity", fontsize=12)
    ax.legend(fontsize=9, framealpha=0.9)

fig.suptitle("Biofuel Carbon Intensity vs. Fossil Baselines  |  Central Scenario",
             fontsize=13, fontweight="bold", y=1.01)
fig.tight_layout()
fig.savefig(f"{PLOT_DIR}/02_saf_vs_ethanol_ci.png", dpi=150, bbox_inches="tight")
plt.close()
print("Plot 2 saved: SAF vs Ethanol grouped bar")

# =============================================================================
# FIGURE 3 — Horizontal bar: GHG reduction % ranked
# =============================================================================
central_sorted = central.sort_values("reduction_pct", ascending=True)
colors_bar = [TEAL if f == "SAF" else CORAL for f in central_sorted["fuel_product"]]

fig, ax = plt.subplots(figsize=(10, 7))
bars = ax.barh(range(len(central_sorted)), central_sorted["reduction_pct"],
               color=colors_bar, alpha=0.88, height=0.65, edgecolor="white")

ax.axvline(50, color=SLATE, linestyle=":", linewidth=1.5, label="50% threshold")
ax.axvline(70, color=AMBER, linestyle=":", linewidth=1.5, label="70% threshold (EU RED III)")
ax.axvline(0,  color="black", linewidth=0.8)

for i, (_, row) in enumerate(central_sorted.iterrows()):
    ax.text(row["reduction_pct"] + 0.5, i,
            f"{row['reduction_pct']:.1f}%", va="center", fontsize=8)

ax.set_yticks(range(len(central_sorted)))
ax.set_yticklabels([s.split("\n")[0] for s in central_sorted["label"]], fontsize=8.5)
ax.set_xlabel("GHG Reduction vs. Fossil Baseline (%)")
ax.set_title("GHG Reduction by Pathway — Central Scenario\nRanked lowest to highest", pad=12)

patch_saf  = mpatches.Patch(color=TEAL,  alpha=0.88, label="SAF")
patch_etoh = mpatches.Patch(color=CORAL, alpha=0.88, label="Ethanol")
ax.legend(handles=[patch_saf, patch_etoh,
                   mpatches.Patch(color=SLATE, alpha=0, label="50% threshold"),
                   mpatches.Patch(color=AMBER, alpha=0, label="70% (EU RED III)")],
          loc="lower right", fontsize=9)

fig.tight_layout()
fig.savefig(f"{PLOT_DIR}/03_ghg_reduction_ranked.png", dpi=150, bbox_inches="tight")
plt.close()
print("Plot 3 saved: GHG reduction ranked")

# =============================================================================
# FIGURE 4 — Sensitivity: transport distance vs CI for key pathways
# =============================================================================
key_pathways = [
    "Corn Stover → Cellulosic Ethanol (AFEX)",
    "Switchgrass → Cellulosic Ethanol (Dilute Acid)",
    "Forestry Residues → FT-SAF (Gasification)",
    "Soybean Oil → HEFA-SAF",
    "Algae (Raceway)",   # partial match
]

transport_scenarios = ["Near   (40 km truck, current grid)",
                       "Central (80 km truck, current grid)",
                       "Far   (160 km truck, current grid)",
                       "Rail  (400 km rail,  current grid)"]
dist_map = {
    "Near   (40 km truck, current grid)":  40,
    "Central (80 km truck, current grid)": 80,
    "Far   (160 km truck, current grid)": 160,
    "Rail  (400 km rail,  current grid)": 400,
}

fig, ax = plt.subplots(figsize=(10, 6))
line_colors = [CORAL, TEAL, NAVY, AMBER, SAGE, PURPLE]

plotted = 0
for pw_name, lc in zip(key_pathways, line_colors):
    sub = df[df["pathway_name"].str.contains(pw_name[:25], regex=False) &
             df["scenario_name"].isin(transport_scenarios)].copy()
    if sub.empty:
        # Try feedstock name match for algae
        sub = df[df["feedstock_name"].str.contains(pw_name[:10], regex=False) &
                 df["scenario_name"].isin(transport_scenarios)].copy()
    if sub.empty:
        continue
    sub["dist"] = sub["scenario_name"].map(dist_map)
    sub = sub.sort_values("dist")
    short = pw_name.split("→")[-1].strip()[:30] if "→" in pw_name else pw_name[:30]
    ax.plot(sub["dist"], sub["ci_total_kg_per_mj"],
            marker="o", color=lc, linewidth=2.2, markersize=7, label=short)
    plotted += 1

ax.set_xlabel("Transport Distance (km)")
ax.set_ylabel("Carbon Intensity (kg CO₂e / MJ)")
ax.set_title("Sensitivity Analysis: Transport Distance vs. Carbon Intensity\nCurrent grid electricity scenario", pad=12)
ax.legend(fontsize=9, framealpha=0.9, loc="upper left")
fig.tight_layout()
fig.savefig(f"{PLOT_DIR}/04_transport_sensitivity.png", dpi=150, bbox_inches="tight")
plt.close()
print("Plot 4 saved: transport sensitivity")

# =============================================================================
# FIGURE 5 — Heat map: CI matrix (feedstock × fuel type)
# =============================================================================
pivot = central.pivot_table(
    values="ci_total_kg_per_mj",
    index="feedstock_name",
    columns="fuel_product",
    aggfunc="mean"
)

fig, ax = plt.subplots(figsize=(8, 7))
sns.heatmap(pivot, annot=True, fmt=".3f", cmap="YlOrRd",
            linewidths=0.5, linecolor="white",
            cbar_kws={"label": "CI (kg CO₂e / MJ)"},
            ax=ax, annot_kws={"size": 9})
ax.set_title("Carbon Intensity Heat Map\nFeedstock × Fuel Type (Central Scenario)", pad=14)
ax.set_xlabel("Fuel Product")
ax.set_ylabel("Feedstock")
ax.tick_params(axis="x", labelsize=10)
ax.tick_params(axis="y", labelsize=8.5, rotation=0)
fig.tight_layout()
fig.savefig(f"{PLOT_DIR}/05_ci_heatmap.png", dpi=150, bbox_inches="tight")
plt.close()
print("Plot 5 saved: CI heat map")

# =============================================================================
# FIGURE 6 — Grid scenario comparison (current vs renewable)
# =============================================================================
current_grid  = df[df["scenario_name"] == "Central (80 km truck, current grid)"].copy()
renew_grid    = df[df["scenario_name"] == "Renewable grid (80 km truck)"].copy()
optim         = df[df["scenario_name"] == "Optimistic (40 km, renewable grid)"].copy()

# Merge on pathway
comp = current_grid[["pathway_name","feedstock_name","fuel_product",
                      "ci_total_kg_per_mj","fossil_baseline_kg_per_mj"]].copy()
comp = comp.rename(columns={"ci_total_kg_per_mj":"ci_current"})
comp = comp.merge(
    renew_grid[["pathway_name","ci_total_kg_per_mj"]].rename(
        columns={"ci_total_kg_per_mj":"ci_renewable"}),
    on="pathway_name", how="inner"
).merge(
    optim[["pathway_name","ci_total_kg_per_mj"]].rename(
        columns={"ci_total_kg_per_mj":"ci_optimistic"}),
    on="pathway_name", how="inner"
)
comp = comp.sort_values("ci_current")

x      = np.arange(len(comp))
width  = 0.26

fig, ax = plt.subplots(figsize=(14, 6))
ax.bar(x - width,   comp["ci_current"],    width, label="Current grid (80 km)",     color=CORAL,  alpha=0.88, edgecolor="white")
ax.bar(x,           comp["ci_renewable"],  width, label="Renewable grid (80 km)",   color=TEAL,   alpha=0.88, edgecolor="white")
ax.bar(x + width,   comp["ci_optimistic"], width, label="Renewable grid (40 km)",   color=SAGE,   alpha=0.88, edgecolor="white")

# Fossil baseline dots
for i, row in enumerate(comp.itertuples()):
    ax.hlines(row.fossil_baseline_kg_per_mj, i - 0.42, i + 0.42,
              colors="black", linewidths=1.4, linestyles="--", zorder=5)

ax.set_xticks(x)
ax.set_xticklabels([s.split("\n")[0][:22] for s in
                    [short_label(r) for _, r in comp.iterrows()]],
                   rotation=38, ha="right", fontsize=8)
ax.set_ylabel("CI (kg CO₂e / MJ)")
ax.set_title("Grid Scenario Comparison: Current vs. Renewable Electricity\nDashed line = fossil baseline", pad=12)
ax.legend(fontsize=9, framealpha=0.9)
fig.tight_layout()
fig.savefig(f"{PLOT_DIR}/06_grid_scenario_comparison.png", dpi=150, bbox_inches="tight")
plt.close()
print("Plot 6 saved: grid scenario comparison")

print(f"\nAll 6 plots saved to {PLOT_DIR}/")

"""
04_export_tables.py
Biofuel LCA — Export clean summary tables for report / GitHub

Outputs:
  outputs/summary_central_scenario.csv
  outputs/stage_breakdown_all_pathways.csv
  outputs/scenario_sensitivity.csv
  outputs/emission_factors_reference.csv
  outputs/assumptions_log.csv
"""

import sqlite3
import pandas as pd
import numpy as np
import os

DB_PATH  = "data/biofuel_lca.db"
CSV_PATH = "data/scenario_results.csv"
OUT_DIR  = "outputs"
os.makedirs(OUT_DIR, exist_ok=True)

df     = pd.read_csv(CSV_PATH)
conn   = sqlite3.connect(DB_PATH)
ef_df  = pd.read_sql("SELECT * FROM emission_factors", conn)
fs_df  = pd.read_sql("SELECT * FROM feedstocks", conn)
pw_df  = pd.read_sql("SELECT * FROM conversion_pathways", conn)
conn.close()

central = df[df["scenario_name"].str.startswith("Central")].copy()
central = central.sort_values("ci_total_kg_per_mj")

# ── 1. Summary central scenario ───────────────────────────────────────────────
summary = central[[
    "feedstock_name","pathway_name","fuel_product",
    "ci_cultivation_kg_per_mj","ci_harvest_kg_per_mj","ci_transport_kg_per_mj",
    "ci_preprocessing_kg_per_mj","ci_conversion_kg_per_mj","ci_combustion_kg_per_mj",
    "ci_total_kg_per_mj","fossil_baseline_kg_per_mj","reduction_pct"
]].copy()

summary.columns = [
    "Feedstock","Pathway","Fuel",
    "CI Cultivation","CI Harvesting","CI Transport",
    "CI Preprocessing","CI Conversion","CI Combustion",
    "CI Total (kg CO2e/MJ)","Fossil Baseline","GHG Reduction %"
]

summary.to_csv(f"{OUT_DIR}/summary_central_scenario.csv", index=False, float_format="%.5f")
print("Saved: summary_central_scenario.csv")

# ── 2. Stage breakdown long format ───────────────────────────────────────────
stages = [
    ("ci_cultivation_kg_per_mj",   "1. Cultivation"),
    ("ci_harvest_kg_per_mj",       "2. Harvesting"),
    ("ci_transport_kg_per_mj",     "3. Transport"),
    ("ci_preprocessing_kg_per_mj", "4. Preprocessing"),
    ("ci_conversion_kg_per_mj",    "5. Conversion"),
    ("ci_combustion_kg_per_mj",    "6. Combustion"),
]
long_rows = []
for _, row in central.iterrows():
    for col, stage in stages:
        long_rows.append({
            "Feedstock":      row["feedstock_name"],
            "Pathway":        row["pathway_name"],
            "Fuel":           row["fuel_product"],
            "Stage":          stage,
            "CI (kg CO2e/MJ)":row[col],
            "Share of Total %": (row[col] / row["ci_total_kg_per_mj"] * 100)
                                  if row["ci_total_kg_per_mj"] > 0 else 0,
        })
pd.DataFrame(long_rows).to_csv(f"{OUT_DIR}/stage_breakdown_all_pathways.csv",
                                index=False, float_format="%.5f")
print("Saved: stage_breakdown_all_pathways.csv")

# ── 3. Scenario sensitivity table ────────────────────────────────────────────
scen_cols = ["feedstock_name","pathway_name","fuel_product","scenario_name",
             "transport_distance_km","transport_mode","grid_scenario",
             "ci_total_kg_per_mj","reduction_pct"]
df[scen_cols].to_csv(f"{OUT_DIR}/scenario_sensitivity.csv", index=False, float_format="%.5f")
print("Saved: scenario_sensitivity.csv")

# ── 4. Emission factors reference ────────────────────────────────────────────
ef_df.to_csv(f"{OUT_DIR}/emission_factors_reference.csv", index=False)
print("Saved: emission_factors_reference.csv")

# ── 5. Assumptions log ───────────────────────────────────────────────────────
assumptions = []

# Feedstock assumptions
for _, fs in fs_df.iterrows():
    assumptions.append({
        "Category":  "Feedstock",
        "Parameter": f"{fs['name']} — yield (dry t/ha/yr)",
        "Value":     fs["yield_dry_t_per_ha"],
        "Unit":      "dry t/ha/yr",
        "Type":      fs["source_label"].split("]")[0].replace("[",""),
        "Source":    fs["source_label"],
    })
    assumptions.append({
        "Category":  "Feedstock",
        "Parameter": f"{fs['name']} — N fertilizer",
        "Value":     fs["n_fertilizer_kg_per_t_dry"],
        "Unit":      "kg N / dry t biomass",
        "Type":      fs["source_label"].split("]")[0].replace("[",""),
        "Source":    fs["source_label"],
    })

# Pathway assumptions
for _, pw in pw_df.iterrows():
    assumptions.append({
        "Category":  "Conversion Pathway",
        "Parameter": f"{pw['name']} — conversion efficiency",
        "Value":     pw["conversion_eff_mj_per_t_dry"],
        "Unit":      "MJ fuel / dry t biomass",
        "Type":      pw["source_label"].split("]")[0].replace("[",""),
        "Source":    pw["source_label"],
    })

# Emission factors
for _, ef_row in ef_df.iterrows():
    assumptions.append({
        "Category":  "Emission Factor",
        "Parameter": ef_row["parameter"],
        "Value":     ef_row["value"],
        "Unit":      ef_row["unit"],
        "Type":      ef_row["source_label"].split("]")[0].replace("[",""),
        "Source":    ef_row["source_label"],
    })

pd.DataFrame(assumptions).to_csv(f"{OUT_DIR}/assumptions_log.csv",
                                   index=False, float_format="%.5f")
print("Saved: assumptions_log.csv")

# ── Print key statistics ──────────────────────────────────────────────────────
print("\n" + "="*60)
print("KEY RESULTS SUMMARY — Central Scenario")
print("="*60)

for fuel in ["SAF","Ethanol"]:
    sub = central[central["fuel_product"] == fuel]
    print(f"\n{fuel}:")
    print(f"  Pathways analyzed : {len(sub)}")
    print(f"  CI range          : {sub['ci_total_kg_per_mj'].min():.4f} – "
          f"{sub['ci_total_kg_per_mj'].max():.4f} kg CO2e/MJ")
    print(f"  Reduction range   : {sub['reduction_pct'].min():.1f}% – "
          f"{sub['reduction_pct'].max():.1f}%")
    best = sub.loc[sub["ci_total_kg_per_mj"].idxmin()]
    print(f"  Best pathway      : {best['feedstock_name']} "
          f"({best['reduction_pct']:.1f}% reduction)")
    worst = sub.loc[sub["ci_total_kg_per_mj"].idxmax()]
    print(f"  Worst pathway     : {worst['feedstock_name']} "
          f"({worst['reduction_pct']:.1f}% reduction)")

print("\nDone.")

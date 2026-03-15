"""
02_lca_calculations.py
Biofuel LCA — Stage-by-Stage Carbon Intensity Calculator

For each feedstock × pathway × scenario combination:
  Stage 1: Cultivation   — fertilizer N2O + field diesel
  Stage 2: Harvesting    — harvest diesel + land-use change
  Stage 3: Transport     — truck/rail/barge from field to biorefinery
  Stage 4: Preprocessing — drying + size reduction
  Stage 5: Conversion    — process energy GHG
  Stage 6: Combustion    — biogenic CO2 (neutral) + any fossil combustion co-products

All results in kg CO2e / MJ of fuel (functional unit).
"""

import sqlite3
import pandas as pd
import numpy as np
import os

DB_PATH  = "data/biofuel_lca.db"
OUT_CSV  = "data/scenario_results.csv"
os.makedirs("data", exist_ok=True)

conn = sqlite3.connect(DB_PATH)

# ── Load tables ───────────────────────────────────────────────────────────────
feedstocks = pd.read_sql("SELECT * FROM feedstocks", conn)
pathways   = pd.read_sql("SELECT * FROM conversion_pathways", conn)
ef_df      = pd.read_sql("SELECT parameter, value FROM emission_factors", conn)
ef         = dict(zip(ef_df["parameter"], ef_df["value"]))

conn.close()

# ── Emission factor shortcuts ─────────────────────────────────────────────────
N2O_EF       = ef["N2O emission factor (fertilizer)"]   # kg N2O / kg N
N2O_GWP      = ef["N2O GWP100 (AR5)"]                   # 265
DIESEL_EF    = ef["Diesel combustion EF"]               # kg CO2e / MJ
NG_EF        = ef["Natural gas combustion EF"]          # kg CO2e / MJ
GRID_EF_NOW  = ef["US grid electricity EF (2023)"]      # kg CO2e / MJ
GRID_EF_REN  = ef["Renewable electricity EF"]           # kg CO2e / MJ
DIESEL_LPR_T = ef["Field operations diesel"]            # L diesel / dry t
DRYING_NG    = ef["Biomass drying energy (NG)"]         # MJ NG / kg H2O removed
GRIND_ELEC   = ef["Biomass grinding electricity"]       # MJ elec / dry t
DIESEL_MJ_L  = 35.8                                     # MJ per litre diesel [GREET]

# ── Scenario matrix ───────────────────────────────────────────────────────────
#   Each row: (scenario_name, transport_km, transport_mode, grid_scenario)
SCENARIOS = [
    ("Central (80 km truck, current grid)", 80,  "truck", "current"),
    ("Near   (40 km truck, current grid)",  40,  "truck", "current"),
    ("Far   (160 km truck, current grid)", 160,  "truck", "current"),
    ("Rail  (400 km rail,  current grid)", 400,  "rail",  "current"),
    ("Renewable grid (80 km truck)",        80,  "truck", "renewable"),
    ("Optimistic (40 km, renewable grid)",  40,  "truck", "renewable"),
]

# Transport emission factors (kg CO2e / t-km)
TRANSPORT_EF = {
    "truck": 0.0623,   # [M] GREET 2024 Class 8 diesel
    "rail":  0.0196,   # [M] GREET 2024 freight rail
    "barge": 0.0108,   # [L] GREET 2024 inland barge
}

# Fossil fuel baselines (kg CO2e / MJ) — well-to-wheel
FOSSIL_BASELINE = {
    "Ethanol":  ef["Gasoline (fossil) combustion CO2"] + 0.0170,  # gasoline WTW
    "SAF":      ef["Jet fuel (fossil) combustion CO2"] + 0.0165,  # Jet-A WTW
}

# =============================================================================
# Core calculation function
# =============================================================================
def calc_stage_ci(feedstock, pathway, transport_km, transport_mode, grid_scenario):
    """
    Returns dict of kg CO2e / MJ fuel for each life-cycle stage.
    """
    conv_eff = pathway["conversion_eff_mj_per_t_dry"]   # MJ fuel / dry tonne biomass
    if conv_eff <= 0:
        return None

    grid_ef = GRID_EF_NOW if grid_scenario == "current" else GRID_EF_REN

    # ------------------------------------------------------------------
    # STAGE 1: CULTIVATION
    # Fertilizer N2O + field machinery diesel + direct LUC
    # ------------------------------------------------------------------
    n_applied   = feedstock["n_fertilizer_kg_per_t_dry"]  # kg N / dry t biomass
    n2o_kg_per_t = n_applied * N2O_EF * N2O_GWP           # kg CO2e / dry t
    luc_kg_per_t = feedstock["land_use_co2e_kg_per_t_dry"]

    ci_cultivation = (n2o_kg_per_t + luc_kg_per_t) / conv_eff

    # ------------------------------------------------------------------
    # STAGE 2: HARVESTING
    # Diesel for cutting, baling, collection
    # ------------------------------------------------------------------
    diesel_l     = DIESEL_LPR_T                            # L / dry t
    diesel_mj    = diesel_l * DIESEL_MJ_L                  # MJ / dry t
    harvest_co2e = diesel_mj * DIESEL_EF                   # kg CO2e / dry t

    ci_harvest = harvest_co2e / conv_eff

    # ------------------------------------------------------------------
    # STAGE 3: TRANSPORT (field → biorefinery)
    # ------------------------------------------------------------------
    t_ef_per_tkm = TRANSPORT_EF[transport_mode]
    transport_co2e = t_ef_per_tkm * transport_km           # kg CO2e / dry t

    ci_transport = transport_co2e / conv_eff

    # ------------------------------------------------------------------
    # STAGE 4: PREPROCESSING (drying + size reduction)
    # ------------------------------------------------------------------
    moisture     = feedstock["moisture_pct"] / 100.0
    dry_fraction = 1.0 - moisture
    # Water to remove to reach ~10% moisture target
    water_to_remove_kg = max(0, (moisture - 0.10) / dry_fraction)  # kg H2O / kg dry

    drying_mj    = water_to_remove_kg * DRYING_NG          # MJ NG / kg dry biomass
    drying_co2e  = drying_mj * NG_EF                       # kg CO2e / kg dry biomass
    grind_co2e   = GRIND_ELEC * grid_ef / 1000.0           # MJ → convert properly

    # Units: everything per dry tonne (× 1000 for t→kg)
    preproc_co2e = (drying_co2e * 1000.0 + GRIND_ELEC * grid_ef)

    ci_preprocessing = preproc_co2e / conv_eff

    # ------------------------------------------------------------------
    # STAGE 5: CONVERSION
    # Process energy (NG, electricity, or self-generated syngas)
    # ------------------------------------------------------------------
    proc_co2e_per_mj = pathway["co2e_process_kg_per_mj"]

    # Adjust if conversion uses grid electricity (renewable vs current)
    proc_src = pathway["process_energy_source"]
    if "Electricity" in proc_src:
        # Back out original grid assumption, apply scenario grid EF
        # Original coded at US avg grid; scale proportionally
        scale = grid_ef / GRID_EF_NOW
        proc_co2e_per_mj = proc_co2e_per_mj * scale

    ci_conversion = proc_co2e_per_mj

    # ------------------------------------------------------------------
    # STAGE 6: COMBUSTION (use phase)
    # Biogenic CO2 = carbon neutral under GREET accounting
    # No fossil CO2 credit for biofuels in base case
    # ------------------------------------------------------------------
    ci_combustion = 0.0  # biogenic carbon neutral

    # ------------------------------------------------------------------
    # TOTAL
    # ------------------------------------------------------------------
    ci_total = (ci_cultivation + ci_harvest + ci_transport +
                ci_preprocessing + ci_conversion + ci_combustion)

    fuel_type = pathway["fuel_product"]
    fossil_bl = FOSSIL_BASELINE.get(fuel_type, 0.09)
    reduction_pct = (1.0 - ci_total / fossil_bl) * 100.0

    return {
        "ci_cultivation_kg_per_mj":   round(ci_cultivation,   6),
        "ci_harvest_kg_per_mj":       round(ci_harvest,       6),
        "ci_transport_kg_per_mj":     round(ci_transport,     6),
        "ci_preprocessing_kg_per_mj": round(ci_preprocessing, 6),
        "ci_conversion_kg_per_mj":    round(ci_conversion,    6),
        "ci_combustion_kg_per_mj":    round(ci_combustion,    6),
        "ci_total_kg_per_mj":         round(ci_total,         6),
        "fossil_baseline_kg_per_mj":  round(fossil_bl,        6),
        "reduction_pct":              round(reduction_pct,    2),
    }

# =============================================================================
# Run all combinations
# =============================================================================
print("Running LCA calculations...")
print(f"  {len(feedstocks)} feedstocks × {len(pathways)} pathways × {len(SCENARIOS)} scenarios")
print()

results = []
run_id  = 0

for _, fs in feedstocks.iterrows():
    for _, pw in pathways.iterrows():
        # Only pair compatible feedstock categories
        if fs["category"] != pw["feedstock_category"]:
            continue

        for scen_name, t_km, t_mode, grid_sc in SCENARIOS:
            run_id += 1
            ci = calc_stage_ci(fs, pw, t_km, t_mode, grid_sc)
            if ci is None:
                continue

            row = {
                "run_id":               run_id,
                "scenario_name":        scen_name,
                "feedstock_name":       fs["name"],
                "feedstock_id":         fs["id"],
                "feedstock_category":   fs["category"],
                "pathway_name":         pw["name"],
                "pathway_id":           pw["pathway_id"],
                "fuel_product":         pw["fuel_product"],
                "transport_distance_km": t_km,
                "transport_mode":       t_mode,
                "grid_scenario":        grid_sc,
                **ci,
            }
            results.append(row)

df = pd.DataFrame(results)
print(f"Total scenario runs: {len(df)}")

# =============================================================================
# Write to DB and CSV
# =============================================================================
conn = sqlite3.connect(DB_PATH)
df_db = df[[
    "run_id","scenario_name","feedstock_id","pathway_id",
    "transport_distance_km","transport_mode","grid_scenario",
    "ci_cultivation_kg_per_mj","ci_harvest_kg_per_mj",
    "ci_transport_kg_per_mj","ci_preprocessing_kg_per_mj",
    "ci_conversion_kg_per_mj","ci_combustion_kg_per_mj",
    "ci_total_kg_per_mj","fossil_baseline_kg_per_mj","reduction_pct"
]].copy()
df_db.to_sql("scenario_runs", conn, if_exists="replace", index=False)
conn.close()

df.to_csv(OUT_CSV, index=False)
print(f"Saved: {OUT_CSV}")
print(f"Saved: {DB_PATH} (scenario_runs table)")

# =============================================================================
# Summary table — central scenario only
# =============================================================================
central = df[df["scenario_name"].str.startswith("Central")].copy()
central = central.sort_values("ci_total_kg_per_mj")

print("\n" + "="*80)
print("CENTRAL SCENARIO SUMMARY  (kg CO2e / MJ fuel)")
print("="*80)
print(f"{'Feedstock':<28} {'Pathway':<38} {'Fuel':<8} "
      f"{'Total CI':>9} {'Fossil BL':>9} {'Reduc%':>7}")
print("-"*80)
for _, r in central.iterrows():
    pw_short = r["pathway_name"].split("→")[-1].strip()[:35]
    print(f"{r['feedstock_name']:<28} {pw_short:<38} {r['fuel_product']:<8} "
          f"{r['ci_total_kg_per_mj']:>9.4f} {r['fossil_baseline_kg_per_mj']:>9.4f} "
          f"{r['reduction_pct']:>6.1f}%")

print("\nDone.")

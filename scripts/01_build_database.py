"""
01_build_database.py
Biofuel LCA — Cradle-to-Fuel / Well-to-Wheel Analysis
Builds the SQLite database with:
  - feedstocks
  - transport
  - conversion_pathways
  - emission_factors
  - scenario_runs

Data sources & transparency labels:
  [M] = measured / directly from GREET 2024 documentation
  [L] = literature assumption (GREET, Berkeley Lab, Scown et al.)
  [S] = scenario assumption (conservative / central / optimistic)

Functional unit : kg CO2e per MJ of fuel produced
System boundary : Cradle-to-fuel (feedstock cultivation → conversion)
                  + combustion (well-to-wheel)
GWP basis       : AR5 100-year GWP (IPCC 2013)
Reference model : GREET 2024 (Argonne National Laboratory)
"""

import sqlite3
import pandas as pd
import numpy as np
import os

DB_PATH = "data/biofuel_lca.db"
os.makedirs("data", exist_ok=True)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# ── Drop & recreate tables ────────────────────────────────────────────────────
c.executescript("""
DROP TABLE IF EXISTS feedstocks;
DROP TABLE IF EXISTS transport;
DROP TABLE IF EXISTS conversion_pathways;
DROP TABLE IF EXISTS emission_factors;
DROP TABLE IF EXISTS scenario_runs;
DROP TABLE IF EXISTS stage_emissions;
""")

# =============================================================================
# TABLE 1: feedstocks
# Columns: id, name, category, region, yield_dry_t_per_ha,
#          n_fertilizer_kg_per_t_dry, moisture_pct,
#          land_use_co2e_kg_per_t_dry, source_label
# =============================================================================
c.execute("""
CREATE TABLE feedstocks (
    id                       INTEGER PRIMARY KEY,
    name                     TEXT NOT NULL,
    category                 TEXT,          -- energy_crop / ag_residue / waste
    region                   TEXT,
    yield_dry_t_per_ha       REAL,          -- dry tonnes biomass per hectare/yr
    n_fertilizer_kg_per_t_dry REAL,         -- kg N applied per dry tonne biomass
    moisture_pct             REAL,          -- harvest moisture %
    land_use_co2e_kg_per_t_dry REAL,        -- direct land-use change GHG
    source_label             TEXT
)
""")

feedstocks = [
    # (name, category, region, yield_dry_t_per_ha, N_kg/t_dry, moisture%, LUC_kg_CO2e/t_dry, source)
    ("Corn Stover",          "ag_residue",   "US Midwest",      3.5,   5.0,  15.0,   0.0,  "[L] GREET 2024 Table 3.1"),
    ("Switchgrass",          "energy_crop",  "US Southeast",    8.0,  10.0,  15.0,   5.2,  "[L] Scown et al. 2022 / GREET 2024"),
    ("Miscanthus",           "energy_crop",  "US Midwest",     12.0,   4.0,  18.0,   3.1,  "[L] GREET 2024; Heaton et al. 2008"),
    ("Forestry Residues",    "ag_residue",   "US Pacific NW",   2.0,   0.0,  40.0,   0.0,  "[L] GREET 2024 Table 3.5"),
    ("Municipal Solid Waste","waste",        "US Average",      0.0,   0.0,  25.0,   0.0,  "[L] GREET 2024 MSW pathway"),
    ("Soybean Oil",          "energy_crop",  "US Midwest",      0.5,  18.0,  13.0,  12.4,  "[M] GREET 2024 Table 2.1; USDA"),
    ("Camelina",             "energy_crop",  "US Northern Plains",0.9, 8.0,   9.0,   6.8,  "[L] Moser 2010; GREET 2024"),
    ("Algae (Raceway)",      "energy_crop",  "US Southwest",    20.0, 0.0,   90.0,   0.0,  "[S] Davis et al. 2016 central case"),
    ("Corn Grain",           "energy_crop",  "US Midwest",      9.5,  15.0,  15.5,   8.9,  "[M] GREET 2024 Table 2.1; NASS 2023"),
    ("Sugarcane Bagasse",    "ag_residue",   "Brazil / US Gulf", 12.0,  2.0,  50.0,   1.5,  "[L] GREET 2024; Dias et al. 2012"),
]

c.executemany("""
INSERT INTO feedstocks
  (name, category, region, yield_dry_t_per_ha, n_fertilizer_kg_per_t_dry,
   moisture_pct, land_use_co2e_kg_per_t_dry, source_label)
VALUES (?,?,?,?,?,?,?,?)
""", feedstocks)

# =============================================================================
# TABLE 2: transport
# Hauling biomass from field to biorefinery gate
# kg CO2e per dry tonne per km (mode-specific)
# =============================================================================
c.execute("""
CREATE TABLE transport (
    id              INTEGER PRIMARY KEY,
    mode            TEXT NOT NULL,
    distance_km     REAL,
    co2e_per_t_km   REAL,   -- kg CO2e / (dry tonne * km)
    source_label    TEXT
)
""")

transport = [
    ("Diesel truck (flatbed)",  80,   0.0623,  "[M] GREET 2024 Table 6.1 — Class 8 truck"),
    ("Diesel truck (flatbed)", 160,   0.0623,  "[M] GREET 2024 Table 6.1"),
    ("Rail (diesel freight)",  400,   0.0196,  "[M] GREET 2024 Table 6.2"),
    ("Rail (diesel freight)",  800,   0.0196,  "[M] GREET 2024 Table 6.2"),
    ("Barge (inland)",         600,   0.0108,  "[L] GREET 2024 Table 6.3"),
    ("Pipeline (slurry)",      200,   0.0089,  "[L] GREET 2024 estimate"),
]

c.executemany("""
INSERT INTO transport (mode, distance_km, co2e_per_t_km, source_label)
VALUES (?,?,?,?)
""", transport)

# =============================================================================
# TABLE 3: conversion_pathways
# Each pathway maps a feedstock category → fuel product
# Columns: pathway_id, name, feedstock_category, fuel_product,
#          conversion_efficiency_mj_per_t_dry, process_energy_mj_per_mj_fuel,
#          process_energy_source, co2e_process_kg_per_mj_fuel, source_label
# =============================================================================
c.execute("""
CREATE TABLE conversion_pathways (
    pathway_id               INTEGER PRIMARY KEY,
    name                     TEXT NOT NULL,
    feedstock_category       TEXT,
    fuel_product             TEXT,
    lhv_mj_per_kg_fuel       REAL,   -- lower heating value of fuel
    conversion_eff_mj_per_t_dry REAL,-- MJ fuel per dry tonne biomass
    process_energy_mj_per_mj REAL,   -- process energy intensity
    process_energy_source    TEXT,
    co2e_process_kg_per_mj   REAL,   -- GHG from conversion process only
    source_label             TEXT
)
""")

pathways = [
    # (name, feedstock_cat, fuel, LHV, conv_eff, proc_energy, energy_src, proc_co2e, source)
    ("Corn Stover → Cellulosic Ethanol (AFEX)",
     "ag_residue",  "Ethanol",
     26.8, 6800,  0.42, "Natural Gas",  0.0385,
     "[L] GREET 2024 Pathway CE-01; Wyman 2013"),

    ("Switchgrass → Cellulosic Ethanol (Dilute Acid)",
     "energy_crop", "Ethanol",
     26.8, 7200,  0.38, "Natural Gas",  0.0348,
     "[L] GREET 2024 Pathway CE-03; Scown et al. 2022"),

    ("Miscanthus → Cellulosic Ethanol",
     "energy_crop", "Ethanol",
     26.8, 8100,  0.35, "Natural Gas",  0.0320,
     "[L] GREET 2024; Heaton et al. 2008"),

    ("Forestry Residues → FT-SAF (Gasification)",
     "ag_residue",  "SAF",
     43.2, 9500,  0.55, "Syngas (self)", 0.0210,
     "[L] GREET 2024 Pathway FT-01; NREL 2011"),

    ("MSW → FT-SAF (Gasification)",
     "waste",       "SAF",
     43.2, 7800,  0.60, "Syngas (self)", 0.0195,
     "[L] GREET 2024 MSW-FT pathway"),

    ("Soybean Oil → HEFA-SAF",
     "energy_crop", "SAF",
     43.2, 37200, 0.12, "Natural Gas",  0.0089,
     "[M] GREET 2024 Pathway HEFA-01; ICAO CORSIA"),

    ("Camelina → HEFA-SAF",
     "energy_crop", "SAF",
     43.2, 36800, 0.11, "Natural Gas",  0.0082,
     "[L] GREET 2024; Shonnard et al. 2010"),

    ("Algae → HEFA-SAF (Wet Lipid Extraction)",
     "energy_crop", "SAF",
     43.2, 18000, 0.85, "Natural Gas",  0.0620,
     "[S] Davis et al. 2016 central; GREET 2024 algae"),

    ("Corn Grain → Ethanol (Dry Mill, NG)",
     "energy_crop", "Ethanol",
     26.8, 10400, 0.32, "Natural Gas",  0.0298,
     "[M] GREET 2024 Pathway E-01; Wang et al. 2022"),

    ("Corn Grain → Ethanol (Dry Mill, Electric)",
     "energy_crop", "Ethanol",
     26.8, 10400, 0.30, "Grid Electricity (US avg)", 0.0401,
     "[M] GREET 2024 Pathway E-02"),

    ("Sugarcane Bagasse → Cellulosic Ethanol",
     "ag_residue",  "Ethanol",
     26.8, 6200,  0.30, "Bagasse Steam (self)", 0.0180,
     "[L] GREET 2024; Dias et al. 2012"),
]

c.executemany("""
INSERT INTO conversion_pathways
  (name, feedstock_category, fuel_product, lhv_mj_per_kg_fuel,
   conversion_eff_mj_per_t_dry, process_energy_mj_per_mj,
   process_energy_source, co2e_process_kg_per_mj, source_label)
VALUES (?,?,?,?,?,?,?,?,?)
""", pathways)

# =============================================================================
# TABLE 4: emission_factors
# Generic emission factors used across calculations
# =============================================================================
c.execute("""
CREATE TABLE emission_factors (
    id           INTEGER PRIMARY KEY,
    parameter    TEXT NOT NULL,
    value        REAL,
    unit         TEXT,
    source_label TEXT
)
""")

ef = [
    # Agricultural inputs
    ("N2O emission factor (fertilizer)",       0.01,    "kg N2O / kg N applied",        "[M] IPCC 2006 Tier 1"),
    ("N2O GWP100 (AR5)",                      265.0,   "kg CO2e / kg N2O",             "[M] IPCC AR5 2013"),
    ("Diesel combustion EF",                   0.0741,  "kg CO2e / MJ diesel",          "[M] GREET 2024 Table 1.1"),
    ("Natural gas combustion EF",              0.0562,  "kg CO2e / MJ NG",              "[M] GREET 2024 Table 1.2"),
    ("US grid electricity EF (2023)",          0.1432,  "kg CO2e / MJ electricity",     "[M] EPA eGRID 2023 national avg"),
    ("Renewable electricity EF",               0.0050,  "kg CO2e / MJ electricity",     "[L] NREL ATB 2024 wind/solar"),
    # Harvest / field operations diesel
    ("Field operations diesel",                2.8,     "L diesel / dry tonne biomass", "[L] GREET 2024 Table 3.2"),
    # Fuel combustion (use phase)
    ("Ethanol combustion CO2",                 0.0,     "kg fossil CO2e / MJ ethanol",  "[M] Biogenic carbon neutral — GREET"),
    ("SAF combustion CO2",                     0.0,     "kg fossil CO2e / MJ SAF",      "[M] Biogenic carbon neutral — GREET"),
    ("Jet fuel (fossil) combustion CO2",       0.0715,  "kg CO2e / MJ Jet-A",           "[M] GREET 2024 Jet-A baseline"),
    ("Gasoline (fossil) combustion CO2",       0.0736,  "kg CO2e / MJ gasoline",        "[M] GREET 2024 gasoline baseline"),
    # Drying energy
    ("Biomass drying energy (NG)",             1.15,    "MJ NG / kg water removed",     "[L] GREET 2024 preprocessing"),
    # Preprocessing electricity
    ("Biomass grinding electricity",           0.05,    "MJ electricity / dry tonne",   "[L] GREET 2024 preprocessing"),
]

c.executemany("""
INSERT INTO emission_factors (parameter, value, unit, source_label)
VALUES (?,?,?,?)
""", ef)

# =============================================================================
# TABLE 5: scenario_runs  (populated by analysis script)
# =============================================================================
c.execute("""
CREATE TABLE scenario_runs (
    run_id              INTEGER PRIMARY KEY,
    scenario_name       TEXT,
    feedstock_id        INTEGER,
    pathway_id          INTEGER,
    transport_distance_km REAL,
    transport_mode      TEXT,
    grid_scenario       TEXT,   -- 'current' / 'renewable'
    ci_cultivation_kg_per_mj  REAL,
    ci_harvest_kg_per_mj      REAL,
    ci_transport_kg_per_mj    REAL,
    ci_preprocessing_kg_per_mj REAL,
    ci_conversion_kg_per_mj   REAL,
    ci_combustion_kg_per_mj   REAL,
    ci_total_kg_per_mj        REAL,
    fossil_baseline_kg_per_mj REAL,
    reduction_pct             REAL,
    FOREIGN KEY (feedstock_id) REFERENCES feedstocks(id),
    FOREIGN KEY (pathway_id)   REFERENCES conversion_pathways(pathway_id)
)
""")

conn.commit()
conn.close()

print("Database built:", DB_PATH)

# Verify
conn = sqlite3.connect(DB_PATH)
for tbl in ["feedstocks","transport","conversion_pathways","emission_factors","scenario_runs"]:
    n = pd.read_sql(f"SELECT COUNT(*) as n FROM {tbl}", conn).iloc[0,0]
    print(f"  {tbl:30s}: {n:3d} rows")
conn.close()
print("Done.")

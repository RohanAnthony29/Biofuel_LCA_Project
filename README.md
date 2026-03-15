# Biofuel Life Cycle Assessment — Carbon Intensity Analysis
### Cradle-to-Fuel / Well-to-Wheel GHG Analysis | GREET-Style Framework

---

## Overview

This project computes the **carbon intensity (kg CO₂e / MJ fuel)** of 11 biofuel conversion pathways across 10 feedstocks and 6 transport/grid scenarios — totalling **312 scenario runs**. .

**Functional unit:** kg CO₂e per MJ of fuel produced  
**System boundary:** Cradle-to-fuel (feedstock cultivation → conversion) + combustion  
**Impact metric:** Global Warming Potential (GWP100, IPCC AR5)  
**Reference model:** GREET 2024 (Argonne National Laboratory)

---

## Life Cycle Stages

| Stage | Description | Key drivers |
|-------|-------------|-------------|
| 1. Cultivation | N fertilizer N₂O, field diesel, land-use change | N₂O EF, yield, LUC |
| 2. Harvesting | Cutting, baling, collection diesel | Diesel EF, field ops intensity |
| 3. Transport | Field → biorefinery (truck / rail / barge) | Distance, mode, load factor |
| 4. Preprocessing | Drying to target moisture, size reduction | Moisture content, energy source |
| 5. Conversion | Process energy (NG / electricity / syngas) | Pathway efficiency, process EF |
| 6. Combustion | Biogenic CO₂ (carbon neutral under GREET) | Fuel LHV, biogenic accounting |

---

## Feedstocks & Pathways

**10 feedstocks** across 3 categories:
- **Energy crops:** Switchgrass, Miscanthus, Soybean Oil, Camelina, Algae (Raceway), Corn Grain
- **Agricultural residues:** Corn Stover, Forestry Residues, Sugarcane Bagasse
- **Waste:** Municipal Solid Waste

**11 conversion pathways:**
- Cellulosic ethanol (AFEX, Dilute Acid)
- Corn grain dry-mill ethanol (NG and electric)
- HEFA-SAF (conventional and wet lipid extraction)
- Fischer-Tropsch SAF (gasification)

---

## Key Results (Central Scenario — 80 km truck, current grid)

### SAF Pathways
| Best | CI (kg CO₂e/MJ) | Reduction vs Jet-A |
|------|-----------------|-------------------|
| Miscanthus → HEFA-SAF | 0.0091 | **89.7%** |
| Camelina → HEFA-SAF | 0.0093 | 89.4% |
| Forestry Residues → FT-SAF | 0.0257 | 70.8% |
| Algae → HEFA-SAF | 0.0226 | 74.3% |

### Ethanol Pathways
| Best | CI (kg CO₂e/MJ) | Reduction vs Gasoline |
|------|-----------------|----------------------|
| Corn Stover → CE (AFEX) | 0.0228 | **74.9%** |
| Forestry Residues → CE | 0.0252 | 72.2% |
| Sugarcane Bagasse → CE | 0.0294 | 67.5% |
| Corn Grain → Dry Mill NG | 0.0361 | 60.2% |

---

## Project Structure

```
biofuel_lca/
├── run_all.py                          ← Master pipeline runner
├── scripts/
│   ├── 01_build_database.py            ← SQLite DB with emission factors
│   ├── 02_lca_calculations.py          ← Stage-by-stage CI calculator
│   ├── 03_visualizations.py            ← 6 publication-quality figures
│   └── 04_export_tables.py             ← Summary CSV tables
├── data/
│   ├── biofuel_lca.db                  ← SQLite database (5 tables)
│   └── scenario_results.csv            ← All 312 scenario runs
├── plots/
│   ├── 01_stacked_stage_ci.png         ← Stage breakdown all pathways
│   ├── 02_saf_vs_ethanol_ci.png        ← SAF vs Ethanol vs fossil
│   ├── 03_ghg_reduction_ranked.png     ← Reduction % ranked
│   ├── 04_transport_sensitivity.png    ← Distance sensitivity
│   ├── 05_ci_heatmap.png               ← Feedstock × fuel heat map
│   └── 06_grid_scenario_comparison.png ← Current vs renewable grid
└── outputs/
    ├── summary_central_scenario.csv
    ├── stage_breakdown_all_pathways.csv
    ├── scenario_sensitivity.csv
    ├── emission_factors_reference.csv
    └── assumptions_log.csv
```

---

## Database Schema

```sql
feedstocks          -- 10 rows: yield, N fertilizer, moisture, LUC
transport           -- 6 rows: mode, distance, CO2e/t-km
conversion_pathways -- 11 rows: efficiency, process energy, process EF
emission_factors    -- 13 rows: N2O EF, diesel/NG/grid EFs, GWPs
scenario_runs       -- 312 rows: full stage-by-stage CI per scenario
```

---

## Data Transparency

Each value is tagged with a source type:
- **[M]** Measured / directly from GREET 2024 documentation
- **[L]** Literature assumption (GREET, Berkeley Lab, Scown et al.)
- **[S]** Scenario assumption (conservative / central / optimistic)

See `outputs/assumptions_log.csv` for the full parameter log.

---

## How to Run

```bash
pip install pandas numpy matplotlib seaborn
python run_all.py
```

---

## References

- GREET 2024 — Argonne National Laboratory (Wang et al.)
- Scown et al. (2022) — *Nature Energy* — Biofuel sustainability
- Davis et al. (2016) — NREL algae TEA/LCA
- ICAO CORSIA — SAF eligibility and LCA methodology
- IPCC AR5 (2013) — GWP100 factors
- EPA eGRID (2023) — US electricity emission factors
- NREL ATB (2024) — Renewable energy cost/emission factors

---

## GitHub Push

```bash
git init
git add .
git commit -m "Initial commit: biofuel LCA — cradle-to-fuel carbon intensity"
git remote add origin https://github.com/YOUR_USERNAME/biofuel-lca.git
git push -u origin main
```

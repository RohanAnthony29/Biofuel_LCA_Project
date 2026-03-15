"""
run_all.py
Biofuel LCA — Master Pipeline Runner

Runs all four steps in order:
  1. Build SQLite database
  2. LCA calculations (all scenarios)
  3. Generate all 6 visualizations
  4. Export summary tables
"""

import subprocess
import sys
import os
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))

steps = [
    ("scripts/01_build_database.py",  "Build database"),
    ("scripts/02_lca_calculations.py","LCA calculations"),
    ("scripts/03_visualizations.py",  "Visualizations"),
    ("scripts/04_export_tables.py",   "Export tables"),
]

print("=" * 60)
print("  BIOFUEL LCA PIPELINE — FULL RUN")
print("  Cradle-to-Fuel / Well-to-Wheel Analysis")
print("=" * 60)

total_start = time.time()
for script, label in steps:
    print(f"\n[{label}]")
    print("-" * 40)
    t0 = time.time()
    result = subprocess.run([sys.executable, script], capture_output=False)
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"  ERROR in {script} (exit code {result.returncode})")
        sys.exit(1)
    print(f"  Completed in {elapsed:.1f}s")

total = time.time() - total_start
print(f"\n{'='*60}")
print(f"  ALL STEPS COMPLETE  ({total:.1f}s total)")
print(f"  Outputs:")
print(f"    data/biofuel_lca.db")
print(f"    data/scenario_results.csv")
print(f"    plots/  (6 figures)")
print(f"    outputs/ (5 CSV tables)")
print(f"{'='*60}")

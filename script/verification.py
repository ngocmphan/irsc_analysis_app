import pandas as pd
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_FILE = (SCRIPT_DIR.parent / "app_data" / "cihr_projects.parquet").resolve()
SUMMARY_FILE = (SCRIPT_DIR.parent / "app_data" / "cihr_summary_metrics.parquet").resolve()
results = pd.read_parquet(PROJECT_FILE)
summary = pd.read_parquet(SUMMARY_FILE)

results = results[(results["competition_year"] == 2025)]

print(results["cihr_contribution"].sum())

print(results.columns)

prc_stats = results.groupby('prc_category').agg(
            total_funding=('cihr_contribution', 'sum'),
            average_funding=('cihr_contribution', 'mean'),
            project_count=('cihr_contribution', 'count')
        ).reset_index()

print(results["institution"].unique())
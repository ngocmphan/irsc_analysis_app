# Import libraries
import pandas as pd
from pathlib import Path
import numpy as np
import re

# Configuration paths
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR_RESULTS = SCRIPT_DIR.parent / "raw_data" / "results"
DATA_DIR_SUM = SCRIPT_DIR.parent / "raw_data" / "summary"
OUTPUT_DIR = SCRIPT_DIR.parent / "app_data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROJECT_FILE = OUTPUT_DIR/"cihr_projects.parquet"
SUMMARY_FILE = OUTPUT_DIR/"cihr_summary_metrics.parquet"

# Standard functions for cleaning

def process_single_file(file_path: Path) -> pd.DataFrame:
    """Reads, cleans and standardizes a single raw file"""

    if file_path.suffix == ".csv":
        try:
            df = pd.read_csv(file_path, encoding="utf-8")
        except UnicodeDecodeError:
            print(f"UTF-8 decoding failed for {file_path.name}. Retrying with cp1252 encoding.")
            df = pd.read_csv(file_path, encoding="cp1252")
    else: 
        df = pd.read_excel(file_path)

    # Standardize columns names
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # Clean up financial numeric fields
    financial_cols = ["cihr_contribution", "cihr_equipment"]
    for col in financial_cols: 
        df[col] = df[col].astype(str).str.replace(r'[\$,]', '', regex=True).str.strip()
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    # Clean up subvention duration field
    df["term_years"] = df["term_years_months"].str.extract(r'(\d+)\s*yrs').astype(float)
    df["term_months"] = df["term_years_months"].str.extract(r'(\d+)\s*mth').astype(float).fillna(0)
    df["total_months"] = (df["term_years"]*12) + df["term_months"]
    df["term_years_precise"] = df["total_months"]/12
    df["funding_per_year"] = df["cihr_contribution"] / df["term_years_precise"]
    df["source_file"] = file_path.name

    # Create fiscal year fields based on competition information
    df["competition_year"] = df["competition_cd"].astype(str).str.extract(r"^(\d{4})").astype(float)
    df = df.rename(columns={"institution_paid": "institution", "prc_name": "prc_category"})
    return df


def update_results():
    files = list(DATA_DIR_RESULTS.glob("*.csv")) + list(DATA_DIR_RESULTS.glob("*.xlsx"))
    if not files:
        print("No results files found in raw_data/results.")
        return
    
    # Take the most recently modified file in results folder
    latest_file = max(files, key=lambda x: x.stat().st_mtime)
    print(f"reading latest cumulatiive export: {latest_file.name}")

    df = process_single_file(latest_file)

    df.to_parquet(PROJECT_FILE, index=False)
    print(f"Successfully refreshed master result database ({len(df)} records).")


OCCASION_MAP = {
    "F": "Fall",
    "S": "Spring"
}

def filename_parse(filename: str):
    match = re.search(r"(\d{4})([A-Za-z]+)", filename)
    if match: 
        year = int(match.group(1))
        code = match.group(2).upper()
        occasion = OCCASION_MAP.get(code, code)
        return year, occasion


def process_summaries(file_path: Path):
    try:
        df = pd.read_csv(file_path, sep=None, engine="python", encoding="utf-8")
    except Exception as e:
        df = pd.read_excel(file_path)

    cleaned_headers = []
    for col in df.columns:
        c = col.strip().lower()
        c = re.sub(r'footnote.*$', '', c)  # Strips "footnote*" or "footnote1" from the end
        c = re.sub(r'[^a-z0-9_]', '_', c)   # Replaces spaces, brackets, and % with underscores
        c = re.sub(r'_+', '_', c).strip('_') # Clean up duplicate underscores
        cleaned_headers.append(c)

    df.columns = cleaned_headers
    if 'province' in df.columns:
            df = df[df['province'].astype(str).str.strip().str.lower() != 'total']
            df['province'] = df['province'].astype(str).str.strip()

    def clean_numeric_strings(series: pd.Series) -> pd.Series:
            """Removes commas, dollar signs, and percentage symbols to ensure standard numeric types."""
            return pd.to_numeric(
                series.astype(str)
                .str.replace(r"[$,% \t]", "", regex=True)
                .str.replace(r"\+?\bpp\b", "", regex=True)
                .str.strip(), 
                errors='coerce'
            ).fillna(0)

    for col in df.columns:
        if col != 'province':
            df[col] = clean_numeric_strings(df[col])
    

    fiscal_year, occasion = filename_parse(file_path.name)
    df["fiscal_year"] = fiscal_year
    df["occasion"] = occasion
    df["source_file"] = file_path.name
    

    return df


def flatten_source_files(x):
    flat_set = set()
    for item in x:
        if isinstance(item, (list, np.ndarray)):
            flat_set.update(item)
        elif pd.notna(item): # Skip any NaN values safely
            flat_set.add(item)
    return list(flat_set)



def update_summaries():
    all_summary_files = list(DATA_DIR_SUM.glob("*.csv")) + list(DATA_DIR_SUM.glob("*.xlsx"))

    if not all_summary_files:
        print("No sumamry files found in raw data/summary. Skipping this step")
        return
    
    processed_files = set()

    # Check with summary files if it has been appended historically
    if SUMMARY_FILE.exists():
        existing_archive = pd.read_parquet(SUMMARY_FILE)
        
        if "source_file" in existing_archive.columns:
            # Flatten any nested arrays or lists down to a pristine set of raw strings
            processed_files = set()
            for item in existing_archive["source_file"].dropna():
                if isinstance(item, (list, np.ndarray)):
                    processed_files.update(item)
                else:
                    processed_files.add(item)
        else:
            processed_files = set()
    else:
        existing_archive = pd.DataFrame()
        processed_files = set()

    # Identify new occasion files
    new_files = [f for f in all_summary_files if f.name not in processed_files]
    if not new_files:
        print("Sumamry files are up to date.")
        return
    
    new_batches = []
    for file_path in new_files:
        print(f"Processing new file: {file_path.name}")
        df = process_summaries(file_path)
        new_batches.append(df)

    new_combined = pd.concat(new_batches, ignore_index=True)
    if not existing_archive.empty:
        updated_archive = pd.concat([existing_archive, new_combined], ignore_index=True)
        updated_archive = updated_archive.drop_duplicates(subset=["occasion", "province", "fiscal_year"], keep="last")
    else: updated_archive = new_combined

    updated_archive['total_funding_temp'] = (
        updated_archive['average_grant_amount'] * updated_archive['number_of_applications_funded']
    )
    updated_archive['total_median_weight_temp'] = (
        updated_archive['median_grant_amount'] * updated_archive['number_of_applications_funded']
    )

    aggregated = updated_archive.groupby(["fiscal_year", "province"]).agg(
        number_of_applications_submitted = ("number_of_applications_submitted", "sum"),
        number_of_applications_funded = ("number_of_applications_funded", "sum"), 
        total_funding_temp=('total_funding_temp', 'sum'),
        total_median_weight_temp=('total_median_weight_temp', 'sum'),
        source_file=('source_file', flatten_source_files)
    ).reset_index()

    aggregated['national_apps_submitted'] = aggregated.groupby('fiscal_year')['number_of_applications_submitted'].transform('sum')
    aggregated['national_apps_funded'] = aggregated.groupby('fiscal_year')['number_of_applications_funded'].transform('sum')

    aggregated["percent_of_total_applications_submitted"] = (
        (aggregated["number_of_applications_submitted"] / aggregated["national_apps_submitted"])*100
    ).fillna(0)

    aggregated['percent_of_applications_funded'] = (
        (aggregated['number_of_applications_funded'] / aggregated['national_apps_funded']) * 100
    ).fillna(0)

    aggregated['provincial_success_rate'] = (round(
        (aggregated['number_of_applications_funded'] / aggregated['number_of_applications_submitted']) * 100, 2)
    ).fillna(0)

    aggregated['average_grant_amount'] = (
        aggregated['total_funding_temp'] / aggregated['number_of_applications_funded']
    ).fillna(0)

    aggregated['median_grant_amount'] = (
        aggregated['total_median_weight_temp'] / aggregated['number_of_applications_funded']
    ).fillna(0)

    aggregated.to_parquet(SUMMARY_FILE, index=False)
    print(f"Updated Summary file. Total global rows: {len(updated_archive)}")


if __name__ == "__main__":
    update_results()
    update_summaries()



    
    


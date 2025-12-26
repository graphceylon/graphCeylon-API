# services/recommender_service/src/ingestion/sltda_loader.py

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Optional, Dict, Any, List

import pandas as pd

# -------------------------------------------------------------------
# Project root (graphCeylon-API/)
# sltda_loader.py is at:
# graphCeylon-API/services/recommender_service/src/ingestion/sltda_loader.py
# parents[4] -> graphCeylon-API
# -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[4]

# Default folders (your paths)
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data/recommender_service/raw/data_raw/sltda_arrivals"
DEFAULT_OUTPUT_CSV = PROJECT_ROOT / "data/recommender_service/clean/sltda_arrivals_monthly.csv"

# Map SLTDA column names → month numbers
MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
MONTH_COLS = list(MONTH_MAP.keys())


def _parse_int(x: Any) -> Optional[int]:
    """Parse ints like '3,129' or '  45 ' or 45.0. Return None if not parseable."""
    if pd.isna(x):
        return None
    s = str(x).strip()
    if s == "":
        return None
    s = s.replace(",", "")
    try:
        return int(float(s))
    except Exception:
        return None


def find_header_row(df_raw: pd.DataFrame) -> int:
    """
    Find the header row by locating a cell that contains 'country' (case-insensitive).
    """
    for idx, row in df_raw.iterrows():
        values = [str(x).strip().lower() for x in row.values]
        if any("country" in v for v in values):
            return idx
    raise ValueError("Could not find a row containing 'country' in this sheet.")


def extract_from_sheet(df_raw: pd.DataFrame, year: int, sheet_name: str, file_name: str) -> pd.DataFrame:
    """
    Extract monthly TOTAL arrivals from a sheet.
    Preference:
      - If a 'Total' row exists in Country column -> use it
      - Else sum all countries per month
    """
    header_idx = find_header_row(df_raw)
    print(f"[SLTDA]   Sheet '{sheet_name}': detected header row at index {header_idx}")

    header = df_raw.iloc[header_idx].astype(str).str.strip().tolist()
    df = df_raw.iloc[header_idx + 1 :].copy()
    df.columns = header
    df = df.dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]

    # Normalize "Country" column
    if "Country" not in df.columns:
        for col in df.columns:
            if str(col).strip().lower() == "country":
                df = df.rename(columns={col: "Country"})
                break

    if "Country" not in df.columns:
        raise ValueError(f"[SLTDA] Sheet '{sheet_name}' of {file_name} has no 'Country' column. Columns={list(df.columns)}")

    # Ensure month columns exist (some sheets may have different formatting)
    available_months = [m for m in MONTH_COLS if m in df.columns]
    if not available_months:
        raise ValueError(f"[SLTDA] Sheet '{sheet_name}' of {file_name} has no month columns {MONTH_COLS}")

    total_rows = df[df["Country"].astype(str).str.strip().str.lower().eq("total")]
    use_total_row = not total_rows.empty

    if use_total_row:
        total_row = total_rows.iloc[0]
        print(f"[SLTDA]   Sheet '{sheet_name}': using Country == 'Total' row.")
    else:
        print(f"[SLTDA]   Sheet '{sheet_name}': no Total row; summing all countries per month.")

    records: List[Dict[str, Any]] = []

    for month_name in available_months:
        month_num = MONTH_MAP[month_name]

        if use_total_row:
            v = _parse_int(total_row[month_name])
            if v is None:
                print(f"[SLTDA]   Sheet '{sheet_name}': month {month_name} is NaN/non-numeric in Total row, skipping.")
                continue
            total_arrivals = v
        else:
            ser = df[month_name].apply(_parse_int)
            if ser.isna().all():
                print(f"[SLTDA]   Sheet '{sheet_name}': month {month_name} all NaN/non-numeric, skipping.")
                continue
            total_arrivals = int(ser.dropna().sum())

        records.append(
            {
                "date": pd.to_datetime(f"{year}-{month_num:02d}-01"),
                "year": year,
                "month": month_num,
                "month_name": month_name,
                "total_arrivals": total_arrivals,
            }
        )

    if not records:
        raise ValueError(f"[SLTDA] Sheet '{sheet_name}' of {file_name}: no monthly totals extracted.")

    out_df = pd.DataFrame(records).sort_values("date")
    print(f"[SLTDA]   Sheet '{sheet_name}' of {file_name}: extracted {len(out_df)} months for {year}.")
    return out_df


def extract_monthly_totals_from_excel(excel_path: Path, year: int) -> pd.DataFrame:
    print(f"[SLTDA] Reading {excel_path.name} for year {year}...")
    all_sheets = pd.read_excel(excel_path, header=None, sheet_name=None)

    last_error = None
    for sheet_name, df_raw in all_sheets.items():
        print(f"[SLTDA] Trying sheet '{sheet_name}'...")
        try:
            return extract_from_sheet(df_raw, year, str(sheet_name), excel_path.name)
        except Exception as e:
            print(f"[SLTDA]   Sheet '{sheet_name}' failed: {e}")
            last_error = e

    raise ValueError(f"[SLTDA] Could not extract from ANY sheet in {excel_path.name}. Last error: {last_error}")


def append_to_master_csv(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        existing = pd.read_csv(output_path, parse_dates=["date"])
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df.copy()

    combined = combined.drop_duplicates(subset=["date"]).sort_values("date")
    combined.to_csv(output_path, index=False)
    print(f"[SLTDA] Saved {len(combined)} rows → {output_path}")


def infer_year_from_filename(path: Path) -> Optional[int]:
    """
    Accepts things like:
      sltda_arrivals_2018.xlsx
      arrivals2019.xlsx
    """
    m = re.search(r"(19|20)\d{2}", path.name)
    return int(m.group(0)) if m else None


def main():
    parser = argparse.ArgumentParser(
        description="Extract monthly total tourist arrivals from SLTDA Excel files."
    )
    parser.add_argument(
        "--input_dir",
        type=str,
        required=True,
        help="Directory containing SLTDA arrival Excel files (2018–2025)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/recommender_service/clean/sltda_arrivals_monthly.csv",
        help="Path to the master monthly arrivals CSV",
    )

    args = parser.parse_args()

    input_dir = PROJECT_ROOT / args.input_dir
    output_path = PROJECT_ROOT / args.output

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    excel_files = sorted(input_dir.glob("*.xlsx"))

    if not excel_files:
        raise ValueError("No Excel files found in input directory.")

    for excel_path in excel_files:
        # Extract year from filename (e.g., sltda_arrivals_2018.xlsx)
        year = int("".join(filter(str.isdigit, excel_path.stem)))

        print(f"\n[SLTDA] Processing {excel_path.name} (year={year})")
        df_year = extract_monthly_totals_from_excel(excel_path, year)
        append_to_master_csv(df_year, output_path)



if __name__ == "__main__":
    main()

# src/ingestion/sltda_loader.py

import argparse
from pathlib import Path

import pandas as pd

# Map SLTDA column names → month numbers
MONTH_MAP = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def find_header_row(df_raw: pd.DataFrame) -> int:
    """
    Find the row index that contains the column header (where a cell contains 'country').

    We read the Excel with header=None, so rows are 0,1,2,... and we search for 'country'
    (case-insensitive, substring) anywhere in each row.
    """
    for idx, row in df_raw.iterrows():
        values = [str(x).strip().lower() for x in row.values]
        if any("country" in v for v in values):
            return idx

    raise ValueError("Could not find a row containing 'country' (any case) in this sheet.")


def extract_from_sheet(df_raw: pd.DataFrame, year: int, sheet_name: str, file_name: str) -> pd.DataFrame:
    """
    Try to extract monthly totals from a single sheet dataframe.

    Strategy:
    1. Detect header row by looking for a cell containing 'country'
    2. Ensure we have a 'Country' column
    3. Prefer a row where Country == 'Total'   (if present)
    4. If no such row, compute monthly totals by summing all countries
    """
    header_idx = find_header_row(df_raw)
    print(f"[SLTDA]   Sheet '{sheet_name}': detected header row at index {header_idx}")

    # Header row -> column names
    header = df_raw.iloc[header_idx].astype(str).str.strip().tolist()

    # Data starts after header
    df = df_raw.iloc[header_idx + 1 :].copy()
    df.columns = header

    # Drop fully empty rows
    df = df.dropna(how="all")

    # Normalize column names (strip)
    df.columns = [str(c).strip() for c in df.columns]

    # Normalise Country column name (case-insensitive)
    if "Country" not in df.columns:
        for col in df.columns:
            if str(col).strip().lower() == "country":
                df = df.rename(columns={col: "Country"})
                break

    if "Country" not in df.columns:
        raise ValueError(
            f"[SLTDA] Sheet '{sheet_name}' of {file_name} has no 'Country' column "
            f"after header detection. Columns: {df.columns}"
        )

    # Try to find a 'Total' row
    total_rows = df[df["Country"].astype(str).str.strip().str.lower().eq("total")]
    use_total_row = not total_rows.empty

    if use_total_row:
        print(f"[SLTDA]   Sheet '{sheet_name}': using row where Country == 'Total'.")
        total_row = total_rows.iloc[0]
    else:
        print(
            f"[SLTDA]   Sheet '{sheet_name}': no row where Country == 'Total'; "
            f"will sum all countries per month instead."
        )

    records = []

    for col_name, month_num in MONTH_MAP.items():
        if col_name not in df.columns:
            print(
                f"[SLTDA]   Sheet '{sheet_name}': column '{col_name}' not found, skipping..."
            )
            continue

        if use_total_row:
            # --- old behaviour: take value from Total row ---
            raw_val = total_row[col_name]

            if pd.isna(raw_val):
                print(
                    f"[SLTDA]   Sheet '{sheet_name}': month {col_name} is NaN in Total row, skipping..."
                )
                continue

            if isinstance(raw_val, str):
                cleaned = raw_val.replace(",", "").strip()
                if cleaned == "":
                    print(
                        f"[SLTDA]   Sheet '{sheet_name}': empty string for {col_name} in Total row, skipping..."
                    )
                    continue
                total_arrivals = int(cleaned)
            else:
                total_arrivals = int(raw_val)

        else:
            # --- new behaviour: sum all rows for that month ---
            ser = df[col_name]

            # Clean commas and blanks
            ser_clean = (
                ser.astype(str)
                .str.replace(",", "", regex=False)
                .str.strip()
            )

            numeric = pd.to_numeric(ser_clean, errors="coerce")
            if numeric.isna().all():
                print(
                    f"[SLTDA]   Sheet '{sheet_name}': all values for {col_name} are non-numeric/NaN, skipping..."
                )
                continue

            total_arrivals = int(numeric.sum(skipna=True))

        date_str = f"{year}-{month_num:02d}-01"
        records.append(
            {
                "date": date_str,
                "year": int(year),
                "month": int(month_num),
                "month_name": col_name,
                "total_arrivals": total_arrivals,
            }
        )

    if not records:
        raise ValueError(
            f"[SLTDA] Sheet '{sheet_name}' of {file_name}: no monthly totals extracted."
        )

    out_df = pd.DataFrame.from_records(records)
    out_df["date"] = pd.to_datetime(out_df["date"])

    print(
        f"[SLTDA]   Sheet '{sheet_name}' of {file_name}: extracted {len(out_df)} months for year {year}."
    )
    return out_df



def extract_monthly_totals_from_excel(excel_path: Path, year: int) -> pd.DataFrame:
    """
    Read a single SLTDA Excel (possibly with multiple sheets) and return a tidy dataframe:

    columns: date, year, month, month_name, total_arrivals
    """
    print(f"[SLTDA] Reading {excel_path} for year {year}...")

    # Read all sheets, no headers
    all_sheets = pd.read_excel(excel_path, header=None, sheet_name=None)

    last_error = None
    for sheet_name, df_raw in all_sheets.items():
        print(f"[SLTDA] Trying sheet '{sheet_name}'...")
        try:
            out_df = extract_from_sheet(df_raw, year, str(sheet_name), excel_path.name)
            # If success, return immediately
            return out_df
        except Exception as e:
            print(f"[SLTDA]   Sheet '{sheet_name}' failed: {e}")
            last_error = e

    # If all sheets failed
    raise ValueError(
        f"[SLTDA] Could not extract monthly totals from ANY sheet in {excel_path.name}. "
        f"Last error: {last_error}"
    )


def append_to_master_csv(df: pd.DataFrame, output_path: Path) -> None:
    """
    Append a year's data to the master CSV (creating it if needed).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        print(f"[SLTDA] Master file {output_path} exists. Appending...")
        existing = pd.read_csv(output_path, parse_dates=["date"])
        combined = pd.concat([existing, df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["date"]).sort_values("date")
    else:
        print(f"[SLTDA] Creating new master file {output_path}...")
        combined = df.sort_values("date")

    combined.to_csv(output_path, index=False)
    print(f"[SLTDA] Saved {len(combined)} rows → {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract monthly total tourist arrivals from SLTDA Excel and update master CSV."
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Year of the SLTDA data (e.g., 2019)",
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to the SLTDA Excel file for that year",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data_clean/forecast/sltda_arrivals_monthly.csv",
        help="Path to the master monthly arrivals CSV",
    )

    args = parser.parse_args()

    excel_path = Path(args.input)
    output_path = Path(args.output)

    df_year = extract_monthly_totals_from_excel(excel_path, args.year)
    append_to_master_csv(df_year, output_path)


if __name__ == "__main__":
    main()

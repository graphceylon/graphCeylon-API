from pathlib import Path
import pandas as pd

CSV = Path("data/recommender_service/clean/sltda_arrivals_monthly.csv")
SARIMA_FORECAST_CSV = Path("data/recommender_service/forecast/sltda_arrivals_sarima_forecast.csv")


def forecast_month_arrivals(month_start):
    """
    Sustainability-aware fallback forecast (TEMP until real SARIMA is wired):

    Goal:
    - Still NEVER raise (safe for production/dev).
    - Avoid using the *last known month* blindly (often a high-recovery month),
      which makes many districts classify as 'VeryHigh' when compared to 2018–2019 baselines.
    - Instead, anchor to the 2018–2019 baseline mean and allow only limited uplift.

    Logic:
    1) Parse CSV robustly (auto-detect date & arrivals columns).
    2) Compute baseline_mean = mean(arrivals for 2018–2019).
    3) Compute last_known = last non-null arrivals.
    4) scale = last_known / baseline_mean
    5) capped_scale = min(scale, 1.25)  # cap uplift to +25% over baseline
    6) forecast = baseline_mean * capped_scale
    7) If baseline is missing, fall back to last_known.
    8) If all fails, return 200_000.0
    """
    try:
                # ---------- 1) SARIMA forecast override ----------
        if SARIMA_FORECAST_CSV.exists():
            fdf = pd.read_csv(SARIMA_FORECAST_CSV)
            if not fdf.empty and "date" in fdf.columns:
                fdf["date"] = pd.to_datetime(fdf["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()

                col = None
                if "forecast_total_arrivals" in fdf.columns:
                    col = "forecast_total_arrivals"
                elif "forecast" in fdf.columns:
                    col = "forecast"
                elif "yhat" in fdf.columns:
                    col = "yhat"

                if col:
                    ms = pd.to_datetime(month_start).to_period("M").to_timestamp()
                    row = fdf.loc[fdf["date"] == ms, col]
                    if not row.empty and pd.notna(row.iloc[0]):
                        return float(row.iloc[0])

        df = pd.read_csv(CSV)
        if df.empty:
            return 200_000.0

        # detect columns
        cols = {str(c).strip().lower(): c for c in df.columns}
        date_col = cols.get("date") or cols.get("ds") or list(df.columns)[0]

        arr_col = cols.get("arrivals") or cols.get("total_arrivals") or cols.get("foreign_arrivals")
        if not arr_col:
            for low, orig in cols.items():
                if "arrival" in low:
                    arr_col = orig
                    break
        if not arr_col:
            # can't detect arrivals column -> hard fallback
            return 200_000.0

        # parse + sort
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df[arr_col] = pd.to_numeric(df[arr_col], errors="coerce")
        df = df.dropna(subset=[date_col]).sort_values(date_col)

        # last known
        last_series = df[arr_col].dropna()
        if last_series.empty:
            return 200_000.0
        last_known = float(last_series.iloc[-1])

        # 2018–2019 baseline mean
        baseline_df = df[df[date_col].dt.year.isin([2018, 2019])]
        baseline_mean = float(baseline_df[arr_col].dropna().mean()) if not baseline_df.empty else float("nan")

        # if no baseline, fallback to last known
        if pd.isna(baseline_mean) or baseline_mean <= 0:
            return last_known

        # cap uplift to reduce "always VeryHigh" bias
        scale = last_known / baseline_mean
        capped_scale = min(scale, 1.25)

        return float(baseline_mean * capped_scale)

    except Exception:
        # absolute fallback constant if file is broken
        return 200_000.0

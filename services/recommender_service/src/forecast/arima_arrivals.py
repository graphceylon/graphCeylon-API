# src/forecast/arima_arrivals.py

import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas.tseries.offsets import MonthBegin
from statsmodels.tsa.arima.model import ARIMA

INPUT_CSV = Path("data_clean/forecast/sltda_arrivals_monthly.csv")
OUTPUT_CSV = Path("data_clean/forecast/sltda_arrivals_arima_forecast.csv")


def load_arrivals():
    df = pd.read_csv(INPUT_CSV, parse_dates=["date"])
    df = df.sort_values("date")
    df = df.set_index("date")

    # Make sure index is a DatetimeIndex (it already is, but be explicit)
    df.index = pd.to_datetime(df.index)

    # ✅ Improvement 1: handle COVID-era collapse by interpolating
    # Treat very low arrivals as missing and interpolate so ARIMA
    # doesn't treat the pandemic shock as a recurring seasonal pattern.
    df["total_arrivals"] = df["total_arrivals"].astype(float)
    df.loc[df["total_arrivals"] < 1000, "total_arrivals"] = np.nan
    df["total_arrivals"] = df["total_arrivals"].interpolate(method="linear")

    return df


def run_arima_forecast(df, forecast_months: int = 12) -> pd.DataFrame:
    """
    Fit ARIMA baseline and forecast N future months.
    We manually build the future date index so statsmodels'
    lack-of-frequency warnings don't break us.
    """
    series = df["total_arrivals"]

    # Simple baseline model; you can later tune (p,d,q)
    model = ARIMA(series, order=(1, 1, 1))
    fitted = model.fit()

    # Get numeric forecast values
    forecast_values = fitted.forecast(steps=forecast_months)

    # Build proper monthly datetime index for the forecast
    last_date = df.index.max()
    # next month start
    start_future = last_date + MonthBegin(1)
    future_index = pd.date_range(start=start_future, periods=forecast_months, freq="MS")

    future_df = pd.DataFrame(
        {
            "date": future_index,
            "forecast_total_arrivals": forecast_values.values,
        }
    )

    return future_df


def evaluate_arima(df, val_months: int = 12):
    """
    Evaluate ARIMA on a hold-out validation period (last N months).
    Returns RMSE and MAE on the original scale.
    """
    series = df["total_arrivals"]

    if len(series) <= val_months + 5:
        print("[ARIMA] Not enough data for a separate validation split; skipping metrics.")
        return None, None

    train = series.iloc[:-val_months]
    val = series.iloc[-val_months:]

    model = ARIMA(train, order=(1, 1, 1))
    fitted = model.fit()
    forecast_vals = fitted.forecast(steps=val_months)

    y_true = val.values
    y_pred = forecast_vals.values

    mse = np.mean((y_true - y_pred) ** 2)
    rmse = math.sqrt(mse)
    mae = np.mean(np.abs(y_true - y_pred))

    print(
        f"[ARIMA] Validation window: {val.index.min().date()} → {val.index.max().date()}"
    )
    print(f"[ARIMA] Validation RMSE: {rmse:.2f}")
    print(f"[ARIMA] Validation MAE : {mae:.2f}")

    return rmse, mae


def main():
    print("\n=== Running ARIMA baseline forecasting ===")
    df = load_arrivals()
    print(
        f"[ARIMA] Loaded {len(df)} monthly points from "
        f"{df.index.min().date()} to {df.index.max().date()}"
    )

    # 🔎 Evaluate ARIMA on a hold-out period (e.g. last 12 months)
    evaluate_arima(df, val_months=12)

    # 🔮 Train on full series and forecast next 12 months
    future_df = run_arima_forecast(df, forecast_months=12)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    future_df.to_csv(OUTPUT_CSV, index=False)
    print(f"[ARIMA] Saved 12-month forecast → {OUTPUT_CSV}")

    # ✅ Optional Improvement 3: smooth forecast in the plot (3-month moving average)
    forecast_series = pd.Series(
        future_df["forecast_total_arrivals"].values, index=future_df["date"]
    )
    forecast_smooth = forecast_series.rolling(window=3, min_periods=1).mean()

    # Plot historical + smoothed forecast
    plt.figure(figsize=(12, 6))
    plt.plot(df.index, df["total_arrivals"], label="Historical")
    plt.plot(
        forecast_smooth.index,
        forecast_smooth.values,
        label="ARIMA Forecast (3-month MA)",
    )
    plt.title("SLTDA Monthly Tourist Arrivals Forecast (ARIMA)")
    plt.legend()
    plt.tight_layout()
    plt.savefig("data_clean/forecast/arima_plot.png")
    print("[ARIMA] Saved plot → data_clean/forecast/arima_plot.png")


if __name__ == "__main__":
    main()

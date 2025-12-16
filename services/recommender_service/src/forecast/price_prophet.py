# src/forecast/price_prophet.py

import os
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from prophet import Prophet
from sklearn.metrics import mean_squared_error, mean_absolute_error
import numpy as np


# ---------- Paths ----------

BASE_DIR = Path(__file__).resolve().parents[2]  # .../component3_service
DATA_RAW_PRICE = BASE_DIR / "data_raw" / "price" / "hotel_price_overall.csv"
DATA_CLEAN_FORECAST = BASE_DIR / "data_clean" / "forecast"
DATA_CLEAN_FORECAST.mkdir(parents=True, exist_ok=True)


# ---------- Helpers ----------

def load_price_series(path: Path) -> pd.DataFrame:
    """
    Load raw hotel price series and prepare for Prophet.
    Expected columns: date, avg_price_lkr
    """
    if not path.exists():
        raise FileNotFoundError(f"Price CSV not found: {path}")

    df = pd.read_csv(path)

    # Basic validation
    required_cols = {"date", "avg_price_lkr"}
    if not required_cols.issubset(df.columns):
        raise ValueError(
            f"CSV must contain columns {required_cols}, found {df.columns.tolist()}"
        )

    # Ensure datetime and sort
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # Prophet needs columns 'ds' (date) and 'y' (value)
    df_prophet = df.rename(columns={"date": "ds", "avg_price_lkr": "y"})

    return df_prophet


def train_test_split_time_series(df: pd.DataFrame, test_months: int = 6):
    """
    Split a Prophet-style df into train/test by time.
    """
    if len(df) <= test_months + 5:
        # not enough data to do a proper split – just train on all
        return df, None

    train_df = df.iloc[:-test_months].copy()
    test_df = df.iloc[-test_months:].copy()
    return train_df, test_df


# ---------- Main pipeline ----------

def run_prophet_price_forecast(
    input_path: Path = DATA_RAW_PRICE,
    forecast_months: int = 12,
):
    print("=== Running Prophet price forecasting ===")

    df = load_price_series(input_path)
    print(f"[PRICE] Loaded {len(df)} points from {input_path.name}")

    # Train/test split
    train_df, test_df = train_test_split_time_series(df, test_months=6)

    # Define model (you can tweak seasonality later for research)
    m = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        interval_width=0.8,
    )

    m.fit(train_df)

    # Make a future dataframe
    # periods = number of months to forecast ahead
    future = m.make_future_dataframe(periods=forecast_months, freq="MS")  # Month start
    forecast = m.predict(future)

    # Save only the forecast part for the future months
    forecast_future = forecast.tail(forecast_months)[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    forecast_future.rename(
        columns={
            "ds": "date",
            "yhat": "forecast_avg_price_lkr",
            "yhat_lower": "forecast_lower",
            "yhat_upper": "forecast_upper",
        },
        inplace=True,
    )

    out_csv = DATA_CLEAN_FORECAST / "hotel_price_prophet_forecast.csv"
    forecast_future.to_csv(out_csv, index=False)
    print(f"[PRICE] Saved {forecast_months}-month forecast → {out_csv}")

    # ---------- Evaluation on the last 6 months (if we had a test set) ----------
    if test_df is not None:
        # get model predictions for the full historical timeline
        full_forecast = forecast.set_index("ds").loc[test_df["ds"]]
        y_true = test_df["y"].values
        y_pred = full_forecast["yhat"].values

        rmse = mean_squared_error(y_true, y_pred, squared=False)
        mae = mean_absolute_error(y_true, y_pred)

        print(f"[PRICE] Validation RMSE: {rmse:,.2f} LKR")
        print(f"[PRICE] Validation MAE : {mae:,.2f} LKR")
    else:
        print("[PRICE] Not enough data for train/test split; trained on full series.")

    # ---------- Plot ----------
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df["ds"], df["y"], label="Historical avg price")
    ax.plot(
        forecast["ds"],
        forecast["yhat"],
        label="Prophet forecast",
        linestyle="--",
    )
    ax.set_title("Hotel Price Forecast (Prophet)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Average price (LKR)")
    ax.legend()

    out_plot = DATA_CLEAN_FORECAST / "hotel_price_prophet_plot.png"
    plt.tight_layout()
    plt.savefig(out_plot)
    plt.close(fig)
    print(f"[PRICE] Saved plot → {out_plot}")


if __name__ == "__main__":
    run_prophet_price_forecast()

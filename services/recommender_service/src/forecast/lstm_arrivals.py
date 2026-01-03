# src/forecast/lstm_arrivals.py

import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import MinMaxScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


INPUT_CSV = Path("data_clean/forecast/sltda_arrivals_monthly.csv")
OUTPUT_CSV = Path("data_clean/forecast/sltda_arrivals_lstm_forecast.csv")
PLOT_PATH = Path("data_clean/forecast/lstm_plot.png")


# -----------------------------
# 1. Utility: dataset loading
# -----------------------------
def load_arrivals():
    df = pd.read_csv(INPUT_CSV, parse_dates=["date"])
    df = df.sort_values("date")
    df = df.set_index("date")
    df.index = pd.to_datetime(df.index)

    # ✅ Improvement 1: handle COVID-era collapse (e.g. 0 arrivals) via interpolation
    # Treat very small values as missing and interpolate over them so the model
    # doesn't learn the pandemic shock as "normal" behaviour.
    df["total_arrivals"] = df["total_arrivals"].astype(float)
    df.loc[df["total_arrivals"] < 1000, "total_arrivals"] = np.nan
    df["total_arrivals"] = df["total_arrivals"].interpolate(method="linear")

    return df


def create_sequences(data: np.ndarray, window_size: int):
    """
    Turn a 1D array into (X, y) sequences with sliding window.
    X shape: (num_samples, window_size, 1)
    y shape: (num_samples, 1)
    """
    xs, ys = [], []
    for i in range(len(data) - window_size):
        x = data[i : i + window_size]
        y = data[i + window_size]
        xs.append(x)
        ys.append(y)
    xs = np.array(xs)
    ys = np.array(ys)
    return xs, ys


# -----------------------------
# 2. LSTM model definition
# -----------------------------
class LSTMArrivals(nn.Module):
    def __init__(self, input_size=1, hidden_size=64, num_layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout,
        )
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x):
        # x: (batch, seq_len, input_size)
        out, _ = self.lstm(x)
        # Take output of last time step
        out = out[:, -1, :]
        out = self.fc(out)
        return out


# -----------------------------
# 3. Training + forecasting
# -----------------------------
def train_lstm_model(
    train_loader: DataLoader,
    val_loader: DataLoader,
    n_epochs: int = 80,
    lr: float = 1e-3,
    device: str = "cpu",
):
    model = LSTMArrivals().to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    for epoch in range(1, n_epochs + 1):
        model.train()
        train_losses = []
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)

            optimizer.zero_grad()
            preds = model(xb)
            loss = criterion(preds, yb)
            loss.backward()
            optimizer.step()
            train_losses.append(loss.item())

        # simple validation
        model.eval()
        val_losses = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device)
                yb = yb.to(device)
                preds = model(xb)
                loss = criterion(preds, yb)
                val_losses.append(loss.item())

        if epoch % 10 == 0 or epoch == 1:
            print(
                f"[LSTM] Epoch {epoch}/{n_epochs} "
                f"- train_loss={np.mean(train_losses):.6f} "
                f"- val_loss={np.mean(val_losses):.6f}"
            )

    return model


def forecast_future(
    model: nn.Module,
    last_window: np.ndarray,
    forecast_steps: int,
    scaler: MinMaxScaler,
    device: str = "cpu",
):
    """
    Autoregressive forecast:
    - last_window is a (window_size, 1) normalized array
    - we repeatedly feed the window and append prediction
    """
    model.eval()
    window = last_window.copy()  # (win, 1)
    preds_scaled = []

    with torch.no_grad():
        for _ in range(forecast_steps):
            x = torch.tensor(window, dtype=torch.float32).unsqueeze(0).to(device)
            y_hat = model(x)  # (1, 1)
            y_hat_val = y_hat.cpu().numpy()[0, 0]

            # append to list
            preds_scaled.append(y_hat_val)

            # slide the window: drop first, add new prediction at end
            window = np.vstack([window[1:], [[y_hat_val]]])

    # inverse transform to original scale
    preds_scaled = np.array(preds_scaled).reshape(-1, 1)
    preds = scaler.inverse_transform(preds_scaled)
    return preds.ravel()


# -----------------------------
# 4. Main pipeline
# -----------------------------
def main():
    print("\n=== Running LSTM forecasting for tourist arrivals ===")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[LSTM] Using device: {device}")

    df = load_arrivals()
    series = df["total_arrivals"].values.astype(float).reshape(-1, 1)
    n_samples = len(series)
    print(f"[LSTM] Loaded {n_samples} monthly points.")

    # ✅ Improvement 2: Normalize series to [0, 1] for stable LSTM training
    scaler = MinMaxScaler()
    series_scaled = scaler.fit_transform(series)

    window_size = 12  # 12 months → predict next month
    X, y = create_sequences(series_scaled, window_size)

    # Train/val split (80/20 on sequences)
    train_size = int(len(X) * 0.8)
    X_train, X_val = X[:train_size], X[train_size:]
    y_train, y_val = y[:train_size], y[train_size:]

    # Convert to tensors
    X_train_t = torch.tensor(X_train, dtype=torch.float32)
    y_train_t = torch.tensor(y_train, dtype=torch.float32)
    X_val_t = torch.tensor(X_val, dtype=torch.float32)
    y_val_t = torch.tensor(y_val, dtype=torch.float32)

    train_ds = TensorDataset(X_train_t, y_train_t)
    val_ds = TensorDataset(X_val_t, y_val_t)

    train_loader = DataLoader(train_ds, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=16)

    # Train model
    model = train_lstm_model(
        train_loader=train_loader,
        val_loader=val_loader,
        n_epochs=80,
        lr=1e-3,
        device=device,
    )

    # Evaluate on validation set (for metrics in your thesis)
    model.eval()
    with torch.no_grad():
        val_preds = model(X_val_t.to(device)).cpu().numpy()

    # Inverse scale for metrics
    y_val_orig = scaler.inverse_transform(y_val.reshape(-1, 1)).ravel()
    val_preds_orig = scaler.inverse_transform(val_preds.reshape(-1, 1)).ravel()

    mse = np.mean((y_val_orig - val_preds_orig) ** 2)
    rmse = math.sqrt(mse)
    mae = np.mean(np.abs(y_val_orig - val_preds_orig))

    print(f"[LSTM] Validation RMSE: {rmse:.2f}")
    print(f"[LSTM] Validation MAE : {mae:.2f}")

    # Forecast next 12 months using last window from full series
    last_window = series_scaled[-window_size:]
    forecast_steps = 12
    future_preds = forecast_future(
        model=model,
        last_window=last_window,
        forecast_steps=forecast_steps,
        scaler=scaler,
        device=device,
    )

    # ✅ Improvement 3: smooth forecast with 3-month moving average (for plotting)
    # Keep raw predictions for CSV; use smoothed curve only for visualization.
    last_date = df.index.max()
    future_dates = pd.date_range(
        start=last_date + pd.offsets.MonthBegin(1),
        periods=forecast_steps,
        freq="MS",
    )

    future_series_raw = pd.Series(future_preds, index=future_dates)
    future_series_smooth = future_series_raw.rolling(window=3, min_periods=1).mean()

    future_df = pd.DataFrame(
        {
            "date": future_dates,
            "forecast_total_arrivals": future_preds,  # raw values for downstream use
        }
    )

    # Save CSV
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    future_df.to_csv(OUTPUT_CSV, index=False)
    print(f"[LSTM] Saved 12-month forecast → {OUTPUT_CSV}")

    # Plot historical vs smoothed forecast
    plt.figure(figsize=(12, 6))
    plt.plot(df.index, df["total_arrivals"], label="Historical")
    plt.plot(
        future_series_smooth.index,
        future_series_smooth.values,
        label="LSTM Forecast (3-month MA)",
    )
    plt.title("SLTDA Monthly Tourist Arrivals Forecast (LSTM)")
    plt.legend()
    plt.tight_layout()

    PLOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(PLOT_PATH)
    print(f"[LSTM] Saved plot → {PLOT_PATH}")


if __name__ == "__main__":
    # For reproducibility
    torch.manual_seed(42)
    np.random.seed(42)
    main()

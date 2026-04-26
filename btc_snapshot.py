"""
BTC/USDT Market Snapshot
Fetches OHLCV data from Bybit via ccxt and computes technical indicators.

Dependencies:
    pip install ccxt pandas
"""

import json
import sys
from datetime import datetime, timezone

import ccxt
import pandas as pd

from divergence import detect_rsi_divergence


# ─── Configuration ────────────────────────────────────────────────────────────

EXCHANGE_ID = "bybit"       # swap to "binance" if needed
SYMBOL      = "BTC/USDT"
TIMEFRAME   = "15m"
LIMIT       = 200           # number of candles to fetch


# ─── Data Fetching ────────────────────────────────────────────────────────────

def fetch_ohlcv(exchange_id: str, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Fetch OHLCV candles from the exchange and return a DataFrame."""
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({"enableRateLimit": True})

        raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except ccxt.NetworkError as e:
        sys.exit(f"[NetworkError] Could not reach {exchange_id}: {e}")
    except ccxt.ExchangeError as e:
        sys.exit(f"[ExchangeError] {exchange_id} returned an error: {e}")
    except AttributeError:
        sys.exit(f"[ConfigError] Unknown exchange id: '{exchange_id}'")

    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").sort_index()
    return df


# ─── Indicators ───────────────────────────────────────────────────────────────

def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's smoothed RSI."""
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs  = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range using Wilder smoothing."""
    high, low, prev_close = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Attach RSI, EMA20, EMA50, ATR columns to the DataFrame in place."""
    df["rsi"]   = compute_rsi(df["close"], period=14)
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["atr"]   = compute_atr(df, period=14)
    return df


# ─── Snapshot Builder ─────────────────────────────────────────────────────────

def build_snapshot(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    last_n: int = 20,
) -> dict:
    """Collect the latest values and assemble the JSON snapshot."""
    last = df.iloc[-1]

    # Volume stats over last 20 candles
    vol_window  = df["volume"].iloc[-last_n:]
    vol_current = float(last["volume"])
    vol_avg20   = float(vol_window.mean())
    vol_trend   = "above_average" if vol_current >= vol_avg20 else "below_average"

    # Last N candles as records
    candle_slice = df.iloc[-last_n:].reset_index()
    candles = [
        {
            "timestamp": row["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open":      round(row["open"],   2),
            "high":      round(row["high"],   2),
            "low":       round(row["low"],    2),
            "close":     round(row["close"],  2),
            "volume":    round(row["volume"], 4),
        }
        for _, row in candle_slice.iterrows()
    ]

    divergence = detect_rsi_divergence(df, timeframe=timeframe)

    snapshot = {
        "symbol":    symbol,
        "timeframe": timeframe,
        "price":     round(float(last["close"]), 2),
        "rsi":       round(float(last["rsi"]),   2),
        "ema20":     round(float(last["ema20"]), 2),
        "ema50":     round(float(last["ema50"]), 2),
        "atr":       round(float(last["atr"]),   2),
        "volume": {
            "current":      round(vol_current, 4),
            "avg_20":       round(vol_avg20,   4),
            "trend":        vol_trend,
        },
        **divergence,
        "last_20_candles": candles,
    }
    return snapshot


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Fetching {LIMIT} × {TIMEFRAME} candles for {SYMBOL} from {EXCHANGE_ID}…",
          file=sys.stderr)

    df = fetch_ohlcv(EXCHANGE_ID, SYMBOL, TIMEFRAME, LIMIT)
    df = add_indicators(df)

    snapshot = build_snapshot(df, SYMBOL, TIMEFRAME)
    print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()

"""
RSI Divergence Detector
=======================
Detects bullish and bearish RSI divergences on OHLCV + RSI DataFrame.

Expected DataFrame columns:
    high, low, rsi  — with timestamp as index (pd.DatetimeIndex)

Usage:
    from divergence import detect_rsi_divergence
    result = detect_rsi_divergence(df)
"""

import json
from itertools import combinations

import pandas as pd


# ─── Configuration ────────────────────────────────────────────────────────────

LOOKBACK        = 100   # recent candles to analyse
SWING_N         = 3     # strict candles required on EACH side of a swing point
MAX_SWING_PAIRS = 5     # how many recent swing points to consider
MIN_SWINGS      = 2     # minimum swing points needed

# RSI delta thresholds for strength classification
WEAK_THRESH     = 3.0
STRONG_THRESH   = 7.0

# Required columns in the input DataFrame
REQUIRED_COLS   = {"high", "low", "rsi"}

# Timeframes that use right_confirmation=True (confirmed mode).
# Daily and weekly charts — signals are slow anyway, better to avoid false positives.
# Everything else uses right_confirmation=False (real-time, no delay).
RIGHT_CONFIRMATION_TIMEFRAMES = {"1d", "3d", "1w", "1M"}

# Automatic swing_n by timeframe.
# Lower timeframes → more neighbours needed to filter noise.
# Higher timeframes → fewer neighbours to avoid excessive confirmation lag.
SWING_N_BY_TIMEFRAME: dict = {
    "1m":  5,
    "3m":  5,
    "5m":  4,
    "15m": 3,
    "30m": 3,
    "1h":  3,
    "2h":  2,
    "4h":  2,
    "6h":  2,
    "12h": 2,
    "1d":  2,
    "3d":  1,
    "1w":  1,
    "1M":  1,
}


def resolve_swing_n(timeframe: str = None) -> int:
    """
    Return the appropriate swing_n for a given timeframe string.
    Falls back to SWING_N if the timeframe is unknown.
    """
    if not timeframe:
        return SWING_N
    return SWING_N_BY_TIMEFRAME.get(timeframe.strip(), SWING_N)


def resolve_right_confirmation(timeframe: str = None) -> bool:
    """
    Return True (confirmed mode) for daily/weekly timeframes where
    avoiding false positives matters more than speed.
    Return False (real-time, no delay) for intraday timeframes.
    """
    if not timeframe:
        return True
    return timeframe.strip() in RIGHT_CONFIRMATION_TIMEFRAMES


# ─── Validation ───────────────────────────────────────────────────────────────

def validate_dataframe(df: pd.DataFrame) -> None:
    """Raise ValueError if required columns are missing or DataFrame is empty."""
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"DataFrame is missing required columns: {sorted(missing)}. "
            f"Expected: {sorted(REQUIRED_COLS)}."
        )
    if df.empty:
        raise ValueError("DataFrame is empty.")


# ─── Swing Point Detection ────────────────────────────────────────────────────

def find_swing_highs(
    df: pd.DataFrame,
    n: int = SWING_N,
    right_confirmation: bool = True,
) -> pd.DataFrame:
    """
    Strict swing high detection: high[i] must be STRICTLY greater than all N
    neighbours checked via shift(), ensuring no tie passes.

    right_confirmation=True  (default)
        Both left and right neighbours are checked.
        The last N candles can never qualify — they have no right neighbours yet.
        Delay: swing_n candles after the actual peak.

    right_confirmation=False  (real-time mode)
        Only left neighbours are checked.
        The most recent candle can immediately qualify as a swing high.
        Delay: 0 candles, but more false positives on noisy data.
    """
    highs = df["high"]
    mask  = pd.Series(True, index=df.index)

    for offset in range(1, n + 1):
        mask &= highs > highs.shift(offset)         # left side: always required
        if right_confirmation:
            mask &= highs > highs.shift(-offset)    # right side: confirmed mode only

    return df[mask]


def find_swing_lows(
    df: pd.DataFrame,
    n: int = SWING_N,
    right_confirmation: bool = True,
) -> pd.DataFrame:
    """
    Strict swing low detection: low[i] must be STRICTLY less than all N
    neighbours on the left (and optionally right) side.

    See find_swing_highs for right_confirmation semantics.
    """
    lows = df["low"]
    mask = pd.Series(True, index=df.index)

    for offset in range(1, n + 1):
        mask &= lows < lows.shift(offset)
        if right_confirmation:
            mask &= lows < lows.shift(-offset)

    return df[mask]


# ─── Strength Classification ──────────────────────────────────────────────────

def classify_strength(rsi_delta: float) -> str:
    """
    Classify divergence strength by the absolute RSI difference between swings.

        weak   → |Δrsi| < 3
        medium → 3  ≤ |Δrsi| < 7
        strong → |Δrsi| ≥ 7
    """
    abs_delta = abs(rsi_delta)
    if abs_delta >= STRONG_THRESH:
        return "strong"
    if abs_delta >= WEAK_THRESH:
        return "medium"
    return "weak"


# ─── Point Formatting ─────────────────────────────────────────────────────────

def _format_points(prev: pd.Series, last: pd.Series, price_col: str) -> dict:
    """Serialise two swing rows into price_points / rsi_points lists."""
    return {
        "price_points": [
            {"timestamp": str(prev.name), "value": round(float(prev[price_col]), 2)},
            {"timestamp": str(last.name), "value": round(float(last[price_col]), 2)},
        ],
        "rsi_points": [
            {"timestamp": str(prev.name), "value": round(float(prev["rsi"]), 2)},
            {"timestamp": str(last.name), "value": round(float(last["rsi"]), 2)},
        ],
    }


# ─── Pair-wise Divergence Search ─────────────────────────────────────────────

def _find_best_bearish(swings: pd.DataFrame) -> tuple[bool, dict]:
    """
    Scan all ordered pairs from the last MAX_SWING_PAIRS swing highs,
    newest-first, and return the most recent valid bearish divergence.

    Bearish:  price HH  (last.high > prev.high)
              RSI   LH  (last.rsi  < prev.rsi)
    """
    pool = swings.iloc[-MAX_SWING_PAIRS:]   # last N swing highs

    # combinations(range(k), 2) yields (i, j) with i < j, i.e. prev_i < last_i.
    # Sort by (j, i) descending → check pairs with the most recent last_i first.
    for prev_i, last_i in sorted(
        combinations(range(len(pool)), 2), key=lambda p: (p[1], p[0]), reverse=True
    ):
        prev, last = pool.iloc[prev_i], pool.iloc[last_i]

        if last["high"] > prev["high"] and last["rsi"] < prev["rsi"]:
            rsi_delta = last["rsi"] - prev["rsi"]   # negative
            return True, {
                "strength":         classify_strength(rsi_delta),
                "last_detected_at": str(last.name),
                **_format_points(prev, last, "high"),
            }

    return False, {}


def _find_best_bullish(swings: pd.DataFrame) -> tuple[bool, dict]:
    """
    Scan all ordered pairs from the last MAX_SWING_PAIRS swing lows,
    newest-first, and return the most recent valid bullish divergence.

    Bullish:  price LL  (last.low  < prev.low)
              RSI   HL  (last.rsi  > prev.rsi)
    """
    pool = swings.iloc[-MAX_SWING_PAIRS:]

    for prev_i, last_i in sorted(
        combinations(range(len(pool)), 2), key=lambda p: (p[1], p[0]), reverse=True
    ):
        prev, last = pool.iloc[prev_i], pool.iloc[last_i]

        if last["low"] < prev["low"] and last["rsi"] > prev["rsi"]:
            rsi_delta = last["rsi"] - prev["rsi"]   # positive
            return True, {
                "strength":         classify_strength(rsi_delta),
                "last_detected_at": str(last.name),
                **_format_points(prev, last, "low"),
            }

    return False, {}


# ─── Main Entry Point ─────────────────────────────────────────────────────────

_EMPTY_RESULT = {
    "type":                       "none",
    "strength":                   None,
    "last_detected_at":           None,
    "price_points":               [],
    "rsi_points":                 [],
    "confirmed":                  True,
    "confirmation_delay_candles": 0,
}


def detect_rsi_divergence(
    df:                 pd.DataFrame,
    lookback:           int  = LOOKBACK,
    swing_n:            int  = None,
    timeframe:          str  = None,
    right_confirmation: bool = None,
) -> dict:
    """
    Analyse recent candles for RSI divergence.

    Parameters
    ----------
    df                 : DataFrame with columns high, low, rsi and DatetimeIndex
    lookback           : number of recent candles to consider (default 100)
    swing_n            : override swing neighbour count; if None, resolved from timeframe
    timeframe          : ccxt timeframe string (e.g. "15m", "1h", "1d") — drives both
                         swing_n and right_confirmation automatically
    right_confirmation : explicit override; if None, resolved from timeframe:
                           1d / 3d / 1w / 1M → True  (confirmed, no false positives)
                           everything else    → False (real-time, zero delay)

    Returns
    -------
    {
        "divergence": {
            "rsi": {
                "type":                       "bullish | bearish | none",
                "strength":                   "weak | medium | strong | null",
                "last_detected_at":           "<ISO timestamp> | null",
                "price_points":               [{"timestamp": ..., "value": ...}, ...],
                "rsi_points":                 [{"timestamp": ..., "value": ...}, ...],
                "confirmation_delay_candles": <int>   ← swing_n used for detection
            }
        }
    }

    Raises
    ------
    ValueError  if required columns are missing or DataFrame is empty
    """
    validate_dataframe(df)

    # Resolve parameters: explicit override > timeframe lookup > global default
    effective_n    = swing_n            if swing_n            is not None else resolve_swing_n(timeframe)
    effective_rc   = right_confirmation if right_confirmation is not None else resolve_right_confirmation(timeframe)

    # Restrict to recent confirmed candles; drop RSI warm-up NaNs
    window = df.dropna(subset=["rsi"]).iloc[-lookback:].copy()

    swing_highs = find_swing_highs(window, n=effective_n, right_confirmation=effective_rc)
    swing_lows  = find_swing_lows(window,  n=effective_n, right_confirmation=effective_rc)

    bear_found, bear_details = (
        _find_best_bearish(swing_highs) if len(swing_highs) >= MIN_SWINGS else (False, {})
    )
    bull_found, bull_details = (
        _find_best_bullish(swing_lows) if len(swing_lows) >= MIN_SWINGS else (False, {})
    )

    # Both found → keep the more recent signal
    if bear_found and bull_found:
        if bear_details["last_detected_at"] >= bull_details["last_detected_at"]:
            bull_found = False
        else:
            bear_found = False

    delay = effective_n if effective_rc else 0

    if bear_found:
        result = {"type": "bearish", **bear_details,
                  "confirmed": effective_rc,
                  "confirmation_delay_candles": delay}
    elif bull_found:
        result = {"type": "bullish", **bull_details,
                  "confirmed": effective_rc,
                  "confirmation_delay_candles": delay}
    else:
        result = {**_EMPTY_RESULT,
                  "confirmed": effective_rc,
                  "confirmation_delay_candles": delay}

    return {"divergence": {"rsi": result}}


# ─── Example Usage ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from btc_snapshot import fetch_ohlcv, add_indicators

    df     = fetch_ohlcv("bybit", "BTC/USDT", "15m", 200)
    df     = add_indicators(df)
    result = detect_rsi_divergence(df)

    print(json.dumps(result, indent=2))

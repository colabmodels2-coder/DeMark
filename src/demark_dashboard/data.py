from __future__ import annotations

import warnings
import time
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf
from datetime import datetime

warnings.filterwarnings("ignore")


def _stooq_symbol(symbol: str) -> str:
    """Map supported Yahoo-style symbols to Stooq symbols."""
    mapping = {
        "EURUSD=X": "eurusd",
        "GBPUSD=X": "gbpusd",
        "JPY=X": "usdjpy",
        "AUDUSD=X": "audusd",
        "USDCAD=X": "usdcad",
        "CHF=X": "usdchf",
        "GC=F": "gc.f",
        "SI=F": "si.f",
        "CL=F": "cl.f",
        "NG=F": "ng.f",
        "ZC=F": "zc.f",
        "ZS=F": "zs.f",
    }

    if symbol in mapping:
        return mapping[symbol]

    # Most US equities/ETFs on Stooq use .us suffix (e.g., spy.us, aapl.us).
    if "=" not in symbol and "." not in symbol:
        return f"{symbol.lower()}.us"

    return symbol.lower()


def _filter_by_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """Trim daily history to requested period length."""
    days = {"6mo": 183, "1y": 365, "2y": 730, "5y": 1825}.get(period)
    if not days or df.empty:
        return df
    cutoff = pd.Timestamp(datetime.now()) - pd.Timedelta(days=days)
    return df[df.index >= cutoff]


def _load_stooq_daily(symbol: str, period: str) -> pd.DataFrame:
    """Fetch daily OHLCV data from Stooq as a Yahoo fallback source."""
    stooq = _stooq_symbol(symbol)
    url = f"https://stooq.com/q/d/l/?s={stooq}&i=d"
    df = pd.read_csv(url)
    if df.empty or "Date" not in df.columns:
        return pd.DataFrame()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).set_index("Date").sort_index()
    required = ["Open", "High", "Low", "Close", "Volume"]
    if any(col not in df.columns for col in required):
        return pd.DataFrame()

    df = df[required].copy()
    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna()
    df = _filter_by_period(df, period)
    return df


def _generate_demo_ohlc(symbol: str, periods: int = 252) -> pd.DataFrame:
    """Generate synthetic OHLC data for demo/testing."""
    dates = pd.date_range(end=datetime.now(), periods=periods, freq="D")
    np.random.seed(hash(symbol) % 2**32)
    
    close = 100 + np.cumsum(np.random.randn(periods) * 2)
    high = close + np.abs(np.random.randn(periods))
    low = close - np.abs(np.random.randn(periods))
    open_prices = np.roll(close, 1)
    open_prices[0] = close[0]
    volumes = np.random.randint(1_000_000, 10_000_000, periods)
    
    df = pd.DataFrame({
        'Open': open_prices,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': volumes
    }, index=dates)
    
    return df


@st.cache_data(show_spinner=False, ttl=1800)
def load_ohlc(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    # Enforce daily data only to reduce provider throttling and meet dashboard scope.
    interval = "1d"
    yahoo_error = None
    for attempt in range(3):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval, auto_adjust=False, progress=False)

            if not df.empty:
                cols = ["Open", "High", "Low", "Close", "Volume"]
                df = df[cols].copy()
                if isinstance(df.index, pd.DatetimeIndex):
                    df.index = df.index.tz_localize(None)
                df.dropna(inplace=True)
                return df
        except Exception as e:
            yahoo_error = e
            if attempt < 2:
                time.sleep(1.25 * (attempt + 1))

    # Daily Stooq fallback can often bypass temporary Yahoo rate limits.
    try:
        stooq_df = _load_stooq_daily(symbol, period)
        if not stooq_df.empty:
            if yahoo_error is not None:
                st.info(
                    f"📡 Yahoo Finance is rate limited for {symbol}. "
                    f"Using Stooq daily data fallback."
                )
            return stooq_df
    except Exception:
        pass

    if yahoo_error is not None:
        error_msg = str(yahoo_error)[:150]
        st.info(
            f"📡 Live Yahoo Finance data unavailable. "
            f"Using synthetic demo data for {symbol}. "
            f"**To restore live data:** Reduce refresh frequency, monitor fewer symbols at once, "
            f"or retry after Yahoo rate limits clear.\n\n"
            f"_Error detail: {error_msg}_"
        )

    try:
        periods = {"6mo": 126, "1y": 252, "2y": 504, "5y": 1260}.get(period, 252)
        return _generate_demo_ohlc(symbol, periods)
    except Exception as demo_error:
        st.error(f"❌ Cannot generate demo data: {str(demo_error)}")
        return pd.DataFrame()



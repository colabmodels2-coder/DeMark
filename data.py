from __future__ import annotations

import warnings
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf
from datetime import datetime

warnings.filterwarnings("ignore")


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


@st.cache_data(show_spinner=False, ttl=300)
def load_ohlc(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
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
        error_msg = str(e)[:150]
        st.info(
            f"📡 Live Yahoo Finance data unavailable. "
            f"Using synthetic demo data for {symbol}. "
            f"**To restore live data:** Check your internet connection and network configuration.\n\n"
            f"_Error detail: {error_msg}_"
        )

    try:
        periods = {"6mo": 126, "1y": 252, "2y": 504, "5y": 1260}.get(period, 252)
        return _generate_demo_ohlc(symbol, periods)
    except Exception as demo_error:
        st.error(f"❌ Cannot generate demo data: {str(demo_error)}")
        return pd.DataFrame()



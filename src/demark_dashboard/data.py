from __future__ import annotations

import warnings
import time
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf
from datetime import datetime

warnings.filterwarnings("ignore")


@st.cache_resource
def _shared_ohlc_cache() -> dict[str, pd.DataFrame]:
    # Shared across users on the same running app instance.
    return {}


def _period_days(period: str) -> int:
    return {"6mo": 183, "1y": 365, "2y": 730, "5y": 1825}.get(period, 365)


def _normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    cols = ["Open", "High", "Low", "Close", "Volume"]
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if any(col not in df.columns for col in cols):
        return pd.DataFrame()
    out = df[cols].copy()
    if isinstance(out.index, pd.DatetimeIndex):
        out.index = out.index.tz_localize(None)
    out.index = pd.to_datetime(out.index, errors="coerce")
    out = out[~out.index.isna()]
    out = out[~out.index.duplicated(keep="last")].sort_index()
    for col in cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna()
    return out


def _cache_get(symbol: str) -> pd.DataFrame:
    cache = _shared_ohlc_cache()
    return cache.get(symbol, pd.DataFrame()).copy()


def _cache_set(symbol: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    cache = _shared_ohlc_cache()
    cache[symbol] = df.copy()


def _merge_ohlc(old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    if old_df.empty:
        return _normalize_ohlc(new_df)
    if new_df.empty:
        return _normalize_ohlc(old_df)
    merged = pd.concat([old_df, new_df], axis=0)
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    return _normalize_ohlc(merged)


def _is_recent(df: pd.DataFrame) -> bool:
    if df.empty:
        return False
    latest = pd.Timestamp(df.index.max()).normalize()
    today = pd.Timestamp(datetime.now().date())
    return latest >= (today - pd.Timedelta(days=2))


def _has_coverage(df: pd.DataFrame, period: str) -> bool:
    if df.empty:
        return False
    cutoff = pd.Timestamp(datetime.now().date()) - pd.Timedelta(days=_period_days(period))
    return df.index.min() <= cutoff


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
    days = _period_days(period)
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
    df = _normalize_ohlc(df)
    return _filter_by_period(df, period)


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
    cached = _cache_get(symbol)

    # If cache is fresh and deep enough, skip external pulls.
    if not cached.empty and _is_recent(cached) and _has_coverage(cached, period):
        return _filter_by_period(cached, period)

    # Primary Yahoo path: yf.download tends to be more stable across yfinance versions.
    for attempt in range(3):
        try:
            if not cached.empty:
                # Incremental refresh over a short overlap window.
                start_dt = (cached.index.max() - pd.Timedelta(days=14)).strftime("%Y-%m-%d")
                df = yf.download(
                    symbol,
                    start=start_dt,
                    interval=interval,
                    auto_adjust=False,
                    progress=False,
                    threads=False,
                )
            else:
                df = yf.download(
                    symbol,
                    period=period,
                    interval=interval,
                    auto_adjust=False,
                    progress=False,
                    threads=False,
                )
            df = _normalize_ohlc(df)
            if not df.empty:
                merged = _merge_ohlc(cached, df)
                _cache_set(symbol, merged)
                return _filter_by_period(merged, period)
        except Exception as e:
            yahoo_error = e
            if attempt < 2:
                time.sleep(1.25 * (attempt + 1))

    # Secondary Yahoo path: Ticker.history fallback without unsupported kwargs.
    if yahoo_error is not None:
        for attempt in range(2):
            try:
                ticker = yf.Ticker(symbol)
                if not cached.empty:
                    start_dt = (cached.index.max() - pd.Timedelta(days=14)).strftime("%Y-%m-%d")
                    df = ticker.history(start=start_dt, interval=interval, auto_adjust=False)
                else:
                    df = ticker.history(period=period, interval=interval, auto_adjust=False)
                df = _normalize_ohlc(df)
                if not df.empty:
                    merged = _merge_ohlc(cached, df)
                    _cache_set(symbol, merged)
                    return _filter_by_period(merged, period)
            except Exception as e:
                yahoo_error = e
                if attempt < 1:
                    time.sleep(1.5)

    # Daily Stooq fallback can often bypass temporary Yahoo rate limits.
    try:
        stooq_df = _load_stooq_daily(symbol, period)
        if not stooq_df.empty:
            merged = _merge_ohlc(cached, stooq_df)
            _cache_set(symbol, merged)
            if yahoo_error is not None:
                st.info(
                    f"📡 Yahoo Finance is rate limited for {symbol}. "
                    f"Using Stooq daily data fallback."
                )
            return _filter_by_period(merged, period)
    except Exception:
        pass

    # If remote pulls fail but app has cached data, return cache.
    if not cached.empty:
        st.info(f"📁 Using in-app cached history for {symbol} (live pull unavailable).")
        return _filter_by_period(cached, period)

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



from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
import pandas as pd

import streamlit as st

# Ensure local package imports work in environments that don't auto-add ./src to PYTHONPATH.
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec for {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _import_dashboard_symbols():
    try:
        from demark_dashboard.charts import build_figure as _build_figure
        from demark_dashboard.config import (
            COMMODITIES as _COMMODITIES,
            EQUITIES as _EQUITIES,
            FX as _FX,
            INTERVAL_OPTIONS as _INTERVAL_OPTIONS,
            PERIOD_OPTIONS as _PERIOD_OPTIONS,
        )
        from demark_dashboard.data import load_ohlc as _load_ohlc
        from demark_dashboard.indicators import apply_demark as _apply_demark
        from demark_dashboard.insights import build_insight_text as _build_insight_text
        return (
            _build_figure,
            _COMMODITIES,
            _EQUITIES,
            _FX,
            _INTERVAL_OPTIONS,
            _PERIOD_OPTIONS,
            _load_ohlc,
            _apply_demark,
            _build_insight_text,
        )
    except Exception as import_error:
        package_dir_candidates = [ROOT_DIR / "src" / "demark_dashboard", ROOT_DIR / "demark_dashboard"]
        package_dir = next((p for p in package_dir_candidates if p.exists()), None)
        if package_dir is None:
            raise ModuleNotFoundError(
                "Could not find 'demark_dashboard'. Ensure repository includes "
                "src/demark_dashboard with charts.py, config.py, data.py, indicators.py, insights.py"
            ) from import_error

        charts_mod = _load_module("demark_dashboard_charts", package_dir / "charts.py")
        config_mod = _load_module("demark_dashboard_config", package_dir / "config.py")
        data_mod = _load_module("demark_dashboard_data", package_dir / "data.py")
        indicators_mod = _load_module("demark_dashboard_indicators", package_dir / "indicators.py")
        insights_mod = _load_module("demark_dashboard_insights", package_dir / "insights.py")

        return (
            charts_mod.build_figure,
            config_mod.COMMODITIES,
            config_mod.EQUITIES,
            config_mod.FX,
            config_mod.INTERVAL_OPTIONS,
            config_mod.PERIOD_OPTIONS,
            data_mod.load_ohlc,
            indicators_mod.apply_demark,
            insights_mod.build_insight_text,
        )


(
    build_figure,
    COMMODITIES,
    EQUITIES,
    FX,
    INTERVAL_OPTIONS,
    PERIOD_OPTIONS,
    load_ohlc,
    apply_demark,
    build_insight_text,
) = _import_dashboard_symbols()


st.set_page_config(page_title="DeMark Market Dashboard", layout="wide")


# ============================================================================
# PASSWORD PROTECTION
# ============================================================================
def _check_password():
    """Verify password via session state."""
    if st.session_state.get("password_correct"):
        return True
    return False


def _password_entered():
    """Callback for when user enters password."""
    if st.session_state["password_input"] == "SHPPF":
        st.session_state["password_correct"] = True
        del st.session_state["password_input"]
    else:
        st.session_state["password_correct"] = False


if not _check_password():
    st.title("🔒 DeMark Market Dashboard - Access Restricted")
    st.markdown("### Please enter the password to access this dashboard.")
    
    st.text_input(
        "Password:",
        type="password",
        on_change=_password_entered,
        key="password_input",
        placeholder="Enter password",
    )
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ Incorrect password. Please try again.")
    
    st.stop()


# ============================================================================
# END PASSWORD PROTECTION
# ============================================================================

st.title("📊 DeMark Market Dashboard")
st.caption(
    "**TD Sequential by Jason Perl** — Daily OHLC market structure monitor. "
    "Setup counts (1-9), countdown counts (1-13), perfection flags, deferred states, TDST support/resistance, and exhaust detection."
)

with st.sidebar:
    st.header("⚙️ Configuration")
    st.caption("Symbol: SPY")
    selected = ["SPY"]
    period = st.selectbox("Period", PERIOD_OPTIONS, index=1)
    interval = "1d"
    st.caption("Data interval: Daily OHLC only (1d)")

    st.divider()

if not selected:
    st.info("👈 Select at least one symbol in the sidebar.")
    st.stop()

# Display charts and signals
rows = []
for symbol in selected:
    data = load_ohlc(symbol=symbol, period=period, interval=interval)
    if data.empty:
        st.warning(f"⚠️ No data for {symbol}.")
        continue

    demark_df_daily = apply_demark(data)
    latest = demark_df_daily.iloc[-1]

    weekly = (
        data.resample("W-FRI")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna()
    )
    demark_df_weekly = apply_demark(weekly) if not weekly.empty else pd.DataFrame()

    rows.append(
        {
            "Symbol": symbol,
            "Close": f"{float(latest['Close']):,.2f}",
            "Buy Setup": int(latest["buy_setup"]),
            "Sell Setup": int(latest["sell_setup"]),
            "Buy CD": int(latest["buy_countdown"]),
            "Sell CD": int(latest["sell_countdown"]),
            "Buy Perfect": "✓" if latest.get("buy_perfected") else "",
            "Sell Perfect": "✓" if latest.get("sell_perfected") else "",
            "Buy Deferred": "⊕" if latest.get("deferred_buy") else "",
            "Sell Deferred": "⊕" if latest.get("deferred_sell") else "",
        }
    )

    st.subheader(f"{symbol}")
    fig_daily = build_figure(demark_df_daily, symbol, timeframe_label="Daily")
    st.plotly_chart(fig_daily, use_container_width=True)

    st.subheader(f"{symbol} — Weekly")
    if demark_df_weekly.empty:
        st.info("Not enough data to build weekly chart.")
    else:
        fig_weekly = build_figure(demark_df_weekly, symbol, timeframe_label="Weekly")
        st.plotly_chart(fig_weekly, use_container_width=True)

    with st.expander(f"📋 Insights: {symbol}", expanded=True):
        st.markdown("#### Daily")
        st.markdown(build_insight_text(demark_df_daily, symbol))
        if not demark_df_weekly.empty:
            st.markdown("#### Weekly")
            st.markdown(build_insight_text(demark_df_weekly, f"{symbol} (Weekly)"))

# Summary table
if rows:
    st.divider()
    st.subheader("📊 Cross-Market Signal Summary")
    st.dataframe(rows, use_container_width=True)

st.divider()
st.markdown(
    "*TD Sequential | Daily OHLC market structure monitor | Data from Yahoo Finance | Implementation: Jason Perl's DeMark Indicators*"
)

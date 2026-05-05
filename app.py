from __future__ import annotations

import sys
import importlib.util
from pathlib import Path

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

st.title("📊 DeMark Market Dashboard")
st.caption(
    "**TD Sequential by Jason Perl** — Interactive daily market monitor for equities, FX, and commodities. "
    "Based on 'DeMark Indicators' (Bloomberg Press, 2008). Shows setup counts, countdown counts, "
    "perfection flags, deferred signals, TDST levels, and risk management guidance."
)

with st.sidebar:
    st.header("⚙️ Configuration")
    st.caption("Symbol: SPY")
    selected = ["SPY"]
    period = st.selectbox("Period", PERIOD_OPTIONS, index=1)
    interval = "1d"
    st.caption("Data interval: Daily OHLC only (1d)")

    st.divider()
    st.header("📈 Legend")
    st.markdown("""
    - **B9** / **S9**: Buy/Sell Setup complete (9 bars)
    - **B13** / **S13**: Buy/Sell Countdown complete (13 bars) ← **SIGNAL**
    - **⊕**: Deferred signal (bar 13 conditions incomplete)
    - **↑** / **↓**: Setup perfected
    - **TDST**: Support/Resistance levels from setup extremes
    """)

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

    demark_df = apply_demark(data)
    latest = demark_df.iloc[-1]

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
    fig = build_figure(demark_df, symbol)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander(f"📋 Insights: {symbol}", expanded=True):
        st.markdown(build_insight_text(demark_df, symbol))

# Summary table
if rows:
    st.divider()
    st.subheader("📊 Cross-Market Signal Summary")
    st.dataframe(rows, use_container_width=True)

st.divider()
st.markdown("""
### 📚 Methodology Reference
This dashboard implements **TD Sequential** from Jason Perl's *DeMark Indicators* (Bloomberg Press, 2008), 
which describes exhaustion-point identification through:
- **Setup Phase**: 9-bar momentum sequences with 4-bar lookback
- **Countdown Phase**: 13-bar trend sequences with 2-bar lookback
- **TDST Levels**: Dynamic support/resistance from setup extremes
- **Risk Management**: True-range-based stop placement
- **Perfection & Deferral**: Qualifier rules for signal validity

**Limitations**: DeMark implementations vary across platforms. This dashboard provides a transparent, editable baseline.
Validate signals against your reference charts and adjust rules as needed.

---
*Dashboard by Sean | Based on Jason Perl's DeMark Indicators methodology | Data from Yahoo Finance*
""")

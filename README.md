# DeMark Market Dashboard

**Interactive TD Sequential analysis across equities, FX, and commodities** — Based on Jason Perl's *DeMark Indicators* (Bloomberg Press, 2008).

## Features

### 📊 Core Indicators
- **TD Setup** (1-9): Momentum sequences identifying range extremes
- **TD Countdown** (1-13): Trend sequences identifying exhaustion points
- **TDST Levels**: Dynamic support/resistance from setup extremes
- **Perfection Flags** (↑↓): Setup quality indicators
- **Deferred Signals** (⊕): Incomplete bar-13 conditions
- **Risk Management**: True-range-based stop placement

### 🎯 Visual Markers
- **B9/S9**: Buy/Sell Setup complete
- **B13/S13**: Buy/Sell Countdown complete ← **SIGNAL**
- **↑**: Buy Setup perfected
- **↓**: Sell Setup perfected
- **⊕**: Signal deferred (conditions incomplete)
- **TDST**: Support/resistance lines

### 🌍 Multi-Asset Support
- **Equities**: SPY, QQQ, DIA, IWM, AAPL, MSFT, NVDA, etc.
- **FX**: EURUSD, GBPUSD, JPYUSD, AUDUSD, USDCAD, USDCHF
- **Commodities**: Gold, Silver, Crude Oil, Natural Gas, Corn, Soybeans

### 🔄 Timeframes
- Daily (1d)
- Hourly (1h)
- 30-minute (30m)
- Customizable periods (6mo, 1y, 2y, 5y)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Locally

```bash
streamlit run app.py
```

Opens at: `http://localhost:8501`

### 3. Deploy to Cloud

See [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step Streamlit Cloud setup.

---

## Methodology

### TD Sequential (2-Phase)

**Phase 1: TD Setup** — Identifies consolidation and trend transitions
- 9 consecutive closes with specific 4-bar lookback relationship
- Perfection check: Bar 8-9 low/high more extreme than bars 6-7
- Completion signals: TDST support/resistance definition

**Phase 2: TD Countdown** — Identifies exhaustion points and reversals
- 13 consecutive closes with specific 2-bar lookback relationship
- Requires prior TD Setup completion (bar 9)
- Bar 13 completion conditions: Low ≤ bar-8 low AND close ≤ low-2
- Deferred (+): Conditions incomplete; signal awaiting confirmation
- Completion signals: Potential trend exhaustion

### TDST (TD Setup Trend)
- **Support**: Lowest low across 9-bar Buy Setup
- **Resistance**: Highest high across 9-bar Sell Setup
- **Usage**: Defines structural trend bias; used for stop placement and trend validation

### Risk Management
1. Identify bar with lowest/highest true range during countdown
2. Subtract/add true range from/to that bar's low/high
3. Position size adjusted to match required stop level

---

## Architecture

```
demark-dashboard/
├── app.py                          # Main Streamlit entrypoint
├── requirements.txt                # Python dependencies
├── setup.py                        # Package configuration
├── DEPLOYMENT.md                   # Cloud deployment guide
├── README.md                       # This file
├── .gitignore                      # Git ignore rules
├── .streamlit/
│   └── config.toml                 # Streamlit theme/settings
└── src/demark_dashboard/
    ├── __init__.py
    ├── config.py                   # Asset symbols and UI settings
    ├── data.py                     # Yahoo Finance fetcher + demo fallback
    ├── indicators.py               # Complete TD Sequential engine
    ├── charts.py                   # Plotly interactive visualizations
    └── insights.py                 # Signal interpretation & insights
```

---

## Key Implementation Notes

### TD Sequential Rules (Per Perl/DeMark)

**Price Flip** — Entry for setup phase
- Bearish: Close > Close[4 bars ago] → Close < Close[4 bars ago]
- Bullish: Close < Close[4 bars ago] → Close > Close[4 bars ago]

**Setup Completion** — 9 bars
- Buy: 9 consecutive closes < close[4 bars ago]
- Sell: 9 consecutive closes > close[4 bars ago]

**Countdown Initiation** — After setup bar 9
- Buy: Close ≤ low[2 bars ago]
- Sell: Close ≥ high[2 bars ago]

**Countdown Completion** — 13 bars (with conditions)
- Buy: Low ≤ bar-8 low AND Close ≤ low[2 bars ago]
- Sell: High ≥ bar-8 high AND Close ≥ high[2 bars ago]

### Limitations & Disclaimers

1. **Platform Variance**: Different platforms implement DeMark indicators with subtle differences. This dashboard is a transparent, editable baseline.
2. **Demo Data**: If Yahoo Finance is unreachable, the dashboard falls back to synthetic data. Live trading should use real market data.
3. **Signal Confirmation**: Countdown 13 signals are exhaustion indicators, not guaranteed reversals. Always use risk management.
4. **Perfection**: Setup perfection increases confidence but is not mandatory for countdown initiation.

---

## Examples: Reading Signals

### Buy Setup 9 + Perfection ✓
- **Meaning**: Range consolidation with downside bias likely forming
- **Action**: Monitor for countdown initiation (close ≤ low[2 bars ago])
- **Risk**: If TDST support breaks, trend may continue lower

### Buy Countdown 13 Complete
- **Meaning**: 13 consecutive closes below 2-bar lows + bar-13 low ≤ bar-8 low
- **Action**: Potential exhaustion of downtrend; aggressive: buy on close; conservative: wait for bullish flip
- **Stop**: One true range below lowest low across countdown
- **Target**: TDST resistance or prior setup high

### Deferred Signal (⊕)
- **Meaning**: Bar 13 has close ≤ low[2], but bar-13 low > bar-8 low
- **Action**: Wait; does not qualify as valid bar 13 yet
- **Risk**: Market may retrace to bar-8 low before completing

### TDST Break
- Close above TDST Sell Resistance (before completing Sell Setup 9): Uptrend likely continues
- Close below TDST Buy Support (before completing Buy Setup 9): Downtrend likely continues

---

## Troubleshooting

### SSL/TLS Errors
- **Cause**: Network or OpenSSL misconfiguration
- **Solution**: Check internet connection; if problem persists, demo data will display automatically
- **Workaround**: Run on a different network or VPN

### Data Gaps
- **Cause**: Yahoo Finance API rate limiting or temporary outage
- **Solution**: Refresh page; wait a few minutes; try a different symbol
- **Fallback**: Dashboard shows synthetic data with same signal structure for testing

### Performance Issues
- **Solution**: Reduce number of symbols or increase history period window
- **Note**: Charting large datasets may be slow; consider 1d interval + 1y period

---

## References

**Primary Source:**
- Perl, Jason. *DeMark Indicators*. Bloomberg Press, 2008.
  - Comprehensive coverage of TD Sequential, TD Combo, TD D-Wave, TD Lines, TD Oscillators, and more
  - Methodology: Exhaustion-point identification for market timing
  - Risk management: True-range-based stop placement

**Trademarks:**
All DeMark indicator names are protected trademarks (TD Sequential™, TD Countdown™, TDST™, etc.).

---

## Contributing

To customize rules or add new indicators:

1. Edit `src/demark_dashboard/indicators.py` for signal logic
2. Edit `src/demark_dashboard/charts.py` for visual presentation
3. Edit `src/demark_dashboard/insights.py` for interpretation text
4. Test locally: `streamlit run app.py`

---

## License & Disclaimer

**For Educational Use Only** — This dashboard is provided for learning and research purposes. Not financial advice. Always validate signals against your own reference charts and use proper risk management before trading.

**Copyright Notice:** DeMark Indicators™ are trademarks of Market Studies. This dashboard is an independent educational implementation.

---

*Dashboard created: May 2026 | Data source: Yahoo Finance | Framework: Streamlit + Plotly*


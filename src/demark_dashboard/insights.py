from __future__ import annotations

import pandas as pd


def build_insight_text(df: pd.DataFrame, symbol: str) -> str:
    """Generate TD Sequential market commentary in Jason Perl's voice."""
    if df.empty:
        return f"No data available for {symbol}."

    latest = df.iloc[-1]
    lines: list[str] = []

    def _last_nonzero(series: pd.Series) -> tuple[int, int]:
        """Return (value, bars_ago) for last nonzero entry."""
        s = pd.to_numeric(series, errors="coerce").fillna(0)
        nz_indices = s[s > 0].index
        if len(nz_indices) == 0:
            return 0, 0
        last_idx_pos = s.index.get_loc(nz_indices[-1])
        if isinstance(last_idx_pos, slice):
            last_idx_pos = last_idx_pos.stop - 1
        elif isinstance(last_idx_pos, (list, tuple)):
            last_idx_pos = last_idx_pos[-1]
        bars_ago = len(s) - 1 - last_idx_pos
        return int(s.iloc[-1 - bars_ago]), bars_ago

    close = float(latest["Close"])
    
    # Current setup state (latest row)
    buy_setup = int(latest.get("buy_setup", 0))
    sell_setup = int(latest.get("sell_setup", 0))
    buy_perfected = bool(latest.get("buy_perfected", False))
    sell_perfected = bool(latest.get("sell_perfected", False))
    
    # Last nonzero countdown values (most recent print, may be several bars ago)
    last_buy_cd, buy_cd_bars_ago = _last_nonzero(df["buy_countdown"])
    last_sell_cd, sell_cd_bars_ago = _last_nonzero(df["sell_countdown"])
    
    # Deferred/Recycled flags (from latest row)
    deferred_buy = bool(latest.get("deferred_buy", False))
    deferred_sell = bool(latest.get("deferred_sell", False))
    recycled_buy = bool(latest.get("recycled_buy", False))
    recycled_sell = bool(latest.get("recycled_sell", False))
    
    # TDST levels
    tdst_buy = latest.get("tdst_buy")
    tdst_sell = latest.get("tdst_sell")

    # Determine ACTIVE countdown direction (mutual exclusivity: only one is active)
    # Active = last nonzero > 0 OR deferred state is true
    has_buy_cd = (last_buy_cd > 0) or deferred_buy
    has_sell_cd = (last_sell_cd > 0) or deferred_sell

    # =========================================================================
    # SETUP PHASE STATUS
    # =========================================================================
    setup_text = ""
    if buy_setup > 0 and sell_setup == 0:
        if buy_setup == 9:
            setup_text = f"Buy setup complete (9). Downside exhaustion structure is formed."
        elif buy_setup >= 7:
            setup_text = f"Buy setup {buy_setup}/9 — downside momentum is mature and approaching exhaustion."
            if buy_perfected:
                setup_text += " Perfection confirms strong selling discipline."
        else:
            setup_text = f"Buy setup {buy_setup}/9 — downside sequence forming."
    elif sell_setup > 0 and buy_setup == 0:
        if sell_setup == 9:
            setup_text = f"Sell setup complete (9). Upside exhaustion structure is formed."
        elif sell_setup >= 7:
            setup_text = f"Sell setup {sell_setup}/9 — upside momentum is mature and approaching exhaustion."
            if sell_perfected:
                setup_text += " Perfection confirms strong buying discipline."
        else:
            setup_text = f"Sell setup {sell_setup}/9 — upside sequence forming."
    elif buy_setup > 0 and sell_setup > 0:
        setup_text = f"Conflicted structure: buy {buy_setup}/9 vs sell {sell_setup}/9."
    else:
        setup_text = "No setup in progress. Awaiting price flip to initiate next sequence."

    # =========================================================================
    # COUNTDOWN PHASE STATUS (ACTIVE DIRECTION ONLY)
    # =========================================================================
    countdown_text = ""
    
    if has_buy_cd and not has_sell_cd:
        # Buy countdown is active
        if deferred_buy:
            countdown_text = f"Buy countdown deferred (12+). Waiting for low to penetrate Close[8] reference."
        else:
            if last_buy_cd == 13:
                countdown_text = f"Buy countdown complete (13). Downside exhaustion is confirmed — market at critical reversal point."
            elif last_buy_cd >= 10:
                countdown_text = f"Buy countdown {last_buy_cd}/13 ({buy_cd_bars_ago} bars ago). Late exhaustion zone — downside pressure may reverse soon."
            elif last_buy_cd > 0:
                countdown_text = f"Buy countdown {last_buy_cd}/13 ({buy_cd_bars_ago} bars ago). Downside momentum continues."
            
            if recycled_buy and countdown_text:
                countdown_text += " [Recycled — timing extended]"
    
    elif has_sell_cd and not has_buy_cd:
        # Sell countdown is active
        if deferred_sell:
            countdown_text = f"Sell countdown deferred (12+). Waiting for high to penetrate Close[8] reference."
        else:
            if last_sell_cd == 13:
                countdown_text = f"Sell countdown complete (13). Upside exhaustion is confirmed — market at critical reversal point."
            elif last_sell_cd >= 10:
                countdown_text = f"Sell countdown {last_sell_cd}/13 ({sell_cd_bars_ago} bars ago). Late exhaustion zone — upside extension vulnerable to correction."
            elif last_sell_cd > 0:
                countdown_text = f"Sell countdown {last_sell_cd}/13 ({sell_cd_bars_ago} bars ago). Upside momentum continues."
            
            if recycled_sell and countdown_text:
                countdown_text += " [Recycled — timing extended]"
    
    else:
        # No active countdown
        countdown_text = "No active countdown. Transition phase — awaiting setup 9 to launch next exhaust sequence."

    # =========================================================================
    # TDST STRUCTURAL CONTEXT
    # =========================================================================
    tdst_text = ""
    if pd.notna(tdst_buy) and pd.notna(tdst_sell):
        tdst_buy_float = float(tdst_buy)
        tdst_sell_float = float(tdst_sell)
        
        if close > tdst_sell_float:
            tdst_text = (
                f"Price {close:,.2f} >> TDST Resistance {tdst_sell_float:,.2f} | "
                f"Structural strength confirmed. Bullish bias intact."
            )
        elif close < tdst_buy_float:
            tdst_text = (
                f"Price {close:,.2f} << TDST Support {tdst_buy_float:,.2f} | "
                f"Structural weakness confirmed. Bearish bias intact."
            )
        else:
            tdst_text = (
                f"Price {close:,.2f} between TDST Support {tdst_buy_float:,.2f} — Resistance {tdst_sell_float:,.2f} | "
                f"Transitional structure."
            )

    # =========================================================================
    # TREND STRENGTH ASSESSMENT
    # =========================================================================
    trend_strength = ""
    
    if has_buy_cd and buy_setup == 0:
        if last_buy_cd >= 10:
            trend_strength = "Strong downtrend exhaustion — reversal risk elevated."
        elif last_buy_cd >= 7:
            trend_strength = "Downtrend showing fatigue in late-stage countdown."
        else:
            trend_strength = "Downtrend momentum remains intact; countdown still early."
    elif has_sell_cd and sell_setup == 0:
        if last_sell_cd >= 10:
            trend_strength = "Strong uptrend exhaustion — pullback risk elevated."
        elif last_sell_cd >= 7:
            trend_strength = "Uptrend showing fatigue in late-stage countdown."
        else:
            trend_strength = "Uptrend momentum remains intact; countdown still early."
    elif buy_setup > 0 and not has_buy_cd:
        trend_strength = f"Downside structure forming ({buy_setup}/9). Awaiting countdown initiation."
    elif sell_setup > 0 and not has_sell_cd:
        trend_strength = f"Upside structure forming ({sell_setup}/9). Awaiting countdown initiation."
    elif buy_setup > 0 and sell_setup > 0:
        trend_strength = "Market in conflicted state — directional bias unclear."
    else:
        trend_strength = "Awaiting sequential structure."

    # =========================================================================
    # BUILD FINAL OUTPUT
    # =========================================================================
    lines.append(f"**{symbol}**")
    lines.append("")
    lines.append(f"**Setup:** {setup_text}")
    lines.append("")
    if countdown_text:
        lines.append(f"**Countdown:** {countdown_text}")
        lines.append("")
    lines.append(f"**Structure:** {tdst_text}")
    lines.append("")
    lines.append(f"**Trend:** {trend_strength}")

    return "\n".join(lines)

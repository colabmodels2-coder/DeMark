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
            setup_text = (
                f"Buy setup 9 complete. Nine consecutive bars where Close < Close[4]. "
                f"Downside momentum structure formed."
            )
            if buy_perfected:
                setup_text += " Perfected: Low[8-9] ≤ min(Low[6-7])."
        elif buy_setup >= 7:
            setup_text = (
                f"Buy setup {buy_setup}/9. Counting consecutive bars where Close < Close[4]. "
                f"Downside momentum maturing."
            )
            if buy_perfected:
                setup_text += " Perfected."
        else:
            setup_text = (
                f"Buy setup {buy_setup}/9. Counting consecutive bars where Close < Close[4]."
            )
    elif sell_setup > 0 and buy_setup == 0:
        if sell_setup == 9:
            setup_text = (
                f"Sell setup 9 complete. Nine consecutive bars where Close > Close[4]. "
                f"Upside momentum structure formed."
            )
            if sell_perfected:
                setup_text += " Perfected: High[8-9] ≥ max(High[6-7])."
        elif sell_setup >= 7:
            setup_text = (
                f"Sell setup {sell_setup}/9. Counting consecutive bars where Close > Close[4]. "
                f"Upside momentum maturing."
            )
            if sell_perfected:
                setup_text += " Perfected."
        else:
            setup_text = (
                f"Sell setup {sell_setup}/9. Counting consecutive bars where Close > Close[4]."
            )
    elif buy_setup > 0 and sell_setup > 0:
        setup_text = (
            f"Conflicted structure: buy setup {buy_setup}/9 vs sell setup {sell_setup}/9. "
            f"Setup counts interrupted; directional clarity needed."
        )
    else:
        setup_text = "No setup in progress. Awaiting price flip (Close crossing Close[4]) to initiate new sequence."

    # =========================================================================
    # COUNTDOWN PHASE STATUS (ACTIVE DIRECTION ONLY)
    # =========================================================================
    countdown_text = ""
    
    if has_buy_cd and not has_sell_cd:
        # Buy countdown is active (Close <= Low[2])
        if deferred_buy:
            countdown_text = (
                f"Buy countdown deferred (12+). "
                f"Bar 13 was reached but failed condition: Low[13] > Close[8]. "
                f"Awaiting next qualifying bar with Low ≤ Close[8]."
            )
        else:
            if last_buy_cd == 13:
                countdown_text = (
                    f"Buy countdown 13 COMPLETE. Both conditions satisfied: "
                    f"Low[13] ≤ Close[8] AND Close[13] ≤ Low[2 bars]. "
                    f"Downside exhaustion confirmed."
                )
            elif last_buy_cd >= 10:
                countdown_text = (
                    f"Buy countdown {last_buy_cd}/13 ({buy_cd_bars_ago} bars ago). "
                    f"Counting bars where Close ≤ Low[2 bars]. Late-stage exhaustion zone."
                )
            elif last_buy_cd > 0:
                countdown_text = (
                    f"Buy countdown {last_buy_cd}/13 ({buy_cd_bars_ago} bars ago). "
                    f"Counting bars where Close ≤ Low[2 bars]."
                )
            
            if recycled_buy and countdown_text:
                countdown_text += " [Recycled: new Setup 9 restarted count]"
    
    elif has_sell_cd and not has_buy_cd:
        # Sell countdown is active (Close >= High[2])
        if deferred_sell:
            countdown_text = (
                f"Sell countdown deferred (12+). "
                f"Bar 13 was reached but failed condition: High[13] < Close[8]. "
                f"Awaiting next qualifying bar with High ≥ Close[8]."
            )
        else:
            if last_sell_cd == 13:
                countdown_text = (
                    f"Sell countdown 13 COMPLETE. Both conditions satisfied: "
                    f"High[13] ≥ Close[8] AND Close[13] ≥ High[2 bars]. "
                    f"Upside exhaustion confirmed."
                )
            elif last_sell_cd >= 10:
                countdown_text = (
                    f"Sell countdown {last_sell_cd}/13 ({sell_cd_bars_ago} bars ago). "
                    f"Counting bars where Close ≥ High[2 bars]. Late-stage exhaustion zone."
                )
            elif last_sell_cd > 0:
                countdown_text = (
                    f"Sell countdown {last_sell_cd}/13 ({sell_cd_bars_ago} bars ago). "
                    f"Counting bars where Close ≥ High[2 bars]."
                )
            
            if recycled_sell and countdown_text:
                countdown_text += " [Recycled: new Setup 9 restarted count]"
    
    else:
        # No active countdown
        countdown_text = "No active countdown. Awaiting Setup 9 completion to initiate exhaust count."

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
        # Buy countdown active, setup complete
        if last_buy_cd >= 13:
            trend_strength = "Downside exhaustion confirmed. Bars counting where Close ≤ Low[2]. Reversal risk present."
        elif last_buy_cd >= 10:
            trend_strength = "Downside exhaustion in late stage. Bars counting where Close ≤ Low[2]. Reversal risk elevated."
        elif last_buy_cd >= 7:
            trend_strength = "Downside exhaustion mid-stage. Bars counting where Close ≤ Low[2]."
        else:
            trend_strength = "Downside exhaustion counting started. Bars counting where Close ≤ Low[2]."
    elif has_sell_cd and sell_setup == 0:
        # Sell countdown active, setup complete
        if last_sell_cd >= 13:
            trend_strength = "Upside exhaustion confirmed. Bars counting where Close ≥ High[2]. Reversal risk present."
        elif last_sell_cd >= 10:
            trend_strength = "Upside exhaustion in late stage. Bars counting where Close ≥ High[2]. Reversal risk elevated."
        elif last_sell_cd >= 7:
            trend_strength = "Upside exhaustion mid-stage. Bars counting where Close ≥ High[2]."
        else:
            trend_strength = "Upside exhaustion counting started. Bars counting where Close ≥ High[2]."
    elif buy_setup > 0 and not has_buy_cd:
        # Buy setup active but countdown not yet initiated
        if buy_setup == 9:
            trend_strength = "Buy setup 9 complete. Countdown will initiate when first qualifying bar appears (Close ≤ Low[2])."
        else:
            trend_strength = f"Buy setup {buy_setup}/9 forming. Awaiting setup 9 to activate exhaustion count."
    elif sell_setup > 0 and not has_sell_cd:
        # Sell setup active but countdown not yet initiated
        if sell_setup == 9:
            trend_strength = "Sell setup 9 complete. Countdown will initiate when first qualifying bar appears (Close ≥ High[2])."
        else:
            trend_strength = f"Sell setup {sell_setup}/9 forming. Awaiting setup 9 to activate exhaustion count."
    elif buy_setup > 0 and sell_setup > 0:
        trend_strength = "Conflicted structure. Both setups present — directional exhaustion bias unclear."
    else:
        trend_strength = "No setup or countdown active. Awaiting price flip to initiate exhaustion sequence."

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

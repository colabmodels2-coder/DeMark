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
    # A setup can be forming while an opposite-direction countdown is still active.
    # The countdown is only cancelled when the new setup COMPLETES to 9.
    # =========================================================================
    setup_lines = []

    if buy_setup > 0:
        if buy_setup == 9:
            s = (
                f"Buy setup 9 complete. Nine consecutive closes < Close[4]. "
                f"Downside momentum structure formed."
            )
            if buy_perfected:
                s += " Perfected: Low[8-9] ≤ min(Low[6-7])."
            if has_sell_cd:
                s += " ⚠️ This completion has cancelled the prior sell countdown."
        else:
            s = f"Buy setup {buy_setup}/9 — counting consecutive closes < Close[4]."
            if buy_setup >= 7:
                s += " Downside momentum maturing."
            if has_sell_cd:
                s += f" Note: if this reaches 9, it will cancel the active sell countdown."
        setup_lines.append(s)

    if sell_setup > 0:
        if sell_setup == 9:
            s = (
                f"Sell setup 9 complete. Nine consecutive closes > Close[4]. "
                f"Upside momentum structure formed."
            )
            if sell_perfected:
                s += " Perfected: High[8-9] ≥ max(High[6-7])."
            if has_buy_cd:
                s += " ⚠️ This completion has cancelled the prior buy countdown."
        else:
            s = f"Sell setup {sell_setup}/9 — counting consecutive closes > Close[4]."
            if sell_setup >= 7:
                s += " Upside momentum maturing."
            if has_buy_cd:
                s += f" Note: if this reaches 9, it will cancel the active buy countdown."
        setup_lines.append(s)

    if not setup_lines:
        setup_lines.append("No setup in progress. Awaiting price flip (Close crossing Close[4]) to initiate new sequence.")

    setup_text = " | ".join(setup_lines)

    # =========================================================================
    # COUNTDOWN PHASE STATUS
    # Only ONE direction can be active at a time (mutual exclusivity).
    # But a new SETUP can be forming in the opposite direction simultaneously —
    # that countdown only gets cancelled when the new setup COMPLETES to 9.
    # =========================================================================
    countdown_text = ""

    if has_buy_cd and not has_sell_cd:
        # Buy countdown is active
        if deferred_buy:
            countdown_text = (
                f"Buy countdown deferred (12+). "
                f"Bar 13 reached but Low[13] > Close[8] — condition not yet met. "
                f"Awaiting a bar where Low ≤ Close[8] and Close ≤ Low[2]."
            )
        else:
            if last_buy_cd == 13:
                countdown_text = (
                    f"Buy countdown 13 complete. Both conditions met: "
                    f"Low[13] ≤ Close[8] and Close[13] ≤ Low[2]. "
                    f"Downside exhaustion confirmed."
                )
            elif last_buy_cd >= 10:
                countdown_text = (
                    f"Buy countdown {last_buy_cd}/13 ({buy_cd_bars_ago} bars ago). "
                    f"Late stage — counting closes ≤ Low[2]. Exhaustion risk elevated."
                )
            elif last_buy_cd > 0:
                countdown_text = (
                    f"Buy countdown {last_buy_cd}/13 ({buy_cd_bars_ago} bars ago). "
                    f"Counting closes ≤ Low[2]. Sequence ongoing."
                )
        if recycled_buy and countdown_text:
            countdown_text += " [Recycled: same-direction Setup 9 restarted count from bar 1]"
        # Warn if opposite setup is forming and could cancel this
        if sell_setup > 0:
            countdown_text += f" Active sell setup {sell_setup}/9 — would cancel this countdown if it reaches 9."

    elif has_sell_cd and not has_buy_cd:
        # Sell countdown is active
        if deferred_sell:
            countdown_text = (
                f"Sell countdown deferred (12+). "
                f"Bar 13 reached but High[13] < Close[8] — condition not yet met. "
                f"Awaiting a bar where High ≥ Close[8] and Close ≥ High[2]."
            )
        else:
            if last_sell_cd == 13:
                countdown_text = (
                    f"Sell countdown 13 complete. Both conditions met: "
                    f"High[13] ≥ Close[8] and Close[13] ≥ High[2]. "
                    f"Upside exhaustion confirmed."
                )
            elif last_sell_cd >= 10:
                countdown_text = (
                    f"Sell countdown {last_sell_cd}/13 ({sell_cd_bars_ago} bars ago). "
                    f"Late stage — counting closes ≥ High[2]. Exhaustion risk elevated."
                )
            elif last_sell_cd > 0:
                countdown_text = (
                    f"Sell countdown {last_sell_cd}/13 ({sell_cd_bars_ago} bars ago). "
                    f"Counting closes ≥ High[2]. Sequence ongoing."
                )
        if recycled_sell and countdown_text:
            countdown_text += " [Recycled: same-direction Setup 9 restarted count from bar 1]"
        # Warn if opposite setup is forming and could cancel this
        if buy_setup > 0:
            countdown_text += f" Active buy setup {buy_setup}/9 — would cancel this countdown if it reaches 9."

    else:
        countdown_text = "No active countdown. Awaiting Setup 9 completion to initiate exhaustion count."

    # =========================================================================
    # TDST STRUCTURAL CONTEXT
    # =========================================================================
    tdst_text = ""
    if pd.notna(tdst_buy) and pd.notna(tdst_sell):
        tdst_buy_float = float(tdst_buy)
        tdst_sell_float = float(tdst_sell)
        if close > tdst_sell_float:
            tdst_text = (
                f"Price {close:,.2f} above TDST Resistance {tdst_sell_float:,.2f}. "
                f"Structural strength confirmed. Bullish bias intact."
            )
        elif close < tdst_buy_float:
            tdst_text = (
                f"Price {close:,.2f} below TDST Support {tdst_buy_float:,.2f}. "
                f"Structural weakness confirmed. Bearish bias intact."
            )
        else:
            tdst_text = (
                f"Price {close:,.2f} between TDST Support {tdst_buy_float:,.2f} and Resistance {tdst_sell_float:,.2f}. "
                f"Transitional structure."
            )
    elif pd.notna(tdst_buy):
        tdst_buy_float = float(tdst_buy)
        tdst_text = f"TDST Support {tdst_buy_float:,.2f}. Price {'above' if close > tdst_buy_float else 'below'} support."
    elif pd.notna(tdst_sell):
        tdst_sell_float = float(tdst_sell)
        tdst_text = f"TDST Resistance {tdst_sell_float:,.2f}. Price {'above' if close > tdst_sell_float else 'below'} resistance."

    # =========================================================================
    # TREND STRENGTH — combination of setup + countdown + TDST
    # =========================================================================
    trend_parts = []

    # Countdown + opposite setup forming is the key combined state
    if has_buy_cd and sell_setup > 0:
        trend_parts.append(
            f"Buy countdown active ({last_buy_cd}/13) while sell setup forming ({sell_setup}/9). "
            f"Market attempting to reverse direction — exhaustion sequence at risk of cancellation."
        )
    elif has_sell_cd and buy_setup > 0:
        trend_parts.append(
            f"Sell countdown active ({last_sell_cd}/13) while buy setup forming ({buy_setup}/9). "
            f"Market attempting to reverse direction — exhaustion sequence at risk of cancellation."
        )
    elif has_buy_cd:
        if last_buy_cd >= 10:
            trend_parts.append("Late-stage downside exhaustion. Reversal probability increasing.")
        elif last_buy_cd >= 7:
            trend_parts.append("Mid-stage downside exhaustion. Trend intact but tiring.")
        else:
            trend_parts.append("Early downside exhaustion count. Trend remains dominant.")
    elif has_sell_cd:
        if last_sell_cd >= 10:
            trend_parts.append("Late-stage upside exhaustion. Reversal probability increasing.")
        elif last_sell_cd >= 7:
            trend_parts.append("Mid-stage upside exhaustion. Trend intact but tiring.")
        else:
            trend_parts.append("Early upside exhaustion count. Trend remains dominant.")
    elif buy_setup > 0 and not has_buy_cd:
        if buy_setup == 9:
            trend_parts.append("Downside structure complete. Countdown initiation pending.")
        else:
            trend_parts.append(f"Downside structure building ({buy_setup}/9). No exhaustion count yet.")
    elif sell_setup > 0 and not has_sell_cd:
        if sell_setup == 9:
            trend_parts.append("Upside structure complete. Countdown initiation pending.")
        else:
            trend_parts.append(f"Upside structure building ({sell_setup}/9). No exhaustion count yet.")
    else:
        trend_parts.append("No active structure. Awaiting price flip for sequence initiation.")

    trend_strength = " ".join(trend_parts)

    # =========================================================================
    # BUILD FINAL OUTPUT
    # =========================================================================
    lines.append(f"**{symbol}**")
    lines.append("")
    lines.append(f"**Setup:** {setup_text}")
    lines.append("")
    lines.append(f"**Countdown:** {countdown_text}")
    lines.append("")
    if tdst_text:
        lines.append(f"**Structure:** {tdst_text}")
        lines.append("")
    lines.append(f"**Trend:** {trend_strength}")

    return "\n".join(lines)

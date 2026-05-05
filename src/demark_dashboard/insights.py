from __future__ import annotations

import pandas as pd


def build_insight_text(df: pd.DataFrame, symbol: str) -> str:
    """Generate TD Sequential market commentary in Jason Perl's voice."""
    if df.empty:
        return f"No data available for {symbol}."

    latest = df.iloc[-1]
    lines: list[str] = []

    def _last_nonzero(series: pd.Series) -> tuple[int, int]:
        """Return (value, bars_ago) for last nonzero entry. bars_ago=-1 means none found."""
        s = pd.to_numeric(series, errors="coerce").fillna(0)
        nz_indices = s[s > 0].index
        if len(nz_indices) == 0:
            return 0, -1
        last_label = nz_indices[-1]
        pos = s.index.get_loc(last_label)
        if isinstance(pos, slice):
            pos = pos.stop - 1
        elif isinstance(pos, (list, tuple)):
            pos = int(pos[-1])
        bars_ago = len(s) - 1 - int(pos)
        return int(s.iloc[int(pos)]), bars_ago

    n = len(df)
    close = float(latest["Close"])

    # Setup state on current bar
    buy_setup = int(latest.get("buy_setup", 0))
    sell_setup = int(latest.get("sell_setup", 0))
    buy_perfected = bool(latest.get("buy_perfected", False))
    sell_perfected = bool(latest.get("sell_perfected", False))

    # Countdown active state — read directly from indicators engine output
    # buy_countdown_active / sell_countdown_active are True on every bar the countdown is running
    # (including initiated-but-no-prints and deferred/awaiting states)
    has_buy_cd = bool(latest.get("buy_countdown_active", False))
    has_sell_cd = bool(latest.get("sell_countdown_active", False))

    # Deferred/awaiting state — True throughout entire awaiting period (not just the first deferral bar)
    buy_in_deferred = bool(latest.get("buy_deferred_active", False))
    sell_in_deferred = bool(latest.get("sell_deferred_active", False))

    # Deferred/Recycled event flags (from latest row — for commentary nuance)
    deferred_buy_today = bool(latest.get("deferred_buy", False))
    deferred_sell_today = bool(latest.get("deferred_sell", False))
    recycled_buy = bool(latest.get("recycled_buy", False))
    recycled_sell = bool(latest.get("recycled_sell", False))

    # Last printed countdown bar (may be several bars ago — countdowns are non-continuous)
    last_buy_cd, buy_cd_bars_ago = _last_nonzero(df["buy_countdown"])
    last_sell_cd, sell_cd_bars_ago = _last_nonzero(df["sell_countdown"])

    # TDST levels
    tdst_buy = latest.get("tdst_buy")
    tdst_sell = latest.get("tdst_sell")

    # =========================================================================
    # SETUP PHASE STATUS
    # A setup can be forming while an opposite-direction countdown is still active.
    # The countdown is only cancelled when the new setup COMPLETES to 9.
    # =========================================================================
    setup_lines = []

    if buy_setup > 0:
        if buy_setup == 9:
            s = "Buy setup 9 complete. Nine consecutive closes < Close[4]. Downside momentum structure formed."
            if buy_perfected:
                s += " Perfected: Low[8-9] ≤ min(Low[6-7])."
            if has_sell_cd:
                s += " ⚠️ This completion cancelled the prior sell countdown."
        else:
            s = f"Buy setup {buy_setup}/9 — consecutive closes < Close[4]."
            if buy_setup >= 7:
                s += " Downside momentum maturing."
            if has_sell_cd:
                s += f" Reaches 9, this will cancel the active sell countdown."
        setup_lines.append(s)

    if sell_setup > 0:
        if sell_setup == 9:
            s = "Sell setup 9 complete. Nine consecutive closes > Close[4]. Upside momentum structure formed."
            if sell_perfected:
                s += " Perfected: High[8-9] ≥ max(High[6-7])."
            if has_buy_cd:
                s += " ⚠️ This completion cancelled the prior buy countdown."
        else:
            s = f"Sell setup {sell_setup}/9 — consecutive closes > Close[4]."
            if sell_setup >= 7:
                s += " Upside momentum maturing."
            if has_buy_cd:
                s += f" Reaches 9, this will cancel the active buy countdown."
        setup_lines.append(s)

    if not setup_lines:
        setup_lines.append("No setup in progress. Awaiting price flip (Close crossing Close[4]) to begin.")

    setup_text = " | ".join(setup_lines)

    # =========================================================================
    # COUNTDOWN PHASE STATUS
    # Only ONE direction can be active at a time (mutual exclusivity).
    # A new setup in the OPPOSITE direction can form while countdown runs —
    # it cancels only when that new setup COMPLETES to 9.
    # =========================================================================
    countdown_text = ""

    if has_buy_cd and not has_sell_cd:
        if buy_in_deferred:
            # In awaiting state: bar 13 close condition was met but low[13] > close[8]
            if last_buy_cd > 0:
                countdown_text = (
                    f"Buy countdown deferred at bar {last_buy_cd}. "
                    f"Qualifying bar reached but Low[13] > Close[8]. "
                    f"Countdown continues — awaiting bar where Low ≤ Close[8] AND Close ≤ Low[2]."
                )
            else:
                countdown_text = "Buy countdown deferred (12+). Awaiting bar where Low ≤ Close[8] AND Close ≤ Low[2]."
        elif last_buy_cd == 13:
            countdown_text = (
                f"Buy countdown 13 complete. "
                f"Low[13] ≤ Close[8] AND Close[13] ≤ Low[2]. "
                f"Downside exhaustion confirmed."
            )
        elif last_buy_cd >= 10:
            countdown_text = (
                f"Buy countdown {last_buy_cd}/13 ({buy_cd_bars_ago} bars ago). "
                f"Counting closes ≤ Low[2]. Late-stage exhaustion zone."
            )
        elif last_buy_cd >= 1:
            countdown_text = (
                f"Buy countdown {last_buy_cd}/13 ({buy_cd_bars_ago} bars ago). "
                f"Counting closes ≤ Low[2]. Sequence ongoing."
            )
        else:
            # Countdown initiated (setup 9 complete) but no qualifying bar yet
            countdown_text = "Buy countdown initiated. Waiting for first qualifying bar (Close ≤ Low[2])."

        if recycled_buy:
            countdown_text += " [Recycled: a same-direction Setup extended to 18 before countdown completion, so the developing countdown was reset (R)]"
        if sell_setup > 0 and sell_setup < 9:
            countdown_text += f" Note: sell setup {sell_setup}/9 forming — if it reaches 9, this countdown is cancelled."

    elif has_sell_cd and not has_buy_cd:
        if sell_in_deferred:
            if last_sell_cd > 0:
                countdown_text = (
                    f"Sell countdown deferred at bar {last_sell_cd}. "
                    f"Qualifying bar reached but High[13] < Close[8]. "
                    f"Countdown continues — awaiting bar where High ≥ Close[8] AND Close ≥ High[2]."
                )
            else:
                countdown_text = "Sell countdown deferred (12+). Awaiting bar where High ≥ Close[8] AND Close ≥ High[2]."
        elif last_sell_cd == 13:
            countdown_text = (
                f"Sell countdown 13 complete. "
                f"High[13] ≥ Close[8] AND Close[13] ≥ High[2]. "
                f"Upside exhaustion confirmed."
            )
        elif last_sell_cd >= 10:
            countdown_text = (
                f"Sell countdown {last_sell_cd}/13 ({sell_cd_bars_ago} bars ago). "
                f"Counting closes ≥ High[2]. Late-stage exhaustion zone."
            )
        elif last_sell_cd >= 1:
            countdown_text = (
                f"Sell countdown {last_sell_cd}/13 ({sell_cd_bars_ago} bars ago). "
                f"Counting closes ≥ High[2]. Sequence ongoing."
            )
        else:
            countdown_text = "Sell countdown initiated. Waiting for first qualifying bar (Close ≥ High[2])."

        if recycled_sell:
            countdown_text += " [Recycled: a same-direction Setup extended to 18 before countdown completion, so the developing countdown was reset (R)]"
        if buy_setup > 0 and buy_setup < 9:
            countdown_text += f" Note: buy setup {buy_setup}/9 forming — if it reaches 9, this countdown is cancelled."

    else:
        countdown_text = "No active countdown. Awaiting Setup 9 completion to initiate exhaustion count."

    # =========================================================================
    # TDST STRUCTURAL CONTEXT
    # =========================================================================
    tdst_text = ""
    if pd.notna(tdst_buy) and pd.notna(tdst_sell):
        tdst_buy_float = float(tdst_buy)
        tdst_sell_float = float(tdst_sell)
        if close > tdst_buy_float:
            tdst_text = (
                f"Price {close:,.2f} above TDST Resistance {tdst_buy_float:,.2f}. "
                f"Structural strength confirmed. Bullish bias intact."
            )
        elif close < tdst_sell_float:
            tdst_text = (
                f"Price {close:,.2f} below TDST Support {tdst_sell_float:,.2f}. "
                f"Structural weakness confirmed. Bearish bias intact."
            )
        else:
            tdst_text = (
                f"Price {close:,.2f} between TDST Support {tdst_sell_float:,.2f} and Resistance {tdst_buy_float:,.2f}. "
                f"Transitional structure."
            )
    elif pd.notna(tdst_buy):
        tdst_buy_float = float(tdst_buy)
        tdst_text = f"TDST Resistance {tdst_buy_float:,.2f}. Price {'above' if close > tdst_buy_float else 'below'} resistance."
    elif pd.notna(tdst_sell):
        tdst_sell_float = float(tdst_sell)
        tdst_text = f"TDST Support {tdst_sell_float:,.2f}. Price {'above' if close > tdst_sell_float else 'below'} support."

    # =========================================================================
    # TREND STRENGTH — combination of setup + countdown + TDST
    # =========================================================================
    trend_parts = []

    if has_buy_cd and sell_setup > 0 and sell_setup < 9:
        trend_parts.append(
            f"Buy countdown running ({last_buy_cd}/13) while sell setup builds ({sell_setup}/9). "
            f"Market attempting to reverse — if sell setup reaches 9, exhaustion count is cancelled."
        )
    elif has_sell_cd and buy_setup > 0 and buy_setup < 9:
        trend_parts.append(
            f"Sell countdown running ({last_sell_cd}/13) while buy setup builds ({buy_setup}/9). "
            f"Market attempting to reverse — if buy setup reaches 9, exhaustion count is cancelled."
        )
    elif has_buy_cd:
        if buy_in_deferred:
            trend_parts.append("Downside exhaustion deferred — countdown in awaiting state for qualifying bar 13.")
        elif last_buy_cd == 13:
            trend_parts.append("Downside exhaustion complete (13). Reversal evidence present.")
        elif last_buy_cd >= 10:
            trend_parts.append("Late-stage downside exhaustion. Reversal probability increasing.")
        elif last_buy_cd >= 7:
            trend_parts.append("Mid-stage downside exhaustion. Trend intact but tiring.")
        elif last_buy_cd >= 1:
            trend_parts.append("Early downside exhaustion count. Trend remains dominant.")
        else:
            trend_parts.append("Downside countdown initiated. Trend dominant, no qualifying bars yet.")
    elif has_sell_cd:
        if sell_in_deferred:
            trend_parts.append("Upside exhaustion deferred — countdown in awaiting state for qualifying bar 13.")
        elif last_sell_cd == 13:
            trend_parts.append("Upside exhaustion complete (13). Reversal evidence present.")
        elif last_sell_cd >= 10:
            trend_parts.append("Late-stage upside exhaustion. Reversal probability increasing.")
        elif last_sell_cd >= 7:
            trend_parts.append("Mid-stage upside exhaustion. Trend intact but tiring.")
        elif last_sell_cd >= 1:
            trend_parts.append("Early upside exhaustion count. Trend remains dominant.")
        else:
            trend_parts.append("Upside countdown initiated. Trend dominant, no qualifying bars yet.")
    elif buy_setup > 0 and not has_buy_cd:
        if buy_setup == 9:
            trend_parts.append("Downside structure complete. Countdown initiated — awaiting first qualifying bar.")
        else:
            trend_parts.append(f"Downside structure building ({buy_setup}/9). No exhaustion count yet.")
    elif sell_setup > 0 and not has_sell_cd:
        if sell_setup == 9:
            trend_parts.append("Upside structure complete. Countdown initiated — awaiting first qualifying bar.")
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

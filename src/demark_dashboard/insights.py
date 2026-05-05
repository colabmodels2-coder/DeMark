from __future__ import annotations

import pandas as pd


def build_insight_text(df: pd.DataFrame, symbol: str) -> str:
    """Generate TD Sequential commentary in a DeMark desk-note style."""
    if df.empty:
        return f"No data available for {symbol}."

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    lines: list[str] = []

    def _last_nonzero_event(series: pd.Series) -> tuple[int, pd.Timestamp | None, int | None]:
        s = pd.to_numeric(series, errors="coerce").fillna(0)
        nz = s[s > 0]
        if nz.empty:
            return 0, None, None
        idx = nz.index[-1]
        val = int(nz.iloc[-1])
        pos = s.index.get_loc(idx)
        if isinstance(pos, slice):
            pos = pos.stop - 1
        elif isinstance(pos, (list, tuple)):
            pos = int(pos[-1])
        bars_ago = len(s) - 1 - int(pos)
        return val, idx, bars_ago

    def _fmt_idx(idx: pd.Timestamp | None) -> str:
        if idx is None:
            return "n/a"
        try:
            return idx.strftime("%Y-%m-%d")
        except Exception:
            return str(idx)

    close = float(latest["Close"])
    buy_setup = int(latest.get("buy_setup", 0))
    sell_setup = int(latest.get("sell_setup", 0))
    buy_countdown = int(latest.get("buy_countdown", 0))
    sell_countdown = int(latest.get("sell_countdown", 0))
    buy_perfected = bool(latest.get("buy_perfected", False))
    sell_perfected = bool(latest.get("sell_perfected", False))
    deferred_buy = bool(latest.get("deferred_buy", False))
    deferred_sell = bool(latest.get("deferred_sell", False))
    recycled_buy = bool(latest.get("recycled_buy", False))
    recycled_sell = bool(latest.get("recycled_sell", False))
    tdst_buy = latest.get("tdst_buy")
    tdst_sell = latest.get("tdst_sell")
    prev_close = float(prev["Close"]) if len(df) > 1 else close
    latest_buy_cd_print, latest_buy_cd_date, latest_buy_cd_bars_ago = _last_nonzero_event(df["buy_countdown"])
    latest_sell_cd_print, latest_sell_cd_date, latest_sell_cd_bars_ago = _last_nonzero_event(df["sell_countdown"])

    lines.append(f"**{symbol}** | Close: {close:,.2f}")
    lines.append("")
    lines.append("### TD Sequential Commentary")

    if close > prev_close:
        session_bias = "higher close"
    elif close < prev_close:
        session_bias = "lower close"
    else:
        session_bias = "unchanged close"
    lines.append(f"Current bar context: **{session_bias}** versus prior bar. Sequential focus remains on exhaustion, not trend-chasing.")

    lines.append("")
    lines.append("### Setup Phase (1 to 9)")

    if buy_setup > 0:
        status = "✓ Perfected" if buy_perfected else "○ Unperfected"
        lines.append(f"🔵 **Buy Setup**: {buy_setup}/9 {status}")
        if buy_setup >= 7:
            lines.append("   → Setup is mature. Downside pressure may be nearing exhaustion if Countdown can initiate.")
        if buy_setup == 9:
            lines.append("   → **Setup complete (9).** This defines an important reference for TDST and potential transition into Countdown.")
        if buy_perfected:
            lines.append("   → Perfection strengthens the quality of the Setup signal but is not, by itself, a trade trigger.")

    if sell_setup > 0:
        status = "✓ Perfected" if sell_perfected else "○ Unperfected"
        lines.append(f"🔴 **Sell Setup**: {sell_setup}/9 {status}")
        if sell_setup >= 7:
            lines.append("   → Setup is mature. Upside pressure may be nearing exhaustion if Countdown can initiate.")
        if sell_setup == 9:
            lines.append("   → **Setup complete (9).** This sets the structural context for TDST and potential Countdown progression.")
        if sell_perfected:
            lines.append("   → Perfection supports signal credibility but still requires disciplined confirmation.")

    if buy_setup == 0 and sell_setup == 0:
        lines.append("No active Setup count at present. Monitor for a qualifying Price Flip to begin a new sequence.")

    lines.append("")
    lines.append("### Countdown Phase (1 to 13)")
    lines.append("⚠️ **Mutual Exclusivity Rule**: Only ONE active countdown direction at a time.")
    lines.append("When an opposite-direction Setup 9 completes, it immediately cancels the prior countdown.")
    lines.append("")

    # Determine active countdown direction
    has_active_buy_cd = latest_buy_cd_print > 0 or deferred_buy
    has_active_sell_cd = latest_sell_cd_print > 0 or deferred_sell
    
    if has_active_buy_cd and has_active_sell_cd:
        # Should never happen with corrected rules, but log if it does
        lines.append("⚠️ **ALERT**: Both buy and sell countdowns detected. Review data integrity.")
    
    if has_active_buy_cd:
        lines.append(
            f"🟢 **BUY COUNTDOWN (ACTIVE)**: last qualified print **{latest_buy_cd_print}/13** on "
            f"**{_fmt_idx(latest_buy_cd_date)}** ({latest_buy_cd_bars_ago} bars ago)."
        )
        if latest_buy_cd_bars_ago and latest_buy_cd_bars_ago > 0:
            lines.append("   → Countdown prints can have gaps; no new print today does not automatically invalidate the sequence.")
        if deferred_buy:
            lines.append("🟢 **Buy Countdown**: 12+ (13+ Deferred)")
            lines.append("   → The sequence reached deferred status; condition for a qualified 13 is still outstanding.")
            lines.append("   → Market must trade below Close[8] reference while maintaining the countdown condition to complete.")
        else:
            if latest_buy_cd_print >= 10:
                lines.append("   → Late-stage Countdown. Market is in potential exhaustion territory; avoid chasing downside extension.")
                lines.append("   → Risk of correction or consolidation rise significantly in bars 10-13 range.")
            if latest_buy_cd_print == 13:
                lines.append("   → **Buy Countdown 13 COMPLETE.** Reversal risk rises; market has given a structural exhaustion signal.")
                if pd.notna(tdst_buy):
                    lines.append(f"   → Reference TDST support at {float(tdst_buy):,.2f} — important structural level for position sizing and invalidation.")
        
        # Check if opposite setup is developing (which would cancel this)
        if sell_setup > 0:
            lines.append(f"   → ⚠️ Note: Sell Setup {sell_setup}/9 is developing. If it completes to 9, it will cancel this Buy Countdown.")
    
    elif has_active_sell_cd:
        lines.append(
            f"🔴 **SELL COUNTDOWN (ACTIVE)**: last qualified print **{latest_sell_cd_print}/13** on "
            f"**{_fmt_idx(latest_sell_cd_date)}** ({latest_sell_cd_bars_ago} bars ago)."
        )
        if latest_sell_cd_bars_ago and latest_sell_cd_bars_ago > 0:
            lines.append("   → Countdown prints are non-consecutive by design; intervening bars simply fail qualification.")
        if deferred_sell:
            lines.append("🔴 **Sell Countdown**: 12+ (13+ Deferred)")
            lines.append("   → The sequence reached deferred status; qualified 13 conditions remain incomplete.")
            lines.append("   → Market must trade above Close[8] reference while maintaining the countdown condition to complete.")
        else:
            if latest_sell_cd_print >= 10:
                lines.append("   → Late-stage Countdown. Upside extension is vulnerable to exhaustion and mean reversion.")
                lines.append("   → Market structure enters critical risk zone; confirm before extending positions.")
            if latest_sell_cd_print == 13:
                lines.append("   → **Sell Countdown 13 COMPLETE.** Uptrend exhaustion signal has been generated.")
                if pd.notna(tdst_sell):
                    lines.append(f"   → Reference TDST resistance at {float(tdst_sell):,.2f} — key structural level for risk management.")
        
        # Check if opposite setup is developing (which would cancel this)
        if buy_setup > 0:
            lines.append(f"   → ⚠️ Note: Buy Setup {buy_setup}/9 is developing. If it completes to 9, it will cancel this Sell Countdown.")
    
    else:
        # No active countdown
        if buy_setup > 0 or sell_setup > 0:
            lines.append("No active Countdown at present. Waiting for Setup 9 completion to initiate next direction.")
            if buy_setup > 0:
                lines.append(f"   → Buy Setup {buy_setup}/9 is developing; once it completes to 9, Buy Countdown will begin.")
            if sell_setup > 0:
                lines.append(f"   → Sell Setup {sell_setup}/9 is developing; once it completes to 9, Sell Countdown will begin.")
        else:
            lines.append("No active Countdown sequence. Monitor for Price Flip and Setup initiation.")

    if recycled_buy:
        lines.append("🔁 **Buy Countdown Recycled (R)**")
        lines.append("   → A new Buy Setup 9 occurred while Buy Countdown was active (before 13 completion), forcing recycle.")
        lines.append("   → Recycle resets timing; new countdown begins from bar 1. Structural setup quality is reaffirmed, but exhaustion timeline extends.")

    if recycled_sell:
        lines.append("🔁 **Sell Countdown Recycled (R)**")
        lines.append("   → A new Sell Setup 9 occurred while Sell Countdown was active (before 13 completion), forcing recycle.")
        lines.append("   → Recycle resets timing; new countdown begins from bar 1. Patience and discipline are essential; reversal signals gain conviction when 13 ultimately completes.")

    lines.append("")
    lines.append("### TDST Structure (Support / Resistance)")

    if pd.notna(tdst_buy):
        tdst_buy_float = float(tdst_buy)
        if close < tdst_buy_float:
            lines.append(f"📉 Price **below** TDST Buy Support ({tdst_buy_float:,.2f})")
            lines.append("   → Structural tone remains vulnerable. Sequential buy signals generally require stronger confirmation when below TDST support.")
        elif close > tdst_buy_float * 1.005:
            lines.append(f"📈 Price **above** TDST Buy Support ({tdst_buy_float:,.2f})")
            lines.append("   → Structural footing is improved; downside exhaustion signals gain context when support is respected.")
        else:
            lines.append(f"⚖️ Price is testing TDST Buy Support ({tdst_buy_float:,.2f})")
            lines.append("   → Inflection zone: wait for confirmation rather than anticipatory positioning.")

    if pd.notna(tdst_sell):
        tdst_sell_float = float(tdst_sell)
        if close > tdst_sell_float:
            lines.append(f"📈 Price **above** TDST Sell Resistance ({tdst_sell_float:,.2f})")
            lines.append("   → Structural tone remains strong. Sequential sell signals should be treated with stricter confirmation standards.")
        elif close < tdst_sell_float * 0.995:
            lines.append(f"📉 Price **below** TDST Sell Resistance ({tdst_sell_float:,.2f})")
            lines.append("   → Rejection from resistance supports corrective or mean-reversion scenarios.")
        else:
            lines.append(f"⚖️ Price is testing TDST Sell Resistance ({tdst_sell_float:,.2f})")
            lines.append("   → Critical decision area: confirmation through subsequent closes is preferred.")

    lines.append("")
    lines.append("### Process Notes (Per Sequential Discipline)")
    lines.append("1. **One direction at a time**: Opposite-direction Setup 9 immediately cancels prior countdown. Track which direction is active.")
    lines.append("2. **Setup 9 as context**: Marks structural maturity and initiates Countdown sequence. Not a reversal trigger by itself.")
    lines.append("3. **Countdown 13 as exhaustion**: Represents terminal depletion; treat as evidence, then demand price confirmation before action.")
    lines.append("4. **Bar-8 reference is critical**: Countdown 13 must occur with Low[13] ≤ Close[8] (not Low[8]). This ensures signal integrity.")
    lines.append("5. **Deferred (13+) states**: When 13 fails the Close[8] check, countdown pauses at bar 12 with '+' marker pending condition completion.")
    lines.append("6. **Recycle (R)**: New same-direction Setup 9 during active countdown extends timing; different from direction switch (mutual exclusivity).")
    lines.append("7. **TDST structure**: Use support/resistance zones to validate whether sequential signals align with structural tone.")
    lines.append("8. **Size and risk**: Calibrate to volatility and TDST invalidation levels. Countdown timing alone does not justify leveraged positions.")

    return "\n".join(lines)

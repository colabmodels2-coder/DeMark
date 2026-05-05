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

    if latest_buy_cd_print > 0:
        lines.append(
            f"🟢 **Buy Countdown Sequence**: last qualified print **{latest_buy_cd_print}/13** on "
            f"**{_fmt_idx(latest_buy_cd_date)}** ({latest_buy_cd_bars_ago} bars ago)."
        )
        if latest_buy_cd_bars_ago and latest_buy_cd_bars_ago > 0:
            lines.append("   → Countdown prints can have gaps; no new print today does not automatically invalidate the sequence.")
        if deferred_buy:
            lines.append("🟢 **Buy Countdown**: 12+ (13+ Deferred)")
            lines.append("   → The sequence reached deferred status; condition for a qualified 13 is still outstanding.")
        else:
            if latest_buy_cd_print >= 10:
                lines.append("   → Late-stage Countdown. Market is in potential exhaustion territory; avoid chasing directional extension.")
            if latest_buy_cd_print == 13:
                lines.append("   → **Buy Countdown 13 complete.** Reversal risk rises, especially if price action stabilizes above downside extremes.")
                if pd.notna(tdst_buy):
                    lines.append(f"   → Reference TDST support at {float(tdst_buy):,.2f} for structure and invalidation context.")

    if latest_sell_cd_print > 0:
        lines.append(
            f"🔴 **Sell Countdown Sequence**: last qualified print **{latest_sell_cd_print}/13** on "
            f"**{_fmt_idx(latest_sell_cd_date)}** ({latest_sell_cd_bars_ago} bars ago)."
        )
        if latest_sell_cd_bars_ago and latest_sell_cd_bars_ago > 0:
            lines.append("   → Countdown prints can be non-consecutive; intervening bars may simply fail qualification.")
        if deferred_sell:
            lines.append("🔴 **Sell Countdown**: 12+ (13+ Deferred)")
            lines.append("   → The sequence reached deferred status; qualified 13 conditions remain incomplete.")
        else:
            if latest_sell_cd_print >= 10:
                lines.append("   → Late-stage Countdown. Upside extension is vulnerable to exhaustion and two-sided volatility.")
            if latest_sell_cd_print == 13:
                lines.append("   → **Sell Countdown 13 complete.** Uptrend persistence should now be questioned unless structure quickly reasserts.")
                if pd.notna(tdst_sell):
                    lines.append(f"   → Reference TDST resistance at {float(tdst_sell):,.2f} for structural confirmation.")

    if latest_buy_cd_print == 0 and latest_sell_cd_print == 0 and not deferred_buy and not deferred_sell:
        lines.append("No active Countdown sequence. Setup completion and follow-through criteria remain the priority.")

    if recycled_buy:
        lines.append("🔁 **Buy Countdown Recycled (R)**")
        lines.append("   → A new Buy Setup 9 emerged before a qualified 13, forcing a recycle. Signal timing is extended.")

    if recycled_sell:
        lines.append("🔁 **Sell Countdown Recycled (R)**")
        lines.append("   → A new Sell Setup 9 emerged before a qualified 13, forcing a recycle. Patience remains essential.")

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
    lines.append("1. Treat Setup 9 as context, not an automatic reversal command.")
    lines.append("2. Treat Countdown 13 as exhaustion evidence, then demand confirmation from price behavior.")
    lines.append("3. Use TDST to frame whether the market is structurally supportive or hostile to the signal direction.")
    lines.append("4. Respect deferred (13+) and recycle (R) outcomes as warnings that timing has extended.")
    lines.append("5. Size and risk should be calibrated to volatility and structural invalidation levels.")

    return "\n".join(lines)

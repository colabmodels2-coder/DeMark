from __future__ import annotations

import pandas as pd


def build_insight_text(df: pd.DataFrame, symbol: str) -> str:
    """Generate insights based on TD Sequential signals per Jason Perl's DeMark Indicators methodology."""
    if df.empty:
        return f"No data available for {symbol}."

    latest = df.iloc[-1]
    lines: list[str] = []

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

    lines.append(f"**{symbol}** | Close: {close:,.2f}")
    lines.append("")

    # Setup phase analysis
    if buy_setup > 0:
        status = "✓ Perfected" if buy_perfected else "○ Unperfected"
        lines.append(f"🔵 **Buy Setup**: {buy_setup}/9 {status}")
        if buy_setup >= 7:
            lines.append(f"   → Setup is advanced; watch for completion and potential exhaustion.")
        if buy_setup == 9:
            lines.append(f"   → **Setup complete.** Awaiting countdown phase or trend bias confirmation.")

    if sell_setup > 0:
        status = "✓ Perfected" if sell_perfected else "○ Unperfected"
        lines.append(f"🔴 **Sell Setup**: {sell_setup}/9 {status}")
        if sell_setup >= 7:
            lines.append(f"   → Setup is advanced; watch for completion and potential exhaustion.")
        if sell_setup == 9:
            lines.append(f"   → **Setup complete.** Awaiting countdown phase or trend bias confirmation.")

    # Countdown phase analysis
    if buy_countdown > 0:
        if deferred_buy:
            lines.append(f"🟢 **Buy Countdown**: 12+ (⊕ Deferred)")
            lines.append(f"   → Countdown bar 13 conditions not yet met. Watching for full completion...")
        else:
            lines.append(f"🟢 **Buy Countdown**: {buy_countdown}/13")
            if buy_countdown >= 10:
                lines.append(f"   → Advanced countdown; approaching critical exhaustion signal.")
            if buy_countdown == 13:
                lines.append(f"   → **🎯 CRITICAL: Buy Countdown 13 completed!**")
                lines.append(f"   → Potential trend exhaustion / reversal signal. Evaluate long entry conditions.")
                if pd.notna(tdst_buy):
                    lines.append(f"   → TDST Buy Support: {float(tdst_buy):,.2f}")

    if sell_countdown > 0:
        if deferred_sell:
            lines.append(f"🔴 **Sell Countdown**: 12+ (⊕ Deferred)")
            lines.append(f"   → Countdown bar 13 conditions not yet met. Watching for full completion...")
        else:
            lines.append(f"🔴 **Sell Countdown**: {sell_countdown}/13")
            if sell_countdown >= 10:
                lines.append(f"   → Advanced countdown; approaching critical exhaustion signal.")
            if sell_countdown == 13:
                lines.append(f"   → **🎯 CRITICAL: Sell Countdown 13 completed!**")
                lines.append(f"   → Potential trend exhaustion / reversal signal. Evaluate short entry conditions.")
                if pd.notna(tdst_sell):
                    lines.append(f"   → TDST Sell Resistance: {float(tdst_sell):,.2f}")

    if recycled_buy:
        lines.append("🔁 **Buy Countdown Recycled (R)**")
        lines.append("   → A new Buy Setup 9 occurred before Buy Countdown 13 completion; countdown restarted.")

    if recycled_sell:
        lines.append("🔁 **Sell Countdown Recycled (R)**")
        lines.append("   → A new Sell Setup 9 occurred before Sell Countdown 13 completion; countdown restarted.")

    # TDST level analysis
    if pd.notna(tdst_buy):
        tdst_buy_float = float(tdst_buy)
        if close < tdst_buy_float:
            lines.append(f"📉 Price **below** TDST Buy Support ({tdst_buy_float:,.2f})")
            lines.append(f"   → Indicates downside momentum and structural weakness.")
        elif close > tdst_buy_float * 1.005:
            lines.append(f"📈 Price **above** TDST Buy Support ({tdst_buy_float:,.2f})")
            lines.append(f"   → Suggests recovery potential or consolidation bias.")

    if pd.notna(tdst_sell):
        tdst_sell_float = float(tdst_sell)
        if close > tdst_sell_float:
            lines.append(f"📈 Price **above** TDST Sell Resistance ({tdst_sell_float:,.2f})")
            lines.append(f"   → Indicates upside momentum and structural strength.")
        elif close < tdst_sell_float * 0.995:
            lines.append(f"📉 Price **below** TDST Sell Resistance ({tdst_sell_float:,.2f})")
            lines.append(f"   → Suggests correction risk or consolidation bias.")

    # Default summary if no active signals
    if buy_setup == 0 and sell_setup == 0 and buy_countdown == 0 and sell_countdown == 0:
        lines.append("⏳ No active TD Sequential signals currently.")
        lines.append("   Awaiting price flip to initiate new setup or countdown phase.")

    # Risk management reminder
    lines.append("")
    lines.append("📋 **Risk Management:**")
    lines.append("   • Always use TDST levels to define trend bias and risk zones.")
    lines.append("   • Calculate stop-loss from true range of lowest low during countdown.")
    lines.append("   • Deferred signals (⊕) indicate bar 13 conditions incomplete—wait for full completion.")
    lines.append("   • Perfected setups (✓) increase probability of valid reversals.")
    lines.append("   • Based on Jason Perl's DeMark Indicators methodology.")

    return "\n".join(lines)

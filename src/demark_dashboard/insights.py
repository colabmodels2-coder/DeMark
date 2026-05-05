from __future__ import annotations

import pandas as pd


def build_insight_text(df: pd.DataFrame, symbol: str) -> str:
    """Generate TD Sequential market commentary in Jason Perl's voice."""
    if df.empty:
        return f"No data available for {symbol}."

    latest = df.iloc[-1]
    lines: list[str] = []

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

    # Determine which direction is currently ACTIVE (only one can be)
    has_buy_cd = (buy_countdown > 0) or deferred_buy
    has_sell_cd = (sell_countdown > 0) or deferred_sell

    # Setup commentary with trend context
    setup_text = ""
    if buy_setup > 0 and sell_setup == 0:
        if buy_setup >= 7:
            setup_text = f"Downside momentum is maturing ({buy_setup}/9 buy setup)"
            if buy_perfected:
                setup_text += "; perfection confirms strong selling discipline."
        else:
            setup_text = f"Early downside sequence ({buy_setup}/9)"
    elif sell_setup > 0 and buy_setup == 0:
        if sell_setup >= 7:
            setup_text = f"Upside momentum is maturing ({sell_setup}/9 sell setup)"
            if sell_perfected:
                setup_text += "; perfection confirms strong buying discipline."
        else:
            setup_text = f"Early upside sequence ({sell_setup}/9)"
    elif buy_setup > 0 and sell_setup > 0:
        setup_text = f"Conflicted structure: buy setup {buy_setup}/9 vs sell setup {sell_setup}/9"
    else:
        setup_text = "No active setup; awaiting price flip for sequence initiation."

    # Countdown commentary (only show ACTIVE direction)
    countdown_text = ""
    if has_buy_cd and not has_sell_cd:
        if deferred_buy:
            countdown_text = f"Buy countdown in deferred state (12+). Low must penetrate Close[8] to complete."
        else:
            if buy_countdown == 13:
                countdown_text = f"Buy countdown complete (13): downside exhaustion signal. Market is at critical inflection."
            elif buy_countdown >= 10:
                countdown_text = f"Buy countdown {buy_countdown}/13: late-stage exhaustion zone. Reversal risk is elevated."
            else:
                countdown_text = f"Buy countdown {buy_countdown}/13: downside momentum persisting."
            if recycled_buy:
                countdown_text += " [Recycled]"
    elif has_sell_cd and not has_buy_cd:
        if deferred_sell:
            countdown_text = f"Sell countdown in deferred state (12+). High must penetrate Close[8] to complete."
        else:
            if sell_countdown == 13:
                countdown_text = f"Sell countdown complete (13): upside exhaustion signal. Market is at critical inflection."
            elif sell_countdown >= 10:
                countdown_text = f"Sell countdown {sell_countdown}/13: late-stage exhaustion zone. Consolidation or reversal risk is elevated."
            else:
                countdown_text = f"Sell countdown {sell_countdown}/13: upside momentum persisting."
            if recycled_sell:
                countdown_text += " [Recycled]"
    elif not has_buy_cd and not has_sell_cd:
        countdown_text = "No active countdown. Waiting for setup 9 to initiate next sequence."
    # Note: has_buy_cd and has_sell_cd cannot both be true simultaneously (mutual exclusivity rule)

    # TDST context
    tdst_text = ""
    if pd.notna(tdst_buy) and pd.notna(tdst_sell):
        tdst_buy_float = float(tdst_buy)
        tdst_sell_float = float(tdst_sell)
        if close > tdst_sell_float:
            tdst_text = "Price is above both TDST levels; structural strength is present."
        elif close < tdst_buy_float:
            tdst_text = "Price is below both TDST levels; structural weakness is present."
        else:
            tdst_text = "Price is between TDST levels; structure is transitional."

    # Build final output
    lines.append(f"**{symbol}** — {setup_text}")
    lines.append("")
    if countdown_text:
        lines.append(countdown_text)
        lines.append("")
    if tdst_text:
        lines.append(tdst_text)

    return "\n".join(lines)

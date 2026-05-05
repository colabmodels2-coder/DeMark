from __future__ import annotations

import pandas as pd


def build_insight_text(df: pd.DataFrame, symbol: str) -> str:
    """Generate TD Sequential market commentary in Jason Perl's voice."""
    if df.empty:
        return f"No data available for {symbol}."

    latest = df.iloc[-1]
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
    latest_buy_cd_print, latest_buy_cd_date, latest_buy_cd_bars_ago = _last_nonzero_event(df["buy_countdown"])
    latest_sell_cd_print, latest_sell_cd_date, latest_sell_cd_bars_ago = _last_nonzero_event(df["sell_countdown"])

    # Build concise market commentary
    commentary_parts = []
    
    # Setup status
    if buy_setup == 9:
        commentary_parts.append("buy setup complete (9)")
    elif buy_setup > 0:
        perf = "perfected" if buy_perfected else f"{buy_setup}/9"
        commentary_parts.append(f"buy setup {perf}")
    
    if sell_setup == 9:
        commentary_parts.append("sell setup complete (9)")
    elif sell_setup > 0:
        perf = "perfected" if sell_perfected else f"{sell_setup}/9"
        commentary_parts.append(f"sell setup {perf}")
    
    # Countdown status
    has_buy_cd = latest_buy_cd_print > 0 or deferred_buy
    has_sell_cd = latest_sell_cd_print > 0 or deferred_sell
    
    if has_buy_cd:
        if deferred_buy:
            commentary_parts.append("buy countdown deferred (12+)")
        else:
            if latest_buy_cd_print == 13:
                commentary_parts.append("buy countdown complete (13)")
            else:
                commentary_parts.append(f"buy countdown {latest_buy_cd_print}/13")
            if recycled_buy:
                commentary_parts.append("buy recycled (R)")
    
    if has_sell_cd:
        if deferred_sell:
            commentary_parts.append("sell countdown deferred (12+)")
        else:
            if latest_sell_cd_print == 13:
                commentary_parts.append("sell countdown complete (13)")
            else:
                commentary_parts.append(f"sell countdown {latest_sell_cd_print}/13")
            if recycled_sell:
                commentary_parts.append("sell recycled (R)")
    
    # TDST positioning
    tdst_context = ""
    if pd.notna(tdst_buy) and pd.notna(tdst_sell):
        tdst_buy_float = float(tdst_buy)
        tdst_sell_float = float(tdst_sell)
        if close > tdst_sell_float:
            tdst_context = "price above both TDST levels"
        elif close < tdst_buy_float:
            tdst_context = "price below both TDST levels"
        else:
            tdst_context = "price between TDST levels"
    
    # Assemble final commentary
    if commentary_parts:
        lines.append(f"{symbol} shows: {', '.join(commentary_parts)}.")
        if tdst_context:
            lines.append(f"Structure: {tdst_context}.")
    elif tdst_context:
        lines.append(f"{symbol}: {tdst_context}.")
    else:
        lines.append(f"{symbol}: Awaiting setup or countdown initiation.")
    
    return "\n".join(lines)

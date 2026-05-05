from __future__ import annotations

import numpy as np
import pandas as pd


def _true_range(df: pd.DataFrame) -> pd.Series:
    """Calculate true range: max(high - low, abs(high - prev_close), abs(low - prev_close))"""
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr


def _price_flips(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    Bearish TD Price Flip: Close > Close[4 bars ago], then Close < Close[4 bars ago]
    Bullish TD Price Flip: Close < Close[4 bars ago], then Close > Close[4 bars ago]
    """
    shifted_4 = close.shift(4)
    prev_close = close.shift(1)
    prev_shifted_4 = close.shift(5)

    bullish_flip = (close > shifted_4) & (prev_close <= prev_shifted_4)
    bearish_flip = (close < shifted_4) & (prev_close >= prev_shifted_4)
    return bullish_flip.fillna(False), bearish_flip.fillna(False)


def _setup_counts(df: pd.DataFrame, bullish_flip: pd.Series, bearish_flip: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    TD Setup: 9 consecutive closes with correct relationship to close 4 bars earlier.
    Buy Setup: 9 closes < close[4 bars ago]
    Sell Setup: 9 closes > close[4 bars ago]
    Perfection: Low/High of bar 8-9 more extreme than bars 6-7
    """
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    buy_setup = pd.Series(0, index=df.index, dtype="int64")
    sell_setup = pd.Series(0, index=df.index, dtype="int64")
    buy_perfected = pd.Series(False, index=df.index)
    sell_perfected = pd.Series(False, index=df.index)

    buy_active = False
    sell_active = False
    bcount = 0
    scount = 0
    buy_start_idx = 0
    sell_start_idx = 0

    for i in range(len(df)):
        if i < 5:
            continue

        # Start buy setup on bearish flip
        if bearish_flip.iloc[i]:
            buy_active = True
            sell_active = False
            bcount = 1
            buy_start_idx = i
            buy_setup.iloc[i] = 1
            continue

        # Start sell setup on bullish flip
        if bullish_flip.iloc[i]:
            sell_active = True
            buy_active = False
            scount = 1
            sell_start_idx = i
            sell_setup.iloc[i] = 1
            continue

        # Continue or reset buy setup
        if buy_active:
            if close.iloc[i] < close.iloc[i - 4]:
                bcount += 1
                buy_setup.iloc[i] = bcount
                if bcount >= 9:
                    buy_active = False
            else:
                buy_active = False
                bcount = 0

        # Continue or reset sell setup
        if sell_active:
            if close.iloc[i] > close.iloc[i - 4]:
                scount += 1
                sell_setup.iloc[i] = scount
                if scount >= 9:
                    sell_active = False
            else:
                sell_active = False
                scount = 0

    # Check for perfection: low/high of bars 8-9 more extreme than bars 6-7
    for i in range(len(df)):
        if buy_setup.iloc[i] == 9:
            loc = i
            if loc >= 8:
                low_8_9 = min(low.iloc[loc - 1], low.iloc[loc])
                low_6_7 = min(low.iloc[loc - 3], low.iloc[loc - 2])
                if low_8_9 <= low_6_7:
                    buy_perfected.iloc[i] = True

        if sell_setup.iloc[i] == 9:
            loc = i
            if loc >= 8:
                high_8_9 = max(high.iloc[loc - 1], high.iloc[loc])
                high_6_7 = max(high.iloc[loc - 3], high.iloc[loc - 2])
                if high_8_9 >= high_6_7:
                    sell_perfected.iloc[i] = True

    return buy_setup, sell_setup, buy_perfected, sell_perfected


def _countdowns(
    df: pd.DataFrame,
    buy_setup: pd.Series,
    sell_setup: pd.Series,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    TD Countdown: 13 bars comparing close to low/high 2 bars earlier.
    Buy Countdown: 13 closes <= low[2 bars ago]
    Sell Countdown: 13 closes >= high[2 bars ago]
    MUTUAL EXCLUSIVITY: Only one active countdown direction at a time.
    When opposite-direction Setup 9 completes, it cancels the prior countdown.

    Deferred (13+): bar 13 condition (close <= low[2]) is met but low[13] > close[8].
      Per book, countdown remains ACTIVE in awaiting state until a bar satisfies BOTH:
        low <= close[8]  AND  close <= low[2]   (buy)
        high >= close[8] AND  close >= high[2]  (sell)

    Returns:
      buy_countdown, sell_countdown,
      deferred_buy (+), deferred_sell (+),
      recycled_buy (R), recycled_sell (R),
      buy_countdown_active, sell_countdown_active,   <- True on every bar countdown is running
      buy_deferred_active, sell_deferred_active      <- True on every bar in deferred/awaiting state
    """
    close = df["Close"]
    low = df["Low"]
    high = df["High"]

    buy_countdown = pd.Series(0, index=df.index, dtype="int64")
    sell_countdown = pd.Series(0, index=df.index, dtype="int64")
    deferred_buy = pd.Series(False, index=df.index)
    deferred_sell = pd.Series(False, index=df.index)
    recycled_buy = pd.Series(False, index=df.index)
    recycled_sell = pd.Series(False, index=df.index)
    buy_countdown_active = pd.Series(False, index=df.index)
    sell_countdown_active = pd.Series(False, index=df.index)
    buy_deferred_active = pd.Series(False, index=df.index)
    sell_deferred_active = pd.Series(False, index=df.index)

    active_buy = False
    active_sell = False
    bcount = 0
    scount = 0
    buy_cd8_close = np.nan   # Book rule: save CLOSE of bar 8, not Low
    sell_cd8_close = np.nan  # Book rule: save CLOSE of bar 8, not High
    buy_awaiting_13 = False  # True after deferred 13: countdown persists looking for qualifying bar 13
    sell_awaiting_13 = False

    for i in range(len(df)):
        if i < 2:
            continue

        # ------------------------------------------------------------------
        # MUTUAL EXCLUSIVITY: Opposite Setup 9 immediately cancels prior countdown
        # Checked BEFORE recycle so cancellation takes priority
        # ------------------------------------------------------------------
        if buy_setup.iloc[i] == 9 and active_sell:
            active_sell = False
            active_buy = True
            bcount = 0
            scount = 0
            buy_cd8_close = np.nan
            sell_cd8_close = np.nan
            buy_awaiting_13 = False
            sell_awaiting_13 = False

        if sell_setup.iloc[i] == 9 and active_buy:
            active_buy = False
            active_sell = True
            scount = 0
            bcount = 0
            sell_cd8_close = np.nan
            buy_cd8_close = np.nan
            buy_awaiting_13 = False
            sell_awaiting_13 = False

        # ------------------------------------------------------------------
        # RECYCLE: Same-direction Setup 9 before bar 13 completion resets count
        # This includes the awaiting/deferred state (bcount=12, awaiting_13=True)
        # ------------------------------------------------------------------
        if active_buy and 0 < bcount <= 12 and buy_setup.iloc[i] == 9:
            recycled_buy.iloc[i] = True
            bcount = 0
            buy_cd8_close = np.nan
            buy_awaiting_13 = False

        if active_sell and 0 < scount <= 12 and sell_setup.iloc[i] == 9:
            recycled_sell.iloc[i] = True
            scount = 0
            sell_cd8_close = np.nan
            sell_awaiting_13 = False

        # ------------------------------------------------------------------
        # INITIATE: Start countdown when Setup 9 completes and not already active
        # ------------------------------------------------------------------
        if buy_setup.iloc[i] == 9 and not active_buy:
            active_buy = True
            bcount = 0
            buy_cd8_close = np.nan

        if sell_setup.iloc[i] == 9 and not active_sell:
            active_sell = True
            scount = 0
            sell_cd8_close = np.nan

        # ------------------------------------------------------------------
        # BUY COUNTDOWN (only when active and sell not active)
        # ------------------------------------------------------------------
        if active_buy and not active_sell:
            if buy_awaiting_13:
                # Deferred/awaiting state: countdown reached bar 13 (close <= low[2]) but
                # low[13] > close[8] failed. Now wait for BOTH conditions simultaneously.
                if close.iloc[i] <= low.iloc[i - 2]:
                    if low.iloc[i] <= buy_cd8_close:
                        # Both conditions now satisfied: countdown 13 complete
                        buy_countdown.iloc[i] = 13
                        active_buy = False
                        buy_awaiting_13 = False
                    else:
                        # Close condition met but low still > close[8]: mark deferred again
                        deferred_buy.iloc[i] = True
                # else: close > low[2], neither condition met — continue waiting silently
            else:
                # Normal countdown: count bars where close <= low[2 bars ago]
                if close.iloc[i] <= low.iloc[i - 2]:
                    bcount += 1
                    buy_countdown.iloc[i] = bcount
                    if bcount == 8:
                        buy_cd8_close = close.iloc[i]  # Book rule: save Close[8]
                    elif bcount == 13:
                        if low.iloc[i] <= buy_cd8_close:
                            # Both conditions met: complete and stop countdown
                            active_buy = False
                        else:
                            # Close condition met but low[13] > close[8]: enter deferred state
                            buy_countdown.iloc[i] = 0  # Clear — not a completed 13
                            deferred_buy.iloc[i] = True
                            bcount = 12        # Hold at 12 (awaiting bar 13 completion)
                            buy_awaiting_13 = True  # Countdown continues in awaiting state
                # else: close > low[2] — countdown pauses on this bar (no action, preserves bcount)
                # Note: bcount == 0 pause is intentional — countdown waits for first qualifying bar

        # ------------------------------------------------------------------
        # SELL COUNTDOWN (only when active and buy not active)
        # ------------------------------------------------------------------
        if active_sell and not active_buy:
            if sell_awaiting_13:
                if close.iloc[i] >= high.iloc[i - 2]:
                    if high.iloc[i] >= sell_cd8_close:
                        # Both conditions satisfied: countdown 13 complete
                        sell_countdown.iloc[i] = 13
                        active_sell = False
                        sell_awaiting_13 = False
                    else:
                        deferred_sell.iloc[i] = True
            else:
                if close.iloc[i] >= high.iloc[i - 2]:
                    scount += 1
                    sell_countdown.iloc[i] = scount
                    if scount == 8:
                        sell_cd8_close = close.iloc[i]  # Book rule: save Close[8]
                    elif scount == 13:
                        if high.iloc[i] >= sell_cd8_close:
                            # Both conditions met: complete and stop countdown
                            active_sell = False
                        else:
                            sell_countdown.iloc[i] = 0  # Clear — not a completed 13
                            deferred_sell.iloc[i] = True
                            scount = 12
                            sell_awaiting_13 = True

        # ------------------------------------------------------------------
        # Record active/deferred state AFTER processing (end-of-bar state)
        # ------------------------------------------------------------------
        buy_countdown_active.iloc[i] = active_buy
        sell_countdown_active.iloc[i] = active_sell
        buy_deferred_active.iloc[i] = buy_awaiting_13
        sell_deferred_active.iloc[i] = sell_awaiting_13

    return (
        buy_countdown, sell_countdown,
        deferred_buy, deferred_sell,
        recycled_buy, recycled_sell,
        buy_countdown_active, sell_countdown_active,
        buy_deferred_active, sell_deferred_active,
    )


def _tdst_levels(df: pd.DataFrame, buy_setup: pd.Series, sell_setup: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    TDST (TD Setup Trend): Support/Resistance levels from completed setups.
    Buy Support: Low of 9-bar buy setup
    Sell Resistance: High of 9-bar sell setup
    """
    tdst_buy = pd.Series(np.nan, index=df.index)
    tdst_sell = pd.Series(np.nan, index=df.index)

    curr_buy = np.nan
    curr_sell = np.nan

    for i in range(len(df)):
        if buy_setup.iloc[i] == 9:
            window = df.iloc[max(0, i - 8) : i + 1]
            curr_buy = float(window["Low"].min())
        if sell_setup.iloc[i] == 9:
            window = df.iloc[max(0, i - 8) : i + 1]
            curr_sell = float(window["High"].max())

        tdst_buy.iloc[i] = curr_buy
        tdst_sell.iloc[i] = curr_sell

    return tdst_buy, tdst_sell


def apply_demark(df: pd.DataFrame) -> pd.DataFrame:
    """Apply complete TD Sequential indicators as per Jason Perl's DeMark Indicators."""
    out = df.copy()
    
    # Price flips
    bullish_flip, bearish_flip = _price_flips(out["Close"])
    out["bullish_flip"] = bullish_flip
    out["bearish_flip"] = bearish_flip

    # Setup counts
    buy_setup, sell_setup, buy_perfected, sell_perfected = _setup_counts(out, bullish_flip, bearish_flip)
    out["buy_setup"] = buy_setup
    out["sell_setup"] = sell_setup
    out["buy_perfected"] = buy_perfected
    out["sell_perfected"] = sell_perfected

    # Countdown counts
    (
        buy_countdown, sell_countdown,
        deferred_buy, deferred_sell,
        recycled_buy, recycled_sell,
        buy_countdown_active, sell_countdown_active,
        buy_deferred_active, sell_deferred_active,
    ) = _countdowns(out, buy_setup, sell_setup)
    out["buy_countdown"] = buy_countdown
    out["sell_countdown"] = sell_countdown
    out["deferred_buy"] = deferred_buy
    out["deferred_sell"] = deferred_sell
    out["recycled_buy"] = recycled_buy
    out["recycled_sell"] = recycled_sell
    out["buy_countdown_active"] = buy_countdown_active
    out["sell_countdown_active"] = sell_countdown_active
    out["buy_deferred_active"] = buy_deferred_active
    out["sell_deferred_active"] = sell_deferred_active

    # TDST levels
    tdst_buy, tdst_sell = _tdst_levels(out, buy_setup, sell_setup)
    out["tdst_buy"] = tdst_buy
    out["tdst_sell"] = tdst_sell

    # True range for risk calculations
    out["true_range"] = _true_range(out)

    return out

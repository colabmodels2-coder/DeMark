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


def _countdowns(df: pd.DataFrame, buy_setup: pd.Series, sell_setup: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    TD Countdown: 13 bars comparing close to low/high 2 bars earlier.
    Buy Countdown: 13 closes <= low[2 bars ago]
    Sell Countdown: 13 closes >= high[2 bars ago]
    Returns: buy_countdown, sell_countdown, deferred_buy (+), deferred_sell (+)
    """
    close = df["Close"]
    low = df["Low"]
    high = df["High"]

    buy_countdown = pd.Series(0, index=df.index, dtype="int64")
    sell_countdown = pd.Series(0, index=df.index, dtype="int64")
    deferred_buy = pd.Series(False, index=df.index)
    deferred_sell = pd.Series(False, index=df.index)

    active_buy = False
    active_sell = False
    bcount = 0
    scount = 0
    buy_cd8_low = np.inf
    sell_cd8_high = -np.inf

    for i in range(len(df)):
        if i < 2:
            continue

        # Initiate countdown on completed setup
        if buy_setup.iloc[i] == 9:
            active_buy = True
            bcount = 0
            buy_cd8_low = np.inf

        if sell_setup.iloc[i] == 9:
            active_sell = True
            scount = 0
            sell_cd8_high = -np.inf

        # Process buy countdown
        if active_buy:
            if close.iloc[i] <= low.iloc[i - 2]:
                bcount += 1
                if bcount <= 13:
                    buy_countdown.iloc[i] = bcount
                    if bcount == 8:
                        buy_cd8_low = low.iloc[i]
                    elif bcount == 13:
                        # Check completion conditions
                        if low.iloc[i] <= buy_cd8_low and close.iloc[i] <= low.iloc[i - 2]:
                            buy_countdown.iloc[i] = 13
                        else:
                            deferred_buy.iloc[i] = True
                            bcount = 12  # Stays at 12 with + marker
                            active_buy = False
                if bcount > 13:
                    active_buy = False
            else:
                if bcount > 0 and bcount < 13:
                    pass  # Countdown pauses but doesn't reset
                elif bcount == 0:
                    active_buy = False

        # Process sell countdown
        if active_sell:
            if close.iloc[i] >= high.iloc[i - 2]:
                scount += 1
                if scount <= 13:
                    sell_countdown.iloc[i] = scount
                    if scount == 8:
                        sell_cd8_high = high.iloc[i]
                    elif scount == 13:
                        # Check completion conditions
                        if high.iloc[i] >= sell_cd8_high and close.iloc[i] >= high.iloc[i - 2]:
                            sell_countdown.iloc[i] = 13
                        else:
                            deferred_sell.iloc[i] = True
                            scount = 12  # Stays at 12 with + marker
                            active_sell = False
                if scount > 13:
                    active_sell = False
            else:
                if scount > 0 and scount < 13:
                    pass  # Countdown pauses but doesn't reset
                elif scount == 0:
                    active_sell = False

    return buy_countdown, sell_countdown, deferred_buy, deferred_sell


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
    buy_countdown, sell_countdown, deferred_buy, deferred_sell = _countdowns(out, buy_setup, sell_setup)
    out["buy_countdown"] = buy_countdown
    out["sell_countdown"] = sell_countdown
    out["deferred_buy"] = deferred_buy
    out["deferred_sell"] = deferred_sell

    # TDST levels
    tdst_buy, tdst_sell = _tdst_levels(out, buy_setup, sell_setup)
    out["tdst_buy"] = tdst_buy
    out["tdst_sell"] = tdst_sell

    # True range for risk calculations
    out["true_range"] = _true_range(out)

    return out

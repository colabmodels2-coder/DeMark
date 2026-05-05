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


def _waves(df: pd.DataFrame) -> tuple:
    """
    TD D-Wave detection using closing prices as per Jason Perl's methodology.

    Returns discrete pivot events for waves 1-5 and A-B-C plus projection levels.
    Wave labels are emitted only on completion bars (no forward-filled markers).

    For downtrend sequences, mirrored rules are applied and pivots are written to
    the same columns so charting can display the complete structure.
    """
    close = df["Close"].astype(float).values
    n = len(close)

    wave_1 = np.full(n, np.nan)
    wave_2 = np.full(n, np.nan)
    wave_3 = np.full(n, np.nan)
    wave_4 = np.full(n, np.nan)
    wave_5 = np.full(n, np.nan)
    wave_a = np.full(n, np.nan)
    wave_b = np.full(n, np.nan)
    wave_c = np.full(n, np.nan)

    wave_2_proj = np.full(n, np.nan)
    wave_3_proj = np.full(n, np.nan)
    wave_4_proj = np.full(n, np.nan)
    wave_5_proj = np.full(n, np.nan)
    wave_c_proj = np.full(n, np.nan)
    wave_state = [""] * n

    trend = None  # None | "bull" | "bear"
    state = ""

    # Bull structure tracking
    bw1_low = np.nan
    bw1_high = np.nan
    bw2_low = np.nan
    bw2_high = np.nan
    bw3_low = np.nan
    bw3_high = np.nan
    bw4_low = np.nan
    bw4_high = np.nan
    bw5_low = np.nan
    bw5_high = np.nan
    bwa_low = np.nan
    bwa_high = np.nan
    bwb_high = np.nan
    bwc_low = np.nan
    bw3_start = -1
    bw5_start = -1
    bwa_start = -1
    bwb_start = -1

    # Bear structure tracking (mirrored rules)
    sw1_high = np.nan
    sw1_low = np.nan
    sw2_high = np.nan
    sw2_low = np.nan
    sw3_high = np.nan
    sw3_low = np.nan
    sw4_high = np.nan
    sw4_low = np.nan
    sw5_high = np.nan
    sw5_low = np.nan
    swa_high = np.nan
    swa_low = np.nan
    swb_low = np.nan
    swc_high = np.nan
    sw3_start = -1
    sw5_start = -1
    swa_start = -1
    swb_start = -1

    def reset_cycle() -> None:
        nonlocal trend, state
        trend = None
        state = ""

    def is_n_bar_low(i: int, lookback: int) -> bool:
        if i < lookback - 1:
            return False
        return close[i] < np.min(close[i - lookback + 1 : i])

    def is_n_bar_high(i: int, lookback: int) -> bool:
        if i < lookback - 1:
            return False
        return close[i] > np.max(close[i - lookback + 1 : i])

    for i in range(n):
        c = close[i]

        if trend is None:
            if is_n_bar_low(i, 21):
                trend = "bull"
                state = "W1_origin"
                bw1_low = c
                wave_state[i] = "W1_origin"
                continue
            if is_n_bar_high(i, 21):
                trend = "bear"
                state = "D1_origin"
                sw1_high = c
                wave_state[i] = "D1_origin"
                continue

        if trend == "bull":
            if state == "W1_origin":
                if c < bw1_low:
                    bw1_low = c
                if is_n_bar_high(i, 13):
                    bw1_high = c
                    state = "W1_wait_end"

            elif state == "W1_wait_end":
                if is_n_bar_low(i, 8):
                    wave_1[i] = bw1_high
                    bw2_low = c
                    state = "W2"

            elif state == "W2":
                if c < bw2_low:
                    bw2_low = c
                if is_n_bar_high(i, 21):
                    # Invalidation: W2 cannot close below W1 origin low.
                    if c < bw1_low:
                        reset_cycle()
                        continue
                    bw2_high = c
                    wave_2[i] = bw2_high
                    w1_range = bw1_high - bw1_low
                    wave_2_proj[i] = bw1_low + w1_range * 0.618
                    wave_3_proj[i] = bw1_low + w1_range * 1.618
                    bw3_low = c
                    bw3_start = i
                    state = "W3"

            elif state == "W3":
                if c < bw3_low:
                    bw3_low = c
                if is_n_bar_low(i, 13):
                    bw3_high = float(np.max(close[max(0, bw3_start) : i + 1]))
                    # Wave 3 peak must exceed Wave 1 peak.
                    if bw3_high <= bw1_high:
                        reset_cycle()
                        continue
                    wave_3[i] = bw3_high
                    bw4_low = c
                    bw4_high = np.nan
                    state = "W4"

            elif state == "W4":
                if c < bw4_low:
                    bw4_low = c
                # Invalidation: Wave 4 cannot close below Wave 2 low.
                if c < bw2_low:
                    reset_cycle()
                    continue
                if is_n_bar_high(i, 34):
                    bw4_high = c
                    wave_4[i] = bw4_high
                    w3_range = bw3_high - bw3_low
                    wave_4_proj[i] = bw3_high - (w3_range * 0.382)
                    wave_5_proj[i] = bw3_low + (w3_range * 1.618)
                    bw5_start = i
                    bw5_low = c
                    state = "W5"

            elif state == "W5":
                if c < bw5_low:
                    bw5_low = c
                if is_n_bar_low(i, 13):
                    bw5_high = float(np.max(close[max(0, bw5_start) : i + 1]))
                    # Wave 5 peak must exceed Wave 3 peak.
                    if bw5_high <= bw3_high:
                        reset_cycle()
                        continue
                    wave_5[i] = bw5_high
                    bwa_start = i
                    bwa_low = c
                    bwa_high = c
                    state = "WA"

            elif state == "WA":
                if c < bwa_low:
                    bwa_low = c
                if c > bwa_high:
                    bwa_high = c
                if is_n_bar_high(i, 8):
                    wave_a[i] = bwa_low
                    bwb_start = i
                    bwb_high = c
                    state = "WB"

            elif state == "WB":
                if c > bwb_high:
                    bwb_high = c
                # Enforce continuously during Wave B.
                if c > bw5_high:
                    reset_cycle()
                    continue
                if is_n_bar_low(i, 21):
                    wave_b[i] = bwb_high
                    wa_range = bwa_high - bwa_low
                    wave_c_proj[i] = bwa_high - (wa_range * 1.618)
                    bwc_low = c
                    state = "WC"

            elif state == "WC":
                if c < bwc_low:
                    bwc_low = c
                # Wave C completes when close <= Wave A low.
                if c <= bwa_low:
                    wave_c[i] = bwc_low
                    reset_cycle()
                    continue

            wave_state[i] = state

        elif trend == "bear":
            if state == "D1_origin":
                if c > sw1_high:
                    sw1_high = c
                if is_n_bar_low(i, 13):
                    sw1_low = c
                    state = "D1_wait_end"

            elif state == "D1_wait_end":
                if is_n_bar_high(i, 8):
                    wave_1[i] = sw1_low
                    sw2_high = c
                    state = "D2"

            elif state == "D2":
                if c > sw2_high:
                    sw2_high = c
                if is_n_bar_low(i, 21):
                    # Invalidation: mirrored rule (cannot close above Wave1 origin high).
                    if c > sw1_high:
                        reset_cycle()
                        continue
                    sw2_low = c
                    wave_2[i] = sw2_low
                    w1_range = sw1_high - sw1_low
                    wave_2_proj[i] = sw1_high - w1_range * 0.618
                    wave_3_proj[i] = sw1_high - w1_range * 1.618
                    sw3_high = c
                    sw3_start = i
                    state = "D3"

            elif state == "D3":
                if c > sw3_high:
                    sw3_high = c
                if is_n_bar_high(i, 13):
                    sw3_low = float(np.min(close[max(0, sw3_start) : i + 1]))
                    # Mirrored: Wave 3 trough must be below Wave 1 trough.
                    if sw3_low >= sw1_low:
                        reset_cycle()
                        continue
                    wave_3[i] = sw3_low
                    sw4_high = c
                    sw4_low = np.nan
                    state = "D4"

            elif state == "D4":
                if c > sw4_high:
                    sw4_high = c
                # Mirrored invalidation: Wave 4 cannot close above Wave 2 high.
                if c > sw2_high:
                    reset_cycle()
                    continue
                if is_n_bar_low(i, 34):
                    sw4_low = c
                    wave_4[i] = sw4_low
                    w3_range = sw3_high - sw3_low
                    wave_4_proj[i] = sw3_low + (w3_range * 0.382)
                    wave_5_proj[i] = sw3_high - (w3_range * 1.618)
                    sw5_start = i
                    sw5_high = c
                    state = "D5"

            elif state == "D5":
                if c > sw5_high:
                    sw5_high = c
                if is_n_bar_high(i, 13):
                    sw5_low = float(np.min(close[max(0, sw5_start) : i + 1]))
                    if sw5_low >= sw3_low:
                        reset_cycle()
                        continue
                    wave_5[i] = sw5_low
                    swa_start = i
                    swa_low = c
                    swa_high = c
                    state = "DA"

            elif state == "DA":
                if c < swa_low:
                    swa_low = c
                if c > swa_high:
                    swa_high = c
                if is_n_bar_low(i, 8):
                    wave_a[i] = swa_high
                    swb_start = i
                    swb_low = c
                    state = "DB"

            elif state == "DB":
                if c < swb_low:
                    swb_low = c
                # Continuous mirrored Wave B constraint.
                if c < sw5_low:
                    reset_cycle()
                    continue
                if is_n_bar_high(i, 21):
                    wave_b[i] = swb_low
                    sa_range = swa_high - swa_low
                    wave_c_proj[i] = swa_low + (sa_range * 1.618)
                    swc_high = c
                    state = "DC"

            elif state == "DC":
                if c > swc_high:
                    swc_high = c
                # Mirrored Wave C completion.
                if c >= swa_high:
                    wave_c[i] = swc_high
                    reset_cycle()
                    continue

            wave_state[i] = state

    return (
        pd.Series(wave_1, index=df.index),
        pd.Series(wave_2, index=df.index),
        pd.Series(wave_3, index=df.index),
        pd.Series(wave_4, index=df.index),
        pd.Series(wave_5, index=df.index),
        pd.Series(wave_a, index=df.index),
        pd.Series(wave_b, index=df.index),
        pd.Series(wave_c, index=df.index),
        pd.Series(wave_2_proj, index=df.index),
        pd.Series(wave_3_proj, index=df.index),
        pd.Series(wave_4_proj, index=df.index),
        pd.Series(wave_5_proj, index=df.index),
        pd.Series(wave_c_proj, index=df.index),
        pd.Series(wave_state, index=df.index),
    )


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

    # TD D-Wave analysis
    (
        wave_1, wave_2, wave_3, wave_4, wave_5,
        wave_a, wave_b, wave_c,
        wave_2_proj,
        wave_4_proj,
        wave_3_proj, wave_5_proj, wave_c_proj,
        wave_state
    ) = _waves(out)
    out["wave_1"] = wave_1
    out["wave_2"] = wave_2
    out["wave_3"] = wave_3
    out["wave_4"] = wave_4
    out["wave_5"] = wave_5
    out["wave_a"] = wave_a
    out["wave_b"] = wave_b
    out["wave_c"] = wave_c
    out["wave_2_proj"] = wave_2_proj
    out["wave_3_proj"] = wave_3_proj
    out["wave_4_proj"] = wave_4_proj
    out["wave_5_proj"] = wave_5_proj
    out["wave_c_proj"] = wave_c_proj
    out["wave_state"] = wave_state

    return out

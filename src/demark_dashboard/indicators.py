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
    Returns: wave_1, wave_2, wave_3, wave_4, wave_5, wave_a, wave_b, wave_c,
             wave_3_projection, wave_5_projection, wave_c_projection,
             wave_state_label (for charting)
    """
    close = df["Close"].values
    n = len(close)
    
    # Initialize output arrays
    wave_1 = np.full(n, np.nan)
    wave_2 = np.full(n, np.nan)
    wave_3 = np.full(n, np.nan)
    wave_4 = np.full(n, np.nan)
    wave_5 = np.full(n, np.nan)
    wave_a = np.full(n, np.nan)
    wave_b = np.full(n, np.nan)
    wave_c = np.full(n, np.nan)
    
    # Projection targets
    wave_3_proj = np.full(n, np.nan)
    wave_5_proj = np.full(n, np.nan)
    wave_c_proj = np.full(n, np.nan)
    
    # Wave state tracking
    wave_state = [""] * n  # "W1", "W2", "W3", etc.
    
    # State machine for uptrend sequence
    state_up = None  # None, "W1_origin", "W1_confirmed", "W1", "W2", "W3", "W4", "W5"
    state_down = None  # None, "WA", "WB", "WC"
    
    # Wave extremes tracking
    w1_low = np.nan
    w1_high = np.nan
    w1_idx = -1
    w2_low = np.nan
    w2_high = np.nan
    w2_idx = -1
    w3_low = np.nan
    w3_high = np.nan
    w3_idx = -1
    w4_low = np.nan
    w4_high = np.nan
    w4_idx = -1
    w5_low = np.nan
    w5_high = np.nan
    w5_idx = -1
    
    wa_low = np.nan
    wa_high = np.nan
    wa_idx = -1
    wb_low = np.nan
    wb_high = np.nan
    wb_idx = -1
    wc_low = np.nan
    wc_high = np.nan
    wc_idx = -1
    
    wc_locked = False  # Wave C completed (close < Wave A low)
    
    # Helper: Check if bar i has N-bar-low close
    def is_n_bar_low(i: int, n: int) -> bool:
        if i < n - 1:
            return False
        return close[i] < np.min(close[i - n + 1 : i])
    
    # Helper: Check if bar i has N-bar-high close
    def is_n_bar_high(i: int, n: int) -> bool:
        if i < n - 1:
            return False
        return close[i] > np.max(close[i - n + 1 : i])
    
    # Main state machine loop
    for i in range(n):
        current_close = close[i]
        
        # ===== UPTREND SEQUENCE (Waves 1-5) =====
        
        if state_up is None:
            # Looking for Wave 1 origin: 21-bar-low
            if is_n_bar_low(i, 21):
                state_up = "W1_origin"
                w1_low = current_close
                w1_idx = i
        
        elif state_up == "W1_origin":
            # Confirm Wave 1: 13-bar-high after origin
            if is_n_bar_high(i, 13):
                state_up = "W1_confirmed"
                w1_high = current_close
                wave_1[i] = current_close
                wave_state[i] = "W1"
            # If price falls to new low before 13-bar-high, reset origin
            elif current_close < w1_low:
                w1_low = current_close
                w1_idx = i
        
        elif state_up == "W1_confirmed":
            # Wave 1 ends with 8-bar-low
            if is_n_bar_low(i, 8):
                state_up = "W2"
                w2_low = current_close
                w2_idx = i
                wave_1[i] = w1_high
            else:
                wave_1[i] = w1_high
        
        elif state_up == "W2":
            # Wave 2 ends with 21-bar-high (confirms Wave 3 start)
            if is_n_bar_high(i, 21):
                # Wave 2 cannot close below Wave 1 low (invalidation rule)
                if current_close >= w1_low:
                    state_up = "W3"
                    w2_high = current_close
                    w2_idx = i
                    wave_2[i] = current_close
                    w3_low = np.inf
                    
                    # Calculate Wave 3 projection: Low_W1 + (High_W1 - Low_W1) * 1.618
                    w1_range = w1_high - w1_low
                    wave_3_proj[i] = w1_low + w1_range * 1.618
                else:
                    # Wave invalidated, restart
                    state_up = None
                    state_down = None
                    wc_locked = False
            else:
                # Update Wave 2 low if lower
                if current_close < w2_low:
                    w2_low = current_close
                    w2_idx = i
                wave_2[i] = w2_high if not np.isnan(w2_high) else w2_low
        
        elif state_up == "W3":
            # Track Wave 3 low
            if current_close < w3_low:
                w3_low = current_close
                w3_idx = i
            
            # Wave 3 ends with 13-bar-low (confirms Wave 4 start)
            if is_n_bar_low(i, 13):
                state_up = "W4"
                w3_high = np.max(close[max(0, w2_idx + 1) : i + 1])
                w4_low = current_close
                w4_idx = i
                wave_3[i] = w3_high
                
                # Wave 3 peak must be > Wave 1 peak
                if w3_high > w1_high:
                    pass  # Valid
                else:
                    # Invalid wave structure, reset
                    state_up = None
                    state_down = None
                    wc_locked = False
            else:
                wave_3[i] = w3_high if not np.isnan(w3_high) else np.nan
        
        elif state_up == "W4":
            # Track Wave 4 low
            if current_close < w4_low:
                w4_low = current_close
                w4_idx = i
            
            # Wave 4 ends with 34-bar-high (confirms Wave 5 start)
            if is_n_bar_high(i, 34):
                state_up = "W5"
                w4_high = current_close
                w4_idx = i
                wave_4[i] = current_close
                w5_low = np.inf
                
                # Calculate Wave 5 projection: Low_W3 + (High_W3 - Low_W3) * 1.618
                w3_range = w3_high - w3_low
                wave_5_proj[i] = w3_low + w3_range * 1.618
            else:
                wave_4[i] = w4_high if not np.isnan(w4_high) else np.nan
        
        elif state_up == "W5":
            # Track Wave 5 low
            if current_close < w5_low:
                w5_low = current_close
                w5_idx = i
            
            # Wave 5 ends with 13-bar-low (start of Wave A)
            if is_n_bar_low(i, 13):
                w5_high = np.max(close[max(0, w4_idx + 1) : i + 1])
                wave_5[i] = w5_high
                
                # Wave 5 peak must be > Wave 3 peak
                if w5_high > w3_high:
                    state_up = "COMPLETE"
                    state_down = "WA"
                    wa_low = current_close
                    wa_idx = i
                    wc_locked = False
                else:
                    # Invalid, reset
                    state_up = None
                    state_down = None
                    wc_locked = False
            else:
                wave_5[i] = w5_high if not np.isnan(w5_high) else np.nan
        
        # ===== CORRECTIVE SEQUENCE (Waves A-B-C) =====
        
        if state_down == "WA":
            # Track Wave A low
            if current_close < wa_low:
                wa_low = current_close
                wa_idx = i
            
            # Wave A ends with 8-bar-high (start of Wave B)
            if is_n_bar_high(i, 8):
                wa_high = np.max(close[max(0, w5_idx + 1) : i + 1])
                wave_a[i] = wa_high
                state_down = "WB"
                wb_low = current_close
                wb_idx = i
            else:
                wave_a[i] = wa_high if not np.isnan(wa_high) else np.nan
        
        elif state_down == "WB":
            # Track Wave B high
            if current_close > wb_low:
                wb_low = current_close
                wb_idx = i
            
            # Wave B ends with 21-bar-low (start of Wave C)
            if is_n_bar_low(i, 21):
                # Wave B cannot close above Wave 5 high (until Wave C locks)
                if not wc_locked and current_close <= w5_high:
                    wb_high = np.max(close[max(0, wa_idx + 1) : i + 1])
                    wave_b[i] = wb_high
                    state_down = "WC"
                    wc_low = current_close
                    wc_idx = i
                    
                    # Calculate Wave C projection: High_WA - (High_WA - Low_WA) * 1.618
                    wa_range = wa_high - wa_low
                    wave_c_proj[i] = wa_high - wa_range * 1.618
                elif wc_locked:
                    # Wave already locked, just track for next cycle
                    pass
            else:
                wave_b[i] = wb_high if not np.isnan(wb_high) else np.nan
        
        elif state_down == "WC":
            # Track Wave C low
            if current_close < wc_low:
                wc_low = current_close
                wc_idx = i
            
            # Wave C LOCKED when close <= Wave A low
            if current_close <= wa_low:
                wc_high = np.max(close[max(0, wb_idx + 1) : i + 1])
                wave_c[i] = wc_high
                wc_locked = True
                
                # Check if uptrend resumes (new Wave 1 starting)
                # This will be detected in next iteration when new 21-bar-low found
            else:
                wave_c[i] = wc_high if not np.isnan(wc_high) else np.nan
        
        # Update wave state labels for charting
        if state_up == "W1_confirmed" or state_up == "W1":
            wave_state[i] = "W1"
        elif state_up == "W2":
            wave_state[i] = "W2"
        elif state_up == "W3":
            wave_state[i] = "W3"
        elif state_up == "W4":
            wave_state[i] = "W4"
        elif state_up == "W5":
            wave_state[i] = "W5"
        elif state_down == "WA":
            wave_state[i] = "WA"
        elif state_down == "WB":
            wave_state[i] = "WB"
        elif state_down == "WC":
            wave_state[i] = "WC"
    
    # Convert to pandas Series
    return (
        pd.Series(wave_1, index=df.index),
        pd.Series(wave_2, index=df.index),
        pd.Series(wave_3, index=df.index),
        pd.Series(wave_4, index=df.index),
        pd.Series(wave_5, index=df.index),
        pd.Series(wave_a, index=df.index),
        pd.Series(wave_b, index=df.index),
        pd.Series(wave_c, index=df.index),
        pd.Series(wave_3_proj, index=df.index),
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
    out["wave_3_proj"] = wave_3_proj
    out["wave_5_proj"] = wave_5_proj
    out["wave_c_proj"] = wave_c_proj
    out["wave_state"] = wave_state

    return out

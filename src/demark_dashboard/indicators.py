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

    # Strict flip definition per book language:
    # bullish: prior bar was strictly below close[4], current bar strictly above close[4]
    # bearish: prior bar was strictly above close[4], current bar strictly below close[4]
    bullish_flip = (close > shifted_4) & (prev_close < prev_shifted_4)
    bearish_flip = (close < shifted_4) & (prev_close > prev_shifted_4)
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

    # Perfection can be deferred beyond setup bar 9.
    pending_buy_level = np.nan   # threshold = min(Low6, Low7) from most recent buy setup 9
    pending_sell_level = np.nan  # threshold = max(High6, High7) from most recent sell setup 9
    buy_pending = False
    sell_pending = False

    for i in range(len(df)):
        if buy_setup.iloc[i] == 9 and i >= 8:
            pending_buy_level = min(low.iloc[i - 3], low.iloc[i - 2])
            buy_pending = True
            # Immediate perfection on bar 9 if bar 8 or 9 satisfies level.
            if min(low.iloc[i - 1], low.iloc[i]) <= pending_buy_level:
                buy_perfected.iloc[i] = True
                buy_pending = False

        if sell_setup.iloc[i] == 9 and i >= 8:
            pending_sell_level = max(high.iloc[i - 3], high.iloc[i - 2])
            sell_pending = True
            # Immediate perfection on bar 9 if bar 8 or 9 satisfies level.
            if max(high.iloc[i - 1], high.iloc[i]) >= pending_sell_level:
                sell_perfected.iloc[i] = True
                sell_pending = False

        # Deferred perfection after setup 9.
        if buy_pending and low.iloc[i] <= pending_buy_level:
            buy_perfected.iloc[i] = True
            buy_pending = False

        if sell_pending and high.iloc[i] >= pending_sell_level:
            sell_perfected.iloc[i] = True
            sell_pending = False

        # New opposite completed setup invalidates pending perfection context.
        if buy_setup.iloc[i] == 9:
            sell_pending = False
        if sell_setup.iloc[i] == 9:
            buy_pending = False

    return buy_setup, sell_setup, buy_perfected, sell_perfected


def _setup_extensions(
    df: pd.DataFrame,
    bullish_flip: pd.Series,
    bearish_flip: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """Internal Setup counts that continue beyond 9 for recycle qualification."""
    close = df["Close"]
    buy_ext = pd.Series(0, index=df.index, dtype="int64")
    sell_ext = pd.Series(0, index=df.index, dtype="int64")

    buy_active = False
    sell_active = False
    bcount = 0
    scount = 0

    for i in range(len(df)):
        if i < 5:
            continue

        if bearish_flip.iloc[i]:
            buy_active = True
            sell_active = False
            bcount = 1
            scount = 0
            buy_ext.iloc[i] = 1
            continue

        if bullish_flip.iloc[i]:
            sell_active = True
            buy_active = False
            scount = 1
            bcount = 0
            sell_ext.iloc[i] = 1
            continue

        if buy_active:
            if close.iloc[i] < close.iloc[i - 4]:
                bcount += 1
                buy_ext.iloc[i] = bcount
            else:
                buy_active = False
                bcount = 0

        if sell_active:
            if close.iloc[i] > close.iloc[i - 4]:
                scount += 1
                sell_ext.iloc[i] = scount
            else:
                sell_active = False
                scount = 0

    return buy_ext, sell_ext


def _countdowns(
    df: pd.DataFrame,
    buy_setup: pd.Series,
    sell_setup: pd.Series,
    buy_setup_ext: pd.Series,
    sell_setup_ext: pd.Series,
    tdst_buy: pd.Series,
    tdst_sell: pd.Series,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """
        TD Countdown: 13 bars comparing close to low/high 2 bars earlier.
        Buy Countdown: 13 closes <= low[2 bars ago]
        Sell Countdown: 13 closes >= high[2 bars ago]

        This implementation supports concurrent hidden countdowns per direction.
        Multiple countdown candidates can run in the background, but only the
        countdown closest to completion is displayed on the chart for that bar.

        Deferred (13+): bar 13 close condition is met but bar-13 extreme vs close[8]
        fails. Countdown remains in awaiting state until both conditions are met.

        Returns:
            buy_countdown, sell_countdown,
            deferred_buy (+), deferred_sell (+),
            recycled_buy (R), recycled_sell (R),
            buy_countdown_active, sell_countdown_active,
            buy_deferred_active, sell_deferred_active
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

    buy_trackers: list[dict] = []
    sell_trackers: list[dict] = []
    last_buy_13_idx = None
    last_sell_13_idx = None

    # Gating policy for hidden same-direction trackers:
    # Avoid spawning unlimited overlapping countdowns (which can overproduce 13s),
    # but still allow limited overlap when the currently displayed tracker is very
    # close to completion (awaiting/deferred 13).
    ALLOW_OVERLAP_WHEN_AWAITING_13 = True

    def _progress_score(tracker: dict) -> float:
        if tracker["done"]:
            return 13.0
        if tracker["awaiting_13"]:
            return 12.5
        return float(tracker["count"])

    def _can_spawn_same_direction_tracker(trackers: list[dict]) -> bool:
        active = [t for t in trackers if not t["done"]]
        if not active:
            return True
        if ALLOW_OVERLAP_WHEN_AWAITING_13 and any(t["awaiting_13"] for t in active):
            return True
        return False

    def _update_buy_tracker(tracker: dict, i: int) -> tuple[int | None, bool]:
        printed_value: int | None = None
        deferred_event = False

        if tracker["done"]:
            return printed_value, deferred_event

        if tracker["awaiting_13"]:
            if close.iloc[i] <= low.iloc[i - 2]:
                if low.iloc[i] <= tracker["cd8_close"]:
                    tracker["done"] = True
                    printed_value = 13
                else:
                    deferred_event = True
            return printed_value, deferred_event

        if close.iloc[i] <= low.iloc[i - 2]:
            tracker["count"] += 1
            printed_value = tracker["count"]
            if tracker["count"] == 8:
                tracker["cd8_close"] = float(close.iloc[i])
            elif tracker["count"] == 13:
                if low.iloc[i] <= tracker["cd8_close"]:
                    tracker["done"] = True
                    printed_value = 13
                else:
                    tracker["count"] = 12
                    tracker["awaiting_13"] = True
                    printed_value = None
                    deferred_event = True

        return printed_value, deferred_event

    def _update_sell_tracker(tracker: dict, i: int) -> tuple[int | None, bool]:
        printed_value: int | None = None
        deferred_event = False

        if tracker["done"]:
            return printed_value, deferred_event

        if tracker["awaiting_13"]:
            if close.iloc[i] >= high.iloc[i - 2]:
                if high.iloc[i] >= tracker["cd8_close"]:
                    tracker["done"] = True
                    printed_value = 13
                else:
                    deferred_event = True
            return printed_value, deferred_event

        if close.iloc[i] >= high.iloc[i - 2]:
            tracker["count"] += 1
            printed_value = tracker["count"]
            if tracker["count"] == 8:
                tracker["cd8_close"] = float(close.iloc[i])
            elif tracker["count"] == 13:
                if high.iloc[i] >= tracker["cd8_close"]:
                    tracker["done"] = True
                    printed_value = 13
                else:
                    tracker["count"] = 12
                    tracker["awaiting_13"] = True
                    printed_value = None
                    deferred_event = True

        return printed_value, deferred_event

    for i in range(len(df)):
        if i < 2:
            continue

        true_low = min(float(low.iloc[i]), float(close.iloc[i - 1]))
        true_high = max(float(high.iloc[i]), float(close.iloc[i - 1]))

        # TDST cancellation of incomplete countdowns.
        if buy_trackers and pd.notna(tdst_buy.iloc[i]) and true_low > float(tdst_buy.iloc[i]):
            buy_trackers = []
        if sell_trackers and pd.notna(tdst_sell.iloc[i]) and true_high < float(tdst_sell.iloc[i]):
            sell_trackers = []

        # Opposite-direction Setup 9 cancels existing background trackers.
        if buy_setup.iloc[i] == 9 and sell_trackers:
            sell_trackers = []
        if sell_setup.iloc[i] == 9 and buy_trackers:
            buy_trackers = []

        # Start a new background tracker on every Setup 9.
        if buy_setup.iloc[i] == 9:
            if _can_spawn_same_direction_tracker(buy_trackers):
                buy_trackers.append({"count": 0, "cd8_close": np.nan, "awaiting_13": False, "done": False})
        if sell_setup.iloc[i] == 9:
            if _can_spawn_same_direction_tracker(sell_trackers):
                sell_trackers.append({"count": 0, "cd8_close": np.nan, "awaiting_13": False, "done": False})

        buy_events: list[tuple[int | None, bool]] = []
        for tracker in buy_trackers:
            buy_events.append(_update_buy_tracker(tracker, i))

        sell_events: list[tuple[int | None, bool]] = []
        for tracker in sell_trackers:
            sell_events.append(_update_sell_tracker(tracker, i))

        # Display only the tracker closest to completion for each direction.
        if buy_trackers:
            buy_best_idx = max(range(len(buy_trackers)), key=lambda k: _progress_score(buy_trackers[k]))
            buy_print, buy_deferred = buy_events[buy_best_idx]
            if buy_print is not None:
                buy_countdown.iloc[i] = int(buy_print)
                if int(buy_print) == 13:
                    last_buy_13_idx = df.index[i]
            if buy_deferred:
                deferred_buy.iloc[i] = True
            buy_deferred_active.iloc[i] = bool(buy_trackers[buy_best_idx]["awaiting_13"])

        if sell_trackers:
            sell_best_idx = max(range(len(sell_trackers)), key=lambda k: _progress_score(sell_trackers[k]))
            sell_print, sell_deferred = sell_events[sell_best_idx]
            if sell_print is not None:
                sell_countdown.iloc[i] = int(sell_print)
                if int(sell_print) == 13:
                    last_sell_13_idx = df.index[i]
            if sell_deferred:
                deferred_sell.iloc[i] = True
            sell_deferred_active.iloc[i] = bool(sell_trackers[sell_best_idx]["awaiting_13"])

        # Recycle applies to a completed 13 when a subsequent overlapping same-direction
        # Setup reaches 22 (default recycle threshold in the official implementation).
        if last_buy_13_idx is not None and buy_setup_ext.iloc[i] >= 22:
            buy_countdown.loc[last_buy_13_idx] = 0
            recycled_buy.loc[last_buy_13_idx] = True
            last_buy_13_idx = None

        if last_sell_13_idx is not None and sell_setup_ext.iloc[i] >= 22:
            sell_countdown.loc[last_sell_13_idx] = 0
            recycled_sell.loc[last_sell_13_idx] = True
            last_sell_13_idx = None

        buy_countdown_active.iloc[i] = any(not t["done"] for t in buy_trackers)
        sell_countdown_active.iloc[i] = any(not t["done"] for t in sell_trackers)

        # Keep completed trackers only for the completion bar, then remove.
        buy_trackers = [t for t in buy_trackers if not t["done"]]
        sell_trackers = [t for t in sell_trackers if not t["done"]]

    return (
        buy_countdown, sell_countdown,
        deferred_buy, deferred_sell,
        recycled_buy, recycled_sell,
        buy_countdown_active, sell_countdown_active,
        buy_deferred_active, sell_deferred_active,
    )


def _tdst_levels(df: pd.DataFrame, buy_setup: pd.Series, sell_setup: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    TDST (TD Setup Trend) from completed setups using true highs/lows.
    Buy Setup -> TDST Resistance = highest true high of completed 9 Buy Setup series.
    Sell Setup -> TDST Support = lowest true low of completed 9 Sell Setup series.

    Column naming is preserved for compatibility:
      tdst_buy  = TDST resistance from Buy Setup
      tdst_sell = TDST support from Sell Setup
    """
    tdst_buy = pd.Series(np.nan, index=df.index)
    tdst_sell = pd.Series(np.nan, index=df.index)

    curr_buy = np.nan
    curr_sell = np.nan
    prev_close = df["Close"].shift(1)
    true_high = pd.concat([df["High"], prev_close], axis=1).max(axis=1)
    true_low = pd.concat([df["Low"], prev_close], axis=1).min(axis=1)

    for i in range(len(df)):
        if buy_setup.iloc[i] == 9:
            window = df.iloc[max(0, i - 8) : i + 1]
            curr_buy = float(true_high.iloc[max(0, i - 8) : i + 1].max())
        if sell_setup.iloc[i] == 9:
            window = df.iloc[max(0, i - 8) : i + 1]
            curr_sell = float(true_low.iloc[max(0, i - 8) : i + 1].min())

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

    # Extended setup counts (internal recycle qualification support)
    buy_setup_ext, sell_setup_ext = _setup_extensions(out, bullish_flip, bearish_flip)
    out["buy_setup_ext"] = buy_setup_ext
    out["sell_setup_ext"] = sell_setup_ext

    # TDST levels
    tdst_buy, tdst_sell = _tdst_levels(out, buy_setup, sell_setup)
    out["tdst_buy"] = tdst_buy
    out["tdst_sell"] = tdst_sell

    # Countdown counts
    (
        buy_countdown, sell_countdown,
        deferred_buy, deferred_sell,
        recycled_buy, recycled_sell,
        buy_countdown_active, sell_countdown_active,
        buy_deferred_active, sell_deferred_active,
    ) = _countdowns(out, buy_setup, sell_setup, buy_setup_ext, sell_setup_ext, tdst_buy, tdst_sell)
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

    # True range for risk calculations
    out["true_range"] = _true_range(out)

    # TD D-Wave is disabled for now pending full accuracy validation.
    # Keep columns present as placeholders to preserve downstream compatibility.
    out["wave_1"] = np.nan
    out["wave_2"] = np.nan
    out["wave_3"] = np.nan
    out["wave_4"] = np.nan
    out["wave_5"] = np.nan
    out["wave_a"] = np.nan
    out["wave_b"] = np.nan
    out["wave_c"] = np.nan
    out["wave_2_proj"] = np.nan
    out["wave_3_proj"] = np.nan
    out["wave_4_proj"] = np.nan
    out["wave_5_proj"] = np.nan
    out["wave_c_proj"] = np.nan
    out["wave_state"] = ""

    return out

from __future__ import annotations

import numpy as np
import pandas as pd


def _true_range(df: pd.DataFrame) -> pd.Series:
    """True range = max(high-low, abs(high-prev_close), abs(low-prev_close))."""
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr


def _price_flips(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    Bearish TD Price Flip: Close > Close[4], then immediate Close < Close[4]
    Bullish TD Price Flip: Close < Close[4], then immediate Close > Close[4]
    """
    shifted_4 = close.shift(4)
    prev_close = close.shift(1)
    prev_shifted_4 = close.shift(5)

    bullish_flip = (close > shifted_4) & (prev_close < prev_shifted_4)
    bearish_flip = (close < shifted_4) & (prev_close > prev_shifted_4)
    return bullish_flip.fillna(False), bearish_flip.fillna(False)


def _setup_counts(
    df: pd.DataFrame,
    bullish_flip: pd.Series,
    bearish_flip: pd.Series,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Compute buy/sell setups (1-9) and deferred perfection states."""
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

    for i in range(len(df)):
        if i < 5:
            continue

        if bearish_flip.iloc[i]:
            buy_active = True
            sell_active = False
            bcount = 1
            buy_setup.iloc[i] = 1
            continue

        if bullish_flip.iloc[i]:
            sell_active = True
            buy_active = False
            scount = 1
            sell_setup.iloc[i] = 1
            continue

        if buy_active:
            if close.iloc[i] < close.iloc[i - 4]:
                bcount += 1
                buy_setup.iloc[i] = bcount
                if bcount >= 9:
                    buy_active = False
            else:
                buy_active = False
                bcount = 0

        if sell_active:
            if close.iloc[i] > close.iloc[i - 4]:
                scount += 1
                sell_setup.iloc[i] = scount
                if scount >= 9:
                    sell_active = False
            else:
                sell_active = False
                scount = 0

    pending_buy_level = np.nan
    pending_sell_level = np.nan
    buy_pending = False
    sell_pending = False

    for i in range(len(df)):
        if buy_setup.iloc[i] == 9 and i >= 8:
            pending_buy_level = min(low.iloc[i - 3], low.iloc[i - 2])
            buy_pending = True
            if min(low.iloc[i - 1], low.iloc[i]) <= pending_buy_level:
                buy_perfected.iloc[i] = True
                buy_pending = False

        if sell_setup.iloc[i] == 9 and i >= 8:
            pending_sell_level = max(high.iloc[i - 3], high.iloc[i - 2])
            sell_pending = True
            if max(high.iloc[i - 1], high.iloc[i]) >= pending_sell_level:
                sell_perfected.iloc[i] = True
                sell_pending = False

        if buy_pending and low.iloc[i] <= pending_buy_level:
            buy_perfected.iloc[i] = True
            buy_pending = False

        if sell_pending and high.iloc[i] >= pending_sell_level:
            sell_perfected.iloc[i] = True
            sell_pending = False

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
    """Internal setup counts that continue beyond 9 until extinguished by opposite flip."""
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
    """TD Countdown engine with cancellation, recycle, and qualifier logic."""
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

    RECYCLE_SETUP_EXTENSION = 18
    PHI = 1.618
    ALLOW_OVERLAP_WHEN_AWAITING_13 = True

    buy_setup_ctxs: list[dict] = []
    sell_setup_ctxs: list[dict] = []
    buy_curr_ctx: dict | None = None
    sell_curr_ctx: dict | None = None
    last_buy_setup9_idx: int | None = None
    last_sell_setup9_idx: int | None = None

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

    def _new_setup_ctx(i: int, true_low_value: float, true_high_value: float) -> dict:
        c = float(close.iloc[i])
        return {
            "start": i,
            "end": i,
            "true_high": true_high_value,
            "true_low": true_low_value,
            "close_high": c,
            "close_low": c,
        }

    def _update_setup_ctx(ctx: dict, i: int, true_low_value: float, true_high_value: float) -> None:
        ctx["end"] = i
        ctx["true_high"] = max(float(ctx["true_high"]), true_high_value)
        ctx["true_low"] = min(float(ctx["true_low"]), true_low_value)
        c = float(close.iloc[i])
        ctx["close_high"] = max(float(ctx["close_high"]), c)
        ctx["close_low"] = min(float(ctx["close_low"]), c)

    def _ctx_range(ctx: dict) -> float:
        return float(ctx["true_high"]) - float(ctx["true_low"])

    def _within(outer_low: float, outer_high: float, inner_low: float, inner_high: float) -> bool:
        return inner_low >= outer_low and inner_high <= outer_high

    def _evaluate_qualifiers(prev_ctx: dict, curr_ctx: dict) -> tuple[bool, bool]:
        prev_range = _ctx_range(prev_ctx)
        curr_range = _ctx_range(curr_ctx)
        qualifier_i = prev_range > 0 and (curr_range >= prev_range) and (curr_range < PHI * prev_range)
        qualifier_ii = _within(
            float(prev_ctx["true_low"]),
            float(prev_ctx["true_high"]),
            float(curr_ctx["close_low"]),
            float(curr_ctx["close_high"]),
        ) and _within(
            float(prev_ctx["true_low"]),
            float(prev_ctx["true_high"]),
            float(curr_ctx["true_low"]),
            float(curr_ctx["true_high"]),
        )
        return qualifier_i, qualifier_ii

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

        if buy_setup_ext.iloc[i] == 1:
            buy_curr_ctx = _new_setup_ctx(i, true_low, true_high)
        elif buy_setup_ext.iloc[i] > 1 and buy_curr_ctx is not None:
            _update_setup_ctx(buy_curr_ctx, i, true_low, true_high)
        elif buy_setup_ext.iloc[i] == 0:
            buy_curr_ctx = None

        if sell_setup_ext.iloc[i] == 1:
            sell_curr_ctx = _new_setup_ctx(i, true_low, true_high)
        elif sell_setup_ext.iloc[i] > 1 and sell_curr_ctx is not None:
            _update_setup_ctx(sell_curr_ctx, i, true_low, true_high)
        elif sell_setup_ext.iloc[i] == 0:
            sell_curr_ctx = None

        if buy_trackers and pd.notna(tdst_buy.iloc[i]) and true_low > float(tdst_buy.iloc[i]):
            buy_trackers = []
        if sell_trackers and pd.notna(tdst_sell.iloc[i]) and true_high < float(tdst_sell.iloc[i]):
            sell_trackers = []

        if buy_trackers and buy_setup_ext.iloc[i] >= RECYCLE_SETUP_EXTENSION:
            buy_trackers = []
            recycled_buy.iloc[i] = True
        if sell_trackers and sell_setup_ext.iloc[i] >= RECYCLE_SETUP_EXTENSION:
            sell_trackers = []
            recycled_sell.iloc[i] = True

        if buy_setup.iloc[i] == 9 and sell_trackers:
            sell_trackers = []
        if sell_setup.iloc[i] == 9 and buy_trackers:
            buy_trackers = []

        if buy_setup.iloc[i] == 9:
            qualifier_i = False
            qualifier_ii = False
            if buy_curr_ctx is not None:
                buy_setup_ctxs.append(buy_curr_ctx.copy())
                if len(buy_setup_ctxs) >= 2 and (last_sell_setup9_idx is None or last_sell_setup9_idx < int(buy_curr_ctx["start"])):
                    qualifier_i, qualifier_ii = _evaluate_qualifiers(buy_setup_ctxs[-2], buy_setup_ctxs[-1])

            if qualifier_i and buy_trackers:
                buy_trackers = []
                recycled_buy.iloc[i] = True

            if not qualifier_ii and _can_spawn_same_direction_tracker(buy_trackers):
                buy_trackers.append({"count": 0, "cd8_close": np.nan, "awaiting_13": False, "done": False})

            last_buy_setup9_idx = i

        if sell_setup.iloc[i] == 9:
            qualifier_i = False
            qualifier_ii = False
            if sell_curr_ctx is not None:
                sell_setup_ctxs.append(sell_curr_ctx.copy())
                if len(sell_setup_ctxs) >= 2 and (last_buy_setup9_idx is None or last_buy_setup9_idx < int(sell_curr_ctx["start"])):
                    qualifier_i, qualifier_ii = _evaluate_qualifiers(sell_setup_ctxs[-2], sell_setup_ctxs[-1])

            if qualifier_i and sell_trackers:
                sell_trackers = []
                recycled_sell.iloc[i] = True

            if not qualifier_ii and _can_spawn_same_direction_tracker(sell_trackers):
                sell_trackers.append({"count": 0, "cd8_close": np.nan, "awaiting_13": False, "done": False})

            last_sell_setup9_idx = i

        buy_events = [_update_buy_tracker(t, i) for t in buy_trackers]
        sell_events = [_update_sell_tracker(t, i) for t in sell_trackers]

        if buy_trackers:
            best = max(range(len(buy_trackers)), key=lambda k: _progress_score(buy_trackers[k]))
            buy_print, buy_def = buy_events[best]
            if buy_print is not None:
                buy_countdown.iloc[i] = int(buy_print)
            if buy_def:
                deferred_buy.iloc[i] = True
            buy_deferred_active.iloc[i] = bool(buy_trackers[best]["awaiting_13"])

        if sell_trackers:
            best = max(range(len(sell_trackers)), key=lambda k: _progress_score(sell_trackers[k]))
            sell_print, sell_def = sell_events[best]
            if sell_print is not None:
                sell_countdown.iloc[i] = int(sell_print)
            if sell_def:
                deferred_sell.iloc[i] = True
            sell_deferred_active.iloc[i] = bool(sell_trackers[best]["awaiting_13"])

        buy_countdown_active.iloc[i] = any(not t["done"] for t in buy_trackers)
        sell_countdown_active.iloc[i] = any(not t["done"] for t in sell_trackers)

        buy_trackers = [t for t in buy_trackers if not t["done"]]
        sell_trackers = [t for t in sell_trackers if not t["done"]]

    return (
        buy_countdown,
        sell_countdown,
        deferred_buy,
        deferred_sell,
        recycled_buy,
        recycled_sell,
        buy_countdown_active,
        sell_countdown_active,
        buy_deferred_active,
        sell_deferred_active,
    )


def _tdst_levels(df: pd.DataFrame, buy_setup: pd.Series, sell_setup: pd.Series) -> tuple[pd.Series, pd.Series]:
    """TDST from completed setups using true highs/lows."""
    tdst_buy = pd.Series(np.nan, index=df.index)
    tdst_sell = pd.Series(np.nan, index=df.index)

    curr_buy = np.nan
    curr_sell = np.nan
    prev_close = df["Close"].shift(1)
    true_high = pd.concat([df["High"], prev_close], axis=1).max(axis=1)
    true_low = pd.concat([df["Low"], prev_close], axis=1).min(axis=1)

    for i in range(len(df)):
        if buy_setup.iloc[i] == 9:
            curr_buy = float(true_high.iloc[max(0, i - 8) : i + 1].max())
        if sell_setup.iloc[i] == 9:
            curr_sell = float(true_low.iloc[max(0, i - 8) : i + 1].min())

        tdst_buy.iloc[i] = curr_buy
        tdst_sell.iloc[i] = curr_sell

    return tdst_buy, tdst_sell


def apply_demark(df: pd.DataFrame) -> pd.DataFrame:
    """Apply TD Sequential indicators to OHLCV history."""
    out = df.copy()

    bullish_flip, bearish_flip = _price_flips(out["Close"])
    out["bullish_flip"] = bullish_flip
    out["bearish_flip"] = bearish_flip

    buy_setup, sell_setup, buy_perfected, sell_perfected = _setup_counts(out, bullish_flip, bearish_flip)
    out["buy_setup"] = buy_setup
    out["sell_setup"] = sell_setup
    out["buy_perfected"] = buy_perfected
    out["sell_perfected"] = sell_perfected

    buy_setup_ext, sell_setup_ext = _setup_extensions(out, bullish_flip, bearish_flip)
    out["buy_setup_ext"] = buy_setup_ext
    out["sell_setup_ext"] = sell_setup_ext

    tdst_buy, tdst_sell = _tdst_levels(out, buy_setup, sell_setup)
    out["tdst_buy"] = tdst_buy
    out["tdst_sell"] = tdst_sell

    (
        buy_countdown,
        sell_countdown,
        deferred_buy,
        deferred_sell,
        recycled_buy,
        recycled_sell,
        buy_countdown_active,
        sell_countdown_active,
        buy_deferred_active,
        sell_deferred_active,
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

    out["true_range"] = _true_range(out)
    return out

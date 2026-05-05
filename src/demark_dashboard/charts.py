from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_figure(df: pd.DataFrame, symbol: str) -> go.Figure:
    """Build interactive candlestick chart with complete TD Sequential overlays."""
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.75, 0.25],
    )

    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name=symbol,
            increasing_line_color="#16a34a",
            decreasing_line_color="#dc2626",
        ),
        row=1,
        col=1,
    )

    # TDST support (Buy Support)
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["tdst_buy"],
            mode="lines",
            name="TDST Buy Support",
            line=dict(color="#0ea5e9", width=1.5, dash="dot"),
            fill=None,
        ),
        row=1,
        col=1,
    )

    # TDST resistance (Sell Resistance)
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["tdst_sell"],
            mode="lines",
            name="TDST Sell Resistance",
            line=dict(color="#f97316", width=1.5, dash="dot"),
            fill=None,
        ),
        row=1,
        col=1,
    )

    # Buy Setup completion (9) - green diamonds
    buy9 = df[df["buy_setup"] == 9]
    fig.add_trace(
        go.Scatter(
            x=buy9.index,
            y=buy9["Low"] * 0.98,
            mode="markers+text",
            marker=dict(color="#2563eb", size=10, symbol="diamond"),
            text=["B9"] * len(buy9),
            textposition="bottom center",
            textfont=dict(size=9, color="#2563eb"),
            name="Buy Setup 9",
            hovertext=[f"Buy Setup 9 Complete" for _ in buy9.index],
            hoverinfo="x+text",
        ),
        row=1,
        col=1,
    )

    # Sell Setup completion (9) - red diamonds
    sell9 = df[df["sell_setup"] == 9]
    fig.add_trace(
        go.Scatter(
            x=sell9.index,
            y=sell9["High"] * 1.02,
            mode="markers+text",
            marker=dict(color="#dc2626", size=10, symbol="diamond"),
            text=["S9"] * len(sell9),
            textposition="top center",
            textfont=dict(size=9, color="#dc2626"),
            name="Sell Setup 9",
            hovertext=[f"Sell Setup 9 Complete" for _ in sell9.index],
            hoverinfo="x+text",
        ),
        row=1,
        col=1,
    )

    # Buy Countdown 13 - green squares
    buy13 = df[df["buy_countdown"] == 13]
    fig.add_trace(
        go.Scatter(
            x=buy13.index,
            y=buy13["Low"] * 0.96,
            mode="markers+text",
            marker=dict(color="#059669", size=12, symbol="square"),
            text=["B13"] * len(buy13),
            textposition="bottom center",
            textfont=dict(size=10, color="#059669", family="monospace"),
            name="Buy Countdown 13",
            hovertext=[f"Buy Countdown 13 - Signal!" for _ in buy13.index],
            hoverinfo="x+text",
        ),
        row=1,
        col=1,
    )

    # Sell Countdown 13 - red squares
    sell13 = df[df["sell_countdown"] == 13]
    fig.add_trace(
        go.Scatter(
            x=sell13.index,
            y=sell13["High"] * 1.04,
            mode="markers+text",
            marker=dict(color="#991b1b", size=12, symbol="square"),
            text=["S13"] * len(sell13),
            textposition="top center",
            textfont=dict(size=10, color="#991b1b", family="monospace"),
            name="Sell Countdown 13",
            hovertext=[f"Sell Countdown 13 - Signal!" for _ in sell13.index],
            hoverinfo="x+text",
        ),
        row=1,
        col=1,
    )

    # Deferred Buy (+)
    deferred_buy = df[df["deferred_buy"]]
    if not deferred_buy.empty:
        fig.add_trace(
            go.Scatter(
                x=deferred_buy.index,
                y=deferred_buy["Low"] * 0.965,
                mode="markers+text",
                marker=dict(color="#fbbf24", size=9),
                text=["+"] * len(deferred_buy),
                textposition="bottom center",
                textfont=dict(size=14, color="#fbbf24"),
                name="Deferred Buy (+)",
                hovertext=[f"Buy Countdown Deferred" for _ in deferred_buy.index],
                hoverinfo="x+text",
            ),
            row=1,
            col=1,
        )

    # Deferred Sell (+)
    deferred_sell = df[df["deferred_sell"]]
    if not deferred_sell.empty:
        fig.add_trace(
            go.Scatter(
                x=deferred_sell.index,
                y=deferred_sell["High"] * 1.032,
                mode="markers+text",
                marker=dict(color="#fbbf24", size=9),
                text=["+"] * len(deferred_sell),
                textposition="top center",
                textfont=dict(size=14, color="#fbbf24"),
                name="Deferred Sell (+)",
                hovertext=[f"Sell Countdown Deferred" for _ in deferred_sell.index],
                hoverinfo="x+text",
            ),
            row=1,
            col=1,
        )

    # Perfection arrows - Buy (up arrows)
    buy_perf = df[df["buy_perfected"]]
    if not buy_perf.empty:
        fig.add_trace(
            go.Scatter(
                x=buy_perf.index,
                y=buy_perf["Low"] * 0.99,
                mode="markers",
                marker=dict(color="#10b981", size=15, symbol="triangle-up"),
                name="Buy Perfected ↑",
                hovertext=[f"Buy Setup Perfected" for _ in buy_perf.index],
                hoverinfo="x+text",
            ),
            row=1,
            col=1,
        )

    # Perfection arrows - Sell (down arrows)
    sell_perf = df[df["sell_perfected"]]
    if not sell_perf.empty:
        fig.add_trace(
            go.Scatter(
                x=sell_perf.index,
                y=sell_perf["High"] * 1.01,
                mode="markers",
                marker=dict(color="#ef4444", size=15, symbol="triangle-down"),
                name="Sell Perfected ↓",
                hovertext=[f"Sell Setup Perfected" for _ in sell_perf.index],
                hoverinfo="x+text",
            ),
            row=1,
            col=1,
        )

    # Volume bars
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["Volume"],
            name="Volume",
            marker_color="#94a3b8",
            opacity=0.5,
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        title=f"<b>{symbol}</b> — DeMark TD Sequential Dashboard (Jason Perl Methodology)",
        template="plotly_white",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="v", yanchor="top", y=0.99, xanchor="left", x=0.01, font=dict(size=9)),
        margin=dict(l=50, r=50, t=80, b=50),
        height=800,
        hovermode="x unified",
        font=dict(family="Courier New, monospace"),
    )

    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_xaxes(title_text="Date", row=2, col=1)

    return fig

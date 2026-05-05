from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_figure(df: pd.DataFrame, symbol: str) -> go.Figure:
    """Build interactive OHLC chart with TD Sequential overlays in DeMark-style notation."""
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.75, 0.25],
    )

    # OHLC bars (book-style visual language)
    fig.add_trace(
        go.Ohlc(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name=symbol,
            increasing_line_color="#16a34a",
            decreasing_line_color="#dc2626",
            line_width=1,
        ),
        row=1,
        col=1,
    )

    # Full Setup counts 1-9
    buy_setup = df[df["buy_setup"] > 0]
    if not buy_setup.empty:
        fig.add_trace(
            go.Scatter(
                x=buy_setup.index,
                y=buy_setup["Low"] * 0.995,
                mode="text",
                text=[str(int(v)) for v in buy_setup["buy_setup"]],
                textposition="bottom center",
                textfont=dict(size=10, color="#2563eb", family="Courier New, monospace"),
                name="Buy Setup 1-9",
                hovertext=[f"Buy Setup {int(v)}/9" for v in buy_setup["buy_setup"]],
                hoverinfo="x+text",
            ),
            row=1,
            col=1,
        )

    sell_setup = df[df["sell_setup"] > 0]
    if not sell_setup.empty:
        fig.add_trace(
            go.Scatter(
                x=sell_setup.index,
                y=sell_setup["High"] * 1.005,
                mode="text",
                text=[str(int(v)) for v in sell_setup["sell_setup"]],
                textposition="top center",
                textfont=dict(size=10, color="#dc2626", family="Courier New, monospace"),
                name="Sell Setup 1-9",
                hovertext=[f"Sell Setup {int(v)}/9" for v in sell_setup["sell_setup"]],
                hoverinfo="x+text",
            ),
            row=1,
            col=1,
        )

    # Full Countdown counts 1-13 (display as parenthesized numbers)
    buy_cd = df[df["buy_countdown"] > 0]
    if not buy_cd.empty:
        fig.add_trace(
            go.Scatter(
                x=buy_cd.index,
                y=buy_cd["Low"] * 0.985,
                mode="text",
                text=[f"({int(v)})" for v in buy_cd["buy_countdown"]],
                textposition="bottom center",
                textfont=dict(size=9, color="#0f766e", family="Courier New, monospace"),
                name="Buy Countdown 1-13",
                hovertext=[f"Buy Countdown {int(v)}/13" for v in buy_cd["buy_countdown"]],
                hoverinfo="x+text",
            ),
            row=1,
            col=1,
        )

    sell_cd = df[df["sell_countdown"] > 0]
    if not sell_cd.empty:
        fig.add_trace(
            go.Scatter(
                x=sell_cd.index,
                y=sell_cd["High"] * 1.015,
                mode="text",
                text=[f"({int(v)})" for v in sell_cd["sell_countdown"]],
                textposition="top center",
                textfont=dict(size=9, color="#9f1239", family="Courier New, monospace"),
                name="Sell Countdown 1-13",
                hovertext=[f"Sell Countdown {int(v)}/13" for v in sell_cd["sell_countdown"]],
                hoverinfo="x+text",
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

    # Buy Setup completion (9)
    buy9 = df[df["buy_setup"] == 9]
    fig.add_trace(
        go.Scatter(
            x=buy9.index,
            y=buy9["Low"] * 0.98,
            mode="markers+text",
            marker=dict(color="#2563eb", size=10, symbol="diamond"),
            text=["9"] * len(buy9),
            textposition="bottom center",
            textfont=dict(size=9, color="#2563eb"),
            name="Buy Setup 9 Complete",
            hovertext=["Buy Setup 9 complete" for _ in buy9.index],
            hoverinfo="x+text",
        ),
        row=1,
        col=1,
    )

    # Sell Setup completion (9)
    sell9 = df[df["sell_setup"] == 9]
    fig.add_trace(
        go.Scatter(
            x=sell9.index,
            y=sell9["High"] * 1.02,
            mode="markers+text",
            marker=dict(color="#dc2626", size=10, symbol="diamond"),
            text=["9"] * len(sell9),
            textposition="top center",
            textfont=dict(size=9, color="#dc2626"),
            name="Sell Setup 9 Complete",
            hovertext=["Sell Setup 9 complete" for _ in sell9.index],
            hoverinfo="x+text",
        ),
        row=1,
        col=1,
    )

    # Buy Countdown 13
    buy13 = df[df["buy_countdown"] == 13]
    fig.add_trace(
        go.Scatter(
            x=buy13.index,
            y=buy13["Low"] * 0.96,
            mode="markers+text",
            marker=dict(color="#059669", size=12, symbol="square"),
            text=["13"] * len(buy13),
            textposition="bottom center",
            textfont=dict(size=10, color="#059669", family="monospace"),
            name="Buy Countdown 13 Complete",
            hovertext=["Buy Countdown 13 signal" for _ in buy13.index],
            hoverinfo="x+text",
        ),
        row=1,
        col=1,
    )

    # Sell Countdown 13
    sell13 = df[df["sell_countdown"] == 13]
    fig.add_trace(
        go.Scatter(
            x=sell13.index,
            y=sell13["High"] * 1.04,
            mode="markers+text",
            marker=dict(color="#991b1b", size=12, symbol="square"),
            text=["13"] * len(sell13),
            textposition="top center",
            textfont=dict(size=10, color="#991b1b", family="monospace"),
            name="Sell Countdown 13 Complete",
            hovertext=["Sell Countdown 13 signal" for _ in sell13.index],
            hoverinfo="x+text",
        ),
        row=1,
        col=1,
    )

    # Deferred Buy (13+)
    deferred_buy = df[df["deferred_buy"]]
    if not deferred_buy.empty:
        fig.add_trace(
            go.Scatter(
                x=deferred_buy.index,
                y=deferred_buy["Low"] * 0.965,
                mode="markers+text",
                marker=dict(color="#fbbf24", size=9),
                text=["13+"] * len(deferred_buy),
                textposition="bottom center",
                textfont=dict(size=14, color="#fbbf24"),
                name="Deferred Buy 13+",
                hovertext=["Buy Countdown deferred (13+)" for _ in deferred_buy.index],
                hoverinfo="x+text",
            ),
            row=1,
            col=1,
        )

    # Deferred Sell (13+)
    deferred_sell = df[df["deferred_sell"]]
    if not deferred_sell.empty:
        fig.add_trace(
            go.Scatter(
                x=deferred_sell.index,
                y=deferred_sell["High"] * 1.032,
                mode="markers+text",
                marker=dict(color="#fbbf24", size=9),
                text=["13+"] * len(deferred_sell),
                textposition="top center",
                textfont=dict(size=14, color="#fbbf24"),
                name="Deferred Sell 13+",
                hovertext=["Sell Countdown deferred (13+)" for _ in deferred_sell.index],
                hoverinfo="x+text",
            ),
            row=1,
            col=1,
        )

    # Recycle markers (R)
    recycled_buy = df[df.get("recycled_buy", False)]
    if not recycled_buy.empty:
        fig.add_trace(
            go.Scatter(
                x=recycled_buy.index,
                y=recycled_buy["Low"] * 0.975,
                mode="text",
                text=["R"] * len(recycled_buy),
                textposition="bottom center",
                textfont=dict(size=12, color="#1d4ed8", family="Courier New, monospace"),
                name="Buy Recycle (R)",
                hovertext=["Buy Countdown recycled" for _ in recycled_buy.index],
                hoverinfo="x+text",
            ),
            row=1,
            col=1,
        )

    recycled_sell = df[df.get("recycled_sell", False)]
    if not recycled_sell.empty:
        fig.add_trace(
            go.Scatter(
                x=recycled_sell.index,
                y=recycled_sell["High"] * 1.025,
                mode="text",
                text=["R"] * len(recycled_sell),
                textposition="top center",
                textfont=dict(size=12, color="#b91c1c", family="Courier New, monospace"),
                name="Sell Recycle (R)",
                hovertext=["Sell Countdown recycled" for _ in recycled_sell.index],
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

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import yfinance as yf

st.set_page_config(
    page_title="Stock Portfolio Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Stock Portfolio Dashboard")

uploaded_file = st.file_uploader(
    "Upload stock portfolio Excel-fil",
    type=["xlsx"]
)

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    required_cols = [
        "Ticker",
        "Antal",
        "Købskurs",
        "Aktuel kurs",
        "Beholdning",
        "Gevinst",
        "Sektor"
    ]

            def yahoo_ticker(ticker):
            try:
                ticker = str(ticker)
                mapping = {
                    "XCSE": ".CO",
                    "XSTO": ".ST",
                    "XAMS": ".AS",
                    "XETR": ".DE",
                    "XNYS": "",
                    "XNAS": "",
                    "NEOE": ".NE"
                }

                if ":" in ticker:
                    symbol, exchange = ticker.split(":")
                    return symbol + mapping.get(exchange, "")
                return ticker
            except Exception:
                return ticker

        df["Yahoo"] = df["Ticker"].apply(yahoo_ticker)
    
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        st.error(f"Mangler kolonner: {missing_cols}")

    else:
        # ---------------------------------------------------
        # Grunddata og beregninger
        # ---------------------------------------------------

        df["Market value"] = df["Beholdning"]
        df["Cost value"] = df["Market value"] / (1 + df["Gevinst"])
        df["Gain/Loss"] = df["Market value"] - df["Cost value"]
        df["Return %"] = df["Gain/Loss"] / df["Cost value"]
        df["Weight %"] = df["Market value"] / df["Market value"].sum()

        total_value = df["Market value"].sum()
        total_cost = df["Cost value"].sum()
        total_gain = total_value - total_cost
        total_return = total_gain / total_cost

        # ---------------------------------------------------
        # KPI'er
        # ---------------------------------------------------

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Porteføljeværdi", f"{total_value:,.0f}".replace(",", "."))
        col2.metric("Gevinst/tab", f"{total_gain:,.0f}".replace(",", "."))
        col3.metric("Afkast %", f"{total_return:.1%}".replace(".", ","))
        col4.metric("Antal aktier", len(df))

        # ---------------------------------------------------
        # Momentum-lignende scoringmodel
        # ---------------------------------------------------

        df["Current weight"] = df["Weight %"]

        def performance_score(gain):
            try:
                gain = float(gain)

                if gain >= 0.40:
                    return 5
                elif gain >= 0.15:
                    return 4
                elif gain >= 0.00:
                    return 3
                elif gain >= -0.15:
                    return 2
                else:
                    return 1
            except Exception:
                return 2

        df["Momentum score"] = df["Gevinst"].apply(performance_score)

        def concentration_risk(weight):
            try:
                weight = float(weight)

                if weight >= 0.18:
                    return 5
                elif weight >= 0.12:
                    return 4
                elif weight >= 0.08:
                    return 3
                elif weight >= 0.04:
                    return 2
                else:
                    return 1
            except Exception:
                return 3

        df["Concentration risk"] = df["Current weight"].apply(concentration_risk)

        high_risk_tickers = [
            "AMC:XETR",
            "IVN:NEOE",
            "VWS:XCSE",
            "ENR:XETR"
        ]

        low_risk_tickers = [
            "MSF:XETR",
            "TSM:XNYS",
            "ABB:XSTO"
        ]

        def stock_risk_score(ticker):
            ticker = str(ticker)

            if ticker in high_risk_tickers:
                return 5
            elif ticker in low_risk_tickers:
                return 2
            else:
                return 3

        df["Stock risk"] = df["Ticker"].apply(stock_risk_score)

        df["Risk score"] = (
            df["Concentration risk"] * 0.50
            + df["Stock risk"] * 0.35
            + (6 - df["Momentum score"]) * 0.15
        )

        df["Portfolio score"] = (
            df["Momentum score"] * 0.65
            + (6 - df["Risk score"]) * 0.35
        )

        df["Portfolio score"] = df["Portfolio score"].clip(lower=0.5)

        # Foreslået vægt ud fra score
        df["Suggested weight"] = df["Portfolio score"] / df["Portfolio score"].sum()

        # Min/max vægt for enkeltaktier
        min_weight = 0.02
        max_weight = 0.12

        df["Suggested weight"] = df["Suggested weight"].clip(
            lower=min_weight,
            upper=max_weight
        )

        # Normaliser til 100%
        df["Suggested weight"] = df["Suggested weight"] / df["Suggested weight"].sum()

        df["Suggested value"] = df["Suggested weight"] * total_value
        df["Trade DKK"] = df["Suggested value"] - df["Market value"]
        df["Weight change"] = df["Suggested weight"] - df["Current weight"]

        # ---------------------------------------------------
        # Porteføljeoversigt
        # ---------------------------------------------------

        st.subheader("Porteføljeoversigt")

        display_df = df.copy()

        def format_dkk(value):
            try:
                return f"{float(value):,.0f}".replace(",", ".")
            except Exception:
                return value

        def format_pct(value):
            try:
                return f"{float(value) * 100:.1f}%".replace(".", ",")
            except Exception:
                return value

        def format_number(value):
            try:
                return f"{float(value):.0f}"
            except Exception:
                return value

        for col in ["Købskurs", "Aktuel kurs"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(format_number)

        for col in ["Beholdning", "Gain/Loss"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(format_dkk)

        for col in ["Gevinst", "Return %", "Weight %"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(format_pct)

        columns_to_hide = [
            "Market value",
            "Cost value",
            "Current weight",
            "Momentum score",
            "Concentration risk",
            "Stock risk",
            "Risk score",
            "Portfolio score",
            "Suggested weight",
            "Suggested value",
            "Trade DKK",
            "Weight change",
            "Target weight"
        ]

        display_df = display_df.drop(
            columns=[col for col in columns_to_hide if col in display_df.columns],
            errors="ignore"
        )

        preferred_order = [
            "Navn",
            "Ticker",
            "Weight %",
            "Antal",
            "Købskurs",
            "Aktuel kurs",
            "Beholdning",
            "Gevinst",
            "Gain/Loss",
            "Return %",
            "Valuta",
            "Sektor"
        ]

        existing_cols = [col for col in preferred_order if col in display_df.columns]
        other_cols = [col for col in display_df.columns if col not in existing_cols]
        display_df = display_df[existing_cols + other_cols]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

        # ---------------------------------------------------
        # Vægtning pr. aktie
        # ---------------------------------------------------

        st.subheader("Vægtning pr. aktie")

        weight_df = df.sort_values("Weight %", ascending=False).copy()

        weight_df["Weight label"] = weight_df["Weight %"].apply(
            lambda x: f"{x:.1%}".replace(".", ",")
        )

        fig_weight = px.bar(
            weight_df,
            x="Ticker",
            y="Weight %",
            text="Weight label"
        )

        fig_weight.update_traces(
            textposition="outside"
        )

        fig_weight.update_layout(
            yaxis_tickformat=".0%",
            xaxis_title="Aktie",
            yaxis_title="Vægt",
            uniformtext_minsize=10,
            uniformtext_mode="show"
        )

        st.plotly_chart(fig_weight, use_container_width=True)

        # ---------------------------------------------------
        # Rebalanceringsforslag
        # ---------------------------------------------------

        st.subheader("Rebalanceringsforslag")

        rebalance_df = df.copy()

        def recommendation(row):
            trade = row["Trade DKK"]
            weight_change = row["Weight change"]

            if trade > total_value * 0.015 and weight_change > 0:
                return "Øg"
            elif trade < -total_value * 0.015 and weight_change < 0:
                return "Reducer"
            else:
                return "Hold"

        rebalance_df["Anbef."] = rebalance_df.apply(recommendation, axis=1)

        def yahoo_ticker(ticker):
            try:
                ticker = str(ticker)
                mapping = {
                    "XCSE": ".CO",
                    "XSTO": ".ST",
                    "XAMS": ".AS",
                    "XETR": ".DE",
                    "XNYS": "",
                    "XNAS": "",
                    "NEOE": ".NE"
                }

                if ":" in ticker:
                    symbol, exchange = ticker.split(":")
                    return symbol + mapping.get(exchange, "")
                return ticker
            except Exception:
                return ticker

        rebalance_df["Yahoo"] = rebalance_df["Ticker"].apply(yahoo_ticker)

        name_col = "Navn" if "Navn" in rebalance_df.columns else "Ticker"

        display_rebalance = rebalance_df[
            [
                name_col,
                "Yahoo",
                "Current weight",
                "Suggested weight",
                "Weight change",
                "Market value",
                "Trade DKK",
                "Momentum score",
                "Risk score",
                "Portfolio score",
                "Anbef."
            ]
        ].copy()

        display_rebalance = display_rebalance.rename(
            columns={
                name_col: "Instrument",
                "Current weight": "Aktuel",
                "Suggested weight": "Forslag",
                "Weight change": "Ændring",
                "Market value": "Eksponering",
                "Trade DKK": "Handel",
                "Momentum score": "Momentum",
                "Risk score": "Risiko",
                "Portfolio score": "Score"
            }
        )

        def format_pct_display(value):
            try:
                return f"{float(value) * 100:.1f}%".replace(".", ",")
            except Exception:
                return value

        def format_dkk_display(value):
            try:
                return f"{float(value):,.0f} kr.".replace(",", ".")
            except Exception:
                return value

        def format_score(value):
            try:
                return f"{float(value):.1f}".replace(".", ",")
            except Exception:
                return value

        for col in ["Aktuel", "Forslag", "Ændring"]:
            display_rebalance[col] = display_rebalance[col].apply(format_pct_display)

        for col in ["Eksponering", "Handel"]:
            display_rebalance[col] = display_rebalance[col].apply(format_dkk_display)

        for col in ["Momentum", "Risiko", "Score"]:
            display_rebalance[col] = display_rebalance[col].apply(format_score)

        display_rebalance["_sort"] = rebalance_df["Trade DKK"].abs().values
        display_rebalance = display_rebalance.sort_values("_sort", ascending=False)
        display_rebalance = display_rebalance.drop(columns="_sort")

        st.dataframe(
            display_rebalance,
            use_container_width=True,
            hide_index=True
        )

        # ---------------------------------------------------
        # Top buys / reductions
        # ---------------------------------------------------

        col_buy, col_reduce = st.columns(2)

        with col_buy:
            st.subheader("Top buys")

            top_buys = display_rebalance[
                display_rebalance["Anbef."] == "Øg"
            ].head(5)

            st.dataframe(
                top_buys,
                use_container_width=True,
                hide_index=True
            )

        with col_reduce:
            st.subheader("Top reductions")

            top_reductions = display_rebalance[
                display_rebalance["Anbef."] == "Reducer"
            ].head(5)

            st.dataframe(
                top_reductions,
                use_container_width=True,
                hide_index=True
            )

        # ---------------------------------------------------
        # Risk KPI heatmap
        # ---------------------------------------------------

        st.subheader("Risk KPI heatmap")

        heatmap_df = rebalance_df[
            [
                name_col,
                "Momentum score",
                "Risk score",
                "Portfolio score",
                "Weight %",
                "Suggested weight",
                "Weight change"
            ]
        ].copy()

        heatmap_df = heatmap_df.rename(
            columns={
                name_col: "Instrument",
                "Momentum score": "Momentum",
                "Risk score": "Risiko",
                "Portfolio score": "Score",
                "Weight %": "Aktuel vægt",
                "Suggested weight": "Forslag",
                "Weight change": "Ændring"
            }
        )

        heatmap_df = heatmap_df.sort_values("Score", ascending=False)

        fig_heatmap = px.imshow(
            heatmap_df[
                [
                    "Momentum",
                    "Risiko",
                    "Score",
                    "Aktuel vægt",
                    "Forslag",
                    "Ændring"
                ]
            ],
            x=[
                "Momentum",
                "Risiko",
                "Score",
                "Aktuel vægt",
                "Forslag",
                "Ændring"
            ],
            y=heatmap_df["Instrument"],
            aspect="auto",
            text_auto=".2f"
        )

        fig_heatmap.update_layout(
            xaxis_title="KPI",
            yaxis_title="Aktie"
        )

        st.plotly_chart(fig_heatmap, use_container_width=True)

        # ---------------------------------------------------
        # Sektorfordeling
        # ---------------------------------------------------

        st.subheader("Sektorfordeling")

        sector_df = (
            df.groupby("Sektor", as_index=False)["Market value"]
            .sum()
            .sort_values("Market value", ascending=False)
        )

        fig_sector = px.pie(
            sector_df,
            names="Sektor",
            values="Market value"
        )

        st.plotly_chart(fig_sector, use_container_width=True)

else:
    st.info("Upload din AI_Stock.xlsx for at starte.")

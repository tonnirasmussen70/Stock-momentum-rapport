import streamlit as st
import pandas as pd
import plotly.express as px

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

    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        st.error(f"Mangler kolonner: {missing_cols}")

    else:
        # Brug Beholdning som korrekt markedsværdi i DKK
        df["Market value"] = df["Beholdning"]

        # Cost value beregnes ud fra markedsværdi og gevinst %
        df["Cost value"] = df["Market value"] / (1 + df["Gevinst"])

        # Gevinst/tab i DKK
        df["Gain/Loss"] = df["Market value"] - df["Cost value"]

        # Afkast %
        df["Return %"] = df["Gain/Loss"] / df["Cost value"]

        # Porteføljevægt
        df["Weight %"] = df["Market value"] / df["Market value"].sum()

        # Samlede KPI'er
        total_value = df["Market value"].sum()
        total_cost = df["Cost value"].sum()
        total_gain = total_value - total_cost
        total_return = total_gain / total_cost

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Porteføljeværdi", f"{total_value:,.0f}".replace(",", "."))
        col2.metric("Gevinst/tab", f"{total_gain:,.0f}".replace(",", "."))
        col3.metric("Afkast %", f"{total_return:.1%}".replace(".", ","))
        col4.metric("Antal aktier", len(df))

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

        display_df = display_df.drop(
            columns=[
                col for col in ["Market value", "Cost value"]
                if col in display_df.columns
            ],
            errors="ignore"
        )

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

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

        st.subheader("Rebalanceringsforslag")

        rebalance_df = df.copy()

        # Hvis Target weight mangler eller er tom, bruges equal weight som fallback
        if "Target weight" not in rebalance_df.columns:
            rebalance_df["Target weight"] = 1 / len(rebalance_df)

        # Rens Target weight
        rebalance_df["Target weight"] = rebalance_df["Target weight"].replace(
            ["None", "none", "", "-", None],
            pd.NA
        )

        # Hvis Target weight er angivet som fx 7,5 eller 7.5, tolkes det som %
        rebalance_df["Target weight"] = pd.to_numeric(
            rebalance_df["Target weight"],
            errors="coerce"
        )

        # Hvis target weight er større end 1, antages det at være procent
        rebalance_df["Target weight"] = rebalance_df["Target weight"].apply(
            lambda x: x / 100 if pd.notna(x) and x > 1 else x
        )

        # Hvis der stadig mangler target, bruges equal weight
        rebalance_df["Target weight"] = rebalance_df["Target weight"].fillna(
            1 / len(rebalance_df)
        )

        # Normaliser target weights så de summerer til 100%
        rebalance_df["Target weight"] = (
            rebalance_df["Target weight"] / rebalance_df["Target weight"].sum()
        )

        # Beregninger
        rebalance_df["Current weight"] = rebalance_df["Weight %"]
        rebalance_df["Target value"] = rebalance_df["Target weight"] * total_value
        rebalance_df["Trade DKK"] = rebalance_df["Target value"] - rebalance_df["Market value"]
        rebalance_df["Change %"] = rebalance_df["Target weight"] - rebalance_df["Current weight"]

        def get_recommendation(trade_value):
            if trade_value > total_value * 0.01:
                return "Øg"
            elif trade_value < -total_value * 0.01:
                return "Reducer"
            else:
                return "Hold"

        rebalance_df["Anbef."] = rebalance_df["Trade DKK"].apply(get_recommendation)

        # Yahoo ticker mapping
        def yahoo_ticker(ticker):
            try:
                ticker = str(ticker)
                mapping = {
                    "XCSE": ".CO",
                    "XSTO": ".ST",
                    "XAMS": ".AS",
                    "XETR": ".DE",
                    "XNYSE": "",
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

        # Vælg kolonnenavn
        name_col = "Navn" if "Navn" in rebalance_df.columns else "Ticker"

        display_rebalance = rebalance_df[
            [
                name_col,
                "Yahoo",
                "Current weight",
                "Target weight",
                "Change %",
                "Market value",
                "Trade DKK",
                "Anbef."
            ]
        ].copy()

        display_rebalance = display_rebalance.rename(
            columns={
                name_col: "Instrument",
                "Current weight": "Aktuel",
                "Target weight": "Mål",
                "Change %": "Ændring",
                "Market value": "Eksponering",
                "Trade DKK": "Handel"
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

        for col in ["Aktuel", "Mål", "Ændring"]:
            display_rebalance[col] = display_rebalance[col].apply(format_pct_display)

        for col in ["Eksponering", "Handel"]:
            display_rebalance[col] = display_rebalance[col].apply(format_dkk_display)

        # Sortér efter største handelsbehov
        display_rebalance["_sort"] = rebalance_df["Trade DKK"].abs().values
        display_rebalance = display_rebalance.sort_values("_sort", ascending=False)
        display_rebalance = display_rebalance.drop(columns="_sort")

        st.dataframe(
            display_rebalance,
            use_container_width=True,
            hide_index=True
        )
        
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

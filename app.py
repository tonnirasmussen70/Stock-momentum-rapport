import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="Stock Portfolio Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Stock Portfolio Dashboard")

uploaded_file = st.file_uploader("Upload stock portfolio Excel-fil", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    required_cols = ["Ticker", "Navn", "Antal", "Købskurs", "Aktuel kurs", "Sektor", "Target weight"]

    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        st.error(f"Mangler kolonner: {missing_cols}")
    else:
        df["Market value"] = df["Beholdning"]
        df["Cost value"] = df["Antal"] * df["Købskurs"]
        df["Gain/Loss"] = df["Market value"] - df["Cost value"]
        df["Return %"] = df["Gain/Loss"] / df["Cost value"]
        df["Weight %"] = df["Market value"] / df["Market value"].sum()

        total_value = df["Market value"].sum()
        total_cost = df["Cost value"].sum()
        total_gain = total_value - total_cost
        total_return = total_gain / total_cost

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Porteføljeværdi", f"{total_value:,.0f}")
        col2.metric("Gevinst/tab", f"{total_gain:,.0f}")
        col3.metric("Afkast %", f"{total_return:.1%}")
        col4.metric("Antal aktier", len(df))

        st.subheader("Porteføljeoversigt")

# Lav en visningsversion af tabellen
display_df = df.copy()

# Fjern tekniske beregningskolonner fra visningen
columns_to_hide = ["Market value", "Cost value"]

display_df = display_df.drop(
    columns=[col for col in columns_to_hide if col in display_df.columns],
    errors="ignore"
)

# Vis pæn formatteret tabel
st.dataframe(
    display_df,
    use_container_width=True,
    column_config={
        "Købskurs": st.column_config.NumberColumn(
            "Købskurs",
            format="%.0f"
        ),
        "Aktuel kurs": st.column_config.NumberColumn(
            "Aktuel kurs",
            format="%.0f"
        ),
        "Beholdning": st.column_config.NumberColumn(
            "Beholdning",
            format="%d"
        ),
        "Gevinst": st.column_config.NumberColumn(
            "Gevinst",
            format="%.1f%%"
        ),
        "Gain/Loss": st.column_config.NumberColumn(
            "Gain/Loss",
            format="%d"
        ),
        "Return %": st.column_config.NumberColumn(
            "Return %",
            format="%.1f%%"
        ),
        "Weight %": st.column_config.NumberColumn(
            "Weight %",
            format="%.1f%%"
        ),
    }
)

        st.subheader("Vægtning pr. aktie")
        fig = px.bar(
            df.sort_values("Weight %", ascending=False),
            x="Navn",
            y="Weight %",
            text=df["Weight %"].apply(lambda x: f"{x:.1%}")
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Sektorfordeling")
        sector_df = df.groupby("Sektor")["Market value"].sum().reset_index()
        fig2 = px.pie(
            sector_df,
            names="Sektor",
            values="Market value"
        )
        st.plotly_chart(fig2, use_container_width=True)

else:
    st.info("Upload din stock_portfolio.xlsx for at starte.")

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

# ---------------------------------------------------
# Datakilde
# ---------------------------------------------------

st.sidebar.header("Datakilde")

data_mode = st.sidebar.radio(
    "Vælg datakilde",
    ["Automatisk fra repository", "Manuel upload"]
)

if data_mode == "Manuel upload":
    uploaded_file = st.sidebar.file_uploader(
        "Upload AI_Stock.xlsx",
        type=["xlsx"]
    )

    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)
    else:
        st.warning("Upload en Excel-fil for at starte.")
        st.stop()
else:
    try:
        df = pd.read_excel("AI_Stock.xlsx")
    except Exception as e:
        st.error("Kunne ikke finde eller læse AI_Stock.xlsx i repository.")
        st.exception(e)
        st.stop()

# ---------------------------------------------------
# Kontrol af kolonner
# ---------------------------------------------------

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
    st.stop()

# ---------------------------------------------------
# Hjælpefunktioner
# ---------------------------------------------------

def yahoo_ticker(ticker):
    try:
        ticker = str(ticker).strip()
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
            return symbol.strip() + mapping.get(exchange.strip(), "")

        return ticker

    except Exception:
        return ticker


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


def format_pct_from_percent(value):
    try:
        return f"{float(value):.1f}%".replace(".", ",")
    except Exception:
        return value


def format_number(value):
    try:
        return f"{float(value):.0f}"
    except Exception:
        return value


def format_score(value):
    try:
        return f"{float(value):.2f}".replace(".", ",")
    except Exception:
        return value


def format_score_1(value):
    try:
        return f"{float(value):.1f}".replace(".", ",")
    except Exception:
        return value


# ---------------------------------------------------
# Grunddata og beregninger
# ---------------------------------------------------

df["Yahoo"] = df["Ticker"].apply(yahoo_ticker)

df["Market value"] = df["Beholdning"]
df["Cost value"] = df["Market value"] / (1 + df["Gevinst"])
df["Gain/Loss"] = df["Market value"] - df["Cost value"]
df["Return %"] = df["Gain/Loss"] / df["Cost value"]
df["Weight %"] = df["Market value"] / df["Market value"].sum()

total_value = df["Market value"].sum()

# ---------------------------------------------------
# Historiske kurser
# ---------------------------------------------------

@st.cache_data(ttl=3600)
def download_prices(tickers, period="13mo"):
    price_data = yf.download(
        tickers,
        period=period,
        auto_adjust=True,
        progress=False,
        group_by="column"
    )["Close"]

    if isinstance(price_data, pd.Series):
        price_data = price_data.to_frame(name=tickers[0])

    price_data = price_data.dropna(how="all")

    return price_data


# ---------------------------------------------------
# Momentum 1/3/6/12 måneder
# ---------------------------------------------------

def calculate_momentum(dataframe):
    try:
        tickers = dataframe["Yahoo"].dropna().unique().tolist()

        if len(tickers) == 0:
            return pd.DataFrame(columns=[
                "Yahoo",
                "MOM 1M",
                "MOM 3M",
                "MOM 6M",
                "MOM 12M",
                "Momentum composite"
            ])

        price_data = download_prices(tickers, period="13mo")

        if price_data.empty:
            return pd.DataFrame(columns=[
                "Yahoo",
                "MOM 1M",
                "MOM 3M",
                "MOM 6M",
                "MOM 12M",
                "Momentum composite"
            ])

        price_data = price_data.ffill().dropna(how="all")

        latest = price_data.iloc[-1]

        def calc_return(days):
            if len(price_data) > days:
                return latest / price_data.iloc[-days] - 1
            else:
                return np.nan

        momentum_df = pd.DataFrame(index=price_data.columns)
        momentum_df["MOM 1M"] = calc_return(21)
        momentum_df["MOM 3M"] = calc_return(63)
        momentum_df["MOM 6M"] = calc_return(126)
        momentum_df["MOM 12M"] = calc_return(252)

        # Vægtning efter momentumrapport-princip:
        # 3M og 6M vægtes højest, 1M bruges som tidlig trend, 12M som langsigtet filter.
        momentum_df["Momentum composite"] = (
            momentum_df["MOM 1M"] * 0.15
            + momentum_df["MOM 3M"] * 0.25
            + momentum_df["MOM 6M"] * 0.30
            + momentum_df["MOM 12M"] * 0.20
        )

        momentum_df = momentum_df.reset_index()

        # Robust navngivning af første kolonne, uanset om pandas/yfinance kalder den index, Date eller noget andet.
        first_col = momentum_df.columns[0]
        momentum_df = momentum_df.rename(columns={first_col: "Yahoo"})

        return momentum_df

    except Exception:
        return pd.DataFrame(columns=[
            "Yahoo",
            "MOM 1M",
            "MOM 3M",
            "MOM 6M",
            "MOM 12M",
            "Momentum composite"
        ])


momentum_df = calculate_momentum(df)

# Robust fallback:
# Hvis Yahoo/yfinance ikke returnerer en korrekt momentumtabel, oprettes en tom tabel
# med de nødvendige kolonner, så app'en ikke crasher på merge.
required_momentum_cols = [
    "Yahoo",
    "MOM 1M",
    "MOM 3M",
    "MOM 6M",
    "MOM 12M",
    "Momentum composite"
]

if momentum_df is None or momentum_df.empty or "Yahoo" not in momentum_df.columns:
    momentum_df = pd.DataFrame(columns=required_momentum_cols)

for col in required_momentum_cols:
    if col not in momentum_df.columns:
        momentum_df[col] = np.nan

momentum_df = momentum_df[required_momentum_cols]

df = df.merge(momentum_df, on="Yahoo", how="left")

# Fallback hvis Yahoo ikke leverer data:
# Brug Gevinst-kolonnen som midlertidig proxy, så app'en stadig virker.
for col in ["MOM 1M", "MOM 3M", "MOM 6M", "MOM 12M", "Momentum composite"]:
    if col not in df.columns:
        df[col] = np.nan

df["Momentum composite"] = df["Momentum composite"].fillna(df["Gevinst"])

# ---------------------------------------------------
# Sharpe / Sortino
# ---------------------------------------------------

def calculate_sharpe_sortino(dataframe, period="1y", risk_free_rate=0.02):
    try:
        tickers = dataframe["Yahoo"].dropna().unique().tolist()

        if len(tickers) == 0:
            return None, None

        price_data = download_prices(tickers, period=period)
        daily_returns = price_data.pct_change().dropna()

        if daily_returns.empty:
            return None, None

        weights = (
            dataframe.groupby("Yahoo")["Market value"].sum()
            / dataframe["Market value"].sum()
        )

        weights = weights.reindex(daily_returns.columns).fillna(0)

        portfolio_returns = daily_returns.dot(weights)

        mean_daily_return = portfolio_returns.mean()
        daily_volatility = portfolio_returns.std()

        downside_returns = portfolio_returns[portfolio_returns < 0]
        downside_volatility = downside_returns.std()

        annual_return = mean_daily_return * 252
        annual_volatility = daily_volatility * np.sqrt(252)
        annual_downside_volatility = downside_volatility * np.sqrt(252)

        if annual_volatility == 0 or pd.isna(annual_volatility):
            sharpe = None
        else:
            sharpe = (annual_return - risk_free_rate) / annual_volatility

        if annual_downside_volatility == 0 or pd.isna(annual_downside_volatility):
            sortino = None
        else:
            sortino = (annual_return - risk_free_rate) / annual_downside_volatility

        return sharpe, sortino

    except Exception:
        return None, None


sharpe_score, sortino_score = calculate_sharpe_sortino(df)

# ---------------------------------------------------
# KPI'er
# ---------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric("Porteføljeværdi", format_dkk(total_value))

if sharpe_score is not None:
    col2.metric("Sharpe score", format_score(sharpe_score))
else:
    col2.metric("Sharpe score", "N/A")

if sortino_score is not None:
    col3.metric("Sortino score", format_score(sortino_score))
else:
    col3.metric("Sortino score", "N/A")

col4.metric("Antal aktier", len(df))

# ---------------------------------------------------
# Momentum-lignende scoringmodel
# ---------------------------------------------------

df["Current weight"] = df["Weight %"]


def momentum_score(value):
    try:
        value = float(value)

        if value >= 0.25:
            return 5
        elif value >= 0.10:
            return 4
        elif value >= 0.00:
            return 3
        elif value >= -0.10:
            return 2
        else:
            return 1
    except Exception:
        return 2


df["Momentum score"] = df["Momentum composite"].apply(momentum_score)


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

# Risiko-score:
# Jo højere score, jo større risikobelastning.
df["Risk score"] = (
    df["Concentration risk"] * 0.50
    + df["Stock risk"] * 0.35
    + (6 - df["Momentum score"]) * 0.15
)

# Samlet score:
# Momentum driver kapital mod stærke aktier.
# Risiko trækker ned.
df["Portfolio score"] = (
    df["Momentum score"] * 0.70
    + (6 - df["Risk score"]) * 0.30
)

df["Portfolio score"] = df["Portfolio score"].clip(lower=0.5)

df["Suggested weight"] = df["Portfolio score"] / df["Portfolio score"].sum()

min_weight = 0.02
max_weight = 0.12

df["Suggested weight"] = df["Suggested weight"].clip(
    lower=min_weight,
    upper=max_weight
)

df["Suggested weight"] = df["Suggested weight"] / df["Suggested weight"].sum()

df["Suggested value"] = df["Suggested weight"] * total_value
df["Trade DKK"] = df["Suggested value"] - df["Market value"]
df["Weight change"] = df["Suggested weight"] - df["Current weight"]

# ---------------------------------------------------
# Porteføljeoversigt
# ---------------------------------------------------

st.subheader("Porteføljeoversigt")

display_df = df.copy()

for col in ["Købskurs", "Aktuel kurs"]:
    if col in display_df.columns:
        display_df[col] = display_df[col].apply(format_number)

for col in ["Beholdning", "Gain/Loss"]:
    if col in display_df.columns:
        display_df[col] = display_df[col].apply(format_dkk)

for col in ["Gevinst", "Return %", "Weight %", "MOM 1M", "MOM 3M", "MOM 6M", "MOM 12M"]:
    if col in display_df.columns:
        display_df[col] = display_df[col].apply(format_pct)

columns_to_hide = [
    "Yahoo",
    "Market value",
    "Cost value",
    "Current weight",
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
display_df = display_df[existing_cols]

if "Momentum composite" in display_df.columns:
    display_df["Momentum composite"] = display_df["Momentum composite"].apply(format_pct)

if "Momentum score" in display_df.columns:
    display_df["Momentum score"] = display_df["Momentum score"].apply(format_score_1)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    height=550

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
# Momentum overview
# ---------------------------------------------------

st.subheader("Momentum 1/3/6/12 måneder")

momentum_view = df.copy()
name_col = "Navn" if "Navn" in momentum_view.columns else "Ticker"

momentum_view = momentum_view[
    [
        name_col,
        "Ticker",
        "MOM 1M",
        "MOM 3M",
        "MOM 6M",
        "MOM 12M",
        "Momentum composite",
        "Momentum score"
    ]
].copy()

momentum_view = momentum_view.rename(
    columns={
        name_col: "Instrument",
        "Momentum composite": "Momentum samlet",
        "Momentum score": "Score"
    }
)

momentum_view = momentum_view.sort_values("Momentum samlet", ascending=False)

momentum_display = momentum_view.copy()

for col in ["MOM 1M", "MOM 3M", "MOM 6M", "MOM 12M", "Momentum samlet"]:
    momentum_display[col] = momentum_display[col].apply(format_pct)

momentum_display["Score"] = momentum_display["Score"].apply(format_score_1)

st.dataframe(
    momentum_display,
    use_container_width=True,
    hide_index=True
)

momentum_chart_df = momentum_view.copy()
momentum_chart_df["Momentum samlet"] = momentum_chart_df["Momentum samlet"] * 100

fig_momentum = px.bar(
    momentum_chart_df,
    x="Instrument",
    y="Momentum samlet",
    text=momentum_chart_df["Momentum samlet"].apply(lambda x: f"{x:.1f}%".replace(".", ",")),
    title="Samlet momentum-score baseret på 1/3/6/12M"
)

fig_momentum.update_traces(
    textposition="outside"
)

fig_momentum.update_layout(
    xaxis_title="Aktie",
    yaxis_title="Momentum samlet (%)",
    xaxis_tickangle=-45,
    uniformtext_minsize=9,
    uniformtext_mode="show"
)

st.plotly_chart(fig_momentum, use_container_width=True)

# ---------------------------------------------------
# Rebalanceringsforslag
# ---------------------------------------------------

st.subheader("Rebalanceringsforslag")

rebalance_df = df.copy()


def recommendation(row):
    trade = row["Trade DKK"]
    weight_change = row["Weight change"]
    momentum = row["Momentum score"]

    if trade > total_value * 0.015 and weight_change > 0 and momentum >= 3:
        return "Øg"
    elif trade < -total_value * 0.015 and weight_change < 0:
        return "Reducer"
    else:
        return "Hold"


rebalance_df["Anbef."] = rebalance_df.apply(recommendation, axis=1)

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
        "MOM 1M",
        "MOM 3M",
        "MOM 6M",
        "MOM 12M",
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

for col in ["Aktuel", "Forslag", "Ændring", "MOM 1M", "MOM 3M", "MOM 6M", "MOM 12M"]:
    display_rebalance[col] = display_rebalance[col].apply(format_pct)

for col in ["Eksponering", "Handel"]:
    display_rebalance[col] = display_rebalance[col].apply(
        lambda x: f"{float(x):,.0f} kr.".replace(",", ".")
    )

for col in ["Momentum", "Risiko", "Score"]:
    display_rebalance[col] = display_rebalance[col].apply(
        lambda x: f"{float(x):.1f}".replace(".", ",")
    )

display_rebalance["_sort"] = rebalance_df["Trade DKK"].abs().values
display_rebalance = display_rebalance.sort_values("_sort", ascending=False)
display_rebalance = display_rebalance.drop(columns="_sort")

st.dataframe(
    display_rebalance,
    use_container_width=True,
    hide_index=True
)

# ---------------------------------------------------
# Rebalanceringsgraf
# ---------------------------------------------------

st.subheader("Nuværende vægt vs. foreslået allokering")

allocation_chart_df = rebalance_df.copy()

allocation_chart_df = allocation_chart_df[
    [
        name_col,
        "Current weight",
        "Suggested weight"
    ]
].copy()

allocation_chart_df = allocation_chart_df.rename(
    columns={
        name_col: "Instrument",
        "Current weight": "Nuværende",
        "Suggested weight": "Forslag"
    }
)

allocation_chart_df = allocation_chart_df.sort_values(
    "Nuværende",
    ascending=False
)

allocation_chart_df["Nuværende"] = allocation_chart_df["Nuværende"] * 100
allocation_chart_df["Forslag"] = allocation_chart_df["Forslag"] * 100

allocation_long_df = allocation_chart_df.melt(
    id_vars="Instrument",
    value_vars=["Nuværende", "Forslag"],
    var_name="Type",
    value_name="Porteføljevægt"
)

fig_allocation = px.bar(
    allocation_long_df,
    x="Instrument",
    y="Porteføljevægt",
    color="Type",
    barmode="group",
    text=allocation_long_df["Porteføljevægt"].apply(
        lambda x: f"{x:.1f}%".replace(".", ",")
    ),
    title="Nuværende vægt vs. foreslået allokering"
)

fig_allocation.update_traces(
    textposition="outside"
)

fig_allocation.update_layout(
    xaxis_title="Aktie",
    yaxis_title="Porteføljevægt (%)",
    xaxis_tickangle=-45,
    legend_title_text="",
    uniformtext_minsize=9,
    uniformtext_mode="show"
)

st.plotly_chart(fig_allocation, use_container_width=True)

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

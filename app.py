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
# Indstillinger for momentumrotation
# ---------------------------------------------------

st.sidebar.header("Momentumrotation")

rotation_strength = st.sidebar.selectbox(
    "Rotationsstyrke",
    ["Moderat", "Aggressiv", "Meget aggressiv"],
    index=1,
    help="Højere styrke betyder, at kapital flyttes hårdere mod de stærkeste momentumaktier."
)

rotation_power_map = {
    "Moderat": 2.0,
    "Aggressiv": 3.0,
    "Meget aggressiv": 4.0
}
rotation_power = rotation_power_map[rotation_strength]

max_weight = st.sidebar.slider(
    "Maks. vægt pr. aktie",
    min_value=0.05,
    max_value=0.25,
    value=0.14,
    step=0.01,
    format="%.0f%%"
)

nan_policy = st.sidebar.selectbox(
    "Manglende momentumdata",
    ["Reducer til minimum", "Behold nuværende vægt"],
    index=0,
    help="Aktier uden valide 1/3/6/12M data må ikke få Øg-anbefaling."
)

missing_data_weight = st.sidebar.slider(
    "Minimumsvægt ved manglende data",
    min_value=0.00,
    max_value=0.05,
    value=0.01,
    step=0.005,
    format="%.1f%%"
)

trade_threshold = st.sidebar.slider(
    "Minimum handelssignal",
    min_value=0.005,
    max_value=0.05,
    value=0.015,
    step=0.005,
    format="%.1f%%"
)

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
        if pd.isna(value):
            return "N/A"
        return f"{float(value) * 100:.1f}%".replace(".", ",")
    except Exception:
        return value


def format_pct_from_percent(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.1f}%".replace(".", ",")
    except Exception:
        return value


def format_number(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.0f}"
    except Exception:
        return value


def format_score(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.2f}".replace(".", ",")
    except Exception:
        return value


def format_score_1(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.1f}".replace(".", ",")
    except Exception:
        return value


def format_kr(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):,.0f} kr.".replace(",", ".")
    except Exception:
        return value


# ---------------------------------------------------
# Grunddata og beregninger
# ---------------------------------------------------

df["Yahoo"] = df["Ticker"].apply(yahoo_ticker)

df["Market value"] = pd.to_numeric(df["Beholdning"], errors="coerce").fillna(0)
df["Gevinst"] = pd.to_numeric(df["Gevinst"], errors="coerce").fillna(0)

# Hvis Gevinst ligger som procenttal, fx 12,5 i stedet for 0,125, normaliseres den.
if df["Gevinst"].abs().median() > 2:
    df["Gevinst"] = df["Gevinst"] / 100

df["Cost value"] = np.where(
    1 + df["Gevinst"] != 0,
    df["Market value"] / (1 + df["Gevinst"]),
    np.nan
)
df["Gain/Loss"] = df["Market value"] - df["Cost value"]
df["Return %"] = df["Gain/Loss"] / df["Cost value"]
df["Weight %"] = df["Market value"] / df["Market value"].sum()

total_value = df["Market value"].sum()

if total_value <= 0:
    st.error("Porteføljeværdi er 0 eller ugyldig. Kontroller Beholdning-kolonnen.")
    st.stop()

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
        group_by="column",
        threads=True
    )

    if isinstance(price_data, pd.DataFrame) and "Close" in price_data.columns:
        price_data = price_data["Close"]

    if isinstance(price_data, pd.Series):
        first_name = tickers[0] if isinstance(tickers, list) and tickers else "Ticker"
        price_data = price_data.to_frame(name=first_name)

    if isinstance(price_data, pd.DataFrame):
        price_data = price_data.dropna(how="all")

    return price_data


# ---------------------------------------------------
# Momentum 1/3/6/12 måneder
# ---------------------------------------------------

def calculate_momentum(dataframe):
    empty_cols = [
        "Yahoo",
        "MOM 1M",
        "MOM 3M",
        "MOM 6M",
        "MOM 12M",
        "Momentum raw",
        "Momentum composite"
    ]

    try:
        tickers = dataframe["Yahoo"].dropna().unique().tolist()

        if len(tickers) == 0:
            return pd.DataFrame(columns=empty_cols)

        price_data = download_prices(tickers, period="13mo")

        if price_data is None or price_data.empty:
            return pd.DataFrame(columns=empty_cols)

        price_data = price_data.ffill().dropna(how="all")
        latest = price_data.iloc[-1]

        def calc_return(days):
            if len(price_data) > days:
                return latest / price_data.iloc[-days] - 1
            return pd.Series(np.nan, index=price_data.columns)

        momentum_df = pd.DataFrame(index=price_data.columns)
        momentum_df["MOM 1M"] = calc_return(21)
        momentum_df["MOM 3M"] = calc_return(63)
        momentum_df["MOM 6M"] = calc_return(126)
        momentum_df["MOM 12M"] = calc_return(252)

        # Momentum vægtning:
        # 12M og 6M vægtes højest, fordi de bedst fanger den større trend.
        # 1M og 3M bruges som trendvending / acceleration.
        momentum_df["Momentum raw"] = (
            momentum_df["MOM 1M"] * 0.10
            + momentum_df["MOM 3M"] * 0.25
            + momentum_df["MOM 6M"] * 0.30
            + momentum_df["MOM 12M"] * 0.35
        )

        momentum_df["Momentum composite"] = momentum_df["Momentum raw"].copy()

        # Straf ved kortsigtet trendbrud.
        momentum_df.loc[momentum_df["MOM 1M"] < 0, "Momentum composite"] *= 0.75
        momentum_df.loc[momentum_df["MOM 3M"] < 0, "Momentum composite"] *= 0.65
        momentum_df.loc[momentum_df["MOM 6M"] < 0, "Momentum composite"] *= 0.70

        momentum_df = momentum_df.reset_index()
        first_col = momentum_df.columns[0]
        momentum_df = momentum_df.rename(columns={first_col: "Yahoo"})

        return momentum_df[empty_cols]

    except Exception:
        return pd.DataFrame(columns=empty_cols)


momentum_df = calculate_momentum(df)

required_momentum_cols = [
    "Yahoo",
    "MOM 1M",
    "MOM 3M",
    "MOM 6M",
    "MOM 12M",
    "Momentum raw",
    "Momentum composite"
]

if momentum_df is None or momentum_df.empty or "Yahoo" not in momentum_df.columns:
    momentum_df = pd.DataFrame(columns=required_momentum_cols)

for col in required_momentum_cols:
    if col not in momentum_df.columns:
        momentum_df[col] = np.nan

momentum_df = momentum_df[required_momentum_cols]
df = df.merge(momentum_df, on="Yahoo", how="left")

for col in ["MOM 1M", "MOM 3M", "MOM 6M", "MOM 12M", "Momentum raw", "Momentum composite"]:
    if col not in df.columns:
        df[col] = np.nan

# Valide momentumdata kræver alle 1/3/6/12M afkast.
df["Momentum data valid"] = df[["MOM 1M", "MOM 3M", "MOM 6M", "MOM 12M"]].notna().all(axis=1)

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

        sharpe = None if annual_volatility == 0 or pd.isna(annual_volatility) else (annual_return - risk_free_rate) / annual_volatility
        sortino = None if annual_downside_volatility == 0 or pd.isna(annual_downside_volatility) else (annual_return - risk_free_rate) / annual_downside_volatility

        return sharpe, sortino

    except Exception:
        return None, None


sharpe_score, sortino_score = calculate_sharpe_sortino(df)

# ---------------------------------------------------
# KPI'er
# ---------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric("Porteføljeværdi", format_dkk(total_value))
col2.metric("Sharpe score", format_score(sharpe_score) if sharpe_score is not None else "N/A")
col3.metric("Sortino score", format_score(sortino_score) if sortino_score is not None else "N/A")
col4.metric("Antal aktier", len(df))

# ---------------------------------------------------
# Momentum-fokuseret scoringmodel
# ---------------------------------------------------

df["Current weight"] = df["Weight %"]


def momentum_score_from_row(row):
    if not row["Momentum data valid"] or pd.isna(row["Momentum composite"]):
        return 1

    value = float(row["Momentum composite"])

    if value >= 0.45:
        return 5
    elif value >= 0.25:
        return 4
    elif value >= 0.10:
        return 3
    elif value > 0:
        return 2
    return 1


df["Momentum score"] = df.apply(momentum_score_from_row, axis=1)


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
    return 3


df["Stock risk"] = df["Ticker"].apply(stock_risk_score)

# Risiko-score: højere score = højere risiko.
df["Risk score"] = (
    df["Concentration risk"] * 0.45
    + df["Stock risk"] * 0.35
    + (6 - df["Momentum score"]) * 0.20
)

# Investerbarhed: kun aktier med komplette momentumdata og positivt momentum kan få overvægt.
df["Investable"] = (
    df["Momentum data valid"]
    & df["Momentum composite"].notna()
    & (df["Momentum composite"] > 0)
)

# Allokeringsscore:
# 1) momentum driver modellen
# 2) risiko reducerer kapitalallokering
# 3) score opløftes med power 2/3/4 for at undgå jævn fordeling
risk_adjustment = (6 - df["Risk score"]).clip(lower=0.25) / 5
trend_quality = np.where(
    (df["MOM 1M"] > 0) & (df["MOM 3M"] > 0) & (df["MOM 6M"] > 0) & (df["MOM 12M"] > 0),
    1.15,
    np.where((df["MOM 3M"] > 0) & (df["MOM 6M"] > 0), 1.00, 0.70)
)

df["Allocation base"] = np.where(
    df["Investable"],
    df["Momentum composite"].clip(lower=0) * risk_adjustment * trend_quality,
    0
)

df["Allocation score"] = np.where(
    df["Allocation base"] > 0,
    df["Allocation base"] ** rotation_power,
    0
)

# Portfolio score bruges til visning. Den må ikke alene drive target weight.
df["Portfolio score"] = (
    df["Momentum score"] * 0.65
    + (6 - df["Risk score"]) * 0.35
).clip(lower=0.5)


def cap_and_redistribute(score_series, cap):
    """Normaliserer scores til vægte, capper maks. vægt og redistribuerer resten."""
    scores = pd.Series(score_series).fillna(0).clip(lower=0)
    weights = pd.Series(0.0, index=scores.index)

    if scores.sum() <= 0:
        return weights

    remaining_index = scores.index[scores > 0].tolist()
    remaining_weight = 1.0
    capped = set()

    for _ in range(20):
        if not remaining_index or remaining_weight <= 0:
            break

        sub_scores = scores.loc[remaining_index]
        if sub_scores.sum() <= 0:
            break

        tentative = sub_scores / sub_scores.sum() * remaining_weight
        over_cap = tentative[tentative > cap]

        if over_cap.empty:
            weights.loc[remaining_index] = tentative
            break

        for idx in over_cap.index:
            weights.loc[idx] = cap
            capped.add(idx)

        remaining_weight = 1.0 - weights.sum()
        remaining_index = [idx for idx in remaining_index if idx not in capped]

    # Sikkerhedsnormalisering hvis cap er for lav til antal positioner.
    if weights.sum() > 0:
        weights = weights / weights.sum()

    return weights


# Først reserveres vægt til aktier uden valide momentumdata, afhængigt af policy.
missing_mask = ~df["Momentum data valid"]
reserved_missing_weight = pd.Series(0.0, index=df.index)

if nan_policy == "Behold nuværende vægt":
    reserved_missing_weight.loc[missing_mask] = df.loc[missing_mask, "Current weight"]
else:
    reserved_missing_weight.loc[missing_mask] = missing_data_weight

# Sikring mod at missing-data-reserven ikke overstiger 35% af porteføljen.
if reserved_missing_weight.sum() > 0.35:
    reserved_missing_weight = reserved_missing_weight / reserved_missing_weight.sum() * 0.35

remaining_capital_weight = max(0.0, 1.0 - reserved_missing_weight.sum())

valid_weights = cap_and_redistribute(df["Allocation score"], max_weight)
df["Suggested weight"] = reserved_missing_weight + valid_weights * remaining_capital_weight

# Hvis ingen aktier er investerbare, beholdes nuværende portefølje for ikke at give meningsløse signaler.
if df["Suggested weight"].sum() <= 0:
    df["Suggested weight"] = df["Current weight"]
else:
    df["Suggested weight"] = df["Suggested weight"] / df["Suggested weight"].sum()

# Aktier uden valide data må aldrig få højere vægt end nuværende vægt.
no_data_increase = (~df["Momentum data valid"]) & (df["Suggested weight"] > df["Current weight"])
df.loc[no_data_increase, "Suggested weight"] = df.loc[no_data_increase, "Current weight"]

# Normaliser igen efter datakontrol.
df["Suggested weight"] = df["Suggested weight"] / df["Suggested weight"].sum()

df["Suggested value"] = df["Suggested weight"] * total_value
df["Trade DKK"] = df["Suggested value"] - df["Market value"]
df["Weight change"] = df["Suggested weight"] - df["Current weight"]


def priority_bucket(row):
    if not row["Momentum data valid"]:
        return "Datatjek"
    if row["Momentum composite"] <= 0:
        return "Negativ trend"
    if row["Momentum score"] >= 5 and row["Risk score"] <= 3.0:
        return "Top momentum"
    if row["Momentum score"] >= 4:
        return "Stærk"
    if row["Momentum score"] >= 3:
        return "Neutral+"
    return "Svag"


df["Prioritet"] = df.apply(priority_bucket, axis=1)

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
    "Target weight",
    "Investable",
    "Allocation base",
    "Allocation score",
    "Momentum data valid",
    "Momentum raw"
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
    "Sektor",
    "Prioritet"
]

existing_cols = [col for col in preferred_order if col in display_df.columns]
display_df = display_df[existing_cols]

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
weight_df["Weight label"] = weight_df["Weight %"].apply(lambda x: f"{x:.1%}".replace(".", ","))

fig_weight = px.bar(
    weight_df,
    x="Ticker",
    y="Weight %",
    text="Weight label"
)

fig_weight.update_traces(textposition="outside")
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
        "Momentum score",
        "Momentum data valid",
        "Prioritet"
    ]
].copy()

momentum_view = momentum_view.rename(
    columns={
        name_col: "Instrument",
        "Momentum composite": "Momentum samlet",
        "Momentum score": "Score",
        "Momentum data valid": "Data OK"
    }
)

momentum_view = momentum_view.sort_values("Momentum samlet", ascending=False, na_position="last")
momentum_display = momentum_view.copy()

for col in ["MOM 1M", "MOM 3M", "MOM 6M", "MOM 12M", "Momentum samlet"]:
    momentum_display[col] = momentum_display[col].apply(format_pct)

momentum_display["Score"] = momentum_display["Score"].apply(format_score_1)
momentum_display["Data OK"] = momentum_display["Data OK"].map({True: "Ja", False: "Nej"})

st.dataframe(
    momentum_display,
    use_container_width=True,
    hide_index=True,
    height=550
)

momentum_chart_df = momentum_view.copy()
momentum_chart_df["Momentum samlet"] = momentum_chart_df["Momentum samlet"] * 100
momentum_chart_df = momentum_chart_df.dropna(subset=["Momentum samlet"])

fig_momentum = px.bar(
    momentum_chart_df,
    x="Instrument",
    y="Momentum samlet",
    text=momentum_chart_df["Momentum samlet"].apply(lambda x: f"{x:.1f}%".replace(".", ",")),
    color="Prioritet",
    title="Samlet momentum baseret på 1/3/6/12M"
)

fig_momentum.update_traces(textposition="outside")
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

st.caption(
    "Modellen bruger momentumrotation: stærke 1/3/6/12M trends får kapital, svage/negative trends reduceres, og aktier uden valide data kan ikke få Øg-anbefaling."
)

rebalance_df = df.copy()


def recommendation(row):
    trade = row["Trade DKK"]
    weight_change = row["Weight change"]
    momentum = row["Momentum score"]
    data_ok = row["Momentum data valid"]
    investable = row["Investable"]

    if not data_ok:
        if trade < -total_value * trade_threshold:
            return "Reducer / datatjek"
        return "Hold / datatjek"

    if not investable:
        if trade < -total_value * trade_threshold:
            return "Reducer"
        return "Hold"

    if trade > total_value * trade_threshold and weight_change > 0 and momentum >= 3:
        return "Øg"
    elif trade < -total_value * trade_threshold and weight_change < 0:
        return "Reducer"
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
        "Prioritet",
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
    display_rebalance[col] = display_rebalance[col].apply(format_kr)

for col in ["Momentum", "Risiko", "Score"]:
    display_rebalance[col] = display_rebalance[col].apply(format_score_1)

# Sortér efter anbefalet køb først og derefter reduktioner.
display_rebalance["_sort"] = rebalance_df["Suggested weight"].values
display_rebalance = display_rebalance.sort_values("_sort", ascending=False).drop(columns="_sort")

st.dataframe(
    display_rebalance,
    use_container_width=True,
    hide_index=True,
    height=550
)

# ---------------------------------------------------
# Rebalanceringsgraf
# ---------------------------------------------------

st.subheader("Nuværende vægt vs. foreslået momentumallokering")

allocation_chart_df = rebalance_df[
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

allocation_chart_df = allocation_chart_df.sort_values("Forslag", ascending=False)
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
    text=allocation_long_df["Porteføljevægt"].apply(lambda x: f"{x:.1f}%".replace(".", ",")),
    title="Nuværende vægt vs. foreslået momentumallokering"
)

fig_allocation.update_traces(textposition="outside")
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

    top_buys = display_rebalance[display_rebalance["Anbef."] == "Øg"].head(5)

    st.dataframe(
        top_buys,
        use_container_width=True,
        hide_index=True
    )

with col_reduce:
    st.subheader("Top reductions")

    top_reductions = display_rebalance[display_rebalance["Anbef."].str.contains("Reducer", na=False)].head(5)

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
    text_auto=".2f",
    color_continuous_scale="RdYlGn"
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

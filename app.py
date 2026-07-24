import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf

st.set_page_config(
    page_title="Stock Portfolio Dashboard",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Stock Portfolio Dashboard")
st.caption(
    "Porteføljeoverblik, momentum, rebalancering, AI-beslutningsstøtte og risikoheatmap · Version 2026-07-24.6"
)


# =========================================================
# UI-HJÆLPERE
# =========================================================

def zebra_table(dataframe: pd.DataFrame):
    def zebra(row):
        background = "#101826" if row.name % 2 == 0 else "#162033"
        return [f"background-color: {background}"] * len(row)

    return dataframe.style.apply(zebra, axis=1)


def table_height(dataframe: pd.DataFrame, row_px: int = 38, max_height: int = 900):
    return min((len(dataframe) + 1) * row_px, max_height)


def format_dkk(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return value


def format_kr(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):,.0f} kr.".replace(",", ".")
    except (TypeError, ValueError):
        return value


def format_pct(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value) * 100:.1f}%".replace(".", ",")
    except (TypeError, ValueError):
        return value


def format_number(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return value


def format_score(value, decimals=1):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.{decimals}f}".replace(".", ",")
    except (TypeError, ValueError):
        return value


def yahoo_ticker(ticker):
    ticker = str(ticker).strip()
    mapping = {
        "XCSE": ".CO",
        "XSTO": ".ST",
        "XAMS": ".AS",
        "XETR": ".DE",
        "XFRA": ".F",
        "XLON": ".L",
        "XPAR": ".PA",
        "XMIL": ".MI",
        "XNYS": "",
        "XNAS": "",
        "NEOE": ".NE",
        "XTSE": ".TO",
    }

    if ":" in ticker:
        symbol, exchange = ticker.split(":", 1)
        return symbol.strip() + mapping.get(exchange.strip(), "")

    return ticker


# =========================================================
# SIDEBAR OG DATAKILDE
# =========================================================

with st.sidebar:
    st.header("Datakilde")

    data_mode = st.radio(
        "Vælg datakilde",
        ["Automatisk fra repository", "Manuel upload"],
        index=0,
    )

    if data_mode == "Manuel upload":
        uploaded_file = st.file_uploader(
            "Upload AI_Stock.xlsx",
            type=["xlsx", "xls"],
        )
        if uploaded_file is None:
            st.info("Upload AI_Stock.xlsx for at starte.")
            st.stop()
        df = pd.read_excel(uploaded_file)
    else:
        try:
            df = pd.read_excel("AI_Stock.xlsx")
        except Exception as exc:
            st.error("Kunne ikke finde eller læse AI_Stock.xlsx i repository.")
            st.exception(exc)
            st.stop()

    st.divider()
    st.header("Momentumrotation")

    st.subheader("Momentum-vægtning")
    w_1w = st.slider("Vægt 1W", 0.00, 0.60, 0.30, 0.05)
    w_3m = st.slider("Vægt 3M", 0.00, 0.60, 0.25, 0.05)
    w_6m = st.slider("Vægt 6M", 0.00, 0.60, 0.25, 0.05)
    w_12m = st.slider("Vægt 12M", 0.00, 0.60, 0.20, 0.05)

    weight_sum = w_1w + w_3m + w_6m + w_12m
    if weight_sum <= 0:
        st.error("Momentum-vægtene må ikke alle være 0.")
        st.stop()

    w_1w /= weight_sum
    w_3m /= weight_sum
    w_6m /= weight_sum
    w_12m /= weight_sum

    st.caption(
        f"Normaliseret: 1W {w_1w:.0%} · 3M {w_3m:.0%} · "
        f"6M {w_6m:.0%} · 12M {w_12m:.0%}"
    )

    rotation_strength = st.selectbox(
        "Rotationsstyrke",
        ["Moderat", "Aggressiv", "Meget aggressiv"],
        index=1,
    )
    rotation_power = {
        "Moderat": 1.5,
        "Aggressiv": 2.25,
        "Meget aggressiv": 3.0,
    }[rotation_strength]

    max_weight = st.slider(
        "Maks. vægt pr. aktie",
        min_value=0.05,
        max_value=0.25,
        value=0.14,
        step=0.01,
        format="%.2f",
    )

    trade_threshold = st.slider(
        "Minimum handelssignal",
        min_value=0.005,
        max_value=0.05,
        value=0.015,
        step=0.005,
        format="%.3f",
    )

    missing_data_policy = st.selectbox(
        "Manglende momentumdata",
        ["Behold nuværende vægt", "Reducer til minimum"],
        index=0,
    )

    missing_data_weight = st.slider(
        "Minimumsvægt ved manglende data",
        0.00,
        0.05,
        0.01,
        0.005,
        format="%.3f",
    )

    st.divider()
    benchmark_ticker = st.selectbox(
        "Benchmark",
        ["URTH", "ACWI", "SPY", "QQQ", "^OMXC25"],
        index=0,
        help="Anvendes til relativ styrke og trend.",
    )

    if st.button("🔄 Clear cache og genberegn"):
        st.cache_data.clear()
        st.rerun()


# =========================================================
# DATAKONTROL OG GRUNDBEREGNINGER
# =========================================================

required_cols = [
    "Ticker",
    "Antal",
    "Købskurs",
    "Aktuel kurs",
    "Beholdning",
    "Gevinst",
    "Sektor",
]

missing_cols = [column for column in required_cols if column not in df.columns]
if missing_cols:
    st.error(f"AI_Stock.xlsx mangler kolonner: {missing_cols}")
    st.stop()

df = df.copy()
df["Yahoo"] = df["Ticker"].apply(yahoo_ticker)

# Numeriske grunddata
for numeric_column in ["Antal", "Købskurs", "Aktuel kurs", "Beholdning"]:
    df[numeric_column] = pd.to_numeric(df[numeric_column], errors="coerce")

# Beholdning er autoritativ markedsværdi i DKK fra Excel-filen.
df["Market value"] = df["Beholdning"].fillna(0)

# Afkast beregnes direkte fra købskurs og aktuel kurs.
# Det giver korrekt procentafkast uanset om aktien handles i DKK, SEK, EUR eller USD,
# så længe købskurs og aktuel kurs står i samme handelsvaluta.
df["Return %"] = np.where(
    df["Købskurs"] > 0,
    df["Aktuel kurs"] / df["Købskurs"] - 1,
    np.nan,
)

# Kostpris i DKK estimeres ud fra den aktuelle DKK-markedsværdi og kursforholdet.
# Metoden undgår at blande udenlandske handelskurser direkte med danske kroner.
# Eventuelle historiske valutakursændringer er ikke medregnet.
df["Cost value"] = np.where(
    (df["Aktuel kurs"] > 0) & (df["Købskurs"] > 0),
    df["Market value"] * df["Købskurs"] / df["Aktuel kurs"],
    np.nan,
)

df["Gain/Loss"] = df["Market value"] - df["Cost value"]

total_value = float(df["Market value"].sum())
total_cost = float(df["Cost value"].sum(skipna=True))
total_gain = total_value - total_cost
total_return = total_gain / total_cost if total_cost > 0 else np.nan

if total_value <= 0:
    st.error("Porteføljeværdien er 0. Kontroller kolonnen Beholdning.")
    st.stop()

df["Weight %"] = df["Market value"] / total_value
df["Current weight"] = df["Weight %"]


# =========================================================
# MARKEDSDATA
# =========================================================

@st.cache_data(ttl=3600, show_spinner=False)
def download_prices(tickers, period="18mo"):
    cleaned = [ticker for ticker in tickers if isinstance(ticker, str) and ticker.strip()]
    if not cleaned:
        return pd.DataFrame()

    try:
        prices = yf.download(
            cleaned,
            period=period,
            auto_adjust=True,
            progress=False,
            group_by="column",
            threads=True,
        )

        if isinstance(prices, pd.DataFrame) and "Close" in prices.columns:
            prices = prices["Close"]

        if isinstance(prices, pd.Series):
            prices = prices.to_frame(name=cleaned[0])

        if not isinstance(prices, pd.DataFrame):
            return pd.DataFrame()

        if len(cleaned) == 1 and prices.shape[1] == 1:
            prices.columns = cleaned

        return prices.sort_index().dropna(how="all")
    except Exception:
        return pd.DataFrame()


all_tickers = df["Yahoo"].dropna().astype(str).unique().tolist()
asset_prices = download_prices(all_tickers, period="18mo")
benchmark_prices = download_prices([benchmark_ticker], period="18mo")


def price_series(prices, ticker):
    if prices is None or prices.empty:
        return pd.Series(dtype=float)

    if ticker in prices.columns:
        return prices[ticker].dropna()

    if prices.shape[1] == 1:
        return prices.iloc[:, 0].dropna()

    return pd.Series(dtype=float)


# =========================================================
# MOMENTUM, TREND OG RISIKO
# =========================================================

periods = {
    "MOM 1W": 5,
    "MOM 1M": 21,
    "MOM 3M": 63,
    "MOM 6M": 126,
    "MOM 12M": 252,
}

rows = []

for ticker in all_tickers:
    prices = price_series(asset_prices, ticker)
    row = {"Yahoo": ticker}

    for label, days in periods.items():
        if len(prices) > days:
            row[label] = prices.iloc[-1] / prices.iloc[-(days + 1)] - 1
        else:
            row[label] = np.nan

    returns = prices.pct_change().dropna()

    row["Volatility"] = (
        returns.std() * np.sqrt(252)
        if len(returns) >= 20
        else np.nan
    )

    if len(prices) >= 20:
        rolling_peak = prices.cummax()
        drawdown = prices / rolling_peak - 1
        row["Max drawdown"] = drawdown.min()
    else:
        row["Max drawdown"] = np.nan

    ma50 = prices.rolling(50).mean().iloc[-1] if len(prices) >= 50 else np.nan
    ma200_period = 200 if len(prices) >= 200 else 100
    ma200 = (
        prices.rolling(ma200_period).mean().iloc[-1]
        if len(prices) >= ma200_period
        else np.nan
    )

    latest = prices.iloc[-1] if not prices.empty else np.nan
    row["Above MA50"] = bool(latest > ma50) if pd.notna(ma50) else False
    row["MA50 above MA200"] = bool(ma50 > ma200) if pd.notna(ma50) and pd.notna(ma200) else False

    rows.append(row)

analytics = pd.DataFrame(rows)
if analytics.empty:
    analytics = pd.DataFrame(columns=["Yahoo", *periods.keys()])

df = df.merge(analytics, on="Yahoo", how="left")

for column in [
    "MOM 1W", "MOM 1M", "MOM 3M", "MOM 6M", "MOM 12M",
    "Volatility", "Max drawdown",
]:
    if column not in df.columns:
        df[column] = np.nan

df["Momentum composite"] = (
    df["MOM 1W"].fillna(0) * w_1w
    + df["MOM 3M"].fillna(0) * w_3m
    + df["MOM 6M"].fillna(0) * w_6m
    + df["MOM 12M"].fillna(0) * w_12m
)

df["Momentum data valid"] = df[
    ["MOM 1W", "MOM 3M", "MOM 6M", "MOM 12M"]
].notna().all(axis=1)

benchmark_series = price_series(benchmark_prices, benchmark_ticker)


def benchmark_return(days):
    if len(benchmark_series) <= days:
        return np.nan
    return benchmark_series.iloc[-1] / benchmark_series.iloc[-(days + 1)] - 1


benchmark_3m = benchmark_return(63)
benchmark_6m = benchmark_return(126)

df["Relative strength"] = (
    0.55 * (df["MOM 3M"] - benchmark_3m)
    + 0.45 * (df["MOM 6M"] - benchmark_6m)
)


def momentum_score(value):
    if pd.isna(value):
        return 1.0
    return float(np.clip((value + 0.10) / 0.50 * 4 + 1, 1, 5))


df["Momentum score"] = df["Momentum composite"].apply(momentum_score)


def concentration_risk(weight):
    return float(np.clip(weight / max(max_weight, 0.01) * 5, 1, 5))


df["Concentration risk"] = df["Current weight"].apply(concentration_risk)

volatility_risk = (
    df["Volatility"].fillna(0.30) / 0.60 * 5
).clip(1, 5)

drawdown_risk = (
    df["Max drawdown"].abs().fillna(0.20) / 0.50 * 5
).clip(1, 5)

df["Risk score"] = (
    0.40 * df["Concentration risk"]
    + 0.35 * volatility_risk
    + 0.25 * drawdown_risk
).clip(1, 5)

df["Portfolio score"] = (
    0.65 * df["Momentum score"]
    + 0.35 * (6 - df["Risk score"])
).clip(0, 5)


# =========================================================
# PORTEFØLJEAFKAST, SHARPE OG SORTINO
# =========================================================

def portfolio_daily_returns(dataframe, prices):
    if prices is None or prices.empty:
        return pd.Series(dtype=float)

    returns = prices.pct_change().dropna(how="all")
    weights = dataframe.groupby("Yahoo")["Market value"].sum()
    weights = weights / weights.sum()
    weights = weights.reindex(returns.columns).fillna(0)

    valid_columns = weights[weights > 0].index.intersection(returns.columns)
    if len(valid_columns) == 0:
        return pd.Series(dtype=float)

    aligned_returns = returns[valid_columns].fillna(0)
    aligned_weights = weights.reindex(valid_columns)
    aligned_weights = aligned_weights / aligned_weights.sum()

    return aligned_returns.dot(aligned_weights)


portfolio_returns = portfolio_daily_returns(df, asset_prices)

if len(portfolio_returns) >= 20:
    annual_return = portfolio_returns.mean() * 252
    annual_volatility = portfolio_returns.std() * np.sqrt(252)
    downside = portfolio_returns[portfolio_returns < 0]
    downside_volatility = downside.std() * np.sqrt(252) if not downside.empty else np.nan

    sharpe_score = (
        (annual_return - 0.02) / annual_volatility
        if annual_volatility > 0
        else np.nan
    )
    sortino_score = (
        (annual_return - 0.02) / downside_volatility
        if pd.notna(downside_volatility) and downside_volatility > 0
        else np.nan
    )

    portfolio_curve = (1 + portfolio_returns).cumprod()
    portfolio_drawdown = portfolio_curve / portfolio_curve.cummax() - 1
    portfolio_max_drawdown = portfolio_drawdown.min()
else:
    annual_return = np.nan
    annual_volatility = np.nan
    sharpe_score = np.nan
    sortino_score = np.nan
    portfolio_max_drawdown = np.nan


# =========================================================
# REBALANCERING
# =========================================================

df["Investable"] = (
    df["Momentum data valid"]
    & (df["Momentum composite"] > 0)
    & (df["MOM 1W"] > -0.05)
)

trend_quality = np.select(
    [
        (df["MOM 1W"] > 0) & (df["MOM 3M"] > 0) & (df["MOM 6M"] > 0) & (df["MOM 12M"] > 0),
        (df["MOM 3M"] > 0) & (df["MOM 6M"] > 0),
    ],
    [1.20, 1.00],
    default=0.65,
)

risk_adjustment = (6 - df["Risk score"]).clip(lower=0.5) / 5
relative_strength_factor = (
    1 + df["Relative strength"].fillna(0).clip(-0.25, 0.25)
)

df["Allocation base"] = np.where(
    df["Investable"],
    df["Momentum composite"].clip(lower=0)
    * trend_quality
    * risk_adjustment
    * relative_strength_factor,
    0,
)

df["Allocation score"] = np.where(
    df["Allocation base"] > 0,
    df["Allocation base"] ** rotation_power,
    0,
)


def cap_and_redistribute(scores, cap):
    scores = pd.Series(scores, dtype=float).fillna(0).clip(lower=0)
    weights = pd.Series(0.0, index=scores.index)

    active = scores[scores > 0].index.tolist()
    remaining = 1.0

    for _ in range(30):
        if not active or remaining <= 1e-9:
            break

        active_scores = scores.loc[active]
        tentative = active_scores / active_scores.sum() * remaining
        over_cap = tentative[tentative > cap]

        if over_cap.empty:
            weights.loc[active] = tentative
            break

        weights.loc[over_cap.index] = cap
        remaining = max(0.0, 1.0 - weights.sum())
        active = [index for index in active if index not in over_cap.index]

    return weights


missing_mask = ~df["Momentum data valid"]
reserved = pd.Series(0.0, index=df.index)

if missing_data_policy == "Behold nuværende vægt":
    reserved.loc[missing_mask] = df.loc[missing_mask, "Current weight"]
else:
    reserved.loc[missing_mask] = missing_data_weight

if reserved.sum() > 0.35:
    reserved = reserved / reserved.sum() * 0.35

remaining_weight = max(0.0, 1.0 - reserved.sum())
model_weights = cap_and_redistribute(df["Allocation score"], max_weight)

df["Suggested weight"] = reserved + model_weights * remaining_weight

if df["Suggested weight"].sum() <= 0:
    df["Suggested weight"] = df["Current weight"]
else:
    df["Suggested weight"] /= df["Suggested weight"].sum()

no_data_increase = (
    ~df["Momentum data valid"]
    & (df["Suggested weight"] > df["Current weight"])
)
df.loc[no_data_increase, "Suggested weight"] = df.loc[
    no_data_increase, "Current weight"
]

df["Suggested weight"] /= df["Suggested weight"].sum()
df["Suggested value"] = df["Suggested weight"] * total_value
df["Trade DKK"] = df["Suggested value"] - df["Market value"]
df["Weight change"] = df["Suggested weight"] - df["Current weight"]


def recommendation(row):
    threshold_dkk = total_value * trade_threshold

    if not row["Momentum data valid"]:
        return "Reducer / datatjek" if row["Trade DKK"] < -threshold_dkk else "Hold / datatjek"

    if row["Trade DKK"] > threshold_dkk and row["Momentum score"] >= 3:
        return "Øg"

    if row["Trade DKK"] < -threshold_dkk:
        return "Reducer"

    return "Hold"


df["Anbefaling"] = df.apply(recommendation, axis=1)


def priority_bucket(row):
    if not row["Momentum data valid"]:
        return "Datatjek"
    if row["MOM 1W"] < 0 and row["MOM 3M"] > 0:
        return "Kort afmatning"
    if row["Momentum composite"] <= 0:
        return "Negativ trend"
    if row["Momentum score"] >= 4.2 and row["Risk score"] <= 3:
        return "Top momentum"
    if row["Momentum score"] >= 3.4:
        return "Stærk"
    if row["Momentum score"] >= 2.5:
        return "Neutral+"
    return "Svag"


df["Prioritet"] = df.apply(priority_bucket, axis=1)


# =========================================================
# AI CONFIDENCE SCORE
# =========================================================

def minmax_score(value, low, high):
    if pd.isna(value) or high <= low:
        return 0.5
    return float(np.clip((value - low) / (high - low), 0, 1))


benchmark_trend_score = 0.5
if len(benchmark_series) >= 200:
    benchmark_ma50 = benchmark_series.rolling(50).mean().iloc[-1]
    benchmark_ma200 = benchmark_series.rolling(200).mean().iloc[-1]
    benchmark_trend_score = 1.0 if benchmark_ma50 > benchmark_ma200 else 0.25
elif len(benchmark_series) >= 100:
    benchmark_ma50 = benchmark_series.rolling(50).mean().iloc[-1]
    benchmark_ma100 = benchmark_series.rolling(100).mean().iloc[-1]
    benchmark_trend_score = 1.0 if benchmark_ma50 > benchmark_ma100 else 0.25


def confidence_components(row):
    momentum = minmax_score(row["Momentum composite"], -0.15, 0.45)

    trend = (
        0.55 * float(bool(row.get("Above MA50", False)))
        + 0.45 * float(bool(row.get("MA50 above MA200", False)))
    )

    volatility = 1 - minmax_score(row["Volatility"], 0.10, 0.60)
    drawdown = 1 - minmax_score(abs(row["Max drawdown"]), 0.05, 0.50)

    # Kapitalflow er her en transparent markedsdata-proxy:
    # kort acceleration + relativ styrke.
    acceleration = row["MOM 1W"] - (row["MOM 3M"] / 13 if pd.notna(row["MOM 3M"]) else 0)
    capital_flow = (
        0.55 * minmax_score(acceleration, -0.05, 0.05)
        + 0.45 * minmax_score(row["Relative strength"], -0.15, 0.20)
    )

    macro_regime = benchmark_trend_score
    relative_strength = minmax_score(row["Relative strength"], -0.15, 0.20)

    score = (
        0.30 * momentum
        + 0.20 * trend
        + 0.10 * volatility
        + 0.10 * drawdown
        + 0.10 * capital_flow
        + 0.05 * macro_regime
        + 0.15 * relative_strength
    ) * 100

    return pd.Series(
        {
            "AI Confidence": round(score, 1),
            "AI Momentum": momentum * 100,
            "AI Trend": trend * 100,
            "AI Volatility": volatility * 100,
            "AI Drawdown": drawdown * 100,
            "AI Capital flow": capital_flow * 100,
            "AI Makro": macro_regime * 100,
            "AI Relative strength": relative_strength * 100,
        }
    )


confidence_df = df.apply(confidence_components, axis=1)
df = pd.concat([df, confidence_df], axis=1)


def confidence_label(score):
    if pd.isna(score):
        return "Datamangel"
    if score >= 80:
        return "Høj"
    if score >= 65:
        return "Moderat-høj"
    if score >= 50:
        return "Moderat"
    if score >= 35:
        return "Lav"
    return "Meget lav"


df["Confidence niveau"] = df["AI Confidence"].apply(confidence_label)


def portfolio_confidence_label(score):
    if pd.isna(score):
        return "Datamangel"
    if score >= 80:
        return "Meget stærkt signalgrundlag"
    if score >= 70:
        return "Stærkt signalgrundlag"
    if score >= 55:
        return "Blandet / moderat signalgrundlag"
    if score >= 40:
        return "Svagt signalgrundlag"
    return "Meget svagt signalgrundlag"


def build_ai_explanation(row):
    factors = {
        "momentum": row.get("AI Momentum", np.nan),
        "trend": row.get("AI Trend", np.nan),
        "volatilitet": row.get("AI Volatility", np.nan),
        "drawdown": row.get("AI Drawdown", np.nan),
        "kapitalflow": row.get("AI Capital flow", np.nan),
        "makroregime": row.get("AI Makro", np.nan),
        "relativ styrke": row.get("AI Relative strength", np.nan),
    }

    valid = {name: float(value) for name, value in factors.items() if pd.notna(value)}
    if not valid:
        return "Utilstrækkelige data til en forklaring."

    strongest = sorted(valid.items(), key=lambda item: item[1], reverse=True)[:2]
    weakest = sorted(valid.items(), key=lambda item: item[1])[:2]

    strong_text = " og ".join(name for name, _ in strongest)
    weak_text = " og ".join(name for name, _ in weakest)

    confidence = row.get("AI Confidence", np.nan)
    recommendation = row.get("Anbefaling", "Hold")

    if pd.notna(confidence) and confidence >= 80:
        opening = f"{recommendation}: meget stærkt samlet signal"
    elif pd.notna(confidence) and confidence >= 65:
        opening = f"{recommendation}: godt samlet signal"
    elif pd.notna(confidence) and confidence >= 50:
        opening = f"{recommendation}: blandet signalbillede"
    else:
        opening = f"{recommendation}: svagt samlet signal"

    return (
        f"{opening}. Styrkes især af {strong_text}. "
        f"Confidence begrænses især af {weak_text}."
    )


df["AI forklaring"] = df.apply(build_ai_explanation, axis=1)


# =========================================================
# RELATIV TREND OG MONTHLY HEATMAP
# =========================================================

trend_prices = asset_prices.copy()

if not trend_prices.empty:
    monthly_prices = trend_prices.resample("ME").last()
    monthly_returns = monthly_prices.pct_change()

    monthly_index = monthly_returns.add(1).cumprod() * 100
    if not monthly_index.empty:
        monthly_index.iloc[0] = 100

    weights_by_yahoo = df.groupby("Yahoo")["Current weight"].sum()
    trend_columns = monthly_returns.columns.intersection(weights_by_yahoo.index)

    if len(trend_columns) > 0:
        portfolio_monthly_return = (
            monthly_returns[trend_columns]
            .fillna(0)
            .mul(weights_by_yahoo.reindex(trend_columns), axis=1)
            .sum(axis=1)
        )
        portfolio_index = (1 + portfolio_monthly_return).cumprod() * 100
        if not portfolio_index.empty:
            portfolio_index.iloc[0] = 100
        monthly_index["Portefølje"] = portfolio_index
else:
    monthly_returns = pd.DataFrame()
    monthly_index = pd.DataFrame()


# =========================================================
# FANER
# =========================================================

tab_overview, tab_momentum, tab_rebalance, tab_ai, tab_heatmap = st.tabs(
    [
        "1. Overblik",
        "2. Momentum",
        "3. Rebalancering",
        "4. AI Insights",
        "5. Heatmap",
    ]
)


# =========================================================
# FANE 1 – OVERBLIK
# =========================================================

with tab_overview:
    st.subheader("Porteføljeoversigt")

    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6, kpi7 = st.columns(7)
    kpi1.metric("Porteføljeværdi", format_dkk(total_value))
    kpi2.metric("Kostpris", format_dkk(total_cost))
    kpi3.metric("Gevinst/tab", format_dkk(total_gain))
    kpi4.metric("Afkast", format_pct(total_return))
    kpi5.metric("Sharpe", format_score(sharpe_score, 2))
    kpi6.metric("Sortino", format_score(sortino_score, 2))
    kpi7.metric("Antal aktier", len(df))

    st.caption(
        "Afkast beregnes som aktuel kurs / købskurs − 1. Kostpris i DKK estimeres "
        "ud fra Beholdning × købskurs / aktuel kurs. Historiske valutaændringer er ikke medregnet."
    )

    overview = df.copy()

    display_columns = [
        column for column in [
            "Navn",
            "Weight %",
            "Antal",
            "Købskurs",
            "Aktuel kurs",
            "Beholdning",
            "Gain/Loss",
            "Return %",
            "Valuta",
            "Sektor",
            "Prioritet",
        ]
        if column in overview.columns
    ]

    overview = overview[display_columns].copy()

    for column in ["Købskurs", "Aktuel kurs", "Antal"]:
        if column in overview.columns:
            overview[column] = overview[column].apply(format_number)

    for column in ["Beholdning", "Gain/Loss"]:
        if column in overview.columns:
            overview[column] = overview[column].apply(format_dkk)

    for column in ["Weight %", "Return %"]:
        if column in overview.columns:
            overview[column] = overview[column].apply(format_pct)

    st.dataframe(
        zebra_table(overview),
        use_container_width=True,
        hide_index=True,
        height=table_height(overview, max_height=700),
    )

    st.subheader("Vægtning pr. aktie")
    weight_name = "Navn" if "Navn" in df.columns else "Ticker"
    weight_df = df.sort_values("Weight %", ascending=False).copy()
    weight_df["Vægt"] = weight_df["Weight %"] * 100
    weight_df["Label"] = weight_df["Weight %"].apply(
        lambda value: f"{value:.1%}".replace(".", ",")
    )

    fig_weight = px.bar(
        weight_df,
        x=weight_name,
        y="Vægt",
        text="Label",
    )
    fig_weight.update_traces(textposition="outside")
    fig_weight.update_layout(
        xaxis_title="Aktie",
        yaxis_title="Porteføljevægt (%)",
        xaxis_tickangle=-45,
        showlegend=False,
    )
    st.plotly_chart(fig_weight, use_container_width=True)

    st.subheader("Relativ trendudvikling")

    if not monthly_index.empty:
        fig_trend = go.Figure()

        for column in monthly_index.columns:
            fig_trend.add_trace(
                go.Scatter(
                    x=monthly_index.index,
                    y=monthly_index[column],
                    mode="lines",
                    name=column,
                    line=dict(width=4 if column == "Portefølje" else 1.5),
                )
            )

        if not benchmark_series.empty:
            benchmark_monthly = benchmark_series.resample("ME").last()
            benchmark_index = benchmark_monthly / benchmark_monthly.iloc[0] * 100
            fig_trend.add_trace(
                go.Scatter(
                    x=benchmark_index.index,
                    y=benchmark_index,
                    mode="lines",
                    name=f"Benchmark: {benchmark_ticker}",
                    line=dict(width=3, dash="dash"),
                )
            )

        fig_trend.update_layout(
            yaxis_title="Indeks 100",
            xaxis_title="Måned",
            hovermode="x unified",
            height=650,
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.warning("Relativ trendudvikling kunne ikke beregnes.")

    st.subheader("Sektorfordeling")
    sector_df = (
        df.groupby("Sektor", as_index=False)["Market value"]
        .sum()
        .sort_values("Market value", ascending=False)
    )

    fig_sector = px.pie(
        sector_df,
        names="Sektor",
        values="Market value",
        hole=0.45,
    )
    fig_sector.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig_sector, use_container_width=True)


# =========================================================
# FANE 2 – MOMENTUM
# =========================================================

with tab_momentum:
    st.subheader("Momentum 1W, 3M, 6M og 12M")

    momentum_name = "Navn" if "Navn" in df.columns else "Ticker"
    momentum_table = df[
        [
            momentum_name,
            "MOM 1W",
            "MOM 3M",
            "MOM 6M",
            "MOM 12M",
            "Momentum composite",
            "Momentum score",
            "Relative strength",
            "Prioritet",
        ]
    ].copy()

    momentum_table = momentum_table.rename(
        columns={
            momentum_name: "Instrument",
            "Momentum composite": "Samlet momentum",
            "Momentum score": "Momentumscore",
            "Relative strength": "Relativ styrke",
        }
    ).sort_values("Samlet momentum", ascending=False)

    momentum_display = momentum_table.copy()
    for column in [
        "MOM 1W",
        "MOM 3M",
        "MOM 6M",
        "MOM 12M",
        "Samlet momentum",
        "Relativ styrke",
    ]:
        momentum_display[column] = momentum_display[column].apply(format_pct)

    momentum_display["Momentumscore"] = momentum_display["Momentumscore"].apply(
        lambda value: format_score(value, 1)
    )

    st.dataframe(
        zebra_table(momentum_display),
        use_container_width=True,
        hide_index=True,
        height=table_height(momentum_display, max_height=700),
    )

    st.subheader("Samlet momentum baseret på 1W, 3M, 6M og 12M")
    chart_df = momentum_table.dropna(subset=["Samlet momentum"]).copy()
    chart_df["Momentum (%)"] = chart_df["Samlet momentum"] * 100
    chart_df["Label"] = chart_df["Samlet momentum"].apply(
        lambda value: f"{value:.1%}".replace(".", ",")
    )

    fig_momentum = px.bar(
        chart_df,
        x="Instrument",
        y="Momentum (%)",
        text="Label",
    )
    fig_momentum.update_traces(textposition="outside")
    fig_momentum.update_layout(
        xaxis_title="Aktie",
        yaxis_title="Samlet momentum (%)",
        xaxis_tickangle=-45,
        showlegend=False,
    )
    st.plotly_chart(fig_momentum, use_container_width=True)


# =========================================================
# FANE 3 – REBALANCERING
# =========================================================

with tab_rebalance:
    st.subheader("Rebalanceringsforslag")
    st.caption(
        "Momentumallokeringen er risikokorrigeret og begrænset af den valgte maksimumvægt. "
        "Aktier uden valide data kan ikke få en automatisk Øg-anbefaling."
    )

    rebalance_name = "Navn" if "Navn" in df.columns else "Ticker"
    rebalance_table = df[
        [
            rebalance_name,
            "Current weight",
            "Suggested weight",
            "Weight change",
            "Market value",
            "Trade DKK",
            "Momentum composite",
            "Risk score",
            "AI Confidence",
            "Anbefaling",
        ]
    ].copy()

    rebalance_table = rebalance_table.rename(
        columns={
            rebalance_name: "Instrument",
            "Current weight": "Nuværende vægt",
            "Suggested weight": "Foreslået vægt",
            "Weight change": "Ændring",
            "Market value": "Eksponering",
            "Trade DKK": "Handel",
            "Momentum composite": "Momentum",
            "Risk score": "Risiko",
            "AI Confidence": "AI confidence",
        }
    ).sort_values("Foreslået vægt", ascending=False)

    rebalance_display = rebalance_table.copy()

    for column in ["Nuværende vægt", "Foreslået vægt", "Ændring", "Momentum"]:
        rebalance_display[column] = rebalance_display[column].apply(format_pct)

    for column in ["Eksponering", "Handel"]:
        rebalance_display[column] = rebalance_display[column].apply(format_kr)

    rebalance_display["Risiko"] = rebalance_display["Risiko"].apply(
        lambda value: format_score(value, 1)
    )
    rebalance_display["AI confidence"] = rebalance_display["AI confidence"].apply(
        lambda value: f"{format_score(value, 1)}%"
    )

    st.dataframe(
        zebra_table(rebalance_display),
        use_container_width=True,
        hide_index=True,
        height=table_height(rebalance_display, max_height=700),
    )

    st.subheader("Nuværende vægt vs. foreslået momentumallokering")

    allocation_df = rebalance_table[
        ["Instrument", "Nuværende vægt", "Foreslået vægt"]
    ].copy()

    allocation_long = allocation_df.melt(
        id_vars="Instrument",
        value_vars=["Nuværende vægt", "Foreslået vægt"],
        var_name="Type",
        value_name="Vægt",
    )
    allocation_long["Vægt (%)"] = allocation_long["Vægt"] * 100

    fig_allocation = px.bar(
        allocation_long,
        x="Instrument",
        y="Vægt (%)",
        color="Type",
        barmode="group",
        text=allocation_long["Vægt"].apply(
            lambda value: f"{value:.1%}".replace(".", ",")
        ),
    )
    fig_allocation.update_traces(textposition="outside")
    fig_allocation.update_layout(
        xaxis_title="Aktie",
        yaxis_title="Porteføljevægt (%)",
        xaxis_tickangle=-45,
        legend_title_text="",
    )
    st.plotly_chart(fig_allocation, use_container_width=True)

    col_buy, col_reduce = st.columns(2)

    top_columns = [
        "Instrument",
        "Nuværende vægt",
        "Foreslået vægt",
        "Ændring",
        "Handel",
        "Momentum",
        "AI confidence",
        "Anbefaling",
    ]

    with col_buy:
        st.subheader("Top buys")
        top_buys = (
            rebalance_table[rebalance_table["Anbefaling"] == "Øg"]
            .sort_values(["Handel", "AI confidence"], ascending=[False, False])
            .head(5)
            .copy()
        )

        if top_buys.empty:
            st.info("Ingen køb overstiger det valgte handelssignal.")
        else:
            top_buys_display = top_buys[top_columns].copy()
            for column in ["Nuværende vægt", "Foreslået vægt", "Ændring", "Momentum"]:
                top_buys_display[column] = top_buys_display[column].apply(format_pct)
            top_buys_display["Handel"] = top_buys_display["Handel"].apply(format_kr)
            top_buys_display["AI confidence"] = top_buys_display["AI confidence"].apply(
                lambda value: f"{format_score(value, 1)}%"
            )
            st.dataframe(
                zebra_table(top_buys_display),
                use_container_width=True,
                hide_index=True,
            )

    with col_reduce:
        st.subheader("Top reductions")
        top_reductions = (
            rebalance_table[
                rebalance_table["Anbefaling"].str.contains("Reducer", na=False)
            ]
            .sort_values("Handel", ascending=True)
            .head(5)
            .copy()
        )

        if top_reductions.empty:
            st.info("Ingen reduktioner overstiger det valgte handelssignal.")
        else:
            top_reductions_display = top_reductions[top_columns].copy()
            for column in ["Nuværende vægt", "Foreslået vægt", "Ændring", "Momentum"]:
                top_reductions_display[column] = top_reductions_display[column].apply(format_pct)
            top_reductions_display["Handel"] = top_reductions_display["Handel"].apply(format_kr)
            top_reductions_display["AI confidence"] = top_reductions_display["AI confidence"].apply(
                lambda value: f"{format_score(value, 1)}%"
            )
            st.dataframe(
                zebra_table(top_reductions_display),
                use_container_width=True,
                hide_index=True,
            )


# =========================================================
# FANE 4 – AI INSIGHTS
# =========================================================

with tab_ai:
    st.subheader("AI Confidence Score")

    avg_confidence = np.average(
        df["AI Confidence"],
        weights=df["Current weight"],
    )

    high_confidence_count = int((df["AI Confidence"] >= 80).sum())
    buy_count = int((df["Anbefaling"] == "Øg").sum())
    reduce_count = int(df["Anbefaling"].str.contains("Reducer", na=False).sum())

    portfolio_confidence_text = portfolio_confidence_label(avg_confidence)

    ai1, ai2, ai3, ai4 = st.columns(4)
    ai1.metric("Porteføljens confidence", f"{avg_confidence:.0f}%")
    ai2.metric("Høj confidence", high_confidence_count)
    ai3.metric("Købssignaler", buy_count)
    ai4.metric("Reduktionssignaler", reduce_count)

    st.info(
        f"**Fortolkning: {portfolio_confidence_text}.** "
        "Tallet er porteføljevægtet og viser, hvor stærkt de nuværende positioner "
        "understøttes af momentum, trend, risiko, kapitalflow, makroregime og relativ styrke. "
        "Det er ikke sandsynligheden for positivt afkast."
    )

    ai_name = "Navn" if "Navn" in df.columns else "Ticker"
    ai_table = df[
        [
            ai_name,
            "Anbefaling",
            "AI Confidence",
            "Confidence niveau",
            "AI Momentum",
            "AI Trend",
            "AI Volatility",
            "AI Drawdown",
            "AI Capital flow",
            "AI Makro",
            "AI Relative strength",
            "AI forklaring",
        ]
    ].copy()

    ai_table = ai_table.rename(
        columns={
            ai_name: "Instrument",
            "AI Confidence": "Confidence",
            "Confidence niveau": "Niveau",
            "AI Momentum": "Momentum",
            "AI Trend": "Trend",
            "AI Volatility": "Volatilitet",
            "AI Drawdown": "Drawdown",
            "AI Capital flow": "Kapitalflow",
            "AI Makro": "Makroregime",
            "AI Relative strength": "Relativ styrke",
            "AI forklaring": "AI forklaring",
        }
    ).sort_values("Confidence", ascending=False)

    ai_display = ai_table.copy()
    for column in [
        "Confidence",
        "Momentum",
        "Trend",
        "Volatilitet",
        "Drawdown",
        "Kapitalflow",
        "Makroregime",
        "Relativ styrke",
    ]:
        ai_display[column] = ai_display[column].apply(
            lambda value: f"{format_score(value, 0)}%"
        )

    st.dataframe(
        zebra_table(ai_display),
        use_container_width=True,
        hide_index=True,
        height=table_height(ai_display, max_height=700),
    )

    st.subheader("AI Confidence-ranking")

    ranking_df = ai_table[
        ["Instrument", "Confidence", "Niveau", "Anbefaling"]
    ].copy().sort_values("Confidence", ascending=True)
    ranking_df["Label"] = ranking_df["Confidence"].apply(lambda value: f"{value:.0f}%")

    fig_ranking = px.bar(
        ranking_df,
        x="Confidence",
        y="Instrument",
        orientation="h",
        text="Label",
        hover_data={"Confidence": ":.1f", "Niveau": True, "Anbefaling": True, "Label": False},
    )
    fig_ranking.update_traces(textposition="outside")
    fig_ranking.update_layout(
        xaxis_title="AI Confidence (%)",
        yaxis_title="Aktie",
        xaxis=dict(range=[0, 105]),
        showlegend=False,
        height=max(450, len(ranking_df) * 38),
        margin=dict(l=20, r=80, t=20, b=20),
    )
    st.plotly_chart(fig_ranking, use_container_width=True)

    st.subheader("Confidence-faktorer pr. aktie")
    factor_columns = ["Momentum", "Trend", "Volatilitet", "Drawdown", "Kapitalflow", "Makroregime", "Relativ styrke"]
    factor_heatmap = (
        ai_table[["Instrument", *factor_columns]]
        .set_index("Instrument")
        .reindex(ranking_df.sort_values("Confidence", ascending=False)["Instrument"])
    )
    fig_factor_heatmap = px.imshow(
        factor_heatmap,
        aspect="auto",
        text_auto=".0f",
        color_continuous_scale="RdYlGn",
        zmin=0,
        zmax=100,
        labels={"x": "Confidence-faktor", "y": "Aktie", "color": "Score"},
    )
    fig_factor_heatmap.update_layout(
        height=max(500, len(factor_heatmap) * 38),
        xaxis_title="Confidence-faktor",
        yaxis_title="Aktie",
    )
    st.plotly_chart(fig_factor_heatmap, use_container_width=True)

    col_profile, col_observations = st.columns([1.15, 0.85], gap="large")

    with col_profile:
        st.subheader("Detaljeret confidence-profil")

        radar_options = ai_table["Instrument"].astype(str).tolist()
        selected_instrument = st.selectbox(
            "Vælg aktie",
            radar_options,
            index=0,
            key="ai_confidence_radar_stock",
        )

        selected_row = ai_table.loc[
            ai_table["Instrument"].astype(str) == selected_instrument
        ].iloc[0]

        radar_values = [float(selected_row[column]) for column in factor_columns]
        radar_values_closed = radar_values + [radar_values[0]]
        radar_labels_closed = factor_columns + [factor_columns[0]]

        fig_radar = go.Figure()

        fig_radar.add_trace(
            go.Scatterpolar(
                r=radar_values_closed,
                theta=radar_labels_closed,
                fill="toself",
                name=selected_instrument,
                hovertemplate="%{theta}: %{r:.0f}<extra></extra>",
            )
        )

        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    tickvals=[0, 20, 40, 60, 80, 100],
                )
            ),
            showlegend=False,
            height=520,
            margin=dict(l=35, r=35, t=55, b=35),
            title=(
                f"{selected_instrument} · Confidence "
                f"{selected_row['Confidence']:.0f}% · "
                f"{selected_row['Anbefaling']}"
            ),
        )

        st.plotly_chart(fig_radar, use_container_width=True)

        selected_explanation = selected_row.get("AI forklaring", "")
        if selected_explanation:
            st.info(
                f"**AI-forklaring for {selected_instrument}:** "
                f"{selected_explanation}"
            )

    with col_observations:
        st.subheader("Vigtigste observationer")

        strongest = df.sort_values("AI Confidence", ascending=False).head(3)
        weakest = df.sort_values("AI Confidence", ascending=True).head(3)
        concentrated = df.sort_values("Current weight", ascending=False).head(3)

        strongest_names = ", ".join(
            strongest[ai_name].astype(str).tolist()
        )
        weakest_names = ", ".join(
            weakest[ai_name].astype(str).tolist()
        )
        concentrated_names = ", ".join(
            concentrated[ai_name].astype(str).tolist()
        )

        st.success(
            f"**Stærkeste beslutningsgrundlag**\n\n"
            f"{strongest_names}\n\n"
            "Disse positioner har den højeste samlede confidence i den nuværende model."
        )

        st.warning(
            f"**Svageste beslutningsgrundlag**\n\n"
            f"{weakest_names}\n\n"
            "Kontroller trend, risiko og datakvalitet før nye køb."
        )

        st.info(
            f"**Største koncentrationer**\n\n"
            f"{concentrated_names}\n\n"
            "Vurder om de fortsat passer til din valgte maksimumvægt."
        )

        st.caption(
            "Kapitalflow og makroregime er markedsdatabaserede proxyer – ikke direkte "
            "institutionelle fund-flowdata. Confidence er beslutningsstøtte og ikke en garanti."
        )


# =========================================================
# FANE 5 – HEATMAP
# =========================================================

with tab_heatmap:
    st.subheader("Monthly heatmap and risk KPI")

    risk1, risk2, risk3, risk4, risk5 = st.columns(5)
    risk1.metric("Volatilitet", format_pct(annual_volatility))
    risk2.metric("Max drawdown", format_pct(portfolio_max_drawdown))
    risk3.metric("Sharpe", format_score(sharpe_score, 2))
    risk4.metric("Sortino", format_score(sortino_score, 2))
    risk5.metric("Årligt afkast", format_pct(annual_return))

    st.subheader("Monthly heatmap")

    if not monthly_returns.empty:
        heatmap_months = monthly_returns.tail(12).copy()
        heatmap_months.index = heatmap_months.index.strftime("%b %Y")

        ticker_to_name = (
            df.drop_duplicates("Yahoo")
            .set_index("Yahoo")[
                "Navn" if "Navn" in df.columns else "Ticker"
            ]
            .to_dict()
        )
        heatmap_months = heatmap_months.rename(columns=ticker_to_name)

        fig_monthly = px.imshow(
            heatmap_months.T * 100,
            aspect="auto",
            text_auto=".1f",
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
            labels={
                "x": "Måned",
                "y": "Aktie",
                "color": "Afkast %",
            },
        )
        fig_monthly.update_layout(height=max(500, len(heatmap_months.columns) * 35))
        st.plotly_chart(fig_monthly, use_container_width=True)
    else:
        st.warning("Monthly heatmap kunne ikke beregnes.")

    st.subheader("Heatmap grafik")

    heatmap_name = "Navn" if "Navn" in df.columns else "Ticker"
    risk_heatmap = df[
        [
            heatmap_name,
            "MOM 1W",
            "MOM 3M",
            "MOM 6M",
            "MOM 12M",
            "Momentum score",
            "Risk score",
            "AI Confidence",
            "Current weight",
            "Suggested weight",
        ]
    ].copy()

    risk_heatmap = risk_heatmap.rename(
        columns={
            heatmap_name: "Instrument",
            "Momentum score": "Momentumscore",
            "Risk score": "Risiko",
            "AI Confidence": "AI confidence",
            "Current weight": "Aktuel vægt",
            "Suggested weight": "Forslag",
        }
    ).sort_values("AI confidence", ascending=False)

    heat_values = risk_heatmap.set_index("Instrument").copy()
    heat_values["MOM 1W"] *= 100
    heat_values["MOM 3M"] *= 100
    heat_values["MOM 6M"] *= 100
    heat_values["MOM 12M"] *= 100
    heat_values["Aktuel vægt"] *= 100
    heat_values["Forslag"] *= 100

    # Separat normalisering gør KPI'er med forskellige skalaer sammenlignelige.
    normalized = heat_values.copy()
    for column in normalized.columns:
        series = normalized[column]
        minimum = series.min(skipna=True)
        maximum = series.max(skipna=True)
        if pd.isna(minimum) or pd.isna(maximum) or maximum == minimum:
            normalized[column] = 0
        else:
            normalized[column] = (series - minimum) / (maximum - minimum) * 2 - 1

    # Høj risiko skal vises negativt i det samlede farvebillede.
    if "Risiko" in normalized.columns:
        normalized["Risiko"] = -normalized["Risiko"]

    text_formatter = lambda value: "" if pd.isna(value) else f"{value:.1f}"
    text_matrix = heat_values.map(text_formatter)

    fig_risk = go.Figure(
        data=go.Heatmap(
            z=normalized.values,
            x=normalized.columns,
            y=normalized.index,
            text=text_matrix.values,
            texttemplate="%{text}",
            colorscale="RdYlGn",
            zmid=0,
            colorbar=dict(title="Relativ score"),
            hovertemplate=(
                "Aktie: %{y}<br>"
                "KPI: %{x}<br>"
                "Værdi: %{text}<extra></extra>"
            ),
        )
    )
    fig_risk.update_layout(
        xaxis_title="KPI",
        yaxis_title="Aktie",
        height=max(550, len(risk_heatmap) * 38),
    )
    st.plotly_chart(fig_risk, use_container_width=True)

"""Commodity exotics book dashboard. Synthetic, educational market data only."""
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from engines.models import simulate_book

st.set_page_config(page_title="Commodity Exotics | Ayoub El Ammari", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

PALETTE = {"blue": "#60a5fa", "teal": "#45d6b0", "amber": "#f0b86e", "red": "#f48b8b", "muted": "#91a4c1"}

def desk_style():
    st.markdown("""<style>
    .stApp {background: #0b1322; color: #e8effa;}
    [data-testid="stSidebar"] {background: #111e31; border-right: 1px solid #25354d;}
    [data-testid="stMetric"] {background: #15243a; border: 1px solid #2a405b;
      padding: 16px 18px; border-radius: 12px;}
    [data-testid="stMetricLabel"] {color: #a6b9d3;}
    [data-testid="stMetricValue"] {font-size: 1.55rem; letter-spacing: -.02em;}
    h1,h2,h3 {letter-spacing: -.025em;}
    [data-testid="stCaptionContainer"] {color: #a6b9d3;}
    div.stButton > button[kind="primary"] {background: #2671cc; border-radius: 9px;}
    [data-testid="stDataFrame"] {border-radius: 9px;}
    </style>""", unsafe_allow_html=True)

def header(kicker, title, description):
    st.markdown(f'<div style="color:#78aaf0;font-size:12px;font-weight:700;letter-spacing:.12em">'
                f'{kicker} · AYOUB EL AMMARI / TRADING ANALYTICS</div>', unsafe_allow_html=True)
    st.title(title)
    st.caption(description)

def chart(fig, height=350):
    fig.update_layout(template="plotly_dark", height=height, margin=dict(l=16,r=15,t=42,b=20),
        paper_bgcolor="#111e31", plot_bgcolor="#111e31", font=dict(color="#d9e5f5",size=12),
        legend=dict(orientation="h", y=1.12, x=0), hovermode="x unified")
    fig.update_xaxes(showgrid=True,gridcolor="#293a50",zeroline=False)
    fig.update_yaxes(showgrid=True,gridcolor="#293a50",zeroline=False)
    st.plotly_chart(fig, use_container_width=True)

def downloadable_frame(frame, filename):
    st.download_button("↓ Export CSV", frame.to_csv(index=False).encode("utf-8"),
                       file_name=filename, mime="text/csv")

def render_model_guide(content):
    """Render guide prose and display equations separately for reliable Streamlit output."""
    import re
    sections = re.split(r"\$\$(.*?)\$\$", content, flags=re.DOTALL)
    for index, section in enumerate(sections):
        if not section.strip():
            continue
        if index % 2:
            st.latex(section.strip())
        else:
            # Dollar amounts (e.g., $100) should not start inline LaTeX spans.
            prose = re.sub(r"(?<!\\)\$(?=\d)", r"\\$", section)
            st.markdown(prose)

desk_style()
header("COMMODITIES / EXOTIC TRADING BOOK", "Portfolio Risk Monitor",
       "Barrier & rainbow options · Simulated positions and markets · 21-day trading and hedge replay")
with st.sidebar:
    st.header("Book controls")
    b_count = st.number_input("Short oil barrier contracts", min_value=1, max_value=100, value=20)
    r_count = st.number_input("Short rainbow notes", min_value=1, max_value=20, value=4)
    nominal = st.number_input("Rainbow notional per note ($)", min_value=10000, max_value=1000000, value=100000, step=10000)
    barrier = st.slider("Oil upper KO barrier ($/bbl)", 85., 130., 100., 1.)
    corr = st.slider("Cross-asset correlation", -.40, .90, .50, .05)
    st.divider()
    st.subheader("Risk scenario")
    shock_day = st.slider("Volatility spike day", 1, 20, 10)
    shock_mult = st.slider("Post-shock vol multiplier", 1., 3., 2., .25)
    paths = st.select_slider("Monte Carlo paths", options=[400,800,1200,2000], value=1200)
    costs = st.slider("Transaction cost (bps)", 0., 10., 1., .5)
    vega_hedge = st.toggle("Use oil vanilla vega proxy", value=True)
    seed = st.number_input("Random seed", value=17, step=1)
    run = st.button("Reprice trading book", type="primary", use_container_width=True)
    st.caption("Synthetic market paths. No live exchange or broker connection.")

@st.cache_data(show_spinner=False)
def compute(b_count, r_count, nominal, barrier, corr, shock_day, shock_mult, paths, costs, vega_hedge, seed):
    return simulate_book(barrier_contracts=-b_count, rainbow_contracts=-r_count,
                         rainbow_notional=nominal, barrier=barrier, corr=corr,
                         spike_day=shock_day, vol_multiplier=shock_mult, n=paths,
                         cost_bps=costs, hedge_vega=vega_hedge, seed=seed)

inputs = (b_count,r_count,nominal,barrier,corr,shock_day,shock_mult,paths,costs,vega_hedge,seed)
if run or "book_results" not in st.session_state:
    with st.spinner("Repricing exotics and simulating portfolio hedges..."):
        try:
            data = compute(*inputs)
        except Exception as exc:
            st.error(f"Simulation failed: {exc}")
            st.stop()
        st.session_state.book_results = data
        st.session_state.book_inputs = inputs
if inputs != st.session_state.book_inputs:
    st.warning("Inputs changed. Click **Reprice trading book** to apply them; charts still show the previous run.")
df = st.session_state.book_results
last = df.iloc[-1]
a,b,c,d = st.columns(4)
a.metric("Final net book P&L", f"${last['cumulative_pnl']:,.0f}")
b.metric("Cumulative transaction costs", f"${df['transaction_cost'].sum():,.0f}")
c.metric("Daily P&L standard deviation", f"${df['daily_pnl'].iloc[1:].std():,.0f}")
d.metric("Unwound short inventory", f"{last['unwound_pct']:.0%}")
st.caption("Simulation metrics, not real trading results. P&L is marked and rehedged daily; transaction costs included.")
t1,t2,t3,t4,t5,t6=st.tabs(["Overview", "Positions & prices", "Greeks & hedges", "Stress & unwind", "Data & methodology", "Model Guide"])
with t1:
    left,right=st.columns([1.5,1])
    with left:
        f=go.Figure()
        f.add_trace(go.Scatter(x=df.day,y=df.cumulative_pnl,mode="lines+markers",name="Net cumulative P&L",line=dict(color=PALETTE['teal'],width=3)))
        f.update_layout(title="Net hedged book P&L",xaxis_title="Simulation day",yaxis_title="USD")
        chart(f)
    with right:
        f=go.Figure(go.Bar(x=df.day,y=df.daily_pnl,marker_color=[PALETTE['teal'] if x>=0 else PALETTE['red'] for x in df.daily_pnl]))
        f.update_layout(title="Daily P&L",xaxis_title="Simulation day",yaxis_title="USD",showlegend=False)
        chart(f)
    st.info("The simulation is a short exotics book with delta hedging and an optional oil vanilla vega proxy. It is not an exchange-connected position management system.")
with t2:
    st.subheader("End-of-run position blotter")
    positions=pd.DataFrame([
        {"Instrument":"Oil up-and-out call", "Underlying":"Oil", "Position":last.barrier_contracts, "Units":"contracts (1,000 bbl each)", "Model price":last.barrier_price},
        {"Instrument":"Rainbow best-of note", "Underlying":"Oil / Gold / Copper", "Position":last.rainbow_contracts, "Units":"notes", "Model price":last.rainbow_price},
        {"Instrument":"Oil vanilla call", "Underlying":"Oil", "Position":last.vanilla_hedge, "Units":"options", "Model price":np.nan}])
    st.dataframe(positions,hide_index=True,use_container_width=True)
    st.caption("Prices use different units across instruments; do not sum unscaled model prices.")
    f=go.Figure()
    for name,color in [("oil",PALETTE['blue']),("gold",PALETTE['amber']),("copper",PALETTE['teal'])]:
        f.add_trace(go.Scatter(x=df.day,y=100*df[name]/df[name].iloc[0],name=name.title(),line=dict(color=color)))
    f.update_layout(title="Commodity prices normalized to 100 at day 0",xaxis_title="Simulation day",yaxis_title="Index (day 0 = 100)")
    chart(f)
with t3:
    left,right=st.columns(2)
    with left:
        f=go.Figure()
        for name,color in [("hedge_oil",PALETTE['blue']),("hedge_gold",PALETTE['amber']),("hedge_copper",PALETTE['teal'])]:
            f.add_trace(go.Scatter(x=df.day,y=df[name],name=name.replace('hedge_','').title(),line=dict(color=color)))
        f.update_layout(title="Delta hedge inventory",xaxis_title="Day",yaxis_title="Underlying units")
        chart(f)
    with right:
        f=go.Figure()
        f.add_trace(go.Scatter(x=df.day,y=df.vanilla_hedge,name="Vanilla hedge",line=dict(color=PALETTE['amber'])))
        f.update_layout(title="Oil vanilla vega-proxy inventory",xaxis_title="Day",yaxis_title="Vanilla call units")
        chart(f)
    greeks=pd.DataFrame({"Risk measure":["Oil barrier delta","Rainbow delta / oil","Rainbow delta / gold","Rainbow delta / copper","Barrier vega (unscaled)","Rainbow parallel vega (per note)","Rainbow oil-gold cross gamma"],
                          "Final value":[last.barrier_delta,last.rainbow_delta_oil,last.rainbow_delta_gold,last.rainbow_delta_copper,last.barrier_vega,last.rainbow_vega,last.rainbow_cross_gamma_og]})
    st.dataframe(greeks,use_container_width=True,hide_index=True)
    st.caption("Displayed Greeks are per instrument or note, not aggregated portfolio risk. Oil's vanilla hedge only approximates parallel vega exposure.")
with t4:
    left,right=st.columns(2)
    with left:
        f=go.Figure(go.Scatter(x=df.day,y=100*df.oil_vol,mode="lines",line=dict(color=PALETTE['amber'])))
        f.add_vline(x=st.session_state.book_inputs[5],line_dash="dash",line_color=PALETTE['red'])
        f.update_layout(title="Oil implied volatility regime",xaxis_title="Day",yaxis_title="Volatility (%)")
        chart(f)
    with right:
        f=go.Figure()
        for col,color in [("barrier_contracts",PALETTE['blue']),("rainbow_contracts",PALETTE['teal'])]:
            f.add_trace(go.Scatter(x=df.day,y=df[col],name=col.replace('_',' ').title(),line=dict(color=color)))
        f.update_layout(title="Short exotic position unwind",xaxis_title="Day",yaxis_title="Contracts / notes")
        chart(f)
    st.info("After the volatility spike, inventory is unwound across five days if maximum implied volatility exceeds 30%. No market-impact or slippage model is applied beyond turnover costs.")
with t5:
    st.subheader("Daily trading-book ledger")
    st.dataframe(df.round(5),use_container_width=True,height=390)
    downloadable_frame(df,"commodity_exotics_daily_book.csv")
    st.markdown("**Model boundaries:** Synthetic correlated GBM markets; rainbow payoff is based on maximum percentage return, not maximum absolute asset price. Brownian bridge prices a continuously monitored upper barrier, while the simulated realized hedge path checks oil at four intraday steps. Portfolio P&L excludes financing, bid/ask asymmetry and liquidity risk beyond configured transaction costs.")


# Concise technical reference; pricing and dashboard logic above is unchanged.
with t6:
    st.subheader("Model Guide | Commodity Exotic Trading Book")
    st.caption("A quick explanation of the products, pricing, hedging and limitations. Synthetic markets; not live trading.")

    with st.expander("1. What is being traded?", expanded=True):
        st.markdown("""**Book:** short oil up-and-out calls and short best-of rainbow calls linked to **oil, gold and copper**.

- **Oil barrier call:** pays the positive difference between oil price and strike only if oil never touches the upper barrier.
- **Rainbow call:** pays on the highest *percentage return* of the three commodities relative to their original reference prices.
- One oil option contract represents **1,000 barrels**; each rainbow note has a configurable USD notional.
""")
        st.latex(r"X_B=(S_T-K)^+\,\mathbf{1}_{\{\max_{0\le t\le T}S_t<B\}}")
        st.latex(r"X_R=N\left(\max_i\left[\frac{S_{i,T}}{S_{i,0}^{\mathrm{ref}}}-1\right]\right)^+")

    with st.expander("2. How are prices calculated?"):
        st.markdown("""- Simulate **63-step correlated geometric Brownian-motion paths** for the three commodities using Cholesky decomposition and antithetic shocks.
- Apply **Brownian-bridge survival weights** to price a continuously monitored upper barrier, including crossings between simulated dates.
- Average each payoff and discount it at the flat risk-free rate. Reuse seeded random shocks for reproducible risk estimates.""")
        st.latex(r"\widehat V=e^{-rT}\frac{1}{n}\sum_{m=1}^{n}\text{payoff}_m\,w_m")
        st.caption("For the rainbow option, the survival weight is 1: it has no barrier.")

    with st.expander("3. Greeks, hedging and P&L"):
        st.markdown("""- **Delta and vega:** reprice after small spot or volatility bumps; **cross-gamma** measures interactions between two commodity prices.
- Rebalance **oil, gold and copper delta hedges daily**. An optional vanilla oil call provides an imperfect proxy for the portfolio's combined volatility exposure.
- Record daily changes in exotic marks and hedge values, then subtract turnover-based transaction costs.
- Apply the chosen volatility shock and, if the modeled threshold is breached, **unwind short exotic positions over five sessions**.""")
        st.latex(r"\Delta_i\approx\frac{V(S_i+h)-V(S_i-h)}{2h}")
        st.latex(r"\mathrm{PnL}_t=\Delta V_{\mathrm{exotics},t}+\Delta V_{\mathrm{hedges},t}-\mathrm{costs}_t")

    with st.expander("4. How to interpret the results"):
        st.markdown("""**Read the dashboard:** *Overview* tracks simulated P&L; *Positions & prices* shows positions and underlying moves; *Greeks & hedges* shows sensitivities and inventories; *Stress & unwind* shows volatility shocks and risk reduction.

**Check:** unchanged seeds should reproduce results; a knocked-out oil call must be worth zero; a barrier call should not exceed its matching vanilla call.

**Limitations:** synthetic constant-volatility markets, no smile calibration or observed commodity term structures. The oil-call hedge cannot eliminate separate commodity vegas or correlation risk. Transaction costs are simplified; results are **not live or historical trading performance**.""")

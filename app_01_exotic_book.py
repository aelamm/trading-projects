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

# Detailed source-aligned technical reference.
with t6:
    st.subheader("Model guide — Commodity exotic trading book")
    st.caption("Technical documentation of the actual educational implementation in engines/models.py. Synthetic prices and paths; no live market feeds.")
    with st.expander("1. Desk mandate, product definitions and conventions", expanded=True):
        render_model_guide(r"""
**Objective.** Simulate a short book containing an oil **up-and-out call** and a three-commodity **best-of percentage-return rainbow call** on oil, gold and copper; compute marks and finite-difference Greeks; hedge exposures daily; examine a volatility shock and staged unwind.

| Convention | Implementation |
|---|---|
| Oil initial level / barrier option strike | $78 per barrel / $78 |
| Oil upper knock-out barrier | User-selected (default $100 per barrel) |
| Gold / copper starting levels | $2,650 per ounce / $4 per pound |
| Annualized starting volatilities | Oil 25%, gold 15%, copper 20% |
| Risk-free rate | Flat, continuously compounded 2% |
| Rainbow reference levels | Fixed at the initial oil, gold and copper levels |
| Rainbow note payout notional | User-selected, default $100,000 per note |
| Oil contract multiplier | 1,000 barrels per contract |
| Position convention | Negative contracts = short exotic liability |
| Trading experiment | 21 business-day changes plus day 0; 252 days/year |

The **oil call payoff for an unbreached upper barrier** is

$$X_B=(S_T-K)^+\,\mathbf 1_{\{\max_{0\le t\le T}S_t<B\}}.$$

The **rainbow note** is normalized by the *original* reference prices, rather than choosing the largest absolute commodity price:

$$X_R=N\left(\max_{i\in\{1,2,3\}}\left[\frac{S_{i,T}}{S_{i,0}^{\mathrm{ref}}}-1\right]\right)^+.$$

Both positions are marked in USD, but **oil option marks must be multiplied by 1,000 barrels per contract**; rainbow marks are already dollars per note. The app reports Greeks per product/note rather than automatically interpreting them as net book Greeks.
""")
    with st.expander("2. Simulated market dynamics, correlation and Monte Carlo"):
        render_model_guide(r"""
Each commodity follows a **risk-neutral geometric Brownian motion** with constant annual volatility between scenario changes:

$$\frac{dS_i}{S_i}=(r-q_i)dt+\sigma_i\,dW_i,\qquad q_i=0.$$

A discrete simulation step is

$$S_{i,t+\Delta t}=S_{i,t}\exp\left[(r-\tfrac12\sigma_i^2)\Delta t+\sigma_i\sqrt{\Delta t}Z_{i,t}\right].$$

Three correlated normals are obtained by Cholesky factorization: if $LL^\top=C$, then $Z^{\mathrm{corr}}=LZ$, where $C$ is the equicorrelation matrix with user-set off-diagonal correlation $\rho$. The model requires this matrix to be **positive definite**.

The pricing engine uses **63 time steps** and **antithetic Gaussian shocks**: for each sampled $Z$, it also runs $-Z$. The same seeded shock matrix is reused for bumped prices, reducing simulation noise in finite-difference Greeks. This is a **synthetic scenario generator**, not calibrated historical commodity-market data.

For the continuously observed oil upper barrier, the simulation weights surviving endpoint intervals using a **Brownian-bridge conditional no-hit probability**:

$$p_{\mathrm{surv},j}=1-\exp\left[-\frac{2\log(B/S_j)\log(B/S_{j+1})}{\sigma^2\Delta t}\right]$$

when both endpoints are below $B$ (zero otherwise). The **path survival weight** is $w=\prod_j p_{\mathrm{surv},j}$, and the oil call mark is

$$\widehat V_B=e^{-rT}\frac1n\sum_{m=1}^n(S_T^{(m)}-K)^+w_m.$$

The rainbow Monte Carlo mark is likewise $e^{-rT}$ times the average rainbow payoff. There is no barrier on the rainbow note.
""")
    with st.expander("3. Greeks, cross-gamma and hedge construction"):
        render_model_guide(r"""
Greeks are computed using **central price bumps with common random numbers**:

$$\Delta_i\approx\frac{V(S_i+h_i)-V(S_i-h_i)}{2h_i},\qquad
\Gamma_i\approx\frac{V(S_i+h_i)-2V(S_i)+V(S_i-h_i)}{h_i^2}.$$

For the rainbow, $h_i=0.5\%\times S_i$. The oil barrier Greek bump is approximately $0.2\%$ of spot, limited to 20% of the gap to the upper barrier (and subject to small minimum thresholds). These step sizes are implementation choices, not analytical identities.

The rainbow **oil–gold cross-gamma** (one example of the cross-asset interactions) is

$$\Gamma_{ij}\approx\frac{V_{++}-V_{+-}-V_{-+}+V_{--}}{4h_i h_j}.$$

Oil barrier vega is a finite difference in oil volatility. Rainbow **parallel vega** bumps all three commodity volatilities by $\pm 0.005$ together; it is *not* a separate oil/gold/copper vega vector.

Daily target hedge inventory for each commodity $i$ is

$$H_i=-\left(q_B\,1000\,\Delta_{B,i}+q_R\Delta_{R,i}\right)-\mathbf1_{i=\mathrm{oil}}H_C\Delta_C,$$

where the oil barrier has delta only to oil, and $H_C$ is the quantity of a **vanilla oil call** used as a *parallel-vega proxy*:

$$H_C=-\frac{q_B\,1000\,\nu_B+q_R\nu_R^{\mathrm{parallel}}}{\nu_C}.$$

$H_C$ is set to zero when the toggle is off or the vanilla vega is near zero. A single oil call cannot precisely hedge the three underlying-specific volatility sensitivities or correlation risk.
""")
    with st.expander("4. P&L ledger, costs, spike and unwind"):
        render_model_guide(r"""
At day $t$, **yesterday's positions** are revalued *before* hedge rebalancing and any unwind:

$$\Delta\Pi_t=q_{B,t-1}\,1000\,\Delta V_{B,t}+q_{R,t-1}\Delta V_{R,t}+\sum_i H_{i,t-1}\Delta S_{i,t}+H_{C,t-1}\Delta C_t-\mathrm{TC}_t.$$

Transaction fees are proportional to **absolute hedge turnover marked at current prices**, including changes in exotic inventories and vanilla hedge quantity:

$$\mathrm{TC}_t=\frac{b}{10^4}\left[\sum_i |\Delta H_i|S_i+|\Delta q_B|\,1000\,V_B+|\Delta q_R|V_R+|\Delta H_C|C\right].$$

A volatility multiplier applies to **all three** market volatilities on and after the selected shock day. If the highest simulated volatility then exceeds **30%**, the short exotic positions are reduced linearly over **five sessions** starting on the shock day. Hedging inventory is re-targeted each day.

The realized oil path is checked at **four intraday substeps per hedge day**, whereas valuation assumes continuous monitoring through the bridge calculation. Thus the realized knock-out indicator and risk-neutral knock-out probability are not interchangeable.
""")
    with st.expander("5. Build sequence, validation and limitations"):
        render_model_guide(r"""
**Reconstructing the application:** (1) define product terms and positions; (2) generate seeded correlated GBM shocks; (3) evaluate barrier and rainbow payoffs; (4) use common random numbers for Greeks; (5) construct stock and optional vanilla-call hedge inventories; (6) move the synthetic market forward; (7) mark previous inventories, apply turnover costs, and update positions; (8) record a row of the simulated ledger; (9) chart and export results.

**Useful validation checks:** a knocked-out oil call must price at zero; an up-and-out call must not exceed a matched vanilla call under the same assumptions; correlation matrices must be positive definite; the rainbow note should respond to correlation and cross-gamma; P&L should be reproducible when the seed is unchanged; displayed option prices must be scaled to their product units when forming book P&L.

**Scope:** no empirical volatility surfaces, commodity seasonality, jumps, stochastic rates, convenience yields, funding/carry, credit, order-book execution, bid/ask asymmetry, cross-vega hedge, correlation hedge or market-impact model. The scenario is a teaching simulation, **not a production trading system**. The model's option-price Monte Carlo sampling uncertainty is not an estimate of hedging risk, VaR or P&L forecast accuracy.

**Source code:** `engines/models.py` (`shocks`, `gbm_paths`, `bridge_survival`, `barrier_mc`, `rainbow_mc`, `barrier_greeks`, `rainbow_greeks`, `simulate_book`).
""")

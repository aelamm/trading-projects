"""Equity up-and-out option pricing / hedging workstation."""
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from engines.models import barrier_mc, barrier_greeks, simulate_barrier_hedge, shocks

st.set_page_config(page_title="Equity Barrier Option | Ayoub El Ammari", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

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
header("EQUITY EXOTICS / BARRIER OPTIONS", "Barrier Pricing & Hedging",
       "Continuously monitored up-and-out call · Antithetic Monte Carlo & Brownian bridge · Simulated delta/vega hedge")
with st.sidebar:
    st.header("Option terms")
    spot=st.number_input("Underlying spot ($)",min_value=1.,value=100.,step=1.)
    strike=st.number_input("Call strike ($)",min_value=1.,value=100.,step=1.)
    barrier=st.number_input("Upper knock-out barrier ($)",min_value=1.,value=120.,step=1.)
    vol=st.slider("Implied volatility (%)",1.,70.,25.,1.)/100
    rate=st.slider("Risk-free rate (%)",0.,10.,2.,.25)/100
    maturity=st.slider("Maturity (years)",.25,2.,1.,.25)
    st.divider()
    st.subheader("Simulation & hedge")
    paths=st.select_slider("Monte Carlo paths",options=[500,1000,2000,5000,10000],value=2000)
    qty=st.number_input("Short options",100,100000,1000,100)
    hedge_vega=st.toggle("Hedge vega with vanilla calls",value=True)
    cost=st.slider("Transaction cost (bps)",0.,10.,1.,.5)
    seed=st.number_input("Random seed",value=31,step=1)
    run=st.button("Run pricing & hedge replay",type="primary",use_container_width=True)
    st.caption("Synthetic risk-neutral market, not market quotes.")

@st.cache_data(show_spinner=False)
def compute(spot,strike,barrier,vol,rate,maturity,paths,qty,hedge_vega,cost,seed):
    z=shocks(paths,63,1,seed+10)
    price=barrier_mc(spot,strike,barrier,rate,maturity,vol,z=z)
    greeks=barrier_greeks(spot,strike,barrier,rate,maturity,vol,z)
    hedge=simulate_barrier_hedge(s0=spot,k=strike,barrier=barrier,r=rate,t=maturity,
                                 sigma=vol,n=paths,contracts=-qty,cost_bps=cost,
                                 hedge_vega=hedge_vega,seed=seed)
    return price,greeks,hedge

inputs=(spot,strike,barrier,vol,rate,maturity,paths,qty,hedge_vega,cost,seed)
if run or "barrier_results" not in st.session_state:
    with st.spinner("Running antithetic Monte Carlo and 21-day hedge simulation..."):
        try:
            payload=compute(*inputs)
        except Exception as exc:
            st.error(f"Calculation failed: {exc}")
            st.stop()
        st.session_state.barrier_results=payload
        st.session_state.barrier_inputs=inputs
if inputs!=st.session_state.barrier_inputs:
    st.warning("Parameters changed. Click **Run pricing & hedge replay** to refresh results.")
mark,g,df=st.session_state.barrier_results
spot_used,strike_used,barrier_used,vol_used,rate_used,maturity_used,paths_used,qty_used,vega_used,cost_used,seed_used=st.session_state.barrier_inputs
k1,k2,k3,k4=st.columns(4)
k1.metric("Model premium / option",f"${mark['price']:.4f}")
k2.metric("Monte Carlo 95% CI",f"${mark['ci_low']:.3f} – ${mark['ci_high']:.3f}")
k3.metric("Option delta",f"{g['delta']:+.4f}")
k4.metric("Vega / 1.0 vol",f"{g['vega']:+.3f}")
st.caption(f"Risk-neutral KO estimate: {mark['ko_probability']:.1%} · Gamma: {g['gamma']:+.4f} · 21-day short-position hedged P&L: ${df.cumulative_pnl.iloc[-1]:,.2f}. CI measures sampling error only.")
if spot_used>=barrier_used:
    st.warning("Initial spot is at or above the upper barrier; the product is knocked out at inception in this model.")
t1,t2,t3,t4,t5,t6=st.tabs(["Price & confidence", "Barrier sensitivity", "Hedging desk", "Scenario analysis", "Data & model notes", "Model Guide"])
with t1:
    left,right=st.columns([1.5,1])
    with left:
        counts=[500,1000,2000,5000]
        conv=[]
        for n in counts:
            x=barrier_mc(spot_used,strike_used,barrier_used,rate_used,maturity_used,vol_used,n=n,steps=63,seed=seed_used+10)
            conv.append((n,x['price'],x['ci_low'],x['ci_high']))
        conv=pd.DataFrame(conv,columns=["Paths","Premium","CI low","CI high"])
        f=go.Figure()
        f.add_trace(go.Scatter(x=conv.Paths,y=conv.Premium,name="MC price",mode="lines+markers",line=dict(color=PALETTE['blue'],width=3)))
        f.add_trace(go.Scatter(x=conv.Paths,y=conv['CI low'],name="95% lower",line=dict(color=PALETTE['muted'],dash="dash")))
        f.add_trace(go.Scatter(x=conv.Paths,y=conv['CI high'],name="95% upper",line=dict(color=PALETTE['teal'],dash="dash")))
        f.update_layout(title="Price convergence & sampling interval",xaxis_title="Paths",yaxis_title="Price (USD)")
        chart(f)
    with right:
        st.subheader("Valuation diagnostics")
        diag=pd.DataFrame({"Metric":["Model premium","Standard error","95% CI lower","95% CI upper","Risk-neutral KO estimate","Delta","Gamma","Vega per 1.0 vol"],
                           "Estimate":[mark['price'],mark['stderr'],mark['ci_low'],mark['ci_high'],mark['ko_probability'],g['delta'],g['gamma'],g['vega']]})
        st.dataframe(diag,hide_index=True,use_container_width=True)
        st.caption("Brownian-bridge conditional survival approximates continuous barrier monitoring between simulated time steps.")
with t2:
    st.subheader("Greeks approaching the upper knock-out barrier")
    if spot_used>=barrier_used:
        st.info("Sensitivity grid unavailable: option is knocked out at the initial spot.")
    else:
        with st.expander("Calculate spot sensitivity curves (computationally intensive)",expanded=False):
            if st.button("Compute Greek curves",key="compute_greek_curves"):
                z=shocks(min(paths_used,1200),63,1,seed_used+10)
                levels=np.linspace(max(1.,spot_used*.75),barrier_used*.995,20)
                sens=[]
                with st.spinner("Calculating finite-difference sensitivities..."):
                    for level in levels:
                        result=barrier_greeks(level,strike_used,barrier_used,rate_used,maturity_used,vol_used,z)
                        sens.append((level,result['delta'],result['vega']))
                st.session_state.greek_scan=(inputs,sens)
            existing=st.session_state.get("greek_scan")
            if existing is not None and existing[0]==inputs:
                sens=pd.DataFrame(existing[1],columns=["Spot","Delta","Vega"])
                f=go.Figure()
                f.add_trace(go.Scatter(x=sens.Spot,y=sens.Delta,name="Delta",line=dict(color=PALETTE['blue'])))
                f.add_trace(go.Scatter(x=sens.Spot,y=sens.Vega,name="Vega",line=dict(color=PALETTE['amber'])))
                f.update_layout(title="Finite-difference delta & vega by spot",xaxis_title="Spot ($)",yaxis_title="Greek (different units)")
                chart(f)
                st.caption("Delta and vega have different units and share the axis for visualization only. Estimates can be noisy near the barrier.")
with t3:
    left,right=st.columns(2)
    with left:
        f=go.Figure(go.Scatter(x=df.day,y=df.cumulative_pnl,line=dict(color=PALETTE['teal'],width=3)))
        f.update_layout(title="Net cumulative hedge P&L",xaxis_title="Hedge day",yaxis_title="USD")
        chart(f)
    with right:
        f=go.Figure()
        f.add_trace(go.Scatter(x=df.day,y=df.stock_hedge,name="Stock units",line=dict(color=PALETTE['blue'])))
        f.add_trace(go.Scatter(x=df.day,y=df.vanilla_hedge,name="Vanilla calls",line=dict(color=PALETTE['amber'])))
        f.update_layout(title="Daily hedging inventories",xaxis_title="Hedge day",yaxis_title="Instrument units")
        chart(f)
    x,y,z=st.columns(3)
    x.metric("21-day net P&L",f"${df.cumulative_pnl.iloc[-1]:,.2f}")
    y.metric("Total hedge turnover costs",f"${df.cost.sum():,.2f}")
    z.metric("Observed barrier breach", "YES" if df.knocked_out.any() else "NO")
    st.caption("The underlying path is checked at four intraday steps, not continuously. The hedge is rebalanced daily. Inventory includes short initial option exposure.")
with t4:
    st.subheader("Price sensitivity across spot & volatility")
    st.caption("A compact illustrative stress grid, recomputed only when requested. Each cell uses fresh pricing calls with common random shocks.")
    if st.button("Run scenario grid",key="run_scenario_grid"):
        with st.spinner("Pricing stress scenarios..."):
            z=shocks(min(paths_used,1200),63,1,seed_used+20)
            spots=np.array([spot_used*.85,spot_used*.925,spot_used,spot_used*1.075,spot_used*1.15])
            vols=np.clip(np.array([vol_used*.75,vol_used,vol_used*1.25]),.0001,2.)
            heat=np.array([[barrier_mc(s,strike_used,barrier_used,rate_used,maturity_used,v,z=z)['price'] for s in spots] for v in vols])
            st.session_state.stress_grid=(inputs,spots,vols,heat)
    stress=st.session_state.get("stress_grid")
    if stress is not None and stress[0]==inputs:
        _,spots,vols,heat=stress
        f=go.Figure(go.Heatmap(x=[round(x,2) for x in spots],y=[round(v*100,2) for v in vols],z=heat,colorscale="Blues",colorbar=dict(title="Premium")))
        f.update_layout(title="Up-and-out call premium by spot and vol",xaxis_title="Spot ($)",yaxis_title="Implied volatility (%)")
        chart(f)
with t5:
    st.subheader("Simulated hedge ledger")
    st.dataframe(df.round(5),hide_index=True,use_container_width=True,height=390)
    downloadable_frame(df,"equity_barrier_hedge_21_days.csv")
    st.warning("Model limitations: pricing assumes continuous barrier observation using Brownian bridges; realized simulation checks the stock at four intraday points. Greeks are finite differences with common random numbers; estimates near knockout can be unstable. Mid-pricing with proportional trading costs excludes explicit bid/ask spread, liquidity and barrier gap risk.")

# Detailed source-aligned technical reference.
with t6:
    st.subheader("Model guide — Equity barrier pricing and dynamic hedging")
    st.caption("The equations and implementation notes below describe the code actually deployed in engines/models.py, not a generic barrier-options model.")
    with st.expander("1. Instrument, objective and assumptions", expanded=True):
        render_model_guide(r"""
**Goal.** Price a European **up-and-out call**, estimate its sampling uncertainty and Greeks, then simulate a short-option book hedged with stock and an optional vanilla call.

| Parameter | Implementation |
|---|---|
| $S_0$ | Underlying spot (default $100) |
| $K$ | Strike (default $100) |
| $B$ | Upper barrier (default $120) |
| $T$ | Time to expiry (default 1 year) |
| $r$ | Flat continuously compounded risk-free rate (default 2%) |
| $\sigma$ | Constant annualized volatility (default 25%) |
| Quantity | Negative short option position, default 1,000 options |
| Price path | Risk-neutral lognormal GBM with no dividends |
| Valuation monitoring | Continuous upper barrier (Brownian-bridge adjustment) |
| Hedge replay | 21 trading days, one rebalance daily, four observed price substeps per day |

The payout is

$$X=(S_T-K)^+\mathbf1_{\{\max_{0\le t\le T}S_t<B\}}.$$

The barrier is **knock-out**, not knock-in: a touch at or above $B$ extinguishes the option, without rebate. If $S_0\ge B$, the implementation returns zero price, zero Greeks and risk-neutral knock-out probability 100%.

Under risk-neutral pricing,

$$V_0=\mathbb E^{\mathbb Q}[e^{-rT}X].$$

The underlying follows $dS_t=rS_tdt+\sigma S_tdW_t$ under the no-dividend assumptions. This is a **teaching model with synthetic prices**, not a live implied-volatility surface.
""")
    with st.expander("2. Antithetic Monte Carlo, Brownian bridge and price intervals"):
        render_model_guide(r"""
Lognormal path stepping for a simulation grid $\Delta t=T/M$ is

$$S_{t+\Delta t}=S_t\exp[(r-\tfrac12\sigma^2)\Delta t+\sigma\sqrt{\Delta t}Z_t].$$

The engine uses **63 time steps** and pairs each Gaussian path $Z$ with the antithetic path $-Z$. To approximate continuously observed knock-out from discretely sampled paths, it computes conditional **no-touch probability** on each segment with both endpoints below the barrier:

$$p_j=1-\exp\left[-\frac{2\log(B/S_j)\log(B/S_{j+1})}{\sigma^2\Delta t}\right].$$

If either endpoint is at or above $B$, $p_j=0$. The path-level weight is $w=\prod_j p_j$, leading to the conditional Monte Carlo estimator:

$$\widehat V_0=e^{-rT}\frac1n\sum_{m=1}^n (S_T^{(m)}-K)^+w_m.$$

The reported risk-neutral **knock-out estimate** is $1-\frac1n\sum_m w_m$; it is **not** the observed fraction knocked out during the subsequent 21-day hedge replay.

The engine reports a price sampling standard error $s/\sqrt n$ and indicative confidence interval $\widehat V\pm1.96s/\sqrt n$ (lower price endpoint truncated to zero). **Caution:** because samples are antithetically paired, the formula does not account for pair covariance and should not be treated as a precisely calibrated 95% coverage guarantee. It also excludes model risk and hedging P&L uncertainty.
""")
    with st.expander("3. Spot Greeks, vega and vanilla hedge instrument"):
        render_model_guide(r"""
For option value $V(S,\sigma)$, price sensitivities are estimated using **common random shocks** across bumped scenarios:

$$\Delta\approx\frac{V(S+h,\sigma)-V(S-h,\sigma)}{2h},\qquad
\Gamma\approx\frac{V(S+h,\sigma)-2V(S,\sigma)+V(S-h,\sigma)}{h^2}.$$

The spot bump is adapted to the **gap to the upper barrier**: nominal $h=\max(0.002S,0.01)$, capped at 20% of $B-S$, with a small floor. Vega is

$$\nu\approx\frac{V(S,\sigma+u)-V(S,\max(0,\sigma-u))}{(\sigma+u)-\max(0,\sigma-u)},\quad u=\max(0.002,0.02\sigma).$$

**Units:** delta is option-price change per $1 of spot; gamma per squared dollar; vega is price change per **1.00 (100 percentage points)** of volatility. To interpret vega for a 1-volatility-percentage-point move, divide by 100.

The auxiliary hedge is a same-strike, same-residual-maturity **European vanilla call** priced with Black–Scholes (no dividend yield):

$$d_1=\frac{\ln(S/K)+(r+\sigma^2/2)\tau}{\sigma\sqrt\tau},\quad d_2=d_1-\sigma\sqrt\tau,$$

$$C=S\Phi(d_1)-Ke^{-r\tau}\Phi(d_2),\quad
\Delta_C=\Phi(d_1),\quad \nu_C=S\phi(d_1)\sqrt\tau.$$

For a short exotic inventory $q<0$, the model chooses vanilla-call quantity $H_C=-q\nu/\nu_C$ when vega hedging is enabled and $\nu_C$ is nonzero, followed by stock inventory $H_S=-q\Delta-H_C\Delta_C$. This hedges local first-order delta/vega, not jump or barrier gap risk.
""")
    with st.expander("4. Daily hedge replay, P&L and transaction costs"):
        render_model_guide(r"""
The simulation moves spot using **four GBM substeps per trading day**, checks the realized upper barrier at those four observations, and revalues the remaining position using $\tau=\max(T-t/252,1/252)$. Once a realized breach is observed, the exotic is zero in all subsequent daily marks.

The hedge is **rebalanced once a day**; the prior day's holdings determine the mark-to-market profit and loss before the next rebalance:

$$\mathrm{PnL}^{\mathrm{pretrade}}_t=q[V_t-V_{t-1}]+H_{S,t-1}(S_t-S_{t-1})+H_{C,t-1}(C_t-C_{t-1}).$$

Trading costs use proportional **absolute traded notional**, with basis-point rate $b$:

$$\mathrm{TC}_t=\frac{b}{10^4}\left(|H_{S,t}-H_{S,t-1}|S_t+|H_{C,t}-H_{C,t-1}|C_t\right).$$

Therefore $\mathrm{PnL}^{\mathrm{net}}_t=\mathrm{PnL}^{\mathrm{pretrade}}_t-\mathrm{TC}_t$ and cumulative P&L is the sum of the net daily entries.

The initial hedge formation incurs costs even though the mark-to-market P&L at day zero is zero. The app separately shows hedge inventories, cumulative P&L, and whether the simulated *realized* upper barrier was observed to be breached.
""")
    with st.expander("5. How to reproduce, verify and interpret the outputs"):
        render_model_guide(r"""
**Build sequence:** (1) input option terms; (2) generate seeded antithetic shocks; (3) simulate GBM endpoints; (4) calculate Brownian-bridge survival weights; (5) discount expected survival-weighted payoff; (6) compute finite-difference delta/gamma/vega using common shocks; (7) price the vanilla hedge analytically; (8) simulate 21 daily spot movements, revalue and rebalance; (9) accumulate trading costs and net P&L; (10) produce convergence plots, sensitivity scans and exported ledgers.

**Validation ideas:** zero option value whenever initial spot is already beyond the upper barrier; barrier price between zero and comparable vanilla call price; no negative Monte Carlo option price; reproducibility with the same seed; price sensitivity to spot and volatility; cost-free replays should have zero turnover fees; hedging costs should rise when the configured bps rate increases (all else fixed).

**Interpretation cautions:** price simulation intervals are *sampling* intervals, not prediction bands; path convergence is not a substitute for out-of-sample validation; finite-difference Greeks become sensitive to step size and sampling noise near the barrier; vanilla hedges do not span discontinuous knock-out exposure; the realized path's four daily observations miss intrastep barrier hits. No dividends, stochastic volatility, rates, jumps, transaction-level bid/ask, funding, liquidity, market impact or implied-volatility smile calibration are modeled.

**Source code:** `engines/models.py` (`shocks`, `gbm_paths`, `bridge_survival`, `barrier_mc`, `barrier_greeks`, `vanilla_call`, `simulate_barrier_hedge`).
""")

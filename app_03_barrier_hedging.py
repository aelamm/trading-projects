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


# Concise technical reference; pricing and dashboard logic above is unchanged.
with t6:
    st.subheader("Model Guide | Equity Barrier Option")
    st.caption("A quick explanation of the payoff, Monte Carlo pricing and daily hedge replay.")

    with st.expander("1. What is the option?", expanded=True):
        st.markdown("""**Product:** European **up-and-out call**. It pays like a normal call at expiry **only if the stock never reaches the upper barrier**.

- The option has no rebate after knock-out.
- Inputs: spot, strike, upper barrier, maturity, rate and volatility.
- The hedge simulator starts with a **short option position** and offsets exposure using stock and, optionally, vanilla calls.""")
        st.latex(r"X=(S_T-K)^+\,\mathbf{1}_{\{\max_{0\le t\le T}S_t<B\}}")

    with st.expander("2. How is the price calculated?"):
        st.markdown("""- Simulate risk-neutral **geometric Brownian motion** with **63 time steps** and antithetic Monte Carlo paths.
- Use **Brownian-bridge survival probabilities** to account for barrier hits between simulated endpoints.
- Discount the average survival-weighted payoff. Display a Monte Carlo standard error and indicative **95% sampling interval**.""")
        st.latex(r"\widehat V=e^{-rT}\frac1n\sum_{m=1}^n(S_T^{(m)}-K)^+w_m")
        st.caption("The interval reflects Monte Carlo sampling, not future market returns; antithetic pairing is not fully reflected in its reported standard error.")

    with st.expander("3. Greeks and dynamic hedging"):
        st.markdown("""- Estimate **delta, gamma and vega** with central finite differences using common random numbers.
- Use a vanilla Black–Scholes call to hedge vega (optional), then hold stock to offset remaining delta.
- Simulate **21 trading days**, rebalance once daily, subtract proportional transaction costs and track cumulative P&L.
- The simulated realized barrier is checked at **four intraday observations per day**; pricing assumes continuous monitoring.""")
        st.latex(r"\Delta\approx\frac{V(S+h)-V(S-h)}{2h}")
        st.latex(r"H_C=-\frac{q\nu}{\nu_C},\qquad H_S=-q\Delta-H_C\Delta_C")
        st.caption("q is the short exotic quantity, H_C the vanilla-call hedge and H_S the stock hedge; when vega hedging is off, H_C = 0.")

    with st.expander("4. How to interpret the results"):
        st.markdown("""**Read the dashboard:** *Price & confidence* shows the premium and Monte Carlo stability; *Barrier sensitivity* shows Greeks near knock-out; *Hedging desk* shows inventory and P&L; *Scenario analysis* shows spot/volatility stresses.

**Check:** the option should be worth zero when spot is already at or above the barrier; it should not exceed the matching vanilla call; repeated seeds should give repeatable results.

**Limitations:** constant volatility, no dividends, no jumps, no volatility smile or market liquidity model. Finite-difference Greeks can be unstable near the barrier; delta–vega hedging cannot eliminate knock-out gap risk.""")

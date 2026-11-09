"""Callable bond workstation using the existing short-rate lattice engine."""
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from engines.models import callable_bond, bond_risk, simulate_callable, zero_rate

st.set_page_config(page_title="Callable Bond | Ayoub El Ammari", page_icon="💵", layout="wide", initial_sidebar_state="expanded")

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
header("FICC / RATES & STRUCTURED CREDIT", "Callable Bond Workstation",
       "10Y semiannual coupon bond · Issuer call at year 5 · Calibrated short-rate lattice & swap proxy hedge")
with st.sidebar:
    st.header("Security terms")
    face=st.number_input("Face value ($)",100000,20000000,1000000,100000)
    coupon=st.slider("Annual coupon (%)",1.,10.,5.,.25)
    st.divider()
    st.subheader("Curve & model")
    y1=st.slider("1-year zero rate (%)",0.,8.,2.,.1)/100
    y5=st.slider("5-year zero rate (%)",0.,8.,2.5,.1)/100
    y10=st.slider("10-year zero rate (%)",0.,8.,3.,.1)/100
    sigma=st.slider("Short-rate volatility (percentage points)",.25,3.,1.2,.05)/100
    st.subheader("Hedge simulation")
    daily=st.slider("Daily parallel shift volatility (bps)",1.,15.,5.,1.)
    cost=st.slider("Swap turnover cost (bps)",0.,5.,.25,.25)
    seed=st.number_input("Random seed",value=21,step=1)
    run=st.button("Reprice bond & hedge",type="primary",use_container_width=True)
    st.caption("Simulated curves and rates; no live market feed.")

@st.cache_data(show_spinner=False)
def compute(face,coupon,y1,y5,y10,sigma,daily,cost,seed):
    curve={1.:y1,5.:y5,10.:y10}
    mark=callable_bond(curve,coupon=coupon,sigma_r=sigma)
    risk=bond_risk(curve,coupon=coupon,sigma_r=sigma)
    hedge=simulate_callable(face=face,coupon=coupon,sigma_r=sigma,daily_shift_bps=daily,
                            cost_bps=cost,seed=seed,base_curve=curve)
    return mark,risk,hedge

inputs=(face,coupon,y1,y5,y10,sigma,daily,cost,seed)
if run or "bond_results" not in st.session_state:
    with st.spinner("Calibrating rate tree and simulating 63 hedging days..."):
        try:
            payload=compute(*inputs)
        except Exception as exc:
            st.error(f"Valuation failed: {exc}")
            st.stop()
        st.session_state.bond_results=payload
        st.session_state.bond_inputs=inputs
if inputs!=st.session_state.bond_inputs:
    st.warning("Inputs have changed. Click **Reprice bond & hedge** to refresh the displayed results.")
mark,risk,df=st.session_state.bond_results
face_used,coupon_used,y1_used,y5_used,y10_used,sigma_used,*_=st.session_state.bond_inputs
k1,k2,k3,k4=st.columns(4)
k1.metric("Callable model price / $100",f"${mark['price']:.3f}")
k2.metric("Embedded issuer option / $100",f"${mark['option_value']:.3f}")
k3.metric("Modeled bond DV01",f"${risk['dv01']*face_used/100:,.2f}/bp")
k4.metric("Effective duration (parallel)",f"{risk['modified_duration']:.2f} yr")
st.caption(f"YTM (no call): {mark['ytm']:.2%} · Hypothetical year-5 YTC: {mark['ytc']:.2%} · Model convexity: {risk['convexity']:,.2f}. YTC is not a forecast of exercise.")
t1,t2,t3,t4,t5=st.tabs(["Valuation", "Curve & callability", "Hedge performance", "Risk report & assumptions", "Model Guide"])
with t1:
    left,right=st.columns([1.6,1])
    with left:
        shifts=np.arange(-150,151,15)
        results=[]
        for bp in shifts:
            shifted={1.:max(.0001,y1_used+bp/10000),5.:max(.0001,y5_used+bp/10000),10.:max(.0001,y10_used+bp/10000)}
            value=callable_bond(shifted,coupon=coupon_used,sigma_r=sigma_used)
            results.append((bp,value['price'],value['noncall_price']))
        r=pd.DataFrame(results,columns=["Shift (bp)","Callable","Non-callable"])
        f=go.Figure()
        f.add_trace(go.Scatter(x=r.iloc[:,0],y=r['Callable'],name="Callable",line=dict(color=PALETTE['amber'],width=3)))
        f.add_trace(go.Scatter(x=r.iloc[:,0],y=r['Non-callable'],name="Non-callable",line=dict(color=PALETTE['blue'],width=3)))
        f.update_layout(title="Price versus parallel curve shift",xaxis_title="Parallel shift (basis points)",yaxis_title="Price per $100")
        chart(f,410)
    with right:
        st.subheader("Valuation bridge")
        bridge=pd.DataFrame({"Measure":["Non-callable model price","Less: issuer call option","Callable model price"],
                            "$/100":[mark['noncall_price'],-mark['option_value'],mark['price']]})
        st.dataframe(bridge,hide_index=True,use_container_width=True)
        st.metric("Call-option cost",f"{mark['option_value']/mark['noncall_price']:.2%} of bullet price")
        st.info("Issuer call at par after the year-5 coupon. Lower interest rates may cap callable price appreciation.")
with t2:
    maturities=np.linspace(.5,10,40)
    curve={1.:y1_used,5.:y5_used,10.:y10_used}
    f=go.Figure(go.Scatter(x=maturities,y=[100*zero_rate(curve,t) for t in maturities],mode="lines",line=dict(color=PALETTE['teal'],width=3)))
    f.update_layout(title="Input zero-coupon term structure (interpolated)",xaxis_title="Tenor (years)",yaxis_title="Continuously compounded zero rate (%)")
    chart(f)
    exercise=mark['call_exercise_states']
    if exercise is not None:
        st.metric("Year-5 lattice states in issuer-call region",f"{int(np.sum(exercise))} / {len(exercise)}")
    st.caption("This state count is not an exercise probability. Calibrated additive short-rate lattice; state-by-state issuer exercise at year 5.")
with t3:
    left,right=st.columns(2)
    with left:
        f=go.Figure()
        f.add_trace(go.Scatter(x=df.day,y=df.hedged_pnl,name="Hedged (net)",line=dict(color=PALETTE['teal'],width=3)))
        f.add_trace(go.Scatter(x=df.day,y=df.unhedged_pnl,name="Unhedged",line=dict(color=PALETTE['blue'],width=2)))
        f.update_layout(title="63-day cumulative P&L",xaxis_title="Day",yaxis_title="USD")
        chart(f)
    with right:
        f=go.Figure()
        f.add_trace(go.Scatter(x=df.day,y=df.swap_notional,name="Pay-fixed swap proxy",line=dict(color=PALETTE['amber'])))
        f.update_layout(title="Rebalanced swap hedge notional",xaxis_title="Day",yaxis_title="USD")
        chart(f)
    c1,c2,c3=st.columns(3)
    c1.metric("Hedged net P&L",f"${df.hedged_pnl.iloc[-1]:,.0f}")
    c2.metric("Unhedged P&L",f"${df.unhedged_pnl.iloc[-1]:,.0f}")
    c3.metric("Swap turnover costs",f"${df.trading_cost.sum():,.2f}")
    st.caption("The swap hedge is a first-order annuity approximation; this is not an independently marked swap pricing engine.")
with t4:
    f=go.Figure()
    for key,name,color in [("bond_pnl","Bond",PALETTE['blue']),("swap_pnl","Swap proxy",PALETTE['teal']),("trading_cost","Costs",PALETTE['red'])]:
        f.add_trace(go.Bar(x=df.day,y=-df[key] if key=='trading_cost' else df[key],name=name,marker_color=color))
    f.update_layout(title="Daily modeled P&L attribution",xaxis_title="Day",yaxis_title="USD",barmode="relative")
    chart(f)
    st.dataframe(df.round(5),hide_index=True,use_container_width=True,height=320)
    downloadable_frame(df,"callable_bond_risk_63_days.csv")
    st.warning("Educational additive short-rate tree, not issuer-specific OAS calibration. No issuer credit spread, funding, curve basis, swap carry, market impact or full revaluation of an actual swap. All simulated curve shocks are parallel.")

# Detailed source-aligned technical reference.
with t5:
    st.subheader("Model guide — Callable bond pricing and rates hedging")
    st.caption("Technical description checked against the implemented lattice and hedge simulator; model outputs use synthetic zero curves.")
    with st.expander("1. Contract, curve conventions and trading objective", expanded=True):
        render_model_guide(r"""
**Goal.** Price an issuer-callable fixed-rate bond by **state-dependent optimal call exercise**, measure its sensitivity to zero-rate shifts, and simulate a first-order **pay-fixed swap proxy** hedge.

| Model input | Meaning |
|---|---|
| Face | User-chosen dollar investment; quoted model price is per $100 face |
| Coupon | User-chosen annual coupon percent on $100 par, paid semiannually |
| Maturity / exercise | 10 years maturity; a single issuer call at **year 5** for $100 par |
| Zero curve | Continuously compounded 1-, 5- and 10-year zero rates |
| Intermediate zero rates | Linear interpolation, flat extrapolation at curve ends |
| Rate volatility | User-selected additive short-rate tree displacement parameter |
| Rate replay | 63 trading days with seeded parallel zero-rate changes |

A zero-coupon discount factor is obtained directly from the interpolated curve:

$$P(0,T)=\exp[-z(T)T].$$

If the semiannual coupon amount is $c=C/2$ dollars per $100 par and dates are $t_k=k/2$, the matching **non-callable bullet price** is

$$V_{\mathrm{bullet}}=\sum_{k=1}^{20}cP(0,t_k)+100P(0,10).$$

Because the issuer may redeem early, the holder's callable bond has a lower or equal model price (under these conventions):

$$V_{\mathrm{callable}}=V_{\mathrm{bullet}}-V_{\mathrm{issuer\ call}}.$$

The option cost in the dashboard is this **price difference**, not the market price of a separately tradable call option.
""")
    with st.expander("2. Calibrated recombining short-rate lattice and exercise"):
        render_model_guide(r"""
The implementation builds a **20-step recombining additive short-rate tree**, with $\Delta t=1/2$ year and equal risk-neutral transition probabilities. At time step $n$, state $j$ has short rate

$$r_{n,j}=a_n+\sigma_r\sqrt{\Delta t}(2j-n),\qquad j=0,\ldots,n.$$

The time-dependent center $a_n$ is chosen to reproduce the **market-implied discount factor** $P(0,t_{n+1})$. Let $Q_{n,j}$ denote the state price (present value weight) arriving at state $(n,j)$. Then

$$P(0,t_{n+1})=\sum_j Q_{n,j}e^{-r_{n,j}\Delta t}.$$

Writing $r_{n,j}=a_n+b_{n,j}$ yields the calibration identity

$$a_n=-\frac1{\Delta t}\log\left[\frac{P(0,t_{n+1})}{\sum_j Q_{n,j}e^{-b_{n,j}\Delta t}}\right].$$

State prices are advanced after discounting, with each node's discounted weight split equally between its two children.

At maturity, the holder receives principal plus final coupon. Backward induction uses the discounted expected value of next-step bond values:

$$\mathrm{Cont}_{n,j}=e^{-r_{n,j}\Delta t}\frac{V_{n+1,j}+V_{n+1,j+1}}2.$$

At coupon dates, the coupon is added after discounting the continuation value. At the **year-5 call date only**, the issuer exercises if the continuation value exceeds the call redemption of $100:

$$V_{\mathrm{call},j}=c+\min(100,\mathrm{Cont}_{\mathrm{call},j}).$$

At other intermediate coupon dates $V_{n,j}=c+\mathrm{Cont}_{n,j}$; initial time zero has no immediate coupon. The final price is the value at the tree root. The dashboard's call-region state count is **not** an exercise probability.
""")
    with st.expander("3. Yield measures, DV01, duration and convexity"):
        render_model_guide(r"""
The bond's **yield to maturity (YTM)** is the scalar yield $y$ solving a semiannual compounded bullet-style yield equation for the **callable model price**:

$$V_{\mathrm{callable}}=\sum_{k=1}^{20}\frac{c}{(1+y/2)^k}+\frac{100}{(1+y/2)^{20}}.$$

**Yield to call (YTC)** solves the analogous equation over ten semiannual periods with $100$ redeemed at year five. These are conventional cash-flow IRRs based on hypothetical holding outcomes; **they do not incorporate a probabilistic call schedule**. The implementation does not separately calculate yield-to-worst.

The rate sensitivities come from **full repricing** at parallel shifts of **plus and minus 1 basis point**, where $1\text{ bp}=10^{-4}$:

$$\mathrm{DV01}_{\$100}=\frac{V(z-1\mathrm{bp})-V(z+1\mathrm{bp})}{2}.$$

The quantity is in **dollars per one-basis-point shift per $100 face**; it is generally positive for a long bond. The effective modified-duration proxy is

$$D_{\mathrm{eff}}=\frac{\mathrm{DV01}_{\$100}}{V_0(10^{-4})}.$$

The implemented effective convexity is

$$\mathcal C_{\mathrm{eff}}=\frac{V_-+V_+-2V_0}{V_0(10^{-4})^2}.$$

Issuer callability can reduce upside price sensitivity as rates fall and may produce **negative convexity in some rate regions**. The model does **not** compute bucketed/key-rate DV01 or issuer-specific spread duration.
""")
    with st.expander("4. Pay-fixed swap proxy and simulated P&L"):
        render_model_guide(r"""
Every simulated day, the three input zero rates receive the same accumulated stochastic shift. The daily shocks are seeded Gaussian draws with the user-selected basis-point standard deviation; zero yields are floored at a small positive value in the replay.

A 5-year semiannual **discount annuity per dollar notional** is computed as

$$A_5=\sum_{k=1}^{10}\tfrac12 P(0,k/2).$$

The model treats the **5-year zero rate** as a *proxy* for a 5-year swap rate and uses the bond's face-scaled DV01 to choose pay-fixed exposure:

$$\mathrm{DV01}_{\mathrm{bond},\$}=\mathrm{DV01}_{\$100}\frac{\mathrm{face}}{100},\qquad
N_{\mathrm{swap}}=\frac{\mathrm{DV01}_{\mathrm{bond},\$}}{A_5(10^{-4})}.$$

For a pay-fixed swap proxy, the model attributes daily hedge P&L from **yesterday's notional** to the change in 5-year rate:

$$\mathrm{PnL}^{\mathrm{swap}}_t=N_{t-1}A_{5,t}(z_{5,t}-z_{5,t-1}).$$

Bond P&L is daily price change times face divided by 100. Simulated net daily P&L is

$$\mathrm{PnL}^{\mathrm{net}}_t=\mathrm{PnL}^{\mathrm{bond}}_t+\mathrm{PnL}^{\mathrm{swap}}_t-\frac{b}{10^4}|N_t-N_{t-1}|.$$

The swap P&L is a **local duration/annuity approximation**, not an independently valued swap with full fixed/floating cash flows, carry or margin. The hedge is designed for approximately parallel interest-rate movements; it is not a curve-shape hedge.
""")
    with st.expander("5. Model-building walkthrough, tests and limitations"):
        render_model_guide(r"""
**Implementation sequence:** (1) construct and interpolate the zero curve; (2) compute discount factors; (3) propagate risk-neutral state prices and calibrate the additive short-rate center at every date; (4) value the bond backward with the issuer's year-5 exercise rule; (5) compute YTM and YTC; (6) bump the entire curve for DV01, duration and convexity; (7) replay 63 parallel-rate shocks, reprice and rebalance the swap proxy; (8) accumulate bond, proxy-hedge and trading-cost P&L; (9) export the ledger.

**Consistency checks:** discount factors matched by lattice calibration; callable price should not exceed the corresponding bullet price; issuer option cost should be nonnegative under consistent inputs; down/up shock prices should be finite; if exercise is never optimal, callable and non-callable prices should be close; simulated P&L should reproduce with the same seed. Check that the issuer exercise condition uses **continuation before adding that date's coupon**.

**What the model omits:** issuer default/credit spreads and OAS calibration; stochastic curve shapes and volatility term structure; negative-rate realism, stochastic spread dynamics and exercise behavior beyond one call date; full swap valuation, accrual/coupon carry, financing, funding, curve basis, bid/ask, margin and liquidity. The short-rate lattice is an educational calibrated additive tree, **not a production Hull–White calibration**.

**Source code:** `engines/models.py` (`zero_rate`, `zero_discount`, `bond_ytm`, `callable_bond`, `bond_risk`, `simulate_callable`).
""")

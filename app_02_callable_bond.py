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


# Concise technical reference; pricing and dashboard logic above is unchanged.
with t5:
    st.subheader("Model Guide | Callable Bond")
    st.caption("A quick walkthrough of cash flows, the interest-rate tree and the hedge approximation.")

    with st.expander("1. What is the product?", expanded=True):
        st.markdown("""**Bond:** 10-year fixed-rate bond paying coupons every **six months**, with one **issuer call at year 5** at par.

- If the issuer calls, the investor receives the coupon and the redemption amount instead of future coupons.
- This option benefits the **issuer**, so the callable bond is worth no more than the comparable non-callable bond under the same assumptions.
- Dashboard prices are quoted **per $100 face value**; the sidebar face value scales dollar exposures.""")
        st.latex(r"V_{\mathrm{callable}}=V_{\mathrm{bullet}}-V_{\mathrm{issuer\ option}}")

    with st.expander("2. How is the bond priced?"):
        st.markdown("""- Build a zero-rate curve from the **1Y, 5Y and 10Y** inputs and derive discount factors.
- Calibrate a **20-step recombining additive short-rate lattice** (six-month intervals) to that curve.
- Work backward through the tree: discount expected cash flows, add each coupon and, at year 5, apply the issuer's optimal call decision.""")
        st.latex(r"P(0,T)=e^{-z(T)T}")
        st.latex(r"V_{\mathrm{call},j}=c+\min\big(100,\mathrm{Continuation}_j\big)")
        st.caption("Here c is the six-month coupon per $100 face. The call decision is applied before adding that day's coupon.")

    with st.expander("3. Interest-rate risk and hedging"):
        st.markdown("""- Reprice after **±1 basis-point parallel rate shifts** to estimate DV01; use the same bumps for effective duration and convexity.
- Compare callable and non-callable price curves; callability can limit upside when rates fall.
- Run a **63-day simulated rate scenario** and hedge first-order interest-rate risk with a dynamically sized **5-year pay-fixed swap proxy**.
- Display hedged versus unhedged P&L and turnover costs.""")
        st.latex(r"\mathrm{DV01}_{\$100}=\frac{V(z-1\,\mathrm{bp})-V(z+1\,\mathrm{bp})}{2}")
        st.latex(r"N_{\mathrm{swap}}\approx\frac{\mathrm{DV01}_{\mathrm{bond}}}{A_5\times10^{-4}}")
        st.caption("A₅ is the five-year fixed-leg discount annuity per dollar notional; the swap is an approximation, not fully priced separately.")

    with st.expander("4. How to interpret the results"):
        st.markdown("""**Read the dashboard:** *Valuation* shows issuer option cost and price curves; *Curve & callability* shows the fitted input curve and call region; *Hedge performance* compares P&L; *Risk report* shows attribution and data.

**Check:** the callable price should not exceed the bullet price; the issuer option value should not be negative; repeated seeds should reproduce the rate simulation.

**Limitations:** one call date, educational additive lattice, no issuer credit or OAS calibration, no key-rate hedging and no full swap cash-flow/mark-to-market engine. YTM and YTC describe hypothetical cash-flow outcomes, **not predicted exercise**.""")

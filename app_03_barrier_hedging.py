"""Streamlit dashboard: Project 3 — barrier option pricing and delta-vega hedging."""
import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
from engines.models import barrier_mc,barrier_greeks,simulate_barrier_hedge,shocks

st.set_page_config(page_title='Equity Exotics | Barrier Hedge',page_icon='📈',layout='wide')
st.title('Equity Exotics | Barrier Option Pricing & Hedging')
st.caption('Up-and-out European call · Antithetic MC + Brownian bridge · Stock and vanilla-call hedges')
with st.sidebar:
    st.header('Trade parameters')
    spot=st.number_input('Spot ($)',min_value=1.,value=100.,step=1.)
    strike=st.number_input('Strike ($)',min_value=1.,value=100.,step=1.)
    barrier=st.number_input('Upper knock-out barrier ($)',min_value=1.,value=120.,step=1.)
    vol=st.slider('Implied volatility (%)',1.,70.,25.,1.)/100
    rf=st.slider('Risk-free rate (%)',0.,10.,2.,.25)/100
    maturity=st.slider('Maturity (years)',.25,2.,1.,.25)
    paths=st.select_slider('Monte Carlo paths',options=[500,1000,2000,5000,10000],value=2000)
    quantity=st.number_input('Number of options sold',100,100000,1000,100)
    hedge_vega=st.toggle('Hedge vega with vanilla calls',value=True)
    costs=st.slider('Transaction costs (bps)',0.,10.,1.,.5)
    seed=st.number_input('Random seed',value=31,step=1)
    run=st.button('Run Monte Carlo & hedging',type='primary',use_container_width=True)

@st.cache_data(show_spinner=False)
def compute(spot,strike,barrier,vol,rf,maturity,paths,quantity,hedge_vega,costs,seed):
    z=shocks(paths,63,1,seed+10)
    mark=barrier_mc(spot,strike,barrier,rf,maturity,vol,z=z)
    g=barrier_greeks(spot,strike,barrier,rf,maturity,vol,z)
    hedge=simulate_barrier_hedge(s0=spot,k=strike,barrier=barrier,r=rf,t=maturity,
             sigma=vol,n=paths,contracts=-quantity,cost_bps=costs,hedge_vega=hedge_vega,seed=seed)
    return mark,g,hedge

if run or 'barrier_data' not in st.session_state:
    with st.spinner('Pricing barrier and rebalancing 21-day hedge...'):
        st.session_state.barrier_data=compute(spot,strike,barrier,vol,rf,maturity,paths,quantity,hedge_vega,costs,seed)
mark,g,df=st.session_state.barrier_data
k1,k2,k3,k4=st.columns(4)
k1.metric('MC barrier option price',f"${mark['price']:.4f}")
k2.metric('95% confidence interval',f"${mark['ci_low']:.3f}–${mark['ci_high']:.3f}")
k3.metric('Delta',f"{g['delta']:+.4f}")
k4.metric('Vega / 1.00 σ',f"{g['vega']:+.3f}")
st.caption(f"Estimated risk-neutral knock-out probability: {mark['ko_probability']:.1%} | Initial gamma: {g['gamma']:.4f} | 21-day hedged P&L: ${df.cumulative_pnl.iloc[-1]:,.2f}")
t1,t2,t3,t4=st.tabs(['Valuation & convergence','Greeks near barrier','Daily hedges & P&L','Positions / export'])
with t1:
    # Reprice at a handful of sample counts so students can inspect confidence interval shrinkage.
    counts=[500,1000,2000,5000]
    conv=[]
    for n in counts:
        x=barrier_mc(spot,strike,barrier,rf,maturity,vol,n=n,steps=63,seed=seed+10)
        conv.append(dict(paths=n,price=x['price'],lower=x['ci_low'],upper=x['ci_high']))
    st.plotly_chart(px.line(pd.DataFrame(conv),x='paths',y=['price','lower','upper'],markers=True,title='MC convergence with 95% confidence bounds'),use_container_width=True)
    st.caption('Monte Carlo 95% intervals describe sampling uncertainty under the assumed model, not uncertainty about future market prices.')
with t2:
    if barrier<=spot:st.info('Current spot is at or above the upper barrier: the up-and-out call has already knocked out.')
    else:
        grid=np.linspace(max(1.,spot*.75),barrier*.999,22)
        z=shocks(min(paths,2000),63,1,seed+10)
        data=[]
        for x in grid:
            greeks=barrier_greeks(x,strike,barrier,rf,maturity,vol,z)
            data.append(dict(spot=x,delta=greeks['delta'],vega=greeks['vega']))
        sens=pd.DataFrame(data)
        c1,c2=st.columns(2)
        with c1:st.plotly_chart(px.line(sens,x='spot',y='delta',title='Delta vs spot approaching upper barrier'),use_container_width=True)
        with c2:st.plotly_chart(px.line(sens,x='spot',y='vega',title='Vega vs spot approaching upper barrier'),use_container_width=True)
    st.caption('Common random numbers stabilize finite-difference Greeks. Estimates can remain noisy close to a discontinuous knock-out boundary.')
with t3:
    c1,c2=st.columns(2)
    with c1:st.plotly_chart(px.line(df,x='day',y='cumulative_pnl',title='Cumulative net hedge P&L ($)'),use_container_width=True)
    with c2:st.plotly_chart(px.line(df,x='day',y=['stock_hedge','vanilla_hedge'],title='Stock and vanilla call inventories (units)'),use_container_width=True)
    st.caption(f"Total turnover costs: ${df.cost.sum():,.2f}. Barrier observed breached on hedge path: {'Yes' if df.knocked_out.any() else 'No'}.")
with t4:
    st.dataframe(df.round(5),use_container_width=True,height=350)
    st.download_button('Download daily hedge CSV',df.to_csv(index=False).encode(),'barrier_hedge.csv','text/csv')
    st.warning('Pricing uses continuous-monitoring bridge survival. The simulated realized stock path checks four points per trading day, so realized intraday barrier hits can be missed. Vanilla hedges are same-strike calls; transactions are valued at mid plus a configurable proportional cost, excluding bid/ask and gap losses.')

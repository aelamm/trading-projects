"""Streamlit dashboard: Project 2 — callable bond and swap management."""
import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
from engines.models import callable_bond,bond_risk,simulate_callable

st.set_page_config(page_title='FICC Exotics | Callable Bond',page_icon='💵',layout='wide')
st.title('FICC Exotics | Callable Bond Desk')
st.caption('10-year semiannual coupon bond · Issuer call after year 5 · Calibrated short-rate tree')
with st.sidebar:
    st.header('Bond & risk settings')
    face=st.number_input('Position face value ($)',100000,20000000,1000000,100000)
    coupon=st.slider('Annual coupon (%)',1.,10.,5.,.25)
    y1=st.slider('1-year zero rate (%)',0.,8.,2.,.10)/100
    y5=st.slider('5-year zero rate (%)',0.,8.,2.5,.10)/100
    y10=st.slider('10-year zero rate (%)',0.,8.,3.,.10)/100
    sigma=st.slider('Short-rate volatility (percentage points)',.25,3.,1.2,.05)/100
    daily=st.slider('Daily parallel curve shift volatility (bps)',1.,15.,5.,1.)
    hedge_cost=st.slider('Swap turnover cost (bps)',0.,5.,.25,.25)
    seed=st.number_input('Random seed',value=21,step=1)
    go=st.button('Reprice and simulate 63 days',type='primary',use_container_width=True)

@st.cache_data(show_spinner=False)
def compute(face,coupon,y1,y5,y10,sigma,daily,hedge_cost,seed):
    curve={1.:y1,5.:y5,10.:y10}
    mark=callable_bond(curve,coupon=coupon,sigma_r=sigma)
    risk=bond_risk(curve,coupon=coupon,sigma_r=sigma)
    path=simulate_callable(face=face,coupon=coupon,sigma_r=sigma,daily_shift_bps=daily,
                           cost_bps=hedge_cost,seed=seed,base_curve=curve)
    return mark,risk,path

if go or 'bond_data' not in st.session_state:
    with st.spinner('Calibrating rate tree and running swap hedge...'):
        st.session_state.bond_data=compute(face,coupon,y1,y5,y10,sigma,daily,hedge_cost,seed)
mark,risk,df=st.session_state.bond_data
k1,k2,k3,k4=st.columns(4)
k1.metric('Callable price / $100',f"${mark['price']:.3f}")
k2.metric('Issuer call option / $100',f"${mark['option_value']:.3f}")
k3.metric('YTM',f"{mark['ytm']:.2%}")
k4.metric('YTC (hypothetical)',f"{mark['ytc']:.2%}")
st.caption(f"Initial duration: {risk['modified_duration']:.2f} years | initial bond DV01: ${risk['dv01']*face/100:,.2f}/bp | convexity: {risk['convexity']:.1f}")
t1,t2,t3=st.tabs(['Callable valuation','63-day swap hedge','Daily risk report / export'])
with t1:
    st.write('The bond is priced with a recombining short-rate tree calibrated to the interpolated zero curve. The issuer can call at par after receiving the year-5 coupon.')
    shifts=np.arange(-150,151,10)
    series=[]
    for bps in shifts:
        shifted={1.:max(.0001,y1+bps/10000),5.:max(.0001,y5+bps/10000),10.:max(.0001,y10+bps/10000)}
        x=callable_bond(shifted,coupon=coupon,sigma_r=sigma)
        series.append(dict(shift_bps=bps,callable=x['price'],noncallable=x['noncall_price']))
    st.plotly_chart(px.line(pd.DataFrame(series),x='shift_bps',y=['callable','noncallable'],title='Price sensitivity: callable vs vanilla bond'),use_container_width=True)
    st.caption('YTC assumes repayment at year 5; it is not a prediction of issuer exercise. YTM assumes the bond is never called.')
with t2:
    c1,c2=st.columns(2)
    with c1:st.plotly_chart(px.line(df,x='day',y=['hedged_pnl','unhedged_pnl'],title='Hedged vs unhedged cumulative P&L ($)'),use_container_width=True)
    with c2:st.plotly_chart(px.line(df,x='day',y=['bond_pnl','swap_pnl'],title='Daily bond and swap P&L ($)'),use_container_width=True)
    st.caption(f"Final hedged P&L: ${df.hedged_pnl.iloc[-1]:,.0f}; unhedged P&L: ${df.unhedged_pnl.iloc[-1]:,.0f}; swap rebalancing costs: ${df.trading_cost.sum():,.0f}.")
with t3:
    st.plotly_chart(px.line(df,x='day',y='swap_notional',title='Daily pay-fixed swap notional ($)'),use_container_width=True)
    st.dataframe(df.round(5),use_container_width=True,height=320)
    st.download_button('Download 63-day bond CSV',df.to_csv(index=False).encode(),'callable_bond_hedging.csv','text/csv')
    st.warning('Model limits: this is an illustrative additive short-rate lattice, not an issuer-specific OAS calibration. Swaps are valued by a first-order par-swap annuity approximation; curve basis, swap carry, funding, credit and market-impact risks are excluded. Simulation uses parallel rate shifts.')

"""Streamlit dashboard: Project 1 — Commodity exotic book management."""
import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
from engines.models import simulate_book, rainbow_mc, barrier_mc, shocks

st.set_page_config(page_title='Exotics Desk | Commodity Book', page_icon='📊',layout='wide')
st.title('Commodity Exotics | Trading Book Management')
st.caption('Exotic Trading — Barrier and Rainbow Options · Synthetic markets · Educational research')
with st.sidebar:
    st.header('Book & scenario parameters')
    contracts_b=st.number_input('Short oil barrier contracts',1,100,20)
    contracts_r=st.number_input('Short rainbow notes',1,20,4)
    rainbow_nominal=st.number_input('Rainbow payoff notional ($)',10000,1000000,100000,step=10000)
    upper=st.slider('Oil upper KO barrier ($/bbl)',85.,130.,100.,1.)
    corr=st.slider('Pairwise cross-asset correlation',-.40,.90,.50,.05)
    spike=st.slider('Volatility-spike day',1,20,10)
    mult=st.slider('Post-shock volatility multiplier',1.,3.,2.,.25)
    paths=st.select_slider('MC paths',options=[400,800,1200,2000],value=1200)
    seed=st.number_input('Random seed',value=17,step=1)
    costs=st.slider('Transaction cost (bps)',0.,10.,1.,.5)
    vega_hedge=st.toggle('Oil vanilla parallel-vega proxy hedge',value=True)
    run=st.button('Run trading-book simulation',type='primary',use_container_width=True)

@st.cache_data(show_spinner=False)
def compute(contracts_b,contracts_r,rainbow_nominal,upper,corr,spike,mult,paths,seed,costs,vega_hedge):
    return simulate_book(barrier_contracts=-contracts_b,rainbow_contracts=-contracts_r,
            rainbow_notional=rainbow_nominal,barrier=upper,corr=corr,spike_day=spike,
            vol_multiplier=mult,n=paths,seed=seed,cost_bps=costs,hedge_vega=vega_hedge)

if run or 'book' not in st.session_state:
    with st.spinner('Pricing correlated paths and rebalancing hedges...'):
        st.session_state.book=compute(contracts_b,contracts_r,rainbow_nominal,upper,corr,spike,mult,paths,seed,costs,vega_hedge)
df=st.session_state.book
last=df.iloc[-1]
a,b,c,d=st.columns(4)
a.metric('Final book P&L',f"${last.cumulative_pnl:,.0f}")
b.metric('Total hedge + unwind costs',f"${df.transaction_cost.sum():,.0f}")
c.metric('P&L daily volatility',f"${df.daily_pnl.iloc[1:].std():,.0f}")
d.metric('Exotics unwound',f"{last.unwound_pct:.0%}")
t1,t2,t3,t4=st.tabs(['P&L and prices','Greeks and hedges','Volatility stress & unwind','Trade blotter / export'])
with t1:
    c1,c2=st.columns(2)
    with c1:st.plotly_chart(px.line(df,x='day',y='cumulative_pnl',title='Cumulative hedged book P&L ($)'),use_container_width=True)
    with c2:st.plotly_chart(px.line(df,x='day',y=['oil','gold','copper'],title='Commodity spot markets — absolute prices'),use_container_width=True)
    st.caption('Oil is in USD/bbl, gold in USD/oz, copper in USD/lb. Different absolute scales: use Greeks/hedges for risk comparisons.')
with t2:
    c1,c2=st.columns(2)
    with c1:st.plotly_chart(px.line(df,x='day',y=['hedge_oil','hedge_gold','hedge_copper'],title='Daily delta hedge units'),use_container_width=True)
    with c2:st.plotly_chart(px.line(df,x='day',y=['barrier_vega','rainbow_vega'],title='Unscaled option vega: $ per 1.00 volatility'),use_container_width=True)
    st.plotly_chart(px.line(df,x='day',y='vanilla_hedge',title='Oil vanilla-call vega-proxy hedge quantity'),use_container_width=True)
    st.caption('Vega is presented per option/structured note, before portfolio position and contract multiplier. The oil vanilla hedge offsets one parallel-vega proxy, not all three individual commodity vegas. Underlying hedge quantities include multipliers.')
with t3:
    c1,c2=st.columns(2)
    with c1:st.plotly_chart(px.line(df,x='day',y='oil_vol',title='Oil volatility regime'),use_container_width=True)
    with c2:st.plotly_chart(px.line(df,x='day',y=['barrier_contracts','rainbow_contracts'],title='Staged unwinding of short option inventory'),use_container_width=True)
    st.info('Unwind rule: when post-spike maximum implied volatility exceeds 30%, reduce each exotic position in five equal daily increments. Positions are closed at modeled fair value. No market-impact/slippage model is included beyond configured turnover costs.')
with t4:
    st.dataframe(df.round(4),use_container_width=True,height=350)
    st.download_button('Download daily book CSV',df.to_csv(index=False).encode(),'commodity_exotics_book.csv','text/csv')
    st.markdown('**Risk notes:** The rainbow best-of call pays the positive maximum percentage return across oil, gold, and copper (not the maximum absolute asset price). Correlated GBM is a simplification. Barrier marks use continuous-monitoring Brownian bridges; the realized hedge path checks oil four times each trading day, so intraday barrier misses remain possible.')

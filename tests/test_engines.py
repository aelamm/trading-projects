import numpy as np
from engines.models import (barrier_mc,barrier_greeks,vanilla_call,rainbow_mc,
  rainbow_greeks,shocks,callable_bond,bond_risk,simulate_book,simulate_callable,
  simulate_barrier_hedge)

def test_barrier_immediate_knockout_and_vanilla_bound():
    assert barrier_mc(s=120,barrier=120)['price']==0
    x=barrier_mc(n=2000)
    assert 0 < x['price'] < vanilla_call(100,100,.02,1,.25)['price']
    assert x['ci_low'] < x['price'] < x['ci_high']
    assert 0<=x['ko_probability']<=1

def test_rainbow_greeks_and_correlation():
    z=shocks(400,25,3,2)
    p=rainbow_mc(z=z)
    g=rainbow_greeks(np.array([78.,2650.,4.]),np.array([.25,.15,.20]),.5,.02,1.,z)
    assert p['price']>0
    assert g['delta'].shape==(3,)
    assert np.allclose(g['cross_gamma'],g['cross_gamma'].T)

def test_callable_exercise_and_dv01():
    c={1.:.02,5.:.025,10.:.03}
    p=callable_bond(c)
    assert p['noncall_price']>=p['price']>0
    assert p['option_value']>=0
    assert bond_risk(c)['dv01']>0

def test_all_three_daily_simulations():
    book=simulate_book(n=400)
    callable_path=simulate_callable(days=5)
    barrier_path=simulate_barrier_hedge(n=400)
    assert len(book)==22 and len(callable_path)==6 and len(barrier_path)==22
    assert book['cumulative_pnl'].notna().all()
    assert book['rainbow_cross_gamma_og'].notna().all()
    assert 'vanilla_hedge' in book
    assert callable_path['hedged_pnl'].notna().all()
    assert barrier_path['cumulative_pnl'].notna().all()
    assert np.isfinite(book.select_dtypes('number').to_numpy()).all()

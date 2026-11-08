"""Research-grade educational models. All price paths/data are synthetic, not market quotes."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import brentq

DAYS = 252


def shocks(n=2000, steps=63, dim=1, seed=42):
    """Antithetic standard normal shocks; n is total samples (rounded up to even)."""
    if n < 2 or steps < 1 or dim < 1:
        raise ValueError('n >= 2, steps >= 1, dim >= 1 required')
    n = 2 * int(np.ceil(n / 2))
    base = np.random.default_rng(seed).standard_normal((n // 2, steps, dim))
    return np.concatenate((base, -base), axis=0)


def gbm_paths(s0, sigma, r, t, z, q=0):
    s0 = np.asarray(s0, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    n, steps, dim = z.shape
    if s0.size != dim or sigma.size != dim:
        raise ValueError('Dimension mismatch')
    if np.any(s0 <= 0) or np.any(sigma < 0) or t <= 0:
        raise ValueError('Positive spot, nonnegative volatility, positive maturity required')
    dt = t / steps
    logchanges = (r-q-0.5*sigma**2)*dt + sigma*np.sqrt(dt)*z
    return np.concatenate([np.broadcast_to(s0, (n,1,dim)),
       np.broadcast_to(s0,(n,1,dim))*np.exp(np.cumsum(logchanges,axis=1))], axis=1)


def bridge_survival(paths, barrier, sigma, t):
    """Conditional no-hit probabilities for continuous upper barrier between sampled dates.
    Exact on each GBM bridge conditional on endpoints for constant volatility.
    """
    x = paths[:, :-1]
    y = paths[:, 1:]
    if np.any(x >= barrier) or np.any(y >= barrier):
        # Endpoint breaches should give 0 probability for that sample, not other samples.
        pass
    safe = (x < barrier) & (y < barrier)
    if sigma <= 0:
        return safe.all(axis=1).astype(float)
    dt = t / (paths.shape[1]-1)
    logx = np.maximum(np.log(barrier / np.maximum(x,1e-15)),0)
    logy = np.maximum(np.log(barrier / np.maximum(y,1e-15)),0)
    p = -np.expm1(-2*logx*logy/(sigma*sigma*dt))
    return np.prod(np.where(safe, p, 0.0), axis=1)


def barrier_mc(s=100, k=100, barrier=120, r=.02, t=1., sigma=.25,
               n=2000, steps=63, seed=42, z=None, knocked=False):
    """Continuously monitored up-and-out call; conditional MC/bridge CI."""
    if s <= 0 or k <= 0 or barrier <= 0 or t <= 0 or sigma < 0:
        raise ValueError('Invalid option inputs')
    if knocked or s >= barrier:
        return dict(price=0., stderr=0., ci_low=0., ci_high=0., ko_probability=1.)
    if z is None: z=shocks(n,steps,1,seed)
    if z.shape[2] != 1: raise ValueError('Barrier option requires one shock factor')
    p=gbm_paths([s],[sigma],r,t,z)[:,:,0]
    surviving=bridge_survival(p,barrier,sigma,t)
    payoff=np.maximum(p[:,-1]-k,0.)*surviving
    pv=np.exp(-r*t)*payoff
    mean=float(pv.mean()); se=float(pv.std(ddof=1)/np.sqrt(len(pv)))
    return dict(price=mean,stderr=se,ci_low=max(0,mean-1.96*se),
                ci_high=mean+1.96*se,ko_probability=float(1-surviving.mean()))


def barrier_greeks(s,k,barrier,r,t,sigma,z,knocked=False):
    if knocked or s>=barrier: return dict(delta=0.,vega=0.,gamma=0.)
    h=min(max(.002*s, .01),max((barrier-s)*.20, .001))
    base=barrier_mc(s,k,barrier,r,t,sigma,z=z)['price']
    plus=barrier_mc(s+h,k,barrier,r,t,sigma,z=z)['price']
    minus=barrier_mc(max(.0001,s-h),k,barrier,r,t,sigma,z=z)['price']
    vd=max(.002, sigma*.02)
    vp=barrier_mc(s,k,barrier,r,t,sigma+vd,z=z)['price']
    vm=barrier_mc(s,k,barrier,r,t,max(0,sigma-vd),z=z)['price']
    return dict(delta=(plus-minus)/(2*h),gamma=(plus-2*base+minus)/(h*h),
                vega=(vp-vm)/(sigma+vd-max(0,sigma-vd)))


def vanilla_call(s,k,r,t,sigma):
    if t<=0: return dict(price=max(s-k,0.),delta=float(s>k),vega=0.)
    if sigma<=0:
        forward=s*np.exp(r*t)
        return dict(price=np.exp(-r*t)*max(forward-k,0.),delta=float(forward>k),vega=0.)
    d1=(np.log(s/k)+(r+sigma*sigma/2)*t)/(sigma*np.sqrt(t))
    d2=d1-sigma*np.sqrt(t)
    return dict(price=float(s*norm.cdf(d1)-k*np.exp(-r*t)*norm.cdf(d2)),
                delta=float(norm.cdf(d1)),vega=float(s*norm.pdf(d1)*np.sqrt(t)))


def _positive_corr(corr):
    a=np.asarray(corr,float)
    if a.shape!=(3,3) or not np.allclose(a,a.T) or np.min(np.linalg.eigvalsh(a))<=0:
        raise ValueError('Correlation must be 3x3 symmetric positive definite')
    return a


def rainbow_mc(spots=(78,2650,4), sigmas=(.25,.15,.20), corr=.5,
               r=.02,t=1,n=2000,steps=63, seed=22, z=None, reference=None,
               payoff_notional=100000):
    """Best-of call on maximum *percentage return* of 3 underlyings; payout in USD."""
    s=np.asarray(spots,float); v=np.asarray(sigmas,float)
    if reference is None: reference=np.asarray((78,2650,4),float)
    reference=np.asarray(reference,float)
    if np.isscalar(corr):
        c=np.full((3,3),float(corr));np.fill_diagonal(c,1.)
    else:c=_positive_corr(corr)
    c=_positive_corr(c)
    if z is None:z=shocks(n,steps,3,seed)
    correlated=z@np.linalg.cholesky(c).T
    p=gbm_paths(s,v,r,t,correlated)
    best_return=np.max(p[:,-1,:]/reference-1.,axis=1)
    pv=np.exp(-r*t)*payoff_notional*np.maximum(best_return,0.)
    val=float(np.mean(pv));se=float(np.std(pv,ddof=1)/np.sqrt(len(pv)))
    return dict(price=val,stderr=se,ci_low=val-1.96*se,ci_high=val+1.96*se,
                expected_payoff=float(np.mean(np.maximum(best_return,0.)*payoff_notional)))


def rainbow_greeks(spots,sigmas,corr,r,t,z,reference=(78,2650,4),payoff_notional=100000):
    spots=np.asarray(spots,float);sigmas=np.asarray(sigmas,float)
    base=rainbow_mc(spots,sigmas,corr,r,t,z=z,reference=reference,payoff_notional=payoff_notional)['price']
    ds=[];gs=[]
    for i in range(3):
        h=spots[i]*.005
        up=spots.copy(); dn=spots.copy(); up[i]+=h;dn[i]-=h
        pu=rainbow_mc(up,sigmas,corr,r,t,z=z,reference=reference,payoff_notional=payoff_notional)['price']
        pd=rainbow_mc(dn,sigmas,corr,r,t,z=z,reference=reference,payoff_notional=payoff_notional)['price']
        ds.append((pu-pd)/(2*h));gs.append((pu-2*base+pd)/h**2)
    bump=.005
    pu=rainbow_mc(spots,sigmas+bump,corr,r,t,z=z,reference=reference,payoff_notional=payoff_notional)['price']
    pd=rainbow_mc(spots,np.maximum(.0001,sigmas-bump),corr,r,t,z=z,reference=reference,payoff_notional=payoff_notional)['price']
    cross=np.zeros((3,3))
    for i in range(3):
        cross[i,i]=gs[i]
        for j in range(i+1,3):
            hi,hj=spots[i]*.005,spots[j]*.005
            vals=[]
            for signi,signj in [(1,1),(1,-1),(-1,1),(-1,-1)]:
                ss=spots.copy();ss[i]+=signi*hi;ss[j]+=signj*hj
                vals.append(rainbow_mc(ss,sigmas,corr,r,t,z=z,reference=reference,payoff_notional=payoff_notional)['price'])
            cross[i,j]=cross[j,i]=(vals[0]-vals[1]-vals[2]+vals[3])/(4*hi*hj)
    return dict(delta=np.array(ds),gamma=np.array(gs),cross_gamma=cross,vega_parallel=(pu-pd)/(2*bump))


def simulate_book(days=21, n=1200, seed=17, spike_day=10, vol_multiplier=2.,
                  corr=.5, barrier=100., barrier_strike=78., rainbow_notional=100000,
                  barrier_contracts=-20, rainbow_contracts=-4, cost_bps=1.,hedge_vega=True):
    """Short exotic book; daily delta hedges; vol-spike staged unwind and PnL.
    Barrier units are 1000 barrels/contract; rainbow prices are USD per note.
    Mark-to-market PnL is computed *before* daily rehedging/unwinds.
    """
    rng=np.random.default_rng(seed)
    initial=np.array([78.,2650.,4.]);base_sig=np.array([.25,.15,.20])
    c=np.full((3,3),corr);np.fill_diagonal(c,1.)
    L=np.linalg.cholesky(_positive_corr(c))
    spot=initial.copy(); knocked=False;prev=initial.copy()
    qb=float(barrier_contracts);qr=float(rainbow_contracts);shares=np.zeros(3);vanilla_qty=0.;prev_van=None
    prev_b=None;prev_r=None; rows=[]; total=0.; unreal=0.; costs_total=0.
    mark_z=shocks(n,63,3,seed+100)
    for day in range(days+1):
        if day>0:
            v_market=base_sig*(vol_multiplier if day>=spike_day else 1.)
            daily_z=rng.standard_normal(3)@L.T
            # one daily observation per hedge day, with intraday substeps for barrier status
            # Oil's *total* daily innovation equals daily_z[0], preserving
            # the intended correlation of day-end oil, gold and copper returns.
            sub=rng.standard_normal(4)
            sub=sub-sub.mean()+daily_z[0]/2
            for zz in sub:
                spot[0]*=np.exp((.02-.5*v_market[0]**2)/(252*4)+v_market[0]/np.sqrt(252*4)*zz)
                if spot[0]>=barrier:knocked=True
            spot[1:]*=np.exp((.02-.5*v_market[1:]**2)/252+v_market[1:]/np.sqrt(252)*daily_z[1:])
        v_market=base_sig*(vol_multiplier if day>=spike_day else 1.)
        t=max(1./252, 1-day/252)
        b_z=mark_z[:,:,:1]
        b=barrier_mc(spot[0],barrier_strike,barrier,.02,t,v_market[0],z=b_z,knocked=knocked)
        r=rainbow_mc(spot,v_market,corr,.02,t,z=mark_z,reference=initial,payoff_notional=rainbow_notional)
        gb=barrier_greeks(spot[0],barrier_strike,barrier,.02,t,v_market[0],b_z,knocked)
        vanilla=vanilla_call(spot[0],barrier_strike,.02,t,v_market[0])
        gr=rainbow_greeks(spot,v_market,corr,.02,t,mark_z,reference=initial,payoff_notional=rainbow_notional)
        daily_pnl=0.
        if day>0:
            daily_pnl=qb*1000*(b['price']-prev_b)+qr*(r['price']-prev_r)+float(shares@(spot-prev))+vanilla_qty*(vanilla['price']-prev_van)
        total+=daily_pnl
        # cumulative book PnL is updated using prior-day holdings; positions change after mark.
        target_qb=qb;target_qr=qr
        if day>=spike_day and max(v_market)>.30:
            # Linear unwinding across five trading days after vol-spike detection
            fraction=max(0.,1-(day-spike_day+1)/5)
            target_qb=barrier_contracts*fraction
            target_qr=rainbow_contracts*fraction
        # One oil vanilla call can hedge one scalar *parallel* volatility risk,
        # but cannot neutralize commodity-specific vegas / cross vegas.
        target_vanilla=(- (target_qb*1000*gb['vega']+target_qr*gr['vega_parallel']) / vanilla['vega']) if hedge_vega and vanilla['vega']>1e-8 else 0.
        target_shares=-(target_qb*1000*np.array([gb['delta'],0.,0.])+target_qr*gr['delta'])
        target_shares[0]-=target_vanilla*vanilla['delta']
        hedge_turnover=float(np.sum(np.abs(target_shares-shares)*spot))
        option_turnover=abs(target_qb-qb)*1000*b['price']+abs(target_qr-qr)*r['price']+abs(target_vanilla-vanilla_qty)*vanilla['price']
        fee=(hedge_turnover+option_turnover)*cost_bps/10000
        total-=fee;costs_total+=fee
        rows.append(dict(day=day,oil=spot[0],gold=spot[1],copper=spot[2],
                         oil_vol=v_market[0],barrier_price=b['price'],rainbow_price=r['price'],
                         barrier_delta=gb['delta'],rainbow_delta_oil=gr['delta'][0],
                         rainbow_delta_gold=gr['delta'][1],rainbow_delta_copper=gr['delta'][2],
                         barrier_vega=gb['vega'],rainbow_vega=gr['vega_parallel'],
                         barrier_contracts=target_qb,rainbow_contracts=target_qr,
                         hedge_oil=target_shares[0],hedge_gold=target_shares[1],hedge_copper=target_shares[2],
                         vanilla_hedge=target_vanilla, rainbow_cross_gamma_og=gr['cross_gamma'][0,1],
                         daily_pnl=daily_pnl-fee,cumulative_pnl=total,transaction_cost=fee,
                         knocked_out=knocked,unwound_pct=1-(abs(target_qr/rainbow_contracts) if rainbow_contracts else 1)))
        qb=target_qb;qr=target_qr;shares=target_shares;vanilla_qty=target_vanilla
        prev_b=b['price'];prev_r=r['price'];prev_van=vanilla['price'];prev=spot.copy()
    return pd.DataFrame(rows)


def zero_rate(curve, t):
    maturities=np.asarray(sorted(curve),float)
    rates=np.array([curve[k] for k in sorted(curve)],float)
    return np.interp(t,maturities,rates,left=rates[0],right=rates[-1])


def zero_discount(curve,t):
    return np.exp(-zero_rate(curve,t)*np.asarray(t))


def bond_ytm(price,coupon=5.,maturity=10.,frequency=2):
    times=np.arange(1,int(round(maturity*frequency))+1)/frequency
    cf=np.full(len(times),coupon/frequency);cf[-1]+=100
    f=lambda y:sum(cf/(1+y/frequency)**(times*frequency))-price
    return brentq(f,-.99,2.)


def callable_bond(curve=None,coupon=5.,maturity=10.,call_at=5.,sigma_r=.012,frequency=2):
    """Calibrated recombining additive short-rate tree with issuer call at par.
    Note: unlike a simple PV-min approximation, exercise is decided state-by-state.
    """
    if curve is None:curve={1.:.02,5.:.025,10.:.03}
    if call_at<=0 or call_at>=maturity or sigma_r<0:raise ValueError('Invalid maturity/call date/vol')
    steps=int(round(maturity*frequency));call_step=int(round(call_at*frequency))
    if abs(steps/frequency-maturity)>1e-9 or abs(call_step/frequency-call_at)>1e-9:
        raise ValueError('Call and maturity must align to coupon dates')
    dt=1/frequency
    state=np.array([1.]); rates=[];states=[state.copy()]
    for n in range(steps):
        spread=sigma_r*np.sqrt(dt)*(2*np.arange(n+1)-n)
        target=zero_discount(curve,(n+1)*dt)
        a=-np.log(target/np.sum(state*np.exp(-spread*dt)))/dt
        short=a+spread
        rates.append(short)
        discounted=state*np.exp(-short*dt)
        next_state=np.zeros(n+2)
        next_state[:-1]+=.5*discounted
        next_state[1:]+=.5*discounted
        state=next_state;states.append(state.copy())
    cf=coupon/frequency
    values=np.full(steps+1,100+cf,dtype=float)
    exercise=None
    for n in range(steps-1,-1,-1):
        continuation=np.exp(-rates[n]*dt)*.5*(values[:-1]+values[1:])
        if n==call_step:
            exercise=continuation>100
            values=cf+np.minimum(100.,continuation)
        elif n>0:values=cf+continuation
        else:values=continuation
    times=np.arange(1,steps+1)/frequency
    cash=np.full(steps,cf);cash[-1]+=100
    noncall=float(np.sum(cash*zero_discount(curve,times)))
    # Bond price conditional on no prior call, at issue
    return dict(price=float(values[0]),noncall_price=noncall,
                option_value=noncall-float(values[0]),ytm=bond_ytm(float(values[0]),coupon,maturity,frequency),
                ytc=bond_ytm(float(values[0]),coupon,call_at,frequency),
                short_rates=rates,call_exercise_states=exercise)


def bond_risk(curve=None,coupon=5,maturity=10,call_at=5,sigma_r=.012):
    if curve is None:curve={1.:.02,5.:.025,10.:.03}
    p=callable_bond(curve,coupon,maturity,call_at,sigma_r)['price']
    shift=lambda bp:{k:v+bp/10000 for k,v in curve.items()}
    down=callable_bond(shift(-1),coupon,maturity,call_at,sigma_r)['price']
    up=callable_bond(shift(1),coupon,maturity,call_at,sigma_r)['price']
    dv01=(down-up)/2.  # $ per bp / $100 face
    convexity=(down+up-2*p)/(.0001**2*p)
    return dict(dv01=float(dv01),modified_duration=float(dv01/(p*.0001)),convexity=float(convexity))


def simulate_callable(days=63,face=1_000_000,seed=21,sigma_r=.012,
                      daily_shift_bps=5.,cost_bps=0.25,coupon=5.,base_curve=None):
    """Daily revalued 10y 5% issuer-callable bond; pay-fixed 5y swap rate hedge.
    Futures/swaps PnL from prior holdings and rate moves; recalibration daily.
    Notional: face dollars; bond price is $ per $100.
    """
    rng=np.random.default_rng(seed)
    base={1.:.02,5.:.025,10.:.03} if base_curve is None else dict(base_curve)
    shift=0.;previous_price=None;prev5=None;swap_notional=0.;cumulative=0.;unhedged=0.;total_costs=0.;rows=[]
    for day in range(days+1):
        if day>0:shift+=rng.normal(0,daily_shift_bps)/10000
        curve={k:max(.0001,v+shift) for k,v in base.items()}
        m=callable_bond(curve,coupon=coupon,sigma_r=sigma_r)
        risk=bond_risk(curve,coupon=coupon,sigma_r=sigma_r)
        price=m['price']*face/100
        r5=curve[5.]
        # Swap annuity per dollar notional at 5yr, semiannual discounted par swap
        annuity=float(np.sum(.5*zero_discount(curve,np.arange(1,11)/2)))
        bond_dv01=risk['dv01']*face/100
        target_swap=bond_dv01/(annuity*.0001)
        bond_pnl=0. if previous_price is None else price-previous_price
        swap_pnl=0. if prev5 is None else swap_notional*annuity*(r5-prev5)
        trading_cost=abs(target_swap-swap_notional)*cost_bps/10000
        cumulative+=bond_pnl+swap_pnl-trading_cost
        unhedged+=bond_pnl;total_costs+=trading_cost
        rows.append(dict(day=day,rate_5y=r5,curve_shift_bps=shift*1e4,
             callable_price=m['price'],noncall_price=m['noncall_price'],
             option_value=m['option_value'],ytm=m['ytm'],ytc=m['ytc'],
             bond_dv01_usd=bond_dv01,swap_notional=target_swap,
             bond_pnl=bond_pnl,swap_pnl=swap_pnl,trading_cost=trading_cost,
             daily_pnl=bond_pnl+swap_pnl-trading_cost,hedged_pnl=cumulative,
             unhedged_pnl=unhedged))
        previous_price=price;prev5=r5;swap_notional=target_swap
    return pd.DataFrame(rows)


def simulate_barrier_hedge(days=21,s0=100,k=100,barrier=120,r=.02,t=1,sigma=.25,
                           n=2000,seed=31,contracts=-1000,cost_bps=1., hedge_vega=True):
    """Short continuously monitored barrier exposure: stock/vanilla delta-vega hedge.
    Rebalance daily, mark prior positions before any trade. Vanilla hedge K = barrier strike.
    """
    rng=np.random.default_rng(seed)
    market=s0;knocked=False;stock=0.;vanilla_qty=0.;last_b=None;last_c=None;previous=s0
    total=0.;total_cost=0.;rows=[]
    z=shocks(n,63,1,seed+10)
    for day in range(days+1):
        if day>0:
            for shock in rng.standard_normal(4):
                market*=np.exp((r-.5*sigma**2)/(252*4)+sigma*np.sqrt(1/(252*4))*shock)
                if market>=barrier:knocked=True
        tau=max(t-day/252,1/252)
        b=barrier_mc(market,k,barrier,r,tau,sigma,z=z,knocked=knocked)
        greeks=barrier_greeks(market,k,barrier,r,tau,sigma,z,knocked=knocked)
        van=vanilla_call(market,k,r,tau,sigma)
        pnl_before=0. if day==0 else contracts*(b['price']-last_b)+stock*(market-previous)+vanilla_qty*(van['price']-last_c)
        target_van=(-contracts*greeks['vega']/van['vega']) if hedge_vega and van['vega']>1e-8 else 0.
        target_stock=-contracts*greeks['delta']-target_van*van['delta']
        turnover=abs(target_stock-stock)*market+abs(target_van-vanilla_qty)*van['price']
        cost=turnover*cost_bps/10000
        total+=pnl_before-cost;total_cost+=cost
        rows.append(dict(day=day,spot=market,barrier_price=b['price'],vanilla_price=van['price'],
            delta=greeks['delta'],vega=greeks['vega'],gamma=greeks['gamma'],
            knock_out_prob=b['ko_probability'],knocked_out=knocked,
            stock_hedge=target_stock,vanilla_hedge=target_van,
            daily_pnl=pnl_before-cost,cumulative_pnl=total,cost=cost))
        last_b=b['price'];last_c=van['price'];previous=market;stock=target_stock;vanilla_qty=target_van
    return pd.DataFrame(rows)

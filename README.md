# Exotics Trading — 3 Jupyter Projects + 3 Streamlit Applications

Three independent, interview-ready quantitative finance case studies, based on the three **Exotic Trader** projects in the supplied course briefs. **All inputs and results are synthetic.** Nothing is a live quote or a trading recommendation.

## Deliverables

| Source | Project notebook | Streamlit app | What it implements |
|---|---|---|---|
| Commodities Project 3 | `notebooks/01_Commodity_Exotic_Book.ipynb` | `app_01_exotic_book.py` | Oil knock-out call + 3-commodity best-of rainbow book; correlated MC, Greeks/cross-gamma, oil vanilla proxy-vega hedge, 21 days, volatility doubling on day 10, 5-day unwind, transaction-cost-aware P&L, CSV export |
| FICC Exotic Trader | `notebooks/02_Callable_Bond.ipynb` | `app_02_callable_bond.py` | 10-year, 5% semiannual coupon issuer-callable bond; calibrated short-rate lattice with call at 5 years, YTC/YTM, effective DV01, 63-day pay-fixed swap hedging, CSV export |
| Equity Derivatives Exotic Trader | `notebooks/03_Barrier_Pricing_Hedging.ipynb` | `app_03_barrier_hedging.py` | One-year up-and-out call; antithetic Monte Carlo + Brownian bridges, 95% confidence intervals, delta/vega/gamma, 21-day stock and vanilla-call hedge, P&L, CSV export |

## Run locally

Install Python 3.10+ and run the following from this folder:

```bash
python -m pip install -r requirements.txt
streamlit run app_01_exotic_book.py
# In another session, or stop the first app:
streamlit run app_02_callable_bond.py
streamlit run app_03_barrier_hedging.py
```

You can also open each `.ipynb` from the repository root using JupyterLab, VS Code or Colab (in Colab, upload the `engines` folder as well). Notebook code uses `engines/models.py` directly and charts work without Streamlit.

## Numerical model conventions

- **Project 1:** oil $78/bbl, gold $2,650/oz, copper $4/lb; 25%/15%/20% volatility and 0.5 pairwise correlations. The brief does not specify oil option strike/barrier, rainbow payoff conventions, position sizes, financing, risk-free rates or fees: this solution sets **K=$78, upper B=$100, $100K payoff notional per rainbow note, 1,000 barrels per oil option, 2% risk-free rate, and configurable transaction costs**. Rainbow is a best-of *percentage-return* call, not a maximum of unequal-dollar underlying spot prices. Cholesky correlated GBM with antithetic sampling. The 2× volatility shock occurs on day 10 and shorts are unwound in 5 equal steps once oil volatility exceeds 30%. The simulated realized oil barrier is monitored at four points per hedge day, whereas valuation uses continuous Brownian-bridge survival. A single oil vanilla call hedges *parallel volatility proxy*, not all three commodity-specific vegas.
- **Project 2:** source specifies $100 par, 5% coupon semiannual, 10-year maturity and issuer par call after year 5, with 2%/2.5%/3% 1/5/10-year curve rates. The brief provides a simplified `min` pricing approximation. To capture state-dependent exercise, this solution instead calibrates a **20-step recombining additive short-rate lattice** to interpolated discount factors and exercises at year 5 in each state. The 5-year pay-fixed swap hedge uses a first-order par-rate annuity approximation with the 5-year zero yield as a swap-rate proxy. It omits curve-basis, carry, credit, issuer spread, and market impact. Callable price is quoted per $100 par; simulated P&L is scaled to face value.
- **Project 3:** 1-year European up-and-out call, **S=100, K=100, B=120, r=2%, sigma=25%**, 21 trading-day hedge horizon. Pricing uses a one-year path over **63 MC time steps**, continuously monitored via Brownian-bridge conditional survival (vs the original brief's potentially ambiguous 21 path steps). Vanilla option for vega hedging is European at the same strike and residual maturity. Realized spot path uses four observed substeps per hedge day. Greeks use finite differences and common random numbers; MC 95% confidence intervals are sampling-noise intervals. Hedges are rebalanced at daily marks and include turnover costs. Pricing and hedging are indicative, not production-grade.

## Validation

- Executed all three notebooks from top to bottom using `nbclient` (saved plots and computed results inside the notebooks).
- Unit tests in `tests/test_engines.py` cover payoff sanity checks, correlation/cross-gamma output, callable exercise bounds, and finite results across 3 daily simulations.
- Streamlit UI source files were syntax-checked. **Streamlit itself could not be installed/run in the build environment because the package index was unavailable**; the UI will require `pip install -r requirements.txt` in an internet-connected environment before local execution or deployment.

Run `python -m pytest -q` to repeat tests.

## Deployment

Create a GitHub repository containing this folder's files. On [Streamlit Community Cloud](https://share.streamlit.io), deploy **three apps** with the entry points `app_01_exotic_book.py`, `app_02_callable_bond.py` and `app_03_barrier_hedging.py`. Streamlit Community Cloud uses the root `requirements.txt`. You can also deploy one at a time; keep the entire `engines/` folder in each deployment.

For interviews: explain Greek units; why delta jumps around barriers; why correlation affects best-of payouts; the issuer's call option and callable negative convexity; where discrete hedges, funding, jump risk, and execution costs make theoretical hedges imperfect.

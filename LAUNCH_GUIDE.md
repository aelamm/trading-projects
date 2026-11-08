# Launch guide (3 separate Streamlit apps)

1. Install Python 3.10 or newer.
2. Unzip the project.
3. Open a terminal in the unzipped folder (the folder that has `engines/` and `requirements.txt`).
4. Run: `python -m pip install -r requirements.txt`.
5. Run one of the three commands below. Streamlit opens a local URL (usually http://localhost:8501).

| Project | Command |
|---|---|
| Commodity Exotic Book | `streamlit run app_01_exotic_book.py` |
| Callable Bond | `streamlit run app_02_callable_bond.py` |
| Equity Barrier | `streamlit run app_03_barrier_hedging.py` |

Open a notebook in JupyterLab/VS Code by loading `notebooks/01_Commodity_Exotic_Book.ipynb`, `notebooks/02_Callable_Bond.ipynb`, or `notebooks/03_Barrier_Pricing_Hedging.ipynb`. All have saved executed results and charts.

To deploy, push the full directory to GitHub and create a Streamlit Community Cloud deployment for each of the three app files.

The programs demonstrate synthetic research scenarios only. The apps have been syntax-checked, but could not be launched in the build environment because Streamlit was not available to install offline.
